"""Species-counting switches: which records count, per data source (backlog A, 10 Oct 2026).

One rule for every screen that counts, lists or maps Wil's records. The kinds of name come
from shared/record_kinds.py (classify; UKSI rank for records with no rank); this module
holds WHICH kinds each source leaves out, and hands screens the excluded record ids in a
form they can use (a Python set, or a SQL fragment).

Sources and their switches (Settings > Species counting; the Scheme dashboard chips change
the same settings):
    observations      genus, family_plus, agg, sl      (all on by default)
                      Subspecies and s.s. are never left out: they ROLL UP to their species
                      for species counts (species + its ssp = 1; "X s.s." holds X's TVK).
                      Hybrids count as their own taxon.
    recording_scheme  all seven kinds (family_plus, genus, ss, sl, agg, hybrid, subsp)

Recording Scheme copies (F53 / Q59, 12 Oct): rows marked as an NBN copy of an iRecord record
(recording_scheme.duplicate_of, shared/scheme_duplicates.py) are left out by not_excluded_sql,
only_excluded_sql and export_sql ALWAYS -- not a switch: a copy is not a second record.
The Scheme tab's "Show duplicates" toggle lists them (dimmed, never counted).

Untouched by the switches: Insect Collection, Contributed, Examen, Codex, iRecord export,
the Data Entry grid and imports.

Caching: per (database file, source) the {record id: kinds} map is built once (about 0.1 s
for 24,962 observations, 0.2 s for 110,510 scheme rows) and kept until the database changes
(PRAGMA data_version on a private read-only connection: any commit by anyone bumps it).
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Dict, FrozenSet, Iterable, Optional

from shared.record_kinds import KIND_LABELS, KINDS, classify, ranks_for_tvks, species_tvks

SOURCES = ("observations", "recording_scheme")

OFFERED: Dict[str, tuple] = {
    "observations": ("genus", "family_plus", "agg", "sl"),
    "recording_scheme": ("family_plus", "genus", "ss", "sl", "agg", "hybrid", "subsp"),
}
SOURCE_LABELS = {"observations": "Observations", "recording_scheme": "Recording Scheme"}

# Export choice: what an export from a counting screen writes
EXPORT_COUNTED, EXPORT_INCLUDE, EXPORT_ONLY = "counted", "include", "only"
EXPORT_LABELS = {
    EXPORT_COUNTED: "Counted records only",
    EXPORT_INCLUDE: "Include excluded records",
    EXPORT_ONLY: "Only excluded records",
}

_KEY = "species_counting/{source}/{kind}"
_LEGACY_OBS = "display/exclude_incomplete_species"          # before 10 Oct: one switch
_LEGACY_SCHEME = {                                             # before 10 Oct: five chips
    "family_plus": "stats/scheme_exclude_family", "genus": "stats/scheme_exclude_genus",
    "ss": "stats/scheme_exclude_ss", "sl": "stats/scheme_exclude_sl",
    "agg": "stats/scheme_exclude_agg",
}
_TABLES = {"observations": "observations", "recording_scheme": "recording_scheme"}


# ---------------------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------------------

def _settings():
    """Observatum's QSettings. Data Entry run on its own registers as ("Flauna",
    "Observatum"), so it reads Observatum's store by name."""
    from PySide6.QtCore import QCoreApplication, QSettings
    if QCoreApplication.organizationName() == "Flauna":
        return QSettings("Observatum", "Observatum V2")
    return QSettings()


def _legacy_default(s, source: str, kind: str) -> bool:
    if source == "observations":
        return s.value(_LEGACY_OBS, True, type=bool)
    legacy = _LEGACY_SCHEME.get(kind)
    return s.value(legacy, False, type=bool) if legacy else False


def excluded_kinds(source: str) -> FrozenSet[str]:
    """The kinds switched off (left out of counts, maps and lists) for this source."""
    s = _settings()
    out = set()
    for kind in OFFERED[source]:
        key = _KEY.format(source=source, kind=kind)
        on = s.value(key, False, type=bool) if s.contains(key) else _legacy_default(s, source, kind)
        if on:
            out.add(kind)
    return frozenset(out)


def set_excluded(source: str, kinds: Iterable[str]) -> None:
    """Save the switched-off kinds for this source and tell open screens."""
    kinds = set(kinds)
    s = _settings()
    for kind in OFFERED[source]:
        s.setValue(_KEY.format(source=source, kind=kind), kind in kinds)
    s.sync()
    notifier().changed.emit(source)


