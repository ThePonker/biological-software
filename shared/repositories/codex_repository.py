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
"""

import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import paths


DB_PATH = paths.CODEX_DB
PANTHEON_PATH = paths.PANTHEON_DB


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

    # Profile text (may be None / empty)
    profile: Optional[str] = None
    profile_source: Optional[str] = None

    # Computed
    is_key: bool = False
    tier: KeySpeciesTier = KeySpeciesTier.NONE
    is_invertebrate: bool = False

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

    def __init__(self, db_path: str = None, pantheon_path: str = None):
        self._db_path = str(db_path or DB_PATH)
        self._pantheon_path = str(pantheon_path or PANTHEON_PATH)
        self._conn = None
        self._pan_conn = None
        self._bridge = None
        self._invert_tvks_cache = None

    def _get_conn(self):
        if self._conn is None:
            if not Path(self._db_path).exists():
                raise FileNotFoundError(f"codex.db not found: {self._db_path}")
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _get_pantheon_conn(self):
        if self._pan_conn is None:
            if not Path(self._pantheon_path).exists():
                return None
            self._pan_conn = sqlite3.connect(self._pantheon_path)
            self._pan_conn.row_factory = sqlite3.Row
        return self._pan_conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
        if self._pan_conn:
            self._pan_conn.close()
            self._pan_conn = None
        self._bridge = None
        self._invert_tvks_cache = None

    # ================================================================
    # Invertebrate TVK lookup (cached on first call)
    # ================================================================
    def _get_invert_tvks(self):
        """Returns set of TVKs whose category is 'Invertebrate'."""
        if self._invert_tvks_cache is None:
            c = self._get_conn().cursor()
            c.execute("""SELECT DISTINCT tvk FROM designations
                         WHERE category = 'Invertebrate'""")
            self._invert_tvks_cache = set(r[0] for r in c.fetchall())
        return self._invert_tvks_cache

    def is_invertebrate(self, tvk):
        """True if the TVK belongs to an invertebrate species."""
        return tvk in self._get_invert_tvks()

    # ================================================================
    # Single species
    # ================================================================
    def get_status_summary(self, tvk, mode=AnalysisMode.CODEX_FULL,
                           jurisdiction=DEFAULT_JURISDICTION):
        if mode == AnalysisMode.PANTHEON_ONLY:
            return self._pantheon_status(tvk, jurisdiction)

        c = self._get_conn().cursor()
        status = SpeciesStatus(tvk=tvk)
        status.is_invertebrate = self.is_invertebrate(tvk)

        c.execute("""SELECT status_track, status_value, status_detail,
                            source, iucn_version
                     FROM status_summary WHERE tvk = ?""", (tvk,))
        for row in c.fetchall():
            self._apply_track(
                status,
                row["status_track"],
                row["status_value"],
                row["status_detail"],
                row["source"] or "",
                row["iucn_version"] or "",
            )

        # SQS
        c.execute("SELECT sqs FROM sqs_scores WHERE tvk = ?", (tvk,))
        r = c.fetchone()
        if r:
            status.sqs = r["sqs"]

        # Profile
        c.execute("""SELECT profile_text, source FROM species_profiles
                     WHERE tvk = ?""", (tvk,))
        r = c.fetchone()
        if r:
            status.profile = r["profile_text"]
            status.profile_source = r["source"]

        # Classification (invertebrate-only)
        status.tier = _classify(status, jurisdiction) if status.is_invertebrate else KeySpeciesTier.NONE
        status.is_key = status.tier != KeySpeciesTier.NONE
        return status

    def get_sqs(self, tvk, mode=AnalysisMode.CODEX_FULL):
        if mode == AnalysisMode.PANTHEON_ONLY:
            return self._pantheon_sqs_single(tvk)
        c = self._get_conn().cursor()
        c.execute("SELECT sqs FROM sqs_scores WHERE tvk = ?", (tvk,))
        r = c.fetchone()
        return r["sqs"] if r else 0

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
        c = self._get_conn().cursor()
        result = {}
        for batch in _chunked(tvks, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({ph})
                          AND source != 'derived'""", batch)
            for row in c.fetchall():
                result[row["tvk"]] = row["sqs"]
        missing = [t for t in set(tvks) if t not in result]
        if missing:
            result.update(self._derive_sqs_batch(missing))
        return result

    def _derive_sqs_batch(self, tvks):
        """Apply Pantheon's published rule to current Codex statuses.

        Invertebrates only -- SQS is an invertebrate construct, and a score for
        a lichen would be arithmetic without meaning.

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
        candidates = [t for t in tvks if t in invert]
        if not candidates:
            return {}

        c = self._get_conn().cursor()
        tracks = {}
        for batch in _chunked(candidates, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, status_track, status_value
                          FROM status_summary WHERE tvk IN ({ph})""", batch)
            for row in c.fetchall():
                tracks.setdefault(row["tvk"], {})[row["status_track"]] = row["status_value"]

        result = {}
        for tvk in candidates:
            score = derive_from_tracks(tracks.get(tvk, {}))
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

        # Fetch all status_summary rows for the batch
        track_data = {}  # {tvk: [(track, value, detail, source, iucn), ...]}
        for batch in _chunked(tvks, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, status_track, status_value, status_detail,
                                source, iucn_version
                         FROM status_summary WHERE tvk IN ({ph})""", batch)
            for row in c.fetchall():
                track_data.setdefault(row["tvk"], []).append((
                    row["status_track"], row["status_value"], row["status_detail"],
                    row["source"] or "", row["iucn_version"] or "",
                ))

        sqs_map = self.get_sqs_scores(tvks, mode)

        # Fetch profiles
        profile_map = {}
        for batch in _chunked(tvks, 500):
            ph = ",".join("?" * len(batch))
            c.execute(f"""SELECT tvk, profile_text, source FROM species_profiles
                         WHERE tvk IN ({ph})""", batch)
            for row in c.fetchall():
                profile_map[row["tvk"]] = (row["profile_text"], row["source"])

        result = {}
        for tvk in tvks:
            status = SpeciesStatus(tvk=tvk, sqs=sqs_map.get(tvk, 0))
            status.is_invertebrate = tvk in invert_set
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

    def compute_sqi(self, tvks, mode=AnalysisMode.CODEX_FULL):
        """Compute SQI. Only invertebrates contribute (SQS is invert-only).

        SQI = (sum of SQS) / (species with SQS) * 100
        Reliable if at least 15 species have SQS scores.
        """
        scores = self.get_sqs_scores(tvks, mode)
        unique = set(tvks)
        sqs_sum = sum(scores.values())
        scoring = len(scores)
        sqi = round(sqs_sum / scoring * 100) if scoring > 0 else 0
        return {"sqi": sqi, "sqs_sum": sqs_sum, "scoring_species": scoring,
                "total_species": len(unique), "reliable": scoring >= 15}

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
            c.execute("""SELECT id, review_name, author, taxon_group,
                                status_track, date_published, date_imported,
                                source_file, species_count, supersedes_id, notes
                         FROM reviews WHERE id = ?""", (review_id,))
            row = c.fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError:
            return None

    # ================================================================
    # TVK Bridge (Pantheon old TVK -> current UKSI TVK)
    # ================================================================
    def _get_bridge(self):
        """Load bridge mapping: {uksi_tvk: pantheon_tvk}."""
        if self._bridge is None:
            self._bridge = {}
            try:
                c = self._get_conn().cursor()
                c.execute("""SELECT uksi_tvk, pantheon_tvk FROM tvk_bridge
                             WHERE match_method = 'name'""")
                for r in c.fetchall():
                    self._bridge[r["uksi_tvk"]] = r["pantheon_tvk"]
            except Exception:
                pass
        return self._bridge

    def _to_pantheon_tvk(self, uksi_tvk):
        bridge = self._get_bridge()
        return bridge.get(uksi_tvk, uksi_tvk)

    def _to_pantheon_tvks(self, uksi_tvks):
        bridge = self._get_bridge()
        return {tvk: bridge.get(tvk, tvk) for tvk in uksi_tvks}

    # ================================================================
    # Pantheon-only internals (bridge-aware, new-track-aware)
    # ================================================================
    def _pantheon_sqs_single(self, tvk):
        pan = self._get_pantheon_conn()
        if not pan:
            return 0
        pc = pan.cursor()
        pan_tvk = self._to_pantheon_tvk(tvk)
        pc.execute("SELECT sqs FROM sqs_scores WHERE tvk = ?", (pan_tvk,))
        r = pc.fetchone()
        return r["sqs"] if r else 0

    def _pantheon_sqs_batch(self, tvks):
        pan = self._get_pantheon_conn()
        if not pan:
            return {}
        pc = pan.cursor()
        tvk_map = self._to_pantheon_tvks(tvks)
        reverse = {v: k for k, v in tvk_map.items()}
        pan_tvks = list(tvk_map.values())

        result = {}
        for batch in _chunked(pan_tvks, 500):
            ph = ",".join("?" * len(batch))
            pc.execute(f"SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({ph})", batch)
            for r in pc.fetchall():
                uksi_tvk = reverse.get(r["tvk"], r["tvk"])
                result[uksi_tvk] = r["sqs"]
        return result

    def _pantheon_status(self, tvk, jurisdiction=DEFAULT_JURISDICTION):
        """Single species Pantheon-only lookup. Uses Pantheon ecology DB,
        maps via the bridge, routes legacy Pantheon status codes to new
        track names."""
        pan = self._get_pantheon_conn()
        status = SpeciesStatus(tvk=tvk)
        status.is_invertebrate = self.is_invertebrate(tvk)
        if not pan:
            return status
        pc = pan.cursor()
        pan_tvk = self._to_pantheon_tvk(tvk)

        pc.execute("SELECT sqs FROM sqs_scores WHERE tvk = ?", (pan_tvk,))
        r = pc.fetchone()
        if r:
            status.sqs = r["sqs"]

        pc.execute("""SELECT reporting_category, abbreviation
                      FROM conservation_status WHERE tvk = ?""", (pan_tvk,))
        for row in pc.fetchall():
            self._apply_pantheon_row(status, row["reporting_category"], row["abbreviation"])

        status.tier = _classify(status, jurisdiction) if status.is_invertebrate else KeySpeciesTier.NONE
        status.is_key = status.tier != KeySpeciesTier.NONE
        return status

    def _pantheon_statuses_batch(self, tvks, jurisdiction=DEFAULT_JURISDICTION):
        pan = self._get_pantheon_conn()
        if not pan:
            return {tvk: SpeciesStatus(tvk=tvk) for tvk in tvks}

        pc = pan.cursor()
        tvk_map = self._to_pantheon_tvks(tvks)
        reverse = {v: k for k, v in tvk_map.items()}
        pan_tvks = list(tvk_map.values())
        invert_set = self._get_invert_tvks()

        # SQS
        sqs_map = {}
        for batch in _chunked(pan_tvks, 500):
            ph = ",".join("?" * len(batch))
            pc.execute(f"SELECT tvk, sqs FROM sqs_scores WHERE tvk IN ({ph})", batch)
            for r in pc.fetchall():
                uksi_tvk = reverse.get(r["tvk"], r["tvk"])
                sqs_map[uksi_tvk] = r["sqs"]

        # Conservation status rows
        con_data = {}
        for batch in _chunked(pan_tvks, 500):
            ph = ",".join("?" * len(batch))
            pc.execute(f"""SELECT tvk, reporting_category, abbreviation
                           FROM conservation_status WHERE tvk IN ({ph})""", batch)
            for row in pc.fetchall():
                uksi_tvk = reverse.get(row["tvk"], row["tvk"])
                con_data.setdefault(uksi_tvk, []).append(
                    (row["reporting_category"], row["abbreviation"]))

        result = {}
        for tvk in tvks:
            status = SpeciesStatus(tvk=tvk, sqs=sqs_map.get(tvk, 0))
            status.is_invertebrate = tvk in invert_set
            for cat, abbr in con_data.get(tvk, []):
                self._apply_pantheon_row(status, cat, abbr)
            status.tier = _classify(status, jurisdiction) if status.is_invertebrate else KeySpeciesTier.NONE
            status.is_key = status.tier != KeySpeciesTier.NONE
            result[tvk] = status
        return result

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


def _chunked(lst, n):
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
