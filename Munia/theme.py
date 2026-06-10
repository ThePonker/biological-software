"""Munia theme — Naturalist palette matching Observatum & Examen."""

# ── Palette ──────────────────────────────────────────────────────
STONE_BG = "#f5f5f4"
STONE_LIGHT = "#fafaf9"
STONE_BORDER = "#d6d3d1"
DUSTY_PURPLE = "#7c6c9f"
DUSTY_PURPLE_LIGHT = "#e8e4f0"
MOSS_GREEN = "#4a7c59"
MOSS_GREEN_LIGHT = "#e6f0ea"
WARM_GRAY = "#8b8178"
WARM_GRAY_LIGHT = "#f0eeec"
FADED_CRIMSON = "#a63d40"
FADED_CRIMSON_LIGHT = "#f5e6e6"
AMBER = "#b8860b"
AMBER_LIGHT = "#fdf4e3"
TEXT_DARK = "#292524"
TEXT_MID = "#57534e"
TEXT_LIGHT = "#78716c"

# ── Day-type colours ─────────────────────────────────────────────
DAY_COLOURS = {
    "field": "#4a7c59",
    "microscope": "#7c6c9f",
    "report": "#b8860b",
}

DAY_COLOURS_LIGHT = {
    "field": "#d4e8da",
    "microscope": "#ddd8e8",
    "report": "#f0e4c4",
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
            font-size: 22px;
            font-weight: bold;
            color: {TEXT_DARK};
        }}
        QLabel#subheading {{
            font-family: "{HEADING_FAMILY}";
            font-size: 14px;
            color: {TEXT_MID};
        }}
        QLabel#sectionTitle {{
            font-family: "{HEADING_FAMILY}";
            font-size: 15px;
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
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton#primary:hover {{
            background-color: #3d6a4b;
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
            font-size: 13px;
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
            font-size: 13px;
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
            font-size: 13px;
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
            font-size: 12px;
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
            font-size: 13px;
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
            font-size: 13px;
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
