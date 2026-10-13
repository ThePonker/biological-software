"""Round 10 review (13 Oct 2026): the small defects the review of branches A, B and C fixed.

1. F69  picking a species with a common name from a quick filter bar's drop-down put
        "Western Honey Bee (Apis mellifera)" in the box, and the filter then found no
        record: the pick now puts the scientific name there (a group keeps its label).
2. F68  a group chip missed records whose TVK UKSI holds with no parent (Morimus funereus
        in the scheme): such a TVK is matched by name, like one UKSI doesn't hold.
3. F72  the cleaning report's "Came back from iRecord" rows are only rows still hidden.
4. F72  a delete request for a record that is also in iRecord never deletes it, whoever
        sends it: the "Also in iRecord" box, then at most a hide.
Offscreen; the data copies are read only.
"""
import os
import sqlite3
import sys

import pytest

pytest.importorskip("PySide6")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

DB = str(paths.OBSERVATUM_DB)
ORPHAN = "NHMSYS0020704743"          # Morimus funereus: in uksi.db's taxa with no parent_tvk


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _need_data():
    if not os.path.exists(DB) or not paths.UKSI_DB.exists():
        pytest.skip("no data copies")


# ---------------------------------------------------------------- 1. the pick fills the box
# with the filter text

def test_quick_bar_pick_puts_the_scientific_name_in_the_box(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit
    from src.views.components.species_box import attach_species_completer, species_items
    edit = QLineEdit()
    edit.show()
    edit.activateWindow()             # QLineEdit inserts a pick only while it has focus
    edit.setFocus()
    qapp.processEvents()
    if not edit.hasFocus():
        pytest.skip("no focus offscreen")
    items, names = species_items([("Apis mellifera", "Western Honey Bee"),
                                  ("Rutpela maculata", None),
                                  ("Coccinella septempunctata", "7-spot Ladybird")])
    c = attach_species_completer(edit, items, names)

    def pick(typed, row):
        edit.clear()
        QTest.keyClicks(edit, typed)
        qapp.processEvents()
        c.popup().setCurrentIndex(c.completionModel().index(row, 0))
        QTest.keyClick(c.popup(), Qt.Key.Key_Return)
        qapp.processEvents()
        return edit.text()

    assert pick("honey", 0) == "Apis mellifera"                  # not "Western Honey Bee (...)"
    assert pick("rut mac", 0) == "Rutpela maculata"
    try:
        from shared.species_search import get_index
        get_index(str(paths.UKSI_DB))
    except Exception:
        return
    _need_data()
    assert pick("ladybird", 0) == "All Coccinellidae (ladybirds) — group"   # a group: its label
    assert pick("ladybird", 1) == "Coccinella septempunctata"


# ---------------------------------------------------------------- 2. an orphan TVK

def test_group_filter_matches_a_parentless_uksi_taxon_by_name():
    _need_data()
    from shared.species_filter import tvks_under
    from shared.species_search import get_index
    u = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    try:
        if u.execute("SELECT parent_tvk FROM taxa WHERE tvk = ?", (ORPHAN,)).fetchone() != (None,):
            pytest.skip("Morimus funereus has a parent in this uksi.db")
    finally:
        u.close()
    idx = get_index(str(paths.UKSI_DB))
    coleoptera = idx.tvk_for_name("Coleoptera")
    chosen, unknown = tvks_under({coleoptera}, {ORPHAN, idx.tvk_for_name("Rutpela maculata")})
    assert ORPHAN in unknown and ORPHAN not in chosen
    assert idx.tvk_for_name("Rutpela maculata") in chosen
    # so a group chip on the scheme finds every Coleoptera row, orphans included
    from src.services.filter_builder import matching_ids
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        by_order = c.execute("SELECT COUNT(*) FROM recording_scheme WHERE order_name = 'Coleoptera'").fetchone()[0]
        orphan_rows = c.execute("SELECT COUNT(*) FROM recording_scheme WHERE species_tvk = ?", (ORPHAN,)).fetchone()[0]
    finally:
        c.close()
    if not orphan_rows:
        pytest.skip("no Morimus funereus rows in the copy")
    ids = matching_ids(DB, "recording_scheme", {"species": ["All Coleoptera (beetles) — group"]})
    assert len(ids) == by_order
    assert len(matching_ids(DB, "recording_scheme", {"species": ["All Morimus — group"]})) == orphan_rows


# ---------------------------------------------------------------- 3. returned rows are hidden rows

def test_returned_lists_only_rows_still_hidden(tmp_path):
    import shared.hidden_records as hr
    db = str(tmp_path / "r.db")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, species_name TEXT)")
    c.execute("INSERT INTO observations VALUES (1, 5001, 'Rutpela maculata'), (2, 5002, 'Clytus arietis')")
    with c:
        hr.ensure_schema(c)
    assert hr.hide(c, 1, 5001, "Rutpela maculata") and hr.hide(c, 2, 5002, "Clytus arietis")
    assert hr.after_download(c, [5001, 5002]) == 2
    assert [r[0] for r in hr.returned(c)] == [2, 1]
    c.execute("UPDATE observations SET hidden_at = NULL WHERE id = 2")     # live again, by hand
    c.commit()
    assert [r[0] for r in hr.returned(c)] == [1]                          # listed once, hidden only
    c.close()


# ---------------------------------------------------------------- 4. no real delete of an
# iRecord record through the tab's delete handler

def test_detail_delete_request_never_deletes_an_irecord_record(qapp, monkeypatch):
    from src.views.components import irecord_delete
    from src.views.observations.observation_detail_mixin import ObservationDetailMixin

    class Repo:
        deleted = []

        def delete(self, rid):
            self.deleted.append(rid)

    class Tab(ObservationDetailMixin):
        _obs_repo = Repo()
        _observation_model = None
        hidden = []
        loaded = 0

        def _load_data(self):
            self.loaded += 1

        class _Sig:
            def emit(self):
                pass
        records_changed = _Sig()

        def _on_detail_hide_requested(self, record):
            self.hidden.append(record["id"])

    asked = []
    monkeypatch.setattr(irecord_delete, "ask", lambda parent, count=1: asked.append(count) or irecord_delete.CANCEL)
    import src.views.components.delete_guard as guard
    monkeypatch.setattr(guard, "backup_before_delete", lambda parent, title="Delete": True)
    tab = Tab()
    tab._on_detail_delete_requested({"id": 1, "irecord_id": 5001, "species_name": "Rutpela maculata"})
    assert asked == [1] and Repo.deleted == [] and tab.hidden == []       # Cancel: nothing
    monkeypatch.setattr(irecord_delete, "ask", lambda parent, count=1: irecord_delete.HIDE)
    tab._on_detail_delete_requested({"id": 1, "irecord_id": 5001})
    assert Repo.deleted == [] and tab.hidden == [1]                        # hidden, not deleted
    tab._on_detail_delete_requested({"id": 2, "irecord_id": None})
    assert Repo.deleted == [2] and tab.loaded == 1                         # no ID: deleted as before
