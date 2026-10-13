"""Round 11 A (13 Oct 2026, backlog 17): the Filter Wizard's What dialog has ONE search box.

Species, whole groups (by a common word too), orders, families and taxon groups in one list
drawn by the shared painter (common name and family on every species row); each pick a chip
saying what it is; the filters dict keeps the keys the four old boxes gave (species / group /
taxon_group / family), so saved filters made before still load and keep the same records.
Offscreen; the data copy is read only.
"""
import os

import pytest

import paths

DB = str(paths.OBSERVATUM_DB)
GROUP = "All Coccinellidae (ladybirds) — group"

# What the four old boxes put in the filters for each test pick (measured on the Round 10
# code, 13 Oct, observation copy of 10 Oct: 901 / 8,174 / 795 / 996 / 62 records)
OLD = {
    "ladybird": {"species": [GROUP]},                          # Species box, group choice
    "Coleoptera": {"taxon_group": ["Coleoptera"]},              # Order box
    "Cerambycidae": {"family": ["Cerambycidae"]},               # Family box
    "insect - butterfly": {"group": ["Butterflies (Lepidoptera)"]},   # Taxon group box
    "Rutpela maculata": {"species": ["Rutpela maculata"]},      # Species box
}


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def values():
    if not os.path.exists(DB) or not paths.UKSI_DB.exists():
        pytest.skip("needs the data copies")
    from src.services.filter_builder import tab_values
    return tab_values(DB, "observations")


def _dialog(values, current=None):
    from src.views.components.filter_wizard.what_filter_dialog import WhatFilterDialog
    v = values
    return WhatFilterDialog(current_values=current, species_list=v["species"],
                            taxon_groups=v["orders"], family_list=v["families"],
                            group_list=v["groups"], species_info=v["species_info"])


def _rows(dialog, text):
    """[(row text as the box shows it, row as the painter draws it)] for typed text."""
    from shared.species_list_delegate import HIT_ROLE, row_text
    c = dialog._completer
    c.setCompletionPrefix(text)
    m = c.completionModel()
    return [(m.data(m.index(i, 0)), row_text(m.data(m.index(i, 0), HIT_ROLE)))
            for i in range(m.rowCount())]


def _pick(dialog, text, row):
    """Choose a row from the list, as a click or arrow keys and Enter do."""
    shown = [r[0] for r in _rows(dialog, text)]
    assert row in shown, (text, shown[:10])
    dialog._on_completer_activated(row)


def test_one_box_replaces_the_four(qapp, values):
    from PySide6.QtWidgets import QLineEdit
    d = _dialog(values)
    boxes = d.findChildren(QLineEdit)
    assert boxes == [d._search_input]
    assert d._search_input.placeholderText().startswith("Search species, groups, families, orders")


def test_rows_say_what_they_are(qapp, values):
    d = _dialog(values)
    # Wil: "blackbi" showed only "Turdus merula"
    shown, drawn = _rows(d, "blackbi")[0]
    assert shown == "Turdus merula"
    assert "Blackbird" in drawn and "Turdidae" in drawn
    # a common word naming a group: the group first, saying its rank, then its species
    rows = _rows(d, "ladybird")
    assert rows[0][0] == GROUP and rows[0][1].endswith("Family")
    assert any("Ladybird" in r[1] and "Coccinellidae" in r[1] for r in rows[1:])
    # an order and a family from the tab's own lists, ahead of the species
    rows = _rows(d, "Coleoptera")
    assert rows[0] [0] == "Coleoptera — order" and rows[0][1].endswith("Order")
    assert rows[1][0] == "Beetles (Coleoptera) — taxon group"
    assert _rows(d, "ceramb")[0][0] == "Cerambycidae — family"
    assert "Coleoptera" in _rows(d, "ceramb")[0][1]          # the family's order, in grey
    # a taxon group found by its iRecord value
    rows = _rows(d, "insect - butterfly")
    assert rows[0][0] == "Butterflies (Lepidoptera) — taxon group"
    assert "insect - butterfly" in rows[0][1] and rows[0][1].endswith("taxon group")
    # multi-word species search still works
    assert _rows(d, "rut mac")[0][0] == "Rutpela maculata"


