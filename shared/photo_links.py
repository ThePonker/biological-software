"""photo_links -- which photos belong to which record (photos B2, agreed 13 Oct 2026).

THE rule for record <-> photo links. The photo library itself is not indexed: the species
folder IS the index (shared/photo_files.py lists it). Only the links are stored:

  photo_links(id INTEGER PRIMARY KEY,
              photo_path  TEXT NOT NULL,   -- relative to paths.MEDIA_ROOT, '/' separators
              specimen_id INTEGER,         -- specimens.id, or NULL
              observation_id INTEGER,      -- observations.id, or NULL
              method TEXT,                 -- 'specimen match' / 'by hand' / 'intake'
              created_at TEXT,
              UNIQUE(photo_path, specimen_id, observation_id))

A photo linked to a specimen belongs to that specimen's field record too (specimens.
observation_id), so photos_for_observation() finds both. The table is added by
scripts/add_photo_links_table.py (dry run first, backup); every reader here returns nothing
on a database without it. No Qt.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable, List, Optional

TABLE = "photo_links"
SPECIMEN_MATCH, BY_HAND, INTAKE = "specimen match", "by hand", "intake"

CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id INTEGER PRIMARY KEY,
    photo_path TEXT NOT NULL,
    specimen_id INTEGER,
    observation_id INTEGER,
    method TEXT,
    created_at TEXT,
    UNIQUE(photo_path, specimen_id, observation_id)
)"""
INDEX_SQL = (
    f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_specimen ON {TABLE}(specimen_id)",
    f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_observation ON {TABLE}(observation_id)",
    f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_path ON {TABLE}(photo_path)",
)


def norm(path: str) -> str:
    """A stored path: '/' separators, no leading './' or '/'."""
    p = str(path).replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def has_table(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (TABLE,)).fetchone() is not None


STAGING = "staging_id"        # a Data Entry row's photo, before the row becomes a record


def has_staging_column(conn) -> bool:
    return has_table(conn) and STAGING in {r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})")}


