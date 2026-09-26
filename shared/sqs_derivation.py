"""sqs_derivation -- compute Species Quality Scores from current Codex statuses.

Why
---
Pantheon stores SQS values that were correct when it last assessed each species.
Where a status review has happened since, the stored score is stale. Codex carries
JNCC December 2023 across 11 tracks, so the same published rule applied to Codex
statuses gives a correctly-computed score for species Pantheon has not revisited.

This is NOT a rival index. It is Pantheon's own rule, applied to newer inputs.

The published rule
------------------
From https://pantheon.brc.ac.uk/lexicon/sqs -- the score is a function of BOTH
rarity and threat, which is why a single rarity category maps to several scores:

    0   Not native.
    1   Species that are not rare or scarce. Includes those new to Britain.
    4   Scarce species not threatened under post-1994 / post-2001 IUCN criteria.
        Rare species listed RDB K or RDB I under pre-1994 criteria.
        Notable species (Na, Nb, Notable).
    8   Rare species not threatened under post-1994 / post-2001 criteria.
        Rare OR scarce species listed Vulnerable under post-1994 / post-2001.
        Rare species listed RDB 2 or RDB 3 under pre-1994 criteria.
    16  Rare or scarce species listed Endangered under post-1994 / post-2001.
        Rare species listed RDB 1 under pre-1994 criteria.
    32  Rare or scarce species listed Critically Endangered, CR (Possibly Extinct),
        Regionally Extinct, Extinct, or Extinct in the Wild.

Note there is no score of 2 in the published rule.

Codex tracks used
-----------------
Only rarity and threat contribute. BoCC, Section 41 / priority, legal protection
and the regional red lists are policy or legislative listings, not measures of
rarity or threat, and take no part in the score.

    rarity_modern       NR, NS
    rarity_legacy       Na, Nb, Notable
    threat_iucn_2001    CR, EN, VU, NT, LC, DD, RE, EX, EW ...
    threat_iucn_legacy  RDB1, RDB2, RDB3, RDBK, RDBI, Extinct ...
"""
from __future__ import annotations

from typing import Dict, Optional

# --- vocabulary ------------------------------------------------------------

# Threat values that count as "threatened" at each score level. Values are
# upper-cased and stripped before lookup, so both codes and words work.
_CRITICAL = {
    "CR", "CRITICALLY ENDANGERED",
    "CR (PE)", "CR(PE)", "CRITICALLY ENDANGERED (POSSIBLY EXTINCT)",
    "RE", "REGIONALLY EXTINCT",
    "EX", "EXTINCT",
    "EW", "EXTINCT IN THE WILD",
}
_ENDANGERED = {"EN", "ENDANGERED"}
_VULNERABLE = {"VU", "VULNERABLE"}

# Data Deficient and Near Threatened DO NOT elevate the score.
#
# Pantheon's scoring-systems page lists five criteria, and DD and NT appear in
# them only as things a Nationally Scarce or Nationally Rare species may ALSO
# be -- never as a qualification in their own right:
#
#   "Nationally Scarce species that do not qualify under any of the other
#    criteria. They may be classed as IUCN Least Concern, Near Threatened, or
#    Data Deficient, Not Evaluated, or Not Assessed."
#
# So a species that is DD or NT and nothing else scores 1, and one that is DD
# AND Nationally Rare scores 8 because of the rarity, not the DD.
#
# These sets are retained for readability and for any caller that wants to
# report the status; they take no part in the score. See patch_sqs_dd_nt.py.
_DATA_DEFICIENT = {"DD", "DATA DEFICIENT"}
_NEAR_THREATENED = {"NT", "NEAR THREATENED"}

# Pre-1994 Red Data Book categories.
_RDB1 = {"RDB1", "RDB 1", "RDB1 (ENDANGERED)", "ENDANGERED (RDB1)"}
_RDB23 = {"RDB2", "RDB 2", "RDB3", "RDB 3",
          "RDB2 (VULNERABLE)", "RDB3 (RARE)"}
