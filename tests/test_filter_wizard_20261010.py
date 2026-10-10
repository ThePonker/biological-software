"""Filter Wizard and filter bars, all three tabs (review OBS-06/07/08/14/15, SRCH1-4, 7-13, 20).

The wizard's chips become SQL in one place (services/filter_builder.build_where), each tab's
columns declared once (TAB_COLUMNS). Counts are checked against hand-written SQL run here,
on a read-only connection to data/observatum.db (on 9 Oct's copy: scheme site "Wood" 16,645,
VC Oxfordshire 1,168, year 2019 5,880, before 2000 28,958; collection 2019 168; observations
2024 2,510, notes "oak" 555, method "MV light" 608, Coleoptera 8,174). Tab-level tests run on
a throwaway copy of the database (sqlite backup), never on the real file.
"""
import os
import sqlite3
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

DB = paths.OBSERVATUM_DB
needs_data = pytest.mark.skipif(not os.path.exists(DB), reason="no data/observatum.db")


def _ro():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def _hand(sql, params=()):
    c = _ro()
    try:
        return c.execute(sql, params).fetchone()[0]
    finally:
        c.close()


def _built(tab, filters):
    from src.services.filter_builder import matching_ids
    ids = matching_ids(DB, tab, filters)
    return None if ids is None else len(ids)


# -- the builder, per tab, against hand SQL ------------------------------------------

SCHEME_CASES = [
    # OBS-06/SRCH1: "~" kept -> 0
    ({"site_name": ["~Wood"]}, "SELECT COUNT(*) FROM recording_scheme WHERE site_name LIKE '%wood%'"),
    # SRCH2: VC name compared with vc_number -> 0
    ({"vice_county": ["Oxfordshire"]},
     "SELECT COUNT(*) FROM recording_scheme WHERE vice_county = 'Oxfordshire' COLLATE NOCASE"),
    ({"vice_county": ["23 - Oxon"]}, "SELECT COUNT(*) FROM recording_scheme WHERE vc_number = 23"),
    # SRCH3: only the first chip was used
    ({"species": ["Rutpela maculata", "Stenurella melanura"]},
     "SELECT COUNT(*) FROM recording_scheme WHERE species_name IN ('Rutpela maculata', 'Stenurella melanura')"),
    # most cards were ignored: year, determiner, status
    ({"year": 2019}, "SELECT COUNT(*) FROM recording_scheme WHERE date LIKE '2019%'"),
    ({"verification_status": ["Accepted"]},
     "SELECT COUNT(*) FROM recording_scheme WHERE verification_status LIKE 'Accepted%'"),
    ({"determiner": ["~Heeney"]}, "SELECT COUNT(*) FROM recording_scheme WHERE determiner LIKE '%heeney%'"),
    # OBS-14: dates before 2000, undated rows excluded
    ({"date_to": "1999-12-31"}, "SELECT COUNT(*) FROM recording_scheme WHERE date <> '' AND date < '2000'"),
    # cards combine with AND, keys of one card with OR
    ({"site_name": ["~Wood"], "year": 2019},
     "SELECT COUNT(*) FROM recording_scheme WHERE site_name LIKE '%wood%' AND date LIKE '2019%'"),
    ({"site_name": ["~Wood"], "vice_county": ["Oxfordshire"]},
     "SELECT COUNT(*) FROM recording_scheme WHERE site_name LIKE '%wood%' OR vice_county = 'Oxfordshire'"),
]

COLLECTION_CASES = [
    ({"year": 2019}, "SELECT COUNT(*) FROM specimens WHERE date_collected LIKE '2019%'"),
    ({"taxon_group": ["Coleoptera", "Hemiptera"]},
     "SELECT COUNT(*) FROM specimens WHERE order_name IN ('Coleoptera', 'Hemiptera')"),
    ({"recorder": ["~heeney"]}, "SELECT COUNT(*) FROM specimens WHERE collector LIKE '%heeney%'"),
    ({"vice_county": ["Oxfordshire", "56"]},
     "SELECT COUNT(*) FROM specimens WHERE vice_county = 'Oxfordshire' OR vc_number = 56"),
    ({"site_name": ["~wood"], "taxon_group": ["Coleoptera"]},
     "SELECT COUNT(*) FROM specimens WHERE site_name LIKE '%wood%' AND order_name = 'Coleoptera'"),
]

