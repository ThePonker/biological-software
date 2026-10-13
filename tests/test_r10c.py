"""Round 10 C (13 Oct 2026): Drawer in hand tick boxes and "Show" choice (F74, F75), the
date pop-up calendar styled once for the application (F76), and backfill_taxon_groups.py
--fix-odd-keys (C4)."""
import importlib.util
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_r9c import _make  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dlg(qapp, tmp_path):
    db = tmp_path / "observatum.db"
    _make(str(db)).close()
    from src.views.collection import drawer_assign_dialog as m
    d = m.DrawerAssignDialog(None, db_path=str(db))
    d._ask = lambda *a, **k: True
    return d


# ---------------------------------------------------------------- F74: the suite's tick boxes
def test_list_tick_column_is_the_suite_delegate_and_rows_look_like_the_table(dlg):
    from src.views.collection.drawer_assign_list import COL_SPECIES, COL_TICK, HEADERS, SpecimenList
    from src.views.components.tick_column import TickDelegate
    from src.themes import theme
    assert isinstance(dlg.list, SpecimenList)
    assert isinstance(dlg.list.itemDelegateForColumn(COL_TICK), TickDelegate)
    assert dlg.list.tick_delegate._accent_key == "accent_collection"
    assert dlg.list.headerItem().text(COL_SPECIES) == "Species" and len(HEADERS) == 6
    assert dlg.list.alternatingRowColors()
    assert theme().get("accent_collection_light") in dlg.list.styleSheet()
    assert "height: 24px" in dlg.list.styleSheet()


def test_show_choice_radios_use_the_tick_mark_style(dlg):
    from src.themes import theme
    qss = dlg.show_choice.styleSheet()
    assert "QRadioButton::indicator:checked" in qss and theme().get("accent_collection") in qss
    assert "dot_" in qss and 'image: url("' in qss          # the drawn dot, as the tick box's tick
    assert dlg.show_choice.value() == "free"                 # the default, as the old check boxes


def test_click_anywhere_in_tick_cell_toggles_and_headings_have_no_tick(dlg, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from src.views.collection.drawer_assign_list import COL_TICK, ROLE_ID
    dlg.go_to("Cabinet 1", "Drawer 9")
    dlg.show(); qapp.processEvents()
    first = dlg.list.topLevelItem(0)
    assert first.data(COL_TICK, ROLE_ID) is None            # a genus heading
    assert first.checkState(COL_TICK) == Qt.CheckState.Unchecked
    it = next(dlg.list.topLevelItem(i) for i in range(dlg.list.topLevelItemCount())
              if dlg.list.topLevelItem(i).data(COL_TICK, ROLE_ID) == 1)
    assert it.checkState(COL_TICK) == Qt.CheckState.Unchecked
    rect = dlg.list.visualItemRect(it)
    pos = rect.topLeft()
    pos.setX(dlg.list.columnViewportPosition(COL_TICK) + 2)   # the cell's edge, not the box
    pos.setY(rect.center().y())
    QTest.mouseClick(dlg.list.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    assert it.checkState(COL_TICK) == Qt.CheckState.Checked and 1 in dlg._ticked
    hrect = dlg.list.visualItemRect(first)
    hpos = hrect.topLeft(); hpos.setX(pos.x()); hpos.setY(hrect.center().y())
    QTest.mouseClick(dlg.list.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, hpos)
    assert first.checkState(COL_TICK) == Qt.CheckState.Unchecked


# ---------------------------------------------------------------- F75: one "Show" choice
def test_show_choice_drives_the_list_as_the_two_boxes_did(dlg):
    dlg.go_to("Cabinet 1", "Drawer 9")
    assert dlg.list.specimen_ids() == [3, 4, 1]          # own drawer always + not in a drawer
    dlg.show_choice.set("all")
    assert dlg.list.specimen_ids() == [2, 3, 4, 1, 5, 6]
    dlg.show_choice.set("this")
    assert dlg.list.specimen_ids() == [3, 4]
    dlg.show_choice.set("free")
    assert dlg.list.specimen_ids() == [3, 4, 1]
    dlg._set_tick(5, True)                               # a ticked one stays shown whatever the choice
    dlg.show_choice.set("this")
    assert dlg.list.specimen_ids() == [3, 4, 5]
    assert [b.text() for b in dlg.show_choice._buttons.values()] == [
        "Not yet in a drawer", "All specimens", "Only this drawer"]
    assert not hasattr(dlg, "chk_free") and not hasattr(dlg, "chk_placed")


# ---------------------------------------------------------------- F76: the calendar
def test_calendar_styled_once_for_every_date_edit(qapp):
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtWidgets import QDateEdit
    from shared import calendar_style
    from src.themes import theme
    calendar_style.install(qapp, lambda: theme().calendar_colours())
    e = QDateEdit()
    e.setCalendarPopup(True)
    cal = e.calendarWidget()
    e.show(); cal.show(); qapp.processEvents()
    assert calendar_style.is_styled(cal)
    qss = cal.styleSheet()
    assert theme().get("primary") in qss and "qt_calendar_navigationbar" in qss
    assert "chevron_l" in qss and "chevron_r" in qss                      # themed arrows
    assert cal.weekdayTextFormat(Qt.DayOfWeek.Saturday).foreground().color().name() == theme().get("warning")
    assert cal.weekdayTextFormat(Qt.DayOfWeek.Monday).foreground().color().name() == theme().get("text_primary")
    today = cal.dateTextFormat(QDate.currentDate())
    assert today.foreground().color().name() == theme().get("primary") and today.font().bold()
    assert theme().get("primary") in theme().calendar_style()
    # the Quick Entry form's own calendar and the date filter's accent one
    from src.views.home.quick_entry import QuickEntryForm
    f = QuickEntryForm()
    c2 = f.date_edit.calendarWidget()
    f.show(); c2.show(); qapp.processEvents()
    assert calendar_style.is_styled(c2)
    from src.views.components.date_filter_widget import DateFilterWidget
    w = DateFilterWidget(accent_color="#b8860b")
    assert calendar_style.is_styled(w._calendar) and "#b8860b" in w._calendar.styleSheet()
    import DataEntry.theme as de
    assert set(de.calendar_colours()) == set(calendar_style.COLOURS)


# ---------------------------------------------------------------- C4: --fix-odd-keys
OLD = "000204010603030I0202010000000000000000000000000000"


@pytest.fixture
def dbs(tmp_path):
    u = sqlite3.connect(tmp_path / "uksi.db")
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              'kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT, family TEXT, sort_code INTEGER, '
              'superfamily TEXT)')
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        ("B1", "Carabus nemoralis", "Species", None, "Animalia", "Arthropoda", "Insecta", "Coleoptera",
         "Carabidae", 18000, "Caraboidea"),
        ("O1", "Aeshna isoceles", "Species", None, "Animalia", "Arthropoda", "Insecta", "Odonata",
         "Aeshnidae", 48170, None),
    ])
    u.execute("CREATE TABLE name_map (tvk TEXT, recommended_tvk TEXT, name TEXT, recommended_name TEXT)")
    u.execute("INSERT INTO name_map VALUES ('O2', 'O1', 'Isoaeschna isoceles', 'Aeshna isoceles')")
    u.commit()
    u.close()
    o = sqlite3.connect(tmp_path / "observatum.db")
    o.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_tvk TEXT, source TEXT, "
              "order_name TEXT, species_name TEXT, taxon_group TEXT, kingdom TEXT, taxon_rank TEXT, "
              "superfamily TEXT, taxonomic_sort_key)")
    o.executemany("INSERT INTO observations (id, species_tvk, order_name, species_name, taxon_group, "
                  "kingdom, taxon_rank, taxonomic_sort_key) VALUES (?,?,?,?,?,?,?,?)", [
                      (1, "B1", "Coleoptera", "Carabus nemoralis", "insect - beetle (Coleoptera)",
                       "Animalia", "Species", 19018000),                  # ours: untouched
                      (2, "B1", "Coleoptera", "Carabus nemoralis", "insect - beetle (Coleoptera)",
                       "Animalia", "Species", "000204010603030602"),      # odd, TVK in UKSI
                      (3, "O2", "Odonata", "Isoaeschna isoceles", "insect - dragonfly (Odonata)",
                       "Animalia", "Species", OLD),                       # odd, superseded TVK
                      (4, "ZZ", None, "Nobody", None, None, None, OLD),   # odd, unresolvable
                      (5, "B1", "Coleoptera", "Carabus nemoralis", None, None, None, None),  # blank
                  ])
    o.commit()
    o.close()
    return str(tmp_path / "observatum.db"), str(tmp_path / "uksi.db"), tmp_path


