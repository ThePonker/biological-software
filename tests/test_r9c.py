"""Round 9 C (12 Oct 2026): Drawer in hand -- remove from a drawer, move between drawers,
the Drawers list and Empty this drawer; Edit Specimen keeps the curatorial fields."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared import drawer_assign as da  # noqa: E402
from shared.checklist_order import Checklist  # noqa: E402

ROWS = [
    # id, species, order, family, storage, drawer, condition, prep, sort key
    (1, "Nebria brevicollis", "Coleoptera", "Carabidae", None, None, None, None, 5000200),
    (2, "Carabus nemoralis", "Coleoptera", "Carabidae", "Cabinet 2", "Drawer 1", "Damaged", "Pinned", 5000100),
    (3, "Carabus violaceus", "Coleoptera", "Carabidae", "Cabinet 1", "Drawer 9", None, None, 5000101),
    (4, "Carabus violaceus", "Coleoptera", "Carabidae", "Cabinet 1", "Drawer 9", "Good", None, 5000101),
    (5, "Syrphus ribesii", "Diptera", "Syrphidae", "Cabinet 1", "Drawer 10", None, None, 23000500),
    (6, "Syrphus vitripennis", "Diptera", "Syrphidae", "Box", None, None, None, 23000501),
]


def _make(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE specimens (id INTEGER PRIMARY KEY, species_name, order_name, family,
                    date_collected, site_name, sex, storage_location, drawer_number, condition,
                    preparation_type, taxonomic_sort_key, updated_at)""")
    conn.executemany("INSERT INTO specimens (id, species_name, order_name, family, storage_location, "
                     "drawer_number, condition, preparation_type, taxonomic_sort_key) "
                     "VALUES (?,?,?,?,?,?,?,?,?)", ROWS)
    conn.commit()
    return conn


def _specs(conn):
    return da.load_specimens(conn, checklist=Checklist())


def _row(conn, sid):
    return conn.execute("SELECT storage_location, drawer_number, condition, preparation_type "
                        "FROM specimens WHERE id=?", (sid,)).fetchone()


# ---------------------------------------------------------------- pure: plan()
def test_remove_clears_storage_and_drawer_only():
    conn = _make()
    specs = _specs(conn)
    ch = da.plan(specs, [4], "Cabinet 1", "Drawer 9", condition="Good", remove=[3])
    assert sorted(ch) == [(3, "drawer_number", "Drawer 9", ""), (3, "storage_location", "Cabinet 1", "")]
    assert da.outline(ch, specs, "Cabinet 1", "Drawer 9") == [("Remove from Cabinet 1 · Drawer 9", 1)]
    assert da.apply(conn, ch) == 2
    assert _row(conn, 3) == (None, None, None, None)              # NULL, not ''
    assert _row(conn, 4) == ("Cabinet 1", "Drawer 9", "Good", None)


def test_remove_refused_unless_in_this_drawer():
    specs = _specs(_make())
    with pytest.raises(ValueError, match="not recorded in"):
        da.plan(specs, [], "Cabinet 1", "Drawer 9", remove=[5])   # in Drawer 10
    with pytest.raises(ValueError, match="not recorded in"):
        da.plan(specs, [], "Cabinet 1", "Drawer 9", remove=[1])   # in no drawer
    with pytest.raises(ValueError, match="both ticked"):
        da.plan(specs, [3], "Cabinet 1", "Drawer 9", remove=[3])


def test_move_needs_move_true_and_writes_both_fields():
    conn = _make()
    specs = _specs(conn)
    with pytest.raises(ValueError, match="recorded in"):
        da.plan(specs, [3], "Cabinet 2", "Drawer 1")
    ch = da.plan(specs, [3, 1], "Cabinet 2", "Drawer 1", move=True)
    assert sorted(ch) == sorted([(3, "storage_location", "Cabinet 1", "Cabinet 2"),
                                 (3, "drawer_number", "Drawer 9", "Drawer 1"),
                                 (1, "storage_location", "", "Cabinet 2"),
                                 (1, "drawer_number", "", "Drawer 1")])
    assert da.outline(ch, specs, "Cabinet 2", "Drawer 1") == [
        ("Add to Cabinet 2 · Drawer 1", 1), ("Move from Cabinet 1 · Drawer 9 to Cabinet 2 · Drawer 1", 1)]
    # a move into a storage location with no drawer clears the old drawer
    ch = da.plan(specs, [5], "Box", "", move=True)
    assert sorted(ch) == [(5, "drawer_number", "Drawer 10", ""), (5, "storage_location", "Cabinet 1", "Box")]
    da.apply(conn, ch)
    assert _row(conn, 5)[:2] == ("Box", None)


