"""
Codex Repository -- Data Access Layer for codex.db (v5)

The canonical read access layer for codex.db. Every Codex consumer
(Observatum, Tabella, Examen's analysis service, web Examen) reads
through this module.

Aligned with Codex Strategy doc (16 April 2026) and codex.db v5 schema:
the 11-track status scheme across 5 conceptual categories.

Tracks exposed via SpeciesStatus:
    Threat:     threat_iucn_2001, threat_iucn_legacy, threat_global_iucn
    Rarity:     rarity_modern, rarity_legacy
    Specialist: bocc, specialist_panel
    Legal:      legal_protection          (list of {value, detail})
    Priority:   priority                  (list of jurisdictions)
    Regional:   red_list_england, red_list_wales
    Plus:       sqs, profile, tier, is_key

Analysis modes:
    CODEX_FULL      -- Use current Codex data (default)
    PANTHEON_ONLY   -- Fall back to Pantheon's 2017 conservation data
                       (for reproducing what the Pantheon website would show,
                        used by Examen's mode-comparison feature)

Key species determination is INVERTEBRATE-ONLY, matching the design
principle that SQS-related concepts apply only to invertebrates.
A bird classified as CR does not get is_key=True via this repository.
"Invertebrate" is UKSI's taxonomy (kingdom Animalia outside phylum Chordata) --
the rule build_codex_db.py uses -- plus anything JNCC's designations call an
invertebrate (CDX-1, 9 Oct 2026). It used to be the designations alone, so a
species whose only status came from a review could never be Key.

Species and broad group (9 Oct 2026). A species (UKSI rank Species) with no
status of its own takes the status held by its sensu-lato / aggregate
counterpart -- same binomial, rank 'Species sensu lato' or 'Species aggregate'.
The status is marked (SpeciesStatus.status_held_at) and display_status says
"status held at sensu lato", so a report never presents it as the species' own.
"""

import os
import re
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import paths
from shared.db_open import connect_ro  # D9: reference data, read-only
from shared.repositories.pantheon_repository import PantheonRepository


DB_PATH = paths.CODEX_DB
PANTHEON_PATH = paths.PANTHEON_DB
UKSI_PATH = paths.UKSI_DB

# The invertebrate rule. scripts/build_codex_db.py applies the same SQL when it
# imports SQS (it cannot import this module at build time; keep the two in step).
UKSI_INVERTEBRATE_SQL = ("SELECT tvk FROM taxa WHERE LOWER(COALESCE(kingdom,'')) = 'animalia' "
                         "AND LOWER(COALESCE(phylum,'')) != 'chordata'")

# UKSI ranks that are the broad-group counterpart of a species, and how a report
# names where the status is held.
SENSU_LATO_RANKS = {"Species sensu lato": "sensu lato", "Species aggregate": "aggregate"}
_SL_SUFFIX = re.compile(r"\s+(agg\.?|s\.\s?l\.?|sens\.\s?lat\.?|sensu lato|s\.\s?lat\.?)\s*$",
                        re.IGNORECASE)


def binomial_key(name):
    """'Xanthogramma pedissequum agg.' -> 'xanthogramma pedissequum'."""
    n = (name or "").strip()
    while True:
        m = _SL_SUFFIX.search(n)
        if not m:
            break
        n = n[:m.start()]
    return " ".join(n.lower().split())


_UKSI_CACHE = {}


def _uksi_cached(kind, uksi_path, loader):
    """A UKSI-derived table, cached per file version (UKSI changes only on a swap)."""
    try:
        mt = os.path.getmtime(str(uksi_path))
    except OSError:
        mt = None
    key = (kind, str(uksi_path), mt)
    if key not in _UKSI_CACHE:
        try:
            _UKSI_CACHE[key] = loader() if mt is not None else None
        except sqlite3.Error as e:
            print(f"[codex_repository] UKSI {kind} unavailable: {e}")
            _UKSI_CACHE[key] = None
    return _UKSI_CACHE[key]


def uksi_invertebrate_tvks(uksi_path=None):
    """TVKs UKSI places in Animalia outside Chordata (empty set if unreadable)."""
    uksi_path = str(uksi_path or UKSI_PATH)

    def load():
        c = connect_ro(uksi_path)
        try:
            return frozenset(r[0] for r in c.execute(UKSI_INVERTEBRATE_SQL))
        finally:
            c.close()
    return _uksi_cached("invertebrates", uksi_path, load) or frozenset()


