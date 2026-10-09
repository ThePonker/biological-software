"""drawer_assign -- record which drawer specimens are in (backlog A1). Pure sqlite, no Qt.

The "drawer in hand" workflow: take a drawer out, tick each specimen in it, write the
storage location and drawer onto those specimens -- plus, optionally, condition and
preparation type where they are empty. Curator plans layouts; this records what is.

    specs = load_specimens(conn)                   # checklist order, genus derived
    changes = plan(specs, ticked_ids, storage="Cabinet 2", drawer="Drawer 1",
                   condition="Good")               # [(id, field, before, after)]
    apply(conn, changes)                           # one transaction

Rules:
  * storage_location and drawer_number are written on every ticked specimen -- ticking
    one says "it is here" -- except that a specimen already recorded in a DIFFERENT
    drawer is refused by plan() (move it deliberately, with move=True).
  * condition and preparation_type are only filled where empty; a recorded value stays.
  * Only these four columns can be written; anything else raises.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, Iterable, List, Optional, Tuple

WRITABLE = ("storage_location", "drawer_number", "condition", "preparation_type")


def genus_of(species_name: str) -> str:
    parts = (species_name or "").split()
    return parts[0] if parts else ""


def _blank(v) -> bool:
    return not str(v or "").strip()


def load_specimens(conn: sqlite3.Connection, checklist=None) -> List[Dict]:
    """Every specimen, in taxonomic order, with genus derived from the name.

    UKSI order, then re-sorted within each family a checklist covers (shared/checklists),
    so a drawer of Carabidae runs Carabus, Cychrus, Leistus... as it is laid out."""
    cur = conn.cursor()
    cur.row_factory = sqlite3.Row          # this query only; the caller's connection is untouched
    rows = cur.execute(
        """SELECT id, species_name, order_name, family, date_collected, site_name, sex,
                  storage_location, drawer_number, condition, preparation_type,
                  taxonomic_sort_key
           FROM specimens
           ORDER BY CASE WHEN taxonomic_sort_key IS NULL THEN 1 ELSE 0 END,
                    taxonomic_sort_key, species_name, date_collected, id""").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["genus"] = genus_of(d["species_name"])
        out.append(d)
    from shared import checklist_order
    return checklist_order.reorder(out, checklist)


def tree(specs: Iterable[Dict]) -> List[Tuple[str, List[Tuple[str, List[Tuple[str, int]]]]]]:
    """[(order, [(family, [(genus, n)])])] in the order the specimens come (taxonomic)."""
    out: Dict[str, Dict[str, Dict[str, int]]] = {}
    for s in specs:
        o = s.get("order_name") or "(no order)"
        f = s.get("family") or "(no family)"
        g = s.get("genus") or "(no genus)"
        out.setdefault(o, {}).setdefault(f, {}).setdefault(g, 0)
        out[o][f][g] += 1
    return [(o, [(f, list(gs.items())) for f, gs in fams.items()]) for o, fams in out.items()]


def elsewhere(spec: Dict, storage: str, drawer: str) -> bool:
    """Already recorded in a different drawer (or storage location)."""
    s, d = (spec.get("storage_location") or "").strip(), (spec.get("drawer_number") or "").strip()
    if not s and not d:
        return False
    return (s, d) != ((storage or "").strip(), (drawer or "").strip())


def plan(specs: Iterable[Dict], ticked: Iterable[int], storage: str, drawer: str,
         condition: Optional[str] = None, preparation: Optional[str] = None,
         move: bool = False) -> List[Tuple[int, str, str, str]]:
    """The changes ticking these specimens into this drawer would make."""
    storage, drawer = (storage or "").strip(), (drawer or "").strip()
    if not storage and not drawer:
        raise ValueError("give a storage location or a drawer")
    by_id = {s["id"]: s for s in specs}
    changes = []
    for sid in ticked:
        s = by_id.get(sid)
        if s is None:
            raise ValueError(f"no specimen {sid}")
        if elsewhere(s, storage, drawer) and not move:
            raise ValueError(f"specimen {sid} ({s.get('species_name')}) is recorded in "
                             f"{s.get('storage_location') or ''} {s.get('drawer_number') or ''}".strip())
        for field, new in (("storage_location", storage), ("drawer_number", drawer)):
            if new and (s.get(field) or "") != new:
                changes.append((sid, field, s.get(field) or "", new))
        for field, new in (("condition", condition), ("preparation_type", preparation)):
            new = (new or "").strip()
            if new and _blank(s.get(field)):
                changes.append((sid, field, "", new))
    return changes


def summary(changes: Iterable[Tuple[int, str, str, str]]) -> Dict[str, int]:
    """{field: number of specimens changed}."""
    out: Dict[str, int] = {}
    for _, field, _, _ in changes:
        out[field] = out.get(field, 0) + 1
    return out


def apply(conn: sqlite3.Connection, changes: Iterable[Tuple[int, str, str, str]]) -> int:
    """Write the changes in one transaction; each guarded by its expected 'before'."""
    n = 0
    with conn:
        for sid, field, before, after in changes:
            if field not in WRITABLE:
                raise ValueError(f"not a curatorial field: {field}")
            cur = conn.execute(
                f"UPDATE specimens SET {field} = ?, updated_at = CURRENT_TIMESTAMP "
                f"WHERE id = ? AND COALESCE({field}, '') = ?", (after, sid, before or ""))
            if cur.rowcount != 1:
                raise RuntimeError(f"specimen {sid} changed since it was read ({field}); "
                                   "nothing was written")
            n += 1
    return n
