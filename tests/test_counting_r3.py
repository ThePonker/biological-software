"""Counting decisions of 11 Oct 2026 (Round 3 wave 2, ROUND9_ITEMS "Decisions raised by the build").

D1 Commercial Reports' project species counts follow the species-counting switches
   (records stay every record).
D2 Species-list dialogs from the Personal / Commercial / All stats dashboards roll
   subspecies (and s.s.) up into their species, as the cards count them.
D3 Scheme month charts leave out year-only, month-only and range dates (date_type != 'D'),
   as the observation month charts do.
D4 The tabs' species search treats a slash pair ("Leiopus linnei/nebulosus") as an
   aggregate asked for by name, as it does "agg." / "s.l.".

Tests use small temp databases, or a copy of data/observatum.db (skipped when absent);
figures are recomputed independently rather than hard-coded, so they hold on Wil's PC.
"""
import os
import sqlite3
from collections import defaultdict
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402
import shared.species_counting as sc  # noqa: E402

DB = paths.OBSERVATUM_DB
needs_data = pytest.mark.skipif(not os.path.exists(DB), reason="no data/observatum.db")
needs_uksi = pytest.mark.skipif(not os.path.exists(paths.UKSI_DB), reason="no data/uksi.db")

SUBSP, ITS_SPECIES = "NHMSYS0021143933", "NHMSYS0000519763"   # a subspecies TVK -> its species


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def settings(qapp):
    """QSettings isolated; the module's caches and default database restored after."""
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("counting_r3")
    QSettings().clear()
    old_default = sc._default_db
    sc.invalidate()
    yield QSettings()
    QSettings().clear()
    sc._default_db = old_default
    sc.invalidate()
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


@pytest.fixture
def on_copy(settings, tmp_path, monkeypatch):
    """A private copy of the data copy, set as the app's database."""
    if not os.path.exists(DB):
        pytest.skip("no data/observatum.db")
    dst = str(tmp_path / "observatum.db")
    src = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    src.backup(out)
    out.close()
    src.close()
    from src.models.database import get_database
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(dst)
    db.set_uksi_path(str(paths.UKSI_DB))
    monkeypatch.setattr(paths, "OBSERVATUM_DB", dst)
    sc.set_default_db(dst)
    yield dst
    db._main_db_path, db._uksi_db_path = old


# ================================================================== D1 Commercial Reports

def _commercial_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, "
              "taxon_rank TEXT, species_tvk TEXT, record_type TEXT, date TEXT, date_type TEXT, "
              "project_name TEXT, client TEXT, embargo_status TEXT, embargo_until TEXT, "
              "site_name TEXT)")
    rows = [
        ("Rutpela maculata", "Species", "NBNSYS0000010849"),
        ("Rutpela maculata", "Species", "NBNSYS0000010849"),
        ("Leiopus", "Genus", "G1"),                               # genus only: left out
        ("Some subspecies", "Subspecies", SUBSP),                 # rolls up ...
        ("Its species", "Species", ITS_SPECIES),                  # ... into this one
        ("Oligia strigilis agg.", "Species aggregate", "AGG1"),   # aggregate: left out
    ]
    c.executemany("INSERT INTO observations (species_name, taxon_rank, species_tvk, record_type, "
                  "date, project_name, client, embargo_status, embargo_until, site_name) "
                  "VALUES (?, ?, ?, 'Commercial', '2025-06-01', 'P1', 'C1', 'Active', '2099-01-01', "
                  "'Wood')", rows)
    c.commit()
    c.close()
    return path


def _table_rows(table):
    return [[table.item(r, c).text() if table.item(r, c) else ""
             for c in range(table.columnCount())] for r in range(table.rowCount())]


@needs_uksi
def test_d1_commercial_reports_species_follow_switches(settings, tmp_path, monkeypatch):
    from src.views.stats import commercial_reports_dashboard as mod
    path = _commercial_db(str(tmp_path / "observatum.db"))
    monkeypatch.setattr(mod, "get_database", lambda: SimpleNamespace(get_main_path=lambda: path))
    d = mod.CommercialReportsDashboard()
    d.refresh()
    row = _table_rows(d._table)[0]
    assert row[0] == "P1" and row[2] == "6"           # records: all six
    assert row[3] == "2"                              # species: Rutpela + the rolled-up one
    d._show_project("P1", "C1")
    assert _table_rows(d._detail_table)[0][2:4] == ["6", "2"]
    assert d._detail_summary.text().startswith("6 records, 2 species")
    sc.set_excluded("observations", [])               # switches off: every kind counts
    d.refresh()
    assert _table_rows(d._table)[0][2:4] == ["6", "4"]   # subspecies still rolled up


