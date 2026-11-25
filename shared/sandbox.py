"""sandbox -- is this run using a sandbox copy of the data, not Wil's live data? (25 Nov 2026)

scripts/make_sandbox.py copies data\\*.db to a sandbox folder; launchers/run_sandbox.bat sets
BIOSOFT_ROOT to it (paths._resolve_root then puts DATA_DIR inside it) and BIOSOFT_SANDBOX=1.
That marker, not BIOSOFT_ROOT alone (the tests set BIOSOFT_ROOT too), makes this a sandbox run:
the window title says SANDBOX, photos are taken from a capture folder inside the sandbox, and
the CSV backup on close stays inside it. No Qt.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def sandbox_root() -> Optional[Path]:
    """The sandbox root in use (run_sandbox.bat: BIOSOFT_SANDBOX=1 and BIOSOFT_ROOT another folder
    than the code folder), else None."""
    if not (os.environ.get("BIOSOFT_ROOT") and os.environ.get("BIOSOFT_SANDBOX") == "1"):
        return None
    import paths
    root = Path(paths.ROOT).resolve()
    return root if root != Path(paths.__file__).resolve().parent else None


def sandbox_capture_folder() -> Optional[Path]:
    """In a sandbox, the folder photos are taken from (inside it), never the live capture folder."""
    root = sandbox_root()
    return root / "capture" if root else None


def window_title(base: str) -> str:
    """`base`, with a SANDBOX warning when running on a sandbox copy."""
    return f"{base} -- SANDBOX (a copy: not your live data)" if sandbox_root() else base
