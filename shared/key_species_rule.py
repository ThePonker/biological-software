"""The Rare / Scarce Key Species rule, in one place (Examen and Codex both use it).

Follows Telfer (2023), as Wil's issued reports did.
Rare Key Species: Red Data Book categories (v1: RDB1, RDB2, RDB3, RDBK, RDBI);
Threatened and Data Deficient (v2: CR, EN, VU, DD, RE, EX, EW); Nationally
Rare (v3: NR).
Scarce Key Species: Near Threatened (v2: NT); Nationally Scarce / Notable
(v3: NS; v1: Na, Nb, Notable, N, Scarce).
Codes are compared after strip + upper-case, so "Na", "NA " and "nb" all match.
Priority and legally protected species are Key but not Rare Key; that part
lives with the callers. Decided 24 November 2026: Codex follows Examen.
"""

RARE_V1 = {"RDB1", "RDB 1", "RDB2", "RDB 2", "RDB3", "RDB 3",
           "RDBK", "RDB K", "RDBI", "RDB I"}
RARE_V2 = {"CR", "EN", "VU", "DD", "RE", "EX", "EW"}
SCARCE_V2 = {"NT"}
RARE_V3 = {"NR"}
SCARCE_V3 = {"NS"}
SCARCE_V1 = {"NA", "NB", "NOTABLE", "N", "SCARCE"}


def norm(v):
    """Strip and upper-case a status code (None -> '')."""
    return (v or "").strip().upper()


def rarity_tier(code):
    """'rare' | 'scarce' | '' for a rarity code (modern or legacy)."""
    c = norm(code)
    if c in RARE_V3:
        return "rare"
    if c in SCARCE_V3 or c in SCARCE_V1:
        return "scarce"
    return ""


def threat_tier(code):
    """'rare' | 'scarce' | '' for a 2001 IUCN GB threat code."""
    c = norm(code)
    if c in RARE_V2:
        return "rare"
    if c in SCARCE_V2:
        return "scarce"
    return ""


def legacy_threat_tier(code):
    """'rare' | 'scarce' | '' for a legacy (RDB-era) threat code."""
    c = norm(code)
    if c in RARE_V1:
        return "rare"
    if c in SCARCE_V1:
        return "scarce"
    return ""


def axis_tier(rarity="", threat="", threat_legacy=""):
    """'rare' | 'scarce' | '' from the rarity and threat codes alone; rare wins."""
    tiers = {rarity_tier(rarity), threat_tier(threat), legacy_threat_tier(threat_legacy)}
    if "rare" in tiers:
        return "rare"
    if "scarce" in tiers:
        return "scarce"
    return ""


ALL_CODES = RARE_V1 | RARE_V2 | SCARCE_V2 | RARE_V3 | SCARCE_V3 | SCARCE_V1
