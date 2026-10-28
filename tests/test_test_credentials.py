"""VALIDATED WITH AN IN-MEMORY FAKE VAULT ONLY. The real Vault path is exercised by the consumer (centinela-ai) against its real Vault."""
import pytest

from centinela_core import test_credentials as tc


class FakeVault:
    class _V2:
        def __init__(self):
            self.store = {}

        def read_secret_version(self, path, mount_point="secret", raise_on_deleted_version=True):
            if path not in self.store:
                class InvalidPath(Exception):
                    pass
                raise InvalidPath()
            return {"data": {"data": dict(self.store[path])}}

        def create_or_update_secret(self, path, secret, mount_point="secret"):
            self.store[path] = dict(secret)

    def __init__(self):
        v2 = self._V2()
        self.secrets = type("S", (), {"kv": type("K", (), {"v2": v2})()})()
        self.store = v2.store


A = "http://app.example.test/front/login"
LOGIN = {"url": "http://app.example.test/api/auth", "username_field": "correo", "token_header": "Authorization"}
UI = {"url": "http://app.example.test/front/login", "routes": ["http://app.example.test/front/home"]}


@pytest.fixture
def v():
    return FakeVault()


def test_path_uses_namespace_and_slug(monkeypatch):
    monkeypatch.setenv("VAULT_NAMESPACE", "ns-test")
    tc._cfg["namespace"] = None
    assert tc.vault_path(A) == "ns-test/authz/http_app.example.test_front_login"
    tc.configure(namespace="other/")
    try:
        assert tc.vault_path(A).startswith("other/authz/")
    finally:
        tc._cfg["namespace"] = None


def test_update_authz_keeps_login_ui_app_login_and_roles(v):
    tc.set_app_config(A, "http://app.example.test/api", LOGIN, client=v, login_ui=UI)
    tc.upsert_role(A, "Administrador", "a@example.test", "pw", kind="admin", client=v)
    tc.update_authz(A, {"endpoints": ["/x", "/y/1"], "admin_only": ["*/x*"]}, client=v)
    raw = tc.read_raw(A, client=v)
    assert raw["login_ui"]["url"] == UI["url"] and raw["app_login"]["url"] == LOGIN["url"]
    assert raw["endpoints"] == ["/x", "/y/1"] and raw["access_model"]["admin_only"] == ["*/x*"]
    assert raw["roles"][0]["login"]["json"] == {"correo": "a@example.test", "password": "pw"}


def test_set_app_config_is_full_replace(v):
    tc.set_app_config(A, "http://app.example.test/api", LOGIN, client=v, login_ui=UI)
    tc.set_app_config(A, "http://app.example.test/api", None, client=v)
    raw = tc.read_raw(A, client=v)
    assert "login_ui" not in raw and "app_login" not in raw


def test_update_authz_needs_existing_config(v):
    with pytest.raises(tc.CredentialsError):
        tc.update_authz(A, {"endpoints": ["/x"]}, client=v)


def test_update_authz_validates_endpoints(v):
    tc.set_app_config(A, "", LOGIN, client=v)
    with pytest.raises(tc.CredentialsError):
        tc.update_authz(A, {"endpoints": ["no-slash"]}, client=v)


def test_describe_never_returns_secrets(v):
    tc.set_app_config(A, "", LOGIN, client=v)
    tc.upsert_role(A, "Perfil", "u@example.test", "s3cret", client=v)
    d = tc.describe(A, client=v)
    assert "s3cret" not in repr(d) and d["roles"][0]["has_password"] is True


def test_get_profile_returns_secret_and_login_ui(v):
    tc.set_app_config(A, "", LOGIN, client=v, login_ui=UI)
    tc.upsert_role(A, "Perfil", "u@example.test", "s3cret", client=v)
    p = tc.get_profile(A, "perfil", client=v)
    assert p["password"] == "s3cret" and p["login_ui"]["url"] == UI["url"]
    with pytest.raises(tc.CredentialsError):
        tc.get_profile(A, "otro", client=v)


def test_client_factory_is_used_when_no_client_passed(v):
    tc.configure(client_factory=lambda: v)
    try:
        tc.set_app_config(A, "", LOGIN)
        assert tc.read_raw(A)["app_login"]["username_field"] == "correo"
    finally:
        tc._cfg["client_factory"] = None


def test_role_validation(v):
    with pytest.raises(tc.CredentialsError):
        tc.upsert_role(A, "A", "u", "p", client=v)
    with pytest.raises(tc.CredentialsError):
        tc.upsert_role(A, "Perfil", "u", "", client=v)
    with pytest.raises(tc.CredentialsError):
        tc.upsert_role(A, "Perfil", "u", "p", kind="root", client=v)
