"""What the Mapping tab maps: a selection, a data source and filters -> the records, through
ONE query builder (build_query). Backlog item 4 (review SRCH18, MAP1-9/11/12/17), 10 Oct 2026.
Read-only; no Qt.

Selection -- chips, each one of:
    {"kind": "taxon", "tvk", "scientific_name", "rank"}  a UKSI taxon of any rank: its records
        and everything below it, old names included (services/map_taxa.py);
    {"kind": "group", "label"}                            a taxon group (shared/taxon_groups.py).
The chips are alternatives: the map shows the union of their records, each record once.
No chips = every record of the source.

Data sources, split as the rest of the suite splits them:
    personal     observations that are not Commercial
    commercial   Commercial observations (optionally one project)
    collection   specimens (Insect Collection)
    scheme       recording_scheme
    contributed  contributed_observations
    all          all five, each record once (MAP2): a specimen that has an observation (its
                 observation_id, else the same TVK, date and grid ref) is shown as that
                 observation; a scheme row that is one of your observations (same iRecord id)
                 likewise.
Embargo (MAP1/OBS-12): an observation under an active embargo -- embargo_status 'Active' and
embargo_until after today, the iRecord export's rule -- is not mapped unless
include_embargoed is set; a specimen whose observation is embargoed is held back with it.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import paths
from shared.db_open import connect_ro
from shared.species_filter import _literals
from shared.taxon_groups import group_filter_sql, group_label, group_values

from .filter_builder import TAB_COLUMNS, TabColumns, build_where_cols
from .map_taxa import GROUP_COLUMN, STORED_COLUMN, TaxonContext, get_context

SOURCES: List[Tuple[str, str]] = [
    ("personal", "Personal records"), ("commercial", "Commercial records"),
    ("collection", "Insect Collection"), ("scheme", "Recording Scheme"),
    ("contributed", "Contributed records"), ("all", "All records")]
SOURCE_LABELS = dict(SOURCES)
SOURCE_TABLES = {
    "personal": ("observations",), "commercial": ("observations",),
    "collection": ("specimens",), "scheme": ("recording_scheme",),
    "contributed": ("contributed_observations",),
    "all": ("observations", "specimens", "recording_scheme", "contributed_observations"),
}


@dataclass(frozen=True)
class MapTable:
    label: str            # the Source column of the square's record list
    date: str
    person: str
    count: str            # "Count / code" column (MAP6: observations keep it in quantity)
    cols: TabColumns      # for the shared filter builder


TABLES: Dict[str, MapTable] = {
    "observations": MapTable("Observation", "date", "recorder", "quantity",
                             TAB_COLUMNS["observations"]),
    "specimens": MapTable("Specimen", "date_collected", "collector", "specimen_code",
                          TAB_COLUMNS["specimens"]),
    "recording_scheme": MapTable("Recording scheme", "date", "recorder", "quantity",
                                 TAB_COLUMNS["recording_scheme"]),
    "contributed_observations": MapTable(
        "Contributed", "date", "recorder", "quantity",
        TabColumns(table="contributed_observations", group=None, notes=("comment",),
                   verification=None, record_type=None)),
}

_COMMERCIAL = "LOWER(COALESCE(record_type, '')) LIKE 'comm%'"
_EMBARGOED = "(COALESCE({p}embargo_status, '') = 'Active' AND COALESCE({p}embargo_until, '') > ?)"
# a specimen's observation: the stored link, else the same taxon, date and grid ref
_SPECIMEN_OBS = ("(o.id = specimens.observation_id OR (specimens.observation_id IS NULL "
                 "AND o.species_tvk = specimens.species_tvk "
                 "AND o.date = specimens.date_collected "
                 "AND REPLACE(UPPER(o.grid_ref), ' ', '') = REPLACE(UPPER(specimens.grid_ref), ' ', '')))")


@dataclass
class MapFilters:
    """The filter panel's values. Dates are ISO (the panel reads any usual form, MAP3)."""
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    vc: Optional[int] = None
    recorder: str = ""
    site: str = ""
    project: str = ""                      # Commercial only
    include_embargoed: bool = False

    def builder_keys(self) -> dict:
        """The keys services/filter_builder.py understands ('~' = contains)."""
        out = {"date_from": self.date_from, "date_to": self.date_to}
        if self.vc:
            out["vice_county"] = [str(int(self.vc))]
        if self.recorder.strip():
            out["recorder"] = ["~" + self.recorder.strip()]
        if self.site.strip():
            out["site_name"] = ["~" + self.site.strip()]
        return out


