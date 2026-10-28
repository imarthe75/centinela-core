#!/usr/bin/env bash
# The repo is mounted READ-ONLY and copied inside, so nothing root-owned is left in the working tree.
# Runs the suite in a throwaway python:3.12-slim container (the host has no pytest). The docker socket is mounted so the
# browser tests can start a REAL sibling container; without it they are reported as skipped.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOCKER_ARGS=()
if [ -S /var/run/docker.sock ]; then DOCKER_ARGS=(-v /var/run/docker.sock:/var/run/docker.sock); fi
exec docker run --rm "${DOCKER_ARGS[@]}" -v "$ROOT":/src:ro python:3.12-slim bash -c '
  set -e
  apt-get -qq update >/dev/null && apt-get -qq install -y docker.io >/dev/null 2>&1 || echo "(sin docker CLI: pruebas de navegador se omiten)"
  cp -r /src /work && cd /work && pip install -q --root-user-action=ignore ".[test]" && python -m pytest -q -rs -p no:cacheprovider "$@"' _ "$@"
