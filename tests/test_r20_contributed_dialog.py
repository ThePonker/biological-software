"""Round 20: the Contributed tab is a window opened from Observation Data (11 Nov 2026).

The main window is built with stand-in tabs (as test_loading_r5); the Contributed window holds
the real ContributedTab, reading a small purpose-made database in tmp_path.
"""
import os
import sqlite3
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(__file__))

from test_contributed_repository import ROWS, SCHEMA  # noqa: E402
from test_loading_r5 import make_window  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings
    import src.views.contributed.contributed_dialog as cd
    import src.views.contributed.contributed_tab as ct
    path = tmp_path / "obs.db"
    c = sqlite3.connect(path)
    c.execute(SCHEMA)
    c.executemany(
        "INSERT INTO contributed_observations (species_name, common_name, date, site_name, "
        "project_name, contributor, source_file, received_date, import_batch, quantity) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ROWS)
    c.commit()
    c.close()
    monkeypatch.setattr(ct, "get_database", lambda: SimpleNamespace(main_db_path=path))
    ini = str(tmp_path / "settings.ini")           # the window size is saved here, not in the registry
    monkeypatch.setattr(cd, "QSettings", lambda: QSettings(ini, QSettings.Format.IniFormat))
    yield from make_window(monkeypatch)


def _with_filter_bar(w):
    """Give the stand-in Observation Data tab the real toolbar (the always-visible row the
    button sits on) and connect its button."""
    from src.views.observations.observation_toolbar import ObservationToolbar
    bar = ObservationToolbar()
    w.observation_tab.toolbar = bar
    w._connect_contributed_button()
    return bar


def test_no_contributed_tab_and_order_of_the_rest(window):
    w, _f = window
    names = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    assert "Contributed" not in names
    assert names == ["Home", "Observation Data", "Recording Scheme", "Insect Collection",
                     "Stats/Reports", "Mapping", "Settings"]
    assert not hasattr(w, "contributed_tab")
    assert w._contributed_dialog is None            # built on first use


def test_tabs_still_open_by_widget_after_the_shift(window, qapp):
    w, _f = window
    w.preload()
    # every tab ready under the splash is the one it names (not an index left over)
    ready = {w.tabs.tabText(i) for i in w._initialized_tabs}
    assert ready == {"Home", "Observation Data", "Insect Collection"}
    w.connect_tab_signal()
    for widget, name in ((w.observation_tab, "Observation Data"),
                         (w.recording_scheme_tab, "Recording Scheme"),
                         (w.insect_collection_tab, "Insect Collection")):
        w.tabs.setCurrentWidget(widget)
        assert w.tabs.tabText(w.tabs.currentIndex()) == name
    w._navigate_to_observation_tab("Rutpela maculata")
    assert w.tabs.currentWidget() is w.observation_tab


def test_button_opens_dialog_with_a_contributed_tab(window, qapp):
    from src.views.contributed import ContributedDialog, ContributedTab
    w, _f = window
    bar = _with_filter_bar(w)
    assert bar.contributed_btn.text() == "Contributed records…"
    assert bar.contributed_btn.toolTip() == "Records other people sent (read-only browse)"
    bar.contributed_btn.click()
    dlg = w._contributed_dialog
    assert isinstance(dlg, ContributedDialog) and dlg.isVisible() and not dlg.isModal()
    tab = dlg.findChild(ContributedTab)
    assert tab is dlg.contributed_tab
    assert tab.model.rowCount() == 4                 # read when first opened, behaviour unchanged
    dlg.close()


def test_second_press_raises_the_same_dialog(window, qapp):
    w, _f = window
    bar = _with_filter_bar(w)
    bar.contributed_btn.click()
    first = w._contributed_dialog
    first.hide()
    bar.contributed_btn.click()
    assert w._contributed_dialog is first and first.isVisible()
    assert w.findChildren(type(first)) == [first]    # one instance only
    first.close()


def test_entry_point_with_a_filter_applies_it(window, qapp):
    w, _f = window
    dlg = w.open_contributed_records("alni")
    assert dlg.isVisible()
    assert dlg.contributed_tab.search_edit.text() == "alni"
    assert dlg.contributed_tab.model.rowCount() == 2
    assert w.open_contributed_records() is dlg
    dlg.close()


def test_dialog_size_follows_main_window_and_fits_a_small_screen(window, qapp):
    w, _f = window
    w.resize(1200, 700)
    dlg = w.open_contributed_records()
    from shared.fit_to_screen import available_geometry
    avail = available_geometry(dlg)
    assert dlg.width() <= avail.width() and dlg.height() <= avail.height()
    dlg.close()


def test_old_remembered_tab_index_is_not_used():
    """Nothing in the window stores or restores a tab number (so an old session's cannot
    open the wrong tab)."""
    import inspect
    import src.views.main_window as mw
    src_text = inspect.getsource(mw)
    assert "last_tab" not in src_text and "currentIndex(" not in src_text.replace(
        "stack.currentIndex()", "")