def _selection_sql(table: str, selection: List[dict], ctx: TaxonContext) -> Tuple[str, list]:
    """The selection on one table (chips OR'd); ('', []) for no selection."""
    if not selection:
        return "", []
    parts, params = [], []
    wanted = {c["tvk"] for c in selection if c.get("kind") == "taxon" and c.get("tvk")}
    if wanted:
        chosen, unknown, names = ctx.under(table, wanted)
        if chosen:
            parts.append(f"species_tvk IN ({_literals(chosen)})")
        if names:
            no_tvk = "COALESCE(species_tvk, '') = ''"
            if unknown:
                no_tvk += f" OR species_tvk IN ({_literals(unknown)})"
            parts.append(f"(({no_tvk}) AND species_name IN ({_literals(names)}))")
    stored = [(STORED_COLUMN[c["rank"]], c["scientific_name"]) for c in selection
              if c.get("kind") == "taxon" and c.get("rank") in STORED_COLUMN]
    if stored:
        orphans = ctx.orphans(table)
        if orphans:
            parts.append(f"(species_tvk IN ({_literals(orphans)}) AND (" + " OR ".join(
                f"{col} = ?" for col, _n in stored) + "))")
            params += [n for _c, n in stored]
    labels = [c["label"] for c in selection if c.get("kind") == "group"]
    if labels:
        sql, p = group_filter_sql(labels, known=ctx.known_groups.get(table, ()),
                                  group_col=GROUP_COLUMN.get(table) or "NULL",
                                  order_col="order_name", family_col="family")
        parts.append(f"({sql})")
        params += p
    return "(" + (" OR ".join(parts) or "0") + ")", params


def build_query(table: str, selection: List[dict], source: str, filters: MapFilters,
                ctx: TaxonContext, part: str = "mapped", today: Optional[str] = None
                ) -> Tuple[str, list]:
    """(WHERE clause, params) for one table: selection + source + filters. The one place
    the Mapping tab's records are chosen. `part`:
        'mapped'    the records the map shows;
        'embargoed' the records held back by the embargo rule (to say so on the map);
        'merged'    (source 'all') specimens / scheme rows shown once, as their observation.
    """
    today = today or _dt.date.today().isoformat()
    where, params = ["COALESCE(grid_ref, '') <> ''"], []
    sql, p = _selection_sql(table, selection, ctx)
    if sql:
        where.append(sql)
        params += p
    sql, p = build_where_cols(TABLES[table].cols, filters.builder_keys())
    if sql:
        where.append(sql)
        params += p
    hold = not filters.include_embargoed
    if table == "observations":
        if source == "personal":
            where.append(f"NOT {_COMMERCIAL}")
        elif source == "commercial":
            where.append(_COMMERCIAL)
            if filters.project:
                where.append("project_name = ?")
                params.append(filters.project)
        if part == "embargoed":
            where.append(_EMBARGOED.format(p=""))
            params.append(today)
        elif part == "merged":
            where.append("0")
        elif hold:
            where.append("NOT " + _EMBARGOED.format(p=""))
            params.append(today)
    elif table == "specimens":
        any_obs = f"EXISTS (SELECT 1 FROM observations o WHERE {_SPECIMEN_OBS})"
        held = (f"EXISTS (SELECT 1 FROM observations o WHERE {_SPECIMEN_OBS} AND "
                f"{_EMBARGOED.format(p='o.')})")
        if part == "embargoed":                # (in 'all' they are counted as their observation)
            where.append(held if source != "all" else "0")
            params += [today] if source != "all" else []
        elif part == "merged":
            where += [any_obs] if source == "all" else ["0"]
            if source == "all" and hold:       # the embargoed ones are counted as held back
                where.append("NOT " + held)
                params.append(today)
        elif source == "all":
            where.append("NOT " + any_obs)
        elif hold:
            where.append("NOT " + held)
            params.append(today)
    elif table == "recording_scheme":
        mine = ("COALESCE(irecord_id, '') <> '' AND irecord_id IN (SELECT irecord_id FROM "
                "observations WHERE COALESCE(irecord_id, '') <> ''"
                + (" AND NOT " + _EMBARGOED.format(p="") if hold else "") + ")")
        if part == "embargoed":
            where.append("0")
        elif source == "all":
            where.append(mine if part == "merged" else f"NOT ({mine})")
            if hold:
                params.append(today)
        elif part == "merged":
            where.append("0")
    elif part != "mapped":
        where.append("0")
    return " AND ".join(where), params


@dataclass
class MapResult:
    records: List[dict] = field(default_factory=list)
    chip_counts: List[int] = field(default_factory=list)     # mapped records per chip (MAP7)
    embargoed: int = 0                                        # held back by the embargo rule
    merged: int = 0                                           # shown once, as their observation