@needs_data
@needs_uksi
def test_d1_on_the_data_copy(on_copy, monkeypatch):
    """Every project's Species = distinct rolled-up TVKs of its counted records; Records = all."""
    from src.views.stats import commercial_reports_dashboard as mod
    monkeypatch.setattr(mod, "get_database", lambda: SimpleNamespace(get_main_path=lambda: on_copy))
    excl = sc.excluded_ids(on_copy, "observations")
    roll = sc.species_key_map(on_copy, "observations")
    want = defaultdict(lambda: [0, set()])
    for i, p, cl, st, u, t in sqlite3.connect(on_copy).execute(
            "SELECT id, project_name, client, embargo_status, embargo_until, species_tvk "
            "FROM observations WHERE record_type = 'Commercial'"):
        k = (p or "(no project)", cl or "", u or "")
        want[k][0] += 1
        if t and i not in excl:
            want[k][1].add(roll.get(t, t))
    d = mod.CommercialReportsDashboard()
    d.refresh()
    got = defaultdict(lambda: [0, 0])
    for r in _table_rows(d._table):
        got[(r[0], r[1], r[5])][0] += int(r[2])
        got[(r[0], r[1], r[5])][1] = int(r[3])
    assert got and {k: v[0] for k, v in got.items()} == {k: v[0] for k, v in want.items()}
    assert {k: v[1] for k, v in got.items()} == {k: len(v[1]) for k, v in want.items()}


# ================================================================== D2 species-list dialogs

def test_d2_rolled_species_list_merges_subspecies_and_ss():
    from src.views.stats.species_list_dialogs import rolled_species_list
    rows = [
        {"species_name": "Epirrhoe alternata alternata", "species_tvk": SUBSP, "n": 5,
         "first_date": "2014-05-01", "last_date": "2020-07-01"},
        {"species_name": "Epirrhoe alternata", "species_tvk": ITS_SPECIES, "n": 2,
         "first_date": "2016-06-01", "last_date": "2023-08-01"},
        {"species_name": "Bombus terrestris s.s.", "species_tvk": "BT", "n": 3,
         "first_date": "2019-04-01", "last_date": "2019-04-02"},
        {"species_name": "Neobulgaria pura var. pura", "species_tvk": "VAR1", "n": 1,
         "first_date": "2018-10-01", "last_date": "2018-10-01"},
        {"species_name": "Neobulgaria pura var. foliacea", "species_tvk": "VAR2", "n": 4,
         "first_date": "2017-10-01", "last_date": "2017-10-01"},
    ]
    roll = {SUBSP: ITS_SPECIES, "VAR1": "NB", "VAR2": "NB"}
    uksi = SimpleNamespace(execute_uksi=lambda q, p: [("NB", "Neobulgaria pura")])
    got = {r["species_name"]: r for r in rolled_species_list(rows, roll, uksi)}
    assert set(got) == {"Epirrhoe alternata", "Bombus terrestris", "Neobulgaria pura"}
    assert (got["Epirrhoe alternata"]["first_date"], got["Epirrhoe alternata"]["last_date"]) == \
        ("2014-05-01", "2023-08-01")
    assert got["Neobulgaria pura"]["first_date"] == "2017-10-01"
    # no UKSI: the most-recorded subspecies name stands in
    got = {r["species_name"] for r in rolled_species_list(rows, roll, None)}
    assert "Neobulgaria pura var. foliacea" in got


@pytest.fixture
def no_exec(monkeypatch):
    from src.views.dialogs import species_list_dialog as m
    monkeypatch.setattr(m.SpeciesListDialog, "exec", lambda self: 0)


def _stats(on_copy):
    from src.models.database import get_database
    from src.services.observation_stats_service import get_observation_stats_service
    svc = get_observation_stats_service()
    svc.initialize(get_database())
    svc.invalidate()
    return svc.get_all()


def _listed(dash, call, *args):
    dash._species_list_dialog = None
    call(*args)
    dlg = dash._species_list_dialog
    return [] if dlg is None else [r["species_name"] for r in dlg._species_data]