def test_rows_are_tall_enough(qapp, values):
    """Each row's height comes from its fonts (no clipped g, p, y)."""
    from PySide6.QtGui import QFontMetrics
    d = _dialog(values)
    _rows(d, "ladybird")
    popup = d._completer.popup()
    model = popup.model()
    assert model.rowCount() > 2
    need = QFontMetrics(popup.font()).height()
    for i in range(3):
        assert popup.sizeHintForRow(i) >= need


def test_each_kind_picked_gives_the_old_keys_and_the_same_records(qapp, values):
    from PySide6.QtWidgets import QLabel
    from src.services.filter_builder import matching_ids
    picks = {
        "ladybird": ("ladybird", GROUP, "Family: All Coccinellidae (ladybirds)"),
        "Coleoptera": ("Coleoptera", "Coleoptera — order", "Order: Coleoptera"),
        "Cerambycidae": ("ceramb", "Cerambycidae — family", "Family: Cerambycidae"),
        "insect - butterfly": ("insect - butterfly",
                               "Butterflies (Lepidoptera) — taxon group",
                               "Taxon group: Butterflies (Lepidoptera)"),
        "Rutpela maculata": ("rut mac", "Rutpela maculata", "Species: Rutpela maculata"),
    }
    together = _dialog(values)
    for name, (text, row, chip) in picks.items():
        d = _dialog(values)
        _pick(d, text, row)
        _pick(together, text, row)
        assert d.get_values() == OLD[name]
        assert d.chip_texts() == [chip]
        new = matching_ids(DB, "observations", d.get_values())
        assert new == matching_ids(DB, "observations", OLD[name]) and new
        assert chip in [w.text() for w in d.findChildren(QLabel)]
    # several chips in the one list: any of them (as the four boxes together)
    merged = {}
    for f in OLD.values():
        for k, v in f.items():
            merged.setdefault(k, []).extend(v)
    assert together.get_values() == merged
    assert matching_ids(DB, "observations", together.get_values()) == \
        matching_ids(DB, "observations", merged)
    assert len(together.chip_texts()) == 5


def test_enter_adds_what_the_text_names(qapp, values):
    d = _dialog(values)
    for text in ("blackbird", "Coleoptera", "insect - butterfly", "ladybird", "zzqx"):
        d._search_input.setText(text)
        d._on_enter()
        assert d._search_input.text() == ""
    assert d.chip_texts() == ["Species: Turdus merula (Blackbird)", "Order: Coleoptera",
                              "Taxon group: Butterflies (Lepidoptera)",
                              "Family: All Coccinellidae (ladybirds)", "Species: *zzqx*"]
    assert d.get_values() == {"species": ["Turdus merula", GROUP, "~zzqx"],
                              "taxon_group": ["Coleoptera"],
                              "group": ["Butterflies (Lepidoptera)"]}
    # the same pick twice is one chip
    d._search_input.setText("Coleoptera")
    d._on_enter()
    assert d.get_values()["taxon_group"] == ["Coleoptera"]


def test_old_saved_filter_loads_into_the_one_list(qapp, values, tmp_path):
    """A filter saved with the four boxes: its chips show in the one list, saying what each
    is, and Apply gives back the same dict -- the same records."""
    from src.services.filter_builder import matching_ids
    from src.services.saved_filters_service import SavedFiltersService
    old_what = {"species": ["Rutpela maculata", GROUP],
                "group": ["Butterflies (Lepidoptera)"],
                "taxon_group": ["Coleoptera", "~Hemip"],
                "family": ["Cerambycidae"]}
    svc = SavedFiltersService(filters_file=tmp_path / "saved_filters.json")
    assert svc.save_filter("before R11", {"what": old_what}, tab="observations")
    loaded = SavedFiltersService(filters_file=tmp_path / "saved_filters.json")
    what = loaded.get_filter("before R11", tab="observations")["what"]
    d = _dialog(values, current=what)
    assert d.chip_texts() == [
        "Species: Rutpela maculata", "Family: All Coccinellidae (ladybirds)",
        "Taxon group: Butterflies (Lepidoptera)", "Order: Coleoptera", "Order: *Hemip*",
        "Family: Cerambycidae"]
    assert d.get_values() == old_what
    assert matching_ids(DB, "observations", d.get_values()) == \
        matching_ids(DB, "observations", old_what)
    # one value instead of a list (older callers) still loads
    d2 = _dialog(values, current={"family": "Cerambycidae"})
    assert d2.get_values() == {"family": ["Cerambycidae"]}


