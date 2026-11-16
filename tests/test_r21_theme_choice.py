"""R21: the second theme (1940s), the stored choice, start-up order, fonts, header, contrast."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from shared import theme_choice

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Observatum"))

from src.themes.forties import FORTIES_THEME          # noqa: E402
from src.themes.naturalist import NATURALIST_THEME    # noqa: E402

# sha256 of the main window's style sheet under Naturalist, computed from the code before R21
NATURALIST_WINDOW_QSS_SHA256 = "28f3b78d66455db80d66ec88f63f79ee5d8b639207dff76a4d6d012579ad5c9c"


@pytest.fixture(autouse=True)
def clean_choice():
    from shared.settings_store import app_settings
    s = app_settings()
    s.remove(theme_choice.KEY)
    s.sync()
    theme_choice._active = "Naturalist"
    yield
    s.remove(theme_choice.KEY)
    s.sync()
    theme_choice._active = "Naturalist"


def _child(code, name="1940s"):
    """Run `code` in a fresh interpreter with the setting stored as `name` (None = unset)."""
    from _sandbox_child import child_code
    store = (f"from shared import theme_choice\ntheme_choice.save_name({name!r})\n"
             if name else "")
    env_path = f"{ROOT}{';' if sys.platform == 'win32' else ':'}{ROOT / 'Observatum'}"
    import os
    env = dict(os.environ, PYTHONPATH=env_path, QT_QPA_PLATFORM="offscreen",
               PYTHONIOENCODING="utf-8")   # Windows: the child prints "\u2713" (R21 fix)
    r = subprocess.run([sys.executable, "-c", child_code(store + code)], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout.strip().splitlines()[-1]


# --- the stored choice -------------------------------------------------------------------

def test_default_is_naturalist_and_names():
    assert theme_choice.NAMES == ("Naturalist", "1940s")
    assert theme_choice.load_name() == "Naturalist"
    assert theme_choice.active_name() == "Naturalist"


def test_save_and_load_and_unknown():
    theme_choice.save_name("1940s")
    assert theme_choice.load_name() == "1940s"
    theme_choice.save_name("Naturalist")
    assert theme_choice.load_name() == "Naturalist"
    from shared.settings_store import app_settings
    app_settings().setValue(theme_choice.KEY, "Light")
    assert theme_choice.load_name() == "Naturalist"
    theme_choice.save_name("banana")
    assert theme_choice.load_name() == "Naturalist"


def test_other_programs_stay_naturalist_until_the_call():
    theme_choice.save_name("1940s")
    assert theme_choice.active_name() == "Naturalist"        # no use_stored call: unchanged
    assert theme_choice.use_stored_theme_for_this_program() == "1940s"
    assert theme_choice.active_name() == "1940s"


def test_set_theme_saves_without_switching():
    from src.themes import theme
    assert theme().available_themes == ["Naturalist", "1940s"]
    assert theme().set_theme("1940s") is False
    assert theme_choice.load_name() == "1940s"


# --- the start-up order (fresh interpreters) ---------------------------------------------

def test_observatum_main_makes_config_and_theme_1940s():
    out = _child(
        "import src.main\n"
        "from src.core.config import TabColors\n"
        "from src.themes import theme\n"
        "print(TabColors.HOME, theme().get('background'), theme()._name)\n")
    assert out == f"{FORTIES_THEME['accent_home']} {FORTIES_THEME['background']} 1940s"


def test_plain_theme_import_without_the_call_is_naturalist():
    out = _child(
        "from src.themes import theme\n"
        "from src.core.config import TabColors\n"
        "print(TabColors.HOME, theme().get('background'), theme()._name)\n")
    assert out == f"{NATURALIST_THEME['accent_home']} {NATURALIST_THEME['background']} Naturalist"


def test_data_entry_tokens_follow_only_after_the_call():
    code = ("{call}from DataEntry import theme\nprint(theme.PAPER)\n")
    assert _child(code.format(call="from shared import theme_choice\n"
                              "theme_choice.use_stored_theme_for_this_program()\n")) \
        == FORTIES_THEME["background"]
    assert _child(code.format(call="")) == NATURALIST_THEME["background"]


def test_both_entry_points_call_it_before_importing_themes():
    for path in ("Observatum/src/main.py", "DataEntry/__main__.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        call = text.index("use_stored_theme_for_this_program()")
        for first_import in ("import src.startup_timing", "bootstrap.init_databases",
                             "from src.themes", "from src.core"):
            if first_import in text:
                assert call < text.index(first_import), (path, first_import)


# --- the theme dictionaries --------------------------------------------------------------

def test_forties_has_every_naturalist_key_and_no_extra():
    assert set(FORTIES_THEME) == set(NATURALIST_THEME)


def test_forties_text_sizes_one_px_larger_where_garamond_runs_small():
    for name in ("caption", "small", "body"):
        k = f"font_px_{name}"
        assert FORTIES_THEME[k] == NATURALIST_THEME[k] + 1
    for k in NATURALIST_THEME:
        if k.startswith("font_px_") and not k.endswith(("_caption", "_small", "_body")):
            assert FORTIES_THEME[k] == NATURALIST_THEME[k], k
    assert min(v for k, v in FORTIES_THEME.items() if k.startswith("font_px_")) >= 13


def test_font_and_header_keys():
    assert FORTIES_THEME["font_family"] == "EB Garamond"
    assert FORTIES_THEME["font_heading"] == "Cormorant SC"
    assert NATURALIST_THEME["font_heading"] == ""
    assert not any(NATURALIST_THEME[k] for k in NATURALIST_THEME if k.startswith("header_"))
    assert FORTIES_THEME["header_bg"] == FORTIES_THEME["primary"] == "#2F4A3A"
    assert FORTIES_THEME["header_rule"] == "#C8A23A"


def test_tab_colours_follow_the_active_theme_dict():
    from src.core.config import TabColors
    from src.themes import active_theme_dict
    assert active_theme_dict() is NATURALIST_THEME           # this process never made the call
    assert TabColors.OBSERVATION == NATURALIST_THEME["accent_observation"]


def _luminance(hex_colour):
    c = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("fg,bg", [
    ("text_primary", "background"), ("text_primary", "surface"), ("text_primary", "input_bg"),
    ("text_secondary", "surface"), ("text_secondary", "background"),
    ("primary_text", "primary"), ("primary_text", "primary_hover"),
    ("danger", "surface"), ("danger_text", "danger_bg"),
    ("success_text", "success_bg"), ("warning_text", "warning_bg"), ("error_text", "error_bg"),
    ("info_text", "info_bg"), ("header_text", "header_bg"), ("tooltip_text", "tooltip_bg"),
])
def test_forties_contrast_at_least_4_5(fg, bg):
    assert contrast(FORTIES_THEME[fg], FORTIES_THEME[bg]) >= 4.5, (fg, bg)


# --- the main window's style sheet and header --------------------------------------------

class _Window:
    def setStyleSheet(self, s):
        self.qss = s


def test_naturalist_window_style_sheet_is_unchanged():
    from src.views.main_window import MainWindow
    w = _Window()
    MainWindow._apply_window_style(w)
    assert hashlib.sha256(w.qss.encode()).hexdigest() == NATURALIST_WINDOW_QSS_SHA256


def test_header_style_only_for_a_theme_with_a_header():
    from src.views.main_window_header import header_style

    class T:
        def __init__(self, d):
            self.d = d

        def get(self, k, fallback=""):
            return self.d.get(k, fallback)
    assert header_style(T(NATURALIST_THEME)) == ""
    qss = header_style(T(FORTIES_THEME))
    assert "#2F4A3A" in qss and "3px solid #C8A23A" in qss and "font-weight: 700" in qss and "first:selected" in qss


def test_beetle_mark_only_with_a_header():
    from PySide6.QtWidgets import QApplication, QTabWidget
    app = QApplication.instance() or QApplication([])      # noqa: F841
    from src.views.main_window_header import add_header_mark, beetle_pixmap

    class T:
        def __init__(self, d):
            self.d = d

        def get(self, k, fallback=""):
            return self.d.get(k, fallback)
    tabs = QTabWidget()
    assert add_header_mark(tabs, T(NATURALIST_THEME)) is None
    label = add_header_mark(tabs, T(FORTIES_THEME))
    assert label is not None and tabs.cornerWidget(Qt.Corner.TopLeftCorner) is label
    img = beetle_pixmap("#C8A23A", "#2F4A3A").toImage()
    assert not img.isNull() and any(img.pixelColor(x, y).alpha() for x in range(28) for y in range(28))


# --- fonts -------------------------------------------------------------------------------

def test_fonts_register_only_for_1940s():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from shared import theme_fonts
    assert theme_fonts.register_theme_fonts(NATURALIST_THEME["font_family"],
                                            NATURALIST_THEME["font_heading"]) == []
    assert theme_fonts.apply_app_font(app, NATURALIST_THEME["font_family"]) is False
    assert theme_fonts.heading_style(NATURALIST_THEME["font_heading"]) == ""
    for f in (theme_fonts.FONT_DIR / n for names in theme_fonts.BUNDLED.values() for n in names):
        assert f.exists(), f
    assert theme_fonts.register_theme_fonts(FORTIES_THEME["font_family"],
                                            FORTIES_THEME["font_heading"]) == ["EB Garamond",
                                                                              "Cormorant SC"]
    from PySide6.QtGui import QFontDatabase
    families = QFontDatabase.families()
    assert "EB Garamond" in families and "Cormorant SC" in families
    assert theme_fonts.apply_app_font(app, "EB Garamond") is True
    assert app.font().family() == "EB Garamond"
    assert "Cormorant SC" in theme_fonts.heading_style("Cormorant SC")


# --- Settings > Appearance ---------------------------------------------------------------

def test_appearance_group_shows_the_stored_choice_and_saves_changes():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])      # noqa: F841
    theme_choice.save_name("1940s")
    from src.views.settings.general_panel import GeneralSettingsPanel
    panel = GeneralSettingsPanel()
    assert not panel.theme_group.isHidden()
    assert [panel.theme_combo.itemText(i) for i in range(panel.theme_combo.count())] \
        == ["Naturalist", "1940s"]
    assert panel.theme_combo.currentText() == "1940s"
    panel.theme_combo.setCurrentText("Naturalist")
    assert theme_choice.load_name() == "Naturalist"
    from PySide6.QtWidgets import QLabel
    notes = [w.text() for w in panel.theme_group.findChildren(QLabel)]
    assert "Takes effect when Observatum is next opened" in notes


def test_text_font_is_the_heavier_cut_and_headings_bold():
    """Wil, 16 Nov: the 1940s text looked faint. The text files are EB Garamond drawn at weight 500
    (bold at 700), registered as plain Regular/Italic/Bold, so Windows can't fall back to the thin
    400; the variable files are not registered. Headings draw in bold small capitals."""
    from shared import theme_fonts
    names = theme_fonts.BUNDLED["EB Garamond"]
    assert not any("wght" in n for n in names)
    assert "font-weight: 700" in theme_fonts.heading_style("Cormorant SC")
    TTFont = pytest.importorskip("fontTools.ttLib").TTFont      # the font tables, where installed
    for n in names:
        f = TTFont(theme_fonts.FONT_DIR / n)
        assert f["name"].getDebugName(1) == "EB Garamond"
        assert "fvar" not in f                                   # a static file, one weight
    reg = TTFont(theme_fonts.FONT_DIR / "EBGaramond-Text-Regular.ttf")
    bold = TTFont(theme_fonts.FONT_DIR / "EBGaramond-Text-Bold.ttf")
    assert reg["OS/2"].usWeightClass == 400 and bold["OS/2"].usWeightClass == 700
