"""Links to a record's page on iRecord (R9-3, 11 Oct 2026).

The one home of the iRecord record-page pattern, confirmed by Wil on 11 Oct: it opens the
right record. Any record that has been into iRecord holds its iRecord ID (observations and
Recording Scheme rows, column irecord_id); records without one get no link.

Used by the record detail dialogs (Open in iRecord button), the Mapping square list and
the cleaning report (Observatum/src/services/cleaning_report.py re-exports these names).
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, Optional

IRECORD_URL = "https://irecord.org.uk/record-details?occurrence_id={id}"

# Tables that hold an iRecord ID (others never get a link)
TABLES_WITH_IRECORD_ID = ("observations", "recording_scheme")


def irecord_id_of(value) -> Optional[int]:
    """The iRecord ID as a positive int, or None (blank, 0, text that is not a number)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def irecord_url(irecord_id) -> Optional[str]:
    """The iRecord page of a record, or None when the record holds no iRecord ID."""
    n = irecord_id_of(irecord_id)
    return IRECORD_URL.format(id=n) if n else None


def record_irecord_url(record: Optional[dict]) -> Optional[str]:
    """irecord_url for a record dict (its 'irecord_id'), None for no record / no ID."""
    return irecord_url((record or {}).get("irecord_id"))


def irecord_ids(conn: sqlite3.Connection, table: str, ids: Iterable[int]) -> Dict[int, int]:
    """{record id: iRecord ID} for the given rows of `table` that hold one (read only).
    Empty for a table with no irecord_id column (specimens, contributed records)."""
    if table not in TABLES_WITH_IRECORD_ID:
        return {}
    want = sorted({int(i) for i in ids if i is not None})
    out: Dict[int, int] = {}
    for start in range(0, len(want), 500):
        chunk = want[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for rid, irid in conn.execute(
                f"SELECT id, irecord_id FROM {table} WHERE id IN ({marks})", chunk):
            n = irecord_id_of(irid)
            if n:
                out[rid] = n
    return out
