"""Round 13: every app takes its colours from one source, Observatum's Naturalist theme.

(a) every literal theme key the code asks for exists in the theme (the magenta-bug guard),
(b) TabColors / ButtonColors are look-ups into the theme, (c) the palette names of Examen,
Munia, Codex, Atrium and Curator resolve to theme values, (d) the check boxes in dialogs and
settings no longer draw their own indicator, so the shared green tick reaches them.
"""
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.themes.naturalist import NATURALIST_THEME as T  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_DIRS = ["Observatum", "shared", "Examen", "Codex", "Curator", "Munia", "Atrium", "Lector", "DataEntry"]
# theme().get('key') / t.get("key", fallback) and the other names the code gives a theme object
GET_RE = re.compile(r"""(?<![\w.])(?:theme\(\)|_theme\(\)|t|T|th|_t|self\._theme|self\.theme)"""
                    r"""\.get\(\s*(['"])([A-Za-z0-9_]+)\1""")
THEME_USER_RE = re.compile(r"themes? import|import theme|\btheme\(\)|NATURALIST_THEME")


def _source_files():
    for d in APP_DIRS:
        for p in (ROOT / d).rglob("*.py"):
            if {"_archive", "__pycache__", "tests"} & set(p.parts):
                continue
            yield p


# ---------------------------------------------------------------- (a)
def test_every_literal_theme_key_exists():
    missing = []
    for p in _source_files():
        text = p.read_text(encoding="utf-8", errors="replace")
        if not THEME_USER_RE.search(text):          # t.get() in a file with no theme is a dict
            continue
        for n, line in enumerate(text.split("\n"), 1):
            for m in GET_RE.finditer(line):
                if m.group(2) not in T:
                    missing.append(f"{p.relative_to(ROOT)}:{n} {m.group(2)}")
    assert not missing, "theme keys the theme does not have:\n" + "\n".join(missing)


# ---------------------------------------------------------------- (b)
TAB_KEYS = {"HOME": "home", "SETTINGS": "settings", "OBSERVATION": "observation",
            "RECORDING_SCHEME": "scheme", "COLLECTION": "collection", "STATS": "stats",
            "MAPPING": "mapping", "PERSONAL": "personal", "COMMERCIAL": "commercial",
            "SPECIES": "species"}
BUTTON_KEYS = {"PRIMARY": "button_primary", "PRIMARY_HOVER": "primary_hover",
               "PRIMARY_PRESSED": "primary_pressed", "PRIMARY_TEXT": "primary_text",
               "SECONDARY": "secondary", "SECONDARY_HOVER": "secondary_hover",
               "SECONDARY_TEXT": "secondary_text", "DANGER": "danger",
               "DANGER_HOVER": "danger_hover", "DANGER_TEXT": "danger_text"}


def test_tab_and_button_colours_are_the_theme_values():
    from src.core.config import ButtonColors, TabColors
    for attr, name in TAB_KEYS.items():
        assert getattr(TabColors, attr) == T["accent_" + name]
        assert getattr(TabColors, attr + "_LIGHT") == T["accent_" + name + "_light"]
        assert getattr(TabColors, attr + "_DARK") == T["accent_" + name + "_dark"]
    for attr, key in BUTTON_KEYS.items():
        assert getattr(ButtonColors, attr) == T[key]
    # the values those tabs have always drawn are unchanged
    assert TabColors.PERSONAL == "#10b981"
    assert TabColors.COMMERCIAL_LIGHT == "#ede9fe"
    assert TabColors.get_variants("scheme")["accent_light"] == T["accent_scheme_light"]


# ---------------------------------------------------------------- (c)
def test_examen_palette_resolves_to_theme():
    from Examen import style
    expect = {"BG": "background", "SURFACE": "surface", "TEXT_PRIMARY": "text_primary",
              "TEXT_HEADING": "text_heading", "TEXT_SECONDARY": "text_secondary",
              "TEXT_MUTED": "text_muted", "BORDER": "border", "SEPARATOR": "separator",
              "ACCENT": "accent_scheme", "ACCENT_LIGHT": "accent_scheme_light",
              "ACCENT_DARK": "accent_scheme_dark", "MOSS_GREEN": "primary",
              "MOSS_HOVER": "primary_hover", "WARM_GRAY": "secondary", "RED_STATUS": "danger",
              "AMBER": "accent_mapping", "TERRACOTTA": "accent_mapping"}
    for name, key in expect.items():
        assert getattr(style, name) == T[key], name


def test_examen_modules_use_the_shared_names():
    import Examen.assemblage_tab as a
    import Examen.examen_ui as u
    import Examen.site_analysis_view as s
    from Examen import style
    assert a.AMBER == style.AMBER and u.ACCENT_LIGHT == T["accent_scheme_light"]
    assert s.ACCENT_DARK == T["accent_scheme_dark"]