def kinds_for_search(source: str, text: Optional[str] = None) -> FrozenSet[str]:
    """The switched-off kinds for a view filtered by species text (the Observation Data and
    Recording Scheme tabs): a search that names an aggregate or s.l. keeps those records
    counted -- they were asked for by name (review 10 Oct: navigating to an aggregate showed
    nothing). "Names an aggregate" is the one rule, record_kinds.classify: "agg.", "s.l." /
    "sensu lato", and a slash pair ("Leiopus linnei/nebulosus", decision D4 11 Oct, so
    Species lookup's "View N records" lands on a tab counting the same records); plus the
    looser endings parse_qualifier reads ("Bombus lucorum s.l" without its last dot).
    Only agg./s.l. are released: a genus typed in the box stays left out."""
    kinds = set(excluded_kinds(source))
    text = (text or "").strip()
    if text and kinds & {"agg", "sl"}:
        from shared.species_lookup import parse_qualifier
        if classify(text) & {"agg", "sl"} or parse_qualifier(text)[0] in ("agg.", "s.l."):
            kinds -= {"agg", "sl"}
    return frozenset(kinds)


def kinds_for_taxon(source: str, name: Optional[str], rank: Optional[str] = None) -> FrozenSet[str]:
    """The switched-off kinds for a view of ONE taxon picked from UKSI (Stats > Species
    lookup): the taxon's own kinds are never left out. Picking "Leiopus linnei/nebulosus"
    (rank Species aggregate) shows its aggregate records though the Aggregate switch is on
    (R9-1, 11 Oct: it showed 0 Scheme records). Other switched-off kinds still apply.
    `rank` is the taxon's UKSI rank; the name's own markers (agg., s.l., a slash pair)
    count too, by the one rule in shared/record_kinds.classify."""
    return frozenset(excluded_kinds(source) - classify(name, rank))


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, kind)


_NOTIFIER = None


def notifier():
    """A QObject whose changed(source) signal fires when a source's switches change."""
    global _NOTIFIER
    if _NOTIFIER is None:
        from PySide6.QtCore import QObject, Signal

        class _Notifier(QObject):
            changed = Signal(str)

        _NOTIFIER = _Notifier()
    return _NOTIFIER


# ---------------------------------------------------------------------------------------
# Per-record kinds, cached per (database file, source)
# ---------------------------------------------------------------------------------------

class Snapshot:
    """kinds: {record id: frozenset of kinds} (only records carrying a kind);
    species_of: {tvk: species tvk} for TVKs below species (the subspecies roll-up)."""

    def __init__(self, kinds: Dict[int, FrozenSet[str]], species_of: Dict[str, str]):
        self.kinds = kinds
        self.species_of = species_of
        self._excl: Dict[FrozenSet[str], FrozenSet[int]] = {}

    def excluded_ids(self, kinds: FrozenSet[str]) -> FrozenSet[int]:
        got = self._excl.get(kinds)
        if got is None:
            got = frozenset(i for i, k in self.kinds.items() if k & kinds)
            self._excl[kinds] = got
        return got


_lock = threading.RLock()
_cache: Dict[tuple, tuple] = {}        # (path, source) -> (data_version, Snapshot)
_watch: Dict[str, sqlite3.Connection] = {}
_uksi_path: Optional[str] = None


def set_uksi_path(path) -> None:
    """Point the rank fallback and the subspecies roll-up at another uksi.db (tests)."""
    global _uksi_path
    _uksi_path = str(path) if path else None
    invalidate()


def invalidate() -> None:
    with _lock:
        _cache.clear()


def _db_file(db) -> str:
    """The database file behind `db`: a sqlite3 connection, a DatabaseManager (main_db_path)
    or a path. '' for an in-memory connection."""
    if isinstance(db, sqlite3.Connection):
        try:
            for _seq, name, file in db.execute("PRAGMA database_list"):
                if name == "main":
                    return file or ""
        except sqlite3.Error:
            pass
        return ""
    p = getattr(db, "main_db_path", db)
    return str(p) if p else ""


def _watch_conn(path: str) -> Optional[sqlite3.Connection]:
    c = _watch.get(path)
    if c is None:
        try:
            from shared.db_open import connect_ro
            c = connect_ro(path, check_same_thread=False)
        except sqlite3.Error:
            return None
        _watch[path] = c
    return c


def _data_version(c: sqlite3.Connection) -> Optional[int]:
    try:
        return c.execute("PRAGMA data_version").fetchone()[0]
    except sqlite3.Error:
        return None


def _uksi_conn() -> Optional[sqlite3.Connection]:
    path = _uksi_path
    if path is None:
        try:
            import paths
            path = str(paths.UKSI_DB)
        except Exception:
            from shared.db_config import db_path
            path = str(db_path("uksi.db"))
    try:
        from shared.db_open import connect_ro
        from pathlib import Path
        if not Path(path).exists():
            return None
        return connect_ro(path)
    except sqlite3.Error:
        return None


