"""Round 9, agent A (12 Oct 2026): F49 species search lists, F50 see-through drop-down lists,
F51 the observation import's picked species, one wording and one row numbering.
Offscreen; the uksi.db copy is read only; no database is written."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

GROUP = " — group"
needs_uksi = pytest.mark.skipif(not os.path.exists(str(paths.UKSI_DB)),
                                reason="data/uksi.db not present")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def idx():
    from shared.species_search import get_index
    return get_index()


def _line_height(widget):
    """The font's line height, upright or italic, whichever is taller."""
    from PySide6.QtGui import QFont, QFontMetrics
    italic = QFont(widget.font())
    italic.setItalic(True)
    return max(QFontMetrics(widget.font()).height(), QFontMetrics(italic).height())


# ---------------------------------------------------------------- F49 labels

@pytest.mark.parametrize("sci, common, label", [
    ("Curculionidae", "Beetles (Weevils)", "All Curculionidae (weevils)"),
    ("Coleoptera", "Invertebrates (Beetles)", "All Coleoptera (beetles)"),
    ("Ephemeridae", "Mayfly (Ephemeridae)", "All Ephemeridae (mayflies)"),
    ("Ephemeroptera", "Mayflies (Greendrakes)", "All Ephemeroptera (mayflies, greendrakes)"),
    ("Diptera", "Fly", "All Diptera (flies)"),
    ("Coccinellidae", "Indet. Ladybird", "All Coccinellidae (ladybirds)"),
    ("Cerambycidae", "Longhorn Beetle", "All Cerambycidae (longhorn beetles)"),
    ("Coleoptera", "", "All Coleoptera"),
])
def test_group_labels_have_one_level_of_brackets(sci, common, label):
    from shared.species_search import group_label
    got = group_label(sci, common)
    assert got == label + GROUP
    assert got.count("(") <= 1 and got.count(")") <= 1


# ---------------------------------------------------------------- F49 scope and order

@needs_uksi
def test_no_plant_group_in_the_lists(idx):
    from shared.species_search import LIST_GROUP_KINGDOMS
    listed = idx.search("beetle", limit=25, group_kingdoms=LIST_GROUP_KINGDOMS)
    assert "Leptochloa" not in {r["scientific_name"] for r in listed}
    assert all(r["kingdom"] == "Animalia" for r in listed if r["is_group"])
    assert not any("((" in r["group_label"] for r in listed)
    # the filters (no scope given) still see every kingdom: what a filter box selects is unchanged
    everything = idx.search("beetle", limit=None)
    assert "Leptochloa" in {r["scientific_name"] for r in everything if r["is_group"]}
    from shared.species_filter import choose_taxa
    assert [r["scientific_name"] for r in choose_taxa("beetle")] == ["Coleoptera"]


@needs_uksi
@pytest.mark.parametrize("text, first", [("beetle", "Coleoptera"), ("ladybird", "Coccinellidae"),
                                         ("longhorn", "Cerambycidae"), ("moth", "Lepidoptera"),
                                         ("weevil", "Curculionidae")])
def test_a_group_word_lists_its_groups_first(idx, text, first):
    from shared.species_search import LIST_GROUP_KINGDOMS
    r = idx.search(text, limit=25, group_kingdoms=LIST_GROUP_KINGDOMS)
    assert r[0]["is_group"] and r[0]["group_first"] and r[0]["scientific_name"] == first
    n = sum(1 for x in r if x["group_first"])
    assert all(x["is_group"] for x in r[:n])
    species = [i for i, x in enumerate(r) if not x["is_group"]]
    assert species and species[0] == n                            # then the species
    later = [i for i, x in enumerate(r) if x["is_group"] and not x["group_first"]]
    assert all(i > species[-1] for i in later)                    # other groups after them


@needs_uksi
@pytest.mark.parametrize("text, first", [("Stag Beetle", "Lucanus cervus"),
                                         ("dor beetle", "Geotrupes stercorarius"),
                                         ("rhag mor", "Rhagium mordax"),
                                         ("Cerambycidae", "Cerambycidae")])