@needs_data
@needs_uksi
@pytest.mark.parametrize("cls_name, prefix", [
    ("personal_dashboard.PersonalStatsDashboard", "personal_"),
    ("commercial_dashboard.CommercialStatsDashboard", "commercial_"),
    ("all_stats_dashboard.AllStatsDashboard", ""),
])
def test_d2_lists_match_their_cards(on_copy, no_exec, cls_name, prefix):
    import importlib
    mod_name, cls = cls_name.split(".")
    mod = importlib.import_module(f"src.views.stats.{mod_name}")
    dash = getattr(mod, cls)()
    stats = _stats(on_copy)
    yearly = stats[f"{prefix}yearly_stats"]
    assert yearly
    for year, v in yearly.items():
        names = _listed(dash, dash._show_species_for_year, year)
        assert len(names) == v["species"], (year, len(names), v["species"])
        assert len(_listed(dash, dash._show_new_species_for_year, year)) == v["newSpecies"], year
    months = stats.get(f"{prefix}monthly_species_counts") or stats["monthly_species_counts"]
    for m in range(1, 13):
        assert len(_listed(dash, dash._show_species_for_month, m)) == months[m - 1], m
    for o in stats[f"{prefix}species_by_order"]:
        assert len(_listed(dash, dash._show_species_for_group, "order_name", o["label"],
                           "x")) == o["species"], o["label"]


@needs_data
@needs_uksi
def test_d2_subspecies_listed_once(on_copy, no_exec):
    """Anthocharis cardamines and A. c. britannica: one row on the Personal lists."""
    from src.views.stats.personal_dashboard import PersonalStatsDashboard
    dash = PersonalStatsDashboard()
    c = sqlite3.connect(on_copy)
    names = {r[0] for r in c.execute("SELECT DISTINCT species_name FROM observations WHERE "
                                     "record_type='Personal' AND species_name LIKE 'Anthocharis cardamines%'")}
    if len(names) < 2:
        pytest.skip("no subspecies records for the example")
    listed = _listed(dash, dash._show_species_for_group, "order_name", "Lepidoptera", "x")
    assert "Anthocharis cardamines" in listed
    assert not [n for n in listed if n.startswith("Anthocharis cardamines ")]


# ================================================================== D3 scheme month charts

def _scheme_svc():
    from src.models.database import get_database
    from src.services.recording_scheme_stats_service import RecordingSchemeStatsService
    svc = RecordingSchemeStatsService()
    svc.initialize(get_database())
    svc.invalidate()
    return svc


def _months(conn, where="", params=()):
    """Hand monthly counts, each record once: the marked NBN copies of iRecord records left
    out by THE rule (shared/scheme_duplicates.live_sql; '' without the column)."""
    from shared.scheme_duplicates import live_sql
    q = (f"SELECT CAST(strftime('%m', date) AS INTEGER), COUNT(*) FROM recording_scheme "
         f"WHERE date IS NOT NULL {where}{live_sql(conn)} GROUP BY 1")
    d = dict(conn.execute(q, params).fetchall())
    return [d.get(m, 0) for m in range(1, 13)]


@needs_data
def test_d3_scheme_month_charts_skip_vague_dates(on_copy):
    c = sqlite3.connect(on_copy)
    day = "AND COALESCE(date_type, 'D') = 'D'"
    svc = _scheme_svc()
    got = svc.get("monthly_counts")
    assert got == _months(c, day)
    from shared.scheme_duplicates import live_sql
    copies = live_sql(c)
    vague = c.execute("SELECT COUNT(*) FROM recording_scheme WHERE COALESCE(date_type,'D') != 'D' "
                      "AND date IS NOT NULL AND strftime('%m', date) IS NOT NULL"
                      + copies).fetchone()[0]
    assert sum(_months(c)) - sum(got) == vague
    # a VC's Records Over Time chart
    vc = c.execute("SELECT vc_number FROM recording_scheme WHERE date_type != 'D' "
                   f"AND vc_number IS NOT NULL{copies} GROUP BY 1 ORDER BY COUNT(*) DESC").fetchone()
    if vc:
        assert svc.get_vc_details(vc[0])["monthly_records"] == _months(
            c, day + " AND vc_number = ?", (vc[0],))
    # the chart's species picker (not built on screen yet; the method it calls was missing)
    sp = c.execute(f"SELECT species_name FROM recording_scheme WHERE date_type != 'D'{copies} "
                   "GROUP BY 1 ORDER BY COUNT(*) DESC").fetchone()[0]
    assert svc.get_monthly_counts_by_species(sp) == _months(c, day + " AND species_name = ?", (sp,))
    assert sum(svc.get_monthly_counts_by_species(sp)) < sum(_months(c, "AND species_name = ?", (sp,)))