def uksi_sensu_lato_map(uksi_path=None):
    """{species_tvk: (counterpart_tvk, 'sensu lato' | 'aggregate')} from UKSI.

    The counterpart has the same binomial (an "agg." or "s.l." suffix aside) and
    rank 'Species sensu lato' or 'Species aggregate', or is the species' own
    parent at one of those ranks. A slash aggregate ("A b/c") is a different
    concept and is not used. Where a binomial names several species, the one in
    the counterpart's genus is used. Sensu lato is preferred over aggregate.
    """
    uksi_path = str(uksi_path or UKSI_PATH)

    def load():
        c = connect_ro(uksi_path)
        try:
            ph = ",".join("?" * len(SENSU_LATO_RANKS))
            broad = c.execute(f"SELECT tvk, scientific_name, rank, parent_tvk FROM taxa "
                              f"WHERE rank IN ({ph})", list(SENSU_LATO_RANKS)).fetchall()
            by_key = {}
            for tvk, name, rank, parent in broad:
                if "/" in (name or "") or "-group" in (name or ""):
                    continue
                by_key.setdefault(binomial_key(name), []).append(
                    (tvk, SENSU_LATO_RANKS[rank], parent))
            species = {}
            keys = list(by_key)
            for i in range(0, len(keys), 400):
                batch = keys[i:i + 400]
                ph = ",".join("?" * len(batch))
                for tvk, name, parent in c.execute(
                        f"SELECT tvk, scientific_name, parent_tvk FROM taxa WHERE rank = 'Species' "
                        f"AND LOWER(scientific_name) IN ({ph})", batch):
                    species.setdefault(binomial_key(name), []).append((tvk, parent))
            out = {}
            order = {"sensu lato": 0, "aggregate": 1}
            for key, counterparts in by_key.items():
                cands = species.get(key, [])
                for sl_tvk, label, sl_parent in sorted(counterparts, key=lambda x: order[x[1]]):
                    pick = cands if len(cands) == 1 else [s for s in cands if s[1] == sl_parent]
                    for sp_tvk, _ in pick:
                        out.setdefault(sp_tvk, (sl_tvk, label))
            # A species whose UKSI parent is itself the aggregate / s.l. taxon.
            for sp_tvk, parent, prank in c.execute(
                    f"SELECT s.tvk, p.tvk, p.rank FROM taxa s JOIN taxa p ON s.parent_tvk = p.tvk "
                    f"WHERE s.rank = 'Species' AND p.rank IN ({','.join('?' * len(SENSU_LATO_RANKS))})",
                    list(SENSU_LATO_RANKS)):
                out.setdefault(sp_tvk, (parent, SENSU_LATO_RANKS[prank]))
            return out
        finally:
            c.close()
    return _uksi_cached("sensu_lato", uksi_path, load) or {}


# species linked to a review by status or account -- the stored reviews.species_count
# is only set by Codex Manager's import screen, so it reads 0 for most reviews
_LIVE_SPECIES_COUNT = """(SELECT COUNT(*) FROM (
        SELECT tvk FROM manual_entries m WHERE m.review_id = reviews.id
        UNION
        SELECT COALESCE(tvk, species_name) FROM species_profiles p
        WHERE p.review_id = reviews.id))"""


class AnalysisMode(Enum):
    CODEX_FULL = "codex_full"
    PANTHEON_ONLY = "pantheon_only"


class KeySpeciesTier(Enum):
    RARE = "Rare"
    SCARCE = "Scarce"
    PRIORITY = "Priority"
    NONE = "None"


# ============================================================
# Pantheon "GB Status" -> (track, value) mapping
# (used in PANTHEON_ONLY mode)
# Updated to the new 11-track names.
# ============================================================
PANTHEON_GB_STATUS_MAP = {
    "NR":               ("rarity_modern",      "NR"),
    "(NR)":             ("rarity_modern",      "NR"),
    "NR (marine)":      ("rarity_modern",      "NR"),
    "NS":               ("rarity_modern",      "NS"),
    "(NS)":             ("rarity_modern",      "NS"),
    "NS (marine)":      ("rarity_modern",      "NS"),
    "Na":               ("rarity_legacy",      "Na"),
    "Nb":               ("rarity_legacy",      "Nb"),
    "Notable":          ("rarity_legacy",      "Notable"),
    "RDB 1":            ("threat_iucn_legacy", "RDB1"),
    "RDB 2":            ("threat_iucn_legacy", "RDB2"),
    "RDB 3":            ("threat_iucn_legacy", "RDB3"),
    "RDB K":            ("threat_iucn_legacy", "RDBK"),
    "RDB I":            ("threat_iucn_legacy", "RDBK"),
    "pRDB 1":           ("threat_iucn_legacy", "RDB1"),
    "pRDB 2":           ("threat_iucn_legacy", "RDB2"),
    "pRDB 3":           ("threat_iucn_legacy", "RDB3"),
    "Extinct":          ("threat_iucn_legacy", "EX"),
}


# ============================================================
# Jurisdiction -- which designations confer key-species status where
# ============================================================
# A priority listing is made under the law of one country and is a material
# consideration only there. Section 41 is England's list; the Scottish
# Biodiversity List is Scotland's. Rarity and threat are GB-wide and are not
# filtered. This affects the KEY SPECIES decision only -- every designation is
# still stored, returned and displayed.
#
# Defined here, above the class, because method default arguments are evaluated
# when the class body runs.

DEFAULT_JURISDICTION = "England"

# Substrings matched case-insensitively against status_value.
_PRIORITY_BY_JURISDICTION = {
    "England":          ("s.41", "s41", "section 41", "bap"),
    "Wales":            ("wales", "s7", "bap"),
    "Scotland":         ("scottish", "bap"),
    "Northern Ireland": ("northern ireland", "ni priority", "bap"),
    "UK":               (),   # empty tuple = accept everything
}

# Legal instruments that apply only in Northern Ireland, matched against
# status_detail. Everything else (WACA, Habitats Regs, Bern, CITES, CMS, the
# Directives) is GB-wide or international.
_NI_ONLY_LEGAL = ("ni wildlife order", "ni conservation regs")


def _priority_applies(value, jurisdiction):
    # S41 "research only" flags research needs, not site conservation: it never
    # confers Key Species status, in any jurisdiction (Pantheon; 02_Current_State).
    if "research" in (value or "").lower():
        return False
    keys = _PRIORITY_BY_JURISDICTION.get(jurisdiction)
    if keys is None or keys == ():
        return True          # unknown or UK-wide: do not filter
    v = (value or "").lower()
    return any(k in v for k in keys)


def _legal_applies(entry, jurisdiction):
    if jurisdiction in ("Northern Ireland", "UK"):
        return True
    d = ((entry.detail or entry.value) or "").lower()
    return not any(k in d for k in _NI_ONLY_LEGAL)


