"""
Pantheon Repository — Data Access Layer

Provides query methods for pantheon.db. Read-only access to
conservation status, habitat traits, SQS scores, SATs, fidelity
scores, and associations for species matched by TVK.

Usage:
    repo = PantheonRepository()
    scores = repo.get_sqs_scores(['NBNSYS0000007302', ...])
    status = repo.get_conservation_status('NBNSYS0000007302')

The bridge (one rule, used everywhere -- fix round 9 Oct 2026, INF1/EXA6/EXA7)
-----------------------------------------------------------------------------
pantheon.db is keyed on 2017 TVKs; callers hold current UKSI TVKs. codex.db's
tvk_bridge maps every Pantheon taxon to the current species it belongs to, and
several Pantheon taxa can land on one species (a sunk segregate, a misspelt
NOTVK: twin). For a current species, EVERY bridge row is a candidate:

  * ecology (biotopes, habitats, SATs, guilds, associations) is UNIONED;
  * single values (SQS, GB status, names) are taken in the J2 order: the
    INCUMBENT first -- the Pantheon taxon whose TVK is the species' own, else
    whose exact name is the species' current name -- then the rest in bridge
    order. A value from a later candidate is used only where every earlier one
    has none, so a collider's score never displaces the incumbent's;
  * a NOTVK: row (a taxon Pantheon published without a TVK) goes after every
    taxon with a TVK in its class, so an empty twin never shadows a populated
    taxon.

CodexRepository's Pantheon Only mode and the Species Database read through
this module, so the rule exists once. scripts/build_codex_db.py applies the
same rule when it stores Codex's SQS (it cannot import this module at build
time; keep the two in step).
"""

import os
import sqlite3
import paths
from pathlib import Path
from dataclasses import dataclass, field
from shared.db_open import connect_ro  # D9: reference data, read-only


DB_PATH = paths.PANTHEON_DB

# Key prefix for species Pantheon published without a TVK (build_pantheon_db.py).
NOTVK_PREFIX = "NOTVK:"

# Pantheon status categories that hold one value per taxon; the rest (Section 41,
# Legal Protection) are lists and are unioned across bridged taxa.
SINGLE_VALUED_CATEGORIES = ("GB Status", "GB Red List")


@dataclass
class SpeciesProfile:
    """Complete Pantheon profile for a single species."""
    tvk: str
    species_name: str
    family: str = ""
    sqs: int = 0
    gb_status: str = ""
    gb_red_list: str = ""
    section41: bool = False
    legal_protection: bool = False
    broad_biotopes: list = field(default_factory=list)
    habitats: list = field(default_factory=list)
    larval_guild: str = ""
    adult_guild: str = ""
    sats: list = field(default_factory=list)
    fidelity_scores: dict = field(default_factory=dict)
    associations: list = field(default_factory=list)
    # The Pantheon taxa combined into this profile, incumbent first.
    pantheon_tvks: list = field(default_factory=list)


# ================================================================
# The bridge -- one loader, one ordering rule
# ================================================================

def j2_order(uksi_tvk, uksi_name, rows):
    """Pantheon TVKs for one current species, in the J2 order.

    rows: [(pantheon_tvk, pantheon_name), ...] in bridge (build) order.
    Incumbent(s) first: the taxon whose TVK is the species' own, else whose
    exact name is its current name. Then the rest, in bridge order. Within each
    group a NOTVK: row goes after every taxon that has a TVK.
    """
    name = (uksi_name or "").strip().lower()
    inc = [p for p, _ in rows if p == uksi_tvk]
    if not inc and name:
        inc = [p for p, n in rows if (n or "").strip().lower() == name]
    rest = [p for p, _ in rows if p not in inc]

    def notvk_last(group):
        return sorted(group, key=lambda p: p.startswith(NOTVK_PREFIX))   # stable

    return notvk_last(inc) + notvk_last(rest)


