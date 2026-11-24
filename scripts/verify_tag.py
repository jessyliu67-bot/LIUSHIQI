#!/usr/bin/env python3
"""Fail release if its tag does not match the checked-in version."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if len(sys.argv)!=2:
    raise SystemExit("Usage: python scripts/verify_tag.py <tag>")
expected=(ROOT/"VERSION").read_text(encoding="utf-8").strip().lower()
actual=sys.argv[1].strip().lower()
if actual.removeprefix("v")!=expected.removeprefix("v"):
    raise SystemExit(f"Tag {sys.argv[1]} does not match VERSION {expected}")
print(f"PASS release tag: {sys.argv[1]}")