def test_munia_palette_resolves_to_theme():
    from Munia import theme as m
    expect = {"STONE_BG": "background", "STONE_BORDER": "border", "DUSTY_PURPLE": "accent_scheme",
              "MOSS_GREEN": "primary", "WARM_GRAY": "secondary", "FADED_CRIMSON": "danger",
              "AMBER": "accent_collection", "TEXT_DARK": "text_primary",
              "TEXT_MID": "text_heading", "TEXT_LIGHT": "text_secondary"}
    for name, key in expect.items():
        assert getattr(m, name) == T[key], name
    assert m.DAY_COLOURS["field"] == T["primary"]
    assert m.MOSS_GREEN_HOVER == T["primary_hover"] and m.MOSS_GREEN_HOVER in m.window_stylesheet()


def test_codex_palette_is_the_shared_palette():
    from Codex import theme as c
    expect = {"ACCENT": "primary", "ACCENT_LIGHT": "primary_bg", "ACCENT_DARK": "primary_dark",
              "SURFACE": "surface", "BORDER": "border", "TEXT_PRIMARY": "text_primary",
              "DANGER": "danger", "WARNING": "warning", "SUCCESS": "success"}
    for name, key in expect.items():
        assert getattr(c, name) == T[key], name


def test_codex_species_tab_has_no_hard_coded_status_colours():
    text = (ROOT / "Codex" / "species_tab.py").read_text(encoding="utf-8")
    assert "color: red" not in text
    for hexcode in ("#c62828", "#ef6c00", "#7cb342"):
        assert hexcode not in text


def test_atrium_identity_colours_come_from_the_theme():
    from Atrium import atrium_ui as ui
    from Atrium.process_manager import APPS
    by_name = {a.name: a for a in APPS}
    assert by_name["Codex"].colour == T["primary"]
    assert by_name["Examen"].colour == T["accent_scheme_dark"]
    assert by_name["Curator"].colour == T["primary"]
    assert by_name["Lector"].colour == T["accent_stats"]
    assert by_name["Observatum"].colour == T["app_observatum"]
    assert by_name["Munia"].colour == T["app_munia"]
    assert ui.MOSS == T["primary"] and ui.BG == T["background"] and ui.GOLD == T["accent_collection"]


def test_curator_palette_resolves_to_theme():
    from Curator import style as s
    expect = {"MOSS": "primary", "MOSS_HOVER": "primary_hover", "DANGER": "danger",
              "WARM_GRAY": "secondary", "SEPARATOR": "separator", "HOVER": "hover",
              "TERRACOTTA": "accent_mapping", "TERRACOTTA_DARK": "accent_mapping_dark",
              "PURPLE_DARK": "accent_scheme_dark", "STEEL": "accent_stats"}
    for name, key in expect.items():
        assert getattr(s, name) == T[key], name
    for f in ("planner_settings", "planner_box_view", "planner_labels_view",
              "planner_family_list", "planner_label_preview"):
        text = (ROOT / "Curator" / (f + ".py")).read_text(encoding="utf-8")
        assert not re.search(r"""["'(]#[0-9a-fA-F]{3,6}\b""", text.replace("# ", "")), f


# ---------------------------------------------------------------- (d)
TICK_FILES = [
    "settings/settings_tab.py",
    "components/filter_wizard/how_filter_dialog.py",
    "components/filter_wizard/status_filter_dialog.py",
    "components/filter_wizard/who_filter_dialog.py",
    "components/filter_wizard/where_filter_dialog.py",
    "home/quick_entry.py",
    "home/quick_entry_fields_mixin.py",
    "dialogs/scheme_import_wizard/wizard_pages_mixin.py",
    "dialogs/specimen_import_wizard/wizard_pages_mixin.py",
]


@pytest.mark.parametrize("rel", TICK_FILES)
def test_dialog_check_boxes_carry_no_indicator_rule(rel):
    text = (ROOT / "Observatum" / "src" / "views" / rel).read_text(encoding="utf-8")
    assert "QCheckBox::indicator" not in text


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_shared_tick_reaches_a_dialog_check_box(qapp):
    from PySide6.QtWidgets import QCheckBox, QWidget
    from shared import tick_style
    from src.themes import theme
    from src.views.dialogs.scheme_import_wizard.wizard_pages_mixin import WizardPagesMixin
    tick_style.install(qapp, lambda: tick_style.theme_colours(theme()))
    sheet = WizardPagesMixin._get_checkbox_style(None)
    assert "::indicator" not in sheet
    host = QWidget()
    box = QCheckBox("Tick me", host)
    box.setStyleSheet(sheet)
    host.show()
    qapp.processEvents()
    assert tick_style.is_styled(box)
    assert "image: url(" in box.styleSheet()
    host.close()
