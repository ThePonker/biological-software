"""Startup speed (Round 4, 11 Oct 2026) -- and what still holds after Round 5.

Round 5 (tests/test_loading_r5.py) loads every tab under the splash screen
(MainWindow.preload) before the window is shown. Building the MainWindow on its own still
builds Stats/Reports, Mapping and Settings lazily and reads no records -- preload does that
-- and the Round 4 first-opening path is kept as the fallback for a tab whose startup step
failed. So these tests still apply:

- Stats/Reports, Mapping and Settings are built by LazyTabPage when first needed; their
  signals are connected when they are built.
- A tab not loaded at startup reads its records on first opening.
- Cross-tab navigation ("View records" etc. from Stats) still works when the target tab
  has never been opened: it is initialised before the filter is applied.
- pandas is not imported at startup (import wizards load it on first use).

The main window is built with light stand-in tabs: no database is opened.
"""
import os
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ── stand-in tabs ───────────────────────────────────────────────────

def _fakes():
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QCheckBox, QLineEdit, QWidget

    class _QuickEntry(QObject):
        record_saved = Signal(dict)

        def reload_defaults(self):
            pass

    class _Filters(QWidget):
        def __init__(self):
            super().__init__()
            self.species_edit = QLineEdit(self)

        def clear_filters(self):
            self.cleared = True

        def set_order_filter(self, name):
            self.order = name

        def set_family_filter(self, name):
            self.family = name

    class _Toolbar(QWidget):
        def __init__(self):
            super().__init__()
            self.filter_btn = QCheckBox(self)

        def set_filters_visible(self, v):
            pass

    class Base(QWidget):
        navigate_to_observations = Signal(str)
        navigate_to_collection = Signal(str)
        data_imported = Signal()
        data_changed = Signal()
        records_changed = Signal()
        log = []

        def __init__(self, *a, **k):
            super().__init__()
            self.calls = []
            self.filter_bar = _Filters()
            self.filters = self.filter_bar
            self.toolbar = _Toolbar()

        def apply_theme(self):
            self.calls.append("theme")

        def refresh_display_settings(self):
            self.calls.append("display")

    class Home(Base):
        def __init__(self, *a, **k):
            super().__init__()
            self.quick_entry = _QuickEntry()

        def initialize(self):
            self.calls.append("init")

        def refresh_data(self):
            self.calls.append("refresh")

    class Obs(Base):
        def initialize(self):
            self._obs_initialized = True
            self.calls.append("init")
            self._all_observations = []

        def refresh(self):
            self.calls.append("refresh")

        def _apply_current_filters(self):
            self.calls.append("filters")

        def show_species(self, name):
            # what the real tab does: needs its records
            assert getattr(self, "_obs_initialized", False), "filtered before it loaded"
            self.calls.append(("species", name))

        def show_new_species_list(self):
            self.calls.append("new species")

        def clear_wizard_filters(self):
            pass

    class Contributed(Base):
        def initialize(self):
            self.calls.append("init")

    class Scheme(Base):
        _initialized = False

        def initialize(self, *a):
            self._initialized = True
            self.calls.append("init")

        def worker_error(self):
            return None

        def start_preload(self, path):
            self.calls.append("preload")

        def refresh(self):
            self.calls.append("refresh")

        def show_species(self, name):
            assert self._initialized, "filtered before it was set up"
            self.calls.append(("species", name))

    class Collection(Base):
        def initialize(self, *a):
            self._ic_initialized = True
            self.calls.append("init")

        def clear_wizard_filters(self):
            pass

    class Stats(Base):
        navigate_to_order = Signal(str)
        navigate_to_month = Signal(int)
        navigate_to_family = Signal(str)
        navigate_to_year = Signal(int)
        filter_collection_by_order = Signal(str)
        filter_collection_by_family = Signal(str)
        filter_collection_by_year = Signal(str)
        filter_collection_by_condition = Signal(str)
        filter_collection_by_prep_type = Signal(str)
        filter_collection_by_storage = Signal(str)
        show_specimen_detail = Signal(int)
        navigate_to_scheme = Signal(str)
        navigate_to_scheme_taxon = Signal(str)      # r4_records (Species lookup)
        navigate_to_scheme_vc = Signal(str, int)
        navigate_to_scheme_record = Signal(int)
        built = 0

        def __init__(self, *a, **k):
            super().__init__()
            type(self).built += 1

        def initialize(self, *a):
            self.calls.append("init")

        def refresh(self):
            self.calls.append("refresh")

        def mark_stale(self):
            self.calls.append("stale")

    class Mapping(Base):
        built = 0

        def __init__(self, *a, **k):
            super().__init__()
            type(self).built += 1

    class Settings(Base):
        settings_changed = Signal()

        def __init__(self, *a, **k):
            super().__init__()

        def initialize(self):
            self.calls.append("init")

    return dict(Home=Home, Obs=Obs, Contributed=Contributed, Scheme=Scheme,
                Collection=Collection, Stats=Stats, Mapping=Mapping, Settings=Settings)


