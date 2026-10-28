"""build_command is pure. run_script runs a REAL sibling container when the docker CLI and a daemon are reachable; otherwise it is skipped
(and the skip is visible in the test report, not hidden)."""
import shutil
import subprocess

import pytest

from centinela_core.browser import BrowserRunError, build_command, run_script

SECRET = "pw-do-not-leak"


def test_command_never_carries_the_config():
    cmd = build_command("img:1", "print(1)", network="net", volumes=["/tmp:/tmp"])
    assert SECRET not in " ".join(cmd)
    assert cmd[:4] == ["docker", "run", "-i", "--rm"] and "--network" in cmd and cmd[-3:] == ["img:1", "-c", "print(1)"]


def _docker_ok():
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


needs_docker = pytest.mark.skipif(not _docker_ok(), reason="sin docker CLI/daemon en este entorno")
IMAGE = "python:3.12-slim"


@needs_docker
def test_real_container_reads_stdin_and_returns_last_json_line():
    script = "import json,sys\ncfg=json.load(sys.stdin)\nprint('ruido')\nprint(json.dumps({'got': cfg['user'], 'has_pw': bool(cfg['pw'])}))"
    out = run_script(script, {"user": "u", "pw": SECRET}, IMAGE, timeout=120)
    assert out["got"] == "u" and out["has_pw"] is True


@needs_docker
def test_timeout_removes_the_container():
    with pytest.raises(BrowserRunError) as ei:
        run_script("import time; time.sleep(120)", {}, IMAGE, timeout=8, name_prefix="core-test-timeout")
    name = str(ei.value).split("eliminado: ")[1].rstrip(")")
    left = subprocess.run(["docker", "ps", "-a", "-q", "--filter", f"name={name}"], capture_output=True, text=True).stdout.strip()
    assert left == "", f"quedó el contenedor {name}"


@needs_docker
def test_real_container_failure_is_reported():
    with pytest.raises(BrowserRunError):
        run_script("import sys; sys.exit(3)", {}, IMAGE, timeout=120)
