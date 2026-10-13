"""Species-counting switches applied software-wide (backlog A, fault F45 / OBS-18), 10 Oct 2026.

One rule (shared/species_counting.py on shared/record_kinds.py), per source:
observations leave out genus / family+ / agg / s.l. by default and roll subspecies up to their
species; the Recording Scheme can leave out any of the seven kinds. Tables list every record
(the excluded ones dimmed; "Show only excluded" lists just them); Home, stats, Mapping, the
achievements and the Data Entry mini-map count only the rest. On the 9 Oct data copy:
observations 24,962 -> 24,785 counted (177 excluded), 3,161 species; scheme "agg" 1,933
(Leiopus linnei/nebulosus 1,813 + 120 named "agg.").
"""
import os
import sqlite3

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
    QCoreApplication.setApplicationName("counting_r2")
    QSettings().clear()
    old_default = sc._default_db
    sc.invalidate()
    yield QSettings()
    QSettings().clear()
    sc._default_db = old_default
    sc.invalidate()
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


def _small_db(path):
    c = sqlite3.connect(path)
    for table in ("observations", "recording_scheme"):
        c.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, species_name TEXT, "
                  "taxon_rank TEXT, species_tvk TEXT, record_type TEXT, date TEXT, "
                  "grid_ref TEXT, updated_at TEXT)")
    rows = [
        (1, "Rutpela maculata", "Species", "NBNSYS0000010849"),
        (2, "Leiopus", "Genus", "G1"),
        (3, "Leiopus sp.", None, None),
        (4, "Cerambycidae", "Family", "F1"),
        (5, "Oligia strigilis agg.", "Species aggregate", "NHMSYS0001703675"),
        (6, "Xanthogramma pedissequum", "Species sensu lato", "SL1"),
        (7, "Some subspecies", "Subspecies", SUBSP),
        (8, "Its species", "Species", ITS_SPECIES),
        (9, "Pipistrellus pipistrellus sensu stricto", "Species", "NHMSYS0020001355"),
        (10, "Pipistrellus pipistrellus", "Species", "NHMSYS0020001355"),
    ]
    for table in ("observations", "recording_scheme"):
        c.executemany(f"INSERT INTO {table} (id, species_name, taxon_rank, species_tvk, "
                      "record_type, date) VALUES (?, ?, ?, ?, 'Personal', '2024-06-01')", rows)
    c.commit()
    c.close()
    return path


# ------------------------------------------------------------------ settings

def test_defaults_and_migration(settings):
    assert sc.excluded_kinds("observations") == {"genus", "family_plus", "agg", "sl"}
    assert sc.excluded_kinds("recording_scheme") == frozenset()
    settings.setValue("display/exclude_incomplete_species", False)     # the old switch off
    settings.setValue("stats/scheme_exclude_family", True)              # old chips
    settings.setValue("stats/scheme_exclude_agg", True)
    assert sc.excluded_kinds("observations") == frozenset()
    assert sc.excluded_kinds("recording_scheme") == {"family_plus", "agg"}
    sc.set_excluded("observations", ["genus"])                          # new keys win
    assert sc.excluded_kinds("observations") == {"genus"}
    assert sc.OFFERED["observations"] == ("genus", "family_plus", "agg", "sl")
    assert "subsp" not in sc.OFFERED["observations"] and "ss" not in sc.OFFERED["observations"]
    assert len(sc.OFFERED["recording_scheme"]) == 7


def test_change_signal(settings):
    got = []
    sc.notifier().changed.connect(got.append)
    try:
        sc.set_excluded("recording_scheme", ["hybrid", "subsp"])
    finally:
        sc.notifier().changed.disconnect(got.append)
    assert got == ["recording_scheme"]
    assert sc.excluded_kinds("recording_scheme") == {"hybrid", "subsp"}


def test_aggregate_asked_for_by_name_counts(settings):
    assert sc.kinds_for_search("observations", "Oligia strigilis agg.") == {"genus", "family_plus"}
    assert sc.kinds_for_search("observations", "Oligia") == {"genus", "family_plus", "agg", "sl"}


# ------------------------------------------------------------------ the rule on a small database

