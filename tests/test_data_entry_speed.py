"""Data Entry speed-ups (backlog B1, B2, B4, B6; 9 Oct 2026)."""
import os
import sqlite3

import pytest

from shared.species_rank import resolve_name

CARABUS = {"scientific_name": "Carabus nemoralis", "tvk": "T1", "match_type": "exact"}
MANGORA = {"scientific_name": "Mangora acalypha", "tvk": "T2", "match_type": "contains"}
WILLOW = {"scientific_name": "Salix alba var. caerulea", "tvk": "T3", "match_type": "starts_with"}


def test_exact_scientific_name_fills():
    assert resolve_name("carabus nemoralis", [CARABUS])[0] == "fill"


def test_single_prefix_hit_fills():
    hit = dict(CARABUS, match_type="starts_with")
    assert resolve_name("car nem", [hit]) == ("fill", hit)


def test_part_of_a_common_name_is_never_filled_silently():
    # B6: "Cricket bat spid" found only Cricket-bat Willow through its common name
    assert resolve_name("Cricket bat spid", [WILLOW])[0] == "pick"
    assert resolve_name("Cricket bat spid", [WILLOW], interactive=False) == ("unresolved", None)


def test_an_old_name_with_one_exact_hit_fills():
    old = dict(MANGORA, match_type="exact")                  # exact on a synonym
    assert resolve_name("Epeira acalypha", [old]) == ("fill", old)


def test_paste_never_guesses_between_several():
    two = [dict(CARABUS, match_type="starts_with"), dict(MANGORA, match_type="starts_with")]
    assert resolve_name("ca", two, interactive=False) == ("unresolved", None)
    assert resolve_name("ca", two)[0] == "pick"


