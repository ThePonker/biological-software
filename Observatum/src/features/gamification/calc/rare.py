"""
Rare Species Calculator Module (v2).

Classifies observed species into rarity tiers using Codex as the source of
truth (was UKSI's stale conservation columns).

v2 changes (Codex Strategy doc, 16 April 2026):
  - Routed through shared.repositories.codex_repository.CodexRepository
  - Tier mapping updated for the 11-track scheme:
        protected: any legal_protection entry
        critical:  threat_iucn_2001 = CR; or threat_iucn_legacy = RDB1
        very_rare: threat_iucn_2001 = EN; or threat_iucn_legacy = RDB2;
                   or rarity_modern = NR; or rarity_legacy = Na
        rare:      threat_iucn_2001 = VU; or threat_iucn_legacy = RDB3
        uncommon:  threat_iucn_2001 = NT; or threat_iucn_legacy = RDBK;
                   or rarity_modern = NS; or rarity_legacy = Nb / Notable
  - Invertebrate-only: matches design principle that rarity-related scoring
    applies only to invertebrates (Pantheon/ISIS lineage)
  - Excludes "WL" (Waiting List) from any tier -- pending assessments don't
    award gamification points
"""

import sqlite3
from typing import Dict, List, Any, Optional

from ..theme import RARE_MILESTONES, RARITY_TIERS


# ============================================================
# Tier classification table
# ============================================================
# Maps (track, value) -> tier. First match wins; precedence is implicit
# in the tier order (protected > critical > very_rare > rare > uncommon).
# We compute candidate tiers for all matches and pick the highest.
# ============================================================
TIER_PRIORITY = {
    "protected": 0,
    "critical":  1,
    "very_rare": 2,
    "rare":      3,
    "uncommon":  4,
}

# (track, value) -> tier
STATUS_TO_TIER = {
    # threat_iucn_2001 (modern GB Red List)
    ("threat_iucn_2001", "CR"): "critical",
    ("threat_iucn_2001", "EN"): "very_rare",
    ("threat_iucn_2001", "VU"): "rare",
    ("threat_iucn_2001", "NT"): "uncommon",
    # LC, DD, NA, NE, RE, EX, WL, EW -- no tier assignment

    # threat_iucn_legacy (pre-2001 RDB)
    ("threat_iucn_legacy", "RDB1"): "critical",
    ("threat_iucn_legacy", "RDB2"): "very_rare",
    ("threat_iucn_legacy", "RDB3"): "rare",
    ("threat_iucn_legacy", "RDBK"): "uncommon",
    # 1994-IUCN values within legacy track:
    ("threat_iucn_legacy", "CR"):  "critical",
    ("threat_iucn_legacy", "EN"):  "very_rare",
    ("threat_iucn_legacy", "VU"):  "rare",
    ("threat_iucn_legacy", "NT"):  "uncommon",

    # rarity_modern (NR/NS hectad-based)
    ("rarity_modern", "NR"): "very_rare",
    ("rarity_modern", "NS"): "uncommon",

    # rarity_legacy (Na/Nb/Notable)
    ("rarity_legacy", "Na"):       "very_rare",
    ("rarity_legacy", "Nb"):       "uncommon",
    ("rarity_legacy", "Notable"):  "uncommon",
}


def _highest_tier(tiers: List[str]) -> Optional[str]:
    """Return the highest-priority tier from a list, or None if empty."""
    if not tiers:
        return None
    return min(tiers, key=lambda t: TIER_PRIORITY.get(t, 99))


