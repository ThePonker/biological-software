"""specimen_staging -- which specimens a Data Entry row was made from (14 Oct 2026).

Records made from specimens go through Data Entry like any other row, so Wil sees and edits
them before they are committed. This table remembers which specimens each row stands for;
on commit those specimens are linked to the new record (specimens.observation_id), and a
deleted row lets its specimens go (they show as "no field record" again).

    staging_specimens(staging_id, specimen_id)   one row per specimen

Two kinds of link (the `origin` column, added 25 Nov 2026):
    NULL            the row was made FROM the specimen (scripts/stage_records_from_specimens.py):
                    at commit the specimen is only linked to the new record.
    "made_from_row" the specimen was made FROM the row (shared/make_specimens.py): at commit it
                    is linked and also takes the committed record's fields (sync_from_record);
                    its own curatorial fields (preparation, condition, storage, drawer, notes,
                    label data) are never touched.

No Qt. Never touches a specimen that already has a field record.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Optional, Set

TABLE = "staging_specimens"
ORIGIN_MADE = "made_from_row"       # origin of a specimen made from its row (Make specimens)

# record column -> specimen column: what a made-from-row specimen takes from its committed record
RECORD_TO_SPECIMEN = (
    ("species_name", "species_name"), ("species_tvk", "species_tvk"), ("common_name", "common_name"),
    ("order_name", "order_name"), ("family", "family"), ("subfamily", "subfamily"),
    ("superfamily", "superfamily"), ("taxonomic_sort_key", "taxonomic_sort_key"),
    ("taxon_group", "taxon_group"), ("date", "date_collected"), ("grid_ref", "grid_ref"),
    ("vice_county", "vice_county"), ("vc_number", "vc_number"), ("site_name", "site_name"),
    ("recorder", "collector"), ("determiner", "determiner"), ("sex", "sex"),
)
_NOT_NULL = ("species_name", "date_collected")


def _columns(conn, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(f"CREATE TABLE IF NOT EXISTS {TABLE} (staging_id INTEGER NOT NULL, "
                 "specimen_id INTEGER NOT NULL, origin TEXT, PRIMARY KEY (staging_id, specimen_id))")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_specimen ON {TABLE}(specimen_id)")
    if "origin" not in _columns(conn, TABLE):          # a table made before 25 Nov 2026
        conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN origin TEXT")


def has_table(conn) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                             (TABLE,)).fetchone())


def add(conn: sqlite3.Connection, staging_id: int, specimen_ids: Iterable[int],
        origin: Optional[str] = None) -> None:
    """origin None: the row was made from these specimens (the reverse flow, unchanged);
    ORIGIN_MADE: these specimens were made from the row."""
    ensure_schema(conn)
    conn.executemany(f"INSERT OR IGNORE INTO {TABLE} (staging_id, specimen_id, origin) VALUES (?, ?, ?)",
                     [(int(staging_id), int(s), origin) for s in specimen_ids])


def for_row(conn, staging_id: int) -> List[int]:
    if not has_table(conn):
        return []
    return [r[0] for r in conn.execute(
        f"SELECT specimen_id FROM {TABLE} WHERE staging_id = ? ORDER BY specimen_id", (staging_id,))]


def made_from_row(conn, staging_id: int) -> List[int]:
    """The row's specimens that were made from it (origin ORIGIN_MADE)."""
    if not has_table(conn) or "origin" not in _columns(conn, TABLE):
        return []
    return [r[0] for r in conn.execute(
        f"SELECT specimen_id FROM {TABLE} WHERE staging_id = ? AND origin = ? ORDER BY specimen_id",
        (staging_id, ORIGIN_MADE))]


def made_counts(conn, job_id: int) -> Dict[int, int]:
    """{staging row id: specimens made from it that still exist} for one Data Entry job -- the
    Keep cell shows "made N" on those rows (Wil, 25 Nov 2026)."""
    if not has_table(conn) or "origin" not in _columns(conn, TABLE):
        return {}
    return {sid: n for sid, n in conn.execute(
        f"SELECT ss.staging_id, COUNT(*) FROM {TABLE} ss "
        "JOIN specimens s ON s.id = ss.specimen_id "
        "JOIN entry_staging e ON e.id = ss.staging_id "
        "WHERE e.job_id = ? AND ss.origin = ? GROUP BY ss.staging_id", (job_id, ORIGIN_MADE))}


