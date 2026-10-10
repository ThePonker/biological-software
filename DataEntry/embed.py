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
        # shared/backup_service.py snapshots observatum.db before every commit and on
        # Observatum close, outside OneDrive. (The old in-OneDrive copier, never called and
        # pruning with os.remove, was taken out 10 Oct 2026 -- review DE10.)
        return DataEntryWidget(live, parent=parent, embedded=True, allow_commit=True)

    db = _resolve_preview_db()
    if db is None:
        try:
            import paths
            db = str(paths.OBSERVATUM_DB)  # staging only; commit disabled in preview
        except Exception as e:
            raise RuntimeError(f"Data Entry: no database available ({e})")
    return DataEntryWidget(db, parent=parent, embedded=True, allow_commit=False)
