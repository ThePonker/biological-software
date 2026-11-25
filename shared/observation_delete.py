"""Deleting observations that specimens point at (R4B, 24 Nov 2026).

specimens.observation_id is a foreign key to observations.id, so deleting a linked
observation failed with a raw "FOREIGN KEY constraint failed". Callers now ask first
(linked_specimens), tell Wil which specimens are linked and let him unlink them or cancel;
delete_observations does the unlink and the delete in ONE transaction, so a failure leaves
both as they were. Long id lists go in batches of CHUNK (SQLite's variable limit).
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from shared.import_core import CHUNK


class LinkedSpecimensError(Exception):
    """Observations still have specimens linked and the caller did not ask to unlink them."""

    def __init__(self, links: List[Dict]):
        self.links = links
        super().__init__(f"{len(links)} specimen(s) are linked to the records being deleted")


def _chunks(ids: Iterable) -> List[List[int]]:
    ids = sorted({int(i) for i in ids})
    return [ids[i:i + CHUNK] for i in range(0, len(ids), CHUNK)]


def linked_specimens(conn, observation_ids) -> List[Dict]:
    """The specimens linked to these observations: id, specimen_code, species_name,
    observation_id (a sqlite3 connection; read only)."""
    out: List[Dict] = []
    for part in _chunks(observation_ids):
        ph = ",".join("?" * len(part))
        for r in conn.execute(
                f"SELECT id, specimen_code, species_name, observation_id FROM specimens "
                f"WHERE observation_id IN ({ph}) ORDER BY observation_id, id", part):
            out.append({"id": r[0], "specimen_code": r[1], "species_name": r[2],
                        "observation_id": r[3]})
    return out


def describe_links(links: List[Dict], limit: int = 15) -> str:
    """One line per linked specimen (the first `limit`), for the question put to Wil."""
    lines = []
    for k in links[:limit]:
        name = k.get("specimen_code") or f"specimen {k['id']}"
        sp = f" ({k['species_name']})" if k.get("species_name") else ""
        lines.append(f"{name}{sp}  is linked to observation {k['observation_id']}")
    if len(links) > limit:
        lines.append(f"... and {len(links) - limit} more")
    return "\n".join(lines)


def delete_observations(db, observation_ids, unlink: bool = False) -> int:
    """Delete the observations (db: a DatabaseManager). With unlink, the specimens linked to
    them are set to no field record first, in the same transaction; without it, linked
    specimens raise LinkedSpecimensError and nothing is changed. Returns rows deleted."""
    parts = _chunks(observation_ids)
    deleted = 0
    with db.main_connection() as conn:
        try:
            if not unlink:
                links = linked_specimens(conn, [i for p in parts for i in p])
                if links:
                    raise LinkedSpecimensError(links)
            for part in parts:
                ph = ",".join("?" * len(part))
                if unlink:
                    conn.execute(f"UPDATE specimens SET observation_id = NULL "
                                 f"WHERE observation_id IN ({ph})", part)
                deleted += conn.execute(f"DELETE FROM observations WHERE id IN ({ph})",
                                        part).rowcount
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return deleted


def update_in_chunks(db, set_sql: str, set_values, observation_ids) -> int:
    """UPDATE observations SET <set_sql> WHERE id IN (...), CHUNK ids at a time, through
    db.execute_main_write. Returns the rows changed."""
    changed = 0
    for part in _chunks(observation_ids):
        ph = ",".join("?" * len(part))
        n = db.execute_main_write(f"UPDATE observations SET {set_sql} WHERE id IN ({ph})",
                                  tuple(set_values) + tuple(part))
        changed += n or 0
    return changed
