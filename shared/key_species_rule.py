"""The Rare / Scarce Key Species rule, in one place (Examen and Codex both use it).

Follows Telfer (2023), as Wil's issued reports did.
Rare Key Species: Red Data Book categories (v1: RDB1, RDB2, RDB3, RDBK, RDBI);
Threatened and Data Deficient (v2: CR, EN, VU, DD, RE, EX, EW); Nationally
Rare (v3: NR).
Scarce Key Species: Near Threatened (v2: NT); Nationally Scarce / Notable
(v3: NS; v1: Na, Nb, Notable, N, Scarce).
Codes are compared after strip + upper-case ("nb" matches "Nb"). Notable A and the IUCN
threat category Not Applicable are both "NA" once upper-cased, so the LINE decides which
it is (24 November 2026, Wil): on a rarity line it is Notable A, on a threat line Not
Applicable -- except "Na" spelt exactly so on a threat line, which is a Notable A in the
wrong place and counts as neither (never zeroed as "not native"). Notable A never counts
on a threat line. case_problem() is the import check that keeps "Na" on rarity lines and
"NA" on threat lines.
The legacy threat track (codex.db threat_iucn_legacy) holds two vocabularies:
the pre-1994 RDB codes, and the CR / EN / VU / DD / NT codes that JNCC publishes
as "Red Listing based on 1994 IUCN guidelines" (Falk & Chandler 2005, Falk &
Crossley 2005, the fly reviews; designation abbreviations RedList_GB_post94-*).
Both count as Rare Key. NT counts as Rare there, not Scarce: in those reviews NT
means 15 or fewer hectads, the Nationally Rare threshold, and Pantheon marks
those species Nationally Rare. Decided 24 November 2026 (Wil, "option 2").
Priority and legally protected species are Key but not Rare Key; that part
lives with the callers. Decided 24 November 2026: Codex follows Examen.
"""

RARE_V1 = {"RDB1", "RDB 1", "RDB2", "RDB 2", "RDB3", "RDB 3",
           "RDBK", "RDB K", "RDBI", "RDB I"}
RARE_V2 = {"CR", "EN", "VU", "DD", "RE", "EX", "EW"}
SCARCE_V2 = {"NT"}
RARE_V3 = {"NR"}
SCARCE_V3 = {"NS"}
SCARCE_V1 = {"NB", "NOTABLE", "N", "SCARCE"}      # Notable A: is_notable_a(), exact spelling
# 1994 IUCN-criteria codes on the legacy threat track (Falk & Chandler 2005; Falk &
# Crossley 2005). NT is here because those reviews' NT = 15 or fewer hectads. EX is
# deliberately absent, as before.
RARE_POST94 = {"CR", "EN", "VU", "DD", "NT"}


NOTABLE_A = "Na"         # rarity: Notable A
NOT_APPLICABLE = "NA"    # threat: IUCN Not Applicable (not an established native)
RARITY_TRACKS = ("rarity_modern", "rarity_legacy")
CODE_LABELS = {NOTABLE_A: "Na (Notable A)", NOT_APPLICABLE: "NA (not applicable)"}


def is_notable_a(code):
    """For a RARITY value: True for Notable A ("Na", any case -- a rarity line cannot hold
    the threat category Not Applicable)."""
    return (code or "").strip().upper() == "NA"


def is_not_applicable(code):
    """For a THREAT value: True for Not Applicable ("NA", any case), but not for "Na" spelt
    exactly so -- that is Notable A on the wrong line, and must not zero a species."""
    v = (code or "").strip()
    return v.upper() == "NA" and v != NOTABLE_A


def code_label(code):
    """A code as shown on screen: "Na (Notable A)", "NA (not applicable)", else unchanged."""
    c = (code or "").strip()
    return CODE_LABELS.get(c, code)


def label_codes(text):
    """A status line for the screen with Na / NA spelt out ("VU, Na" -> "VU, Na (Notable A)").
    Whole codes only, exact case; reports keep the plain codes."""
    import re
    return re.sub(r"(?<![\w(])(Na|NA)(?![\w)]| \()", lambda m: CODE_LABELS[m.group(1)], text or "")


def case_problem(track, value):
    """'' when value is fine on track, else why not: Notable A must be "Na" on a rarity
    line, and Not Applicable "NA" on a threat line. Only NA-like values are checked."""
    v = (value or "").strip()
    if v.upper() != "NA":
        return ""
    want = NOTABLE_A if track in RARITY_TRACKS else NOT_APPLICABLE
    if v == want:
        return ""
    if track in RARITY_TRACKS:
        return (f"'{v}' on {track}: a rarity line takes Notable A as 'Na'; "
                f"Not Applicable ('NA') is a threat category")
    return (f"'{v}' on {track}: a threat line takes Not Applicable as 'NA'; "
            f"Notable A ('Na') is a rarity")


def norm(v):
    """Strip and upper-case a status code (None -> '')."""
    return (v or "").strip().upper()


def rarity_tier(code):
    """'rare' | 'scarce' | '' for a rarity code (modern or legacy)."""
    c = norm(code)
    if c in RARE_V3:
        return "rare"
    if c in SCARCE_V3 or c in SCARCE_V1 or is_notable_a(code):     # rarity line
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
    """'rare' | 'scarce' | '' for a code on the legacy threat track: a pre-1994 RDB
    category, or a 1994-criteria CR / EN / VU / DD / NT (rare; see the module note)."""
    c = norm(code)
    if c in RARE_V1 or c in RARE_POST94:
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


ALL_CODES = (RARE_V1 | RARE_POST94 | RARE_V2 | SCARCE_V2 | RARE_V3 | SCARCE_V3 | SCARCE_V1
             | {NOTABLE_A})
