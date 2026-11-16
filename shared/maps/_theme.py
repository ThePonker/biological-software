"""Colour tokens for the shared map widgets -- the one place they come from.

Maps stay Naturalist in every theme (R21, 16 Nov 2026): a map's colours are part of what a report
or export shows, so they read NATURALIST_THEME directly (shared.theme_lookup.naturalist_value),
never the active theme. The names are those of DataEntry/theme.py, which the maps were built with,
and they mean the same Naturalist keys; `theme.INK`, `theme.MOSS` and so on are used as before.
"""
from types import SimpleNamespace

from shared.theme_lookup import naturalist_value as _n

theme = SimpleNamespace(
    INK=_n("text_primary", "#1f2937"),
    HEADING=_n("text_heading", "#4b5563"),
    MUTED=_n("text_secondary", "#6b7280"),
    PAPER=_n("background", "#f5f5f4"),
    CARD=_n("surface", "#ffffff"),
    LINE=_n("border", "#d1d5db"),
    MOSS=_n("primary", "#4a7c59"),
    MOSS_HOVER=_n("primary_hover", "#3d6649"),
    GOLD=_n("warning", "#d97706"),
    SLATE=_n("accent_stats", "#5c6b7a"),
    CLAY=_n("danger", "#a63d40"),
    PURPLE=_n("purple", "#7c6c9f"),
)
