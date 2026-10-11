"""Round 4 records items, 11 Oct 2026.

1. Stats > Species lookup "View N scheme records": opens the Recording Scheme tab on the
   taxon, and the tab counts the records the lookup counted (Scheme Aggregate switch on
   and off; a slash-pair aggregate and ordinary species).
2. 1 January placeholder dates: scripts/_oneoff/fix_jan1_dates_20261011.py and the
   scheme importer's date precision.
"""
import os
import sqlite3
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402
import shared.species_counting as sc  # noqa: E402

needs_data = pytest.mark.skipif(not os.path.exists(paths.OBSERVATUM_DB),
                                reason="no data/observatum.db")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("records_r4")
    QSettings().clear()
    old_default = sc._default_db
    sc.invalidate()
    yield QSettings()
    QSettings().clear()
    sc._default_db = old_default
    sc.invalidate()
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


# ------------------------------------------------------------------ 1. scheme button

class _Db:
    def __init__(self, path):
        self.main_db_path = str(path)
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)

    def execute_main(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()


def _lookup(db, name, tvk, rank, family="Cerambycidae"):
    from src.views.stats.species_dashboard import SpeciesDashboard
    d = SpeciesDashboard()
    d._db = db
    r = SimpleNamespace(scientific_name=name, tvk=tvk, common_name=None, family=family,
                        order_name="Coleoptera", old_name=None, match_type="exact", rank=rank)
    d._search_results = [r]
    d._on_completer_activated(d._display(r))
    return d


def _tab_count(db_path, name, monkeypatch):
    """What the Recording Scheme tab counts after show_species(name), run synchronously."""
    import src.views.scheme.recording_scheme_tab as rst

    class SyncWorker(rst.SchemeDataWorker):
        def start(self):
            self.run()

    monkeypatch.setattr(rst, "SchemeDataWorker", SyncWorker)
    tab = rst.RecordingSchemeTab()
    tab._main_db_path = str(db_path)
    tab._preload_started = True
    tab._initialized = True                      # filter bar ready; no database set-up
    monkeypatch.setattr(tab, "_on_data_loaded", lambda *a, **k: None)
    tab.show_species(name)
    assert tab.filter_bar.species_edit.text() == name
    records, _n, dimmed, counted = tab.take_worker_results()
    tab._poll_timer.stop()
    return counted


def _small_db(tmp_path):
    p = tmp_path / "o.db"
    conn = sqlite3.connect(p)
    for t in ("observations", "specimens", "recording_scheme"):
        conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY, species_tvk TEXT, "
                     "species_name TEXT, taxon_rank TEXT, common_name TEXT, record_type TEXT, "
                     "family TEXT, date TEXT, date_type TEXT)")
    rows = ([("NHMSYS0021478843", "Leiopus linnei/nebulosus", "Species aggregate")] * 4
            + [("NHMSYS0021478843", "Leiopus linnei/nebulosus agg.", "Species")] * 2
            + [("NHMSYS0021125200", "Leiopus nebulosus", "Species")] * 3)
    conn.executemany("INSERT INTO recording_scheme (species_tvk, species_name, taxon_rank, "
                     "family, date) VALUES (?, ?, ?, 'Cerambycidae', '2024-05-01')", rows)
    conn.commit()
    conn.close()
    return p


def test_scheme_button_hidden_when_none(settings, tmp_path):
    db = _Db(_small_db(tmp_path))
    d = _lookup(db, "Rhagium mordax", "NBNSYS0000011004", "Species")
    assert d._selected_species["schemeTabRecords"] == 0
    assert getattr(d, "_scheme_btn", None) is None


def test_scheme_button_emits_and_counts(settings, tmp_path, monkeypatch):
    path = _small_db(tmp_path)
    db = _Db(path)
    sc.set_excluded("recording_scheme", ["agg"])
    d = _lookup(db, "Leiopus linnei/nebulosus", "NHMSYS0021478843", "Species aggregate")
    assert d._scheme_btn.text() == "View 6 scheme records"
    got = []
    d.navigate_to_scheme.connect(got.append)
    d._scheme_btn.click()
    assert got == ["Leiopus linnei/nebulosus"]
    assert _tab_count(path, got[0], monkeypatch) == 6
    # the scheme families setting limits the tab, so the button says what the tab shows
    settings.setValue("scheme/families", "Carabidae")
    d = _lookup(db, "Leiopus linnei/nebulosus", "NHMSYS0021478843", "Species aggregate")
    assert d._selected_species["schemeRecords"] == 6
    assert getattr(d, "_scheme_btn", None) is None


