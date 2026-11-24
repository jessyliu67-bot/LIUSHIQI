#!/usr/bin/env python3
"""Run deterministic offline checks before creating a BIG BANG release."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from v16_resources import RAW, inspect  # noqa: E402
from resource_archive import materialize_resource_archive  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    materialize_resource_archive()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest_path = ROOT / "data" / "ASSET_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    database = ROOT / "data" / "bigbang.sqlite3"
    checks: list[tuple[str, bool, str]] = []

    checks.append(("release version", version == "V35", version))
    checks.append(("resource archive exists", RAW.is_file(), str(RAW.relative_to(ROOT))))
    archive_sha = sha256(RAW) if RAW.is_file() else ""
    checks.append(("resource SHA-256", archive_sha == manifest.get("source_zip_sha256"), archive_sha))
    report = inspect(RAW, include_packages=True)
    checks.append(("V35 package structure", report["passed_structure_check"], json.dumps(report["summary"], sort_keys=True)))
    checks.append(("fixed 300 store mapping", report["summary"]["package_count"] == 300, str(report["summary"]["package_count"])))
    checks.append(("600 platform bundles", report["summary"]["platform_bundle_count"] == 600, str(report["summary"]["platform_bundle_count"])))
    checks.append(("Shopify resource count", report["summary"]["shopify_files"] == 3600, str(report["summary"]["shopify_files"])))
    checks.append(("SHOPLINE resource count", report["summary"]["shopline_files"] == 3300, str(report["summary"]["shopline_files"])))

    with sqlite3.connect(database) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        template_count = connection.execute("SELECT count(*) FROM templates").fetchone()[0]
        store_count = connection.execute("SELECT count(*) FROM stores").fetchone()[0]
        entity_count = connection.execute("SELECT count(*) FROM entities").fetchone()[0]
        document_count = connection.execute("SELECT count(*) FROM entity_documents").fetchone()[0]
        template_paths = {row[0] for row in connection.execute("SELECT inner_path FROM templates")}
    checks.append(("seed SQLite integrity", integrity == "ok", integrity))
    checks.append(("300 template rows", template_count == 300, str(template_count)))
    checks.append(("300 store rows", store_count == 300, str(store_count)))
    checks.append(("clean seed has no company records", entity_count == 0 and document_count == 0, f"entities={entity_count}, documents={document_count}"))
    resource_paths = {item["path"] for item in report["packages"]}
    checks.append(("fixed template-to-resource mapping", template_paths == resource_paths, f"templates={len(template_paths)}, resources={len(resource_paths)}"))

    failures = 0
    for label, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {label}: {detail}")
        failures += not passed
    print(f"RESULT: {len(checks) - failures}/{len(checks)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
