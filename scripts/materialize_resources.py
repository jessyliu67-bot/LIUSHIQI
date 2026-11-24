#!/usr/bin/env python3
"""Restore the byte-identical canonical V35 ZIP before checks or packaging."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resource_archive import materialize_resource_archive  # noqa: E402


if __name__ == "__main__":
    print(materialize_resource_archive())
