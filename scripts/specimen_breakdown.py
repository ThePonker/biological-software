"""specimen_breakdown -- the rules behind report_specimens_without_records.py (11 Oct 2026).

Specimens with no field record (tier "no match", or "checked: no field record", in
shared/specimen_links.py) are sorted into groups, so Wil can decide which become records:

  1  Wil's, complete       species TVK + full date + grid ref (1 km or finer), nothing near
                           -> one new observation per species + date + grid ref, quantity =
                           number of specimens (a minimum count). Sub-group: Commercial
                           (project) / Personal / unknown, from the records Wil made nearby.
  2  Wil's, near miss      an observation of the same species within NEAR_DAYS days and
                           within NEAR_M metres or at the same site -- probably a link, not a
                           new record (also: same date and grid ref, same genus, other species)
  3  Wil's, details missing  no TVK / no or unreadable date / no or unreadable or coarse grid ref
  4  someone else's        collector is not Wil -> contributed_observations; likely historic
                           when collected before HISTORIC_BEFORE
  5  recorded elsewhere    (a flag on any of the above) the same species, date and grid ref in
                           recording_scheme or contributed_observations ("exact"), or within
                           NEAR_DAYS / NEAR_M ("close")

Whose specimen: the collector field names Wil (alone or with others), see is_wil(). A blank
collector falls back to the determiner. Specimens Wil collected and someone else determined
(Falk, Telfer, ...) are his records with that determiner.

Pure Python over rows the report loads; nothing here opens or writes a database.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from shared.osgb import gridref_to_en
from shared.record_match import blank, comparable_people, norm_ref, norm_text, same_person

NEAR_DAYS = 7          # near miss / close: within this many days either side
NEAR_M = 1000          # ... and grid-square centres within this distance (metres)
VISIT_M = 2000         # a record Wil made that day within this distance = the same visit
SEASON_DAYS = 30       # a Commercial survey visit within this many days, nearby = looks Commercial
COARSEST_M = 1000      # grid refs coarser than 1 km are "vague"
HISTORIC_BEFORE = "2000-01-01"

_WIL_WORDS = re.compile(r"^(he+ney|wjh)$")


def is_wil(name) -> bool:
    """'Heeney, W.J.', 'W.J. Heeney', 'Wil J. Heeney', 'Heeeney, WJ.', 'Heeney. W.J.', 'WJH',
    and joint entries naming him ('Lamin, J., Heeney, W.J.') -- True."""
    return any(_WIL_WORDS.match(w) for w in norm_text(name).split())


def owner(collector, determiner) -> str:
    """'wil' or 'other' (blank collector: decided by the determiner)."""
    if not blank(collector):
        return "wil" if is_wil(collector) else "other"
    return "wil" if is_wil(determiner) else "other"


def day(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v).strip()) if len(str(v).strip()) == 10 else None
    except (TypeError, ValueError):
        return None


def centre(ref) -> Optional[Tuple[float, float, int]]:
    p = gridref_to_en(norm_ref(ref)) if not blank(ref) else None
    return (p[0] + p[2] / 2, p[1] + p[2] / 2, p[2]) if p else None


def dist(a, b) -> Optional[float]:
    if not a or not b:
        return None
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def missing(tvk, dt, ref) -> List[str]:
    """What stops a specimen becoming a record: [] when complete."""
    out = []
    if blank(tvk):
        out.append("no species TVK")
    if blank(dt):
        out.append("no date")
    elif day(dt) is None:
        out.append(f"vague or unreadable date '{dt}'")
    if blank(ref):
        out.append("no grid ref")
    else:
        c = centre(ref)
        if c is None:
            out.append(f"unreadable grid ref '{ref}'")
        elif c[2] > COARSEST_M:
            out.append(f"grid ref coarser than 1 km '{ref}'")
    return out


class SpatialIndex:
    """Points bucketed in CELL-metre squares; near(p, r) yields (item, distance) within r."""
    CELL = 2000

    def __init__(self):
        self.cells = defaultdict(list)

    def add(self, p, item):
        if p:
            self.cells[(int(p[0] // self.CELL), int(p[1] // self.CELL))].append((p, item))

    def near(self, p, r):
        if not p:
            return
        k = int(r // self.CELL) + 1
        cx, cy = int(p[0] // self.CELL), int(p[1] // self.CELL)
        for x in range(cx - k, cx + k + 1):
            for y in range(cy - k, cy + k + 1):
                for q, item in self.cells.get((x, y), ()):
                    d = dist(p, q)
                    if d <= r:
                        yield item, d


def is_commercial(record_type) -> bool:
    return str(record_type or "").strip().lower().startswith("comm")


def genus(name) -> str:
    w = str(name or "").split()
    return w[0] if w else ""


class Records:
    """One table of records (observations, recording_scheme or contributed_observations) as
    dicts with id, species_tvk, species_name, date, grid_ref, recorder, site_name and, for
    observations, record_type, project_name, client, embargo_status, embargo_until.
    rollup: {tvk: species tvk} (subspecies counted as their species) -- optional."""

    def __init__(self, rows: Iterable[Dict], rollup: Optional[Dict[str, str]] = None):
        self.rollup = rollup or {}
        self.by_sp = defaultdict(list)
        self.by_key = defaultdict(list)
        self.by_date = defaultdict(SpatialIndex)
        self.rows = []
        for r in rows:
            r = dict(r)
            r["_day"], r["_c"] = day(r.get("date")), centre(r.get("grid_ref"))
            r["_site"] = norm_text(r.get("site_name"))
            self.rows.append(r)
            if blank(r.get("species_tvk")):
                continue
            sp = self.sp(r["species_tvk"])
            self.by_sp[sp].append(r)
            self.by_key[(sp, r.get("date"), norm_ref(r.get("grid_ref")))].append(r)
            if r["_day"]:
                self.by_date[r["date"]].add(r["_c"], r)

    def sp(self, tvk):
        return self.rollup.get(tvk, tvk)

    def exact(self, s) -> List[Dict]:
        return list(self.by_key.get((self.sp(s["tvk"]), s["date"], norm_ref(s["ref"])), []))

    def near(self, s, days=NEAR_DAYS, metres=NEAR_M) -> List[Tuple[Dict, int, Optional[float]]]:
        """Same species, within days, and within metres or at the same site (exact matches
        left out). [(row, days apart, metres or None)] nearest first."""
        sd, sc, site = day(s["date"]), centre(s["ref"]), norm_text(s.get("site"))
        if not sd:
            return []
        exact_ids = {id(r) for r in self.exact(s)}
        out = []
        for r in self.by_sp.get(self.sp(s["tvk"]), ()):
            if id(r) in exact_ids or not r["_day"]:
                continue
            dd = abs((r["_day"] - sd).days)
            if dd > days:
                continue
            d = dist(sc, r["_c"])
            if (d is not None and d <= metres) or (site and r["_site"] == site):
                out.append((r, dd, d))
        out.sort(key=lambda x: (x[1], x[2] if x[2] is not None else 1e12))
        return out


def person_ok(collector, recorder) -> bool:
    """Collector and recorder do not name different people."""
    return not comparable_people(collector, recorder) or same_person(collector, recorder)


class CommercialRule:
    """Personal / Commercial (project) / unknown for one of Wil's complete specimens, from the
    observations around it. In order:
      same visit   observations Wil made that day within VISIT_M: all Commercial of one
                   project -> that project; all Personal -> Personal; mixed -> unknown
      season       else a Commercial project with a record within SEASON_DAYS and VISIT_M
                   -> looks Commercial (that project)
      site name    else the site name is a Commercial project's site / name -> unknown
      place        else observations within VISIT_M on other dates: only Personal ->
                   Personal (presumed); some Commercial -> unknown; none at all -> unknown
                   (no field records from this place: perhaps a survey not yet entered)"""

    def __init__(self, obs: Records):
        self.obs = obs
        self.projects = defaultdict(SpatialIndex)     # project -> places with dates
        self.places = SpatialIndex()                  # every observation: kind + project
        self.sites = defaultdict(set)                 # normalised site / project name -> projects
        self.terms = {}
        emb = defaultdict(Counter)
        for r in obs.rows:
            self.places.add(r["_c"], (r.get("record_type"), (r.get("project_name") or "").strip()))
            if not is_commercial(r.get("record_type")) or blank(r.get("project_name")):
                continue
            p = r["project_name"].strip()
            self.projects[p].add(r["_c"], r["_day"])
            for n in (r.get("site_name"), p):
                if norm_text(n):
                    self.sites[norm_text(n)].add(p)
            emb[p][(r.get("client"), r.get("embargo_status"), r.get("embargo_until"))] += 1
        for p, c in emb.items():
            (client, st, until), n = c.most_common(1)[0]
            self.terms[p] = {"client": client, "embargo_status": st, "embargo_until": until,
                             "mixed_embargo": len({k[1:] for k in c}) > 1}

    def classify(self, s) -> Tuple[str, str, str]:
        """(sub-group 'Commercial' / 'Personal' / 'unknown', project or '', why)."""
        sc, sd = centre(s["ref"]), day(s["date"])
        same_day = Counter()
        for r, _d in self.obs.by_date[s["date"]].near(sc, VISIT_M) if sd else ():
            if not person_ok(s.get("collector"), r.get("recorder")):
                continue
            kind = "Commercial" if is_commercial(r.get("record_type")) else "Personal"
            same_day[(kind, (r.get("project_name") or "").strip() if kind == "Commercial" else "")] += 1
        if same_day:
            what = ", ".join(f"{k[0]}{' ' + k[1] if k[1] else ''} {n}" for k, n in same_day.items())
            if len(same_day) == 1:
                (kind, proj), = same_day
                return kind, proj, f"same visit: records that day within {VISIT_M} m ({what})"
            return "unknown", "", f"same day, records of more than one kind within {VISIT_M} m ({what})"
        if sd:
            season = []
            for p, idx in self.projects.items():
                for pd, d in idx.near(sc, VISIT_M):
                    if pd and abs((pd - sd).days) <= SEASON_DAYS:
                        season.append(p)
                        break
            if len(season) == 1:
                return ("Commercial", season[0], f"a {season[0]} survey record within "
                        f"{SEASON_DAYS} days and {VISIT_M} m (no records that day)")
            if season:
                return "unknown", "", "near more than one Commercial survey: " + ", ".join(season)
        hit = self.sites.get(norm_text(s.get("site")))
        if hit:
            return ("unknown", "", "site name matches Commercial project "
                    + ", ".join(sorted(hit)) + f" but no survey record within {SEASON_DAYS} days nearby")
        kinds = Counter()
        for (rt, proj), _d in self.places.near(sc, VISIT_M):
            kinds["Commercial " + proj if is_commercial(rt) else "Personal"] += 1
        if not kinds:
            return ("unknown", "", f"no field records of any kind within {VISIT_M} m "
                    "(a survey not yet entered?)")
        what = ", ".join(f"{k} {n}" for k, n in kinds.most_common(4))
        if set(kinds) == {"Personal"}:
            return ("Personal", "", f"presumed: only Personal records within {VISIT_M} m, "
                    f"other dates ({what})")
        return ("unknown", "", f"no records that day; Commercial records within {VISIT_M} m "
                f"on other dates ({what})")


def record_key(s, rollup=None) -> str:
    tvk = (rollup or {}).get(s["tvk"], s["tvk"])
    return f"{tvk}|{s['date']}|{norm_ref(s['ref'])}"


def proposed_records(specs: List[Dict], rollup=None) -> Dict[str, Dict]:
    """One proposed record per key (species + date + grid ref): quantity = specimens, the most
    common collector / determiner / site / sub-group among them; 'conflict' notes a
    disagreement in sub-group or project."""
    by = defaultdict(list)
    for s in specs:
        by[record_key(s, rollup)].append(s)
    out = {}
    for k, ss in by.items():
        def top(f):
            c = Counter(x.get(f) for x in ss if not blank(x.get(f)))
            return c.most_common(1)[0][0] if c else None
        kinds = {(x.get("sub"), x.get("project")) for x in ss}
        out[k] = {"key": k, "quantity": len(ss), "species_name": top("name"),
                  "date": ss[0]["date"], "grid_ref": top("ref"), "site_name": top("site"),
                  "recorder": top("collector"), "determiner": top("determiner"),
                  "sub": top("sub"), "project": top("project"),
                  "conflict": "; ".join(f"{a} {b}".strip() for a, b in sorted(kinds, key=str))
                  if len(kinds) > 1 else ""}
    return out


def inside(a, b) -> bool:
    """Square a (e, n, size from gridref_to_en) lies within square b."""
    return (b[0] <= a[0] and a[0] + a[2] <= b[0] + b[2]
            and b[1] <= a[1] and a[1] + a[2] <= b[1] + b[2])
