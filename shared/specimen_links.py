"""specimen_links -- which observation (field record) a specimen is the same find as.

Moved here 11 Oct 2026 from scripts/report_specimen_observation_links.py so the report, the
link / unlink scripts and the Edit Specimen dialog's "Field record" box use one rule.

The link lives on the specimen: specimens.observation_id. A specimen Wil has checked and
found to have no field record carries the date-time he ticked it in
specimens.no_field_record_checked (added by scripts/add_specimen_link_check_column.py;
code here copes with the column missing). The two are kept mutually exclusive.

A specimen matches an observation with the same species TVK, the same date (date_collected
= date) and the same grid ref (case and spaces ignored, the Mapping rule), and -- where both
name somebody -- a collector and recorder naming the same person (shared/record_match.py).

Tiers, per specimen (match()):
  linked                    observation_id set (checked against the rule; mismatches flagged)
  checked: no field record  no_field_record_checked set (Wil looked; there is none)
  certain                   exactly one matching observation -- safe to link
  quantity short            exactly one, but more specimens on it (linked + certain) than
                            its quantity -- Wil checks
  ambiguous                 two or more matching observations -- Wil chooses
  recorder differs          same species, date and grid ref, collector and recorder disagree
  no match                  none

candidates() is the chooser's list for one specimen: same species (subspecies rolled up to
the species via shared/record_kinds.species_tvks) on the same date first, then any date.
"""
from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from datetime import date
from typing import Dict, List, Optional

from shared.record_match import blank, comparable_people, norm_ref, same_person

CHECK_COLUMN = "no_field_record_checked"

TIERS = ("linked", "checked: no field record", "certain", "quantity short", "ambiguous",
         "recorder differs", "no match")
TO_WORK_THROUGH = ("quantity short", "ambiguous", "recorder differs")


def has_check_column(conn: sqlite3.Connection) -> bool:
    """True once scripts/add_specimen_link_check_column.py has added the column."""
    return any(r[1] == CHECK_COLUMN for r in conn.execute("PRAGMA table_info(specimens)"))


# ---------------------------------------------------------------- whole-collection match

def load(conn):
    """(specimen rows, observation rows). Specimen rows end with the checked value (None
    when the column is not there yet)."""
    chk = CHECK_COLUMN if has_check_column(conn) else "NULL"
    spec = conn.execute(
        "SELECT id, specimen_code, species_name, species_tvk, date_collected, grid_ref, "
        f"collector, site_name, observation_id, sex, {chk} FROM specimens ORDER BY id").fetchall()
    obs = conn.execute(
        "SELECT id, species_tvk, date, grid_ref, recorder, record_type, project_name, "
        "site_name, sex, quantity FROM observations").fetchall()
    return spec, obs


def match(spec, obs) -> dict:
    """{"specimens": [{...per specimen, "tier", "cands": [(obs row, same_person)]}],
        "raw_text": n specimens matching on the exact stored grid-ref text (the review's
        1,337 rule), "rule": n matching on the Mapping rule, recorder not checked}"""
    by_key = defaultdict(list)
    for o in obs:
        if blank(o[1]) or blank(o[2]) or blank(o[3]):
            continue
        by_key[(o[1], o[2], norm_ref(o[3]))].append(o)
    obs_by_id = {o[0]: o for o in obs}
    out = {"specimens": [], "raw_text": 0, "rule": 0}
    for s in spec:
        sid, code, name, tvk, dt, ref, collector, site, linked, sex = s[:10]
        checked = s[10] if len(s) > 10 else None
        cands = []
        if not (blank(tvk) or blank(dt) or blank(ref)):
            cands = by_key.get((tvk, dt, norm_ref(ref)), [])
        if cands:
            out["rule"] += 1
        if any(o[3] == ref for o in cands):
            out["raw_text"] += 1
        scored = []
        for o in cands:
            both = comparable_people(collector, o[4])
            scored.append((o, same_person(collector, o[4]) if both else None))
        ok = [c for c in scored if c[1] is not False]
        agrees = None
        if not blank(linked):
            tier = "linked"
            o = obs_by_id.get(int(linked))
            scored = [(o, None)] if o else []
            agrees = any(c[0][0] == int(linked) for c in ok)
        elif not blank(checked):
            tier = "checked: no field record"
        elif len(ok) == 1:
            tier = "certain"
        elif len(ok) > 1:
            tier = "ambiguous"
        elif scored:
            tier = "recorder differs"
        else:
            tier = "no match"
        out["specimens"].append({"id": sid, "code": code, "name": name, "tvk": tvk,
                                 "date": dt, "ref": ref, "collector": collector,
                                 "site": site, "sex": sex, "tier": tier, "cands": scored,
                                 "ok": ok, "link_agrees": agrees, "checked": checked})
    # specimens already linked to an observation count against its quantity too, so linking
    # one of two by hand does not turn the other into "certain" on an observation of 1
    per_obs = Counter(s["ok"][0][0][0] for s in out["specimens"] if s["tier"] == "certain")
    per_obs.update(int(s[8]) for s in spec if not blank(s[8]))
    for s in out["specimens"]:
        if s["tier"] == "certain":
            o = s["ok"][0][0]
            q = o[9]
            if per_obs[o[0]] > 1 and isinstance(q, int) and q < per_obs[o[0]]:
                s["tier"] = "quantity short"
    return out


def certain_links(found) -> list:
    """[(specimen id, observation id)] for the certain tier -- what the link script writes."""
    return [(s["id"], s["ok"][0][0][0]) for s in found["specimens"] if s["tier"] == "certain"]


# ---------------------------------------------------------------- one specimen: the chooser

