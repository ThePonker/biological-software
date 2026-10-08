"""
Build codex.db -- The Biological Software Conservation Authority (v5)

Primary source: JNCC Conservation Designations Spreadsheet (Dec 2023)
Secondary source: Pantheon v3.7.4 (SQS scores only, re-keyed via TVK bridge)
Override layer: Manual entries + imported reviews (always preserved across rebuilds)

v5 changes (per Codex Strategy doc, 16 April 2026):
  - Biodiversity-wide conservation status (previously invertebrate-only)
  - 11-track status scheme organised in 5 conceptual categories:
        Threat:     threat_iucn_2001, threat_iucn_legacy, threat_global_iucn
        Rarity:     rarity_modern, rarity_legacy
        Specialist: bocc, specialist_panel
        Legal:      legal_protection
        Priority:   priority
        Regional:   red_list_england, red_list_wales
  - Category column added to designations (populated from JNCC Category)
  - species_profiles table added (populated via review imports; survives rebuilds)
  - status_detail used consistently to carry instrument/jurisdiction specifics
  - NR/NS-excludes routed as NR/NS (some reviews publish only -excludes)

Usage:
    python scripts/build_codex_db.py              # Build/rebuild
    python scripts/build_codex_db.py --stats      # Show stats
"""

import sqlite3
import os
import sys
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import paths

# ============================================================
# Paths
# ============================================================
CODEX_PATH = str(paths.CODEX_DB)
JNCC_DIR = str(paths.JNCC_DIR)
import glob as _glob   # the newest designations workbook in JNCC_DIR, whatever its capitalisation
_found = sorted(_glob.glob(os.path.join(JNCC_DIR, "*esignations-*.xlsx")))
JNCC_XLSX = _found[-1] if _found else os.path.join(JNCC_DIR, "taxon-designations.xlsx")
PANTHEON_PATH = str(paths.PANTHEON_DB)
UKSI_PATH = str(paths.UKSI_DB)

# ============================================================
# Schema
# ============================================================
SCHEMA = """
    CREATE TABLE IF NOT EXISTS designations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        species_name TEXT,
        common_name TEXT,
        taxon_group TEXT,
        category TEXT,
        reporting_category TEXT NOT NULL,
        designation TEXT NOT NULL,
        designation_abbreviation TEXT NOT NULL,
        designation_description TEXT,
        source TEXT NOT NULL,
        source_description TEXT,
        date_designated TEXT,
        iucn_version TEXT,
        criteria_description TEXT,
        comments TEXT,
        origin TEXT NOT NULL DEFAULT 'jncc'
    );

    CREATE TABLE IF NOT EXISTS status_summary (
        tvk TEXT NOT NULL,
        status_track TEXT NOT NULL,
        status_value TEXT NOT NULL,
        status_detail TEXT,
        source TEXT,
        iucn_version TEXT,
        date_designated TEXT,
        origin TEXT NOT NULL DEFAULT 'jncc',
        PRIMARY KEY (tvk, status_track, status_detail)
    );

    CREATE TABLE IF NOT EXISTS sqs_scores (
        tvk TEXT PRIMARY KEY,
        sqs INTEGER NOT NULL,
        source TEXT NOT NULL DEFAULT 'pantheon'
    );

    CREATE TABLE IF NOT EXISTS tvk_bridge (
        pantheon_tvk TEXT NOT NULL,
        uksi_tvk TEXT NOT NULL,
        species_name TEXT,
        match_method TEXT NOT NULL DEFAULT 'name',
        PRIMARY KEY (pantheon_tvk)
    );

    CREATE TABLE IF NOT EXISTS manual_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tvk TEXT NOT NULL,
        species_name TEXT,
        status_track TEXT NOT NULL,
        status_value TEXT NOT NULL,
        status_detail TEXT,
        source_review TEXT,
        date_added TEXT NOT NULL,
        added_by TEXT DEFAULT 'manual',
        notes TEXT,
        review_id INTEGER,
        FOREIGN KEY (review_id) REFERENCES reviews(id)
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        licence TEXT,
        review_name TEXT NOT NULL,
        author TEXT,
        taxon_group TEXT,
        status_track TEXT NOT NULL,
        date_published TEXT,
        date_imported TEXT NOT NULL,
        source_file TEXT,
        species_count INTEGER,
        supersedes_id INTEGER,
        notes TEXT,
        FOREIGN KEY (supersedes_id) REFERENCES reviews(id)
    );

    CREATE TABLE IF NOT EXISTS species_profiles (
        tvk TEXT NOT NULL,
        review_id INTEGER NOT NULL DEFAULT 0,
        species_name TEXT,
        profile_text TEXT NOT NULL,
        source TEXT,
        date_added TEXT NOT NULL,
        date_updated TEXT,
        added_by TEXT,
        PRIMARY KEY (tvk, review_id)
    );

    CREATE TABLE IF NOT EXISTS metadata (
        key TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS build_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        jncc_rows INTEGER DEFAULT 0,
        pantheon_sqs INTEGER DEFAULT 0,
        manual_entries INTEGER DEFAULT 0,
        bridge_resolved INTEGER DEFAULT 0,
        profiles_count INTEGER DEFAULT 0,
        notes TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_desig_tvk ON designations(tvk);
    CREATE INDEX IF NOT EXISTS idx_desig_abbr ON designations(designation_abbreviation);
    CREATE INDEX IF NOT EXISTS idx_desig_category ON designations(category);
    CREATE INDEX IF NOT EXISTS idx_summary_tvk ON status_summary(tvk);
    CREATE INDEX IF NOT EXISTS idx_summary_track ON status_summary(status_track);
    CREATE INDEX IF NOT EXISTS idx_sqs_tvk ON sqs_scores(tvk);
    CREATE INDEX IF NOT EXISTS idx_manual_tvk ON manual_entries(tvk);
    CREATE INDEX IF NOT EXISTS idx_reviews_track ON reviews(status_track);
    CREATE INDEX IF NOT EXISTS idx_bridge_pan ON tvk_bridge(pantheon_tvk);
    CREATE INDEX IF NOT EXISTS idx_bridge_uksi ON tvk_bridge(uksi_tvk);
    CREATE INDEX IF NOT EXISTS idx_profiles_tvk ON species_profiles(tvk);
"""

