"""
Per-application test credentials, one set per profile (role), stored ONLY in Vault (KV v2): `<namespace>/authz/<asset>`.

Shape (flat dict, existing keys are preserved):
  base_url        https://app.example/api
  app_login       {url, method, body, username_field, password_field, token_json_path, token_header, extra_fields}  shared by every role
  login_ui        {url, routes, user_selector?, pass_selector?, submit_selector?}                                  browser login screen
  roles           [{name, kind, username, password, login}]   `login` is derived from app_login + the role's username/password
  endpoints / openapi_url / access_model                      what an authorization replay should exercise
  source_assets   [asset names whose code was used to discover profiles]   (non secret)

Secrets are never returned by `describe()`: usernames and a `has_password` flag only.

Two ways to update the app-level configuration:
  * `set_app_config()`  FULL replace of base_url/app_login/login_ui (what a form that shows every field sends). A field passed as None is removed.
  * `update_authz()`    PARTIAL: only endpoints/openapi_url/access_model; nothing else is touched.
Use the partial one from scripts. (A script that called set_app_config just to change the endpoints silently removed app_login and login_ui.)

Configuration (module level, optional): `configure(namespace=..., client_factory=...)`. Defaults: namespace from $VAULT_NAMESPACE
(default "centinela"), client from $VAULT_ADDR/$VAULT_TOKEN.
"""
import os
import re
from typing import Any, Callable, Dict, List, Optional

_ROLE_RE = re.compile(r"^[^\x00-\x1f]{2,80}$")
_FIELD_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,60}$")
_URL_RE = re.compile(r"^https?://[^\s]+$")

_cfg: Dict[str, Any] = {"namespace": None, "client_factory": None}


class CredentialsError(ValueError):
    pass


def configure(namespace: Optional[str] = None, client_factory: Optional[Callable[[], Any]] = None) -> None:
    if namespace is not None:
        _cfg["namespace"] = namespace.strip("/")
    if client_factory is not None:
        _cfg["client_factory"] = client_factory


def _namespace() -> str:
    return _cfg["namespace"] or os.getenv("VAULT_NAMESPACE", "centinela").strip("/")


def default_vault_client():
    import hvac
    client = hvac.Client(url=os.getenv("VAULT_ADDR", ""), token=os.getenv("VAULT_TOKEN", ""), timeout=10)
    if not client.is_authenticated():
        raise CredentialsError("Vault no está disponible o el token no es válido")
    return client


def _client(client=None):
    if client is not None:
        return client
    return (_cfg["client_factory"] or default_vault_client)()


def vault_key(asset_name: str) -> str:
    """Asset names can be URLs or repository paths; a KV path must not contain `//` or `:`."""
    return re.sub(r"[^A-Za-z0-9._@-]+", "_", asset_name).strip("_") or "asset"


def vault_path(asset_name: str) -> str:
    return "/".join([_namespace(), "authz", vault_key(asset_name)])


def read_raw(asset_name: str, client=None) -> Dict[str, Any]:
    client = _client(client)
    try:
        data = client.secrets.kv.v2.read_secret_version(path=vault_path(asset_name), mount_point="secret", raise_on_deleted_version=True)["data"]["data"]
    except Exception as e:
        if e.__class__.__name__ == "InvalidPath":
            return {}
        raise
    return data or {}


def _write(asset_name: str, data: Dict[str, Any], client) -> None:
    client.secrets.kv.v2.create_or_update_secret(path=vault_path(asset_name), secret=data, mount_point="secret")


def _derive_login(app_login: Optional[Dict[str, Any]], username: str, password: str) -> Optional[Dict[str, Any]]:
    if not app_login or not app_login.get("url"):
        return None
    body_key = "json" if app_login.get("body", "json") == "json" else "form"
    body = {app_login.get("username_field", "username"): username, app_login.get("password_field", "password"): password}
    body.update(app_login.get("extra_fields") or {})
    login = {"url": app_login["url"], "method": (app_login.get("method") or "POST").upper(), body_key: body,
             "token_json_path": app_login.get("token_json_path") or "access_token", "verify": False}
    if app_login.get("token_header"):
        login["token_header"] = app_login["token_header"]
    return login


