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
    drawer is refused by plan() (move it deliberately, with move=True). A move writes
    both fields, so a specimen ends up recorded exactly where it was ticked.
  * remove=[ids] takes specimens out of THIS drawer: storage and drawer are cleared
    (written as NULL); condition and preparation are never touched by a removal. Only a
    specimen recorded in this drawer can be removed.
  * condition and preparation_type are only filled where empty; a recorded value stays.
  * Only these four columns can be written; anything else raises.
  * outline() says what a plan does in words for the preview (add / move / remove);
    drawers() lists every drawer with its count; in_drawer() the specimens in one.
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


def placed(spec: Dict) -> bool:
    """Recorded in any drawer or storage location."""
    return bool((spec.get("storage_location") or "").strip() or (spec.get("drawer_number") or "").strip())


def here(spec: Dict, storage: str, drawer: str) -> bool:
    """Recorded in exactly this drawer."""
    return placed(spec) and not elsewhere(spec, storage, drawer)


def where(storage: str, drawer: str) -> str:
    """'Cabinet 1 · Drawer 3' (either part may be blank)."""
    return " · ".join(x for x in ((storage or "").strip(), (drawer or "").strip()) if x)


def plan(specs: Iterable[Dict], ticked: Iterable[int], storage: str, drawer: str,
         condition: Optional[str] = None, preparation: Optional[str] = None,
         move: bool = False, remove: Iterable[int] = ()) -> List[Tuple[int, str, str, str]]:
    """The changes ticking these specimens into this drawer (and taking `remove` out of
    it) would make."""
    storage, drawer = (storage or "").strip(), (drawer or "").strip()
    if not storage and not drawer:
        raise ValueError("give a storage location or a drawer")
    by_id = {s["id"]: s for s in specs}
    ticked = list(ticked)
    remove = list(remove)
    both = set(ticked) & set(remove)
    if both:
        raise ValueError(f"specimen {min(both)} is both ticked and to be removed")
    changes = []
    for sid in ticked:
        s = by_id.get(sid)
        if s is None:
            raise ValueError(f"no specimen {sid}")
        away = elsewhere(s, storage, drawer)
        if away and not move:
            raise ValueError(f"specimen {sid} ({s.get('species_name')}) is recorded in "
                             f"{s.get('storage_location') or ''} {s.get('drawer_number') or ''}".strip())
        for field, new in (("storage_location", storage), ("drawer_number", drawer)):
            # a move writes both fields (a blank one clears the old value); otherwise
            # only a given value is written
            if (new or away) and (s.get(field) or "") != new:
                changes.append((sid, field, s.get(field) or "", new))
        for field, new in (("condition", condition), ("preparation_type", preparation)):
            new = (new or "").strip()
            if new and _blank(s.get(field)):
                changes.append((sid, field, "", new))
    for sid in remove:
        s = by_id.get(sid)
        if s is None:
            raise ValueError(f"no specimen {sid}")
        if not here(s, storage, drawer):
            raise ValueError(f"specimen {sid} ({s.get('species_name')}) is not recorded in "
                             f"{where(storage, drawer)}, so it cannot be removed from it")
        for field in ("storage_location", "drawer_number"):
            if s.get(field) is not None and s.get(field) != "":
                changes.append((sid, field, s.get(field), ""))
    return changes


def in_drawer(specs: Iterable[Dict], storage: str, drawer: str) -> List[int]:
    """Ids of the specimens recorded in exactly this drawer."""
    return [s["id"] for s in specs if here(s, storage, drawer)]


def drawers(specs: Iterable[Dict]) -> List[Tuple[str, str, int]]:
    """[(storage, drawer, n)] for every drawer in use, storage then drawer in natural
    order (Drawer 2 before Drawer 10)."""
    import re

    def nat(x):
        return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", x)]
    n: Dict[Tuple[str, str], int] = {}
    for s in specs:
        if placed(s):
            k = ((s.get("storage_location") or "").strip(), (s.get("drawer_number") or "").strip())
            n[k] = n.get(k, 0) + 1
    return [(st, dr, c) for (st, dr), c in sorted(n.items(), key=lambda kv: (nat(kv[0][0]), nat(kv[0][1])))]


def outline(changes: Iterable[Tuple[int, str, str, str]], specs: Iterable[Dict],
            storage: str, drawer: str) -> List[Tuple[str, int]]:
    """What a plan does, in words: [("Add to Cabinet 2 · Drawer 1", 5),
    ("Move from Cabinet 1 · Drawer 3 to Cabinet 2 · Drawer 1", 2),
    ("Remove from Cabinet 2 · Drawer 1", 3), ("Fill condition", 4), ...]."""
    by_id = {s["id"]: s for s in specs}
    to = where(storage, drawer)
    moved: Dict[int, None] = {}
    filled: Dict[str, set] = {}
    for sid, field, _, _ in changes:
        if field in ("storage_location", "drawer_number"):
            moved[sid] = None
        else:
            filled.setdefault(field, set()).add(sid)
    counts: Dict[str, int] = {}
    for sid in moved:
        s = by_id[sid]
        old = where(s.get("storage_location"), s.get("drawer_number"))
        new = {f: a for i, f, _, a in changes if i == sid and f in ("storage_location", "drawer_number")}
        gone = all(not (new.get(f, s.get(f)) or "").strip() for f in ("storage_location", "drawer_number"))
        if gone:
            key = f"Remove from {old}"
        elif not old:
            key = f"Add to {to}"
        elif old == to:
            key = f"Tidy the spelling in {to}"     # e.g. stray spaces
        else:
            key = f"Move from {old} to {to}"
        counts[key] = counts.get(key, 0) + 1
    # specimens already in this drawer that only have condition/preparation filled
    names = {"condition": "Fill condition", "preparation_type": "Fill preparation"}
    order = sorted(counts.items(), key=lambda kv: (not kv[0].startswith("Add"),
                                                   not kv[0].startswith("Move"), kv[0]))
    return order + [(names[f], len(ids)) for f, ids in filled.items()]


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
                f"WHERE id = ? AND COALESCE({field}, '') = ?",
                (after if str(after or "").strip() else None, sid, before or ""))   # cleared -> NULL
            if cur.rowcount != 1:
                raise RuntimeError(f"specimen {sid} changed since it was read ({field}); "
                                   "nothing was written")
            n += 1
    return n