def _build(db, source: str) -> Snapshot:
    table = _TABLES[source]
    rows = db.execute(f"SELECT id, species_name, taxon_rank, species_tvk FROM {table}").fetchall()
    uksi = _uksi_conn()
    try:
        ranks = ranks_for_tvks(uksi, [r[3] for r in rows if not r[2]]) if uksi else {}
        memo: Dict[tuple, FrozenSet[str]] = {}
        kinds: Dict[int, FrozenSet[str]] = {}
        sub_tvks = set()
        for rid, name, rank, tvk in rows:
            rk = rank or ranks.get(tvk)
            k = memo.get((name, rk))
            if k is None:
                k = memo[(name, rk)] = classify(name, rk)
            if k:
                kinds[rid] = k
                if "subsp" in k and tvk:
                    sub_tvks.add(tvk)
        species_of = {}
        if uksi and sub_tvks:
            species_of = {t: s for t, s in species_tvks(uksi, sub_tvks).items() if s and s != t}
    finally:
        if uksi is not None:
            uksi.close()
    return Snapshot(kinds, species_of)


def snapshot(db, source: str) -> Snapshot:
    """The cached kinds for every record of `source` in db's database (db = a sqlite3
    connection, a DatabaseManager or a path)."""
    path = _db_file(db)
    with _lock:
        watch = _watch_conn(path) if path else None
        dv = _data_version(watch) if watch is not None else None
        if dv is not None:
            hit = _cache.get((path, source))
            if hit and hit[0] == dv:
                return hit[1]
            snap = _build(watch, source)
            _cache[(path, source)] = (dv, snap)
            return snap
        if not isinstance(db, sqlite3.Connection):
            return Snapshot({}, {})
        return _build(db, source)


def excluded_ids(db, source: str,
                 kinds: Optional[Iterable[str]] = None) -> FrozenSet[int]:
    """Ids of the records the switches leave out (or those carrying `kinds`)."""
    ks = frozenset(excluded_kinds(source) if kinds is None else kinds)
    if not ks:
        return frozenset()
    return snapshot(db, source).excluded_ids(ks)


def excluded_reasons(db, source: str, kinds: Optional[Iterable[str]] = None) -> Dict[int, str]:
    """{record id: 'Genus only, ...'} for the excluded records (dimmed rows' tooltips)."""
    ks = frozenset(excluded_kinds(source) if kinds is None else kinds)
    if not ks:
        return {}
    snap = snapshot(db, source)
    out = {}
    for i, kk in snap.kinds.items():
        hit = kk & ks
        if hit:
            out[i] = ", ".join(KIND_LABELS[k] for k in KINDS if k in hit)
    return out


def _id_list(ids) -> str:
    return ",".join(str(int(i)) for i in sorted(ids))


def copies_sql(db, source: str, col: str = "id") -> str:
    """' AND <prefix>duplicate_of IS NULL' for recording_scheme -- the marked NBN copies of
    iRecord records are never counted (shared/scheme_duplicates.py, Q59); for observations
    ' AND <prefix>hidden_at IS NULL' -- records removed here but still in iRecord are never
    counted (shared/hidden_records.py, F72) -- else ''."""
    if source == "recording_scheme":
        from shared.scheme_duplicates import live_sql, prefix_of
        return live_sql(db, prefix_of(col))
    if source == "observations":
        from shared.hidden_records import live_sql
        from shared.scheme_duplicates import prefix_of
        return live_sql(db, prefix_of(col))
    return ""


def _not_excluded(db, source, col, kinds) -> str:
    ids = excluded_ids(db, source, kinds)
    return f" AND {col} NOT IN ({_id_list(ids)})" if ids else ""


def _only_excluded(db, source, col, kinds) -> str:
    ids = excluded_ids(db, source, kinds)
    return f" AND {col} IN ({_id_list(ids)})" if ids else " AND 0"


def not_excluded_sql(db, source: str, col: str = "id",
                     kinds: Optional[Iterable[str]] = None) -> str:
    """' AND <col> NOT IN (...)' leaving out the excluded records (and, for the scheme, the
    marked copies), or '' when there are none."""
    return _not_excluded(db, source, col, kinds) + copies_sql(db, source, col)