class RareCalculator:
    """
    Calculates rare species achievements via CodexRepository.

    Invertebrate-only: only invertebrate observations are counted, matching
    the design principle that SQS / rarity-tier scoring applies only to
    invertebrates (the Pantheon/ISIS lineage).
    """

    # Public for tabs/rare.py
    TIER_ORDER = TIER_PRIORITY

    def __init__(self, get_obs_conn_func, get_uksi_conn_func):
        """
        Initialize with database connection functions.

        Args:
            get_obs_conn_func: Callable returning a Connection to observatum.db
            get_uksi_conn_func: Callable returning a Connection to uksi.db
                                (kept for signature compatibility; not used
                                directly -- CodexRepository handles UKSI joins
                                if needed)
        """
        self._get_obs_conn = get_obs_conn_func
        self._get_uksi_conn = get_uksi_conn_func
        self._cache: Optional[List[Dict[str, Any]]] = None

    # ============================================================
    # Internal: Codex repository accessor
    # ============================================================
    def _get_codex_repo(self):
        """Lazily create a CodexRepository for this call."""
        from shared.repositories.codex_repository import CodexRepository
        return CodexRepository()

    # ============================================================
    # Internal: classify a species' status entries -> tier
    # ============================================================
    def _classify_from_summary(self, status_summary) -> Optional[str]:
        """
        Given a SpeciesStatus from CodexRepository.get_status_summary,
        return the highest applicable rarity tier (or None).

        'protected' wins outright if any legal_protection entry exists.
        Otherwise we collect candidate tiers across threat/rarity tracks
        and return the highest-priority one.
        """
        # Protected trumps everything else
        if status_summary.legal_protection:
            return "protected"

        candidates = []

        # threat_iucn_2001
        if status_summary.threat_iucn_2001:
            t = STATUS_TO_TIER.get(
                ("threat_iucn_2001", status_summary.threat_iucn_2001.value)
            )
            if t:
                candidates.append(t)

        # threat_iucn_legacy
        if status_summary.threat_iucn_legacy:
            t = STATUS_TO_TIER.get(
                ("threat_iucn_legacy", status_summary.threat_iucn_legacy.value)
            )
            if t:
                candidates.append(t)

        # rarity_modern
        if status_summary.rarity_modern:
            t = STATUS_TO_TIER.get(
                ("rarity_modern", status_summary.rarity_modern.value)
            )
            if t:
                candidates.append(t)

        # rarity_legacy
        if status_summary.rarity_legacy:
            t = STATUS_TO_TIER.get(
                ("rarity_legacy", status_summary.rarity_legacy.value)
            )
            if t:
                candidates.append(t)

        return _highest_tier(candidates)

    # ============================================================
    # Public API
    # ============================================================
    def get_observed(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get all rare species the user has observed (invertebrate scope)."""
        if use_cache and self._cache is not None:
            return self._cache

        rare_species: List[Dict[str, Any]] = []

        try:
            # Step 1: distinct observed TVKs
            with self._get_obs_conn() as obs_conn:
                obs_cursor = obs_conn.cursor()
                obs_cursor.execute("""
                    SELECT DISTINCT species_tvk, species_name, common_name, family
                    FROM observations
                    WHERE species_tvk IS NOT NULL AND species_tvk != ''
                """)
                observed = obs_cursor.fetchall()

            if not observed:
                self._cache = []
                return []

            # Step 2: query Codex in batch
            tvks = [row[0] for row in observed]
            obs_index = {row[0]: row for row in observed}

            repo = self._get_codex_repo()
            try:
                statuses = repo.get_statuses_batch(tvks)
            finally:
                repo.close()

            # Step 3: classify -- invertebrate-only (is_invertebrate guard)
            for tvk, status in statuses.items():
                if not status.is_invertebrate:
                    continue
                tier = self._classify_from_summary(status)
                if not tier:
                    continue

                obs_row = obs_index.get(tvk)
                if not obs_row:
                    continue

                # Build a status_text for display (best available label)
                status_text = ""
                if status.threat_iucn_2001:
                    status_text = status.threat_iucn_2001.value
                elif status.threat_iucn_legacy:
                    status_text = status.threat_iucn_legacy.value
                elif status.rarity_modern:
                    status_text = status.rarity_modern.value
                elif status.rarity_legacy:
                    status_text = status.rarity_legacy.value
                elif status.legal_protection:
                    # Use the first legal entry's detail or value
                    le = status.legal_protection[0]
                    status_text = le.detail or le.value

                rare_species.append({
                    "tvk": tvk,
                    "scientific_name": obs_row[1] or "",
                    "common_name": obs_row[2] or "",
                    "family": obs_row[3] or "",
                    "rarity_tier": tier,
                    "status_text": status_text,
                    # Fields kept for backward compat with anything
                    # that reads these names directly
                    "red_list_status": (
                        status.threat_iucn_2001.value
                        if status.threat_iucn_2001 else
                        (status.threat_iucn_legacy.value
                         if status.threat_iucn_legacy else "")
                    ),
                    "rarity_status": (
                        status.rarity_modern.value
                        if status.rarity_modern else
                        (status.rarity_legacy.value
                         if status.rarity_legacy else "")
                    ),
                    "legal_protection": (
                        "; ".join(
                            (e.detail or e.value)
                            for e in status.legal_protection
                        )
                        if status.legal_protection else ""
                    ),
                })

            self._cache = rare_species

        except Exception as e:
            print(f"[Gamification] Error getting rare species: {e}")
            self._cache = []

        return self._cache or []

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of rare species observations by tier."""
        rare_species = self.get_observed()

        tier_counts = {
            "uncommon":  0,
            "rare":      0,
            "very_rare": 0,
            "critical":  0,
            "protected": 0,
        }

        for species in rare_species:
            tier = species["rarity_tier"]
            if tier in tier_counts:
                tier_counts[tier] += 1

        return {
            "total":    sum(tier_counts.values()),
            "by_tier":  tier_counts,
            "species":  rare_species,
        }

    def calculate_milestones(self) -> List[Dict[str, Any]]:
        """Calculate milestone rosettes for rare species."""
        summary = self.get_summary()
        total_rare = summary["total"]

        milestones = []
        for milestone in RARE_MILESTONES:
            earned = total_rare >= milestone["threshold"]
            milestones.append({
                "name":          milestone["name"],
                "threshold":     milestone["threshold"],
                "trophy_tier":   milestone["trophy_tier"],
                "earned":        earned,
                "current_count": total_rare,
            })

        return milestones

    def get_pins(self) -> List[Dict[str, Any]]:
        """Get pin data for each rare species observed."""
        rare_species = self.get_observed()

        pins = []
        for species in rare_species:
            tier = species["rarity_tier"]
            colours = RARITY_TIERS.get(tier, RARITY_TIERS["uncommon"])

            pins.append({
                "tvk":             species["tvk"],
                "scientific_name": species["scientific_name"],
                "common_name":     species["common_name"],
                "family":          species["family"],
                "rarity_tier":     tier,
                "colour":          colours["primary"],
                "status_text":     species.get("status_text", ""),
            })

        # Sort by tier, then by scientific name
        pins.sort(
            key=lambda x: (
                self.TIER_ORDER.get(x["rarity_tier"], 99),
                x["scientific_name"],
            )
        )
        return pins

    def clear_cache(self):
        """Clear the cached rare species data."""
        self._cache = None
