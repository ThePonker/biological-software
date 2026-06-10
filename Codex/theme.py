"""Codex Manager theme — conservation authority aesthetic."""

# Codex accent: deep forest green with gold highlights
ACCENT = "#2d5016"
ACCENT_LIGHT = "#e8f0e4"
ACCENT_DARK = "#1a3a0a"
GOLD = "#8b7535"
GOLD_LIGHT = "#f5f0e0"

SURFACE = "#faf9f7"
SURFACE_ALT = "#f0eeea"
BORDER = "#d4d0c8"
SEPARATOR = "#e0ddd6"
TEXT_PRIMARY = "#2c2c2c"
TEXT_SECONDARY = "#6b6560"
TEXT_HEADING = "#3d3832"
HOVER = "#f0eeea"
RADIUS_SM = "4px"
RADIUS_MD = "6px"

# Status category colours
CAT_COLOURS = {
    "RE": "#1a1a1a",
    "CR": "#d32f2f",
    "EN": "#e65100",
    "VU": "#f9a825",
    "NT": "#7cb342",
    "DD": "#78909c",
    "LC": "#4caf50",
    "NA": "#bdbdbd",
    "NE": "#e0e0e0",
    "NR": "#c62828",
    "NS": "#ef6c00",
}


def status_colour(value: str) -> str:
    """Get a colour for a status value."""
    return CAT_COLOURS.get(value.upper(), TEXT_SECONDARY)


def format_date(date_str: str) -> str:
    """Convert YYYY-MM-DD or ISO date to dd/mm/yyyy."""
    if not date_str:
        return ""
    try:
        # Handle ISO format with time
        clean = date_str[:10]
        parts = clean.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except (IndexError, ValueError):
        pass
    return date_str