# ============================================================
# Designation -> status track mapping (11-track scheme)
# ============================================================
# Each entry maps a JNCC designation_abbreviation to:
#     (status_track, status_value, status_detail)
# status_detail carries instrument/jurisdiction specifics so we don't
# proliferate tracks. None means "no extra detail".
#
# Abbreviations not in this dict are silently dropped -- they are either
# duplicates we've chosen to ignore (e.g. WL, some global and bird codes) or
# codes we've decided aren't useful to surface in status_summary.
# ============================================================
DESIG_TO_TRACK = {

    # -----------------------------------------------------------------
    # THREAT ASSESSMENTS -- threat_iucn_2001 (modern IUCN, GB-scale)
    # -----------------------------------------------------------------
    "RedList_GB_post2001-RE":       ("threat_iucn_2001", "RE", None),
    "RedList_GB_post2001-CR(PE)":   ("threat_iucn_2001", "CR", "Possibly Extinct"),
    "RedList_GB_post2001-CR":       ("threat_iucn_2001", "CR", None),
    "RedList_GB_post2001-EN":       ("threat_iucn_2001", "EN", None),
    "RedList_GB_post2001-VU":       ("threat_iucn_2001", "VU", None),
    "RedList_GB_post2001-NT":       ("threat_iucn_2001", "NT", None),
    "RedList_GB_post2001-DD":       ("threat_iucn_2001", "DD", None),
    "RedList_GB_post2001-LC":       ("threat_iucn_2001", "LC", None),
    "RedList_GB_post2001-NA":       ("threat_iucn_2001", "NA", None),
    "RedList_GB_post2001-NE":       ("threat_iucn_2001", "NE", None),
    "RedList_GB_post2001-EX":       ("threat_iucn_2001", "EX", None),
    "RedList_GB_post2001-EW":       ("threat_iucn_2001", "EW", None),
    "RedList_GB_post2001-WL":       ("threat_iucn_2001", "WL", "Waiting List"),

    # Bird-specific GB IUCN 2001 (breeding/non-breeding population splits)
    "Bird_RedList_GB_post2001-CR_Breeding":     ("threat_iucn_2001", "CR", "Breeding"),
    "Bird_RedList_GB_post2001-EN_Breeding":     ("threat_iucn_2001", "EN", "Breeding"),
    "Bird_RedList_GB_post2001-VU_Breeding":     ("threat_iucn_2001", "VU", "Breeding"),
    "Bird_RedList_GB_post2001-NT_Breeding":     ("threat_iucn_2001", "NT", "Breeding"),
    "Bird_RedList_GB_post2001-LC_Breeding":     ("threat_iucn_2001", "LC", "Breeding"),
    "Bird_RedList_GB_post2001-CR_NonBreeding":  ("threat_iucn_2001", "CR", "Non-breeding"),
    "Bird_RedList_GB_post2001-EN_NonBreeding":  ("threat_iucn_2001", "EN", "Non-breeding"),
    "Bird_RedList_GB_post2001-VU_NonBreeding":  ("threat_iucn_2001", "VU", "Non-breeding"),
    "Bird_RedList_GB_post2001-NT_NonBreeding":  ("threat_iucn_2001", "NT", "Non-breeding"),
    "Bird_RedList_GB_post2001-LC_NonBreeding":  ("threat_iucn_2001", "LC", "Non-breeding"),

    # -----------------------------------------------------------------
    # THREAT ASSESSMENTS -- threat_iucn_legacy (pre-2001 systems)
    # -----------------------------------------------------------------
    # 1994 IUCN guidelines (transitional)
    "RedList_GB_post94-EN":         ("threat_iucn_legacy", "EN", "1994 IUCN"),
    "RedList_GB_post94-VU":         ("threat_iucn_legacy", "VU", "1994 IUCN"),
    "RedList_GB_post94-NT":         ("threat_iucn_legacy", "NT", "1994 IUCN"),
    "RedList_GB_post94-DD":         ("threat_iucn_legacy", "DD", "1994 IUCN"),
    "RedList_GB_post94-CR":         ("threat_iucn_legacy", "CR", "1994 IUCN"),
    "RedList_GB_post94-EX":         ("threat_iucn_legacy", "EX", "1994 IUCN"),

    # Pre-1994 Red Data Book
    "RedList_GB_Pre94-EX":          ("threat_iucn_legacy", "EX", "Pre-1994 RDB"),
    "RedList_GB_Pre94-EN":          ("threat_iucn_legacy", "RDB1", None),
    "RedList_GB_Pre94-VU":          ("threat_iucn_legacy", "RDB2", None),
    "RedList_GB_Pre94-R":           ("threat_iucn_legacy", "RDB3", None),
    "RedList_GB_Pre94-Insu":        ("threat_iucn_legacy", "RDBK", "Insufficiently Known"),
    "RedList_GB_Pre94-Inde":        ("threat_iucn_legacy", "RDBK", "Indeterminate"),

    # -----------------------------------------------------------------
    # THREAT ASSESSMENTS -- threat_global_iucn
    # -----------------------------------------------------------------
    "RedList_Global_post2001-EX":   ("threat_global_iucn", "EX", None),
    "RedList_Global_post2001-CR":   ("threat_global_iucn", "CR", None),
    "RedList_Global_post2001-EN":   ("threat_global_iucn", "EN", None),
    "RedList_Global_post2001-VU":   ("threat_global_iucn", "VU", None),
    "RedList_Global_post2001-NT":   ("threat_global_iucn", "NT", None),
    "RedList_Global_post2001-LC":   ("threat_global_iucn", "LC", None),
    "RedList_Global_post2001-DD":   ("threat_global_iucn", "DD", None),
    # Global pre-2001 (rare, but present)
    "RedList_Global_post94-NT":     ("threat_global_iucn", "NT", "1994 IUCN"),
    "RedList_Global_post94-VU":     ("threat_global_iucn", "VU", "1994 IUCN"),
    "RedList_Global_post94-LR_CD":  ("threat_global_iucn", "NT", "1994 IUCN LR/cd"),

    # -----------------------------------------------------------------
    # RARITY -- rarity_modern (IUCN-compatible hectad-based)
    # Both forms of the modern rarity codes are routed. JNCC: -includes = NS/NR
    # including Red Listed taxa; -excludes = NS/NR excluding them. Both mean the
    # species is Nationally Scarce/Rare, and some reviews publish only -excludes.
    "NR-includes":                  ("rarity_modern", "NR", None),
    "NS-includes":                  ("rarity_modern", "NS", None),
    # -excludes is routed too: for 272 species (Falk & Crossley 2005, water
    # beetles 2010, hoverflies 2014 ...) it is the ONLY NS/NR code. Ranked
    # one below -includes in ABBR_PRIORITY, so a species with both keeps one.
    "NR-excludes":                  ("rarity_modern", "NR", None),
    "NS-excludes":                  ("rarity_modern", "NS", None),
    # Marine variants - kept distinct via status_detail
    "Marine-NR":                    ("rarity_modern", "NR", "Marine"),
    "Marine-NS":                    ("rarity_modern", "NS", "Marine"),

    # -----------------------------------------------------------------
    # RARITY -- rarity_legacy (pre-2001 systems)
    # -----------------------------------------------------------------
    "Notable":                      ("rarity_legacy", "Notable", None),
    "Notable-A":                    ("rarity_legacy", "Na", None),
    "Notable-B":                    ("rarity_legacy", "Nb", None),

    # -----------------------------------------------------------------
    # SPECIALIST PANELS (non-IUCN)
    # -----------------------------------------------------------------
    "Bird-Red":                     ("bocc", "Red", None),
    "Bird-Amber":                   ("bocc", "Amber", None),
    "Spider-Amber":                 ("specialist_panel", "Amber", "Spider Amber List"),

    # -----------------------------------------------------------------
    # REGIONAL RED LISTS
    # -----------------------------------------------------------------
    "RedList_ENG_post2001-CR":      ("red_list_england", "CR", None),
    "RedList_ENG_post2001-EN":      ("red_list_england", "EN", None),
    "RedList_ENG_post2001-VU":      ("red_list_england", "VU", None),
    "RedList_ENG_post2001-NT":      ("red_list_england", "NT", None),
    "RedList_ENG_post2001-LC":      ("red_list_england", "LC", None),
    "RedList_ENG_post2001-DD":      ("red_list_england", "DD", None),
    "RedList_ENG_post2001-NE":      ("red_list_england", "NE", None),
    "RedList_ENG_post2001-NA":      ("red_list_england", "NA", None),
    "RedList_ENG_post2001-RE":      ("red_list_england", "RE", None),
    "RedList_ENG_post2001-EX":      ("red_list_england", "EX", None),

    "RedList_WAL_post2001-CR":      ("red_list_wales", "CR", None),
    "RedList_WAL_post2001-EN":      ("red_list_wales", "EN", None),
    "RedList_WAL_post2001-VU":      ("red_list_wales", "VU", None),
    "RedList_WAL_post2001-NT":      ("red_list_wales", "NT", None),
    "RedList_WAL_post2001-LC":      ("red_list_wales", "LC", None),
    "RedList_WAL_post2001-DD":      ("red_list_wales", "DD", None),
    "RedList_WAL_post2001-NE":      ("red_list_wales", "NE", None),
    "RedList_WAL_post2001-NA":      ("red_list_wales", "NA", None),
    "RedList_WAL_post2001-RE":      ("red_list_wales", "RE", None),
    "RedList_WAL_post2001-EX":      ("red_list_wales", "EX", None),

    # -----------------------------------------------------------------
    # PRIORITY LISTINGS -- jurisdiction in BOTH status_value and status_detail.
    # status_detail is part of the primary key and part of the collapse key at
    # the status_summary build; leaving it None made all five jurisdictions
    # compete for one slot per species. See patch_priority_detail.py.
    # -----------------------------------------------------------------
    "BAP-2007":                     ("priority", "UK BAP",                     "UK BAP"),
    "England_NERC_S.41":            ("priority", "NERC S.41 England",          "NERC S.41 England"),
    "Env (Wales) Act S7":           ("priority", "Env (Wales) Act S7",         "Env (Wales) Act S7"),
    "Scottish_Biodiversity_List":   ("priority", "Scottish Biodiversity List", "Scottish Biodiversity List"),
    "NI_Priority":                  ("priority", "NI Priority Species",        "NI Priority Species"),

    # -----------------------------------------------------------------
    # LEGAL PROTECTION -- instrument goes in status_detail
    # status_value uniform "Protected"
    # -----------------------------------------------------------------
    # Wildlife and Countryside Act 1981 (GB)
    "WACA-Sch1_part1":                  ("legal_protection", "Protected", "WCA 1981 Sch1 Pt1"),
    "WACA-Sch1_part2":                  ("legal_protection", "Protected", "WCA 1981 Sch1 Pt2"),
    "WACA-Sch5":                        ("legal_protection", "Protected", "WCA 1981 Sch5"),
    "WACA-Sch5_sect9.1(kill/injuring)": ("legal_protection", "Protected", "WCA 1981 Sch5 s9.1 kill/injure"),
    "WACA-Sch5_sect9.1(taking)":        ("legal_protection", "Protected", "WCA 1981 Sch5 s9.1 taking"),
    "WACA-Sch5_sect9.2":                ("legal_protection", "Protected", "WCA 1981 Sch5 s9.2"),
    "WACA-Sch5_sect9.4.a":              ("legal_protection", "Protected", "WCA 1981 Sch5 s9.4a"),
    "WACA-Sch5_sect9.4A":               ("legal_protection", "Protected", "WCA 1981 Sch5 s9.4A"),
    "WACA-Sch5_sect9.4b":               ("legal_protection", "Protected", "WCA 1981 Sch5 s9.4b"),
    "WACA-Sch5Sect9.4c":                ("legal_protection", "Protected", "WCA 1981 Sch5 s9.4c"),
    "WACA-Sch5_sect9.5a":               ("legal_protection", "Protected", "WCA 1981 Sch5 s9.5a"),
    "WACA-Sch8":                        ("legal_protection", "Protected", "WCA 1981 Sch8"),

    # Conservation of Habitats and Species Regulations 2010 (GB/UK)
    "HabReg-Sch2":                      ("legal_protection", "Protected", "Habitats Regs 2010 Sch2"),
    "HabReg-Sch4":                      ("legal_protection", "Protected", "Habitats Regs 2010 Sch4"),
    "HabReg-Sch5":                      ("legal_protection", "Protected", "Habitats Regs 2010 Sch5"),

    # Northern Ireland law
    "W(NI)O-Sch1_part1":                ("legal_protection", "Protected", "NI Wildlife Order 1985 Sch1 Pt1"),
    "W(NI)O-Sch1_part2":                ("legal_protection", "Protected", "NI Wildlife Order 1985 Sch1 Pt2"),
    "W(NI)O-Sch5":                      ("legal_protection", "Protected", "NI Wildlife Order 1985 Sch5"),
    "W(NI)O-Sch8_part1":                ("legal_protection", "Protected", "NI Wildlife Order 1985 Sch8 Pt1"),
    "W(NI)O-Sch8_part2":                ("legal_protection", "Protected", "NI Wildlife Order 1985 Sch8 Pt2"),
    "ConsRegsNI-Sch2":                  ("legal_protection", "Protected", "NI Conservation Regs 1995 Sch2"),
    "ConsRegsNI-Sch3":                  ("legal_protection", "Protected", "NI Conservation Regs 1995 Sch3"),
    "ConsRegsNI-Sch4":                  ("legal_protection", "Protected", "NI Conservation Regs 1995 Sch4"),

    # Badgers
    "ProtOfBadgers1992":                ("legal_protection", "Protected", "Protection of Badgers Act 1992"),

    # EU Habitats Directive
    "HabDir-A2":                        ("legal_protection", "Protected", "Habitats Directive Annex 2"),
    "HabDir-A2*":                       ("legal_protection", "Protected", "Habitats Directive Annex 2 (priority)"),
    "HabDir-A4":                        ("legal_protection", "Protected", "Habitats Directive Annex 4"),
    "HabDir-A5":                        ("legal_protection", "Protected", "Habitats Directive Annex 5"),

    # EU Birds Directive
    "BirdsDir-A1":                      ("legal_protection", "Protected", "Birds Directive Annex 1"),
    "BirdsDir-A2.1":                    ("legal_protection", "Protected", "Birds Directive Annex 2.1"),
    "BirdsDir-A2.2":                    ("legal_protection", "Protected", "Birds Directive Annex 2.2"),

    # Bern Convention
    "Bern-A1":                          ("legal_protection", "Protected", "Bern Convention Appendix 1"),
    "Bern-A2":                          ("legal_protection", "Protected", "Bern Convention Appendix 2"),
    "Bern-A3":                          ("legal_protection", "Protected", "Bern Convention Appendix 3"),

    # Convention on Migratory Species (Bonn) + sub-agreements
    "CMS_A1":                           ("legal_protection", "Protected", "CMS Appendix 1"),
    "CMS_A2":                           ("legal_protection", "Protected", "CMS Appendix 2"),
    "CMS_AEWA-A2":                      ("legal_protection", "Protected", "AEWA Annex 2"),
    "CMS_EUROBATS-A1":                  ("legal_protection", "Protected", "EUROBATS Annex 1"),
    "CMS_ASCOBANS":                     ("legal_protection", "Protected", "ASCOBANS"),

    # CITES
    "ECCITES-A":                        ("legal_protection", "Protected", "EU CITES Annex A"),
    "ECCITES-B":                        ("legal_protection", "Protected", "EU CITES Annex B"),
    "ECCITES-C":                        ("legal_protection", "Protected", "EU CITES Annex C"),
    "ECCITES-D":                        ("legal_protection", "Protected", "EU CITES Annex D"),

    # OSPAR
    "OSPAR":                            ("legal_protection", "Protected", "OSPAR List"),
}