def test_drawers_list_and_in_drawer():
    specs = _specs(_make())
    assert da.drawers(specs) == [("Box", "", 1), ("Cabinet 1", "Drawer 9", 2),
                                 ("Cabinet 1", "Drawer 10", 1), ("Cabinet 2", "Drawer 1", 1)]
    assert sorted(da.in_drawer(specs, "Cabinet 1", "Drawer 9")) == [3, 4]
    assert da.in_drawer(specs, "Cabinet 1", "") == []
    ch = da.plan(specs, [], "Cabinet 1", "Drawer 9", remove=[3, 4])
    assert da.outline(ch, specs, "Cabinet 1", "Drawer 9") == [("Remove from Cabinet 1 · Drawer 9", 2)]


def test_old_rules_unchanged():
    specs = _specs(_make())
    assert da.plan(specs, [3, 4], "Cabinet 1", "Drawer 9") == []               # already here
    ch = da.plan(specs, [1], "Cabinet 1", "Drawer 9", condition="Good", preparation="Pinned")
    assert da.outline(ch, specs, "Cabinet 1", "Drawer 9") == [
        ("Add to Cabinet 1 · Drawer 9", 1), ("Fill condition", 1), ("Fill preparation", 1)]


# ---------------------------------------------------------------- dialog, offscreen
@pytest.fixture
def dlg(qapp, tmp_path, monkeypatch):
    db = tmp_path / "observatum.db"
    _make(str(db)).close()
    from src.views.collection import drawer_assign_dialog as m
    monkeypatch.setattr(m.DrawerAssignDialog, "_preview", lambda self, *a, **k: True)
    monkeypatch.setattr(m.DrawerAssignDialog, "_backup", lambda self: True)
    monkeypatch.setattr(m.DrawerAssignDialog, "_info", lambda self, *a: None)
    d = m.DrawerAssignDialog(None, db_path=str(db))
    d.asked = []
    d._ask = lambda title, text, yes="Move here": d.asked.append(text) or d.answer
    d.answer = True
    d.db = db
    return d


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _item(d, sid):
    from PySide6.QtCore import Qt
    for i in range(d.list.topLevelItemCount()):
        it = d.list.topLevelItem(i)
        if it.data(0, Qt.ItemDataRole.UserRole) == sid:
            return it
    raise AssertionError(f"specimen {sid} not shown")


def _click(d, sid, on):
    from PySide6.QtCore import Qt
    _item(d, sid).setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)


def _db_row(d, sid):
    conn = sqlite3.connect(d.db)
    try:
        return _row(conn, sid)
    finally:
        conn.close()


def test_dialog_drawer_contents_show_ticked_and_untick_removes(dlg):
    from PySide6.QtCore import Qt
    dlg.go_to("Cabinet 1", "Drawer 9")
    assert _item(dlg, 3).checkState(0) == Qt.CheckState.Checked
    assert _item(dlg, 4).checkState(0) == Qt.CheckState.Checked
    assert dlg.lbl_count.text() == "2 in this drawer"
    _click(dlg, 3, False)
    assert dlg.lbl_count.text() == "1 in this drawer (1 to remove)"
    assert "to be removed" in _item(dlg, 3).text(5)
    ch = dlg.plan_changes()
    assert da.outline(ch, dlg._specs, "Cabinet 1", "Drawer 9") == [("Remove from Cabinet 1 · Drawer 9", 1)]
    saved = []
    dlg.saved.connect(saved.append)
    dlg._save()
    assert saved == [2]
    assert _db_row(dlg, 3) == (None, None, None, None)
    assert _db_row(dlg, 4) == ("Cabinet 1", "Drawer 9", "Good", None)
    assert dlg.lbl_count.text() == "1 in this drawer"


def test_dialog_move_one_with_confirm_and_decline(dlg):
    from PySide6.QtCore import Qt
    dlg.go_to("Cabinet 2", "Drawer 1")
    dlg.show_choice.set("all")                  # R10: was chk_placed
    dlg.answer = False
    _click(dlg, 5, True)
    assert dlg.asked and "Cabinet 1 · Drawer 10" in dlg.asked[-1]
    assert _item(dlg, 5).checkState(0) == Qt.CheckState.Unchecked      # declined: unticked again
    assert 5 not in dlg._ticked
    dlg.answer = True
    _click(dlg, 5, True)
    assert "moving here" in _item(dlg, 5).text(5)
    assert dlg.lbl_count.text() == "2 in this drawer (1 to move)"
    ch = dlg.plan_changes()
    assert da.outline(ch, dlg._specs, "Cabinet 2", "Drawer 1") == [
        ("Move from Cabinet 1 · Drawer 10 to Cabinet 2 · Drawer 1", 1)]
    dlg._save()
    assert _db_row(dlg, 5)[:2] == ("Cabinet 2", "Drawer 1")


