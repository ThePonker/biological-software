"""24 Nov 2026 (round 3, D): one copy of the dd/mm/yyyy day swap, and no hex colours written into
the Curator planner preview, the gamification views, Munia or the Examen import dialog.

(a) shared.display_format.day_dmy gives what every table showed before, and the six callers that
    used to carry their own copy still show the same text.
(b) every theme token that replaced a literal has the old value under Naturalist, and the same
    value in the 1940s theme.
(c) the changed modules import and hold no '#xxxxxx' string outside a docstring or a
    look-up fallback (`value('key', '#...')`).
"""
import importlib.util
import os
import ast
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.display_format import day_dmy  # noqa: E402
from src.themes.forties import FORTIES_THEME  # noqa: E402
from src.themes.naturalist import NATURALIST_THEME as N  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- (a) dates
def test_day_dmy_outputs():
    assert day_dmy("2026-06-05") == "05/06/2026"
    assert day_dmy("2026-06-05T10:30:00") == "05/06/2026"
    assert day_dmy("2026-06-05 10:30") == "05/06/2026"
    assert day_dmy("") == "" and day_dmy(None) == ""
    assert day_dmy("2021-06") == "2021-06"            # not a whole day: unchanged (dmy() reads it)
    assert day_dmy("unknown") == "unknown"
    assert day_dmy("2021-06", other="") == ""
    assert day_dmy("", other="—") == "—"


def test_every_caller_shows_what_it_showed():
    from Codex.theme import format_date
    from DataEntry.visit_weather_dialog import _dmy
    from src.views.components.sort_items import iso_to_dmy, date_item
    from src.views.components.species_accounts_panel import _ddmmyyyy
    from src.views.stats.month_records_dialog import _fmt_date
    assert [f("2026-06-05") for f in (format_date, _dmy, iso_to_dmy, _ddmmyyyy, _fmt_date)] \
        == ["05/06/2026"] * 5
    assert [f("") for f in (format_date, iso_to_dmy, _ddmmyyyy, _fmt_date)] == [""] * 4
    assert format_date("unknown") == "unknown"        # Codex shows 'unknown' build dates as they are
    assert iso_to_dmy("2021-06") == "" and iso_to_dmy(None) == ""
    assert _ddmmyyyy("2026-06-05T10:30") == "05/06/2026" and _ddmmyyyy(None) == ""
    assert _fmt_date("2021-06") == "2021-06" and _fmt_date(None) == ""
    assert date_item("2026-06-05").text() == "05/06/2026"


def test_munia_date_cell():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Munia.projects_panel import ProjectsPanel

    class Table:
        got = None

        def setItem(self, r, c, item):
            self.got = item

    def show(value):
        fake = type("F", (), {})()
        fake.table = Table()
        ProjectsPanel._date_cell(fake, 0, 0, value)
        return fake.table.got.text()
    assert show("2026-06-05") == "05/06/2026"
    assert show("") == "—" and show(None) == "—" and show("2021-06") == "—"


# ---------------------------------------------------------------- (b) tokens
# token -> the value the literal had before (Naturalist, and the same in every theme)
NEW_TOKENS = {
    "preview_ink": "#333333", "ink_soft": "#555555", "preview_label_muted": "#888888",
    "preview_outline": "#999999", "preview_rule": "#cccccc", "preview_track": "#eeeeee",
    "preview_box_fill": "#fafafa", "family_purple": "#6b5b73",
    "btn_neutral_bg": "#e0e0e0", "btn_neutral_hover": "#d0d0d0", "progress_track": "#dddddd",
    "tab_idle_bg": "#e8e8e8", "neutral_light": "#f0f0f0", "scroll_handle_hover": "#aaaaaa",
    "launcher_bg": "#f0f7f4", "launcher_ink": "#2d5a4a", "launcher_stats_bg": "#e8f4ed",
    "launcher_stats_border": "#c8ddd0", "ink_mid": "#666666", "vc_unearned": "#3d3d3d",
    "season_tint_green": "#edf5ef", "season_tint_purple": "#eee9f3",
    "season_tint_amber": "#f7f0e0", "table_selection_purple": "#c8bfdb",
    "table_alt_row_warm": "#f4f3f1", "primary_hover_alt": "#3d6a4b",
    "outline_btn_hover_bg": "#f0eeec",
}
# existing tokens that now stand for a literal, with that literal
OLD_TOKENS = {
    "accent_mapping": "#c2956e", "stats_personal_accent": "#7a9e7e", "stats_all_accent": "#6e8898",
    "secondary": "#8b8178", "accent_collection": "#b8860b", "danger": "#a63d40",
    "accent_observation": "#5f8575", "accent_mapping_dark": "#9a7555", "primary": "#4a7c59",
    "accent_observation_dark": "#4a6b5c", "text_secondary": "#6b7280",
    "success_bright": "#6a9c79", "btn_outline_disabled_text": "#aaa", "error_bg_light": "#fef2f2",
    "border": "#d1d5db", "disabled_text": "#9ca3af",
}