# ============================================================
# Precedence rules for status_summary
# ============================================================
# When a species has multiple designations in the same (track, detail),
# which one wins? Higher number = higher precedence.
#
# Rule of thumb:
#   - Modern assessments trump legacy
#   - IUCN 2001 trumps 1994 trumps pre-1994
#   - More specific detail trumps less specific
#
# For most tracks, each (tvk, track, detail) combination typically has
# one designation anyway. Precedence matters mainly within threat_iucn_legacy
# (1994 vs pre-1994) and rarity_legacy (Na vs Nb vs Notable).
# ============================================================
ABBR_PRIORITY = {
    # Modern IUCN -- highest
    "RedList_GB_post2001":   100,
    "Bird_RedList_GB_post2001": 100,
    "RedList_Global_post2001": 100,
    "RedList_ENG_post2001":  100,
    "RedList_WAL_post2001":  100,

    # 1994 IUCN
    "RedList_GB_post94":      80,
    "RedList_Global_post94":  80,

    # Rarity (modern)
    "NR-includes":            90,
    "NS-includes":            90,
    "NR-excludes":            89,
    "NS-excludes":            89,
    "Marine-NR":              90,
    "Marine-NS":              90,

    # BoCC / specialist
    "Bird-Red":               90,
    "Bird-Amber":             80,
    "Spider-Amber":           80,

    # Pre-1994 RDB
    "RedList_GB_Pre94":       50,

    # Legacy rarity -- specific variants trump generic
    "Notable-A":              40,
    "Notable-B":              40,
    "Notable":                30,
}