@needs_uksi
def test_small_db_ids_sql_and_rollup(settings, tmp_path):
    db = _small_db(str(tmp_path / "observatum.db"))
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    assert sc.excluded_ids(conn, "observations") == {2, 3, 4, 5, 6}
    assert sc.excluded_reasons(conn, "observations")[3] == "Genus only"
    n = conn.execute("SELECT COUNT(*) FROM observations WHERE 1"
                     + sc.not_excluded_sql(conn, "observations")).fetchone()[0]
    assert n == 5
    only = conn.execute("SELECT COUNT(*) FROM observations WHERE 1"
                        + sc.only_excluded_sql(conn, "observations")).fetchone()[0]
    assert only == 5
    # subspecies rolled up, s.s. already on its species' TVK: 3 species, not 5
    sk = sc.species_key_sql(conn, "observations")
    assert conn.execute(f"SELECT COUNT(DISTINCT {sk}) FROM observations WHERE 1"
                        + sc.not_excluded_sql(conn, "observations")).fetchone()[0] == 3
    assert sc.species_key(conn, "observations", SUBSP) == ITS_SPECIES
    # the scheme set: nothing by default, any of the seven kinds when switched on
    assert sc.not_excluded_sql(conn, "recording_scheme") == ""
    sc.set_excluded("recording_scheme", ["subsp", "ss"])
    assert sc.excluded_ids(conn, "recording_scheme") == {7, 9}
    # export choices
    assert sc.export_sql(conn, "recording_scheme", sc.EXPORT_INCLUDE) == ""
    assert "NOT IN" in sc.export_sql(conn, "recording_scheme", sc.EXPORT_COUNTED)
    assert " IN (7,9)" in sc.export_sql(conn, "recording_scheme", sc.EXPORT_ONLY)
    conn.close()


@needs_uksi
def test_cache_follows_database_changes(settings, tmp_path):
    db = _small_db(str(tmp_path / "observatum.db"))
    assert len(sc.excluded_ids(db, "observations")) == 5
    first = sc.snapshot(db, "observations")
    assert sc.snapshot(db, "observations") is first                    # cached
    w = sqlite3.connect(db)
    w.execute("INSERT INTO observations (id, species_name, taxon_rank) VALUES (11, 'Andrena', 'Genus')")
    w.commit()
    w.close()
    assert 11 in sc.excluded_ids(db, "observations")                    # rebuilt after the write


@needs_uksi
def test_counted_view_for_achievements(settings, tmp_path):
    db = _small_db(str(tmp_path / "observatum.db"))
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    sc.install_counted_view(conn, "observations")
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(DISTINCT species_tvk) FROM observations").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM main.observations").fetchone()[0] == 10
    conn.close()


@needs_uksi
def test_mapping_query_leaves_excluded_off(settings, tmp_path):
    from src.services.map_selection import build_query, counting_exclusions, MapFilters
    db = _small_db(str(tmp_path / "observatum.db"))
    counting = counting_exclusions(db)
    assert set(counting) == {"observations"}                           # scheme set empty
    where, params = build_query("observations", [], "personal", MapFilters(include_embargoed=True),
                                ctx=None, counting=counting)
    assert "id NOT IN (2,3,4,5,6)" in where


# ------------------------------------------------------------------ the data copy

@pytest.fixture
def on_copy(settings, tmp_path, monkeypatch):
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
    yield dst
    db._main_db_path, db._uksi_db_path = old


@needs_data
def test_home_equals_observation_data(on_copy):
    from src.models.database import get_database
    from src.repositories.observation_repository import ObservationRepository
    from src.views.observations.observation_tab import ObservationTab
    stats = ObservationRepository(get_database()).get_quick_stats()
    tab = ObservationTab()
    tab.initialize()
    total = sqlite3.connect(on_copy).execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    excluded = len(sc.excluded_ids(on_copy, "observations"))
    assert tab.table_model.rowCount() == total                         # every record listed
    counted = tab._counted(tab.table_model._observations)
    assert stats["total_records"] == len(counted) == total - excluded
    assert stats["total_species"] == tab._count_species_with_exclusion(counted)
    text = tab.toolbar.count_label.text()
    assert f"{total - excluded:,}" in text and "excluded" not in text   # no "n excluded" note
    # a dimmed row says why
    from PySide6.QtCore import Qt
    model = tab.table_model
    row = next(i for i, o in enumerate(model._observations) if o.id in model._dimmed)
    col = [c[0] for c in model._columns].index('species_name')
    tip = model.data(model.index(row, col), Qt.ItemDataRole.ToolTipRole)
    assert tip.startswith("Not counted (")
    # Show only excluded
    tab.filter_bar.only_excluded_chk.setChecked(True)
    assert tab.table_model.rowCount() == excluded
    tab.filter_bar.only_excluded_chk.setChecked(False)
    assert tab.table_model.rowCount() == total
    # switches off: everything counts
    sc.set_excluded("observations", [])
    tab._apply_current_filters()
    assert ObservationRepository(get_database()).get_quick_stats()["total_records"] == total
    assert len(tab._counted(tab.table_model._observations)) == total


