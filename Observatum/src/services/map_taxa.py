"""Taxa for the Mapping tab: which records sit under a chosen taxon, and the rank picker's
search (backlog item 4, review SRCH18; 10 Oct 2026). Read-only; no Qt.

Everything goes through the suite's one species index (shared/species_search.py) and its
TVK rules (shared/species_filter.py):
  * a record is under a taxon when the taxon is its TVK or an ancestor of it (Rhagium ->
    R. mordax, Cerambycidae -> every longhorn);
  * a record stored under an old TVK counts as its current taxon (UKSI name_map / tvk_remap);
  * a record with no TVK, or one UKSI can't place, is placed by its species_name (its
    scientific or old name) -- or, if UKSI doesn't hold the name either, left out of taxon
    selections (it still shows on an unselected "all records" map).
"""
from __future__ import annotations

import os
import sqlite3
from typing import Dict, Iterable, List, Optional, Set, Tuple

import paths
from shared.db_open import connect_ro
from shared.species_filter import current_tvk_map, tvks_under
from shared.species_search import SPECIES_LEVEL, get_index

# The rank picker: what each choice searches for (UKSI ranks).
RANKS: Dict[str, Optional[frozenset]] = {
    "species": SPECIES_LEVEL,
    "genus": frozenset({"Genus", "Subgenus", "Genus aggregate", "Section", "Series"}),
    "family": frozenset({"Family", "Subfamily", "Superfamily", "Tribe", "Subtribe", "Epifamily"}),
    "order": frozenset({"Order", "Suborder", "Infraorder", "Parvorder", "Superorder"}),
    "group": None,                       # taxon groups (shared/taxon_groups.py), not UKSI ranks
}
RANK_LABELS = {"species": "Species", "genus": "Genus", "family": "Family", "order": "Order",
               "group": "Taxon group"}
# A record's "species" for richness: the nearest of these at or above its taxon
# (a subspecies counts as its species; a record named only to genus counts as none).
_MAIN_SPECIES = frozenset({"Species", "Species aggregate", "Species sensu lato",
                           "Species pro parte", "Microspecies", "Species group"})

# A family or order chip also takes the records whose taxon UKSI holds with nothing above it
# (non-British species such as Morimus funereus, 2 scheme records): by the record's own
# family / order_name column.
STORED_COLUMN = {"Family": "family", "Order": "order_name"}

# The tables the Mapping tab reads, and the column holding each one's taxon group.
GROUP_COLUMN = {"observations": "taxon_group", "specimens": "taxon_group",
                "recording_scheme": "taxon_group", "contributed_observations": None}


class TaxonContext:
    """The record TVKs and names of each table, placed in UKSI once (rebuilt when either
    database file changes). get_context() returns the shared one."""

    def __init__(self, db_path, uksi_path=None):
        self.db_path = str(db_path)
        self.uksi_path = str(uksi_path) if uksi_path else None
        self.idx = get_index(self.uksi_path)
        self.present: Dict[str, Set[str]] = {}            # table -> distinct TVKs
        self.loose_names: Dict[str, Set[str]] = {}        # table -> names of rows with no TVK
        self.known_groups: Dict[str, List[str]] = {}      # table -> stored taxon_group values
        self._counts: Dict[Tuple[str, str], int] = {}     # (tvk, name) -> records, all tables
        conn = connect_ro(self.db_path)
        try:
            for table, gcol in GROUP_COLUMN.items():
                try:
                    rows = conn.execute(
                        f"SELECT species_tvk, species_name, COUNT(*) FROM {table} "
                        f"GROUP BY species_tvk, species_name").fetchall()
                except sqlite3.OperationalError:
                    continue
                self.present[table] = {t for t, _n, _c in rows if t}
                self.loose_names[table] = {n for t, n, _c in rows if not t and n}
                for t, n, c in rows:
                    key = (t or "", "" if t else (n or ""))
                    self._counts[key] = self._counts.get(key, 0) + c
                self.known_groups[table] = [r[0] for r in conn.execute(
                    f"SELECT DISTINCT {gcol} FROM {table} WHERE COALESCE({gcol}, '') <> ''")
                ] if gcol else []
        finally:
            conn.close()
        self._current = current_tvk_map(set().union(*self.present.values()) if self.present
                                        else set(), self.uksi_path)
        self._unknown = {t for t, c in self._current.items() if c is None}
        self._anc: Dict[Tuple[str, str], tuple] = {}
        self._species: Dict[Tuple[str, str], Optional[str]] = {}
        self._by_taxon: Optional[Dict[str, int]] = None

    # ------------------------------------------------------------ one record
    def current(self, tvk: Optional[str], name: Optional[str]) -> Optional[str]:
        """The current UKSI TVK a record stands for: its TVK, else its name, else None."""
        c = self._current.get(tvk) if tvk else None
        if c is None and name:
            c = self.idx.tvk_for_name(name)
        return c

    def ancestors(self, tvk: Optional[str], name: Optional[str]) -> tuple:
        """The record's current taxon and everything above it (empty if it can't be placed)."""
        key = (tvk or "", "" if tvk in self._current and self._current[tvk] else (name or ""))
        hit = self._anc.get(key)
        if hit is None:
            c = self.current(tvk, name)
            hit = tuple(self.idx.ancestors(c)) if c else ()
            self._anc[key] = hit
        return hit

    def species_key(self, tvk: Optional[str], name: Optional[str]) -> Optional[str]:
        """What a record counts as for species richness: its species' TVK; None for a record
        named only above species; 'name:<name>' for a name UKSI doesn't hold."""
        key = (tvk or "", name or "")
        if key in self._species:
            return self._species[key]
        anc = self.ancestors(tvk, name)
        out = None
        if not anc:
            out = f"name:{(name or tvk or '').strip().lower()}" if (name or tvk) else None
        for a in anc:
            if self.idx.rank[self.idx.pos[a]] in _MAIN_SPECIES:
                out = a
                break
        self._species[key] = out
        return out

    # ------------------------------------------------------------ a whole table
    def under(self, table: str, wanted: Iterable[str]) -> Tuple[Set[str], Set[str], Set[str]]:
        """(the table's TVKs under any wanted taxon, its TVKs UKSI can't place, the names of
        its no-TVK / unplaceable rows that are under a wanted taxon)."""
        wanted = set(wanted)
        chosen, unknown = tvks_under(wanted, self.present.get(table, ()), self.uksi_path)
        names = {n for n in self._names_without_tvk(table, unknown)
                 if wanted & set(self.ancestors(None, n))}
        return chosen, unknown, names

    def orphans(self, table: str) -> Set[str]:
        """The table's TVKs that UKSI holds with no taxon above them (no parent_tvk)."""
        return {t for t in self.present.get(table, ()) if len(self.ancestors(t, None)) == 1}

    def _names_without_tvk(self, table: str, unknown: Set[str]) -> Set[str]:
        names = set(self.loose_names.get(table, ()))
        if unknown:
            conn = connect_ro(self.db_path)
            try:
                ph = ",".join("?" * len(unknown))
                names |= {r[0] for r in conn.execute(
                    f"SELECT DISTINCT species_name FROM {table} WHERE species_tvk IN ({ph})",
                    sorted(unknown)) if r[0]}
            finally:
                conn.close()
        return names

    # ------------------------------------------------------------ search counts
    def records_by_taxon(self) -> Dict[str, int]:
        """{UKSI TVK: records at or below it, all tables} -- the counts the picker shows."""
        if self._by_taxon is None:
            out: Dict[str, int] = {}
            for (tvk, name), n in self._counts.items():
                for a in self.ancestors(tvk or None, name or None):
                    out[a] = out.get(a, 0) + n
            self._by_taxon = out
        return self._by_taxon


