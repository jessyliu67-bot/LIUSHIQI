"""Restore the byte-identical V35 resource ZIP from its source-tree compression."""
from __future__ import annotations

import hashlib
import lzma
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "resources" / "BIG_BANG_V35_DUAL_600.zip"
COMPRESSED = Path(str(ARCHIVE) + ".xz")
EXPECTED_SHA256 = "b5686ae01ffdcfee0746ed7e1d34fc3acb291ab5d0d02d98a3bfdb2f13af7aac"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def materialize_resource_archive() -> Path:
    """Ensure the application's original ZIP path exists and has the V35 hash."""
    if ARCHIVE.is_file():
        actual = _sha256(ARCHIVE)
        if actual != EXPECTED_SHA256:
            raise RuntimeError(f"V35 resource ZIP hash mismatch: {actual}")
        return ARCHIVE
    if not COMPRESSED.is_file():
        raise RuntimeError(f"Missing V35 resource package and compressed source: {COMPRESSED}")

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    temporary = ARCHIVE.with_name(ARCHIVE.name + ".materializing")
    try:
        with lzma.open(COMPRESSED, "rb") as source, temporary.open("wb") as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
        actual = _sha256(temporary)
        if actual != EXPECTED_SHA256:
            raise RuntimeError(f"Restored V35 resource ZIP hash mismatch: {actual}")
        os.replace(temporary, ARCHIVE)
    finally:
        temporary.unlink(missing_ok=True)
    return ARCHIVE


if __name__ == "__main__":
    print(materialize_resource_archive())