@needs_data
@pytest.mark.parametrize("agg_off", [False, True])
@pytest.mark.parametrize("name,tvk,rank", [
    ("Leiopus linnei/nebulosus", "NHMSYS0021478843", "Species aggregate"),
    ("Leiopus nebulosus", "NHMSYS0021125200", "Species"),
    ("Rhagium mordax", "NBNSYS0000011004", "Species"),
])
def test_lookup_and_tab_agree_on_copy(settings, monkeypatch, agg_off, name, tvk, rank):
    sc.set_excluded("recording_scheme", ["agg"] if agg_off else [])
    db = _Db(paths.OBSERVATUM_DB)
    d = _lookup(db, name, tvk, rank)
    n = d._selected_species["schemeRecords"]
    assert n > 0 and d._selected_species["schemeTabRecords"] == n
    assert d._scheme_btn.text() == f"View {n:,} scheme records"
    assert _tab_count(paths.OBSERVATUM_DB, name, monkeypatch) == n


# ------------------------------------------------------------------ 2. 1 January dates

def _kind(date_text, **cols):
    from shared.import_core import parse_record_date
    from src.views.dialogs.scheme_import_wizard.nbn_dates import nbn_date_kind
    p = parse_record_date(date_text)
    got = nbn_date_kind({"date": p.date, "date_type": p.date_type or "D", "_date_note": p.note,
                         "date_error": p.error}, date_text, cols.get("precision", ""),
                        cols.get("year", ""), cols.get("month", ""), cols.get("day", ""))
    return got["date"], got["date_type"]


@pytest.mark.parametrize("text, cols, want", [
    ("1985-01-01", {"precision": "Year"}, ("1985-01-01", "Y")),
    ("1985-06-01", {"precision": "MONTH"}, ("1985-06-01", "O")),
    ("1985-01-01", {"year": "1985"}, ("1985-01-01", "Y")),          # a year and no day
    ("1985-06-01", {"year": "1985", "month": "6"}, ("1985-06-01", "O")),
    ("1985-01-01/1985-12-31", {}, ("1985-01-01", "Y")),             # the whole year
    ("1980-01-01/1985-12-31", {}, ("1980-01-01", "YY")),
    ("1985-06-01/1985-06-30", {}, ("1985-06-01", "O")),
    ("1985-05-01/1985-05-15", {}, ("1985-05-01", "DD")),            # a real range stays
    ("1985-01-01", {}, ("1985-01-01", "D")),                         # nothing says otherwise
    ("1985-01-01", {"year": "1985", "month": "1", "day": "1"}, ("1985-01-01", "D")),
    ("1985-01-01", {"precision": "Day"}, ("1985-01-01", "D")),
    ("1985-06-03", {"precision": "Year"}, ("1985-06-03", "D")),      # disagree: not guessed
])
def test_nbn_date_kind(text, cols, want):
    assert _kind(text, **cols) == want


def test_nbn_import_year_padded_to_1_january(qapp):
    from test_imports_20261010 import _scheme
    base = {"scientificName": "Rutpela maculata", "gridReference": "SP4433"}
    got = _scheme("NBN_ATLAS", [
        dict(base, eventDate="1985-01-01", year="1985"),
        dict(base, eventDate="1985-01-01", datePrecision="Year"),
        dict(base, eventDate="1985-01-01", eventDateEnd="1985-12-31"),
        dict(base, eventDate="2024-01-01", year="2024", month="1", day="1"),
        dict(base, eventDate="2024-05-01", eventDateEnd="2024-05-15")])
    assert [(r.date, r.date_type) for r in got] == [
        ("1985-01-01", "Y"), ("1985-01-01", "Y"), ("1985-01-01", "Y"), ("2024-01-01", "D"),
        ("2024-05-01", "DD")]
    assert "a year" in got[0].import_notes


