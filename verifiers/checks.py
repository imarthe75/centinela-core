import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List

CUMPLE, NO_CUMPLE, NO_EVALUADO = "CUMPLE", "NO_CUMPLE", "NO_EVALUADO"
SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "__pycache__", ".venv", "venv", "data"}


@dataclass
class Result:
    verifier: str
    status: str
    method: str                      # "static" (decided from the text) or "heuristic" (a pattern that can miss cases)
    detail: List[str] = field(default_factory=list)
    checked: int = 0                 # how many items were actually examined (0 + CUMPLE would be a lie, so it is NO_EVALUADO)


def _files(root: Path, suffixes) -> List[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        out += [Path(dirpath) / f for f in filenames if f.endswith(tuple(suffixes))]
    return sorted(out)


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


_CREATE_TABLE = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>(?:"?[\w]+"?\.)?"?[\w]+"?)\s*\((?P<body>.*?)\)\s*(?:;|PARTITION|INHERITS|WITH|TABLESPACE|$)',
                           re.IGNORECASE | re.DOTALL)


def _split_columns(body: str) -> List[str]:
    parts, depth, cur = [], 0, []
    for ch in body:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


def pk_uuid(root: Path) -> Result:
    """Every table created in a .sql file has a primary key of type uuid (no integer/bigint/serial/identity)."""
    bad, checked = [], 0
    for f in _files(root, (".sql",)):
        sql = _strip_sql_comments(f.read_text(encoding="utf-8", errors="replace"))
        for m in _CREATE_TABLE.finditer(sql):
            name, cols = m.group("name").replace('"', ""), _split_columns(m.group("body"))
            pk_cols = []
            for c in cols:
                mt = re.match(r'^PRIMARY\s+KEY\s*\(([^)]*)\)', c, re.IGNORECASE)
                if mt:
                    pk_cols += [x.strip().strip('"') for x in mt.group(1).split(",")]
            for c in cols:
                cm = re.match(r'^"?(\w+)"?\s+([\w\[\]\(\), ]+?)(?:\s|$)(.*)$', c, re.DOTALL)
                if not cm or cm.group(1).upper() in ("CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "EXCLUDE", "LIKE"):
                    continue
                col, typ, rest = cm.group(1), cm.group(2).strip().lower(), cm.group(3)
                is_pk = bool(re.search(r"PRIMARY\s+KEY", rest, re.IGNORECASE)) or col in pk_cols
                if not is_pk:
                    continue
                checked += 1
                if not typ.startswith("uuid") or re.search(r"GENERATED\s+(ALWAYS|BY\s+DEFAULT)\s+AS\s+IDENTITY", rest, re.IGNORECASE):
                    bad.append(f"{f.relative_to(root)}: {name}.{col} es {typ or '?'} (se esperaba uuid)")
    if checked == 0:
        return Result("pk_uuid", NO_EVALUADO, "static", ["no se encontró ninguna llave primaria en archivos .sql"], 0)
    return Result("pk_uuid", NO_CUMPLE if bad else CUMPLE, "static", bad, checked)


_STATEFUL = re.compile(r"(postgres|pgvector|mysql|mariadb|mongo|valkey|redis|seaweed|minio|elasticsearch|opensearch|rabbitmq|kafka|redpanda|clickhouse)", re.IGNORECASE)


def compose_volumes(root: Path, data_root: str = None) -> Result:
    """Stateful services (databases, caches, object stores) persist to a host folder under ./data, not to a named volume or elsewhere."""
    import yaml
    data_root = (data_root or os.getenv("DATA_ROOT", "./data")).rstrip("/")
    bad, checked = [], 0
    for f in [p for p in _files(root, (".yml", ".yaml")) if "compose" in p.name.lower()]:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            return Result("compose_volumes", NO_EVALUADO, "static", [f"{f.relative_to(root)}: YAML inválido ({e})"], 0)
        for name, svc in (doc.get("services") or {}).items():
            if not isinstance(svc, dict) or not _STATEFUL.search(str(svc.get("image", ""))):
                continue
            checked += 1
            vols = [v for v in (svc.get("volumes") or [])]
            ok = False
            for v in vols:
                src = (v.get("source") if isinstance(v, dict) else str(v).split(":")[0]) or ""
                if src.startswith(data_root + "/") or src == data_root:
                    ok = True
            if not ok:
                bad.append(f"{f.relative_to(root)}: el servicio con estado '{name}' ({svc.get('image')}) no persiste en {data_root}/…")
    if checked == 0:
        return Result("compose_volumes", NO_EVALUADO, "static", ["ningún servicio con estado en archivos compose"], 0)
    return Result("compose_volumes", NO_CUMPLE if bad else CUMPLE, "static", bad, checked)


def audit_triggers(root: Path) -> Result:
    """HEURISTIC: every table created in .sql files has some trigger whose name mentions 'audit'/'auditoria' on it, or is enabled with auditoria.habilitar_auditoria('schema.table') / asignar_triggers(...). It does not prove the
    trigger function logs the right thing; it proves a trigger was declared."""
    tables, trig = {}, set()
    for f in _files(root, (".sql",)):
        sql = _strip_sql_comments(f.read_text(encoding="utf-8", errors="replace"))
        for m in _CREATE_TABLE.finditer(sql):
            qualified = m.group("name").replace('"', "").lower()
            if qualified.startswith(("auditoria.", "auditoria_control.")):
                continue   # the audit installer's own tables (log, partitions, anchor) are not audited by themselves
            tables[qualified.split(".")[-1]] = f"{f.relative_to(root)}"
        for m in re.finditer(r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+"?(\w+)"?.*?\bON\s+(?:"?\w+"?\.)?"?(\w+)"?', sql, re.IGNORECASE | re.DOTALL):
            if re.search(r"audit", m.group(1), re.IGNORECASE):
                trig.add(m.group(2).lower())
        # The standard installer enables auditing per table with a function call instead of a CREATE TRIGGER statement.
        for m in re.finditer(r"auditoria\.(?:habilitar_auditoria|asignar_triggers)\s*\(\s*'(?:\"?\w+\"?\.)?\"?(\w+)\"?'", sql, re.IGNORECASE):
            trig.add(m.group(1).lower())
    own = {t: f for t, f in tables.items() if t not in ("log_auditoria",)}
    if not own:
        return Result("audit_triggers", NO_EVALUADO, "heuristic", ["no hay tablas en archivos .sql"], 0)
    missing = [f"{f}: la tabla '{t}' no tiene trigger de auditoría declarado" for t, f in sorted(own.items()) if t not in trig]
    return Result("audit_triggers", NO_CUMPLE if missing else CUMPLE, "heuristic", missing, len(own))


_ROUTE_PY = re.compile(r"^@(?:\w+)\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)", re.MULTILINE)


def endpoints_auth(root: Path, auth_regex: str = None) -> Result:
    """HEURISTIC, FastAPI only: every mutating route (post/put/patch/delete) declares an authentication dependency matching AUTH_REGEX
    (default: Depends(<name containing auth|user|token|oidc|principal|require>)). Other frameworks are NOT evaluated (not guessed)."""
    rx = re.compile(auth_regex or os.getenv("AUTH_REGEX", r"Depends\(\s*\w*(auth|user|token|oidc|principal|require|verify)\w*"), re.IGNORECASE)
    bad, checked = [], 0
    for f in _files(root, (".py",)):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in _ROUTE_PY.finditer(text):
            if m.group(1) == "get":
                continue
            checked += 1
            end = text.find("\n@", m.end())
            block = text[m.start(): end if end != -1 else len(text)]
            sig_end = block.find("):")
            signature = block[: sig_end if sig_end != -1 else min(len(block), 600)]
            if not rx.search(m.group(0) + signature):
                bad.append(f"{f.relative_to(root)}: {m.group(1).upper()} {m.group(2)} sin dependencia de autenticación reconocible")
    if checked == 0:
        return Result("endpoints_auth", NO_EVALUADO, "heuristic", ["no se encontraron rutas mutantes de FastAPI (otros frameworks no se evalúan)"], 0)
    return Result("endpoints_auth", NO_CUMPLE if bad else CUMPLE, "heuristic", bad, checked)


# ----------------------------------------------------------------------------- versions_current
_FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent


def _resolved_versions(resolved=None):
    """{tool: {version, major, ...}} from the official sources (or the dict a test injects). Imports the resolver lazily: it does network I/O."""
    if resolved is not None:
        return resolved
    import importlib.util
    spec = importlib.util.spec_from_file_location("latest_versions", _FRAMEWORK_ROOT / "scripts" / "latest_versions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    policy = json.loads((_FRAMEWORK_ROOT / ".agent" / "versions-policy.json").read_text(encoding="utf-8"))
    return mod.resolve_all(policy)


def _mm(v):
    m = re.match(r"^v?(\d+)(?:\.(\d+))?", str(v))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def versions_current(root: Path, resolved=None) -> Result:
    """A project's manifests use the CURRENT versions (the ones scripts/latest_versions.py resolves today). Examined: package.json (Angular,
    React, TypeScript majors), pom.xml (java release, Spring Boot parent), Dockerfile FROM (node, python, eclipse-temurin) and compose images
    (postgres, pgvector, valkey). A tool whose current version could not be resolved (offline) is reported, never assumed current.
    Behind by one MAJOR (or, for Spring Boot/Python, one minor line) is NO_CUMPLE; exact patch lag is not."""
    cur = _resolved_versions(resolved)
    bad, unresolved, checked = [], set(), 0

    def cmp_major(label, where, found, tool):
        nonlocal checked
        info = cur.get(tool) or {}
        if not info.get("version"):
            unresolved.add(tool)
            return
        fm, cm = _mm(found), _mm(info["version"])
        if not fm:
            return
        checked += 1
        if fm[0] < cm[0]:
            bad.append(f"{where}: {label} {found} (vigente: {info['version']}, canal {info.get('channel')})")

    for f in _files(root, ("package.json",)):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        for pkg, tool in (("@angular/core", "angular"), ("react", "react"), ("typescript", "typescript")):
            if pkg in deps:
                cmp_major(pkg, str(f.relative_to(root)), re.sub(r"^[\^~>=<\s]+", "", str(deps[pkg])), tool)

    for f in _files(root, ("pom.xml",)):
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = str(f.relative_to(root))
        m = re.search(r"<(?:java\.version|maven\.compiler\.release|release)>\s*(\d+)\s*</", text)
        if m:
            cmp_major("Java", rel, m.group(1), "java")
        m = re.search(r"<parent>.*?spring-boot-starter-parent.*?<version>\s*([\d.]+)", text, re.DOTALL)
        if m and cur.get("spring-boot", {}).get("version"):
            checked += 1
            if _mm(m.group(1)) < _mm(cur["spring-boot"]["version"]):
                bad.append(f"{rel}: Spring Boot {m.group(1)} (vigente: {cur['spring-boot']['version']})")
        elif m:
            unresolved.add("spring-boot")

    for f in _files(root, ("Dockerfile", ".dockerfile")) + [p for p in _files(root, (".yml", ".yaml")) if "compose" in p.name.lower()]:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = str(f.relative_to(root))
        for img, tag in re.findall(r"(?:FROM|image:)\s+['\"]?([\w./-]+):v?(\w[\w.\-]*)", text):
            base = img.split("/")[-1]
            if base == "node":
                cmp_major("node (imagen)", rel, tag, "node")
            elif base == "python":
                info = cur.get("python") or {}
                if not _mm(tag):
                    continue
                if not info.get("version"):
                    unresolved.add("python")
                else:
                    checked += 1
                    if _mm(tag) < _mm(info["version"]):
                        bad.append(f"{rel}: python:{tag} (vigente: {info['version']})")
            elif base == "eclipse-temurin":
                cmp_major("Java (imagen)", rel, tag, "java")
            elif base == "postgres":
                cmp_major("postgres (imagen)", rel, tag, "postgresql")
            elif base == "pgvector":
                m = re.match(r"pg(\d+)", tag)
                if m:
                    cmp_major("pgvector (imagen)", rel, m.group(1), "postgresql")
            elif base == "valkey":
                cmp_major("valkey (imagen)", rel, tag, "valkey")

    detail = list(bad)
    if unresolved:
        detail.append(f"no se pudo resolver la versión vigente de: {', '.join(sorted(unresolved))} (¿sin red?): NO se asumió que estuviera al día")
    if bad:
        return Result("versions_current", NO_CUMPLE, "static", detail, checked)
    if checked == 0:
        return Result("versions_current", NO_EVALUADO, "static", detail or ["no se encontró ningún manifiesto con una versión comparable"], 0)
    if unresolved:
        return Result("versions_current", NO_EVALUADO, "static", detail, checked)
    return Result("versions_current", CUMPLE, "static", [], checked)


# ----------------------------------------------------------------------------- honesty / safety verifiers (ADR-0003 D10)
import ast

_TEST_FILE = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py|conftest\.py|[^/]*\.(test|spec)\.(ts|tsx|js|jsx))$")


def _is_test(rel: str) -> bool:
    return bool(_TEST_FILE.search(rel.replace(os.sep, "/"))) or "/tests/" in "/" + rel.replace(os.sep, "/")


def _py_modules(root: Path):
    for f in _files(root, (".py",)):
        rel = str(f.relative_to(root))
        try:
            yield f, rel, ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue


def no_stubs(root: Path) -> Result:
    """HEURISTIC: a function that only declares itself (body = pass / ... / raise NotImplementedError / a docstring) or a TODO/FIXME marker in non-test
    source is unfinished work presented as code. Abstract methods, protocols and overloads are skipped."""
    bad, checked = [], 0
    for f, rel, tree_ in _py_modules(root):
        if _is_test(rel):
            continue
        for node in ast.walk(tree_):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decos = " ".join(ast.unparse(d) for d in node.decorator_list)
            if re.search(r"abstractmethod|overload|Protocol", decos):
                continue
            checked += 1
            body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant) and isinstance(b.value.value, str))]
            only_stub = (not body) or all(isinstance(b, ast.Pass) or (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant) and b.value.value is Ellipsis)
                                          or (isinstance(b, ast.Raise) and "NotImplementedError" in ast.unparse(b)) for b in body)
            if only_stub and node.name != "__init__":
                bad.append(f"{rel}:{node.lineno}: {node.name}() no tiene lógica (pass / ... / NotImplementedError)")
    marker = re.compile(r"(#|//|/\*)\s*(TODO|FIXME|XXX)\b")
    for f in _files(root, (".py", ".java", ".ts", ".tsx", ".js", ".jsx", ".sql", ".sh")):
        rel = str(f.relative_to(root))
        if _is_test(rel):
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if marker.search(line):
                bad.append(f"{rel}:{n}: marcador TODO/FIXME en código entregado")
    if checked == 0 and not bad:
        return Result("no_stubs", NO_EVALUADO, "heuristic", ["no se encontraron funciones Python ni marcadores que revisar"], 0)
    return Result("no_stubs", NO_CUMPLE if bad else CUMPLE, "heuristic", bad, checked)