def j2_first(candidates, values, accept=bool):
    """The first candidate's value that `accept` allows, in J2 order, or None."""
    for c in candidates:
        v = values.get(c)
        if v is not None and accept(v):
            return v
    return None


@dataclass
class Bridge:
    to_pan: dict = field(default_factory=dict)     # {uksi_tvk: [pantheon_tvk, ...] J2 order}
    to_uksi: dict = field(default_factory=dict)    # {pantheon_tvk: uksi_tvk}

    def candidates(self, uksi_tvk):
        """Pantheon TVKs to query for a current TVK. A TVK not in the bridge is
        passed through unchanged, so a caller holding a Pantheon TVK still works."""
        return self.to_pan.get(uksi_tvk) or [uksi_tvk]


_BRIDGE_CACHE = {}


def _mtime(p):
    try:
        return os.path.getmtime(str(p))
    except OSError:
        return None


def load_bridge(codex_path=None, uksi_path=None):
    """The bridge from codex.db, J2-ordered. Cached per file version.

    Empty (every TVK passed through) if codex.db cannot be read. UKSI is read
    only for the current names of species several Pantheon taxa land on.
    """
    codex_path = str(codex_path or paths.CODEX_DB)
    uksi_path = str(uksi_path or paths.UKSI_DB)
    key = (codex_path, _mtime(codex_path), uksi_path, _mtime(uksi_path))
    if key in _BRIDGE_CACHE:
        return _BRIDGE_CACHE[key]
    bridge = Bridge()
    if not Path(codex_path).exists():
        return bridge
    try:
        cx = connect_ro(codex_path)
        try:
            rows = cx.execute("SELECT pantheon_tvk, uksi_tvk, species_name "
                              "FROM tvk_bridge ORDER BY rowid").fetchall()
        finally:
            cx.close()
    except sqlite3.Error as e:
        print(f"[pantheon_repository] bridge unavailable: {e}")
        return bridge

    groups = {}
    for pan_tvk, uksi_tvk, name in rows:
        groups.setdefault(uksi_tvk, []).append((pan_tvk, name))
        bridge.to_uksi[pan_tvk] = uksi_tvk

    # Current names, only where they decide the incumbent.
    need = [u for u, m in groups.items() if len(m) > 1 and not any(p == u for p, _ in m)]
    names = {}
    if need and Path(uksi_path).exists():
        try:
            ux = connect_ro(uksi_path)
            try:
                for batch in _chunked(need, 500):
                    ph = ",".join("?" * len(batch))
                    names.update(ux.execute(
                        f"SELECT tvk, scientific_name FROM taxa WHERE tvk IN ({ph})", batch))
            finally:
                ux.close()
        except sqlite3.Error as e:
            print(f"[pantheon_repository] UKSI names unavailable: {e}")

    for uksi_tvk, members in groups.items():
        bridge.to_pan[uksi_tvk] = (j2_order(uksi_tvk, names.get(uksi_tvk), members)
                                   if len(members) > 1 else [members[0][0]])

    # Species and broad group (Wil's rule, 9 Oct 2026): a species with no Pantheon
    # taxon of its own takes its sensu lato / aggregate counterpart's. Pantheon's
    # 2017 concept was usually the broad one (Nomada panzeri before the N. glabella
    # split), so records moved onto the species keep their ecology and SQS --
    # the same fallback CodexRepository applies to conservation status.
    try:
        from shared.repositories.codex_repository import uksi_sensu_lato_map
        sl_map = uksi_sensu_lato_map(uksi_path) if Path(uksi_path).exists() else {}
    except Exception as e:                       # never let the fallback break the bridge
        print(f"[pantheon_repository] sensu lato fallback unavailable: {e}")
        sl_map = {}
    for sp_tvk, (sl_tvk, _label) in sl_map.items():
        if sp_tvk not in bridge.to_pan and sl_tvk in bridge.to_pan:
            bridge.to_pan[sp_tvk] = list(bridge.to_pan[sl_tvk])
    _BRIDGE_CACHE.clear()
    _BRIDGE_CACHE[key] = bridge
    return bridge


