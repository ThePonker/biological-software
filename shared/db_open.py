"""Open the reference databases read-only (backlog D9, 9 Oct 2026).

UKSI, Codex, Pantheon and the VC lookup are reference data: only their build and import
scripts write to them (Codex Manager's own tabs for codex.db). Everything else opens them
through connect_ro(), so a stray write fails loudly ("attempt to write a readonly
database") instead of changing reference data -- the Examen manual-entry dialog emptied
codex.db manual_entries that way before 6 Oct.

    from shared.db_open import connect_ro
    conn = connect_ro(paths.UKSI_DB)
"""
import sqlite3
from pathlib import Path


def connect_ro(path, **kwargs) -> sqlite3.Connection:
    """A read-only connection to the SQLite file at `path` (str or Path).

    The path is passed as a file: URI, so spaces and odd characters in folder names are
    safe. Pragmas that only tune reading (cache_size, mmap_size, foreign_keys) still work;
    `PRAGMA journal_mode = WAL` does not, so don't set it on these connections.
    """
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True, **kwargs)