OBSERVATION_CASES = [
    # SRCH4: year and notes were ignored
    ({"year": 2024}, "SELECT COUNT(*) FROM observations WHERE date LIKE '2024%'"),
    ({"notes_search": ["~oak"]},
     "SELECT COUNT(*) FROM observations WHERE comment LIKE '%oak%' OR internal_notes LIKE '%oak%' "
     "OR sample_comment LIKE '%oak%'"),
    # OBS-15: one method ignoring case
    ({"method": ["MV Light"]}, "SELECT COUNT(*) FROM observations WHERE LOWER(method) = 'mv light'"),
    ({"taxon_group": ["Coleoptera"]}, "SELECT COUNT(*) FROM observations WHERE order_name = 'Coleoptera'"),
    ({"grid_ref": ["sp 5"]}, "SELECT COUNT(*) FROM observations WHERE UPPER(grid_ref) LIKE 'SP5%'"),
    ({"record_type": ["Commercial"], "verification_status": ["Accepted"]},
     "SELECT COUNT(*) FROM observations WHERE record_type = 'Commercial' AND verification_status = 'Accepted'"),
]


@needs_data
@pytest.mark.parametrize("filters,sql", SCHEME_CASES)
def test_builder_scheme_matches_hand_sql(filters, sql):
    assert _built("recording_scheme", filters) == _hand(sql)


@needs_data
@pytest.mark.parametrize("filters,sql", COLLECTION_CASES)
def test_builder_collection_matches_hand_sql(filters, sql):
    assert _built("insect_collection", filters) == _hand(sql)


@needs_data
@pytest.mark.parametrize("filters,sql", OBSERVATION_CASES)
def test_builder_observations_matches_hand_sql(filters, sql):
    assert _built("observations", filters) == _hand(sql)


def test_builder_basics():
    from src.services.filter_builder import build_where, unsupported_keys, KEY_TO_CARD
    assert build_where("observations", {}) == ("", [])
    assert build_where("observations", {"species": [], "year": None}) == ("", [])
    # the collection has no verification status: ignored, and reported
    assert build_where("specimens", {"verification_status": ["Accepted"]}) == ("", [])
    assert unsupported_keys("specimens", {"verification_status": ["Accepted"]}) == ["verification_status"]
    assert KEY_TO_CARD["notes_search"] == "how"       # SRCH11: saved filters kept it from now on
    sql, params = build_where("observations", {"site_name": ["~Wood", "Otmoor"]})
    assert params == ["%Wood%", "Otmoor"] and " OR " in sql


def test_tab_values_merge_case_and_statuses():
    from src.services.filter_builder import merge_case_variants, status_groups
    assert merge_case_variants([("MV light", 589), ("MV Light", 19), (None, 5), ("Net", 3)]) == ["MV light", "Net"]
    assert status_groups(["Accepted - correct", "Accepted", "Unconfirmed - plausible"]) == ["Accepted", "Unconfirmed"]


@needs_data
def test_tab_values_come_from_each_tab():
    """SRCH12: each tab offers its own values, not Observations' or all of UKSI."""
    from src.services.filter_builder import tab_values
    scheme = tab_values(DB, "recording_scheme")
    assert scheme["orders"] == [r[0] for r in _ro().execute(
        "SELECT DISTINCT order_name FROM recording_scheme WHERE TRIM(order_name) <> '' ORDER BY 1")]
    assert scheme["record_types"] == []                         # all "Recording Scheme"
    coll = tab_values(DB, "specimens")
    assert coll["methods"] == [] and coll["statuses"] == []
    obs = tab_values(DB, "observations", only=("methods",))
    assert list(obs) == ["methods"]
    folded = [m.casefold() for m in obs["methods"]]
    assert len(folded) == len(set(folded))                      # one per spelling


# -- the dialogs ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_typed_chip_rules():
    from src.views.components.filter_wizard.chip_values import typed_chip, chip_label
    assert typed_chip("coleoptera", ["Coleoptera", "Diptera"]) == ("Coleoptera", "Coleoptera")
    assert typed_chip("Coleop", ["Coleoptera"]) == ("~Coleop", "*Coleop*")     # SRCH13
    assert chip_label("~oak") == "*oak*" and chip_label("Net") == "Net"


