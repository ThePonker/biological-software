"""Every app pins the light colour scheme, so a dark-mode Windows PC can't turn table text
white on white (seen 25 Oct 2026 on a friend's PC)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ["Observatum/src/main.py", "DataEntry/__main__.py", "Examen/__main__.py",
           "Codex/__main__.py", "Curator/collection_planner.py", "Munia/__main__.py",
           "Atrium/__main__.py", "Lector/ui/app.py",
           "Observatum/src/features/gamification/game_launcher.py",
           "Observatum/src/views/mapping/view3d_child.py"]


def test_prepare_turns_off_windows_dark_mode_only_when_unset(monkeypatch):
    from shared import light_scheme
    monkeypatch.setattr(light_scheme.sys, "platform", "win32")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    light_scheme.prepare()
    import os
    assert os.environ["QT_QPA_PLATFORM"] == "windows:darkmode=0"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    light_scheme.prepare()
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


def test_prepare_leaves_other_systems_alone(monkeypatch):
    from shared import light_scheme
    monkeypatch.setattr(light_scheme.sys, "platform", "linux")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    light_scheme.prepare()
    import os
    assert "QT_QPA_PLATFORM" not in os.environ
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")   # put the test platform back


def test_install_pins_light():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from shared import light_scheme
    qapp = QApplication.instance() or QApplication([])
    if not hasattr(qapp.styleHints(), "setColorScheme"):
        pytest.skip("Qt older than 6.8")
    assert light_scheme.install(qapp)
    assert qapp.styleHints().colorScheme() in (Qt.ColorScheme.Light, Qt.ColorScheme.Unknown)


@pytest.mark.parametrize("entry", ENTRIES)
def test_every_app_prepares_before_and_installs_after_its_qapplication(entry):
    src = (ROOT / entry).read_text(encoding="utf-8")
    made = [m.start() for m in re.finditer(r"app = QApplication", src)]
    assert made, f"{entry}: no QApplication found"
    pos = made[-1]
    assert src.rfind("light_scheme.prepare()", 0, pos) != -1, f"{entry}: prepare() not before it"
    assert src.find("light_scheme.install(app)", pos) != -1, f"{entry}: install(app) not after it"
