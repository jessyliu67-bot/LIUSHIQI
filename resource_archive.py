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
COMPRESSED_PARTS = Path(str(COMPRESSED) + ".parts")
EXPECTED_SHA256 = "b5686ae01ffdcfee0746ed7e1d34fc3acb291ab5d0d02d98a3bfdb2f13af7aac"
EXPECTED_XZ_SHA256 = "005420e5123a861ed18e2562b9a4b587f9eeac81312d9fcbd85a7c56112afa91"
EXPECTED_XZ_SIZE = 5843972


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
        parts = sorted(COMPRESSED_PARTS.glob("part-*.bin"))
        if not parts:
            raise RuntimeError(f"Missing V35 resource package and compressed source parts: {COMPRESSED_PARTS}")
        compressed_temp = COMPRESSED.with_name(COMPRESSED.name + ".assembling")
        try:
            with compressed_temp.open("wb") as target:
                for part in parts:
                    with part.open("rb") as source:
                        shutil.copyfileobj(source, target, 1024 * 1024)
            if compressed_temp.stat().st_size != EXPECTED_XZ_SIZE or _sha256(compressed_temp) != EXPECTED_XZ_SHA256:
                raise RuntimeError("V35 compressed resource parts failed size or SHA-256 verification")
            os.replace(compressed_temp, COMPRESSED)
        finally:
            compressed_temp.unlink(missing_ok=True)
    if COMPRESSED.stat().st_size != EXPECTED_XZ_SIZE or _sha256(COMPRESSED) != EXPECTED_XZ_SHA256:
        raise RuntimeError("V35 compressed resource archive failed size or SHA-256 verification")

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