def test_dialog_move_all_shown_and_tick_all_skips_others(dlg):
    dlg.go_to("Cabinet 2", "Drawer 1")
    dlg.show_choice.set("all")                  # R10: was chk_placed
    dlg._tick_shown(True)                       # free one ticked, others' drawers left alone
    assert dlg._ticked == {1}
    dlg._move_all_shown()
    assert "Move 4 specimens" in dlg.asked[-1] and "from Cabinet 1 · Drawer 9: 2" in dlg.asked[-1]
    assert dlg._ticked == {1, 3, 4, 5, 6}
    ch = dlg.plan_changes()
    out = dict(da.outline(ch, dlg._specs, "Cabinet 2", "Drawer 1"))
    assert out == {"Add to Cabinet 2 · Drawer 1": 1,
                   "Move from Cabinet 1 · Drawer 9 to Cabinet 2 · Drawer 1": 2,
                   "Move from Cabinet 1 · Drawer 10 to Cabinet 2 · Drawer 1": 1,
                   "Move from Box to Cabinet 2 · Drawer 1": 1}
    dlg._save()
    conn = sqlite3.connect(dlg.db)
    assert conn.execute("SELECT COUNT(*) FROM specimens WHERE storage_location='Cabinet 2' "
                        "AND drawer_number='Drawer 1'").fetchone()[0] == 6
    conn.close()


def test_dialog_unticks_dropped_when_drawer_changes(dlg):
    dlg.go_to("Cabinet 1", "Drawer 9")
    _click(dlg, 3, False)
    assert dlg._unticked == {3}
    dlg.go_to("Cabinet 1", "Drawer 10")
    assert dlg._unticked == set()


def test_drawers_dialog_and_empty_this_drawer(dlg):
    from src.views.collection.drawer_preview import DrawersDialog, PreviewDialog
    dd = DrawersDialog(dlg._specs, dlg)
    assert dd.tree.topLevelItemCount() == 3                        # Box, Cabinet 1, Cabinet 2
    assert not dd.btn_empty.isEnabled()
    assert dd.select("Cabinet 1", "Drawer 9")
    dd._done("empty")
    assert dd.action == ("empty", "Cabinet 1", "Drawer 9")
    ch = da.plan(dlg._specs, [], "Cabinet 1", "Drawer 9", remove=[3, 4])
    pv = PreviewDialog(ch, dlg._by_id, "Cabinet 1", "Drawer 9", dlg)
    assert pv.lines == ["Remove from Cabinet 1 · Drawer 9: 2 specimens"]
    assert dlg.empty_drawer("Cabinet 1", "Drawer 9") == 4
    assert _db_row(dlg, 4) == (None, None, "Good", None)           # condition kept
    assert dlg.empty_drawer("Cabinet 1", "Drawer 9") == 0          # already empty
    assert ("Cabinet 1", "Drawer 9") not in [(s, d) for s, d, _ in da.drawers(dlg._specs)]


def test_backup_failure_writes_nothing(dlg, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(type(dlg), "_backup", lambda self: False)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    assert dlg.empty_drawer("Cabinet 1", "Drawer 9") == 0
    assert _db_row(dlg, 3)[:2] == ("Cabinet 1", "Drawer 9")


# ---------------------------------------------------------------- C4: Edit Specimen
def test_edit_specimen_keeps_and_edits_curatorial_fields(qapp):
    from src.views.dialogs.add_specimen_dialog import AddSpecimenDialog
    spec = {"id": 9, "species_name": "Carabus violaceus", "order_name": "Coleoptera",
            "family": "Carabidae", "preparation_type": "Carded", "condition": "Good",
            "storage_location": "Cabinet 1", "drawer_number": "Drawer 9"}
    d = AddSpecimenDialog(None, None, None, existing_specimen=spec)
    data = d.get_specimen_data()
    assert (data["preparation_type"], data["condition"], data["storage_location"],
            data["drawer_number"]) == ("Carded", "Good", "Cabinet 1", "Drawer 9")
    d.storage_combo.setCurrentText("Cabinet 3")         # a name not in the fixed list
    d.drawer_edit.setText("Drawer 4")
    data = d.get_specimen_data()
    assert (data["storage_location"], data["drawer_number"]) == ("Cabinet 3", "Drawer 4")
    d.storage_combo.setCurrentText("")
    d.drawer_edit.setText("")
    data = d.get_specimen_data()
    assert (data["storage_location"], data["drawer_number"]) == ("", "")