@needs_data
@needs_uksi
def test_d3_lookup_phenology_bar_equals_month_dialog(on_copy):
    """Species lookup: the scheme part of the phenology bars skips vague dates, and the
    month dialog lists exactly the bar's records."""
    from src.models.database import get_database
    from src.views.stats.month_records_dialog import month_records
    from src.views.stats.species_dashboard import SpeciesDashboard
    c = sqlite3.connect(on_copy)
    sp, m = c.execute("SELECT species_name, CAST(strftime('%m', date) AS INTEGER) FROM recording_scheme "
                      "WHERE date_type IN ('O','DD') GROUP BY 1, 2 ORDER BY COUNT(*) DESC").fetchone()
    d = SpeciesDashboard.__new__(SpeciesDashboard)
    d._db = get_database()
    bars = d._get_phenology_data(sp)
    rows = month_records(lambda q, p: d._db.execute_main(q, p), d._by_species, sp, m, d._counted)
    assert len(rows) == bars[m - 1]
    ids = {r["id"] for r in rows if r["table"] == "recording_scheme"}
    vague = {r[0] for r in c.execute("SELECT id FROM recording_scheme WHERE species_name = ? "
                                     "AND date_type != 'D'", (sp,))}
    assert vague and not ids & vague


# ================================================================== D4 slash pairs in the tabs' search

LEIOPUS = "Leiopus linnei/nebulosus"


def test_d4_kinds_for_search_reads_slash_pairs(settings):
    on = {"genus", "family_plus", "agg", "sl"}
    assert sc.kinds_for_search("observations", LEIOPUS) == {"genus", "family_plus"}
    # unchanged: agg. / s.l. (also the looser endings), and plain names
    for text in ("Oligia strigilis agg.", "Bombus lucorum AGG", "Bombus lucorum s.l",
                 "Xanthogramma pedissequum s.l.", "Bombus lucorum sensu lato"):
        assert sc.kinds_for_search("observations", text) == {"genus", "family_plus"}, text
    for text in ("", None, "Oligia", "Leiopus", "Leiopus nebulosus", "Bombus terrestris s.s."):
        assert sc.kinds_for_search("observations", text) == on, text
    sc.set_excluded("recording_scheme", ["agg", "hybrid"])
    assert sc.kinds_for_search("recording_scheme", LEIOPUS) == {"hybrid"}


@needs_data
@needs_uksi
def test_d4_lookup_and_tabs_agree_for_leiopus(on_copy):
    from src.models.database import get_database
    from src.views.observations.observation_tab import ObservationTab
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    from src.views.stats.species_dashboard import SpeciesDashboard
    u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    tvk, rank = u.execute("SELECT tvk, rank FROM taxa WHERE scientific_name = ?", (LEIOPUS,)).fetchone()
    u.close()
    obs = ObservationTab()
    obs.initialize()
    for scheme_kinds in ([], ["agg"]):                   # scheme defaults, then Aggregate off
        sc.set_excluded("recording_scheme", scheme_kinds)
        d = SpeciesDashboard()
        d._db = get_database()
        r = SimpleNamespace(scientific_name=LEIOPUS, tvk=tvk, common_name=None, family="Cerambycidae",
                            order_name="Coleoptera", old_name=None, match_type="exact", rank=rank)
        d._search_results = [r]
        d._on_completer_activated(d._display(r))
        n_obs, n_scheme = d._selected_species["observationRecords"], d._selected_species["schemeRecords"]
        assert n_obs > 0 and n_scheme > 0
        obs.show_species(LEIOPUS)                         # what "View N records" does
        assert len(obs._counted(obs.table_model._observations)) == n_obs
        assert f"{n_obs:,}" in obs.toolbar.count_label.text()
        f = {"species": LEIOPUS}
        f["_counting_kinds"] = RecordingSchemeTab._counting_kinds(None, f)
        w = SchemeDataWorker(on_copy, f)
        w.run()
        assert w.counted == n_scheme == len(w.results[0])