def _live_scheme_ids(db_path):
    """The scheme ids counted at all: the marked NBN copies of iRecord records left out by
    THE rule (shared/scheme_duplicates.live_sql; no-op on a database without the column)."""
    from shared.scheme_duplicates import live_sql
    c = sqlite3.connect(db_path)
    try:
        return {r[0] for r in c.execute("SELECT id FROM recording_scheme WHERE 1" + live_sql(c))}
    finally:
        c.close()


@needs_data
def test_scheme_worker_dims_and_lists_only_excluded(on_copy):
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    agg = sc.excluded_ids(on_copy, "recording_scheme", ["agg"])
    live = _live_scheme_ids(on_copy)               # each record once: marked NBN copies out
    live_agg = set(agg) & live
    w = SchemeDataWorker(on_copy, {"_counting_kinds": frozenset({"agg"})})
    w.run()
    records, _n = w.results
    listed = {r["id"] for r in records}
    assert listed == live and len(records) == len(live)
    assert w.counted == len(live) - len(live_agg) and set(w.dimmed) == set(agg)
    assert listed & set(w.dimmed) == live_agg
    w = SchemeDataWorker(on_copy, {"_counting_kinds": frozenset({"agg"}), "only_excluded": True})
    w.run()
    assert len(w.results[0]) == len(live_agg) == w.counted


@needs_data
def test_scheme_stats_follow_the_switches(on_copy):
    from src.models.database import get_database
    from src.services.recording_scheme_stats_service import RecordingSchemeStatsService
    svc = RecordingSchemeStatsService()
    svc.initialize(get_database())
    from shared.scheme_duplicates import live_sql
    c = sqlite3.connect(on_copy)
    copies = live_sql(c)                           # the marked NBN copies: never counted (Q59)
    assert svc._get_exclusion_clause() == copies   # no kinds left out: only the copies rule
    sc.set_excluded("recording_scheme", ["agg"])
    n = c.execute("SELECT COUNT(*) FROM recording_scheme WHERE 1" + svc._get_exclusion_clause()).fetchone()[0]
    leiopus = c.execute("SELECT COUNT(*) FROM recording_scheme WHERE species_name = "
                        "'Leiopus linnei/nebulosus'" + copies).fetchone()[0]
    assert leiopus > 0
    live = _live_scheme_ids(on_copy)
    assert n == len(live) - len(set(sc.excluded_ids(on_copy, "recording_scheme")) & live)
    assert c.execute("SELECT COUNT(*) FROM recording_scheme WHERE species_name = "
                     "'Leiopus linnei/nebulosus'" + svc._get_exclusion_clause()).fetchone()[0] == 0


@needs_data
def test_settings_panel_and_dashboard_chips_in_step(on_copy):
    from src.views.settings.counting_panel import SpeciesCountingPanel
    from src.views.stats.scheme_dashboard import SchemeDashboard
    panel = SpeciesCountingPanel()
    dash = SchemeDashboard()
    dash.refresh = lambda: None                                         # figures not needed here
    dash._kind_chips["agg"].setChecked(True)                            # chip -> settings -> panel
    assert sc.excluded_kinds("recording_scheme") == {"agg"}
    assert panel._boxes[("recording_scheme", "agg")].isChecked()
    panel._boxes[("recording_scheme", "hybrid")].setChecked(True)       # panel -> settings -> chip
    assert dash._kind_chips["hybrid"].isChecked()
    panel._boxes[("observations", "genus")].setChecked(False)
    assert sc.excluded_kinds("observations") == {"family_plus", "agg", "sl"}


@needs_data
def test_species_lookup_and_minimap_follow(on_copy):
    from shared.maps.species_dist_map import DistributionService
    conn = sqlite3.connect(on_copy)
    oligia = "NHMSYS0001703675"
    n = conn.execute("SELECT COUNT(*) FROM observations WHERE species_tvk=?", (oligia,)).fetchone()[0]
    assert n > 0
    svc = DistributionService(conn)
    assert svc._counted("observations").startswith(" AND id NOT IN")
    assert svc._counted("specimens") == ""
    from src.views.stats.species_dashboard import SpeciesDashboard
    d = SpeciesDashboard.__new__(SpeciesDashboard)
    from src.models.database import get_database
    d._db = get_database()
    assert d._counted("observations", "Oligia strigilis agg.").count(f"{_first_id(conn, oligia)}") == 0
    assert d._counted("specimens", "x") == ""


def _first_id(conn, tvk):
    return conn.execute("SELECT MIN(id) FROM observations WHERE species_tvk=?", (tvk,)).fetchone()[0]
