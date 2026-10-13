"""Round 10, agent A (13 Oct 2026): search and filter boxes.

F68  a group choice in the Filter Wizard's What box ("All Coccinellidae (ladybirds) — group")
     filters the table (the chip held "Coccinellidae", which no species_name equals);
F69  the quick filter bars' Species box (Observation Data, Recording Scheme, Contributed)
     opens the shared species drop-down with group choices; typed text still filters;
F70  Examen's Species Database: group rows drawn like any other, a clicked group lists its
     species with a way back, and the result cap is 1,000 with a message when it is hit.
Offscreen; the data copy is read only.
"""
import os
import time

import pytest

import paths

DB = str(paths.OBSERVATUM_DB)
GROUP = "All Coccinellidae (ladybirds) — group"


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _need_data():
    if not os.path.exists(DB) or not paths.UKSI_DB.exists():
        pytest.skip("no data copies")


# ---------------------------------------------------------------- F68

def test_group_label_parses():
    from shared.species_search import group_label, parse_group_label
    assert parse_group_label(GROUP) == "Coccinellidae"
    assert parse_group_label("All Coleoptera — group") == "Coleoptera"
    assert parse_group_label(group_label("Cerambycidae", "Longhorn Beetles")) == "Cerambycidae"
    assert parse_group_label("Rutpela maculata") is None
    assert parse_group_label("") is None


def test_species_filter_understands_a_group_label():
    _need_data()
    import sqlite3
    from shared.species_filter import species_filter, table_tvks
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        present = table_tvks(lambda s: conn.execute(s).fetchall(), "observations")
        f = species_filter(GROUP, present)
        assert f.group == "Coccinellidae" and f.exact and f.tvks and not f.by_name_only
        clause, params = f.sql()
        n = conn.execute(f"SELECT COUNT(*) FROM observations WHERE {clause}", params).fetchone()[0]
        by_family = conn.execute(
            "SELECT COUNT(*) FROM observations WHERE family = 'Coccinellidae'").fetchone()[0]
        assert n == by_family > 0                      # 901 on the 10 Oct copy
        # in memory: a placed ladybird passes, another beetle with a TVK does not
        row = conn.execute("SELECT species_tvk, species_name FROM observations "
                           "WHERE family = 'Coccinellidae' AND species_tvk <> '' LIMIT 1").fetchone()
        assert f.matches(row[0], row[1], "")
        other = conn.execute("SELECT species_tvk, species_name FROM observations "
                             "WHERE family = 'Cerambycidae' AND species_tvk <> '' LIMIT 1").fetchone()
        assert not f.matches(other[0], other[1], "")
        assert f.matches("", "Coccinellidae sp.", "")   # no TVK: by the taxon's name
    finally:
        conn.close()


def test_wizard_group_chip_filters_every_tab():
    _need_data()
    import sqlite3
    from src.services.filter_builder import build_where, matching_ids
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        for tab, table in (("observations", "observations"), ("collection", "specimens"),
                           ("recording_scheme", "recording_scheme")):
            ids = matching_ids(DB, tab, {"species": [GROUP]})
            by_family = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE family = 'Coccinellidae'").fetchone()[0]
            assert len(ids) == by_family, (tab, len(ids), by_family)
        assert len(matching_ids(DB, "observations", {"species": [GROUP]})) > 0
        # a species chip is unchanged, and the two kinds combine with OR
        a = matching_ids(DB, "observations", {"species": ["Rutpela maculata"]})
        both = matching_ids(DB, "observations", {"species": ["Rutpela maculata", GROUP]})
        assert a and both > a
        # a superfamily: by TVK (no order/family column holds it)
        sup = matching_ids(DB, "observations", {"species": ["All Papilionoidea (butterflies) — group"]})
        assert len(sup) > 100
    finally:
        conn.close()
    # without a database the group still matches by its name columns
    sql, params = build_where("observations", {"species": [GROUP]})
    assert "species_tvk" in sql and any("coccinellidae" in str(p) for p in params)


