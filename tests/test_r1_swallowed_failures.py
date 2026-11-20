"""Round 1, items 9 and 10: failures that used to be swallowed are said; live reads are read-only.
Purpose-made databases and fake `self` objects only."""
import ast
import inspect
import sqlite3
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QLabel, QMessageBox

from tests.test_dataentry_r3 import qapp  # noqa: F401


class Bar:
    def __init__(self):
        self.msgs = []

    def showMessage(self, text, timeout=0):
        self.msgs.append(text)


@pytest.fixture
def warned(monkeypatch):
    seen = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: seen.append(a[2]))
    return seen


# -- main_window ---------------------------------------------------------------------------------
def test_stats_refresh_failure_is_shown(qapp):  # noqa: F811
    import src.views.main_window as mw
    stats = SimpleNamespace(refresh=lambda: (_ for _ in ()).throw(RuntimeError("stats broke")))
    fake = SimpleNamespace(_ready=True, _tab_pending_in_background=lambda i: False,
                           tabs=SimpleNamespace(widget=lambda i: stats), stats_reports_tab=stats,
                           _initialized_tabs={0}, statusbar=Bar())
    mw.MainWindow._on_tab_changed(fake, 0)
    assert any("stats broke" in m for m in fake.statusbar.msgs)


def _obs_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, x TEXT)")
    c.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, y TEXT)")
    c.execute("INSERT INTO observations (species_name) VALUES ('Rarus beetle')")
    c.commit()
    c.close()


def test_csv_backup_reports_failed_parts_and_reads_read_only(qapp, tmp_path, monkeypatch, warned):  # noqa: F811
    import paths
    import shared.db_open as dbo
    import src.views.main_window as mw
    obs = tmp_path / "obs.db"
    _obs_db(obs)
    bad = tmp_path / "examen.db"
    bad.write_bytes(b"this is not a database" * 50)
    good = tmp_path / "munia.db"
    _obs_db(good)
    monkeypatch.setattr(paths, "EXAMEN_DB", bad)
    monkeypatch.setattr(paths, "MUNIA_DB", good, raising=False)
    opened = []
    real = dbo.connect_ro
    monkeypatch.setattr(dbo, "connect_ro", lambda p, **k: opened.append(str(p)) or real(p, **k))
    out = tmp_path / "out"
    fake = SimpleNamespace(_main_db_path=str(obs), statusbar=Bar())
    before = obs.read_bytes()
    mw.MainWindow._export_csv_backups(fake, str(out))
    assert (out / "observations.csv").is_file() and (out / "munia.db").is_file()
    assert warned and "examen.db" in warned[0] and "munia.db" not in warned[0]
    assert str(obs) in opened and str(good) in opened and str(bad) in opened
    assert obs.read_bytes() == before


def test_csv_backup_all_good_says_nothing_wrong(qapp, tmp_path, monkeypatch, warned):  # noqa: F811
    import paths
    import src.views.main_window as mw
    obs = tmp_path / "obs.db"
    _obs_db(obs)
    ex = tmp_path / "examen.db"
    _obs_db(ex)
    monkeypatch.setattr(paths, "EXAMEN_DB", ex)
    monkeypatch.delattr(paths, "MUNIA_DB", raising=False)
    fake = SimpleNamespace(_main_db_path=str(obs), statusbar=Bar())
    mw.MainWindow._export_csv_backups(fake, str(tmp_path / "out"))
    assert not warned and any("CSV backup" in m for m in fake.statusbar.msgs)


def test_data_entry_wiring_failure_is_logged_and_shown(caplog):
    import src.views.main_window as mw

    class Sig:
        def connect(self, *a):
            raise RuntimeError("no signal")
    mwin = SimpleNamespace(data_entry_tab=SimpleNamespace(committed=Sig()), statusbar=Bar(),
                           _mark_data_changed=lambda: None)
    with caplog.at_level("ERROR"):
        mw._claude_wire_obs_refresh(mwin)
    assert any("no signal" in m for m in mwin.statusbar.msgs)
    assert "could not be wired" in caplog.text


# -- observation tab -----------------------------------------------------------------------------
def test_import_wizard_failing_to_open_is_a_warning(qapp, monkeypatch, warned):  # noqa: F811
    from src.views.observations import observation_tab as ot

    def boom(**k):
        raise RuntimeError("wizard broke")
    monkeypatch.setattr(ot, "ObservationImportWizard", boom)
    monkeypatch.setattr(ot, "get_database", lambda: None)
    fake = SimpleNamespace(_uksi_model=None, _observation_model=None)
    ot.ObservationTab._on_import_requested(fake)
    assert warned and "wizard broke" in warned[0]


