"""The entry grid's columns and the constants about them: one home (split from entry_grid.py, R13)."""

# (key, header, kind, width). Default order per Wil: Species, No., Sex, Stage, then context.
COLUMNS = [
    ("species_name", "Species", "species", 200),
    ("quantity", "No.", "number", 52),
    ("sex", "Sex", "sex", 78),
    ("stage", "Stage", "stage", 90),
    ("grid_ref", "Grid ref", "text", 95),
    ("method", "Method", "method", 120),
    ("date", "Date", "text", 100),
    ("sub_location", "Sub-location", "text", 120),
    ("trap_number", "Trap", "text", 70),
    ("visit_number", "Visit", "text", 60),
    ("comment", "Comment", "text", 100),
    ("check_flag", "Check", "check", 70),          # "not determined yet" (see check_export.py)
    ("check_note", "Check note", "text", 140),
    ("vc_number", "VC No.", "number", 60),
    ("vice_county", "VC", "text", 60),
    ("recorder", "Recorder", "text", 110),
    ("determiner", "Determiner", "text", 110),
    ("common_name", "Common Name", "text", 120),
    ("order_name", "Order", "text", 110),
    ("family", "Family", "text", 130),
    ("site_name", "Site", "text", 100),
]

COLIDX = {key: i for i, (key, _, _, _) in enumerate(COLUMNS)}
CHECK_HINT = "Run scripts\\add_staging_check_columns.py once"
# what typed or pasted into the Check cell marks a row (anything else clears it)
CHECK_YES = ("1", "x", "yes", "y", "t", "true", "to check", "check")
LAST_ROW_KEY = "DataEntry/lastRow/{}"       # per job: the staging row id last inserted or edited

# the plain CSV export is unchanged: it does not carry the To check columns
_CSV_COLUMNS = [c for c in COLUMNS if not c[0].startswith("check_")]

DEFAULT_DISPLAY_ROWS = 1000  # blank rows shown when a job opens (spreadsheet-style canvas)