@pytest.fixture
def window(qapp, monkeypatch):
    import src.views.main_window as mw
    import src.views.stats as stats_pkg
    import src.views.mapping as mapping_pkg
    import src.views.settings as settings_pkg
    import DataEntry.embed as de_embed

    f = _fakes()
    monkeypatch.setattr(mw, "HomeTab", f["Home"])
    monkeypatch.setattr(mw, "ObservationTab", f["Obs"])
    monkeypatch.setattr(mw, "ContributedTab", f["Contributed"])
    monkeypatch.setattr(mw, "RecordingSchemeTab", f["Scheme"])
    monkeypatch.setattr(mw, "InsectCollectionTab", f["Collection"])
    monkeypatch.setattr(stats_pkg, "StatsReportsTab", f["Stats"])
    monkeypatch.setattr(mapping_pkg, "MappingTab", f["Mapping"])
    monkeypatch.setattr(settings_pkg, "SettingsTab", f["Settings"])

    def no_de(**k):
        raise RuntimeError("not in this test")
    monkeypatch.setattr(de_embed, "make_data_entry_tab", no_de)
    monkeypatch.setattr(mw.MainWindow, "_initialize_services", lambda self: None)
    import src.views.main_window as m2
    monkeypatch.setattr(m2, "get_database", lambda: None)

    w = mw.MainWindow()
    w.connect_tab_signal()
    yield w, f
    w.deleteLater()


def test_lazy_tabs_not_built_at_startup(window):
    """The MainWindow constructor alone builds and reads nothing more (MainWindow.preload,
    under the splash screen, does: test_loading_r5)."""
    w, f = window
    assert w.stats_reports_tab is None and w.mapping_tab is None and w.settings_tab is None
    assert f["Stats"].built == 0 and f["Mapping"].built == 0
    # the data tabs exist (other code reaches into them) but have not read records
    assert "init" not in w.observation_tab.calls
    assert "init" not in w.recording_scheme_tab.calls
    assert "init" not in w.insect_collection_tab.calls
    names = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    assert names[-3:] == ["Stats/Reports", "Mapping", "Settings"]


def test_opening_lazy_tab_builds_it_once_and_initialises(window):
    w, f = window
    w.tabs.setCurrentWidget(w._stats_page)
    assert w.stats_reports_tab is not None and f["Stats"].built == 1
    assert w.stats_reports_tab.calls[:2] == ["theme", "init"]
    w.tabs.setCurrentIndex(0)
    w.tabs.setCurrentWidget(w._stats_page)
    assert f["Stats"].built == 1                      # built once
    assert w.stats_reports_tab.calls.count("refresh") == 1   # refreshed on each later visit
    w.tabs.setCurrentWidget(w._mapping_page)
    assert f["Mapping"].built == 1 and w._mapping_page.page is w.mapping_tab
    w.tabs.setCurrentWidget(w._settings_page)
    assert w.settings_tab.calls == ["theme", "init"]


def test_stats_view_records_into_unopened_observation_tab(window):
    """'View records' on Stats when Observation Data has never been opened: the tab
    reads its records first, then shows the species."""
    w, f = window
    w.tabs.setCurrentWidget(w._stats_page)
    obs = w.observation_tab
    assert not w._observations_loaded()
    w.stats_reports_tab.navigate_to_observations.emit("Rutpela maculata")
    assert w.tabs.currentWidget() is obs
    assert obs.calls.index("init") < obs.calls.index(("species", "Rutpela maculata"))


def test_stats_navigation_to_scheme_and_collection_initialises_them(window):
    w, f = window
    w.tabs.setCurrentWidget(w._stats_page)
    w.stats_reports_tab.navigate_to_collection.emit("")
    assert w.tabs.currentWidget() is w.insect_collection_tab
    assert "init" in w.insect_collection_tab.calls
    w.recording_scheme_tab._load_data = lambda filters=None: w.recording_scheme_tab.calls.append(("load", filters))
    w.stats_reports_tab.navigate_to_scheme.emit("Rhagium mordax")
    rs = w.recording_scheme_tab
    assert w.tabs.currentWidget() is rs
    assert rs.calls.index("init") < rs.calls.index(("load", {"species": "Rhagium mordax", "species_exact": True}))


