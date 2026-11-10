"""R17 C3: the suite-wide Interface size setting."""
import ast
import os
from pathlib import Path

import pytest

from shared import ui_scale

ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINTS = ["Observatum/src/main.py", "Atrium/__main__.py", "Codex/__main__.py",
                "Curator/collection_planner.py", "DataEntry/__main__.py", "Examen/__main__.py",
                "Lector/ui/app.py", "Munia/__main__.py",
                "Observatum/src/views/mapping/view3d_child.py"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("QT_SCALE_FACTOR", raising=False)
    monkeypatch.delenv(ui_scale.MARK, raising=False)
    from shared.settings_store import app_settings
    s = app_settings()
    s.remove(ui_scale.KEY)
    s.sync()
    yield
    s.remove(ui_scale.KEY)
    s.sync()


@pytest.mark.parametrize("percent,factor", [(100, "1"), (110, "1.1"), (125, "1.25"), (150, "1.5")])
def test_setting_sets_scale_factor(percent, factor):
    ui_scale.save_percent(percent)
    assert ui_scale.load_percent() == percent
    ui_scale.apply_before_qapp()
    assert os.environ["QT_SCALE_FACTOR"] == factor


def test_default_is_normal_and_bad_values_fall_back():
    assert ui_scale.load_percent() == 100
    from shared.settings_store import app_settings
    app_settings().setValue(ui_scale.KEY, "banana")
    assert ui_scale.load_percent() == 100
    app_settings().setValue(ui_scale.KEY, 300)
    assert ui_scale.load_percent() == 100
    ui_scale.apply_before_qapp()
    assert os.environ["QT_SCALE_FACTOR"] == "1"


def test_existing_environment_value_is_left_alone(monkeypatch):
    ui_scale.save_percent(150)
    monkeypatch.setenv("QT_SCALE_FACTOR", "2")
    ui_scale.apply_before_qapp()
    assert os.environ["QT_SCALE_FACTOR"] == "2"


def test_value_inherited_from_another_suite_program_is_refreshed():
    ui_scale.save_percent(110)
    ui_scale.apply_before_qapp()
    assert os.environ["QT_SCALE_FACTOR"] == "1.1"
    ui_scale.save_percent(125)                  # changed in Observatum while Atrium was open
    ui_scale.apply_before_qapp()                # a program Atrium starts inherits "1.1"
    assert os.environ["QT_SCALE_FACTOR"] == "1.25"


def test_rounding_policy_is_pass_through():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    ui_scale.apply_before_qapp()
    assert QGuiApplication.highDpiScaleFactorRoundingPolicy() == \
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough


@pytest.mark.parametrize("rel", ENTRY_POINTS)
def test_every_entry_point_applies_it_before_the_qapplication(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    ast.parse(src)
    assert "ui_scale.apply_before_qapp()" in src, rel
    # (Data Entry's away-mode message box makes its own tiny QApplication earlier: not the app)
    assert src.index("ui_scale.apply_before_qapp()") < src.index("light_scheme.install(app)")
    assert src.index("ui_scale.apply_before_qapp()") < src.rindex("QApplication(sys.argv"), rel


def test_settings_panel_has_the_combo():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    assert app is not None
    from src.views.settings.general_panel import GeneralSettingsPanel as GeneralPanel
    panel = GeneralPanel()
    combo = panel.interface_size
    assert [combo.itemText(i) for i in range(combo.count())] == \
        ["Normal (100%)", "110%", "125%", "150%"]
    combo.setCurrentIndex(3)                    # saves at once, like the other settings
    assert ui_scale.load_percent() == 150
    panel2 = GeneralPanel()
    assert panel2.interface_size.currentData() == 150