def test_enter_on_half_typed_text_is_a_contains_chip(qapp):
    """SRCH13: Enter added half-typed text as an exact filter (0 results)."""
    from src.views.components.filter_wizard.what_filter_dialog import WhatFilterDialog
    from src.views.components.filter_wizard.where_filter_dialog import WhereFilterDialog
    from src.views.components.filter_wizard.who_filter_dialog import WhoFilterDialog
    d = WhatFilterDialog(species_list=["Rutpela maculata"], taxon_groups=["Coleoptera", "Diptera"],
                         family_list=["Cerambycidae"])
    d._order_input.setText("Coleop")
    d._on_enter_pressed(d._order_input, "taxon_group", "Order")
    d._family_input.setText("cerambycidae")
    d._on_enter_pressed(d._family_input, "family", "Family")
    assert d.get_values() == {"taxon_group": ["~Coleop"], "family": ["Cerambycidae"]}

    w = WhereFilterDialog(vc_list=["Oxfordshire"], grid_ref_list=["SP5822"], site_list=["Otmoor"])
    w._vc_input.setText("oxf")
    w._on_enter(w._vc_input, "vice_county", "VC", False)
    w._partial_match_cb.setChecked(False)
    w._site_input.setText("otmoor")
    w._on_site_enter()
    assert w.get_values() == {"vice_county": ["~oxf"], "site_name": ["Otmoor"]}

    p = WhoFilterDialog(recorder_list=["W. J. Heeney"], determiner_list=[])
    p._recorder_partial_cb.setChecked(False)
    p._recorder_input.setText("w. j. heeney")
    p._on_enter_with_toggle(p._recorder_input, "recorder", "Recorder", p._recorder_partial_cb)
    assert p.get_values() == {"recorder": ["W. J. Heeney"]}


def test_when_dialog_clear_and_default_add_no_date(qapp):
    """SRCH10: Clear did not clear; Apply always added a 12-month range."""
    from src.views.components.filter_wizard.when_filter_dialog import WhenFilterDialog
    d = WhenFilterDialog(year_list=["2019", "2024"])
    assert d.get_values() == {}                                  # opened and applied: no filter
    d._set_last_12_months()
    assert set(d.get_values()) == {"date_from", "date_to"}
    d._clear_all()
    assert d.get_values() == {}
    d2 = WhenFilterDialog(current_values={"year": 2019}, year_list=[2024, 2019])
    assert d2.get_values() == {"year": 2019}
    assert d2._from_date.minimumDate().year() <= 1500             # OBS-14: old dates allowed


def test_how_and_status_dialogs_offer_tab_values(qapp):
    from src.views.components.filter_wizard.how_filter_dialog import HowFilterDialog
    from src.views.components.filter_wizard.status_filter_dialog import StatusFilterDialog
    h = HowFilterDialog(method_list=["MV light", "Net"], current_values={"method": ["MV Light"]})
    assert list(h._method_checkboxes) == ["MV light", "Net"]
    assert h.get_values() == {"method": ["MV light"]}           # saved spelling ticks the box
    s = StatusFilterDialog(status_list=["Accepted", "Unconfirmed"], type_list=[])
    assert list(s._status_checkboxes) == ["Accepted", "Unconfirmed"]
    assert s._type_checkboxes == {}                              # scheme: no record types


@needs_data
def test_wizard_dialog_lists_are_the_tabs_own(qapp, monkeypatch):
    """SRCH12/SRCH20: lists from the tab's own table, read-only; Status hidden on the collection."""
    from src.views.components.filter_wizard.filter_wizard import FilterWizard
    w = FilterWizard(tab_name="recording_scheme")
    w.set_db_path(DB)
    w._ensure_tab_values()
    assert w._taxon_groups == ["Coleoptera"] and w._record_type_list == []
    c = FilterWizard(tab_name="insect_collection")
    assert c.card_grid.get_card("status").isHidden()
    assert not c.card_grid.get_card("how").isHidden()           # notes search still applies


# -- saved filters (SRCH11) ------------------------------------------------------------

def test_saved_filters_per_tab_and_keep_notes(qapp, tmp_path, monkeypatch):
    import json
    from src.services.saved_filters_service import SavedFiltersService
    from src.views.components.filter_wizard import filter_wizard as fw
    path = tmp_path / "saved_filters.json"
    # a file in the old layout (keyed by name alone) still loads
    path.write_text(json.dumps({"filters": {"Old": {"tab": "observations", "config": {"year": 2020}}}}))
    svc = SavedFiltersService(path)
    assert svc.get_filter("Old", tab="observations") == {"year": 2020}
    svc.save_filter("Wood", {"site_name": ["~Wood"]}, tab="observations")
    svc.save_filter("Wood", {"site_name": ["~Wood"], "year": 2019}, tab="recording_scheme")
    assert svc.get_filter("Wood", tab="observations") == {"site_name": ["~Wood"]}   # not replaced
    assert sorted(SavedFiltersService(path).get_filter_names("recording_scheme")) == ["Wood"]
    assert svc.delete_filter("Wood", tab="recording_scheme")
    assert svc.get_filter("Wood", tab="observations") is not None

    w = fw.FilterWizard(tab_name="observations")
    w._saved_filters_service = svc
    applied = []
    w.filters_applied.connect(applied.append)
    svc.save_filter("Oak", {"notes_search": ["~oak"], "year": 2024}, tab="observations")
    w._load_saved_filter_names()
    w._on_load_saved_filter("Oak")
    assert w.get_all_filters() == {"notes_search": ["~oak"], "year": 2024}   # Notes kept
    assert applied and applied[-1] == {"notes_search": ["~oak"], "year": 2024}  # and applied


