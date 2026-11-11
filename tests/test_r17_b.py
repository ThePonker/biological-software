"""Round 17, builder B: Reference column (B1), client exports (B2), Species Info status (B4),
common-name tie rule (B5), Sync panel / coming-soon line removed (B6), edit-dialog redet (B7).
Tiny purpose-made databases in tmp_path; no live figure is pinned."""
import csv
import sqlite3

import pytest

from tests.test_dataentry_r3 import qapp  # noqa: F401


@pytest.fixture
def qsettings(qapp):  # noqa: F811
    from PySide6.QtCore import QCoreApplication, QSettings
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("r17_b")
    QSettings().clear()
    yield QSettings()
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


# ---------------------------------------------------------------- B1: Reference column
def _keys(m):
    return [k for k, *_ in m.get_columns()]


def test_reference_column_is_available_and_visible_by_default(qsettings):
    from src.views.observations.observation_table_model import ObservationTableModel as M
    assert "data_reference" in [c[0] for c in M.ALL_COLUMNS]
    assert "data_reference" in M.DEFAULT_VISIBLE
    keys = _keys(M())
    assert "data_reference" in keys
    # after the notes / source columns, before the iRecord id
    assert keys.index("data_reference") > keys.index("import_notes")
    assert keys.index("data_reference") < keys.index("irecord_id")


def test_reference_column_shows_the_value(qsettings):
    from src.views.observations.observation_table_model import ObservationTableModel as M
    m = M()
    m.set_observations([{"id": 1, "species_name": "x", "data_reference": "Joe Bloggs, data to 1990"}])
    assert m.data(m.index(0, _keys(m).index("data_reference"))) == "Joe Bloggs, data to 1990"


def test_saved_layout_from_before_gets_the_column_once_then_respects_hiding(qsettings):
    from src.views.observations.observation_table_model import ObservationTableModel as M
    old_order = [c[0] for c in M.ALL_COLUMNS if c[0] not in ("checkbox", "data_reference")]
    qsettings.setValue("observations/visible_columns", ["date", "species_name", "source"])
    qsettings.setValue("observations/column_order", old_order)
    qsettings.setValue("observations/photos_column_added", True)
    m = M()
    keys = _keys(m)
    assert "data_reference" in keys and "source" in keys       # appears, layout otherwise kept
    assert "family" not in keys                                # their other choices untouched
    assert keys.index("data_reference") == keys.index("source") + 1
    # the user hides it: it stays hidden on the next start
    m._visible_columns.discard("data_reference")
    m.save_column_settings()
    assert "data_reference" not in _keys(M())


# ---------------------------------------------------------------- B2: client exports
def test_all_columns_export_leaves_out_the_reference(tmp_path):
    from src.services.export_service import ExportService
    from shared.data_reference import CLIENT_EXPORT_EXCLUDED
    assert "data_reference" in CLIENT_EXPORT_EXCLUDED
    rows = [{"species_name": "Abax parallelus", "grid_ref": "SP1", "data_reference": "Joe Bloggs, data to 1990"}]
    out = tmp_path / "c.csv"
    assert ExportService.export_to_csv(rows, str(out), columns=None, headers=None)
    text = out.read_text(encoding="utf-8")
    assert "data_reference" not in text and "Joe Bloggs" not in text
    r = list(csv.DictReader(text.splitlines()))
    assert r[0]["species_name"] == "Abax parallelus"


def test_year_export_columns_do_not_carry_the_reference():
    from src.views.stats.year_export import YEAR_RECORD_COLUMNS
    assert "data_reference" not in [c for c, _ in YEAR_RECORD_COLUMNS]


# ---------------------------------------------------------------- B4: Species Info status
def test_status_lookup_uses_the_codex_reader_and_shows_none_when_empty():
    from src.views.home.species_status import lookup, NO_STATUS, NO_SQS
    from types import SimpleNamespace as S

    class Repo:
        def get_status_summary(self, tvk):
            if tvk == "T1":
                return S(display_status="NS, Priority (England)", sqs=8, sqs_derived=False)
            if tvk == "T2":
                return S(display_status="", sqs=3, sqs_derived=True)
            return S(display_status="", sqs=0, sqs_derived=False)
    r = Repo()
    assert lookup("T1", r) == ("NS, Priority (England)", "8")
    assert lookup("T2", r) == (NO_STATUS, "3 (derived)")
    assert lookup("T3", r) == (NO_STATUS, NO_SQS)
    assert lookup("", r) == (NO_STATUS, NO_SQS)
    assert (NO_STATUS, NO_SQS) == ("None", "–")

    class Broken:
        def get_status_summary(self, tvk):
            raise FileNotFoundError("codex.db not found")
    assert lookup("T1", Broken()) == (NO_STATUS, NO_SQS)