def _fix_script():
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scripts", "_oneoff", "fix_jan1_dates_20261011.py")
    spec = importlib.util.spec_from_file_location("fix_jan1_dates_20261011", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _jan_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, dataset_name TEXT, "
                 "source TEXT, date TEXT, date_type TEXT, import_notes TEXT, updated_at TEXT)")
    rows = ([("Padded", "Padded", f"{1900 + i}-01-01", "D") for i in range(30)]
            + [("Padded", "Padded", "1990-01-15", "D")]
            + [(None, "Padded", "1950-01-01", None)]                     # source only, no type
            + [("Padded", "Padded", "1950-01-01", "Y")]                  # already a year
            + [("Padded", "Padded", "1950-06-01", "D")]                  # not January
            + [("Mid", "Mid", "2020-01-01", "D")] * 25                   # 12.5x: unclear
            + [("Mid", "Mid", f"2020-01-{d:02d}", "D") for d in range(2, 32)] * 2
            + [("Real", "Real", "2021-01-01", "D")] * 8                  # 4x: genuine
            + [("Real", "Real", f"2021-01-{d:02d}", "D") for d in range(2, 32)] * 2
            + [("Few", "Few", "1960-01-01", "D")] * 5)
    conn.executemany("INSERT INTO recording_scheme (dataset_name, source, date, date_type) "
                     "VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()


def test_fix_jan1_dates_script(tmp_path, capsys):
    mod = _fix_script()
    db = tmp_path / "o.db"
    _jan_db(db)
    assert mod.main(["--db", str(db), "--backup-dir", str(tmp_path / "bk")]) == 0
    out = capsys.readouterr().out
    assert "Nothing has been changed" in out and "records to change: 31" in out
    verdicts = {f["dataset"]: f["verdict"] for f in mod.survey(sqlite3.connect(db))}
    assert verdicts == {"Padded": "padding", "Mid": "unclear", "Real": "genuine",
                        "Few": "too few"}
    assert not (tmp_path / "bk").exists()                               # dry run: no backup

    assert mod.main(["--apply", "--db", str(db), "--backup-dir", str(tmp_path / "bk")]) == 0
    assert len(list((tmp_path / "bk").iterdir())) == 1
    conn = sqlite3.connect(db)
    got = dict(conn.execute("SELECT COALESCE(date_type, '-'), COUNT(*) FROM recording_scheme "
                            "WHERE source = 'Padded' GROUP BY 1").fetchall())
    assert got == {"Y": 32, "D": 2}                     # 31 changed + the one already Y
    assert conn.execute("SELECT COUNT(*) FROM recording_scheme WHERE date_type = 'Y' AND "
                        "import_notes LIKE '%D -> Y%'").fetchone()[0] == 31
    assert conn.execute("SELECT COUNT(*) FROM recording_scheme WHERE source <> 'Padded' AND "
                        "date_type <> 'D'").fetchone()[0] == 0
    assert conn.execute("SELECT date FROM recording_scheme WHERE id = 1").fetchone()[0] == "1900-01-01"
    conn.close()
    capsys.readouterr()
    assert mod.main(["--apply", "--db", str(db), "--backup-dir", str(tmp_path / "bk")]) == 0
    assert "nothing to do" in capsys.readouterr().out                   # idempotent


@needs_data
def test_fix_jan1_dates_dry_run_on_copy(capsys):
    mod = _fix_script()
    found = {f["dataset"]: f for f in mod.survey(
        sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True))}
    # Once fix_jan1_dates --apply has been run (Wil's PC, 11 Oct) these datasets no longer
    # have 1 January dates, so survey() does not list them: a listed one must be padding,
    # an absent one is the applied state
    for ds in ("Cerambycidae Dataset", "Invertebrate Site Register - England (1738-2005)",
               "Shropshire Ecological Data Network Database", "NBIS Records to December 2016",
               "National Trust Species Records", "Welsh Invertebrate Database (WID)"):
        if ds in found:
            assert found[ds]["verdict"] == "padding", ds
    longhorn = found.get("Longhorn beetle (Cerambycidae) data from iRecord")
    if longhorn is not None:                     # never changed by --apply (unclear)
        assert longhorn["verdict"] == "unclear"
    assert all(f["verdict"] in ("genuine", "too few")
               for name, f in found.items() if name.startswith("iRecord"))