def get_desig_priority(abbreviation):
    """Return precedence score for a designation abbreviation."""
    # Try exact match first (handles "Notable" etc)
    if abbreviation in ABBR_PRIORITY:
        return ABBR_PRIORITY[abbreviation]
    # Fall back to prefix match
    for prefix, prio in ABBR_PRIORITY.items():
        if abbreviation.startswith(prefix):
            return prio
    return 10  # default: keep but low priority


# ============================================================
# Build
# ============================================================
def _tvk_translator():
    """old TVK -> current TVK, from the tvk_remap and name_map tables of the current uksi.db
    (written by build_uksi_from_release.py). Without those tables nothing is translated."""
    used = Counter()
    if not os.path.exists(UKSI_PATH):
        return (lambda t: t), used
    u = sqlite3.connect(f"file:{UKSI_PATH}?mode=ro", uri=True)
    try:
        taxa = {r[0] for r in u.execute("SELECT tvk FROM taxa")}
    except sqlite3.OperationalError:
        return (lambda t: t), used
    rem, nmap = {}, {}
    try:
        rem = {a: b for a, b in u.execute("SELECT old_tvk, new_tvk FROM tvk_remap WHERE new_tvk IS NOT NULL")}
    except sqlite3.OperationalError:
        pass
    try:
        nmap = {a: b for a, b in u.execute("SELECT tvk, recommended_tvk FROM name_map")}
    except sqlite3.OperationalError:
        pass
    u.close()

    def tr(t):
        if not t or t in taxa:
            return t
        n = rem.get(t)
        if n and n != t and n in taxa:
            used["tvk_remap"] += 1
            return n
        n = nmap.get(t)
        if n and n != t and n in taxa:
            used["name_map"] += 1
            return n
        return t
    return tr, used