# -- the tabs, on a throwaway copy --------------------------------------------------------

@pytest.fixture(scope="module")
def db_copy(tmp_path_factory):
    if not os.path.exists(DB):
        pytest.skip("no data/observatum.db")
    dst = tmp_path_factory.mktemp("wiz") / "observatum.db"
    src = _ro()
    out = sqlite3.connect(dst)
    src.backup(out)
    out.close()
    src.close()
    return str(dst)


@pytest.fixture
def on_copy(qapp, db_copy, monkeypatch):
    """Every path in the app points at the copy; QSettings isolated."""
    from PySide6.QtCore import QCoreApplication, QSettings
    from src.models.database import get_database
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("filter_wizard_20261010")
    QSettings().clear()
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(db_copy)
    db.set_uksi_path(str(paths.UKSI_DB))
    monkeypatch.setattr(paths, "OBSERVATUM_DB", db_copy)
    yield db_copy
    db._main_db_path, db._uksi_db_path = old
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


def _excluded_count(sql_where):
    """Hand SQL with Observation Data's default exclusion (TVK, binomial, no agg./s.l.)."""
    return _hand(
        "SELECT COUNT(*) FROM observations WHERE " + sql_where +
        " AND COALESCE(species_tvk, '') <> '' AND species_name LIKE '% %'"
        " AND LOWER(species_name) NOT LIKE '%agg.%' AND LOWER(species_name) NOT LIKE '%agg %'"
        " AND LOWER(species_name) NOT LIKE '% agg' AND LOWER(species_name) NOT LIKE '%s.l.%'"
        " AND LOWER(species_name) NOT LIKE '%sensu lato%'")


def test_observation_tab_wizard(on_copy):
    from src.views.observations.observation_tab import ObservationTab
    tab = ObservationTab()
    tab.initialize()
    n = tab.table_model.rowCount

    # SRCH4 + OBS-07: year honoured, and fast (was a 54 s list-membership loop)
    t = time.time()
    tab._on_wizard_filters_applied({"year": 2024, "site_name": ["~Wood", "~Park"]})
    assert time.time() - t < 5
    assert n() == _excluded_count("date LIKE '2024%' AND (site_name LIKE '%wood%' OR site_name LIKE '%park%')")

    # SRCH9: same figure as the filter bar, and kept on reload
    tab._on_wizard_filters_applied({"taxon_group": ["Coleoptera"]})
    wiz = n()
    assert wiz == _excluded_count("order_name = 'Coleoptera'")
    tab._load_data()
    assert n() == wiz
    tab._on_wizard_filters_reset()
    tab.filter_bar.set_order_filter("Coleoptera")
    assert n() == wiz
    # the wizard and the bar combine
    tab._on_wizard_filters_applied({"year": 2024})
    assert n() == _excluded_count("order_name = 'Coleoptera' AND date LIKE '2024%'")

    # OBS-15: the bar's method list is the data's, matching every case
    m = tab.filter_bar.method_combo
    texts = [m.itemText(i) for i in range(m.count())]
    mv = [t for t in texts if t.casefold() == "mv light"]
    assert len(mv) == 1
    tab._on_wizard_filters_reset()
    tab.filter_bar.clear_filters()
    m.setCurrentIndex(texts.index(mv[0]))
    assert n() == _excluded_count("LOWER(method) = 'mv light'")

    # OBS-08: navigating to a species clears every other filter
    tab._on_wizard_filters_applied({"year": 1990})
    tab.show_species("Rutpela maculata")
    assert n() == _excluded_count("species_name LIKE '%Rutpela maculata%'")
    assert tab.filter_bar.method_combo.currentIndex() == 0
    assert tab._wizard_filters == {} and tab.filter_wizard.get_all_filters() == {}