_DESTRUCTIVE = re.compile(r"\b(flushdb|flushall)\b|\bDROP\s+(TABLE|DATABASE|SCHEMA)\b|\bTRUNCATE\b", re.IGNORECASE)
_TEST_GUARD = re.compile(r"[A-Z_]*TEST[A-Z_]*(HOST|DB|URL|DATABASE)|(HOST|DB|URL|DATABASE)[A-Z_]*TEST|ROLLBACK|rollback\(|tmp_path|tempfile|sqlite:///:memory:|testcontainers", re.IGNORECASE)


def tests_isolated(root: Path) -> Result:
    """HEURISTIC: a test file that runs a destructive operation (flushdb/flushall/DROP/TRUNCATE) must show an isolation guard: a test-only connection variable
    (e.g. APP_TEST_DB_HOST), a rollback, a temp dir or an in-memory database. A test must never inherit its target from the application's environment."""
    bad, checked = [], 0
    for f in _files(root, (".py", ".ts", ".tsx", ".js", ".jsx", ".java")):
        rel = str(f.relative_to(root))
        if not _is_test(rel):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        checked += 1
        hits = [(n, l) for n, l in enumerate(text.splitlines(), 1) if _DESTRUCTIVE.search(l) and not l.lstrip().startswith(("#", "//", "--"))]
        if hits and not _TEST_GUARD.search(text):
            n, l = hits[0]
            bad.append(f"{rel}:{n}: operación destructiva sin guarda de aislamiento ({l.strip()[:60]})")
        if re.search(r"os\.(getenv|environ(\.get)?)\(?\[?\s*['\"](?!\w*TEST)\w*(REDIS|VALKEY|DB|DATABASE|POSTGRES)\w*(HOST|URL|URI)\w*['\"]", text) and hits:
            bad.append(f"{rel}: hereda el destino de la variable de producción en una prueba destructiva")
    if checked == 0:
        return Result("tests_isolated", NO_EVALUADO, "heuristic", ["no se encontraron archivos de prueba"], 0)
    return Result("tests_isolated", NO_CUMPLE if bad else CUMPLE, "heuristic", bad, checked)