def test_new_tokens_keep_their_old_value_in_every_theme():
    for key, hexv in NEW_TOKENS.items():
        assert N[key] == hexv, key
        assert FORTIES_THEME[key] == hexv, key


def test_existing_tokens_match_the_literals_they_replace():
    for key, hexv in OLD_TOKENS.items():
        assert N[key].lower() == hexv, key


def test_resolved_palette_values_are_the_old_pixels():
    from Curator import style as cs
    from Curator import planner_preview as pp
    assert pp.FAMILY_COLOURS == ["#c2956e", "#7a9e7e", "#6e8898", "#8b8178", "#b8860b", "#a63d40",
                                 "#5f8575", "#9a7555", "#4a7c59", "#6b5b73"]
    assert (cs.PREVIEW_INK, cs.INK_SOFT, cs.PREVIEW_LABEL_MUTED, cs.PREVIEW_OUTLINE,
            cs.PREVIEW_RULE, cs.PREVIEW_TRACK, cs.PREVIEW_BOX_FILL, cs.SAGE_FILL) == (
        "#333333", "#555555", "#888888", "#999999", "#cccccc", "#eeeeee", "#fafafa", "#7a9e7e")
    from Munia import theme as mt
    assert (mt.TEXT_OFF, mt.ERROR_TINT, mt.SEASON_GREEN, mt.SEASON_PURPLE, mt.SEASON_AMBER,
            mt.SELECTION_PURPLE, mt.ALT_ROW) == (
        "#aaa", "#fef2f2", "#edf5ef", "#eee9f3", "#f7f0e0", "#c8bfdb", "#f4f3f1")
    from Examen import style as es
    assert (es.MOSS_HOVER_ALT, es.OUTLINE_HOVER, es.DISABLED_BG, es.DISABLED_TEXT) == (
        "#3d6a4b", "#f0eeec", "#d1d5db", "#9ca3af")


def test_gamification_pieces_read_the_theme():
    from src.features.gamification import launcher, styles, theme_bridge
    from src.features.gamification.tabs.vcs import VCsTab
    v = VCsTab(renderer=None)
    assert (v.VC_UNEARNED, v.VC_EARNED, v.VC_STROKE, v.VC_EARNED_STROKE) == (
        "#3d3d3d", "#4a7c59", "#555555", "#6a9c79")
    assert launcher._c("launcher_bg") == "#f0f7f4"
    css = styles.get_light_stylesheet()
    for hexv in ("#e0e0e0", "#d0d0d0", "#dddddd", "#e8e8e8", "#f0f0f0", "#aaaaaa"):
        assert hexv in css
    # the two fallbacks that had drifted from the theme now are the theme's values
    assert theme_bridge._LIGHT_FALLBACKS["warning"] == N["warning"]
    assert theme_bridge._LIGHT_FALLBACKS["info"] == N["info"]
    for key, fb in theme_bridge._LIGHT_FALLBACKS.items():
        assert N[key].lower() == fb, key
    assert theme_bridge.LIGHT_COLORS["warning"] == N["warning"]


# ---------------------------------------------------------------- (c) no literals
CHANGED = [
    "Curator/planner_preview.py", "Munia/budget_settings.py", "Munia/capacity_dashboard.py",
    "Munia/projects_panel.py", "Examen/import_species_dialog.py",
    "Observatum/src/features/gamification/launcher.py",
    "Observatum/src/features/gamification/styles.py",
    "Observatum/src/features/gamification/tabs/tiers.py",
    "Observatum/src/features/gamification/tabs/vcs.py",
    "Observatum/src/views/stats/stat_widgets.py",
    "Observatum/src/views/dialogs/species_list_dialog.py",
    "Observatum/src/views/stats/month_records_dialog.py",
    "Observatum/src/views/components/sort_items.py",
    "Observatum/src/views/components/species_accounts_panel.py",
    "DataEntry/visit_weather_dialog.py",    # (Codex/theme.py: the IUCN status colours are not in this round)
]
HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def _r21():
    spec = importlib.util.spec_from_file_location(
        "r21_scan", ROOT / "tests" / "test_r21_no_colours_views_b.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_hex_literal_in_the_changed_modules():
    r21 = _r21()
    left = []
    for rel in CHANGED:
        src = (ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        skip = r21._docstring_nodes(tree) | r21._fallback_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in skip and HEX.search(node.value):
                left.append(f"{rel}:{node.lineno} {HEX.search(node.value).group(0)}")
    assert not left, "hex colours written into the code (use theme()):\n" + "\n".join(left)


def test_changed_modules_import():
    from Curator import planner_preview  # noqa: F401
    from Munia import budget_settings, capacity_dashboard, projects_panel  # noqa: F401
    from Examen import import_species_dialog  # noqa: F401
    from src.features.gamification.tabs import tiers, vcs  # noqa: F401
    from src.views.stats import stat_widgets  # noqa: F401
    from src.views.dialogs import species_list_dialog  # noqa: F401
