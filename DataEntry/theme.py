"""Design tokens for DataEntry.

Tokens resolve from Observatum's Naturalist theme when embedded (src.themes.theme), else fall
back to local values. Style helpers are built directly from these tokens (we do NOT call the
app's preset methods, since some rely on keys the Naturalist theme doesn't define).
"""
_OBS = None
try:
    from src.themes import theme as _obs_theme
    _OBS = _obs_theme()
except Exception:
    _OBS = None

def _g(key, fallback):
    if _OBS is not None:
        try:
            v = _OBS.get(key)
            if v and v != "#ff00ff":
                return v
        except Exception:
            pass
    return fallback

INK         = _g("text_primary",   "#1f2937")
HEADING     = _g("text_heading",   "#4b5563")
MUTED       = _g("text_secondary", "#6b7280")
FAINT       = _g("text_muted",     "#9ca3af")
PAPER       = _g("background",     "#f5f5f4")
CARD        = _g("surface",        "#ffffff")
SURFACE_ALT = _g("surface_alt",    "#f9fafb")
LINE        = _g("border",         "#d1d5db")
SEPARATOR   = _g("separator",      "#e5e7eb")
HOVER       = _g("hover",          "#e5e7eb")
DISABLED_BG   = _g("disabled_bg",   "#f3f4f6")
DISABLED_TEXT = _g("disabled_text", "#9ca3af")

MOSS       = _g("primary",       "#4a7c59")
MOSS_HOVER = _g("primary_hover", "#3d6649")
GOLD       = _g("warning",       "#d97706")
SLATE      = _g("accent_stats",  "#5c6b7a")
CLAY       = _g("danger",        "#a63d40")
CLAY_HOVER = _g("danger_hover",  "#8b3033")
PURPLE     = _g("purple",        "#7c6c9f")

MOSS_BG  = _g("success_bg",         "#f0f5f2")
SLATE_BG = _g("accent_stats_light", "#eaecef")
GOLD_BG  = _g("warning_bg",         "#fef3c7")
CLAY_BG  = _g("danger_bg",          "#fce8e8")

RADIUS_SM = _g("radius_sm", "4px")
RADIUS_MD = _g("radius_md", "6px")
RADIUS_LG = _g("radius_lg", "8px")

def card_qss():
    return "background-color: %s; border: 1px solid %s; border-radius: %s;" % (CARD, LINE, RADIUS_LG)

def button_primary_qss():
    return ("QPushButton { background-color: %s; color: #ffffff; border: none;"
            " border-radius: %s; padding: 6px 14px; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background-color: %s; }"
            "QPushButton:disabled { background-color: %s; color: %s; }"
            % (MOSS, RADIUS_MD, MOSS_HOVER, DISABLED_BG, DISABLED_TEXT))

def button_secondary_qss():
    return ("QPushButton { background-color: transparent; color: %s;"
            " border: 1px solid %s; border-radius: %s; padding: 6px 12px; font-size: 12px; }"
            "QPushButton:hover { background-color: %s; }" % (SLATE, SLATE, RADIUS_MD, HOVER))

def button_delete_qss():
    return ("QPushButton { background-color: transparent; color: %s;"
            " border: 1px solid %s; border-radius: %s; padding: 6px 12px; font-size: 12px; }"
            "QPushButton:hover { background-color: %s; }" % (CLAY, CLAY, RADIUS_MD, CLAY_BG))

def input_qss():
    return ("QLineEdit, QComboBox, QSpinBox { background: %s; border: 1px solid %s;"
            " border-radius: %s; padding: 4px 8px; color: %s; }"
            "QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid %s; padding: 3px 7px; }"
            "QComboBox QAbstractItemView { background: %s; border: 1px solid %s;"
            " selection-background-color: %s; selection-color: #ffffff; outline: none; }"
            % (CARD, LINE, RADIUS_SM, INK, MOSS, CARD, LINE, SLATE))

def checkbox_qss():
    return "QCheckBox { color: %s; spacing: 6px; }" % INK

def badge_qss(kind="default"):
    m = {
        "default":  (SURFACE_ALT, MUTED),
        "success":  (MOSS_BG, _g("success_text", "#3d6b4a")),
        "threat":   (CLAY_BG, _g("danger", "#a63d40")),
        "rarity":   (GOLD_BG, _g("warning_text", "#92400e")),
        "priority": (SLATE_BG, _g("accent_stats_dark", "#454f5c")),
        "legal":    (SLATE_BG, _g("accent_stats_dark", "#454f5c")),
        "warning":  (GOLD_BG, _g("warning_text", "#92400e")),
    }
    bg, fg = m.get(kind, m["default"])
    return ("background-color: %s; color: %s; padding: 2px 8px;"
            " border-radius: %s; font-size: 11px; font-weight: 600;" % (bg, fg, RADIUS_SM))

def header_qss():
    return "color: %s; font-size: 15px; font-weight: 700; letter-spacing: 1px;" % HEADING