_RDB_KI = {"RDBK", "RDB K", "RDBI", "RDB I",
           "RDBK (INSUFFICIENTLY KNOWN)", "RDBI (INDETERMINATE)"}
_RDB_EXTINCT = {"RDB APP", "RDBAPP", "EXTINCT"}

_RARE = {"NR", "NATIONALLY RARE"}
_SCARCE = {"NS", "NATIONALLY SCARCE"}
_NOTABLE = {"NA", "NB", "NOTABLE",
            "NATIONALLY NOTABLE A", "NATIONALLY NOTABLE B", "NATIONALLY NOTABLE"}


def _norm(v: Optional[str]) -> str:
    return (v or "").strip().upper()


def derive_sqs(rarity: Optional[str] = None,
               threat: Optional[str] = None,
               threat_legacy: Optional[str] = None,
               native: bool = True) -> int:
    """Species Quality Score from current status values.

    rarity        rarity_modern or rarity_legacy value (NR, NS, Na, Nb, Notable)
    threat        threat_iucn_2001 value (CR, EN, VU, NT, LC ...)
    threat_legacy threat_iucn_legacy value (RDB1, RDB2, RDB3, RDBK, RDBI ...)
    native        False gives 0, per the published rule

    Returns 0, 1, 4, 8, 16 or 32.
    """
    if not native:
        return 0

    r, t, tl = _norm(rarity), _norm(threat), _norm(threat_legacy)

    rdb_confers_rare = tl in _RDB1 or tl in _RDB23 or tl in _RDB_KI or tl in _RDB_EXTINCT
    iucn_confers_listing = t in _CRITICAL or t in _ENDANGERED or t in _VULNERABLE
    # DD is deliberately NOT included: it qualifies a species for nothing on its
    # own. A Data Deficient species that is also Nationally Rare still scores 8,
    # through r in _RARE.
    is_rare = r in _RARE or rdb_confers_rare
    is_scarce = r in _SCARCE
    is_notable = r in _NOTABLE
    listed = is_rare or is_scarce or is_notable or iucn_confers_listing

    # 32 -- the top of the ladder, for rare or scarce species at the extreme end
    if listed and (t in _CRITICAL or tl in _RDB_EXTINCT):
        return 32

    # 16 -- Endangered, or the pre-1994 equivalent for rare species
    if listed and t in _ENDANGERED:
        return 16
    if is_rare and tl in _RDB1:
        return 16

    # 8 -- Vulnerable (rare or scarce), pre-1994 RDB 2/3 for rare species,
    #      or simply Nationally Rare with no threat listing
    if listed and t in _VULNERABLE:
        return 8
    if is_rare and tl in _RDB23:
        return 8

    # 4 -- RDB K / I for rare species (checked before the bare Nationally Rare
    #      fallback below, since those categories cap the score at 4), scarce
    #      and unthreatened, or Notable
    if is_rare and tl in _RDB_KI:
        return 4

    # Nationally Rare with no threat listing
    if is_rare:
        return 8

    if is_scarce or is_notable:
        return 4

    # 1 -- everything else that is native and neither rare nor scarce.
    #      This includes species that are only Near Threatened, Data Deficient,
    #      Least Concern, Not Evaluated or Not Assessed: under Pantheon's rule
    #      none of those qualifies a species for a higher score.
    return 1


def derive_from_tracks(tracks: Dict[str, str], native: bool = True) -> int:
    """Convenience wrapper taking a {track_name: value} dict from Codex.

    Prefers the modern rarity track over the legacy one, and the 2001 IUCN
    track over the legacy RDB track, matching CodexRepository's own precedence.
    """
    rarity = tracks.get("rarity_modern") or tracks.get("rarity_legacy")
    return derive_sqs(
        rarity=rarity,
        threat=tracks.get("threat_iucn_2001"),
        threat_legacy=tracks.get("threat_iucn_legacy"),
        native=native,
    )


VALID_SCORES = (0, 1, 4, 8, 16, 32)