def test_observation_bar_dates_before_2000_count(on_copy, qapp):
    """OBS-14: a date before 2000 in a filter bar was dropped."""
    from PySide6.QtCore import QDate
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    from src.views.collection.collection_filters import CollectionFilterBar
    for bar in (ObservationFilterBar(), SchemeFilterBar(), CollectionFilterBar()):
        bar.date_to_edit.setDate(QDate(1850, 6, 1))
        assert bar.get_filters()["date_to"] == "1850-06-01"
        bar.date_from_edit.setIsoDate("1899-01-01")             # saved filters used setText (missing)
        assert bar.get_filters()["date_from"] == "1899-01-01"


def _scheme_rows(db_path, filters):
    from src.views.scheme.scheme_data_worker import SchemeDataWorker
    w = SchemeDataWorker(db_path, filters)
    w.run()
    return len(w.results[0])


def test_scheme_tab_wizard_and_bar(on_copy, monkeypatch):
    import src.views.scheme.recording_scheme_tab as rst
    from src.models.database import get_database
    captured = {}

    class Capture:
        def __init__(self, db_path, filters, parent=None):
            captured["f"] = filters
            self.error = type("E", (), {"connect": lambda *a: None})()

        def start(self):
            pass

        def isRunning(self):
            return False

    monkeypatch.setattr(rst, "SchemeDataWorker", Capture)
    tab = rst.RecordingSchemeTab()
    tab._db = get_database()
    tab._initialized = True
    tab.filter_bar.initialize_with_database(get_database())

    tab._on_wizard_filters_applied({"site_name": ["~Wood"], "vice_county": ["Oxfordshire"],
                                    "year": 2019})
    assert _scheme_rows(on_copy, captured["f"]) == _hand(
        "SELECT COUNT(*) FROM recording_scheme WHERE (site_name LIKE '%wood%' "
        "OR vice_county = 'Oxfordshire') AND date LIKE '2019%'")
    tab.refresh()                                               # SRCH9: kept on reload
    assert "_wizard_sql" in captured["f"]
    tab._on_wizard_filters_reset()
    assert "_wizard_sql" not in (captured["f"] or {})

    # SRCH8: Source, Accepted, Subfamily
    assert _scheme_rows(on_copy, {"source": "iRecord"}) == _hand(
        "SELECT COUNT(*) FROM recording_scheme WHERE COALESCE(irecord_id, '') <> ''")
    assert _scheme_rows(on_copy, {"source": "NBN Atlas"}) == _hand(
        "SELECT COUNT(*) FROM recording_scheme WHERE COALESCE(nbn_atlas_id, '') <> ''")
    assert _scheme_rows(on_copy, {"status": "Accepted"}) == _hand(
        "SELECT COUNT(*) FROM recording_scheme WHERE verification_status LIKE 'Accepted%'")
    statuses = [tab.filter_bar.status_combo.itemText(i) for i in range(tab.filter_bar.status_combo.count())]
    assert "Accepted" in statuses and not any(" - " in s for s in statuses)
    has_sub = _hand("SELECT COUNT(*) FROM recording_scheme WHERE TRIM(COALESCE(subfamily, '')) <> ''")
    assert tab.filter_bar.subfamily_combo.isEnabled() == bool(has_sub)
    # OBS-14: the bar's "Date To" no longer lets undated records through
    assert _scheme_rows(on_copy, {"date_to": "1999-12-31"}) == _hand(
        "SELECT COUNT(*) FROM recording_scheme WHERE date <> '' AND date < '2000'")


def test_collection_tab_wizard(on_copy):
    from src.views.collection.insect_collection_tab import InsectCollectionTab
    tab = InsectCollectionTab()
    tab.initialize(uksi_path=str(paths.UKSI_DB))
    n = tab.table_model.rowCount
    tab._on_wizard_filters_applied({"year": 2019})
    assert n() == _hand("SELECT COUNT(*) FROM specimens WHERE date_collected LIKE '2019%'")
    tab._load_data()                                            # SRCH9: kept on reload
    assert n() == _hand("SELECT COUNT(*) FROM specimens WHERE date_collected LIKE '2019%'")
    tab._on_wizard_filters_applied({"taxon_group": ["Coleoptera", "Hemiptera"], "recorder": ["~heeney"]})
    assert n() == _hand("SELECT COUNT(*) FROM specimens WHERE order_name IN ('Coleoptera', 'Hemiptera') "
                        "AND collector LIKE '%heeney%'")
    tab.clear_wizard_filters()
    tab._on_navigate_to_collection("Rutpela maculata")          # OBS-08 on this tab too
    assert tab.filters.get_filters()["species"] == "Rutpela maculata"
    assert tab._wizard_filters == {}