def only_excluded_sql(db, source: str, col: str = "id",
                      kinds: Optional[Iterable[str]] = None,
                      include_copies: bool = False) -> str:
    """' AND <col> IN (...)' keeping only the excluded records (' AND 0' when none are);
    the scheme's marked copies stay out unless include_copies."""
    return _only_excluded(db, source, col, kinds) + (
        "" if include_copies else copies_sql(db, source, col))


def export_sql(db, source: str, mode: str, col: str = "id",
               include_copies: bool = False) -> str:
    """The SQL fragment for an export choice (EXPORT_COUNTED / _INCLUDE / _ONLY). The
    scheme's marked copies are left out unless include_copies (the Scheme tab with
    "Show duplicates" on)."""
    if mode == EXPORT_INCLUDE:
        out = ""
    elif mode == EXPORT_ONLY:
        out = _only_excluded(db, source, col, None)
    else:
        out = _not_excluded(db, source, col, None)
    return out + ("" if include_copies else copies_sql(db, source, col))


def species_key_sql(db, source: str, tvk_col: str = "species_tvk") -> str:
    """A SQL expression giving each record's species TVK with subspecies rolled up:
    use it in place of species_tvk in COUNT(DISTINCT ...). Plain tvk_col when nothing rolls up."""
    m = snapshot(db, source).species_of
    if not m:
        return tvk_col
    whens = " ".join(f"WHEN '{t}' THEN '{s}'" for t, s in sorted(m.items())
                     if "'" not in t and "'" not in s)
    return f"(CASE {tvk_col} {whens} ELSE {tvk_col} END)"


def install_counted_view(conn: sqlite3.Connection, source: str) -> None:
    """On a READ-ONLY connection: a TEMP VIEW with the table's own name holding only the
    records the switches count, species_tvk with subspecies rolled up (observations).
    Unqualified queries on that connection then follow the switches unchanged (used by the
    achievements calculator). Never on a connection that writes: an INSERT would hit the view."""
    table = _TABLES[source]
    cols = [r[1] for r in conn.execute(f"PRAGMA main.table_info({table})")]
    if not cols:
        return
    sk = species_key_sql(conn, source, "species_tvk") if source == "observations" else "species_tvk"
    sel = ", ".join(f"{sk} AS species_tvk" if c == "species_tvk" else f'"{c}"' for c in cols)
    conn.execute(f"DROP VIEW IF EXISTS temp.{table}")
    conn.execute(f"CREATE TEMP VIEW {table} AS SELECT {sel} FROM main.{table} "
                 f"WHERE 1{not_excluded_sql(conn, source, 'id')}")


def species_key_map(db, source: str) -> Dict[str, str]:
    """{tvk: species tvk} for the TVKs that roll up (others are their own key): look keys
    up with .get(tvk, tvk) in a loop instead of calling species_key per record."""
    return snapshot(db, source).species_of


def species_key(db, source: str, tvk: Optional[str]) -> Optional[str]:
    """One record's species TVK with the subspecies roll-up (Python side)."""
    if not tvk:
        return tvk
    return snapshot(db, source).species_of.get(tvk, tvk)


def is_excluded(db, source: str, record_id) -> bool:
    return record_id in excluded_ids(db, source)


# ---------------------------------------------------------------------------------------
# The app's own database (Observatum sets it when it opens its database)
# ---------------------------------------------------------------------------------------

_default_db: Optional[str] = None


def set_default_db(path) -> None:
    global _default_db
    _default_db = str(path) if path else None


def default_db() -> str:
    if _default_db:
        from pathlib import Path
        if Path(_default_db).exists():
            return _default_db
    import paths
    return str(paths.OBSERVATUM_DB)


def counted_clause(source: str, prefix: str = "", db=None) -> str:
    """' AND <prefix>id NOT IN (...)' for the app's database: append to a WHERE clause."""
    return not_excluded_sql(db or default_db(), source, f"{prefix}id")


def counted_clause_for(source: str, text: Optional[str], prefix: str = "", db=None) -> str:
    """counted_clause for a view filtered by species text (see kinds_for_search)."""
    return not_excluded_sql(db or default_db(), source, f"{prefix}id", kinds_for_search(source, text))


def counted_clause_for_taxon(source: str, name: Optional[str], rank: Optional[str] = None,
                             prefix: str = "", db=None) -> str:
    """counted_clause for a view of one taxon picked from UKSI (see kinds_for_taxon)."""
    return not_excluded_sql(db or default_db(), source, f"{prefix}id",
                            kinds_for_taxon(source, name, rank))


def species_key_expr(source: str, prefix: str = "", db=None) -> str:
    """species_tvk with the subspecies roll-up, for COUNT(DISTINCT ...) in the app's database."""
    return species_key_sql(db or default_db(), source, f"{prefix}species_tvk")