def test_status_lookup_on_a_tiny_codex(dbs):  # noqa: F811
    from src.views.home.species_status import lookup
    from tests.test_fix_round_figures import D, A
    assert lookup(D, dbs.codex) == ("NS", "8")
    assert lookup(A, dbs.codex) == ("None", "2")
    assert lookup("U_NOPE", dbs.codex) == ("None", "–")


from tests.test_fix_round_figures import dbs  # noqa: E402,F401  (fixture)


def test_species_info_panel_shows_status_and_sqs(qapp, monkeypatch):  # noqa: F811
    from src.views.home import species_info, species_status
    monkeypatch.setattr(species_status, "lookup", lambda tvk, repo=None: ("NS", "8"))
    p = species_info.SpeciesInfoPanel()
    p.set_species({"scientific_name": "Abax parallelus", "tvk": "T1"})
    assert p.status_value.text() == "NS" and p.sqs_value.text() == "8"
    monkeypatch.setattr(species_status, "lookup", lambda tvk, repo=None: ("None", "–"))
    p.set_species({"scientific_name": "Other", "tvk": "T2"})
    assert p.status_value.text() == "None" and p.sqs_value.text() == "–"


# ---------------------------------------------------------------- B5: common-name tie rule
def _uksi(tmp_path, names):
    p = tmp_path / "uksi.db"
    u = sqlite3.connect(p)
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              'kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT, family TEXT, genus TEXT, '
              'sort_code INTEGER)')
    u.execute("CREATE TABLE common_names (tvk TEXT, common_name TEXT, preferred INTEGER)")
    u.executemany("INSERT INTO common_names VALUES ('T', ?, ?)", names)
    u.commit()
    return u


def _pick(u):
    from shared.common_name_pick import order_by_sql
    return u.execute(f"SELECT cn.common_name FROM common_names cn WHERE cn.tvk = 'T' "
                     f"ORDER BY {order_by_sql()} LIMIT 1").fetchone()[0]


@pytest.mark.parametrize("names,want", [
    ([("Bedstraw Hawk-Moth", 1), ("Bedstraw Hawk-moth", 1)], "Bedstraw Hawk-moth"),
    ([("Great Black-Backed Gull", 1), ("Great Black-backed Gull", 1)], "Great Black-backed Gull"),
    ([("Alpha Beta", 1), ("Alpha beta", 1), ("alpha beta", 1)], "Alpha beta"),         # capital start beats none
    ([("Lady's-Mantle", 1), ("Lady's Mantle", 1)], "Lady's Mantle"),                  # alphabetical (space first)
    ([("b thing", 1), ("A Thing", 1)], "A Thing"),
    ([("Zed", 0), ("Longer name", 1)], "Longer name"),                                # preferred first
    ([("Short Name", 0), ("Shorter", 0)], "Shorter"),                                 # length before capitals
    ([("Ab", 1), ("AB", 1), ("Ac", 1)], "Ab"),                                        # fewer capitals, then alphabet
])
def test_common_name_tie_rule(tmp_path, names, want):
    u = _uksi(tmp_path, names)
    assert _pick(u) == want
    from shared.common_name_pick import sort_key
    assert min(names, key=lambda n: sort_key(n[0], n[1]))[0] == want      # the Python form agrees


def test_choice_does_not_depend_on_row_order(tmp_path):
    a = [("Bedstraw Hawk-Moth", 1), ("Bedstraw Hawk-moth", 1)]
    for i, names in enumerate((a, a[::-1])):
        d = tmp_path / str(i)
        d.mkdir()
        assert _pick(_uksi(d, names)) == "Bedstraw Hawk-moth"


def test_taxon_select_and_search_index_use_the_rule(tmp_path):
    from shared.species_lookup import _taxon_select
    u = _uksi(tmp_path, [("Bedstraw Hawk-Moth", 1), ("Bedstraw Hawk-moth", 1)])
    u.execute("INSERT INTO taxa (tvk, scientific_name, rank) VALUES ('T', 'Hyles gallii', 'Species')")
    u.commit()
    row = u.execute(_taxon_select(u).format(key="t.tvk", src="taxa t")).fetchone()
    assert "Bedstraw Hawk-moth" in tuple(row)


def test_search_index_cache_version_was_bumped():
    from shared import species_index_cache as c
    assert c.CODE_VERSION >= 2 and "common_name_pick.py" in c._CODE_FILES


