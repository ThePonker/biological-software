"""pytest set-up for the suite's tests (backlog I6).

Puts the project root on sys.path (paths, shared, DataEntry, Examen, Observatum.src...)
and Observatum on it as well, for the modules that import `src.` themselves.
Tests here touch no database: they exercise pure functions only.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Offscreen Qt on Windows finds no fonts, so every font measurement was wrong unless an
# earlier test had happened to start Qt the normal way (13 Oct 2026; docs/05_Rules.md
# "Measure on Wil's PC"). Point it at the Windows fonts before any test starts Qt.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR",
                          os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))


import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _backups_never_leave_the_test_folder(tmp_path_factory):
    """Safety net (review R4, 11 Oct 2026): a test that reaches a backup -- the database
    backup on closing the main window, Data Entry's rolling CSVs -- writes into the test
    folder, never C:\\BiologicalSoftware_Backups (on Wil's PC that would overwrite his real
    staging_backup.csv; on Linux it made a folder literally named 'C:\\Biological...').
    Tests that patch these themselves still do."""
    folder = str(tmp_path_factory.mktemp("backups"))
    os.environ["BIOSOFT_BACKUP_ROOT"] = folder
    try:
        import shared.backup_service as bs
        bs.BACKUP_ROOT = folder
    except Exception:
        pass
    try:
        import DataEntry.csv_backup as cb
        cb.BACKUP_DIR = folder
    except Exception:
        pass
    yield folder


@pytest.fixture(autouse=True)
def _application_font_restored():
    """Each test leaves the application font as it found it (13 Oct 2026). Run in parallel
    (pytest -n 6), tests share each worker's QApplication in a different order, and a main
    window applying the saved font size -- or a test's wide font -- carried into the next
    layout test (1280 px fits failed). No QApplication yet: nothing to do."""
    app = None
    if "PySide6.QtWidgets" in sys.modules:
        app = sys.modules["PySide6.QtWidgets"].QApplication.instance()
    font = None
    if app is not None:
        from PySide6.QtGui import QFont
        font = QFont(app.font())
    yield
    if font is not None:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is app and QApplication.font() != font:
            QApplication.setFont(font)


# Layout tests that measure windows against 1280 px: they pass in one process but not under
# parallel workers (pytest -n 6), so they run on their own afterwards (13 Oct 2026):
#   py -3.14 -m pytest tests -q -n 6 -m "not layout"; py -3.14 -m pytest tests -q -m layout
LAYOUT_TESTS = (
    "tests/test_window_width_r4.py::",
    "tests/test_r10c.py::test_drawer_in_hand_fits_laptop_width_with_wide_text",
    "tests/test_lector_r8.py::test_dashboard_rows_fit_1280x720",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "layout: window-width tests, run outside the parallel run")


def pytest_collection_modifyitems(config, items):
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        if nodeid.startswith(LAYOUT_TESTS):
            item.add_marker(pytest.mark.layout)