def _script():
    path = os.path.join(ROOT, "scripts", "backfill_taxon_groups.py")
    spec = importlib.util.spec_from_file_location("backfill_taxon_groups", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _keys(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return dict(c.execute("SELECT id, taxonomic_sort_key FROM observations"))
    finally:
        c.close()


def test_fix_odd_keys_plan_dry_run_and_apply(dbs, capsys):
    db, uksi, tmp = dbs
    m = _script()
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    odd = m.plan(ro, uksi)["observations"]["odd_keys"]
    ro.close()
    assert odd == [(2, "Carabus nemoralis", "000204010603030602", 19018000, None),
                   (3, "Isoaeschna isoceles", OLD, 4048170, "O1"),
                   (4, "Nobody", OLD, None, None)]
    before = _keys(db)
    assert m.main(["--db", db, "--uksi", uksi, "--fix-odd-keys"]) == 0
    out = capsys.readouterr().out
    assert "Nothing has been changed" in out and "in all: 2 odd sort keys to rewrite" in out
    assert "id 3       Isoaeschna isoceles" in out and "-> 4048170" in out
    assert "superseded TVK; key of the current taxon O1" in out
    assert "(TVK not in UKSI: left)" in out
    assert "taxon_group          fill       0" in out                  # no blank filled
    assert _keys(db) == before
    assert m.main(["--db", db, "--uksi", uksi, "--fix-odd-keys", "--apply",
                   "--backup-dir", str(tmp / "bk")]) == 0
    out = capsys.readouterr().out
    assert "observations: odd_keys 2" in out and os.listdir(tmp / "bk")
    after = _keys(db)
    assert after == {1: 19018000, 2: 19018000, 3: 4048170, 4: OLD, 5: None}
    assert isinstance(after[3], int)
    # the ordinary dry run still fills the blank and leaves odd keys alone
    assert m.main(["--db", db, "--uksi", uksi]) == 0
    out = capsys.readouterr().out
    assert "taxonomic_sort_key   fill       1" in out and "with --fix-odd-keys" in out


def test_drawer_in_hand_fits_laptop_width_with_wide_text():
    """R10 fix: the Show choice sits under the tree, so wide text still fits 1280 px (Wil's PC)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import paths
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    if not paths.OBSERVATUM_DB.exists():
        import pytest
        pytest.skip("data copy absent")
    app = QApplication.instance() or QApplication([])
    before = QFont(app.font())
    f = QFont(before)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 200)
    app.setFont(f)
    try:
        from src.views.collection.drawer_assign_dialog import DrawerAssignDialog
        d = DrawerAssignDialog(None, db_path=paths.OBSERVATUM_DB)
        assert d.minimumSizeHint().width() <= 1240
        d.deleteLater()
    finally:
        app.setFont(before)
