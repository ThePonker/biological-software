"""Codex Manager theme: names resolved from Observatum's Naturalist theme."""
from shared.theme_lookup import value as _g


# Codex takes the suite's shared palette (R13, 24 Oct 2026): Moss Green is its accent.
ACCENT = _g("primary", "#4a7c59")
ACCENT_LIGHT = _g("primary_bg", "#e8f0eb")
ACCENT_DARK = _g("primary_dark", "#2f5a3b")
GOLD = _g("accent_collection", "#b8860b")
GOLD_LIGHT = _g("accent_collection_light", "#faf6eb")

SURFACE = _g("surface", "#ffffff")
SURFACE_ALT = _g("surface_alt", "#f9fafb")
BORDER = _g("border", "#d1d5db")
SEPARATOR = _g("separator", "#e5e7eb")
TEXT_PRIMARY = _g("text_primary", "#1f2937")
TEXT_SECONDARY = _g("text_secondary", "#6b7280")
TEXT_HEADING = _g("text_heading", "#4b5563")
HOVER = _g("hover", "#e5e7eb")
RADIUS_SM = _g("radius_sm", "4px")
RADIUS_MD = _g("radius_md", "6px")

# State colours (error text, key-species badges)
DANGER = _g("danger", "#a63d40")
WARNING = _g("warning", "#d97706")
SUCCESS = _g("success", "#4a7c59")

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
