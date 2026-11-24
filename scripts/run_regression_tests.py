#!/usr/bin/env python3
"""Run each pytest module in a fresh process to isolate its temporary database."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def main() -> int:
    modules = sorted(TESTS.glob("test_*.py"))
    if not modules:
        print("No regression test modules found.")
        return 1
    failed = []
    for module in modules:
        print(f"\n=== {module.relative_to(ROOT)} ===", flush=True)
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", str(module)], cwd=ROOT)
        if result.returncode:
            failed.append(module.relative_to(ROOT).as_posix())
    print(f"\nModules passed: {len(modules) - len(failed)}/{len(modules)}")
    if failed:
        print("Failed modules:")
        for name in failed:
            print(f"- {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
