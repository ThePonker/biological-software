"""sync_conflicts -- an iRecord sync never quietly undoes an edit made in Observatum (A2,
agreed 13-14 Oct 2026). No Qt.

THE rule, used by the observation import wizard's sync update (_update_observation):

  observations.local_edited_at (TEXT, ISO time) is set whenever a record is edited by hand in
  Observatum (mark_edited). It is NULL on every record until then, so nothing changes for
  records nobody has edited. The column is added by scripts/add_local_edited_column.py.

  For a record the download brings again (matched by iRecord ID or Observatum key):
    * not edited here since its last sync                -> 'update'  (as before)
    * edited here, and iRecord's copy has not changed      -> 'keep'    (Observatum's edit stays;
      (its "last edited on" is the same as last time)                  nothing is written)
    * edited here AND changed in iRecord, and the two
      now differ in a field that matters                   -> 'conflict' (nothing is written;
                                                              Wil chooses, see resolve())
    * edited here, changed in iRecord, but they agree      -> 'update'
  "Edited here since its last sync" = local_edited_at later than last_synced (or never synced).

resolve(): 'observatum' keeps Observatum's values and remembers iRecord's "last edited on", so
the next sync sees iRecord unchanged and keeps them (correct iRecord by hand; when that edit
comes back the two agree). 'irecord' writes iRecord's values for the differing fields and
marks the record synced now.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

COLUMN = "local_edited_at"
UPDATE, KEEP, CONFLICT = "update", "keep", "conflict"

# The fields a re-determination or correction touches; a difference in one of these is a
# conflict. (Verification and other iRecord-owned fields are not: iRecord is their master.)
CONFLICT_FIELDS = ("species_name", "species_tvk", "date", "grid_ref", "site_name",
                   "recorder", "determiner", "sex", "stage", "quantity", "comment")

# Fields iRecord owns (verification and the like): written by every sync, also for a record
# whose own edits are kept or in conflict, so a verification is never held back.
IRECORD_OWNED = ("verification_status", "verification_status_2", "verifier", "verified_on",
                 "automated_checks", "images", "licence", "input_on_date", "record_key",
                 "irecord_key", "source")

LABELS = {"species_name": "Species", "species_tvk": "TVK", "date": "Date", "grid_ref": "Grid ref",
          "site_name": "Site", "recorder": "Recorder", "determiner": "Determiner", "sex": "Sex",
          "stage": "Stage", "quantity": "Quantity", "comment": "Comment"}


def has_column(conn) -> bool:
    try:
        return COLUMN in {r[1] for r in conn.execute("PRAGMA table_info(observations)")}
    except sqlite3.Error:
        return False


def ensure_schema(conn) -> bool:
    """Add observations.local_edited_at if missing. True when added."""
    if has_column(conn):
        return False
    conn.execute(f"ALTER TABLE observations ADD COLUMN {COLUMN} TEXT")
    return True


def now() -> str:
    return datetime.now().isoformat()


def mark_edited(conn, ids: Iterable[int], when: Optional[str] = None) -> int:
    """Record that these observations were edited by hand here. Does nothing (0) on a
    database without the column. The caller commits."""
    ids = [int(i) for i in ids if i is not None]
    if not ids or not has_column(conn):
        return 0
    stamp = when or now()
    n = 0
    for i in range(0, len(ids), 900):
        part = ids[i:i + 900]
        n += conn.execute(f"UPDATE observations SET {COLUMN} = ? WHERE id IN "
                          f"({','.join('?' * len(part))})", [stamp, *part]).rowcount
    return n


def _norm(v):
    if v is None:
        return ""
    s = str(v).strip()
    try:                                  # 1 and '1' and 1.0 are the same quantity
        f = float(s)
        if f == int(f):
            return str(int(f))
    except ValueError:
        pass
    return " ".join(s.split()).casefold()


def differing(held: Dict, incoming: Dict) -> List[str]:
    """The conflict fields where iRecord's incoming value differs from the held one. A blank
    incoming value is never a difference (a sync never blanks a stored value)."""
    return [f for f in CONFLICT_FIELDS
            if f in incoming and _norm(incoming.get(f)) != "" and _norm(incoming.get(f)) != _norm(held.get(f))]


def cleared(held: Dict, updates: Dict) -> List[str]:
    """The conflict fields an edit here emptied (a value cleared by hand is an edit too, so
    the next sync does not fill it back in; review 14 Oct 2026)."""
    return [f for f in CONFLICT_FIELDS
            if f in updates and _norm(updates.get(f)) == "" and _norm(held.get(f)) != ""]


def decide(held: Dict, incoming: Dict) -> Tuple[str, List[str]]:
    """(UPDATE / KEEP / CONFLICT, differing fields). held: the stored record with
    local_edited_at, last_synced, last_edited_date; incoming: the download's values."""
    edited = held.get(COLUMN)
    if not edited or (held.get("last_synced") and str(edited) <= str(held.get("last_synced"))):
        return UPDATE, []
    diff = differing(held, incoming)
    if not diff:
        return UPDATE, []
    irecord_changed = _norm(incoming.get("last_edited_date")) not in ("", _norm(held.get("last_edited_date")))
    return (CONFLICT if irecord_changed else KEEP), diff


def held_row(conn, record_id: int) -> Dict:
    cols = ("id",) + CONFLICT_FIELDS + (COLUMN, "last_synced", "last_edited_date")
    if not has_column(conn):
        return {}
    row = conn.execute(f"SELECT {', '.join(cols)} FROM observations WHERE id = ?", (record_id,)).fetchone()
    return dict(zip(cols, row)) if row else {}


def resolve(conn, record_id: int, choice: str, incoming: Dict, fields: Iterable[str] = ()) -> None:
    """Wil's answer to a conflict. 'observatum' keeps the record and remembers iRecord's
    'last edited on'; 'irecord' writes iRecord's copy as a sync would (every field the
    download supplied: `incoming` is the sync's own set of changes, so the common name,
    family and sort key follow the species). The caller commits."""
    stamp = incoming.get("last_edited_date")
    if choice == "observatum":
        conn.execute("UPDATE observations SET last_edited_date = ? WHERE id = ?", (stamp, record_id))
        return
    if choice != "irecord":
        raise ValueError(f"unknown choice {choice!r}")
    sets = {k: v for k, v in incoming.items() if v not in (None, "") and k != "id"}
    sets.update(last_edited_date=stamp, last_synced=now())
    conn.execute(f"UPDATE observations SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?",
                 [*sets.values(), record_id])


__all__ = ["COLUMN", "UPDATE", "KEEP", "CONFLICT", "CONFLICT_FIELDS", "IRECORD_OWNED", "LABELS", "cleared", "has_column",
           "ensure_schema", "mark_edited", "differing", "decide", "held_row", "resolve", "now"]
