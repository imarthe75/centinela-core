"""Isolated browser runner: execute a Playwright script in a SIBLING container (docker run on the host daemon), so Chromium never
enters the caller's image.

Contract of the script that runs inside the container:
  * reads ONE JSON document from stdin (the configuration, credentials included);
  * prints ONE JSON document as the LAST line of stdout;
  * anything else goes to stderr.
Credentials travel on stdin only, never in argv or environment variables, so `docker inspect` / `ps` do not show them.
"""
import json
import subprocess
import uuid
from typing import Any, Dict, List, Optional


class BrowserRunError(RuntimeError):
    pass


def build_command(image: str, script: str, network: Optional[str] = None, memory: str = "1g", cpus: str = "1",
                  volumes: Optional[List[str]] = None, entrypoint: str = "python", name: Optional[str] = None) -> List[str]:
    cmd = ["docker", "run", "-i", "--rm", "--memory", memory, "--cpus", cpus]
    if name:
        cmd += ["--name", name]
    if network:
        cmd += ["--network", network]
    for v in volumes or []:
        cmd += ["-v", v]
    cmd += ["--entrypoint", entrypoint, image, "-c", script]
    return cmd


def run_script(script: str, config: Dict[str, Any], image: str, network: Optional[str] = None, timeout: int = 240,
               memory: str = "1g", cpus: str = "1", volumes: Optional[List[str]] = None, name_prefix: str = "centinela-browser") -> Dict[str, Any]:
    """Run `script` (Python source) in `image`; return the JSON printed on its last stdout line, plus stderr tail under `_stderr`."""
    name = f"{name_prefix}-{uuid.uuid4().hex[:12]}"
    cmd = build_command(image, script, network=network, memory=memory, cpus=cpus, volumes=volumes, name=name)
    try:
        proc = subprocess.run(cmd, input=json.dumps(config), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # `--rm` does not fire when the client is killed: remove the container by name or it keeps running (orphan).
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        raise BrowserRunError(f"el contenedor del navegador superó {timeout}s (eliminado: {name})") from e
    if proc.returncode != 0:
        raise BrowserRunError(f"el contenedor terminó con código {proc.returncode}: {(proc.stderr or '')[-400:]}")
    lines = [l for l in (proc.stdout or "").strip().splitlines() if l.strip()]
    if not lines:
        raise BrowserRunError(f"el contenedor no imprimió resultado: {(proc.stderr or '')[-400:]}")
    try:
        out = json.loads(lines[-1])
    except json.JSONDecodeError as e:
        raise BrowserRunError(f"la última línea no es JSON: {lines[-1][:200]}") from e
    if isinstance(out, dict):
        out["_stderr"] = (proc.stderr or "")[-4000:]
    return out


def run_script_file(path: str, config: Dict[str, Any], image: str, **kw) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return run_script(f.read(), config, image, **kw)