# ---------------------------------------------------------------- B6: removed from the interface
def test_settings_has_no_sync_panel(qapp):  # noqa: F811
    import os
    from src.views.settings.settings_tab import SettingsTab
    from src.views.settings.sidebar import SettingsSidebar
    t = SettingsTab()
    assert not hasattr(t, "sync_panel") and t.panel_stack.count() == 4
    assert "sync" not in [s for s, _ in SettingsSidebar.SECTIONS]
    t.sidebar.section_changed.emit("counting")
    assert t.panel_stack.currentWidget() is t.counting_panel
    t.sidebar.section_changed.emit("export")
    assert t.panel_stack.currentWidget() is t.export_panel
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert not os.path.exists(os.path.join(root, "Observatum", "src", "views", "settings", "sync_panel.py"))
    assert os.path.exists(os.path.join(root, "_archive", "sync_panel_20261110", "Observatum", "src",
                                       "views", "settings", "sync_panel.py"))


def test_commercial_reports_has_no_coming_soon_line():
    import inspect
    from src.views.stats import commercial_reports_dashboard as m
    src = inspect.getsource(m)
    assert "coming soon" not in src and "Survey Effort" not in src


# ---------------------------------------------------------------- B7: edit dialog, re-determination
@pytest.fixture
def redet_dbs(tmp_path):
    uksi = tmp_path / "uksi.db"
    u = sqlite3.connect(uksi)
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              'kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT, family TEXT, genus TEXT, '
              'sort_code INTEGER, superfamily TEXT)')
    u.execute("CREATE TABLE common_names (tvk TEXT, common_name TEXT, preferred INTEGER)")
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
        ("OLD", "Old name", "Genus", None, "Animalia", "Arthropoda", "Arachnida", "Araneae",
         "Linyphiidae", None, 7, None),
        ("NEW", "Carabus nemoralis", "Species", None, "Animalia", "Arthropoda", "Insecta",
         "Coleoptera", "Carabidae", "Carabus", 18000, "Caraboidea")])
    u.executemany("INSERT INTO common_names VALUES (?,?,?)", [
        ("NEW", "Bronze Carabid", 1), ("NEW", "Bronze carabid", 1)])
    u.commit()
    u.close()
    obs = tmp_path / "obs.db"
    o = sqlite3.connect(obs)
    o.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, species_tvk TEXT, "
              "common_name TEXT, family TEXT, order_name TEXT, taxon_rank TEXT, kingdom TEXT, "
              "taxon_group TEXT, superfamily TEXT, subfamily TEXT, taxonomic_sort_key INTEGER, "
              "grid_ref TEXT, vice_county TEXT, vc_number INTEGER)")
    o.execute("INSERT INTO observations VALUES (1,'Old name','OLD','Old common','Linyphiidae','Araneae',"
              "'Genus','Animalia','spider','Wrongoidea','Oldsub',7,'SO539092','West Gloucestershire',34)")
    o.commit()
    return str(uksi), o


def test_species_change_refreshes_every_taxonomy_column(redet_dbs):
    from src.views.observations.observation_detail_mixin import (
        with_redet_taxonomy, REDET_TAXONOMY_FIELDS)
    uksi, o = redet_dbs
    # what the dialog hands over: no family / order from the search result (they would be dropped as None)
    updates = {"species_name": "Carabus nemoralis", "species_tvk": "NEW", "common_name": "stale from dialog"}
    with_redet_taxonomy(updates, "OLD", uksi)
    assert set(REDET_TAXONOMY_FIELDS) <= set(updates)
    o.execute(f"UPDATE observations SET {', '.join(k + ' = ?' for k in updates)} WHERE id = 1", list(updates.values()))
    r = dict(zip([d[0] for d in o.execute("SELECT * FROM observations").description],
                 o.execute("SELECT * FROM observations").fetchone()))
    assert (r["taxon_rank"], r["kingdom"], r["order_name"], r["family"]) == (
        "Species", "Animalia", "Coleoptera", "Carabidae")
    assert "Coleoptera" in r["taxon_group"] and r["superfamily"] == "Caraboidea"
    assert r["subfamily"] is None and r["taxonomic_sort_key"] % 1000000 == 18000
    assert r["common_name"] == "Bronze carabid"          # UKSI, by the tie rule
    assert r["grid_ref"] == "SO539092" and r["vc_number"] == 34       # nothing else touched


def test_same_species_adds_nothing(redet_dbs):
    from src.views.observations.observation_detail_mixin import with_redet_taxonomy
    uksi, _ = redet_dbs
    up = with_redet_taxonomy({"species_name": "x", "species_tvk": "OLD"}, "OLD", uksi)
    assert set(up) == {"species_name", "species_tvk"}


def test_emptied_grid_ref_clears_the_vice_county():
    from src.views.observations.observation_detail_mixin import ObservationDetailMixin as M
    assert M._derive_location_fields("", "SO539092", None) == (
        {"vice_county": None, "vc_number": None, "latitude": None, "longitude": None}, "")
    assert M._derive_location_fields("", "", None) == ({}, "")