def describe(asset_name: str, client=None) -> Dict[str, Any]:
    """What a UI may see: no password, no token."""
    data = read_raw(asset_name, client)
    login = data.get("app_login") or {}
    return {
        "base_url": data.get("base_url", ""),
        "app_login": {k: login.get(k) for k in ("url", "method", "body", "username_field", "password_field", "token_json_path", "token_header", "extra_fields")} if login else None,
        "roles": [{"name": r.get("name"), "kind": r.get("kind", "user"), "username": r.get("username", ""),
                   "has_password": bool(r.get("password")), "has_token": bool(r.get("token"))} for r in data.get("roles", [])],
        "login_ui": data.get("login_ui"),
        "authz": {"endpoints": data.get("endpoints", []), "openapi_url": data.get("openapi_url", ""),
                  "admin_only": (data.get("access_model") or {}).get("admin_only", [])},
        "source_assets": data.get("source_assets", []),
    }


def _clean_login_ui(ui: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not ui or not (ui.get("url") or "").strip():
        return None
    if not _URL_RE.match(ui["url"].strip()):
        raise CredentialsError("La URL de la pantalla de inicio de sesión debe ser http(s)")
    routes = [r.strip() for r in (ui.get("routes") or []) if r and r.strip()]
    if any(not _URL_RE.match(r) for r in routes):
        raise CredentialsError("Cada ruta a visitar debe ser una URL http(s) completa")
    return {"url": ui["url"].strip(), "routes": routes[:25],
            **{k: ui[k].strip() for k in ("user_selector", "pass_selector", "submit_selector") if (ui.get(k) or "").strip()}}


def _apply_authz(data: Dict[str, Any], authz: Dict[str, Any]) -> None:
    eps = [e.strip() for e in (authz.get("endpoints") or []) if e and e.strip()]
    if any(not e.startswith("/") for e in eps):
        raise CredentialsError("Cada endpoint debe empezar con «/» (ruta relativa a la URL base)")
    if (authz.get("openapi_url") or "").strip() and not _URL_RE.match(authz["openapi_url"].strip()):
        raise CredentialsError("La URL de OpenAPI debe ser http(s)")
    data["endpoints"] = eps[:400]
    if (authz.get("openapi_url") or "").strip():
        data["openapi_url"] = authz["openapi_url"].strip()
    else:
        data.pop("openapi_url", None)
    admin_only = [a.strip() for a in (authz.get("admin_only") or []) if a and a.strip()]
    model = dict(data.get("access_model") or {})
    if admin_only:
        model["admin_only"] = admin_only
    else:
        model.pop("admin_only", None)
    if model:
        data["access_model"] = model
    else:
        data.pop("access_model", None)


def set_app_config(asset_name: str, base_url: str, app_login: Optional[Dict[str, Any]], client=None, login_ui: Optional[Dict[str, Any]] = None,
                   authz: Optional[Dict[str, Any]] = None) -> None:
    """FULL replace of base_url/app_login/login_ui (None removes them). `authz` is applied only when given."""
    client = _client(client)
    if base_url and not _URL_RE.match(base_url):
        raise CredentialsError("base_url debe ser una URL http(s)")
    login = None
    if app_login and (app_login.get("url") or "").strip():
        if not _URL_RE.match(app_login["url"]):
            raise CredentialsError("La URL de inicio de sesión debe ser http(s)")
        for f in ("username_field", "password_field"):
            if app_login.get(f) and not _FIELD_RE.match(app_login[f]):
                raise CredentialsError(f"{f} contiene caracteres no permitidos")
        login = {"url": app_login["url"].strip(), "method": (app_login.get("method") or "POST").upper(),
                 "body": "form" if app_login.get("body") == "form" else "json",
                 "username_field": app_login.get("username_field") or "username", "password_field": app_login.get("password_field") or "password",
                 "token_json_path": app_login.get("token_json_path") or "access_token",
                 "token_header": (app_login.get("token_header") or "").strip(),
                 "extra_fields": {str(k): str(v) for k, v in (app_login.get("extra_fields") or {}).items()}}
    ui = _clean_login_ui(login_ui)
    data = read_raw(asset_name, client)
    if authz is not None:
        _apply_authz(data, authz)
    data["base_url"] = (base_url or "").strip()
    if ui:
        data["login_ui"] = ui
    else:
        data.pop("login_ui", None)
    if login:
        data["app_login"] = login
    else:
        data.pop("app_login", None)
    for r in data.get("roles", []):          # roles keep their username/password; only the derived login changes
        if r.get("password") and r.get("username"):
            r["login"] = _derive_login(login, r["username"], r["password"]) or r.get("login")
    _write(asset_name, data, client)


def update_authz(asset_name: str, authz: Dict[str, Any], client=None) -> None:
    """PARTIAL update: endpoints / openapi_url / access_model.admin_only. base_url, app_login, login_ui and roles stay as they are."""
    client = _client(client)
    data = read_raw(asset_name, client)
    if not data:
        raise CredentialsError("El activo no tiene configuración de pruebas: guarda primero la configuración del aplicativo")
    _apply_authz(data, authz)
    _write(asset_name, data, client)


def upsert_role(asset_name: str, role: str, username: str, password: str, kind: str = "user", client=None) -> None:
    role, username = (role or "").strip(), (username or "").strip()
    if not _ROLE_RE.match(role):
        raise CredentialsError("Indica el nombre del perfil (2 a 80 caracteres)")
    if not username:
        raise CredentialsError("Indica el usuario de este perfil")
    if kind not in ("admin", "user", "readonly"):
        raise CredentialsError("kind debe ser admin, user o readonly")
    client = _client(client)
    data = read_raw(asset_name, client)
    roles: List[Dict[str, Any]] = data.get("roles", [])
    current = next((r for r in roles if (r.get("name") or "").lower() == role.lower()), None)
    if not password:
        if not current or not current.get("password"):
            raise CredentialsError("Indica la contraseña de este perfil")
        password = current["password"]          # editing the username only: keep the stored password
    entry = {"name": role, "kind": kind, "username": username, "password": password,
             "login": _derive_login(data.get("app_login"), username, password)}
    if current:
        roles[roles.index(current)] = entry
    else:
        roles.append(entry)
    data["roles"] = roles
    _write(asset_name, data, client)


def delete_role(asset_name: str, role: str, client=None) -> bool:
    client = _client(client)
    data = read_raw(asset_name, client)
    before = len(data.get("roles", []))
    data["roles"] = [r for r in data.get("roles", []) if (r.get("name") or "").lower() != (role or "").lower()]
    if len(data["roles"]) == before:
        return False
    _write(asset_name, data, client)
    return True


def set_source_assets(asset_name: str, sources: List[str], client=None) -> None:
    client = _client(client)
    data = read_raw(asset_name, client)
    data["source_assets"] = sorted({s for s in sources if s})
    _write(asset_name, data, client)


def get_profile(asset_name: str, role: str, client=None) -> Dict[str, Any]:
    """One profile WITH its secret, for a runner that must log in. Callers must not log or persist the returned password."""
    data = read_raw(asset_name, client)
    entry = next((r for r in data.get("roles", []) if (r.get("name") or "").lower() == (role or "").lower()), None)
    if not entry or not entry.get("username") or not entry.get("password"):
        raise CredentialsError(f"El perfil «{role}» no tiene usuario y contraseña guardados")
    return {"name": entry["name"], "kind": entry.get("kind", "user"), "username": entry["username"], "password": entry["password"],
            "login_ui": data.get("login_ui"), "app_login": data.get("app_login"), "base_url": data.get("base_url", "")}