def test_what_dialog_group_choice_becomes_a_working_chip(qapp):
    _need_data()
    from src.services.filter_builder import matching_ids, tab_values
    from src.views.components.filter_wizard.what_filter_dialog import WhatFilterDialog
    from PySide6.QtWidgets import QLabel
    v = tab_values(DB, "observations")
    d = WhatFilterDialog(species_list=v["species"], taxon_groups=v["orders"],
                         family_list=v["families"])
    c = d._search_input.completer()          # R11: the one What box
    c.setCompletionPrefix("ladybird")
    m = c.completionModel()
    first = m.data(m.index(0, 0))
    assert first == GROUP
    d._on_completer_activated(first)
    assert d.get_values() == {"species": [GROUP]}            # the chip names what was chosen
    labels = [w.text() for w in d._chips["species"][0].findChildren(QLabel)]
    chip = "Family: All Coccinellidae (ladybirds)"          # R11: the chip says what it is
    assert chip in labels
    assert len(matching_ids(DB, "observations", d.get_values())) > 0
    # reopened: the chip still says the group
    d2 = WhatFilterDialog(current_values=d.get_values(), species_list=v["species"])
    assert chip in [w.text() for w in d2._chips["species"][0].findChildren(QLabel)]


# ---------------------------------------------------------------- F69

def test_species_items_display():
    from src.views.components.species_box import species_items
    items, names = species_items([("Rutpela maculata", "Spotted Longhorn"),
                                  ("Rhagium mordax", None), ("", "x"),
                                  ("Rhagium mordax", "")])
    assert items == ["Spotted Longhorn (Rutpela maculata)", "Rhagium mordax"]
    assert names["Spotted Longhorn (Rutpela maculata)"] == "Rutpela maculata"


def _shown(completer, text, n=None):
    completer.setCompletionPrefix(text)
    m = completer.completionModel()
    rows = [m.data(m.index(i, 0)) for i in range(m.rowCount())]
    return rows if n is None else rows[:n]


def test_filter_bars_offer_the_shared_drop_down(qapp):
    _need_data()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from shared.species_list_delegate import HIT_ROLE, SpeciesListDelegate
    from src.models.database import get_database
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    db = get_database()
    db.set_main_path(DB)
    bar = ObservationFilterBar()
    bar.initialize_with_database(db)
    c = bar._species_completer
    assert c._source_model.rowCount() > 1000
    QTest.keyClick(bar.species_edit, Qt.Key.Key_R)                   # the pop-up gets its painter
    assert isinstance(c.popup().itemDelegate(), SpeciesListDelegate)
    bar.species_edit.clear()
    assert _shown(c, "rut mac")[0] == "Rutpela maculata"             # fuzzy words
    rows = _shown(c, "ladybird")
    assert rows[0] == GROUP and len(rows) > 5                       # the group first
    m = c.completionModel()
    assert m.data(m.index(0, 0), HIT_ROLE)["group_label"] == GROUP   # painted as a group
    assert m.data(m.index(1, 0), HIT_ROLE)["scientific"]
    # typed text keeps filtering: the bar's filter is the text itself
    bar.species_edit.setText("rut mac")
    assert bar.get_filters()["species"] == "rut mac"
    bar.species_edit.setText(GROUP)
    assert bar.get_filters()["species"] == GROUP
    # Recording Scheme: scoped to the scheme's species
    sb = SchemeFilterBar()
    sb.initialize_with_database(db)
    rows = _shown(sb._species_completer, "rhag")
    assert rows and all("Rhagium" in r for r in rows)
    assert _shown(sb._species_completer, "longhorn")[0].startswith("All Cerambycidae")
    assert _shown(sb._species_completer, "ladybird") == []           # no ladybirds in the scheme


def test_species_box_group_filters_the_records(qapp):
    _need_data()
    from src.models.database import get_database
    from src.repositories.observation_repository import ObservationRepository
    db = get_database()
    db.set_main_path(DB)
    repo = ObservationRepository(db)
    assert len(repo.search(species_name=GROUP, limit=999999)) == len(
        repo.search(species_name="Coccinellidae", limit=999999)) > 0
    assert len(repo.search(species_name="rut mac", limit=999999)) > 0


def test_contributed_tab_drop_down_and_group(qapp):
    _need_data()
    from src.models.database import get_database
    from src.views.contributed.contributed_tab import ContributedTab
    get_database().set_main_path(DB)
    tab = ContributedTab()
    tab.initialize()
    if tab._species_completer._source_model.rowCount() == 0:
        pytest.skip("no contributed records in the copy")
    rows = _shown(tab._species_completer, "carab")
    assert rows
    tab.search_edit.setText("All Carabidae (ground beetles) — group")
    tab._load_records()
    n = tab.model.rowCount()
    tab.search_edit.setText("")
    tab._load_records()
    assert 0 < n < tab.model.rowCount()


