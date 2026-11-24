"""Deterministic regression tests for the immutable V35 resource baseline."""
from __future__ import annotations

import csv
import html
import io
import json
import re
import sqlite3
import zipfile
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from v16_resources import RAW, inspect, verify_shopline_products  # noqa: E402
from resource_archive import materialize_resource_archive  # noqa: E402


class V35RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        materialize_resource_archive()
        if not RAW.is_file():
            raise AssertionError(f"Missing canonical V35 resource archive: {RAW}")
        cls.archive = zipfile.ZipFile(RAW)
        if cls.archive.testzip() is not None:
            raise AssertionError("Canonical V35 archive failed CRC validation")

    @classmethod
    def tearDownClass(cls):
        cls.archive.close()

    def test_manifest_and_all_600_bundles(self):
        manifest = json.loads((ROOT / "data" / "ASSET_MANIFEST.json").read_text(encoding="utf-8"))
        report = inspect(RAW, include_packages=True)
        self.assertTrue(report["passed_structure_check"], report["blocking_findings"])
        self.assertEqual(report["summary"]["package_count"], 300)
        self.assertEqual(report["summary"]["platform_bundle_count"], 600)
        self.assertEqual(report["summary"]["file_count"], 6900)
        self.assertEqual(report["summary"]["shopify_files"], 3600)
        self.assertEqual(report["summary"]["shopline_files"], 3300)
        self.assertEqual(len(report["packages"]), 300)
        self.assertEqual(manifest["source_zip_sha256"], report["sha256"])
        self.assertEqual(len({item["path"] for item in report["packages"]}), 300)

    def test_each_bundle_has_csv_seven_policies_and_platform_theme(self):
        per_group = defaultdict(list)
        for name in self.archive.namelist():
            if name.endswith("/"):
                continue
            parts = name.split("/")
            per_group["/".join(parts[1:3])].append(name)
        self.assertEqual(len(per_group), 300)
        for files in per_group.values():
            shopify = [name for name in files if name.startswith("Shopify/")]
            shopline = [name for name in files if name.startswith("SHOPLINE/")]
            self.assertEqual(len(shopify), 12)
            self.assertEqual(len(shopline), 11)
            for subset, theme_count, ext in ((shopify, 4, ".liquid"), (shopline, 3, ".sline")):
                csvs = [name for name in subset if name.lower().endswith(".csv")]
                themes = [name for name in subset if name.lower().endswith(ext)]
                policies = [name for name in subset if "/条款文件/" in name]
                self.assertEqual(len(csvs), 1)
                self.assertEqual(len(themes), theme_count)
                self.assertEqual(len(policies), 7)
                self.assertEqual(sum(name.lower().endswith(".docx") for name in policies), 1)
                self.assertEqual(sum(name.lower().endswith(".txt") for name in policies), 6)
                csv_text = self.archive.read(csvs[0]).decode("utf-8-sig")
                rows = list(csv.DictReader(io.StringIO(csv_text)))
                self.assertTrue(rows)
                handle_columns = {"Handle", "URL handle"}
                self.assertTrue(handle_columns.intersection(rows[0]), f"Missing product handle column: {csvs[0]}")

    def test_every_shopline_handle_is_published_in_its_csv(self):
        groups = defaultdict(list)
        for name in self.archive.namelist():
            if not name.endswith("/"):
                groups["/".join(name.split("/")[1:3])].append(name)
        self.assertEqual(len(groups), 300)
        for names in groups.values():
            home_path = next(name for name in names if name.startswith("SHOPLINE/") and name.endswith("/02-homepage-content.sline"))
            csv_path = next(name for name in names if name.startswith("SHOPLINE/") and name.endswith(".csv"))
            handles = verify_shopline_products(self.archive.read(home_path), self.archive.read(csv_path))
            self.assertEqual(len(handles), 8)

    def test_shopline_second_homepage_section_is_not_empty(self):
        for name in self.archive.namelist():
            if not name.startswith("SHOPLINE/") or not name.endswith("/02-homepage-content.sline"):
                continue
            source = self.archive.read(name).decode("utf-8-sig")
            sections = re.findall(r"<section\b[^>]*>([\s\S]*?)</section\s*>", source, re.IGNORECASE)
            self.assertGreaterEqual(len(sections), 2, name)
            for index, section in enumerate(sections[:2]):
                text = re.sub(r"<style\b[^>]*>[\s\S]*?</style\s*>", " ", section, flags=re.IGNORECASE)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\{\{[\s\S]*?\}\}|\{%[\s\S]*?%\}", " ", text)
                text = " ".join(html.unescape(text).split())
                self.assertTrue(text, f"Empty SHOPLINE homepage section {index + 1}: {name}")
            self.assertRegex(source, r"@media\s*\(max-width\s*:\s*749px\)", name)

    def test_seed_database_is_clean_and_mapped_to_all_templates(self):
        database = ROOT / "data" / "bigbang.sqlite3"
        resource_paths = {item["path"] for item in inspect(RAW, include_packages=True)["packages"]}
        with sqlite3.connect(database) as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT count(*) FROM templates").fetchone()[0], 300)
            self.assertEqual(connection.execute("SELECT count(*) FROM stores").fetchone()[0], 300)
            self.assertEqual(connection.execute("SELECT count(*) FROM entities").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM entity_documents").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(DISTINCT inner_path) FROM templates").fetchone()[0], 300)
            template_paths = {row[0] for row in connection.execute("SELECT inner_path FROM templates")}
            self.assertEqual(template_paths, resource_paths)

    def test_release_metadata_matches_v35(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "V35")
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("version='11.4.3-V35'", app_source)