_contexts: Dict[tuple, TaxonContext] = {}


def _stamp(path) -> int:
    try:
        st = os.stat(path)
        wal = str(path) + "-wal"
        return st.st_mtime_ns + (os.stat(wal).st_mtime_ns if os.path.exists(wal) else 0)
    except OSError:
        return 0


def get_context(db_path=None, uksi_path=None) -> TaxonContext:
    """The TaxonContext for these databases (rebuilt when either file changes)."""
    db = str(db_path or paths.OBSERVATUM_DB)
    uk = str(uksi_path or paths.UKSI_DB)
    stamp = (_stamp(db), _stamp(uk))
    hit = _contexts.get((db, uk))
    if hit and hit[0] == stamp:
        return hit[1]
    ctx = TaxonContext(db, uk)
    _contexts[(db, uk)] = (stamp, ctx)
    return ctx


def search_taxa(text: str, rank: str = "species", limit: int = 8, db_path=None,
                uksi_path=None) -> List[dict]:
    """Recorded taxa of the chosen rank matching the text (shared fuzzy search: every word,
    typing slips, old names and common names -- an old name finds the current taxon).
    [{kind, tvk, scientific_name, common_name, rank, records, old_name}], best first;
    `records` counts every source."""
    if rank == "group":
        return search_groups(text, db_path=db_path, uksi_path=uksi_path)[:limit]
    ctx = get_context(db_path, uksi_path)
    counts = ctx.records_by_taxon()
    out = []
    for r in ctx.idx.search(text, limit=None, ranks=RANKS.get(rank)):
        n = counts.get(r["tvk"], 0)
        if n:
            out.append({"kind": "taxon", "tvk": r["tvk"], "scientific_name": r["label"],
                        "common_name": r["common_name"] or "", "rank": r["rank"],
                        "records": n, "old_name": r["old_name"]})
            if len(out) >= limit:
                break
    return out


def group_counts(db_path=None) -> Dict[str, int]:
    """{taxon-group display label: records, all tables} (shared/taxon_groups.py)."""
    from shared.taxon_groups import group_label, group_sql
    out: Dict[str, int] = {}
    conn = connect_ro(db_path or paths.OBSERVATUM_DB)
    try:
        for table, gcol in GROUP_COLUMN.items():
            expr = group_sql(group_col=gcol or "NULL", order_col="order_name", family_col="family")
            try:
                rows = conn.execute(f"SELECT {expr}, COUNT(*) FROM {table} GROUP BY 1").fetchall()
            except sqlite3.OperationalError:
                continue
            for g, n in rows:
                lab = group_label(g)
                if lab:
                    out[lab] = out.get(lab, 0) + n
    finally:
        conn.close()
    return out


def search_groups(text: str, db_path=None, uksi_path=None) -> List[dict]:
    """Taxon groups present in the records whose label contains every typed word."""
    from shared.taxon_groups import display_labels
    counts = group_counts(db_path)
    order = {lab: i for i, lab in enumerate(display_labels())}
    words = (text or "").lower().split()
    labels = sorted(counts, key=lambda lab: (order.get(lab, len(order)), lab))
    return [{"kind": "group", "label": lab, "scientific_name": lab, "common_name": "",
             "rank": "Taxon group", "records": counts[lab], "tvk": None, "old_name": None}
            for lab in labels if all(w in lab.lower() for w in words)]