# -- Data Entry "This workbook" ---------------------------------------------------------------
def test_workbook_summary_error_is_not_zero_figures(qapp):  # noqa: F811
    from DataEntry.entry_grid import EntryGridPage as EntryGrid
    from DataEntry.info_panel import InfoPanel

    class Conn:
        def execute(self, *a):
            raise sqlite3.OperationalError("database is locked")
    fake = SimpleNamespace(_conn=Conn(), _job_id=1)
    with pytest.raises(sqlite3.OperationalError):
        EntryGrid._workbook_summary(fake)
    title, cleared = QLabel("old"), []
    panel = SimpleNamespace(
        _wb_fn=lambda: EntryGrid._workbook_summary(fake), _wb_title=title,
        _clear_wb_grid=lambda: cleared.append(1))
    InfoPanel.refresh_workbook(panel)
    assert "could not be read" in title.text() and cleared
    assert "0 records" not in title.text()


# -- family detail panel -----------------------------------------------------------------------
def test_british_count_unreadable_is_not_zero(tmp_path):
    from src.views.collection.family_detail_panel import FamilyDetailPanel as P
    fake = SimpleNamespace(_british_species_cache={}, _uksi_db_path=str(tmp_path / "missing.db"))
    assert P._count_british(fake, "family", "Carabidae") is None
    assert "carabidae" not in str(fake._british_species_cache).lower()
    assert P._british_text(None) == "could not be read" and P._british_text(0) == "0"
    uksi = tmp_path / "uksi.db"
    c = sqlite3.connect(uksi)
    c.execute('CREATE TABLE taxa (family TEXT, superfamily TEXT, "order" TEXT, rank TEXT)')
    c.execute("INSERT INTO taxa VALUES ('Carabidae', NULL, NULL, 'Species')")
    c.commit()
    c.close()
    fake = SimpleNamespace(_british_species_cache={}, _uksi_db_path=str(uksi))
    assert P._count_british(fake, "family", "Carabidae") == 1


# -- settings tab ------------------------------------------------------------------------------
def test_settings_apply_theme_has_no_dead_statement():
    from src.views.settings.settings_tab import SettingsTab
    tree = ast.parse(inspect.getsource(SettingsTab.apply_theme).lstrip())
    dead = [n for n in ast.walk(tree) if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Attribute)]
    assert not dead


# -- item 10: commercial dashboard refresh is read-only and closes its connection --------------
def _dash(tmp_path, monkeypatch):
    from src.views.stats import commercial_reports_dashboard as crd
    db = tmp_path / "obs.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (record_type TEXT, project_name TEXT, client TEXT, "
              "embargo_status TEXT, embargo_until TEXT, species_tvk TEXT, date TEXT)")
    c.execute("INSERT INTO observations VALUES ('Commercial','P','C','Active','2099-01-01','t','2024-05-01')")
    c.commit()
    c.close()
    monkeypatch.setattr(crd, "get_database", lambda: SimpleNamespace(get_main_path=lambda: str(db)))
    monkeypatch.setattr(crd, "species_count_sql", lambda path, prefix="": "COUNT(DISTINCT species_tvk)")
    opened = []
    real = crd.connect_ro
    monkeypatch.setattr(crd, "connect_ro", lambda p, **k: opened.append(real(p, **k)) or opened[-1])
    return crd, db, opened


def test_dashboard_refresh_is_read_only_and_closed(qapp, tmp_path, monkeypatch):  # noqa: F811
    crd, db, opened = _dash(tmp_path, monkeypatch)
    w = crd.CommercialReportsDashboard()
    w.refresh()
    assert opened
    with pytest.raises(sqlite3.ProgrammingError):
        opened[-1].execute("SELECT 1")                 # closed
    with pytest.raises(sqlite3.OperationalError):
        sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute("DELETE FROM observations")


def test_dashboard_refresh_closes_even_when_it_fails(qapp, tmp_path, monkeypatch):  # noqa: F811
    crd, db, opened = _dash(tmp_path, monkeypatch)
    w = crd.CommercialReportsDashboard()
    opened.clear()
    monkeypatch.setattr(crd, "species_count_sql", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    w.refresh()
    assert opened
    with pytest.raises(sqlite3.ProgrammingError):
        opened[-1].execute("SELECT 1")