def fetch(selection: List[dict], source: str = "personal", filters: Optional[MapFilters] = None,
          db_path=None, uksi_path=None) -> MapResult:
    """The records for the map, with what was held back. Each record: source, table, id,
    species_name, tvk, common_name, grid_ref, date, year, site_name, person, extra, vc,
    chips (indexes of the chips it falls under) and species (its key for richness)."""
    filters = filters or MapFilters()
    db = db_path or paths.OBSERVATUM_DB
    ctx = get_context(db, uksi_path)
    res = MapResult(chip_counts=[0] * len(selection))
    tests = _chip_tests(selection, ctx)
    want_group = any(c.get("kind") == "group" for c in selection)
    conn = connect_ro(db)
    try:
        for table in SOURCE_TABLES.get(source, SOURCE_TABLES["personal"]):
            mt = TABLES[table]
            where, params = build_query(table, selection, source, filters, ctx)
            rtype = "record_type" if table == "observations" else "NULL"
            gcol = GROUP_COLUMN.get(table)
            gexpr = gcol if (want_group and gcol) else "NULL"
            sql = (f"SELECT id, species_name, species_tvk, common_name, grid_ref, {mt.date}, "
                   f"site_name, {mt.person}, {mt.count}, vc_number, {rtype}, {gexpr}, "
                   f"order_name, family FROM {table} WHERE {where}")
            for (rid, sp, tvk, common, gr, d, site, person, extra, vc, rt, grp, order,
                 family) in conn.execute(sql, params):
                label = mt.label
                if table == "observations":
                    label = "Commercial" if str(rt or "").lower().startswith("comm") else "Personal"
                chips = [i for i, test in enumerate(tests)
                         if test(tvk, sp, grp, order, family)] if selection else []
                for i in chips:
                    res.chip_counts[i] += 1
                res.records.append({
                    "source": label, "table": table, "id": rid, "species_name": sp or "",
                    "tvk": tvk or "", "common_name": common or "", "grid_ref": gr,
                    "date": d or "", "year": _year(d), "site_name": site or "",
                    "person": person or "", "extra": "" if extra is None else str(extra),
                    "vc": vc if isinstance(vc, int) else None, "chips": chips,
                    "species": ctx.species_key(tvk, sp)})
            for part in ("embargoed", "merged"):
                w, p = build_query(table, selection, source, filters, ctx, part=part)
                n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {w}", p).fetchone()[0]
                setattr(res, part, getattr(res, part) + n)
    finally:
        conn.close()
    return res


def _chip_tests(selection: List[dict], ctx: TaxonContext):
    """One test per chip: does a record (tvk, name, stored group, order, family) fall under it?"""
    from shared.taxon_groups import taxon_group
    tests = []
    for chip in selection:
        if chip.get("kind") == "group":
            values = set(group_values(chip["label"], [v for vs in ctx.known_groups.values()
                                                      for v in vs]))
            label = chip["label"]

            def test(tvk, name, grp, order, family, values=values, label=label):
                g = (grp or "").strip() or taxon_group(order, family) or ""
                return g in values or group_label(g) == label
        else:
            target = chip.get("tvk")
            stored = {"family": 1, "order_name": 0}.get(STORED_COLUMN.get(chip.get("rank")))
            sci = chip.get("scientific_name")

            def test(tvk, name, grp, order, family, target=target, stored=stored, sci=sci):
                anc = ctx.ancestors(tvk, name)
                if target in anc:
                    return True        # else a parentless UKSI taxon, by its stored column
                return stored is not None and len(anc) == 1 and (order, family)[stored] == sci
        tests.append(test)
    return tests


def _year(date_str) -> Optional[int]:
    try:
        y = int(str(date_str)[:4])
        return y if 1000 <= y <= 2999 else None
    except (TypeError, ValueError):
        return None


def vc_choices(db_path=None, vc_db_path=None) -> List[Tuple[int, str]]:
    """[(vc number, 'VC23 - Oxfordshire')] -- one entry per vice-county number held by any
    record table, named from vc_lookup.db (MAP8: the old list read names from the records,
    so one VC appeared under two spellings)."""
    names: Dict[int, str] = {}
    try:
        vconn = connect_ro(vc_db_path or paths.VC_LOOKUP_DB)
        try:
            names = {int(n): nm for n, nm in vconn.execute("SELECT vc_number, vc_name FROM vc_names")}
        finally:
            vconn.close()
    except Exception as e:
        print(f"[map_selection] VC names not read: {e}")
    nums = set()
    conn = connect_ro(db_path or paths.OBSERVATUM_DB)
    try:
        for table in TABLES:
            try:
                nums |= {int(r[0]) for r in conn.execute(
                    f"SELECT DISTINCT vc_number FROM {table} WHERE vc_number IS NOT NULL")
                    if str(r[0]).strip().isdigit()}
            except Exception:
                continue
    finally:
        conn.close()
    return [(n, f"VC{n} - {names[n]}" if n in names else f"VC{n}") for n in sorted(nums)]


def distinct_values(kind: str, db_path=None) -> List[str]:
    """Recorders / collectors ('recorder'), sites ('site') or Commercial projects ('project')
    across the record tables, for the filter boxes' completers."""
    conn = connect_ro(db_path or paths.OBSERVATUM_DB)
    out = set()
    try:
        for table, mt in TABLES.items():
            col = {"recorder": mt.person, "site": "site_name",
                   "project": "project_name" if table == "observations" else None}[kind]
            if not col:
                continue
            extra = f" AND {_COMMERCIAL}" if kind == "project" else ""
            out |= {str(r[0]).strip() for r in conn.execute(
                f"SELECT DISTINCT {col} FROM {table} WHERE TRIM(COALESCE({col}, '')) <> ''{extra}")}
    finally:
        conn.close()
    return sorted(out, key=str.casefold)