def ensure_schema(conn: sqlite3.Connection) -> bool:
    """Create the table and its indexes if missing, and the staging_id column (bench photos,
    14 Oct 2026). True when something was created."""
    had, had_staging = has_table(conn), has_staging_column(conn)
    conn.execute(CREATE_SQL)
    if not had_staging:
        conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {STAGING} INTEGER")
    for sql in INDEX_SQL + (f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_staging ON {TABLE}({STAGING})",):
        conn.execute(sql)
    return not (had and had_staging)


# --- bench photos: a Data Entry row's photos until the row is committed ----------------------
def add_staging_link(conn, photo_path: str, staging_id: int) -> bool:
    p = norm(photo_path)
    if conn.execute(f"SELECT 1 FROM {TABLE} WHERE photo_path = ? AND {STAGING} = ?",
                    (p, staging_id)).fetchone():
        return False
    conn.execute(f"INSERT INTO {TABLE} (photo_path, {STAGING}, method, created_at) VALUES (?,?,?,?)",
                 (p, staging_id, INTAKE, datetime.now().isoformat(timespec="seconds")))
    return True


def photos_for_staging(conn, staging_id: int) -> List[str]:
    if not has_staging_column(conn):
        return []
    return _paths(conn.execute(f"SELECT photo_path FROM {TABLE} WHERE {STAGING} = ? ORDER BY photo_path",
                               (staging_id,)))


def staging_counts(conn, staging_ids: Iterable[int]) -> dict:
    """{staging row id: number of photos} for the rows that have any."""
    ids = [int(i) for i in staging_ids if i is not None]
    if not ids or not has_staging_column(conn):
        return {}
    out = {}
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        for sid, n in conn.execute(f"SELECT {STAGING}, COUNT(*) FROM {TABLE} WHERE {STAGING} IN "
                                   f"({','.join('?' * len(part))}) GROUP BY {STAGING}", part):
            out[sid] = n
    return out


def promote_staging(conn, staging_id: int, observation_id: int) -> int:
    """The row became a record: its photos now belong to the record. Returns rows changed."""
    if not has_staging_column(conn):
        return 0
    return conn.execute(f"UPDATE {TABLE} SET observation_id = ?, {STAGING} = NULL WHERE {STAGING} = ?",
                        (observation_id, staging_id)).rowcount


def drop_staging_links(conn, staging_ids: Iterable[int]) -> int:
    """The staging rows are being deleted: remove their photo links (never the photo files;
    shared/bench_photos.release). Returns the rows removed. The caller commits."""
    ids = [int(i) for i in staging_ids if i is not None]
    if not ids or not has_staging_column(conn):
        return 0
    n = 0
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        n += conn.execute(f"DELETE FROM {TABLE} WHERE {STAGING} IN ({','.join('?' * len(part))})",
                          part).rowcount
    return n


def orphan_staging_links(conn) -> List[tuple]:
    """(link id, photo path, staging id) for links whose staging row no longer exists (rows
    deleted before 14 Oct take 2). Empty on a database without the column or staging table."""
    if not has_staging_column(conn) or not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='entry_staging'").fetchone():
        return []
    return [tuple(r) for r in conn.execute(
        f"SELECT l.id, l.photo_path, l.{STAGING} FROM {TABLE} l WHERE l.{STAGING} IS NOT NULL "
        f"AND NOT EXISTS (SELECT 1 FROM entry_staging s WHERE s.id = l.{STAGING}) ORDER BY l.id")]


def orphan_record_links(conn) -> List[tuple]:
    """(link id, photo path, 'record 12' / 'specimen 5') for links to a record or specimen that
    no longer exists (deleted some other way than the apps' delete, which asks; review 14 Oct
    2026). The photo files are not looked at."""
    if not has_table(conn):
        return []
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    out = []
    if "observations" in tables:
        out += [(i, p, f"record {o}") for i, p, o in conn.execute(
            f"SELECT l.id, l.photo_path, l.observation_id FROM {TABLE} l WHERE l.observation_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM observations x WHERE x.id = l.observation_id)")]
    if "specimens" in tables:
        out += [(i, p, f"specimen {s}") for i, p, s in conn.execute(
            f"SELECT l.id, l.photo_path, l.specimen_id FROM {TABLE} l WHERE l.specimen_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM specimens x WHERE x.id = l.specimen_id)")]
    return sorted(out)


def add_link(conn, photo_path: str, specimen_id: Optional[int] = None,
             observation_id: Optional[int] = None, method: str = BY_HAND) -> bool:
    """Link a photo. True when a new link was written (an existing one is left as it is)."""
    if specimen_id is None and observation_id is None:
        raise ValueError("a link needs a specimen or an observation")
    p = norm(photo_path)
    found = conn.execute(
        f"SELECT 1 FROM {TABLE} WHERE photo_path = ? AND specimen_id IS ? AND observation_id IS ?",
        (p, specimen_id, observation_id)).fetchone()
    if found:
        return False
    conn.execute(f"INSERT INTO {TABLE} (photo_path, specimen_id, observation_id, method, created_at) "
                 "VALUES (?,?,?,?,?)",
                 (p, specimen_id, observation_id, method, datetime.now().isoformat(timespec="seconds")))
    return True


def remove_link(conn, photo_path: str, specimen_id: Optional[int] = None,
                observation_id: Optional[int] = None) -> int:
    """Take one link away (Wil's "Not this record's photo"). The photo file is untouched.
    Returns the rows removed (0 or 1)."""
    if specimen_id is None and observation_id is None:
        raise ValueError("a link needs a specimen or an observation")
    cur = conn.execute(f"DELETE FROM {TABLE} WHERE photo_path = ? AND specimen_id IS ? "
                       "AND observation_id IS ?", (norm(photo_path), specimen_id, observation_id))
    return cur.rowcount


def _paths(rows) -> List[str]:
    return list(dict.fromkeys(r[0] for r in rows))


def photos_for_specimen(conn, specimen_id: int) -> List[str]:
    if not has_table(conn):
        return []
    return _paths(conn.execute(f"SELECT photo_path FROM {TABLE} WHERE specimen_id = ? ORDER BY photo_path",
                               (specimen_id,)))


def photos_for_observation(conn, observation_id: int) -> List[str]:
    """Photos linked to the record itself, and to any specimen whose field record it is."""
    if not has_table(conn):
        return []
    return _paths(conn.execute(
        f"SELECT photo_path FROM {TABLE} WHERE observation_id = ? "
        f"UNION SELECT l.photo_path FROM {TABLE} l JOIN specimens s ON s.id = l.specimen_id "
        "WHERE s.observation_id = ? ORDER BY 1", (observation_id, observation_id)))


def observation_photo_counts(conn) -> dict:
    """{observation id: number of photos} -- its own links and its specimens' (the Observation
    Data table's camera column). Empty on a database without the table."""
    if not has_table(conn):
        return {}
    has_specimens = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='specimens'").fetchone()
    sql = f"SELECT observation_id AS oid, photo_path FROM {TABLE} WHERE observation_id IS NOT NULL"
    if has_specimens:
        sql += (f" UNION SELECT s.observation_id, l.photo_path FROM {TABLE} l JOIN specimens s "
                "ON s.id = l.specimen_id WHERE s.observation_id IS NOT NULL")
    return dict(conn.execute(f"SELECT oid, COUNT(DISTINCT photo_path) FROM ({sql}) GROUP BY oid").fetchall())


def specimen_photo_counts(conn) -> dict:
    """{specimen id: number of photos linked to the specimen itself} (Insect Collection's
    camera column). Empty on a database without the table."""
    if not has_table(conn):
        return {}
    return dict(conn.execute(f"SELECT specimen_id, COUNT(DISTINCT photo_path) FROM {TABLE} "
                             "WHERE specimen_id IS NOT NULL GROUP BY specimen_id").fetchall())


def link_count(conn, photo_path: str) -> int:
    """How many records/specimens this photo is linked to."""
    if not has_table(conn):
        return 0
    return conn.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE photo_path = ?",
                        (norm(photo_path),)).fetchone()[0]


def repoint(conn, old_path: str, new_path: str) -> int:
    """After a photo is moved: its links follow. Returns the rows changed."""
    if not has_table(conn):
        return 0
    cur = conn.execute(f"UPDATE {TABLE} SET photo_path = ? WHERE photo_path = ?",
                       (norm(new_path), norm(old_path)))
    return cur.rowcount


def linked_specimen_ids(conn, ids: Iterable[int]) -> set:
    """The specimen ids (of those given) that already have a photo."""
    ids = [int(i) for i in ids]
    if not ids or not has_table(conn):
        return set()
    out = set()
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        ph = ",".join("?" * len(part))
        out.update(r[0] for r in conn.execute(
            f"SELECT DISTINCT specimen_id FROM {TABLE} WHERE specimen_id IN ({ph})", part))
    return out


__all__ = ["TABLE", "CREATE_SQL", "INDEX_SQL", "SPECIMEN_MATCH", "BY_HAND", "INTAKE", "norm",
           "has_table", "ensure_schema", "add_link", "remove_link", "STAGING", "has_staging_column",
           "add_staging_link", "photos_for_staging", "drop_staging_links", "orphan_staging_links", "orphan_record_links", "staging_counts", "promote_staging", "photos_for_specimen",
           "photos_for_observation", "observation_photo_counts", "specimen_photo_counts", "link_count", "repoint", "linked_specimen_ids"]