class PantheonRepository:
    """Read-only access to pantheon.db."""

    def __init__(self, db_path: str = None, use_bridge: bool = True,
                 codex_path: str = None, uksi_path: str = None):
        self._db_path = str(db_path or DB_PATH)
        self._conn = None
        # pantheon.db is keyed on 2017 TVKs; callers hold current UKSI TVKs.
        # Without translation, every species re-keyed by name or synonym
        # returns no ecology at all -- 3,666 of them. See
        # patch_pantheon_bridge.py.
        self._use_bridge = use_bridge
        self._codex_path = codex_path
        self._uksi_path = uksi_path
        self._bridge = None

    def _get_conn(self):
        if self._conn is None:
            if not Path(self._db_path).exists():
                raise FileNotFoundError(f"pantheon.db not found: {self._db_path}")
            self._conn = connect_ro(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ================================================================
    # TVK bridge -- UKSI (current) <-> Pantheon (2017)
    # ================================================================

    def bridge(self):
        if self._bridge is None:
            self._bridge = (load_bridge(self._codex_path, self._uksi_path)
                            if self._use_bridge else Bridge())
        return self._bridge

    def candidates(self, tvk):
        """Pantheon TVKs for one current TVK, J2 order (see module docstring)."""
        return self.bridge().candidates(tvk)

    def _expand(self, tvks):
        """(pantheon TVKs to query, {pantheon_tvk: [caller's TVKs]})."""
        rev = {}
        for t in dict.fromkeys(tvks):
            for p in self.candidates(t):
                rev.setdefault(p, []).append(t)
        return list(rev), rev

    def _by_pan(self, sql_cols, table, pan_tvks, extra="", params=()):
        """{pantheon_tvk: [row, ...]} for a batch query, rows in table order."""
        out = {}
        if not pan_tvks:
            return out
        c = self._get_conn().cursor()
        for batch in _chunked(pan_tvks, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"SELECT tvk, {sql_cols} FROM {table} WHERE tvk IN ({ph}){extra}",
                      list(batch) + list(params))
            for r in c.fetchall():
                out.setdefault(r[0], []).append(r)
        return out

    # ================================================================
    # Single species lookups
    # ================================================================

    def get_species_profile(self, tvk: str) -> SpeciesProfile:
        """Complete Pantheon profile for a species, every bridged taxon combined.

        `tvk` may be a current UKSI TVK. Every Pantheon taxon bridged to it is
        read: lists are unioned; single values (SQS, GB status, Red List, guilds,
        names) come from the incumbent, else the next candidate that has one.
        An empty NOTVK: twin no longer stands in for the species (EXA7).
        """
        cands = self.candidates(tvk)
        rows = self._by_pan("species_name, family", "species", cands)
        present = [p for p in cands if p in rows]
        if not present:
            return None
        named = [p for p in present if not p.startswith(NOTVK_PREFIX)] or present
        first = rows[named[0]][0]
        profile = SpeciesProfile(tvk=tvk, species_name=first["species_name"],
                                 family=first["family"] or "", pantheon_tvks=present)
        profile.family = profile.family or next(
            (rows[p][0]["family"] for p in present if rows[p][0]["family"]), "")

        profile.sqs = self.get_sqs_scores([tvk]).get(tvk, 0)

        status_rows = self.get_conservation_rows([tvk]).get(tvk, [])
        for cat, abbr in status_rows:
            if cat == "GB Status" and not profile.gb_status:
                profile.gb_status = abbr
            elif cat == "GB Red List" and not profile.gb_red_list:
                profile.gb_red_list = abbr
            elif cat == "Section 41 Priority Species":
                profile.section41 = True
            elif cat == "Legal Protection":
                profile.legal_protection = True

        profile.broad_biotopes = self.get_broad_biotopes([tvk]).get(tvk, [])
        profile.habitats = self.get_habitats([tvk]).get(tvk, [])
        guilds = self.get_feeding_guilds([tvk]).get(tvk, {})
        profile.larval_guild = guilds.get("larval guild") or ""
        profile.adult_guild = guilds.get("adult guild") or ""
        profile.sats = self.get_sats([tvk]).get(tvk, [])
        profile.fidelity_scores = self.get_fidelity_scores([tvk]).get(tvk, {})

        assoc = self._by_pan("associated_taxa_type, associated_taxa", "associations", cands)
        seen = []
        for p in cands:
            for r in assoc.get(p, []):
                pair = (r["associated_taxa_type"], r["associated_taxa"])
                if pair not in seen:
                    seen.append(pair)
        profile.associations = seen
        return profile

    # ================================================================
    # Batch lookups (for analysis service)
    # ================================================================

    def get_sqs_scores(self, tvks: list) -> dict:
        """SQS per TVK: {tvk: sqs}, J2 rule.

        The incumbent's published score; a collider's only where the incumbent
        has none. A score of 0 ("known, not scored") is not a score, as in the
        Codex build. NOT the highest: a sunk scarce segregate carries a higher
        score than the common species it was merged into (Sympetrum striolatum).
        """
        if not tvks:
            return {}
        pan, rev = self._expand(tvks)
        raw = {p: rows[0][1] for p, rows in self._by_pan("sqs", "sqs_scores", pan).items()}
        result = {}
        for t in dict.fromkeys(tvks):
            v = j2_first(self.candidates(t), raw, accept=lambda s: (s or 0) > 0)
            if v is not None:
                result[t] = v
        return result

    def held_by_pantheon(self, tvks: list) -> set:
        """TVKs Pantheon analysed: any ecology or SQS row, through the bridge.

        THE definition of "analysed by Pantheon" (EXA5): a broad biotope,
        habitat, SAT, feeding guild or SQS row (a score of 0 included) on any
        Pantheon taxon bridged to the species.
        """
        if not tvks:
            return set()
        pan, rev = self._expand(tvks)
        held = set()
        for table in ("sqs_scores", "broad_biotope", "habitats",
                      "specific_assemblage_types", "feeding_guilds"):
            for p in self._by_pan("1", table, pan):
                held.update(rev.get(p, []))
        return held

    def get_broad_biotopes(self, tvks: list) -> dict:
        """Get broad biotopes for TVKs. Returns {tvk: [biotope, ...]}."""
        return self._get_multi(tvks, "broad_biotope", "biotope")

    def get_habitats(self, tvks: list) -> dict:
        """Get habitats for TVKs. Returns {tvk: [habitat, ...]}."""
        return self._get_multi(tvks, "habitats", "habitat")

    def get_sats(self, tvks: list) -> dict:
        """Get SATs for TVKs. Returns {tvk: [sat_name, ...]}."""
        return self._get_multi(tvks, "specific_assemblage_types", "sat_name")

    def get_conservation_rows(self, tvks: list) -> dict:
        """{tvk: [(reporting_category, abbreviation), ...]}, J2 order -- the
        incumbent's rows first, so a caller taking the first value of a
        single-valued category takes the incumbent's."""
        if not tvks:
            return {}
        pan, rev = self._expand(tvks)
        raw = self._by_pan("reporting_category, abbreviation", "conservation_status", pan)
        out = {}
        for t in dict.fromkeys(tvks):
            rows, taken = [], set()
            for p in self.candidates(t):
                cats = set()
                for r in raw.get(p, []):
                    cat, pair = r[1], (r[1], r[2])
                    # A single-valued category (GB Status, GB Red List) comes from
                    # the first candidate that has one -- J2, as for the SQS -- so a
                    # sunk segregate's NR never lands on the common species.
                    if cat in SINGLE_VALUED_CATEGORIES and cat in taken:
                        continue
                    cats.add(cat)
                    if pair not in rows:
                        rows.append(pair)
                taken |= cats
            if rows:
                out[t] = rows
        return out

    def get_conservation_statuses(self, tvks: list) -> dict:
        """Get GB Status for TVKs. Returns {tvk: abbreviation}, J2 order."""
        out = {}
        for t, rows in self.get_conservation_rows(tvks).items():
            for cat, abbr in rows:
                if cat == "GB Status" and abbr not in ("None", "Unknown", "Not reviewed"):
                    out[t] = abbr
                    break
        return out

    def get_feeding_guilds(self, tvks: list) -> dict:
        """Get feeding guilds. Returns {tvk: {life_stage: guild}}, J2 order per stage."""
        if not tvks:
            return {}
        pan, rev = self._expand(tvks)
        raw = self._by_pan("life_stage, guild", "feeding_guilds", pan)
        result = {}
        for t in dict.fromkeys(tvks):
            for p in self.candidates(t):
                for r in raw.get(p, []):
                    cur = result.setdefault(t, {})
                    if r[1] not in cur or (r[2] and not cur[r[1]]):
                        cur[r[1]] = r[2]
        return result

    def get_fidelity_scores(self, tvks: list, index_name: str = None) -> dict:
        """Get fidelity scores. Returns {tvk: {index: score}}, J2 order per index."""
        if not tvks:
            return {}
        pan, rev = self._expand(tvks)
        if index_name:
            raw = self._by_pan("index_name, score", "fidelity_scores", pan,
                               " AND index_name = ?", (index_name,))
        else:
            raw = self._by_pan("index_name, score", "fidelity_scores", pan)
        result = {}
        for t in dict.fromkeys(tvks):
            for p in self.candidates(t):
                for r in raw.get(p, []):
                    result.setdefault(t, {}).setdefault(r[1], r[2])
        return result

    def national_pool_counts(self) -> dict:
        """National species pool per biotope / habitat / SAT, for "% national pool".

        Definition (EXA13): the number of distinct current UKSI species bridged to
        Pantheon taxa coded for that biotope, habitat or SAT -- each species once,
        however many Pantheon taxa were merged into it. Pantheon taxa the bridge
        does not reach (no current species) are not counted.
        Returns {"biotope": {name: n}, "habitat": {...}, "sat": {...}}.
        """
        to_uksi = self.bridge().to_uksi
        out = {"biotope": {}, "habitat": {}, "sat": {}}
        c = self._get_conn().cursor()
        for key, (table, col) in {"biotope": ("broad_biotope", "biotope"),
                                  "habitat": ("habitats", "habitat"),
                                  "sat": ("specific_assemblage_types", "sat_name")}.items():
            species = {}
            for pan_tvk, value in c.execute(f"SELECT DISTINCT tvk, {col} FROM {table}"):
                uksi = to_uksi.get(pan_tvk)
                if value and uksi:
                    species.setdefault(value, set()).add(uksi)
            out[key] = {v: len(s) for v, s in species.items()}
        return out

    def get_metadata(self) -> dict:
        """Get database metadata."""
        c = self._get_conn().cursor()
        c.execute("SELECT key, value FROM metadata")
        return {r["key"]: r["value"] for r in c.fetchall()}

    def get_species_count(self) -> int:
        c = self._get_conn().cursor()
        c.execute("SELECT COUNT(*) FROM species")
        return c.fetchone()[0]

    # ================================================================
    # Private helpers
    # ================================================================

    def _get_multi(self, tvks, table, column):
        """Batch multi-value lookup, keyed back to the caller's TVKs.

        Values are unioned where several Pantheon taxa map to one current
        species, de-duplicated, incumbent's first.
        """
        if not tvks:
            return {}
        pan, rev = self._expand(tvks)
        raw = self._by_pan(column, table, pan)
        result = {}
        for t in dict.fromkeys(tvks):
            for p in self.candidates(t):
                for r in raw.get(p, []):
                    vals = result.setdefault(t, [])
                    if r[1] not in vals:
                        vals.append(r[1])
        return result


def _chunked(lst, n):
    """Yield successive n-sized chunks from lst."""
    lst = list(lst)
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