# Key-species classification thresholds
RARE_IUCN_2001   = {"CR", "EN", "VU", "DD", "EX", "RE"}
SCARCE_IUCN_2001 = {"NT"}
RARE_LEGACY_RDB   = {"RDB1", "RDB2"}
SCARCE_LEGACY_RDB = {"RDB3", "RDBK"}
SCARCE_LEGACY_RARITY = {"Na", "Nb", "Notable"}


# ============================================================
# Data classes
# ============================================================
@dataclass
class StatusEntry:
    """One entry in a track (value + optional detail + provenance)."""
    value: str
    detail: Optional[str] = None
    source: str = ""
    iucn_version: str = ""


def _priority_label(value: str) -> str:
    """Short, honest label for a priority jurisdiction.

    Abbreviated to fit an appendix cell, but never collapsed to a different
    jurisdiction's name. Anything unrecognised is passed through unchanged
    rather than guessed at.
    """
    v = (value or "").lower()
    if "research" in v:
        return "UK BAP (research only)" if "bap" in v else "S41 (research only)"
    if "s.41" in v or "s41" in v or "section 41" in v:
        return "S41"
    if "wales" in v or "s7" in v:
        return "Wales S7"
    if "scottish" in v:
        return "SBL"
    if "northern ireland" in v or v.startswith("ni "):
        return "NI Priority"
    if "bap" in v:
        return "UK BAP"
    return value or ""

@dataclass
class SpeciesStatus:
    """Complete conservation profile for a single species.

    Each track field is either a single StatusEntry (for tracks where
    multiple entries are rare / uninteresting) or a list of StatusEntry
    (for tracks that naturally carry multiple -- legal, priority, bird
    breeding/non-breeding, regional red lists).
    """
    tvk: str

    # Threat
    threat_iucn_2001: Optional[StatusEntry] = None
    threat_iucn_legacy: Optional[StatusEntry] = None
    threat_global_iucn: Optional[StatusEntry] = None

    # Bird threat entries can split by breeding/non-breeding
    threat_iucn_2001_breeding: Optional[StatusEntry] = None
    threat_iucn_2001_nonbreeding: Optional[StatusEntry] = None

    # Rarity
    rarity_modern: Optional[StatusEntry] = None
    rarity_legacy: Optional[StatusEntry] = None

    # Specialist panels
    bocc: Optional[StatusEntry] = None
    specialist_panel: Optional[StatusEntry] = None

    # Regional red lists
    red_list_england: Optional[StatusEntry] = None
    red_list_wales: Optional[StatusEntry] = None

    # Lists (species can have multiple)
    legal_protection: list = field(default_factory=list)   # list[StatusEntry]
    priority: list = field(default_factory=list)            # list[StatusEntry]

    # Invertebrate-only
    sqs: int = 0
    # True when the score is derived from current status by Pantheon's rule
    # because Pantheon published none (Codex Full only).
    sqs_derived: bool = False

    # Profile text (may be None / empty)
    profile: Optional[str] = None
    profile_source: Optional[str] = None

    # Computed
    is_key: bool = False
    tier: KeySpeciesTier = KeySpeciesTier.NONE
    is_invertebrate: bool = False

    # Where the statuses are not the species' own: "sensu lato" or "aggregate",
    # and the TVK that holds them. Empty for a species' own statuses.
    status_held_at: str = ""
    status_from_tvk: str = ""

    @property
    def status_note(self) -> str:
        return f"status held at {self.status_held_at}" if self.status_held_at else ""

    # ------------------------------------------------------------
    # Display helpers -- used by Observatum / Tabella / web Examen UI
    # ------------------------------------------------------------
    @property
    def display_status(self) -> str:
        """Compact human-readable summary for report cells / UI tooltips."""
        parts = []
        # Threat
        if self.threat_iucn_2001 and self.threat_iucn_2001.value not in ("LC", "NA", "NE", "WL"):
            parts.append(self.threat_iucn_2001.value)
        elif self.threat_iucn_legacy:
            parts.append(self.threat_iucn_legacy.value)
        # Rarity
        if self.rarity_modern:
            parts.append(self.rarity_modern.value)
        elif self.rarity_legacy:
            parts.append(self.rarity_legacy.value)
        # BoCC (birds)
        if self.bocc:
            parts.append(f"BoCC {self.bocc.value}")
        # Priority -- name the jurisdictions. The old "S41/BAP (n)" label
        # predated the 11-track scheme and read as Section 41 for species
        # listed only in Scotland, Wales or Northern Ireland.
        for entry in self.priority:
            parts.append(_priority_label(entry.value))
        # Legal -- kept as a count. The instrument names are long, the
        # appendix cell is narrow, and "Legal" is accurate whichever it is.
        if self.legal_protection:
            parts.append(f"Legal ({len(self.legal_protection)})")
        if parts and self.status_held_at:
            parts.append(self.status_note)
        return ", ".join(parts) if parts else ""

    @property
    def short_status(self) -> str:
        """Shortest meaningful label -- for dense table columns."""
        if self.rarity_modern:
            return self.rarity_modern.value
        if self.rarity_legacy:
            return self.rarity_legacy.value
        if self.threat_iucn_2001 and self.threat_iucn_2001.value not in ("LC", "NA", "NE"):
            return self.threat_iucn_2001.value
        if self.threat_iucn_legacy:
            return self.threat_iucn_legacy.value
        if self.bocc:
            return f"BoCC {self.bocc.value}"
        if self.priority:
            return "Priority"
        return ""


