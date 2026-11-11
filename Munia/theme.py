"""Munia theme — Naturalist palette matching Observatum & Examen."""

from shared.theme_lookup import _theme  # noqa: F401  (Munia/__main__.py imports it from here)
from shared.theme_lookup import value as _g
from shared.text_sizes import font_css


# ── Palette (names resolved from Observatum's Naturalist theme, R13) ──
STONE_BG = _g("background", "#f5f5f4")
STONE_LIGHT = _g("surface_alt", "#f9fafb")
STONE_BORDER = _g("border", "#d1d5db")
DUSTY_PURPLE = _g("accent_scheme", "#7c6c9f")
DUSTY_PURPLE_LIGHT = _g("accent_scheme_light", "#eeeaf3")
MOSS_GREEN = _g("primary", "#4a7c59")
MOSS_GREEN_LIGHT = _g("primary_bg", "#e8f0eb")
MOSS_GREEN_HOVER = _g("primary_hover", "#3d6649")
WARM_GRAY = _g("secondary", "#8b8178")
WARM_GRAY_LIGHT = _g("accent_home_light", "#f5f4f3")
FADED_CRIMSON = _g("danger", "#a63d40")
FADED_CRIMSON_LIGHT = _g("danger_bg", "#fce8e8")
AMBER = _g("accent_collection", "#b8860b")
AMBER_LIGHT = _g("accent_collection_light", "#faf6eb")
TEXT_DARK = _g("text_primary", "#1f2937")
TEXT_MID = _g("text_heading", "#4b5563")
TEXT_LIGHT = _g("text_secondary", "#6b7280")

# ── Day-type colours ─────────────────────────────────────────────
DAY_COLOURS = {
    "field": MOSS_GREEN,
    "microscope": DUSTY_PURPLE,
    "report": AMBER,
}

DAY_COLOURS_LIGHT = {
    "field": MOSS_GREEN_LIGHT,
    "microscope": DUSTY_PURPLE_LIGHT,
    "report": AMBER_LIGHT,
}

# ── Fonts ────────────────────────────────────────────────────────
HEADING_FAMILY = "Georgia"
BODY_FAMILY = "Segoe UI"


def window_stylesheet():
    """Return the master stylesheet for the Munia main window."""
    return f"""
        QMainWindow, QWidget#central {{
            background-color: {STONE_BG};
        }}
        QLabel {{
            color: {TEXT_DARK};
            font-family: "{BODY_FAMILY}";
        }}
        QLabel#heading {{
            font-family: "{HEADING_FAMILY}";
            font-size: {font_css('display_22')};
            font-weight: bold;
            color: {TEXT_DARK};
        }}
        QLabel#subheading {{
            font-family: "{HEADING_FAMILY}";
            font-size: {font_css('body')};
            color: {TEXT_MID};
        }}
        QLabel#sectionTitle {{
            font-family: "{HEADING_FAMILY}";
            font-size: {font_css('body_large')};
            font-weight: bold;
            color: {TEXT_DARK};
        }}
        QPushButton#primary {{
            background-color: {MOSS_GREEN};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 7px 18px;
            font-family: "{BODY_FAMILY}";
            font-size: {font_css('body')};
            font-weight: 600;
        }}
        QPushButton#primary:hover {{
            background-color: {MOSS_GREEN_HOVER};
        }}
        QPushButton#primary:disabled {{
            background-color: {WARM_GRAY_LIGHT};
            color: {TEXT_LIGHT};
        }}
        QPushButton#secondary {{
            background-color: transparent;
            color: {WARM_GRAY};
            border: 1px solid {WARM_GRAY};
            border-radius: 4px;
            padding: 7px 18px;
            font-family: "{BODY_FAMILY}";
            font-size: {font_css('body')};
        }}
        QPushButton#secondary:hover {{
            background-color: {WARM_GRAY_LIGHT};
        }}
        QPushButton#delete {{
            background-color: transparent;
            color: {FADED_CRIMSON};
            border: 1px solid {FADED_CRIMSON};
            border-radius: 4px;
            padding: 7px 18px;
            font-family: "{BODY_FAMILY}";
            font-size: {font_css('body')};
        }}
        QPushButton#delete:hover {{
            background-color: {FADED_CRIMSON_LIGHT};
        }}
        QTableWidget {{
            background-color: {STONE_LIGHT};
            border: 1px solid {STONE_BORDER};
            border-radius: 4px;
            gridline-color: {STONE_BORDER};
            font-family: "{BODY_FAMILY}";
            font-size: {font_css('body')};
            color: {TEXT_DARK};
            selection-background-color: {DUSTY_PURPLE_LIGHT};
        }}
        QTableWidget::item {{
            padding: 4px 8px;
        }}
        QHeaderView::section {{
            background-color: {WARM_GRAY_LIGHT};
            color: {TEXT_DARK};
            font-family: "{BODY_FAMILY}";
            font-size: {font_css('small')};
            font-weight: 600;
            padding: 6px 8px;
            border: none;
            border-bottom: 1px solid {STONE_BORDER};
            border-right: 1px solid {STONE_BORDER};
        }}
        QLineEdit {{
            background-color: white;
            border: 1px solid {STONE_BORDER};
            border-radius: 3px;
            padding: 4px 8px;
            font-family: "{BODY_FAMILY}";
            font-size: {font_css('body')};
            color: {TEXT_DARK};
        }}
        QLineEdit:focus {{
            border-color: {DUSTY_PURPLE};
        }}
        QComboBox {{
            background-color: white;
            border: 1px solid {STONE_BORDER};
            border-radius: 3px;
            padding: 4px 8px;
            font-family: "{BODY_FAMILY}";
            font-size: {font_css('body')};
            color: {TEXT_DARK};
        }}
        QComboBox:focus {{
            border-color: {DUSTY_PURPLE};
        }}
        QScrollBar:vertical {{
            background: {STONE_BG};
            width: 10px;
            border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {STONE_BORDER};
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """
