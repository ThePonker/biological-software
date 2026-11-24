"""Curator's colours: one source, Observatum's Naturalist theme (R13, 24 Oct 2026)."""
from shared.theme_lookup import value as _g


TEXT_SECONDARY = _g("text_secondary", "#6b7280")
SEPARATOR = _g("separator", "#e5e7eb")
BORDER = _g("border", "#d1d5db")
HOVER = _g("hover", "#e5e7eb")
WARM_GRAY = _g("secondary", "#8b8178")
MOSS = _g("primary", "#4a7c59")
MOSS_HOVER = _g("primary_hover", "#3d6649")
DANGER = _g("danger", "#a63d40")
SAGE = _g("success_light", "#5a8c69")              # box has room
TERRACOTTA = _g("accent_mapping", "#c2956e")       # box getting full / drawing accents
TERRACOTTA_DARK = _g("accent_mapping_dark", "#9a7555")
TERRACOTTA_LIGHT = _g("accent_mapping_light", "#f7f2ed")
PURPLE_DARK = _g("accent_scheme_dark", "#5c4f7a")
STEEL = _g("accent_stats", "#5c6b7a")

# The box preview (planner_preview.py) is painted by hand
PREVIEW_INK = _g("preview_ink", "#333333")                    # box title, family name
INK_SOFT = _g("ink_soft", "#555555")                          # capacity label
PREVIEW_LABEL_MUTED = _g("preview_label_muted", "#888888")    # specimen count
PREVIEW_OUTLINE = _g("preview_outline", "#999999")            # box outline
PREVIEW_RULE = _g("preview_rule", "#cccccc")                  # leader line, capacity bar outline
PREVIEW_TRACK = _g("preview_track", "#eeeeee")                # empty capacity bar
PREVIEW_BOX_FILL = _g("preview_box_fill", "#fafafa")          # inside the box
SAGE_FILL = _g("stats_personal_accent", "#7a9e7e")            # capacity bar, under 80 % full
FAMILY_BLUE = _g("stats_all_accent", "#6e8898")
GOLD = _g("accent_collection", "#b8860b")
DARK_SAGE = _g("accent_observation", "#5f8575")
FAMILY_PURPLE = _g("family_purple", "#6b5b73")

# The label preview imitates the printed label, whose ink is plain black.
LABEL_INK = "#000000"
