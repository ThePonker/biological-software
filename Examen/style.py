"""Examen's colours: one source, Observatum's Naturalist theme (R13, 24 Oct 2026).

Every Examen module takes its palette names from here. They resolve from
src.themes.theme() (Observatum is put on the path if the launcher did not), with the
theme's own values as the fallback if it cannot be imported.
"""
from shared.theme_lookup import value as _g


BG = _g("background", "#f5f5f4")
SURFACE = _g("surface", "#ffffff")
TEXT_PRIMARY = _g("text_primary", "#1f2937")
TEXT_HEADING = _g("text_heading", "#4b5563")
TEXT_SECONDARY = _g("text_secondary", "#6b7280")
TEXT_MUTED = _g("text_muted", "#9ca3af")
BORDER = _g("border", "#d1d5db")
SEPARATOR = _g("separator", "#e5e7eb")

ACCENT = _g("accent_scheme", "#7c6c9f")              # Examen's dusty purple
ACCENT_LIGHT = _g("accent_scheme_light", "#eeeaf3")
ACCENT_DARK = _g("accent_scheme_dark", "#5c4f7a")

MOSS_GREEN = _g("primary", "#4a7c59")
MOSS_HOVER = _g("primary_hover", "#3d6649")
WARM_GRAY = _g("secondary", "#8b8178")
RED_STATUS = _g("danger", "#a63d40")
TERRACOTTA = _g("accent_mapping", "#c2956e")
AMBER = TERRACOTTA                                   # Examen's "AMBER" has always been terracotta