def test_not_a_group_word_keeps_species_first(idx, text, first):
    from shared.species_search import LIST_GROUP_KINGDOMS
    r = idx.search(text, limit=25, group_kingdoms=LIST_GROUP_KINGDOMS)
    assert r[0]["scientific_name"] == first and not r[0]["is_group"]
    assert not any(x["group_first"] for x in r)


@needs_uksi
def test_fly_is_not_flyingfishes(idx):
    """A word only begun ("fly" in "Flyingfishes") is not the group's name."""
    from shared.species_search import LIST_GROUP_KINGDOMS
    r = idx.search("fly", limit=25, group_kingdoms=LIST_GROUP_KINGDOMS)
    assert [x["scientific_name"] for x in r if x["group_first"]] == ["Diptera"]
    assert r[0]["group_label"] == "All Diptera (flies)" + GROUP


# ---------------------------------------------------------------- F49 drawing

@needs_uksi
def test_codex_list_is_plain_lines_tall_enough(qapp):
    from PySide6.QtWidgets import QLabel
    from Codex.species_tab import SpeciesTab
    from shared.species_list_delegate import HIT_ROLE, row_text
    tab = SpeciesTab()
    tab.resize(700, 500)
    tab.search_input.setText("beetle")
    tab._do_search()
    lst = tab.results_list
    assert not tab.results_frame.findChildren(QLabel)             # no boxed labels any more
    rows = [row_text(lst.item(i).data(HIT_ROLE)) for i in range(lst.count())]
    assert rows[0] == "All Coleoptera (beetles)" + GROUP
    assert not any("Leptochloa" in t or "((" in t for t in rows)
    assert any(t.startswith("Aclypea opaca") for t in rows)
    line = _line_height(lst)
    assert all(lst.sizeHintForRow(i) >= line for i in range(lst.count()))
    assert lst.height() >= sum(lst.sizeHintForRow(i) for i in range(min(lst.count(), 12)))
    tab.show()                                                      # it draws without error
    img = lst.viewport().grab().toImage()
    assert not img.isNull()
    lst.item(0).setSelected(True)
    tab._on_result_clicked(lst.item(0))                             # a group opens its list
    assert tab.search_input.text() == "Coleoptera"
    tab.close()
    tab.deleteLater()


@needs_uksi
def test_examen_list_rows_tall_enough(qapp):
    from Examen.species_database_view import SpeciesDatabaseView
    from shared.species_list_delegate import HIT_ROLE
    view = SpeciesDatabaseView(None, None)
    view.search_input.setText("ladybird")
    view._do_search()
    lst = view.results_list
    assert lst.count() and lst.item(0).data(HIT_ROLE)["group_label"].startswith("All Coccinellidae")
    line = _line_height(lst)
    assert all(lst.sizeHintForRow(i) >= line for i in range(lst.count()))


def test_record_entry_popup_rows_follow_the_font(qapp):
    """Observatum's species box (Quick Entry, Add Specimen, ...): no fixed 32 px rows."""
    from PySide6.QtGui import QFont
    from src.views.components.species_search import SpeciesSearch
    w = SpeciesSearch()
    w.resize(400, 30)
    hits = [{"scientific_name": "Aclypea opaca", "common_name": "Beet Carrion Beetle",
             "family": "Silphidae", "rank": "Species", "tvk": "A", "is_recorded": True},
            {"scientific_name": "Agabus brunneus", "family": "Dytiscidae", "rank": "Species",
             "tvk": "B", "old_name": "Agabus x"}]
    for size in (9, 14, 22):                                        # whatever the font size
        f = QFont(w.font())
        f.setPointSize(size)
        w._popup.setFont(f)
        w._show_popup(hits)
        line = _line_height(w._popup)
        assert all(w._popup.sizeHintForRow(i) >= line for i in range(2))
        assert w._popup.height() == w.popup_height() >= 2 * line
        w._popup.hide()