def no_silent_except(root: Path) -> Result:
    """STATIC (Python AST): an `except` that catches everything (bare, Exception, BaseException) must re-raise, log the traceback (logger.*, logging.*,
    traceback.print_exc, exc_info=True) or return an explicit error. Swallowing it (pass / continue / returning a success value) hides failures."""
    bad, checked = [], 0
    for f, rel, tree_ in _py_modules(root):
        if _is_test(rel):
            continue
        for node in ast.walk(tree_):
            if not isinstance(node, ast.ExceptHandler):
                continue
            kind = ast.unparse(node.type) if node.type is not None else ""
            if kind not in ("", "Exception", "BaseException"):
                continue
            checked += 1
            src = " ".join(ast.unparse(b) for b in node.body)
            handled = any(isinstance(n, ast.Raise) for b in node.body for n in ast.walk(b)) or re.search(
                r"(logger|logging|log)\.(error|exception|warning|critical)|print_exc|exc_info|traceback\.", src)
            if not handled:
                bad.append(f"{rel}:{node.lineno}: except {kind or '(vacío)'} traga el error sin traza ni relanzar")
    if checked == 0:
        return Result("no_silent_except", NO_EVALUADO, "static", ["no hay bloques except amplios que revisar"], 0)
    return Result("no_silent_except", NO_CUMPLE if bad else CUMPLE, "static", bad, checked)


