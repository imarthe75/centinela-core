#!/usr/bin/env python3
"""Runs the verifiers over a project.   python verifiers/run.py [--path .] [--only pk_uuid,compose_volumes] [--json]
Exit code: 0 = nothing failed (NO_EVALUADO does not fail but is printed), 1 = at least one NO_CUMPLE."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verifiers.checks import NO_CUMPLE, REGISTRY  # noqa: E402


def run(path: Path, only=None):
    names = only or list(REGISTRY)
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        raise SystemExit(f"verificador desconocido: {', '.join(unknown)} (disponibles: {', '.join(REGISTRY)})")
    return [REGISTRY[n](path) for n in names]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".")
    ap.add_argument("--only")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results = run(Path(a.path).resolve(), a.only.split(",") if a.only else None)
    if a.json:
        print(json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{r.status:<12} {r.verifier:<16} ({r.method}, {r.checked} revisados)")
            for line in r.detail[:15]:
                print(f"    - {line}")
    return 1 if any(r.status == NO_CUMPLE for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