@pytest.fixture
def grid(tmp_path):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from DataEntry import staging_repo as repo
    from DataEntry.entry_grid import StagingTableModel
    conn = sqlite3.connect(tmp_path / "obs.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    job = repo.ensure_personal_job(conn)
    repo.insert_row(conn, job, {"species_name": "Carabus nemoralis", "species_tvk": "T1",
                                "family": "Carabidae", "sex": "male", "quantity": 3,
                                "stage": "Adult", "date": "2026-06-01", "grid_ref": "SP580207",
                                "trap_number": "4"})
    return StagingTableModel(conn, job), conn


def test_repeat_row_copies_species_and_context_not_sex_or_count(grid):
    m, conn = grid
    new = m.repeat_row(0)
    row = m.row_dict(new)
    assert new == 1
    assert (row["species_name"], row["species_tvk"], row["stage"], row["grid_ref"], row["trap_number"]) \
        == ("Carabus nemoralis", "T1", "Adult", "SP580207", "4")
    assert row["sex"] is None and row["quantity"] is None
    assert tuple(conn.execute("SELECT species_tvk, sex FROM entry_staging WHERE id=?",
                              (row["id"],)).fetchone()) == ("T1", None)
    assert m.repeat_row(5) is None                           # nothing to repeat


def test_count_mode_counts_up_and_down_but_not_below_one(grid):
    m, _ = grid
    assert m.bump_quantity(0, 1) == 4
    assert m.bump_quantity(0, -1) == 3
    new = m.repeat_row(0)
    assert [m.bump_quantity(new, 1) for _ in range(3)] == [1, 2, 3]   # blank starts at 0
    assert m.bump_quantity(new, -5) == 1


def test_keys_in_the_grid(grid):
    """Space counts in count mode (and only then); Ctrl+R repeats and lands on Sex."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from DataEntry.entry_grid import EntryTableView, COLIDX
    m, _ = grid
    v = EntryTableView()
    v.setModel(m)
    v.setCurrentIndex(m.index(0, COLIDX["species_name"]))
    v.count_mode = True
    seen = []
    v.on_count = lambda r, n: seen.append(n)
    QTest.keyClick(v, Qt.Key.Key_Space)
    QTest.keyClick(v, Qt.Key.Key_Plus)
    QTest.keyClick(v, Qt.Key.Key_Minus)
    assert seen == [4, 5, 4] and m.row_dict(0)["quantity"] == 4
    v.count_mode = False
    QTest.keyClick(v, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
    assert m.row_dict(1)["species_name"] == "Carabus nemoralis"
    assert (v.currentIndex().row(), v.currentIndex().column()) == (1, COLIDX["sex"])


def test_paste_resolves_names_and_lists_the_rest(grid, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from DataEntry.entry_grid import EntryTableView, SpeciesCascadeDelegate, COLIDX

    class Svc:
        def search_species(self, text, limit=25):
            t = text.lower()
            if t == "pterostichus madidus":
                return [{"scientific_name": "Pterostichus madidus", "tvk": "T9", "match_type": "exact"}]
            if t.startswith("cricket"):
                return [dict(WILLOW)]
            return []
    m, _ = grid
    v = EntryTableView()
    v.setModel(m)
    v.setItemDelegateForColumn(COLIDX["species_name"], SpeciesCascadeDelegate(Svc(), v))
    told = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: told.append(a[2]))
    QApplication.clipboard().setText("Pterostichus madidus\nCricket bat spid\n")
    v.setCurrentIndex(m.index(1, COLIDX["species_name"]))
    v._paste()
    assert (m.row_dict(1)["species_name"], m.row_dict(1)["species_tvk"]) == ("Pterostichus madidus", "T9")
    assert (m.row_dict(2)["species_name"], m.row_dict(2)["species_tvk"]) == ("Cricket bat spid", None)
    assert told and "Cricket bat spid" in told[0]


def test_filter_wizard_fuzzy_matching_one_copy():
    """I9: what/who/where share one FuzzyCompleter; place names keep their abbreviations."""
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import importlib.machinery
    import importlib.util
    import sys
    import types
    if importlib.util.find_spec("PySide6.QtWebEngineWidgets") is None:     # headless test machine
        from PySide6.QtWidgets import QWidget
        for m in ("PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore", "PySide6.QtWebChannel"):
            mod = types.ModuleType(m)
            mod.__spec__ = importlib.machinery.ModuleSpec(m, None)
            for n in ("QWebEngineView", "QWebEnginePage", "QWebEngineSettings", "QWebEngineProfile", "QWebChannel"):
                setattr(mod, n, type(n, (QWidget,), {}))
            sys.modules.setdefault(m, mod)
    from src.views.components.filter_wizard import fuzzy, what_filter_dialog, where_filter_dialog
    from src.views.components.filter_wizard import chip_display, how_filter_dialog, who_filter_dialog
    assert what_filter_dialog.FuzzyCompleter is fuzzy.FuzzyCompleter
    assert where_filter_dialog.FuzzyCompleter is fuzzy.PlaceCompleter
    assert how_filter_dialog.FilterChip is who_filter_dialog.FilterChip is chip_display.FilterChip

    def hits(completer_cls, items, text):
        c = completer_cls(items)
        c.splitPath(text)
        return [c._proxy_model.index(i, 0).data() for i in range(c._proxy_model.rowCount())]

    sp = ["Rutpela maculata", "Carabus nemoralis"]
    assert hits(fuzzy.FuzzyCompleter, sp, "rut mac") == ["Rutpela maculata"]
    places = ["South Fen Wood", "North Field"]
    assert hits(fuzzy.PlaceCompleter, places, "sth fen wd") == ["South Fen Wood"]
    assert hits(fuzzy.FuzzyCompleter, places, "sth fen wd") == []


def test_enter_ends_count_mode_and_unmatched_names_stand_out(grid):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from DataEntry.entry_grid import EntryTableView, COLIDX
    m, _ = grid
    v = EntryTableView()
    v.setModel(m)
    v.setCurrentIndex(m.index(0, COLIDX["species_name"]))
    v.count_mode = True
    ended = []
    v.on_count_done = lambda: ended.append(True)
    QTest.keyClick(v, Qt.Key.Key_Space)
    QTest.keyClick(v, Qt.Key.Key_Return)
    assert ended == [True] and m.row_dict(0)["quantity"] == 4 and v.currentIndex().row() == 1
    m.setData(m.index(1, COLIDX["species_name"]), {"scientific_name": "Cricket bat spid"})
    assert m.data(m.index(1, COLIDX["species_name"]), Qt.ItemDataRole.BackgroundRole) is not None
    assert m.data(m.index(0, COLIDX["species_name"]), Qt.ItemDataRole.BackgroundRole) is None


def test_filter_wizard_completer_offers_multi_word_matches_in_its_popup():
    """QCompleter must not re-filter the proxy's rows by plain prefix ("rut mac" showed nothing)."""
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLineEdit
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    app = QApplication.instance() or QApplication([])
    from src.views.components.filter_wizard.fuzzy import FuzzyCompleter, picking_from_popup
    e = QLineEdit()
    c = FuzzyCompleter(["Rutpela maculata", "Carabus nemoralis"], e)
    e.setCompleter(c)
    e.show()
    picked, entered = [], []
    c.activated.connect(picked.append)
    e.returnPressed.connect(lambda: None if picking_from_popup(e) else entered.append(e.text()))
    QTest.keyClicks(e, "rut mac")
    app.processEvents()
    assert c.completionCount() == 1
    QTest.keyClick(c.popup(), Qt.Key.Key_Down)
    QTest.keyClick(c.popup(), Qt.Key.Key_Return)
    assert picked == ["Rutpela maculata"]
    assert entered == []                  # the Enter handler stood aside: no chip for "rut mac"
    QTest.keyClicks(e, "carabus")             # no popup pick: Enter takes the typed text as before
    c.popup().hide()
    QTest.keyClick(e, Qt.Key.Key_Return)
    assert entered and entered[-1].endswith("carabus")


def test_observations_filter_wizard_loads_your_species(monkeypatch):
    """The What card's Species box had no suggestions: the species query always failed."""
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.components.filter_wizard import filter_wizard as fw
    from src.models import database

    class DB:
        def execute_main(self, sql, params=()):
            assert "species_name" in sql
            return [("Carabus nemoralis",), ("Rutpela maculata",)]

    class Uksi:
        def get_orders(self): return ["Coleoptera"]
        def get_families(self): return ["Cerambycidae"]

    monkeypatch.setattr(database, "get_database", lambda: DB())
    w = fw.FilterWizard.__new__(fw.FilterWizard)
    w._taxon_data_loaded, w._uksi_model = False, Uksi()
    w._ensure_taxon_data_loaded()
    assert w._species_list == ["Carabus nemoralis", "Rutpela maculata"]