def test_species_lookup_scheme_button_into_unopened_scheme_tab(window):
    """Species lookup "View N scheme records" (r4_records) with Stats built on first
    opening (r4_startup): the Scheme tab is set up before the species is shown."""
    w, f = window
    w.tabs.setCurrentWidget(w._stats_page)
    rs = w.recording_scheme_tab
    w.stats_reports_tab.navigate_to_scheme_taxon.emit("Leiopus linnei/nebulosus")
    assert w.tabs.currentWidget() is rs
    assert rs.calls.index("init") < rs.calls.index(("species", "Leiopus linnei/nebulosus"))


def test_scheme_dashboard_signal_connected_when_stats_built(window, qapp):
    from PySide6.QtCore import QObject, Signal

    class Dash(QObject):
        data_filters_changed = Signal()

    w, f = window
    orig_init = f["Stats"].__init__

    def init_with_dash(self, *a, **k):
        orig_init(self)
        self.scheme_dashboard = Dash()
    f["Stats"].__init__ = init_with_dash
    try:
        w.tabs.setCurrentWidget(w._stats_page)
    finally:
        f["Stats"].__init__ = orig_init
    w.stats_reports_tab.scheme_dashboard.data_filters_changed.emit()
    assert "refresh" in w.recording_scheme_tab.calls


def test_changes_before_tabs_opened_do_not_load_them(window):
    """A save / settings change / counting change before Observation Data or Stats has been
    opened must not read their records (they read fresh ones when opened)."""
    w, f = window
    w._on_record_saved({})
    w._on_settings_changed()
    w._on_counting_changed("observations")
    w._mark_data_changed()
    obs = w.observation_tab
    assert "refresh" not in obs.calls and "filters" not in obs.calls and "init" not in obs.calls
    assert w.stats_reports_tab is None
    # once opened, they follow changes again
    w.tabs.setCurrentWidget(obs)
    w._on_record_saved({})
    w._on_counting_changed("observations")
    assert "refresh" in obs.calls and "filters" in obs.calls
    w.tabs.setCurrentWidget(w._stats_page)
    w._mark_data_changed()
    assert "stale" in w.stats_reports_tab.calls


def test_settings_changed_signal_wired_when_settings_built(window):
    w, f = window
    w.tabs.setCurrentWidget(w._settings_page)
    w.home_tab.calls.clear()
    w.settings_tab.settings_changed.emit()
    assert "refresh" in w.home_tab.calls


def test_ensure_tab_builds_on_request(window):
    w, f = window
    t = w.ensure_tab("mapping_tab")
    assert t is w.mapping_tab and f["Mapping"].built == 1
    assert w.ensure_tab("observation_tab") is w.observation_tab


def test_lazy_page_builds_when_shown(qapp):
    from PySide6.QtWidgets import QLabel
    from src.views.lazy_tab import LazyTabPage
    made = []
    page = LazyTabPage(lambda: made.append(1) or QLabel("real"), "Thing")
    assert not page.is_built
    page.show()
    assert page.is_built and made == [1]
    assert page.ensure_built().text() == "real" and made == [1]
    page.close()


def test_startup_does_not_import_pandas_or_lazy_tabs():
    """Importing the main window (what startup does) leaves pandas, the Mapping tab and
    the Stats tab unimported. Run in a fresh interpreter."""
    code = ("import sys, paths; import src.views.main_window; "
            "print(sorted(m for m in ('pandas', 'src.views.mapping.mapping_tab', "
            "'src.views.stats.stats_reports_tab', 'src.views.main_window') if m in sys.modules))")
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([ROOT, os.path.join(ROOT, "Observatum")]),
               QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                         env=env, cwd=ROOT, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "['src.views.main_window']"


def test_lazy_pandas_works_in_validation_worker():
    import src.views.dialogs.observation_import_wizard.validation_worker as vw
    df = vw.pd.DataFrame([{"a": 1}])
    assert len(df) == 1 and vw.pd.isna(None)


def test_timing_flag(monkeypatch, capsys):
    import src.startup_timing as st
    monkeypatch.setattr(st, "_timer", None)
    monkeypatch.setattr(sys, "argv", ["x", "--timing"])
    t = st.timer()
    t.mark("phase one")
    assert "phase one" in capsys.readouterr().out
    monkeypatch.setattr(st, "_timer", None)
    monkeypatch.setattr(sys, "argv", ["x"])
    monkeypatch.delenv("OBSERVATUM_TIMING", raising=False)
    st.timer().mark("quiet")
    assert capsys.readouterr().out == ""