def test_clear_cancel_apply_and_fits_a_laptop(qapp, values):
    from PySide6.QtWidgets import QDialog, QPushButton
    d = _dialog(values, current={"species": ["Turdus merula"], "family": ["Cerambycidae"]})
    names = [b.text() for b in d.findChildren(QPushButton)]
    for n in ("Clear", "Cancel", "Apply Filters", "Clear All"):
        assert n in names
    d._clear_btn.click()
    assert d.get_values() == {} and d.chip_texts() == []
    d._cancel_btn.click()
    assert d.result() == QDialog.DialogCode.Rejected
    d2 = _dialog(values, current={"family": ["Cerambycidae"]})
    d2._apply_btn.click()
    assert d2.result() == QDialog.DialogCode.Accepted
    assert d2.get_values() == {"family": ["Cerambycidae"]}
    hint = d2.sizeHint().expandedTo(d2.minimumSize())
    assert hint.width() <= 1280 and hint.height() <= 720 - 60


def test_wizard_passes_common_names_to_the_dialog(qapp, values):
    from src.views.components.filter_wizard import FilterWizard
    w = FilterWizard(tab_name="observations")
    w.set_db_path(DB)
    w._ensure_tab_values()
    assert w._species_info["Turdus merula"]["common"] == "Blackbird"
    assert values["species_info"]["Turdus merula"]["family"] == "Turdidae"


def test_painter_draws_a_plain_taxon_group_and_a_group_rank():
    from shared.species_list_delegate import row_text
    assert row_text({"group_label": GROUP, "rank": "Family"}) == f"{GROUP}  Family"
    assert row_text({"group_label": GROUP}) == GROUP         # other lists: unchanged
    assert row_text({"scientific": "Spiders (Araneae)", "plain": True,
                     "common": "spider (Araneae)", "rank": "taxon group"}) == \
        "Spiders (Araneae)  spider (Araneae)  taxon group"


def test_keyboard_pick_and_enter_keep_the_other_chips(qapp, values):
    """Type, arrow down, Enter picks the row; Enter in the box never presses Clear All or a
    chip's x (F77: a dialog opened on stored chips lost them all on the first Enter)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    d = _dialog(values, current={"family": ["Cerambycidae"]})
    d.show()
    qapp.processEvents()
    box = d._search_input
    box.setFocus()
    QTest.keyClicks(box, "blackbi")
    qapp.processEvents()
    popup = d._completer.popup()
    if popup.isVisible():                     # offscreen: the pop-up normally opens
        QTest.keyClick(popup, Qt.Key.Key_Down)
        QTest.keyClick(popup, Qt.Key.Key_Return)
    else:
        QTest.keyClick(box, Qt.Key.Key_Return)
    QTest.qWait(80)
    assert d.chip_texts() == ["Family: Cerambycidae", "Species: Turdus merula (Blackbird)"]
    QTest.keyClick(box, Qt.Key.Key_Return)    # Enter on an empty box: nothing happens
    QTest.keyClicks(box, "Coleoptera")
    popup.hide()
    QTest.keyClick(box, Qt.Key.Key_Return)
    qapp.processEvents()
    assert d.get_values() == {"family": ["Cerambycidae"], "species": ["Turdus merula"],
                              "taxon_group": ["Coleoptera"]}
    assert d.isVisible()                      # Enter never closes the dialog
    d.close()


@pytest.mark.parametrize("kind", ["where", "who", "how"])
def test_enter_in_the_other_dialogs_keeps_their_chips(qapp, kind):
    """F77 in the Where, Who and How dialogs too: Enter pressed Clear All / a chip's x."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    from src.views.components.filter_wizard import (HowFilterDialog, WhereFilterDialog,
                                                     WhoFilterDialog)
    d = {"where": lambda: WhereFilterDialog(current_values={"site_name": ["Otmoor"]},
                                            vc_list=[], grid_ref_list=[], site_list=["Otmoor"]),
         "who": lambda: WhoFilterDialog(current_values={"recorder": ["W. J. Heeney"]},
                                        recorder_list=["W. J. Heeney"], determiner_list=[]),
         "how": lambda: HowFilterDialog(current_values={"method": ["Net"]},
                                        method_list=["Net"])}[kind]()
    before = d.get_values()
    assert before
    d.show()
    qapp.processEvents()
    box = d.findChildren(QLineEdit)[0]
    box.setFocus()
    QTest.keyClick(box, Qt.Key.Key_Return)
    qapp.processEvents()
    assert d.get_values() == before
    d.close()