# ============================================================
# Repository
# ============================================================
class CodexRepository:

    def __init__(self, db_path: str = None, pantheon_path: str = None,
                 uksi_path: str = None):
        self._db_path = str(db_path or DB_PATH)
        self._pantheon_path = str(pantheon_path or PANTHEON_PATH)
        self._uksi_path = str(uksi_path or UKSI_PATH)
        self._conn = None
        self._pan_repo_obj = None
        self._invert_tvks_cache = None
        self._desig_invert_cache = None

    def _get_conn(self):
        if self._conn is None:
            if not Path(self._db_path).exists():
                raise FileNotFoundError(f"codex.db not found: {self._db_path}")
            self._conn = connect_ro(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _pan_repo(self):
        """pantheon.db through the bridge -- PantheonRepository's one rule (J2)."""
        if self._pan_repo_obj is None:
            if not Path(self._pantheon_path).exists():
                return None
            self._pan_repo_obj = PantheonRepository(
                self._pantheon_path, codex_path=self._db_path, uksi_path=self._uksi_path)
        return self._pan_repo_obj

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
        if self._pan_repo_obj:
            self._pan_repo_obj.close()
            self._pan_repo_obj = None
        self._invert_tvks_cache = None

    # ================================================================
    # Invertebrate TVK lookup (cached on first call)
    # ================================================================
    def _get_invert_tvks(self):
        """TVKs that are invertebrates: UKSI's taxonomy (Animalia outside
        Chordata, the build's rule), plus any TVK JNCC's designations categorise
        as 'Invertebrate' (an old TVK UKSI no longer holds)."""
        if self._invert_tvks_cache is None:
            self._invert_tvks_cache = (self._get_designated_invert_tvks()
                                       | uksi_invertebrate_tvks(self._uksi_path))
        return self._invert_tvks_cache

    def _get_designated_invert_tvks(self):
        """TVKs JNCC's designations categorise as 'Invertebrate' -- the old rule."""
        if getattr(self, "_desig_invert_cache", None) is None:
            c = self._get_conn().cursor()
            c.execute("""SELECT DISTINCT tvk FROM designations
                         WHERE category = 'Invertebrate'""")
            self._desig_invert_cache = frozenset(r[0] for r in c.fetchall())
        return self._desig_invert_cache

    def is_invertebrate(self, tvk):
        """True if the TVK belongs to an invertebrate species."""
        return tvk in self._get_invert_tvks()

    # ================================================================
    # Species and broad group (sensu lato / aggregate)
    # ================================================================
    def sensu_lato_counterpart(self, tvk):
        """(counterpart_tvk, 'sensu lato' | 'aggregate') for a species, or None."""
        return uksi_sensu_lato_map(self._uksi_path).get(tvk)

    def sensu_lato_pairs(self, tvks):
        """{broad_tvk: species_tvk} where BOTH are in `tvks` -- one species
        recorded under two TVKs (the species and its s.l. / aggregate)."""
        present = set(tvks)
        sl_map = uksi_sensu_lato_map(self._uksi_path)
        return {sl: sp for sp, (sl, _) in sl_map.items() if sp in present and sl in present}

    def _status_rows(self, tvks):
        """status_summary rows per TVK, with the s.l. fallback.

        Returns ({tvk: [(track, value, detail, source, iucn), ...]},
                 {tvk: (held_at_tvk, 'sensu lato' | 'aggregate')}).
        A species with no row of its own takes its counterpart's rows.
        """
        def fetch(keys):
            out = {}
            c = self._get_conn().cursor()
            for batch in _chunked(list(dict.fromkeys(keys)), 500):
                ph = ",".join("?" * len(batch))
                c.execute(f"""SELECT tvk, status_track, status_value, status_detail,
                                     source, iucn_version
                              FROM status_summary WHERE tvk IN ({ph})""", batch)
                for row in c.fetchall():
                    out.setdefault(row["tvk"], []).append((
                        row["status_track"], row["status_value"], row["status_detail"],
                        row["source"] or "", row["iucn_version"] or ""))
            return out

        rows = fetch(tvks)
        sl_map = uksi_sensu_lato_map(self._uksi_path)
        need = {t: sl_map[t] for t in tvks if t not in rows and t in sl_map}
        held = {}
        if need:
            broad = fetch(v[0] for v in need.values())
            for t, (sl_tvk, label) in need.items():
                if sl_tvk in broad:
                    rows[t] = broad[sl_tvk]
                    held[t] = (sl_tvk, label)
        return rows, held

    # ================================================================
    # Single species
    # ================================================================
    def get_status_summary(self, tvk, mode=AnalysisMode.CODEX_FULL,
                           jurisdiction=DEFAULT_JURISDICTION):
        """One species -- the batch path, so the two cannot differ."""
        return self.get_statuses_batch([tvk], mode, jurisdiction)[tvk]

    def get_sqs(self, tvk, mode=AnalysisMode.CODEX_FULL):
        return self.get_sqs_scores([tvk], mode).get(tvk, 0)

    def is_key_species(self, tvk, mode=AnalysisMode.CODEX_FULL):
        return self.get_status_summary(tvk, mode).is_key

    def get_all_designations(self, tvk):
        c = self._get_conn().cursor()
        c.execute("""SELECT designation_abbreviation, reporting_category,
                            designation, source, date_designated, iucn_version,
                            criteria_description
                     FROM designations WHERE tvk = ?
                     ORDER BY reporting_category""", (tvk,))
        return [dict(row) for row in c.fetchall()]

    def get_profile(self, tvk):
        """Return just the profile paragraph for a species (or None)."""
        c = self._get_conn().cursor()
        c.execute("""SELECT profile_text, source, date_added, date_updated, added_by
                     FROM species_profiles WHERE tvk = ?""", (tvk,))
        r = c.fetchone()
        if not r:
            return None
        return dict(r)

    # ================================================================
    # Batch
    # ================================================================
    def get_sqs_scores(self, tvks, mode=AnalysisMode.CODEX_FULL):
        """SQS per TVK: what Pantheon published, else derived from the rule.

        Stored scores are Pantheon's own (and any manual entries) -- a record
        of what was published, which is what makes an SQI comparable. Where
        Pantheon has no score, the published rule is applied to current Codex
        statuses instead of storing an invented value. See
        patch_sqs_derive_live.py.
        """
        if not tvks:
            return {}
        if mode == AnalysisMode.PANTHEON_ONLY:
            return self._pantheon_sqs_batch(tvks)
        result = self._stored_sqs(tvks)
        missing = [t for t in dict.fromkeys(tvks) if t not in result]
        if missing:
            result.update(self._derive_sqs_batch(missing))
        return result

    def _stored_sqs(self, tvks):
        c = self._get_conn().cursor()

        def fetch(keys):
            out = {}
            for batch in _chunked(list(dict.fromkeys(keys)), 500):
                ph = ",".join("?" * len(batch))
                c.execute(f"""SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({ph})
                              AND source != 'derived'""", batch)
                for row in c.fetchall():
                    out[row["tvk"]] = row["sqs"]
            return out

        result = fetch(tvks)
        # Species and broad group (Wil's rule, 9 Oct 2026): a species with no
        # stored score of its own takes its sensu lato / aggregate counterpart's.
        # Pantheon's 2017 concept was usually the broad one (Nomada panzeri), and
        # records moved onto the species must not lose the published score.
        missing = [t for t in dict.fromkeys(tvks) if t not in result]
        if missing:
            sl_map = uksi_sensu_lato_map(self._uksi_path)
            via = {t: sl_map[t][0] for t in missing if t in sl_map}
            if via:
                held = fetch(via.values())
                for sp, sl in via.items():
                    if sl in held:
                        result[sp] = held[sl]
        return result

    def get_stored_sqs_tvks(self, tvks):
        """TVKs whose SQS is STORED -- Pantheon's published score or a manual entry --
        as opposed to derived live from the rule by get_sqs_scores."""
        if not tvks:
            return set()
        return set(self._stored_sqs(tvks))

    def _derive_sqs_batch(self, tvks):
        """Apply Pantheon's published rule to current Codex statuses.

        Invertebrates only -- SQS is an invertebrate construct, and a score for
        a lichen would be arithmetic without meaning. The scope is what it was
        before CDX-1 widened "invertebrate": species in JNCC's invertebrate
        designations, plus any other invertebrate Codex holds a status for (its
        own, or held at sensu lato -- a review-only status). An invertebrate
        with no status anywhere is not scored: that would put a derived 1 on
        every species Pantheon lacks.

        Queries status_summary directly: get_statuses_batch calls
        get_sqs_scores, so routing through it would recurse.
        """
        if not tvks:
            return {}
        try:
            from shared.sqs_derivation import derive_from_tracks
        except ImportError:
            try:
                from sqs_derivation import derive_from_tracks
            except ImportError:
                return {}

        invert = self._get_invert_tvks()
        designated = self._get_designated_invert_tvks()
        candidates = [t for t in tvks if t in invert]
        if not candidates:
            return {}
        rows, _held = self._status_rows(candidates)

        result = {}
        for tvk in candidates:
            if tvk not in rows and tvk not in designated:
                continue
            tracks = {}
            for track, value, *_ in rows.get(tvk, []):
                tracks[track] = value
            score = derive_from_tracks(tracks)
            if score:          # 0 and 1 are not worth storing as "has a score"
                result[tvk] = score
        return result

    def get_statuses_batch(self, tvks, mode=AnalysisMode.CODEX_FULL,
                           jurisdiction=DEFAULT_JURISDICTION):
        if not tvks:
            return {}
        if mode == AnalysisMode.PANTHEON_ONLY:
            return self._pantheon_statuses_batch(tvks, jurisdiction)

        c = self._get_conn().cursor()
        invert_set = self._get_invert_tvks()
        track_data, held = self._status_rows(tvks)
        stored = self._stored_sqs(tvks)
        sqs_map = self.get_sqs_scores(tvks, mode)

        # Fetch profiles
        profile_map = {}
        for batch in _chunked(list(dict.fromkeys(tvks)), 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, profile_text, source FROM species_profiles
                         WHERE tvk IN ({ph})""", batch)
            for row in c.fetchall():
                profile_map[row["tvk"]] = (row["profile_text"], row["source"])

        result = {}
        for tvk in tvks:
            status = SpeciesStatus(tvk=tvk, sqs=sqs_map.get(tvk, 0))
            status.sqs_derived = tvk in sqs_map and tvk not in stored
            status.is_invertebrate = tvk in invert_set
            if tvk in held:
                status.status_from_tvk, status.status_held_at = held[tvk]
            for track, value, detail, source, iucn in track_data.get(tvk, []):
                self._apply_track(status, track, value, detail, source, iucn)
            if tvk in profile_map:
                status.profile = profile_map[tvk][0]
                status.profile_source = profile_map[tvk][1]
            status.tier = _classify(status, jurisdiction) if status.is_invertebrate else KeySpeciesTier.NONE
            status.is_key = status.tier != KeySpeciesTier.NONE
            result[tvk] = status
        return result

    def get_key_species_from_list(self, tvks, mode=AnalysisMode.CODEX_FULL):
        """Invertebrate key species from a list. Non-inverts are never key."""
        return {tvk: s for tvk, s in self.get_statuses_batch(tvks, mode).items() if s.is_key}

    def get_key_species_by_tier(self, tvks, mode=AnalysisMode.CODEX_FULL):
        key = self.get_key_species_from_list(tvks, mode)
        tiers = {"Rare": [], "Scarce": [], "Priority": []}
        for s in key.values():
            if s.tier.value in tiers:
                tiers[s.tier.value].append(s)
        for t in tiers.values():
            t.sort(key=lambda s: (-s.sqs, s.tvk))
        return tiers

    def compute_sqi(self, tvks, mode=AnalysisMode.CODEX_FULL,
                    jurisdiction=DEFAULT_JURISDICTION):
        """The SQI, exactly as the assessment computes it.

        Delegates to PantheonAnalysisService -- the one implementation (EXA1):
        SQI = sum of SQS / species analysed x 100, where species analysed are
        those Pantheon holds (ecology or a score, through the bridge) plus any
        scored from current status. It used to divide by scoring species only,
        so Examen's project table showed Glory Park 120 against the report's 117.
        Reliable if at least 15 species have SQS scores.
        """
        from shared.services.pantheon_analysis_service import PantheonAnalysisService
        pan = self._pan_repo()
        r = PantheonAnalysisService(pan, self).analyse(list(tvks), mode=mode,
                                                         jurisdiction=jurisdiction)
        o = r.overall_sqi
        if o is None:
            return {"sqi": 0, "sqs_sum": 0, "scoring_species": 0, "species_analysed": 0,
                    "total_species": 0, "reliable": False}
        return {"sqi": o.sqi, "sqs_sum": o.sqs_sum, "scoring_species": o.species_with_sqs,
                "species_analysed": o.species_analysed, "total_species": r.total_species,
                "reliable": o.reliable}

    def compare_modes(self, tvks):
        """Side-by-side Codex vs Pantheon-only comparison."""
        c_sqi = self.compute_sqi(tvks, AnalysisMode.CODEX_FULL)
        p_sqi = self.compute_sqi(tvks, AnalysisMode.PANTHEON_ONLY)
        c_key = self.get_key_species_from_list(tvks, AnalysisMode.CODEX_FULL)
        p_key = self.get_key_species_from_list(tvks, AnalysisMode.PANTHEON_ONLY)
        total = len(set(tvks))
        c_pct = round(len(c_key) / total * 100, 1) if total else 0
        p_pct = round(len(p_key) / total * 100, 1) if total else 0
        codex_only = [s for tvk, s in c_key.items() if tvk not in p_key]
        return {
            "codex": {"sqi": c_sqi["sqi"], "key_count": len(c_key),
                      "key_pct": c_pct, "sqs_species": c_sqi["scoring_species"]},
            "pantheon": {"sqi": p_sqi["sqi"], "key_count": len(p_key),
                         "key_pct": p_pct, "sqs_species": p_sqi["scoring_species"]},
            "delta": {"sqi": c_sqi["sqi"] - p_sqi["sqi"],
                      "key_count": len(c_key) - len(p_key),
                      "key_pct": round(c_pct - p_pct, 1),
                      "sqs_species": c_sqi["scoring_species"] - p_sqi["scoring_species"]},
            "codex_only_key": codex_only,
        }

    # ================================================================
    # Metadata
    # ================================================================
    def get_metadata(self):
        c = self._get_conn().cursor()
        c.execute("SELECT key, value FROM metadata")
        return {r["key"]: r["value"] for r in c.fetchall()}

    def get_species_count(self):
        c = self._get_conn().cursor()
        c.execute("SELECT COUNT(DISTINCT tvk) FROM designations")
        return c.fetchone()[0]

    def get_build_log(self, limit=10):
        """Latest build_log entries (most recent first)."""
        c = self._get_conn().cursor()
        c.execute("""SELECT timestamp, jncc_rows, pantheon_sqs, manual_entries,
                            bridge_resolved, profiles_count, notes
                     FROM build_log ORDER BY id DESC LIMIT ?""", (limit,))
        return [dict(r) for r in c.fetchall()]

    # ================================================================
    # Consumer-friendly dict APIs
    # (used by Observatum, Tabella, web Examen for display + export)
    # ================================================================
    def get_species_conservation_summary(self, tvk, mode=AnalysisMode.CODEX_FULL):
        """Complete conservation profile as a dict, for species display.

        Returns a dict with every track, SQS, profile, key-species info, and
        display strings. Designed for UI consumption -- the dataclass version
        is for internal / computational use.
        """
        status = self.get_status_summary(tvk, mode)
        return {
            "tvk": tvk,
            "is_invertebrate": status.is_invertebrate,

            "threat_iucn_2001":       _entry_to_dict(status.threat_iucn_2001),
            "threat_iucn_legacy":     _entry_to_dict(status.threat_iucn_legacy),
            "threat_global_iucn":     _entry_to_dict(status.threat_global_iucn),

            "threat_iucn_2001_breeding":    _entry_to_dict(status.threat_iucn_2001_breeding),
            "threat_iucn_2001_nonbreeding": _entry_to_dict(status.threat_iucn_2001_nonbreeding),

            "rarity_modern":  _entry_to_dict(status.rarity_modern),
            "rarity_legacy":  _entry_to_dict(status.rarity_legacy),

            "bocc":              _entry_to_dict(status.bocc),
            "specialist_panel":  _entry_to_dict(status.specialist_panel),

            "red_list_england":  _entry_to_dict(status.red_list_england),
            "red_list_wales":    _entry_to_dict(status.red_list_wales),

            "legal_protection":  [_entry_to_dict(e) for e in status.legal_protection],
            "priority":          [_entry_to_dict(e) for e in status.priority],

            "sqs": status.sqs,
            "sqs_derived": status.sqs_derived,
            "status_held_at": status.status_held_at,
            "status_from_tvk": status.status_from_tvk,
            "profile": status.profile,
            "profile_source": status.profile_source,

            "is_key": status.is_key,
            "key_species_tier": status.tier.value,
            "status_display": status.display_status,
            "short_status": status.short_status,
        }

    def get_conservation_for_export(self, tvks, mode=AnalysisMode.CODEX_FULL):
        """Batch lookup for export columns.

        Returns {tvk: {...}} with keys designed for spreadsheet export.
        Each value is a string (joined with '; ' for multi-entry tracks).
        """
        statuses = self.get_statuses_batch(tvks, mode)
        result = {}
        for tvk, s in statuses.items():
            result[tvk] = {
                "red_list":       _entry_value(s.threat_iucn_2001) or _entry_value(s.threat_iucn_legacy),
                "rarity":         _entry_value(s.rarity_modern) or _entry_value(s.rarity_legacy),
                "bocc":           _entry_value(s.bocc),
                "global_red_list": _entry_value(s.threat_global_iucn),
                "red_list_eng":   _entry_value(s.red_list_england),
                "red_list_wal":   _entry_value(s.red_list_wales),
                "priority":       "; ".join(e.value for e in s.priority),
                "legal":          "; ".join(
                    (e.detail or e.value) for e in s.legal_protection
                ),
                "sqs":            s.sqs,
                "status_display": s.display_status,
                "tier":           s.tier.value,
                "is_key":         s.is_key,
            }
        return result

    # ================================================================
    # Reviews
    # ================================================================
    def get_reviews(self):
        """List all loaded reviews with metadata."""
        c = self._get_conn().cursor()
        try:
            try:
                c.execute(f"""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, {_LIVE_SPECIES_COUNT} AS species_count,
                                supersedes_id, notes
                         FROM reviews ORDER BY id""")
            except sqlite3.OperationalError:      # old codex.db: stored count
                c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews ORDER BY id""")
            return [dict(r) for r in c.fetchall()]
        except sqlite3.OperationalError:
            return []

    def get_review(self, review_id):
        c = self._get_conn().cursor()
        try:
            try:
                c.execute(f"""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, {_LIVE_SPECIES_COUNT} AS species_count,
                                supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
            except sqlite3.OperationalError:      # old codex.db: stored count
                c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
            row = c.fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError:
            return None

    # ================================================================
    # Pantheon-only internals -- through PantheonRepository, so the bridge
    # rule (every bridged taxon, J2 incumbent first, NOTVK: never shadowing a
    # populated taxon) is the one the ecology uses. Until 9 Oct 2026 this mode
    # kept one name-matched Pantheon taxon per species, often an empty NOTVK:
    # twin: Kent strict SQI 171 against the published 175 (INF1 / EXA6).
    # ================================================================
    def _pantheon_sqs_batch(self, tvks):
        pan = self._pan_repo()
        return pan.get_sqs_scores(list(tvks)) if pan else {}

    def _pantheon_statuses_batch(self, tvks, jurisdiction=DEFAULT_JURISDICTION):
        pan = self._pan_repo()
        invert_set = self._get_invert_tvks()
        if not pan:
            out = {}
            for tvk in tvks:
                s = SpeciesStatus(tvk=tvk)
                s.is_invertebrate = tvk in invert_set
                out[tvk] = s
            return out
        sqs_map = pan.get_sqs_scores(list(tvks))
        con_data = pan.get_conservation_rows(list(tvks))

        result = {}
        for tvk in tvks:
            status = SpeciesStatus(tvk=tvk, sqs=sqs_map.get(tvk, 0))
            status.is_invertebrate = tvk in invert_set
            for cat, abbr in con_data.get(tvk, []):     # incumbent's rows first
                self._apply_pantheon_row(status, cat, abbr)
            status.tier = _classify(status, jurisdiction) if status.is_invertebrate else KeySpeciesTier.NONE
            status.is_key = status.tier != KeySpeciesTier.NONE
            result[tvk] = status
        return result

    def _get_research_only_tvks(self):
        """Current UKSI TVKs that Pantheon lists as S41 'research only'.

        Pantheon is keyed on 2017 TVKs, so the list goes through the TVK bridge.
        Cached for the life of the repository.
        """
        if getattr(self, "_research_only", None) is not None:
            return self._research_only
        out = set()
        try:
            pan_repo = self._pan_repo()
            pan = pan_repo._get_conn() if pan_repo is not None else None
            if pan is not None:
                pan_tvks = [r[0] for r in pan.execute(
                    "SELECT DISTINCT tvk FROM conservation_status WHERE reporting_category = ?",
                    ("Section 41 Priority Species - research only",))]
                c = self._get_conn()
                for batch in _chunked(pan_tvks, 500):
                    ph = ",".join("?" * len(batch))
                    out.update(r[0] for r in c.execute(
                        f"SELECT uksi_tvk FROM tvk_bridge WHERE pantheon_tvk IN ({ph})", batch))
        except Exception as e:
            print(f"[codex_repository] _get_research_only_tvks: {e}")  # I7: was silent
        self._research_only = out
        return out

    def _apply_pantheon_row(self, status, cat, abbr):
        """Route a Pantheon conservation_status row to the correct new track."""
        if cat == "GB Status":
            mapping = PANTHEON_GB_STATUS_MAP.get(abbr)
            if not mapping:
                return
            track, value = mapping
            entry = StatusEntry(value=value, source="pantheon")
            if track == "rarity_modern" and not status.rarity_modern:
                status.rarity_modern = entry
            elif track == "rarity_legacy" and not status.rarity_legacy:
                status.rarity_legacy = entry
            elif track == "threat_iucn_legacy" and not status.threat_iucn_legacy:
                status.threat_iucn_legacy = entry
        elif cat == "GB Red List":
            if abbr not in ("None", "Unknown", "Not reviewed") and not status.threat_iucn_2001:
                status.threat_iucn_2001 = StatusEntry(value=abbr, source="pantheon")
        elif cat == "Section 41 Priority Species":
            status.priority.append(StatusEntry(value="NERC S.41 England", source="pantheon"))
        elif cat == "Section 41 Priority Species - research only":
            status.priority.append(StatusEntry(value="NERC S.41 England (research)",
                                               source="pantheon"))
        elif cat == "Legal Protection":
            status.legal_protection.append(StatusEntry(value="Protected", detail=abbr,
                                                       source="pantheon"))

    # ================================================================
    # Internal: apply a status_summary row to a SpeciesStatus
    # ================================================================
    def _apply_track(self, status, track, value, detail, source, iucn):
        """Route a status_summary row into the right SpeciesStatus field."""
        entry = StatusEntry(value=value, detail=detail,
                            source=source, iucn_version=iucn)

        # Threat tracks -- single entry per track, except IUCN 2001 with
        # breeding/non-breeding splits
        if track == "threat_iucn_2001":
            if detail == "Breeding":
                status.threat_iucn_2001_breeding = entry
            elif detail == "Non-breeding":
                status.threat_iucn_2001_nonbreeding = entry
            else:
                status.threat_iucn_2001 = entry
        elif track == "threat_iucn_legacy":
            status.threat_iucn_legacy = entry
        elif track == "threat_global_iucn":
            status.threat_global_iucn = entry

        # Rarity
        elif track == "rarity_modern":
            status.rarity_modern = entry
        elif track == "rarity_legacy":
            status.rarity_legacy = entry

        # Specialist
        elif track == "bocc":
            status.bocc = entry
        elif track == "specialist_panel":
            status.specialist_panel = entry

        # Regional red lists
        elif track == "red_list_england":
            status.red_list_england = entry
        elif track == "red_list_wales":
            status.red_list_wales = entry

        # Lists
        elif track == "legal_protection":
            status.legal_protection.append(entry)
        elif track == "priority":
            # JNCC lists research-only species as plain S41; Pantheon distinguishes them.
            if status.tvk in self._get_research_only_tvks() and \
                    any(k in (value or "").lower() for k in ("s.41", "s41", "section 41", "bap")):
                entry.value = ("UK BAP (research)" if "bap" in (value or "").lower()
                               else "NERC S.41 England (research)")
            status.priority.append(entry)


# ============================================================
# Module-level helpers
# ============================================================
def _classify(status, jurisdiction=DEFAULT_JURISDICTION):
    """Classify into Rare / Scarce / Priority / None.

    Called ONLY for invertebrate species (the caller is responsible for
    checking status.is_invertebrate). This function assumes invert-only.

    `jurisdiction` filters which priority listings and legal instruments count
    towards the Priority tier. Rarity and threat are GB-wide and unfiltered.
    """
    # An NA species -- not applicable: not an established native, so not
    # eligible for IUCN assessment -- is never a Key Species, whatever its
    # rarity status. A recent arrival or a single stray can be "Nationally Rare"
    # simply because it has barely been recorded. Its rarity is still stored
    # and displayed; it confers no key status. Decided 26 September 2026 on
    # NECR702 (Chrysomela vigintipunctata, Smaragdina salicina).
    if status.threat_iucn_2001 and \
            (status.threat_iucn_2001.value or "").strip().upper() == "NA":
        return KeySpeciesTier.NONE

    is_rare = is_scarce = is_priority = False

    # Modern IUCN GB threat
    if status.threat_iucn_2001:
        v = status.threat_iucn_2001.value
        if v in RARE_IUCN_2001:
            is_rare = True
        elif v in SCARCE_IUCN_2001:
            is_scarce = True

    # Modern rarity (NR = rare, NS = scarce)
    if status.rarity_modern:
        v = status.rarity_modern.value
        if v == "NR":
            is_rare = True
        elif v == "NS":
            is_scarce = True

    # Legacy IUCN RDB categories
    if status.threat_iucn_legacy:
        v = status.threat_iucn_legacy.value
        if v in RARE_LEGACY_RDB:
            is_rare = True
        elif v in SCARCE_LEGACY_RDB:
            is_scarce = True

    # Legacy rarity (Na, Nb, Notable -- all scarce)
    if status.rarity_legacy:
        if status.rarity_legacy.value in SCARCE_LEGACY_RARITY:
            is_scarce = True

    # Legal / priority -- priority tier, but only designations that apply in
    # this jurisdiction. An SBL listing does not make a species key in England.
    if any(_priority_applies(e.value, jurisdiction) for e in status.priority):
        is_priority = True
    if any(_legal_applies(e, jurisdiction) for e in status.legal_protection):
        is_priority = True

    # Specialist panel (Spider Amber etc.) -- scarce-like
    if status.specialist_panel:
        is_scarce = True

    if is_rare:
        return KeySpeciesTier.RARE
    if is_scarce:
        return KeySpeciesTier.SCARCE
    if is_priority:
        return KeySpeciesTier.PRIORITY
    return KeySpeciesTier.NONE


_TIER_RANK = {KeySpeciesTier.RARE: 3, KeySpeciesTier.SCARCE: 2,
              KeySpeciesTier.PRIORITY: 1, KeySpeciesTier.NONE: 0}


def stronger_status(first, second):
    """The stronger of two SpeciesStatus by Key tier; `first` on a tie.

    For one species recorded under two TVKs (EXA14): pass the species' own
    status first, so the s.s. status stands unless the s.l. one ranks higher.
    """
    if first is None:
        return second
    if second is None:
        return first
    return second if _TIER_RANK.get(second.tier, 0) > _TIER_RANK.get(first.tier, 0) else first


def _chunked(lst, n):
    lst = list(lst)
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _entry_to_dict(entry):
    """Convert a StatusEntry to a dict (or None)."""
    if entry is None:
        return None
    return {
        "value": entry.value,
        "detail": entry.detail,
        "source": entry.source,
        "iucn_version": entry.iucn_version,
    }


def _entry_value(entry):
    """Return the entry's value, or empty string if None."""
    return entry.value if entry else ""