def staged(conn) -> Dict[int, int]:
    """{specimen id: staging row id} for every specimen already on a Data Entry row."""
    if not has_table(conn):
        return {}
    return {s: r for r, s in conn.execute(f"SELECT staging_id, specimen_id FROM {TABLE}")}


def staged_ids(conn) -> Set[int]:
    return set(staged(conn))


def link_on_commit(conn, staging_id: int, observation_id: int) -> List[str]:
    """The row became observation `observation_id`: link its specimens to it (only those
    still without a field record) and forget the row's list. Returns notes for the commit
    summary. The caller commits."""
    notes = []
    ids = for_row(conn, staging_id)
    if not ids:
        return notes
    mine = set(made_from_row(conn, staging_id))
    synced = []
    for sid in ids:
        cur = conn.execute("UPDATE specimens SET observation_id = ? WHERE id = ? "
                           "AND observation_id IS NULL", (observation_id, sid))
        if cur.rowcount == 0:
            notes.append(f"specimen {sid}: already had a field record (or is gone) -- "
                         f"not linked to record {observation_id}")
        elif sid in mine:
            synced.append(sid)
    if synced:                      # same transaction as the link; the caller commits
        try:
            sync_from_record(conn, synced, observation_id)
        except sqlite3.Error as e:
            notes.append(f"specimens {synced}: linked, but their details were not updated from "
                         f"record {observation_id} ({e})")
    conn.execute(f"DELETE FROM {TABLE} WHERE staging_id = ?", (staging_id,))
    return notes


def sync_from_record(conn, specimen_ids: Iterable[int], observation_id: int) -> int:
    """Rule 5: set the specimens' record-derived fields (RECORD_TO_SPECIMEN) from the committed
    record. Only those columns: preparation, condition, storage, drawer, notes and label data are
    never in the UPDATE. Returns how many specimens were updated. The caller commits."""
    cur = conn.execute("SELECT * FROM observations WHERE id = ?", (observation_id,))
    row = cur.fetchone()
    ids = [int(s) for s in specimen_ids]
    if row is None or not ids:
        return 0
    rec = dict(zip([d[0] for d in cur.description], tuple(row)))
    have = _columns(conn, "specimens")
    # a blank in the record never blanks the specimen (review 25 Nov): only values are copied
    sets = {sc: rec.get(rc) for rc, sc in RECORD_TO_SPECIMEN
            if rc in rec and sc in have and rec.get(rc) not in (None, "")}
    if not sets:
        return 0
    if "updated_at" in have:                     # stamped as SpecimenRepository stamps it
        from datetime import datetime
        sets["updated_at"] = datetime.now().isoformat()
    if "sex" in sets:                            # "male" -> "Male"; "Not recorded" / "mixed" -> leave it
        from shared.specimen_vocab import specimen_sex
        sets["sex"] = specimen_sex(sets["sex"])
        if sets["sex"] is None:
            del sets["sex"]
    cols = ", ".join(f"{c} = ?" for c in sets)
    n = 0
    for sid in ids:
        n += conn.execute(f"UPDATE specimens SET {cols} WHERE id = ?", (*sets.values(), sid)).rowcount
    return n


def release(conn, staging_ids: Iterable[int]) -> None:
    """Rows deleted without a commit: their specimens are free again. The caller commits."""
    if not has_table(conn):
        return
    conn.executemany(f"DELETE FROM {TABLE} WHERE staging_id = ?", [(int(i),) for i in staging_ids])


__all__ = ["TABLE", "ORIGIN_MADE", "RECORD_TO_SPECIMEN", "ensure_schema", "has_table", "add",
           "for_row", "made_from_row", "staged", "staged_ids", "link_on_commit", "sync_from_record",
           "release"]
