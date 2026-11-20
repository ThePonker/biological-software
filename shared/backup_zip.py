"""backup_zip -- write and re-check the encrypted zip (used by shared/nightly_backup.py)."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from shared import backup_service

_CHUNK = 1024 * 1024


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def fsync_file(path, strict: bool) -> None:
    """Flush a finished file to the drive. Not strict: errors are ignored (the final name)."""
    try:
        with open(path, "r+b") as f:
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        if strict:
            raise


def write_zip(partial: Path, members: list, password: str, computer: str, now: datetime) -> None:
    import pyzipper
    manifest = {"computer": computer, "made_at": now.isoformat(timespec="seconds"),
                "files": [{"name": arc, "bytes": os.path.getsize(src), "sha256": sha256(src)}
                          for arc, src in members]}
    with pyzipper.AESZipFile(str(partial), "w", compression=pyzipper.ZIP_DEFLATED,
                             encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode("utf-8"))
        for arc, src in members:
            zf.write(src, arc)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    fsync_file(partial, strict=True)


def verify_zip(partial: Path, password: str) -> Optional[str]:
    """None if the zip opens with the password and matches its manifest, else the reason."""
    import pyzipper
    try:
        with pyzipper.AESZipFile(str(partial)) as zf:
            zf.setpassword(password.encode("utf-8"))
            for info in zf.infolist():
                if not info.flag_bits & 0x1:
                    return f"{info.filename} is not encrypted"
            if zf.testzip() is not None:
                return "testzip found a bad member"
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            names = {i.filename for i in zf.infolist()}
            wanted = {f["name"] for f in manifest["files"]} | {"manifest.json"}
            if names != wanted:
                return "members do not match the manifest"
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
                for f in manifest["files"]:
                    out = os.path.join(tmp, f["name"])
                    h = hashlib.sha256()
                    with zf.open(f["name"]) as src, open(out, "wb") as dst:
                        for block in iter(lambda: src.read(_CHUNK), b""):
                            h.update(block)
                            dst.write(block)
                    if h.hexdigest() != f["sha256"]:
                        return f"{f['name']}: sha256 differs from the manifest"
                    if f["name"].endswith(".db"):
                        why = backup_service.verify_copy(out)
                        if why:
                            return f"{f['name']}: {why}"
    except Exception as e:
        return f"cannot re-open: {e}"
    return None