def test_scheme_choices_read_in_a_thread_feed_the_completer(qapp):
    _need_data()
    from src.models.database import get_database
    from src.views.scheme.scheme_filter_bar import SchemeFilterBar
    db = get_database()
    db.set_main_path(DB)
    choices = SchemeFilterBar.read_choices(db)
    items, names = choices["species"]
    assert len(items) > 10 and all(names[i] for i in items)


# ---------------------------------------------------------------- F70

def _examen_view(qapp):
    from shared.repositories.codex_repository import CodexRepository
    from Examen.species_database_view import SpeciesDatabaseView

    class NoPantheon:
        def get_species_profile(self, tvk):
            return None
    return SpeciesDatabaseView(CodexRepository(), NoPantheon())


def test_examen_group_rows_look_like_the_others(qapp):
    _need_data()
    from PySide6.QtCore import Qt
    from shared.species_list_delegate import HIT_ROLE
    v = _examen_view(qapp)
    v.search_input.setText("beetle")
    v._do_search()
    items = [v.results_list.item(i) for i in range(v.results_list.count())]
    groups = [it for it in items if it.data(HIT_ROLE).get("group_label")]
    species = [it for it in items if not it.data(HIT_ROLE).get("group_label")]
    assert len(groups) >= 2 and species
    # no row carries its own foreground: the painter colours every row the same
    assert all(it.data(Qt.ItemDataRole.ForegroundRole) is None for it in groups + species)
    assert v.results_list.count() > 100                     # the old cap stopped in the A's
    assert v.result_count.text().endswith("species found")


def test_examen_group_click_lists_its_species_and_back(qapp):
    _need_data()
    from shared.species_list_delegate import HIT_ROLE
    v = _examen_view(qapp)
    v.search_input.setText("weevil")
    v._do_search()
    n_search = v.results_list.count()
    items = [v.results_list.item(i) for i in range(n_search)]
    group = next(it for it in items if "Curculionidae" in it.data(HIT_ROLE).get("group_label", ""))
    t = time.time()
    v.results_list.setCurrentItem(group)
    assert time.time() - t < 2.0
    assert v.species_name_label.text() == "Curculionidae"
    assert v.results_list.count() > 300                      # 547 weevils on the 10 Oct uksi.db
    assert v.result_count.text().startswith(f"{v.results_list.count():,} species in Curculionidae")
    assert v.back_button.isVisibleTo(v)
    first = v.results_list.item(0).data(HIT_ROLE)
    assert first["scientific"] and not first["group_label"]
    v.results_list.setCurrentRow(0)                           # a member: its own profile
    assert v.species_name_label.text() == first["scientific"]
    assert v.results_list.count() > 300                       # the list stays
    v.back_button.click()
    assert v.results_list.count() == n_search and not v.back_button.isVisibleTo(v)
    v.search_input.setText("Rhagium")                        # a new search also returns
    v._do_search()
    assert not v.back_button.isVisibleTo(v) and 0 < v.results_list.count() < 50


def test_examen_cap_message_and_speed(qapp):
    _need_data()
    from Examen.species_database_view import SEARCH_LIMIT
    v = _examen_view(qapp)
    v.search_input.setText("rhag")
    v._do_search()                                           # the index is built here
    v.search_input.setText("ata")
    t = time.time()
    v._do_search()
    assert time.time() - t < 1.5
    assert v.results_list.count() == SEARCH_LIMIT == 1000
    assert v.result_count.text() == "First 1,000 shown — type more to narrow"
    v.search_input.setText("Rhagium")
    v._do_search()
    assert v.result_count.text().endswith("species found")


def test_codex_search_still_lists_groups_plainly(qapp):
    """Codex passed Test 31: its group rows and species rows carry no foreground of their own."""
    _need_data()
    from PySide6.QtCore import Qt
    from Codex.species_tab import SpeciesTab
    tab = SpeciesTab()
    tab.search_input.setText("weevil")
    tab._do_search()
    assert tab.results_list.count() > 2
    assert all(tab.results_list.item(i).data(Qt.ItemDataRole.ForegroundRole) is None
               for i in range(tab.results_list.count()))