def webhooks_fail_closed(root: Path) -> Result:
    """HEURISTIC, FastAPI only: a route whose path contains 'webhook' must authenticate the caller and fail closed: compare a configured secret in constant
    time (hmac.compare_digest) AND answer 401/403/503 when the secret is missing or wrong. Other frameworks are NOT evaluated."""
    bad, checked = [], 0
    for f in _files(root, (".py",)):
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in _ROUTE_PY.finditer(text):
            if "webhook" not in m.group(2).lower():
                continue
            checked += 1
            end = text.find("\n@", m.end())
            block = text[m.start(): end if end != -1 else len(text)]
            if not re.search(r"compare_digest", block):
                bad.append(f"{f.relative_to(root)}: {m.group(2)} no compara el secreto en tiempo constante (hmac.compare_digest)")
            if not re.search(r"\b(401|403|503)\b|HTTP_40[13]|HTTP_503", block):
                bad.append(f"{f.relative_to(root)}: {m.group(2)} no responde 401/403/503 cuando falta o no coincide el secreto")
    if checked == 0:
        return Result("webhooks_fail_closed", NO_EVALUADO, "heuristic", ["no se encontraron rutas webhook de FastAPI (otros frameworks no se evalúan)"], 0)
    return Result("webhooks_fail_closed", NO_CUMPLE if bad else CUMPLE, "heuristic", bad, checked)


REGISTRY: Dict[str, Callable[..., Result]] = {"pk_uuid": pk_uuid, "compose_volumes": compose_volumes, "audit_triggers": audit_triggers,
                                              "endpoints_auth": endpoints_auth, "versions_current": versions_current,
                                              "no_stubs": no_stubs, "tests_isolated": tests_isolated, "no_silent_except": no_silent_except,
                                              "webhooks_fail_closed": webhooks_fail_closed}
