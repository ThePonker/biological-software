"""Embedding helper: build the Data Entry widget as a tab for Observatum.

Used by Observatum's main window. In preview mode it points at a DEV copy of observatum.db and
disables commit, so it can be evaluated in place without any risk to live data. The single entry
point keeps the change to Observatum's main_window.py to two lines.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import QWidget


def _resolve_preview_db() -> Optional[str]:
    """Newest dev copy (observatum_dev_*.db) for a safe preview; None if none found."""
    try:
        from DataEntry import bootstrap
        import paths
        dev = bootstrap.newest_dev_db(str(paths.DATA_DIR))
        if dev and os.path.exists(dev):
            return dev
    except Exception:
        pass
    return None


def _backup_live_db(live_path: str) -> Optional[str]:
    """Copy the live DB to data\\_backups\\ before go-live use. Best-effort.

    Skips if a copy already exists from the last MIN_AGE_HOURS, and keeps only the
    newest KEEP_COPIES afterwards -- these are 114 MB each and sit inside OneDrive.
    """
    KEEP_COPIES = 2
    MIN_AGE_HOURS = 4
    try:
        import shutil, datetime
        d = os.path.join(os.path.dirname(live_path), "_backups")
        os.makedirs(d, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        import glob, time
        existing = sorted(glob.glob(os.path.join(d, "observatum_prelive_*.db")))
        if existing:
            age_h = (time.time() - os.path.getmtime(existing[-1])) / 3600.0
            if age_h < MIN_AGE_HOURS:
                print(f"[DataEntry] go-live backup skipped (one written {age_h:.1f}h ago)")
                return existing[-1]
        dest = os.path.join(d, f"observatum_prelive_{stamp}.db")
        shutil.copy2(live_path, dest)
        for old in sorted(glob.glob(os.path.join(d, "observatum_prelive_*.db")))[:-KEEP_COPIES]:
            try:
                os.remove(old)
                print(f"[DataEntry] pruned old backup: {os.path.basename(old)}")
            except OSError:
                pass
        print(f"[DataEntry] go-live backup written: {dest}")
        return dest
    except Exception as e:
        print(f"[DataEntry] go-live backup FAILED: {e}")
        return None


def make_data_entry_tab(parent: Optional[QWidget] = None, embedded: bool = True,
                        go_live: bool = False) -> QWidget:
    """Return a Data Entry widget ready to addTab().

    go_live=False (default): PREVIEW -- points at a dev copy, commit disabled. Zero risk to live.
    go_live=True: LIVE -- points at observatum.db and enables commit. Takes a timestamped backup
                  of observatum.db first (into data\\_backups\\).
    """
    from DataEntry.data_entry_widget import DataEntryWidget
    if go_live:
        import paths
        live = str(paths.OBSERVATUM_DB)
        _backup_live_db(live)  # safety net before any live use
        return DataEntryWidget(live, parent=parent, embedded=True, allow_commit=True)

    db = _resolve_preview_db()
    if db is None:
        try:
            import paths
            db = str(paths.OBSERVATUM_DB)  # staging only; commit disabled in preview
        except Exception as e:
            raise RuntimeError(f"Data Entry: no database available ({e})")
    return DataEntryWidget(db, parent=parent, embedded=True, allow_commit=False)