OBS_COLS = ("id", "species_name", "species_tvk", "date", "grid_ref", "site_name", "recorder",
            "quantity", "sex", "record_type", "project_name")


def get_observation(conn: sqlite3.Connection, oid) -> Optional[Dict]:
    if blank(oid):
        return None
    r = conn.execute(f"SELECT {', '.join(OBS_COLS)} FROM observations WHERE id = ?",
                     (int(oid),)).fetchone()
    return dict(zip(OBS_COLS, r)) if r else None


def sex_hint(spec_sex, obs_sex) -> str:
    """'yes' / 'no' / 'maybe' (observation says mixed) / '' (either not sexed)."""
    from shared.sex_summary import classify_sex
    o = (obs_sex or "").strip().lower()
    a = classify_sex(spec_sex)
    if a is None or not o:
        return ""
    if "mixed" in o or ("female" in o and "male" in o.replace("female", "")):
        return "maybe"
    b = classify_sex(obs_sex)
    if b is None:
        return ""
    return "yes" if a == b else "no"


def _binomial(name) -> str:
    words = [w for w in str(name or "").split() if not w.startswith("(")]
    return " ".join(words[:2])


def species_group_tvks(conn, tvk, name, uksi_conn=None) -> set:
    """The specimen's TVK plus every observation TVK that rolls up to the same species
    (subspecies, varieties) by shared/record_kinds.species_tvks. Exact TVK only when UKSI
    is not to hand."""
    if blank(tvk):
        return set()
    out = {tvk}
    if uksi_conn is None:
        return out
    try:
        from shared.record_kinds import species_tvks
        target = species_tvks(uksi_conn, [tvk]).get(tvk, tvk)
        out.add(target)
        bi = _binomial(name)
        if bi:
            near = [r[0] for r in conn.execute(
                "SELECT DISTINCT species_tvk FROM observations WHERE species_name LIKE ? "
                "AND species_tvk IS NOT NULL", (bi + "%",))]
            rolled = species_tvks(uksi_conn, near)
            out.update(t for t in near if rolled.get(t, t) == target)
    except sqlite3.Error:
        pass
    return out


def _day(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _distance_m(a, b) -> Optional[float]:
    from shared.osgb import gridref_centre
    pa, pb = gridref_centre(norm_ref(a)), gridref_centre(norm_ref(b))
    if not pa or not pb:
        return None
    return ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5


def link_counts(conn, oids, exclude_specimen=None) -> Dict[int, int]:
    """{observation id: specimens linked to it} (this specimen left out)."""
    ids = sorted({int(o) for o in oids})
    out: Dict[int, int] = {}
    for i in range(0, len(ids), 900):
        chunk = ids[i:i + 900]
        ph = ",".join("?" * len(chunk))
        q = (f"SELECT observation_id, COUNT(*) FROM specimens WHERE observation_id IN ({ph})"
             + (" AND id <> ?" if exclude_specimen else "") + " GROUP BY observation_id")
        args = chunk + ([int(exclude_specimen)] if exclude_specimen else [])
        out.update({int(k): n for k, n in conn.execute(q, args)})
    return out


def candidates(conn, spec: Dict, uksi_conn=None, any_date: bool = False, text: str = "",
               limit: int = 500) -> List[Dict]:
    """Observations the specimen could be, best first.

    spec: species_tvk, species_name, date_collected (ISO), grid_ref, collector, sex, id.
    Same species (rolled up) and same date, unless any_date. Order: same date, same grid ref,
    nearest, nearest in time. Each row adds: linked (other specimens on it), same_date,
    same_ref, rule (the report's match rule holds), distance_m, person (True/False/None),
    sex_hint."""
    tvks = species_group_tvks(conn, spec.get("species_tvk"), spec.get("species_name"),
                              uksi_conn)
    if not tvks:
        return []
    ph = ",".join("?" * len(tvks))
    sql = f"SELECT {', '.join(OBS_COLS)} FROM observations WHERE species_tvk IN ({ph})"
    args = list(tvks)
    sd = spec.get("date_collected")
    if not any_date:
        if blank(sd):
            return []
        sql += " AND date = ?"
        args.append(sd)
    rows = [dict(zip(OBS_COLS, r)) for r in conn.execute(sql, args)]
    t = (text or "").strip().casefold()
    if t:
        rows = [r for r in rows if t in " ".join(str(r[k] or "") for k in
                ("id", "date", "grid_ref", "site_name", "recorder", "project_name")).casefold()]
    ref, day = norm_ref(spec.get("grid_ref")), _day(sd)
    counts = link_counts(conn, [r["id"] for r in rows], spec.get("id"))
    for r in rows:
        r["linked"] = counts.get(r["id"], 0)
        r["same_date"] = not blank(sd) and r["date"] == sd
        r["same_ref"] = bool(ref) and norm_ref(r["grid_ref"]) == ref
        r["distance_m"] = _distance_m(spec.get("grid_ref"), r["grid_ref"])
        both = comparable_people(spec.get("collector"), r["recorder"])
        r["person"] = same_person(spec.get("collector"), r["recorder"]) if both else None
        r["rule"] = (r["same_date"] and r["same_ref"] and r["species_tvk"] == spec.get(
            "species_tvk") and r["person"] is not False)
        r["sex_hint"] = sex_hint(spec.get("sex"), r["sex"])
        d = _day(r["date"])
        r["_days"] = abs((d - day).days) if d and day else 10 ** 6
    rows.sort(key=lambda r: (not r["same_date"], not r["same_ref"],
                             r["distance_m"] if r["distance_m"] is not None else 1e12,
                             r["_days"], r["id"]))
    return rows[:limit]
