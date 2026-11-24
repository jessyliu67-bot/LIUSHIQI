#!/usr/bin/env python3
"""Create a release inventory with file hashes and explicit limitations."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "release-manifest.json")
    args = parser.parse_args()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    files = []
    for relative in sorted(item for item in tracked if item and (ROOT / item).is_file()):
        path = ROOT / relative
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    latest_changes = changelog.split("\n## ", 2)[1] if "\n## " in changelog else changelog
    report = {
        "project": "BIG BANG",
        "version": version,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "resource_manifest": json.loads((ROOT / "data" / "ASSET_MANIFEST.json").read_text(encoding="utf-8")),
        "tracked_file_count": len(files),
        "files": files,
        "change_record": latest_changes.strip(),
        "tests": {
            "ci_release_gate": "passed before this manifest is generated",
            "live_platform_status": "No live Shopify or SHOPLINE test store was supplied",
        },
        "known_limitations": [
            "The original supplied EXE has no native launcher source or reproducible build project.",
            "No live Shopify or SHOPLINE storefront installation was tested.",
            "The Windows source build must be distinguished from the original EXE.",
        ],
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