def test_delegate_rows_are_plain_text():
    from shared.species_list_delegate import hit_from_result, row_text
    hit = hit_from_result({"scientific_name": "Rhagium", "common_name": "Ribbed pine borers",
                           "rank": "Genus"})
    assert row_text(hit) == "Rhagium  Ribbed pine borers  Genus"
    hit = hit_from_result({"scientific_name": "Rhagium mordax", "rank": "Species",
                           "match_type": "fuzzy"})
    assert row_text(hit) == "Rhagium mordax  close spelling"


# ---------------------------------------------------------------- F49 Filter Wizard

@needs_uksi
def test_filter_wizard_offers_the_group_first(qapp):
    from PySide6.QtWidgets import QLineEdit
    from src.views.components.filter_wizard.fuzzy import SpeciesCompleter
    items = {"Green Longhorn (Adela reaumurella)": "Adela reaumurella",
             "Rhagium mordax": "Rhagium mordax", "Rutpela maculata": "Rutpela maculata"}
    box = QLineEdit()
    c = SpeciesCompleter(list(items), box, names=items)
    m = c.completionModel()
    for _ in range(2):                                              # rows are replaced, not piled up
        c.setCompletionPrefix("longhorn")
        shown = [m.data(m.index(i, 0)) for i in range(m.rowCount())]
        assert shown == ["All Cerambycidae (longhorn beetles)" + GROUP,
                         "Green Longhorn (Adela reaumurella)"]
    c.setCompletionPrefix("rhag mor")
    assert [m.data(m.index(i, 0)) for i in range(m.rowCount())] == ["Rhagium mordax"]
    assert c._source_model.rowCount() == len(items)


# ---------------------------------------------------------------- F50 drop-down lists

def test_combo_popups_are_solid(qapp):
    from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget
    import shared.opaque_popups as op
    from src.views.home.quick_entry_fields_mixin import QuickEntryFieldsMixin
    form = QWidget()
    form.setStyleSheet("QWidget { background: #ffffff; }")
    lay = QVBoxLayout(form)
    holder = type("Holder", (QuickEntryFieldsMixin,), {})()
    lay.addWidget(holder._create_project_field())                    # Quick Entry's Project box
    combo = holder.project_combo
    combo.addItems(["Choose a project...", "Hook Farm"])
    combo.setEnabled(True)
    styled = QComboBox()                                             # a list styled on purpose
    styled.setStyleSheet("QComboBox QAbstractItemView { background: #fff8e0; }")
    styled.addItems(["a", "b"])
    lay.addWidget(styled)
    earlier = op._installed               # an app's main() run by an earlier test installs it
    if earlier is not None:
        qapp.removeEventFilter(earlier)
        op._installed = None
    form.show()
    combo.showPopup()
    qapp.processEvents()
    assert op.is_see_through(combo.view())                          # the cause, without the fix
    combo.hidePopup()
    f = op.install(qapp, lambda: ("#fafafa", "#111111"))
    try:
        for c in (combo, styled):
            c.showPopup()
            qapp.processEvents()
            assert not op.is_see_through(c.view())
            c.hidePopup()
        assert "#fafafa" in combo.view().styleSheet()
        assert styled.view().styleSheet() == ""                     # left as it was
        assert op.install(qapp) is f                                # once per application
    finally:
        qapp.removeEventFilter(f)
        op._installed = earlier
        if earlier is not None:
            qapp.installEventFilter(earlier)
        form.deleteLater()


# ---------------------------------------------------------------- F51 import wizards

class _Accept:
    """Stands in for SpeciesSearchDialog: the user picks Abax parallelepipedus."""
    picked = {"scientific_name": "Abax parallelepipedus", "tvk": "NBNSYS0000005077",
              "common_name": "", "order_name": "Coleoptera", "family": "Carabidae",
              "kingdom": "Animalia", "rank": "Species"}

    def __init__(self, *a, **k):
        pass

    def exec(self):
        from PySide6.QtWidgets import QDialog
        return QDialog.DialogCode.Accepted

    def get_selected_species(self):
        return dict(self.picked)