def build_codex():
    now = datetime.now().isoformat()
    TR, TR_USED = _tvk_translator()

    # --------------------------------------------------------
    # 0. Preserve manual entries, reviews, and profiles
    # --------------------------------------------------------
    manual_statuses = []
    manual_sqs = []
    saved_reviews = []
    saved_profiles = []
    if os.path.exists(CODEX_PATH):
        try:
            old = sqlite3.connect(CODEX_PATH)
            oc = old.cursor()
            try:
                oc.execute("""SELECT tvk, species_name, status_track, status_value,
                              status_detail, source_review, date_added, added_by, notes, review_id
                              FROM manual_entries""")
                manual_statuses = oc.fetchall()
            except sqlite3.OperationalError:
                # Older schema without status_detail -- try legacy query
                try:
                    oc.execute("""SELECT tvk, species_name, status_track, status_value,
                                  NULL, source_review, date_added, added_by, notes, NULL
                                  FROM manual_entries""")
                    manual_statuses = oc.fetchall()
                except sqlite3.OperationalError:
                    pass
            try:
                oc.execute("SELECT tvk, sqs FROM sqs_scores WHERE source = 'manual'")
                manual_sqs = oc.fetchall()
            except sqlite3.OperationalError:
                pass
            try:
                try:
                    oc.execute("""SELECT id, review_name, author, taxon_group, status_track,
                                  date_published, date_imported, source_file,
                                  species_count, supersedes_id, notes, licence
                                  FROM reviews ORDER BY id""")
                except sqlite3.OperationalError:
                    # Older schema without licence
                    oc.execute("""SELECT id, review_name, author, taxon_group, status_track,
                                  date_published, date_imported, source_file,
                                  species_count, supersedes_id, notes, NULL
                                  FROM reviews ORDER BY id""")
                saved_reviews = oc.fetchall()
            except sqlite3.OperationalError:
                pass
            try:
                try:
                    oc.execute("""SELECT tvk, review_id, species_name, profile_text, source,
                                  date_added, date_updated, added_by
                                  FROM species_profiles""")
                except sqlite3.OperationalError:
                    # Older schema: one account per TVK, no review link
                    oc.execute("""SELECT tvk, 0, NULL, profile_text, source,
                                  date_added, date_updated, added_by
                                  FROM species_profiles""")
                saved_profiles = oc.fetchall()
            except sqlite3.OperationalError:
                pass
            old.close()
            if manual_statuses:
                print(f"Preserved {len(manual_statuses)} manual entries")
            if manual_sqs:
                print(f"Preserved {len(manual_sqs)} manual SQS scores")
            if saved_reviews:
                print(f"Preserved {len(saved_reviews)} review records")
            if saved_profiles:
                print(f"Preserved {len(saved_profiles)} species profiles")
        except Exception as e:
            print(f"Warning: could not preserve prior data: {e}")
        os.remove(CODEX_PATH)

    # --------------------------------------------------------
    # 1. Create fresh codex.db
    # --------------------------------------------------------
    conn = sqlite3.connect(CODEX_PATH)
    c = conn.cursor()
    c.executescript(SCHEMA)

    # --------------------------------------------------------
    # 2. Import JNCC designations
    # --------------------------------------------------------
    jncc_count = 0
    if os.path.exists(JNCC_XLSX):
        print(f"Reading JNCC: {JNCC_XLSX}")
        try:
            import openpyxl
        except ImportError:
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install",
                                   "openpyxl", "--break-system-packages"])
            import openpyxl

        wb = openpyxl.load_workbook(JNCC_XLSX, read_only=True, data_only=True)
        ws = wb["Master List"]

        headers = []
        for row in ws.iter_rows(min_row=2, max_row=2, values_only=True):
            headers = [str(v).strip() if v else f"col_{i}" for i, v in enumerate(row)]
            break
        ci = {h: i for i, h in enumerate(headers)}

        def cell(row, col_name):
            idx = ci.get(col_name)
            if idx is None:
                return ""
            v = row[idx]
            return str(v).strip() if v and str(v).strip() != "None" else ""

        rows_to_insert = []
        for row in ws.iter_rows(min_row=3, values_only=True):
            tvk = cell(row, "Recommended taxon version")
            if not tvk:
                continue
            tvk = TR(tvk)                    # JNCC's TVK -> current UKSI taxon (no-op without tvk_remap)
            rows_to_insert.append((
                tvk,
                cell(row, "Recommended taxon name"),
                cell(row, "Common name"),
                cell(row, "Taxon group"),
                cell(row, "Category"),              # NEW: persist broad category
                cell(row, "Reporting category"),
                cell(row, "Designation"),
                cell(row, "Designation abbreviation"),
                cell(row, "designation description"),
                cell(row, "Source"),
                cell(row, "Source description"),
                cell(row, "Date designated"),
                cell(row, "IUCN version"),
                cell(row, "Criteria description"),
                cell(row, "Comments"),
                "jncc",
            ))

        c.executemany("""INSERT INTO designations
            (tvk, species_name, common_name, taxon_group, category,
             reporting_category, designation, designation_abbreviation,
             designation_description, source, source_description,
             date_designated, iucn_version, criteria_description,
             comments, origin)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows_to_insert)

        jncc_count = len(rows_to_insert)
        wb.close()

        c.execute("SELECT COUNT(DISTINCT tvk) FROM designations WHERE origin = 'jncc'")
        jncc_species = c.fetchone()[0]

        # Show category breakdown
        c.execute("""SELECT category, COUNT(DISTINCT tvk) FROM designations
                     WHERE origin = 'jncc' GROUP BY category
                     ORDER BY COUNT(DISTINCT tvk) DESC""")
        cat_breakdown = c.fetchall()

        print(f"  {jncc_count:,} designation rows for {jncc_species:,} species "
              f"(all taxonomic groups)")
        print(f"  Category breakdown:")
        for cat, n in cat_breakdown:
            print(f"    {(cat or '(uncategorised)'):30s}  {n:>5,}")
    else:
        print(f"WARNING: JNCC spreadsheet not found at {JNCC_XLSX}")

    # --------------------------------------------------------
    # 3. Build status_summary
    # --------------------------------------------------------
    print("\nBuilding status summary...")
    c.execute("SELECT DISTINCT tvk FROM designations")
    all_tvks = [r[0] for r in c.fetchall()]

    summary_rows = []
    unrouted_counter = Counter()

    for tvk in all_tvks:
        c.execute("""SELECT designation_abbreviation, source, iucn_version,
                            date_designated, origin
                     FROM designations WHERE tvk = ?""", (tvk,))
        # best[(track, detail)] = (value, abbr, source, iucn_ver, date_d, origin, priority)
        # Winner = highest priority, then latest date_designated. Precedence must
        # come first: Notable-B (40) must still beat the generic Notable (30) even
        # though the generic review is newer. See patch_status_tiebreak.py.
        best = {}
        for abbr, source, iucn_ver, date_d, origin in c.fetchall():
            mapping = DESIG_TO_TRACK.get(abbr)
            if not mapping:
                unrouted_counter[abbr] += 1
                continue
            track, value, detail = mapping
            prio = get_desig_priority(abbr)
            key = (track, detail or "")
            if (key not in best
                    or (prio, date_d or "") > (best[key][6], best[key][4] or "")):
                best[key] = (value, abbr, source, iucn_ver, date_d, origin, prio)

        for (track, detail), (value, abbr, source, iucn_ver, date_d, origin, _) in best.items():
            summary_rows.append((
                tvk, track, value, detail or None, source, iucn_ver, date_d, origin
            ))

    c.executemany("""INSERT OR REPLACE INTO status_summary
        (tvk, status_track, status_value, status_detail, source,
         iucn_version, date_designated, origin)
        VALUES (?,?,?,?,?,?,?,?)""", summary_rows)

    print(f"  {len(summary_rows):,} entries across {len(all_tvks):,} species")
    track_counts = Counter(row[1] for row in summary_rows)
    for track, cnt in track_counts.most_common():
        print(f"    {track:25s}  {cnt:>5,}")

    if unrouted_counter:
        total_unrouted = sum(unrouted_counter.values())
        print(f"\n  Unrouted: {total_unrouted:,} rows across "
              f"{len(unrouted_counter)} distinct codes")
        print(f"  (top 10 unrouted codes:)")
        for abbr, n in unrouted_counter.most_common(10):
            print(f"    {n:>5,}  {abbr}")

    # --------------------------------------------------------
    # 4. Build TVK bridge (Pantheon -> UKSI)
    # --------------------------------------------------------
    bridge_count = 0
    if os.path.exists(PANTHEON_PATH) and os.path.exists(UKSI_PATH):
        print(f"\nBuilding TVK bridge...")
        uksi = sqlite3.connect(UKSI_PATH)
        pan = sqlite3.connect(PANTHEON_PATH)
        uc = uksi.cursor()
        pc = pan.cursor()

        uc.execute("SELECT tvk FROM taxa")
        uksi_tvk_set = set(r[0] for r in uc.fetchall())

        uc.execute("SELECT scientific_name, tvk FROM taxa WHERE rank = 'Species'")
        uksi_name_tvk = {r[0].lower(): r[1] for r in uc.fetchall()}

        # Synonym index: Pantheon's names are 2017-era, so most bridge
        # failures are species since renamed or moved genus. uksi.synonyms
        # is name-based (synonym string -> current tvk). A synonym that maps
        # to more than one current species is NOT used: until 8 Oct 2026 the
        # first one met was kept (setdefault), which sent Aphodius pusillus to
        # Agrilinus ater (fault F25). Those are left to the NAMES-by-key pass
        # below, or reported.
        uksi_syn_targets = {}
        try:
            uc.execute("SELECT synonym, tvk FROM synonyms")
            for _syn, _tvk in uc.fetchall():
                if _syn:
                    uksi_syn_targets.setdefault(_syn.lower(), set()).add(_tvk)
        except sqlite3.OperationalError:
            print("  ! uksi.synonyms unavailable -- synonym pass skipped")
        uksi_syn_tvk = {s: next(iter(t)) for s, t in uksi_syn_targets.items() if len(t) == 1}
        syn_ambiguous_names = {s for s, t in uksi_syn_targets.items() if len(t) > 1}

        # NAMES-sheet mapping BY KEY (8 Oct 2026, fault F25 / backlog F14).
        # Every Pantheon TVK is a UKSI name key; uksi.name_map (the July 2025
        # NAMES sheet) says which current taxon THAT key belongs to. This is the
        # authority, and it decides by key, not by name -- so it also catches
        # British misapplied names that an exact-name match gets wrong (Pantheon's
        # Noctua janthina -> N. janthe, Polistes gallicus -> P. dominula).
        # f14_bridge_vs_namemap_20261008.py measured 104 rows where the old
        # bridge disagreed with it.
        nm_rec = {}
        tv_remap = {}
        try:
            uc.execute("SELECT tvk, recommended_tvk FROM name_map")
            nm_rec = {r[0]: r[1] for r in uc.fetchall()}
            uc.execute("SELECT old_tvk, new_tvk FROM tvk_remap WHERE new_tvk IS NOT NULL")
            tv_remap = {r[0]: r[1] for r in uc.fetchall()}
        except sqlite3.OperationalError:
            print("  ! uksi.name_map / tvk_remap unavailable -- NAMES-by-key pass skipped")
        uc.execute("SELECT tvk, scientific_name, parent_tvk FROM taxa")
        uksi_taxon = {r[0]: (r[1] or "", r[2]) for r in uc.fetchall()}

        def _names_current(tvk, depth=0):
            """Current taxon the NAMES sheet gives for this key, or None."""
            if tvk in uksi_tvk_set:
                return tvk
            if tvk in tv_remap and tv_remap[tvk] in uksi_tvk_set:
                return tv_remap[tvk]
            if depth < 5 and nm_rec.get(tvk) and nm_rec[tvk] != tvk:
                return _names_current(nm_rec[tvk], depth + 1)
            return None

        # Where NAMES gives a coarser concept (aggregate, "a/b", genus) and the
        # Pantheon name is itself a current species, the species is kept: records
        # are made at species level, so the aggregate would take the data away
        # from them (Gammarus pulex, the Meromyza species). Where NAMES gives a
        # finer one (subspecies, form) with no exact species, its parent is used.
        _COARSE = ("agg.", "/")
        _FINER = (" subsp. ", " form ", " var. ")

        # Kept on the old bridge by judgement (8 Oct 2026): NAMES maps these keys
        # to a different valid British species. Review if the UKSI changes.
        BRIDGE_KEEP = {
            "NHMSYS0001720332",   # Tasgius globulifer   (NAMES: T. melanarius)
            "NBNSYS0000009514",   # Ectemnius rubicola   (NAMES: E. ruficornis)
            "NHMSYS0001701438",   # Hydrobia ventrosa    (NAMES: H. acuta neglecta; kept: Ecrobia ventrosa)
            "NBNSYS0000010106",   # Cimex dissimilis     (NAMES: C. columbarius; kept: C. pipistrelli)
        }
        _keep_old_syn = {"NHMSYS0001701438", "NBNSYS0000010106"}   # previously reached by synonym

        pc.execute("SELECT tvk, species_name FROM species")
        pan_species = pc.fetchall()

        bridge_rows = []
        direct_match = 0
        name_match = 0
        names_key = 0
        names_changed = []     # (pantheon name, exact-name target, NAMES target)
        kept_coarse = 0
        kept_by_judgement = 0
        unmatched = 0

        for pan_tvk, pan_name in pan_species:
            if pan_tvk in uksi_tvk_set:
                bridge_rows.append((pan_tvk, pan_tvk, pan_name, "direct"))
                direct_match += 1
                continue
            exact = uksi_name_tvk.get((pan_name or "").lower())
            target = None
            if pan_tvk in BRIDGE_KEEP:
                kept_by_judgement += 1
                if pan_tvk in _keep_old_syn:
                    unmatched += 1      # the synonym pass takes it back off
                    continue            # left for the synonym pass, as before
                target = exact
            else:
                nmt = _names_current(pan_tvk) if nm_rec else None
                if nmt:
                    nm_name = uksi_taxon.get(nmt, ("", None))[0]
                    coarse = any(x in nm_name for x in _COARSE) or " " not in nm_name.strip()
                    finer = any(x in f" {nm_name} " for x in _FINER)
                    if coarse and exact:
                        target = exact
                        kept_coarse += 1
                    elif finer and exact:
                        target = exact
                        kept_coarse += 1
                    elif finer and uksi_taxon.get(nmt, ("", None))[1] in uksi_tvk_set:
                        target = uksi_taxon[nmt][1]
                        names_key += 1
                    else:
                        target = nmt
                        names_key += 1
                        if exact and exact != nmt:
                            names_changed.append((pan_name, exact, nmt))
                else:
                    target = exact
            if target:
                bridge_rows.append((pan_tvk, target, pan_name, "name"))   # 'name': the label every reader uses
                name_match += 1
            else:
                unmatched += 1

        # Third pass -- synonym resolution for what the first two missed.
        #
        # Collisions ARE bridged (J2, Session 32). Where UKSI has merged two
        # Pantheon taxa into one current species, both are mapped to it and the
        # merge happens at read time: PantheonRepository unions the ecology and
        # keeps the highest SQS. Excluding them lost habitat data for 89 species
        # that nothing else could reach, and a higher SQS for 85.
        #
        # The SQS import below must keep the highest score per species, not the
        # last one written, or this reintroduces the arbitrary overwrite the
        # exclusion was there to prevent.
        syn_match = 0
        syn_collision = 0
        syn_skipped_ambiguous = []
        # Pantheon taxa that landed on a species another taxon already claimed.
        # Their SQS must not displace the incumbent's -- see the merge rule in
        # patch_j2_incumbent_wins.py.
        collider_pan_tvks = set()
        claimed = {r[1] for r in bridge_rows}
        resolved_pan = {r[0] for r in bridge_rows}
        for pan_tvk, pan_name in pan_species:
            if pan_tvk in resolved_pan or not pan_name:
                continue
            if pan_name.lower() in syn_ambiguous_names and pan_tvk not in BRIDGE_KEEP:
                syn_skipped_ambiguous.append(pan_name)
                continue
            new_tvk = uksi_syn_tvk.get(pan_name.lower())
            if not new_tvk and pan_tvk in BRIDGE_KEEP:
                # kept by judgement: the previous first-met target, made explicit
                new_tvk = sorted(uksi_syn_targets.get(pan_name.lower(), ()))[:1]
                new_tvk = new_tvk[0] if new_tvk else None
            if not new_tvk:
                continue
            if new_tvk in claimed:
                syn_collision += 1      # counted, and now also bridged
                collider_pan_tvks.add(pan_tvk)
            bridge_rows.append((pan_tvk, new_tvk, pan_name, "name"))
            claimed.add(new_tvk)
            syn_match += 1
            unmatched -= 1

        # J2 incumbent rule for EVERY merge, however it was found (8 Oct 2026).
        # Where several Pantheon taxa land on one current species, the incumbent
        # is the one whose own TVK -- else whose exact name -- is that species;
        # the rest are colliders, whose SQS is used only where the incumbent has
        # none. Before this, merges found by the NAMES-key pass escaped the rule:
        # Anthonomus humeralis's 4 displaced A. pomorum's own 1 (Badshot Lea +2).
        _by_target = {}
        for _pt, _ut, _nm, _mm in bridge_rows:
            _by_target.setdefault(_ut, []).append((_pt, (_nm or "").lower()))
        _added = 0
        for _ut, _members in _by_target.items():
            if len(_members) < 2:
                continue
            _inc = [pt for pt, nm in _members if pt == _ut] or \
                   [pt for pt, nm in _members if nm == uksi_taxon.get(_ut, ("", None))[0].lower()]
            if not _inc:
                continue                  # no clear incumbent: earlier rule stands
            for pt, nm in _members:
                if pt != _inc[0] and pt not in collider_pan_tvks:
                    collider_pan_tvks.add(pt)
                    _added += 1
        if _added:
            print(f"  Merges by NAMES key treated as colliders (incumbent's SQS kept): {_added:,}")

        c.executemany("INSERT OR REPLACE INTO tvk_bridge VALUES (?,?,?,?)", bridge_rows)
        bridge_count = len(bridge_rows)
        # Carried to the SQS import below.
        globals()["_COLLIDER_PAN_TVKS"] = collider_pan_tvks

        print(f"  Direct TVK match: {direct_match:,}")
        print(f"  Name-resolved:    {name_match:,}"
              f"  (by NAMES key {names_key:,}; species kept over a coarser NAMES concept {kept_coarse:,};"
              f" kept by judgement {kept_by_judgement:,})")
        print(f"  NAMES key overruled an exact-name match: {len(names_changed):,}")
        for _a, _b, _c in sorted(names_changed)[:40]:
            print(f"      {_a[:32]:32} -> {uksi_taxon.get(_c, (_c,))[0][:32]}  (not {uksi_taxon.get(_b, (_b,))[0][:32]})")
        if syn_skipped_ambiguous:
            print(f"  Not bridged -- name maps to several species and NAMES has no key: "
                  f"{len(syn_skipped_ambiguous):,} {sorted(syn_skipped_ambiguous)[:10]}")
        print(f"  Synonym-resolved: {syn_match:,}")
        print(f"  Unmatched:        {unmatched:,}")
        if syn_collision:
            print(f"  of which merged taxa:             {syn_collision:,}"
                  f"  -- two Pantheon taxa in one current species;"
                  f" ecology unioned, incumbent SQS kept")
        print(f"  Bridge total:     {bridge_count:,}")

        pan.close()
        uksi.close()

    # --------------------------------------------------------
    # 5. Import SQS scores (re-keyed via bridge)
    # --------------------------------------------------------
    sqs_count = 0
    sqs_rekeyed = 0
    sqs_dropped_zero = 0
    sqs_dropped_noninvert = 0
    if os.path.exists(PANTHEON_PATH):
        print(f"\nImporting SQS from {PANTHEON_PATH}")

        c.execute("SELECT pantheon_tvk, uksi_tvk FROM tvk_bridge")
        bridge = {r[0]: r[1] for r in c.fetchall()}

        # Build invertebrate TVK set so we can filter Pantheon TVK collisions.
        # Pantheon stores SQS keyed by historic TVKs; some of those TVKs now
        # refer to plants/birds/fungi in current UKSI. Only import scores for
        # species that Codex classifies as invertebrate.
        c.execute("""
            SELECT DISTINCT tvk FROM designations WHERE category = 'Invertebrate'
        """)
        invert_tvks = {r[0] for r in c.fetchall()}
        # Designations alone miss every common species (no designation, so not
        # "invertebrate"), and their Pantheon SQS 1 was dropped -- 4,085 scores,
        # inflating every SQI. Add UKSI's own taxonomy: Animalia outside Chordata.
        # Genuine collisions (a historic TVK now naming a plant/bird/fungus) still fail.
        _n_desig = len(invert_tvks)
        try:
            import paths as _paths
            _u = sqlite3.connect(f"file:{_paths.UKSI_DB}?mode=ro", uri=True)
            invert_tvks |= {r[0] for r in _u.execute(
                "SELECT tvk FROM taxa WHERE LOWER(COALESCE(kingdom,'')) = 'animalia' "
                "AND LOWER(COALESCE(phylum,'')) != 'chordata'")}
            _u.close()
        except Exception as _e:
            print(f"  WARNING: UKSI taxonomy unavailable ({_e}); invertebrate set from designations only")
        print(f"  Invertebrate TVKs: {_n_desig:,} from designations, "
              f"{len(invert_tvks):,} with UKSI taxonomy")

        pan = sqlite3.connect(PANTHEON_PATH)
        pc = pan.cursor()
        # Only meaningful (non-zero) SQS values from Pantheon; zero-SQS rows
        # mean "we know this species but don't award a score" (often non-natives)
        pc.execute("SELECT tvk, sqs FROM sqs_scores WHERE sqs > 0")

        sqs_rows = []
        # Several Pantheon taxa can map to one current species (J2). The
        # INCUMBENT wins -- the taxon bridged by the direct or name pass, whose
        # TVK or name matches the current species. A collider's score is used
        # only where the incumbent has none.
        #
        # NOT the highest score: the sunk taxon usually carries the higher one
        # because it was a scarce segregate, so taking the maximum inflates the
        # merged species. Sympetrum striolatum (Common Darter, one of the
        # commonest British dragonflies) went 1 -> 4 by inheriting the score of
        # S. nigrescens, the Highland Darter form sunk into it.
        colliders = globals().get("_COLLIDER_PAN_TVKS", set())
        best_sqs = {}
        sqs_merged = 0
        rows_raw = pc.fetchall()
        # Incumbents first, then colliders, so setdefault gives the incumbent.
        for is_collider in (False, True):
            for pan_tvk, sqs in rows_raw:
                if (pan_tvk in colliders) != is_collider:
                    continue
                uksi_tvk = bridge.get(pan_tvk, pan_tvk)
                if not is_collider and uksi_tvk != pan_tvk:
                    sqs_rekeyed += 1
                if uksi_tvk not in invert_tvks:
                    if not is_collider:
                        sqs_dropped_noninvert += 1
                    continue
                if uksi_tvk in best_sqs:
                    sqs_merged += 1
                else:
                    best_sqs[uksi_tvk] = sqs
        sqs_rows = [(t, s, "pantheon") for t, s in best_sqs.items()]

        # Also count what we filtered as zero-SQS in Pantheon
        sqs_dropped_zero = pc.execute(
            "SELECT COUNT(*) FROM sqs_scores WHERE sqs = 0"
        ).fetchone()[0]

        pan.close()

        c.executemany("INSERT OR REPLACE INTO sqs_scores VALUES (?,?,?)", sqs_rows)
        sqs_count = len(sqs_rows)
        print(f"  {sqs_count:,} SQS scores ({sqs_rekeyed:,} re-keyed via bridge)")
        if sqs_merged:
            print(f"  {sqs_merged:,} merged onto an existing species "
                  f"(incumbent's score kept)")
        if sqs_dropped_zero or sqs_dropped_noninvert:
            print(f"  Filtered: {sqs_dropped_zero:,} zero-SQS, "
                  f"{sqs_dropped_noninvert:,} non-invertebrate TVK collisions")

    # --------------------------------------------------------
    # 6. Restore preserved data (manual entries, reviews, profiles)
    # --------------------------------------------------------
    manual_statuses = [(TR(r[0]),) + tuple(r[1:]) for r in manual_statuses]
    manual_sqs = [(TR(r[0]), r[1]) for r in manual_sqs]
    if saved_profiles:
        _seen, _kept, _dropped = set(), [], []
        for r in saved_profiles:
            r = (TR(r[0]),) + tuple(r[1:])
            if (r[0], r[1]) in _seen:
                _dropped.append(r)
            else:
                _seen.add((r[0], r[1])); _kept.append(r)
        saved_profiles = _kept
        if _dropped:
            print(f"\n  ! {len(_dropped)} account(s) landed on a species that already has an account "
                  f"from the same review -- first kept, these not restored:")
            for r in _dropped:
                print(f"      review #{r[1]}  {r[2] or '?'}  -> {r[0]}")
    if TR_USED:
        print(f"\n  TVKs translated to current UKSI taxa: {dict(TR_USED)}")
    if manual_statuses:
        # manual_statuses tuple: (tvk, species_name, track, value, detail,
        #                         source_review, date_added, added_by, notes, review_id)
        c.executemany("""INSERT INTO manual_entries
            (tvk, species_name, status_track, status_value, status_detail,
             source_review, date_added, added_by, notes, review_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", manual_statuses)
        # Apply to status_summary, oldest first so a later review wins.
        #
        # DELETE then INSERT -- never INSERT OR REPLACE. SQLite treats NULL as
        # distinct inside a composite primary key, so REPLACE with a NULL
        # status_detail ADDS a row beside the JNCC one instead of replacing it,
        # leaving the old status and the new side by side.
        #
        # A value of 'none' records a status the review REMOVED (a downgrade):
        # delete, insert nothing. See patch_codex_manual_apply.py.
        for row in sorted(manual_statuses, key=lambda r: r[6] or ""):
            tvk, name, track, value, detail, source, date_added, by, notes, rid = row
            c.execute("""DELETE FROM status_summary
                         WHERE tvk = ? AND status_track = ?
                           AND COALESCE(status_detail, '') = COALESCE(?, '')""",
                      (tvk, track, detail))
            if (value or "").strip().lower() == "none":
                continue
            c.execute("""INSERT INTO status_summary
                (tvk, status_track, status_value, status_detail,
                 source, iucn_version, date_designated, origin)
                VALUES (?, ?, ?, ?, ?, NULL, ?, 'manual')""",
                (tvk, track, value, detail, source or "manual", date_added))
        print(f"\nRestored {len(manual_statuses)} manual entries")

    if manual_sqs:
        for tvk, sqs in manual_sqs:
            c.execute("INSERT OR REPLACE INTO sqs_scores VALUES (?, ?, 'manual')",
                      (tvk, sqs))
        print(f"Restored {len(manual_sqs)} manual SQS scores")

    if saved_reviews:
        # id restored explicitly: manual_entries.review_id, supersedes_id and
        # species_profiles.review_id all point at it, so it must not be renumbered.
        c.executemany("""INSERT INTO reviews
            (id, review_name, author, taxon_group, status_track,
             date_published, date_imported, source_file,
             species_count, supersedes_id, notes, licence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", saved_reviews)
        print(f"Restored {len(saved_reviews)} review records")

    profiles_count = 0
    if saved_profiles:
        c.executemany("""INSERT INTO species_profiles
            (tvk, review_id, species_name, profile_text, source,
             date_added, date_updated, added_by)
            VALUES (?,?,?,?,?,?,?,?)""", saved_profiles)
        profiles_count = len(saved_profiles)
        print(f"Restored {profiles_count} species profiles")

    # --------------------------------------------------------
    # 7. Metadata + log
    # --------------------------------------------------------
    c.executemany("INSERT OR REPLACE INTO metadata VALUES (?,?)", [
        ("version", "5.0"),
        ("build_date", now),
        ("jncc_source", JNCC_XLSX if os.path.exists(JNCC_XLSX) else "not found"),
        ("jncc_date", "2023-12-06"),
        ("pantheon_source", PANTHEON_PATH if os.path.exists(PANTHEON_PATH) else "not found"),
        ("schema_version", "5"),
        ("bridge_species", str(bridge_count)),
    ])

    c.execute("""INSERT INTO build_log
                 (timestamp, jncc_rows, pantheon_sqs, manual_entries,
                  bridge_resolved, profiles_count, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (now, jncc_count, sqs_count, len(manual_statuses),
               bridge_count, profiles_count,
               f"JNCC {os.path.basename(JNCC_XLSX)}, Pantheon v3.7.4, 11-track scheme"))

    conn.commit()

    # --------------------------------------------------------
    # 8. Summary
    # --------------------------------------------------------
    c.execute("SELECT COUNT(DISTINCT tvk) FROM designations")
    total_species = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM sqs_scores")
    total_sqs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM manual_entries")
    total_manual = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM species_profiles")
    total_profiles = c.fetchone()[0]
    db_size = os.path.getsize(CODEX_PATH)

    print(f"\n{'='*60}")
    print(f"CODEX.DB v5 BUILT")
    print(f"{'='*60}")
    print(f"  Location:   {CODEX_PATH}")
    print(f"  Size:       {db_size:,} bytes ({db_size//1024} KB)")
    print(f"  Species:    {total_species:,} (all taxonomic groups)")
    print(f"  SQS:        {total_sqs:,} ({sqs_rekeyed:,} re-keyed)")
    print(f"  Bridge:     {bridge_count:,} mappings")
    print(f"  Manual:     {total_manual}")
    print(f"  Profiles:   {total_profiles}")

    # --------------------------------------------------------
    # 9. Verification
    # --------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"VERIFICATION")
    print(f"{'='*60}")

    test_species = {
        "NHMSYS0000876200": "Lasioglossum pauxillum",
        "NHMSYS0000876203": "Lasioglossum puncticolle",
        "NHMSYS0000876116": "Hylaeus signatus",
        "NHMSYS0000875273": "Andrena similis",
        "NBNSYS0000149897": "Larinus carlinae",
        "NHMSYS0000519083": "Coenonympha pamphilus",
        "NHMSYS0000503020": "Lasiommata megera",
        "NHMSYS0001387336": "Forficula lesnei",
        "NHMSYS0020309273": "Graptopeltus lynceus",
        "NHMSYS0000876577": "Philanthus triangulum",
        # Species that should now work under the new track scheme:
        # (a bird, a plant, a mammal -- if the mappings are right)
        "NHMSYS0000530120": "Accipiter nisus (bird)",
    }

    found = 0
    for tvk, name in test_species.items():
        c.execute("""SELECT status_track, status_value, status_detail, origin
                     FROM status_summary WHERE tvk = ?""", (tvk,))
        rows = c.fetchall()
        c.execute("SELECT sqs, source FROM sqs_scores WHERE tvk = ?", (tvk,))
        sqs_row = c.fetchone()
        sqs_s = f"SQS:{sqs_row[0]}({sqs_row[1][:3]})" if sqs_row else "no SQS"

        if rows:
            found += 1
            flags = []
            for t, v, d, o in rows:
                if d:
                    flags.append(f"{t}={v}/{d}")
                else:
                    flags.append(f"{t}={v}")
            print(f"  + {name:40s}  {sqs_s:15s}  {'; '.join(flags[:3])}"
                  + (f" (+{len(flags)-3} more)" if len(flags) > 3 else ""))
        else:
            print(f"  - {name:40s}  {sqs_s:15s}  MISSING")

    print(f"  Resolved: {found}/{len(test_species)}")

    conn.close()
    print("Done.")


def show_stats():
    if not os.path.exists(CODEX_PATH):
        print(f"codex.db not found at {CODEX_PATH}")
        return
    conn = sqlite3.connect(CODEX_PATH)
    c = conn.cursor()

    c.execute("SELECT key, value FROM metadata ORDER BY key")
    print("Metadata:")
    for k, v in c.fetchall():
        print(f"  {k}: {v}")

    c.execute("SELECT COUNT(DISTINCT tvk) FROM designations")
    print(f"\nSpecies: {c.fetchone()[0]:,}")
    c.execute("SELECT COUNT(*) FROM sqs_scores")
    print(f"SQS scores: {c.fetchone()[0]:,}")
    c.execute("SELECT COUNT(*) FROM tvk_bridge")
    print(f"Bridge mappings: {c.fetchone()[0]:,}")
    c.execute("SELECT COUNT(*) FROM manual_entries")
    print(f"Manual entries: {c.fetchone()[0]:,}")
    c.execute("SELECT COUNT(*) FROM species_profiles")
    print(f"Species profiles: {c.fetchone()[0]:,}")

    try:
        c.execute("SELECT COUNT(*) FROM reviews")
        print(f"Reviews: {c.fetchone()[0]:,}")
        c.execute("""SELECT id, review_name, author, species_count
                     FROM reviews ORDER BY id""")
        rows = c.fetchall()
        if rows:
            print("\nRegistered reviews:")
            for rid, name, author, cnt in rows:
                print(f"  #{rid}: {name} ({author}) -- {cnt or 0} species")
    except sqlite3.OperationalError:
        pass

    c.execute("SELECT match_method, COUNT(*) FROM tvk_bridge GROUP BY match_method")
    print("\nBridge by method:")
    for m, cnt in c.fetchall():
        print(f"  {m:15s}  {cnt:>6,}")

    c.execute("""SELECT status_track, COUNT(*) FROM status_summary
                 GROUP BY status_track ORDER BY COUNT(*) DESC""")
    print("\nStatus summary by track:")
    for t, cnt in c.fetchall():
        print(f"  {t:25s}  {cnt:>5,}")

    # Category breakdown from designations
    c.execute("""SELECT category, COUNT(DISTINCT tvk) FROM designations
                 GROUP BY category ORDER BY COUNT(DISTINCT tvk) DESC""")
    print("\nSpecies by category:")
    for cat, n in c.fetchall():
        print(f"  {(cat or '(uncategorised)'):30s}  {n:>5,}")

    conn.close()


if __name__ == "__main__":
    if "--stats" in sys.argv:
        show_stats()
    else:
        build_codex()