def _obs_wizard(rows):
    from src.views.dialogs.observation_import_wizard import ObservationImportWizard
    from src.views.dialogs.observation_import_wizard.validation_worker import ImportMode
    w = ObservationImportWizard(parent=None, uksi_model=object(), vc_service=None, db=None)
    for card in w.mode_cards:
        if card.mode_id == "personal_upload":
            w._select_mode_card(card)
    w._setup_validation_table(ImportMode.PERSONAL_UPLOAD)
    for i, r in enumerate(rows):
        w._on_row_validated(i, r)
    w.validated_rows = rows
    return w


def test_observation_double_click_pick_keeps_what_the_file_had(qapp, monkeypatch):
    from src.views.dialogs.observation_import_wizard.validation_worker import ObservationImportRow
    from src.views.dialogs.row_status import RowStatus
    import src.views.dialogs.specimen_import_wizard.species_search_dialog as ssd
    monkeypatch.setattr(ssd, "SpeciesSearchDialog", _Accept)
    err = "Species not found in UKSI: Ab"
    rows = [ObservationImportRow(row_number=2, raw_data={}, status=RowStatus.VALID,
                                 species_name="Rhagium mordax", date="2024-06-01"),
            ObservationImportRow(row_number=3, raw_data={}, status=RowStatus.ERROR,
                                 species_name="Ab", date="2024-06-01", error_message=err)]
    w = _obs_wizard(rows)
    t = w.validation_table
    assert not (t.item(1, 2).flags() & t.item(1, 2).flags().ItemIsEditable)   # pick, not type
    w._on_cell_double_clicked(1, 2)
    row = w.validated_rows[1]
    msg = "File had 'Ab'; picked by you as Abax parallelepipedus"
    assert row.status == RowStatus.WARNING and row.warnings == [msg]
    assert row.species_name == "Abax parallelepipedus" and row.species_tvk == "NBNSYS0000005077"
    assert row.import_notes == "Imported as 'Ab'; picked by you as 'Abax parallelepipedus'"
    assert t.item(1, 0).text() == "⚠" and t.item(1, 7).text() == msg
    assert t.item(1, 2).text() == "Abax parallelepipedus"
    assert w._edited_row_indices == set()                           # applied at once
    assert w.warning_label.text() == "Warnings: 1" and w.error_label.text() == "Errors: 0"
    # a later revalidation of the row (a date edit) reads the file's name again: still picked
    again = ObservationImportRow(row_number=3, raw_data={}, status=RowStatus.ERROR,
                                 species_name="Ab", date="2024-06-02", error_message=err)
    w._on_row_revalidated(0, again)
    assert w.validated_rows[1] is again and again.warnings == [msg]
    assert again.import_notes == "Imported as 'Ab'; picked by you as 'Abax parallelepipedus'"
    w.deleteLater()


def test_one_wording_in_all_three_wizards():
    root = os.path.join(os.path.dirname(paths.__file__), "Observatum", "src", "views", "dialogs")
    for wizard in ("observation_import_wizard", "scheme_import_wizard", "specimen_import_wizard"):
        folder = os.path.join(root, wizard)
        for name in os.listdir(folder):
            if name.endswith(".py"):
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    assert "resolved by you" not in f.read(), (wizard, name)


def test_rows_numbered_as_a_spreadsheet_shows_them(qapp):
    from types import SimpleNamespace
    from PySide6.QtCore import Qt
    from src.views.dialogs.scheme_import_wizard.wizard_file_mixin import WizardFileMixin
    from src.views.dialogs.scheme_import_wizard.validation_table_model import (
        SchemeValidationTableModel)
    from src.views.dialogs.specimen_import_wizard.validation_table_model import (
        ValidationTableModel)
    from src.views.dialogs.import_common.validation_table_model import ROW_TOOLTIP
    rows = WizardFileMixin._create_import_rows(SimpleNamespace(raw_rows=[{}, {}, {}]))
    assert [r.row_number for r in rows] == [2, 3, 4]                # heading = row 1
    for model in (SchemeValidationTableModel(), ValidationTableModel()):
        col = model.COLUMNS.index("Row")
        assert model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) \
            == ROW_TOOLTIP
        assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) is None
    w = _obs_wizard([])
    assert w.validation_table.horizontalHeaderItem(1).toolTip() == ROW_TOOLTIP
    w.deleteLater()
