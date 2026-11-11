"""Data Entry: the To check mark, Export for checking, and the Last entered row button
(purpose-made databases; nothing from the live data)."""
import sqlite3
from datetime import date
from urllib.parse import unquote

import pytest

import paths
from shared import photo_files as pf
from shared import photo_links as pl


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def named_app(qapp):
    old = (qapp.organizationName(), qapp.applicationName())
    qapp.setOrganizationName("FlaunaTest")
    qapp.setApplicationName("CheckTest")
    yield qapp
    qapp.setOrganizationName(old[0])
    qapp.setApplicationName(old[1])


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path / "Media")
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    (tmp_path / "Media" / "Photos" / "_Bench").mkdir(parents=True)
    pf.refresh()
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "observatum.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pl.ensure_schema(conn)
    yield tmp_path, conn, repo
    pf.refresh()


def _job(conn, repo, name="Pitfalls"):
    return repo.create_job(conn, name, "Personal", None, None)


def _row(conn, repo, jid, **kw):
    data = {"species_name": "Amara aenea", "species_tvk": "NBNSYS0000010000", "date": "2026-06-05",
            "quantity": "2", "recorder": "Heeney, W.J.", **kw}
    return repo.insert_row(conn, jid, data)


class Obs:
    def __init__(self, **kw):
        pass


class Model:
    def __init__(self):
        self.n = 0

    def create(self, o, extra=None):
        self.n += 1
        return 100 + self.n


class Db:
    def execute_main_write(self, sql, params):
        return 1


# ---------------------------------------------------------------- the column script

def _old_db(path):
    """A database made before the Check columns existed."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE entry_staging (id INTEGER PRIMARY KEY, job_id INTEGER, species_name TEXT)")
    conn.execute("INSERT INTO entry_staging (job_id, species_name) VALUES (1, 'x')")
    conn.commit()
    conn.close()


def _cols(path):
    c = sqlite3.connect(path)
    try:
        return {r[1] for r in c.execute("PRAGMA table_info(entry_staging)")}
    finally:
        c.close()


def test_script_dry_run_changes_nothing(tmp_path, capsys):
    from scripts import add_staging_check_columns as sc
    db = tmp_path / "observatum.db"
    _old_db(db)
    assert sc.main(["--db", str(db), "--backup-dir", str(tmp_path / "bk")]) == 0
    out = capsys.readouterr().out
    assert "would add: check_flag" in out and out.strip().endswith("Nothing has been changed.")
    assert "check_flag" not in _cols(db) and not (tmp_path / "bk").exists()


def test_script_apply_adds_columns_with_backup_and_is_idempotent(tmp_path, capsys):
    from scripts import add_staging_check_columns as sc
    db = tmp_path / "observatum.db"
    _old_db(db)
    args = ["--db", str(db), "--backup-dir", str(tmp_path / "bk")]
    assert sc.main(args + ["--apply"]) == 0
    assert {"check_flag", "check_note"} <= _cols(db)
    backups = list((tmp_path / "bk").iterdir())
    assert len(backups) == 1 and "check_flag" not in _cols(backups[0])
    capsys.readouterr()
    assert sc.main(args + ["--apply"]) == 0              # nothing left to add
    assert "Nothing has been changed" in capsys.readouterr().out
    assert len(list((tmp_path / "bk").iterdir())) == 1


def test_script_refuses_other_database(tmp_path):
    from scripts import add_staging_check_columns as sc
    db = tmp_path / "other.db"
    _old_db(db)
    assert sc.main(["--db", str(db), "--backup-dir", str(tmp_path / "bk"), "--apply"]) == 1
    assert "check_flag" not in _cols(db) and not (tmp_path / "bk").exists()


def test_new_databases_have_the_columns(lib):
    _tmp, conn, repo = lib
    assert repo.has_check_columns(conn)
    assert {"check_flag", "check_note"} <= set(repo.STAGING_EDITABLE)


# ---------------------------------------------------------------- commit and iRecord

def test_commit_holds_back_flagged_rows(lib):
    _tmp, conn, repo = lib
    from DataEntry import commit_service as cs
    jid = _job(conn, repo)
    _row(conn, repo, jid)
    held = _row(conn, repo, jid, species_name="Badister sodalis", check_flag=1, check_note="not sure")
    _row(conn, repo, jid, species_name="Carabus nemoralis")
    job = repo.get_job(conn, jid)
    s = cs.commit_job(Db(), Model(), conn, job, observation_cls=Obs, taxonomy={})
    assert s["committed"] == 2 and s["skipped_check"] == 1 and s["remaining"] == 1
    assert [r["id"] for r in repo.fetch_rows(conn, jid)] == [held]
    assert repo.get_job(conn, jid)["status"] == "active"           # the job stays open


def test_precommit_lists_flagged_rows_apart_from_problems(lib):
    _tmp, conn, repo = lib
    from DataEntry import commit_service as cs
    jid = _job(conn, repo)
    _row(conn, repo, jid, date="31/02/2026", check_flag=1)         # would be a problem, but held
    _row(conn, repo, jid)
    found = cs.precommit_issues(repo.fetch_rows(conn, jid))
    assert found["to check (held back)"] == [1]
    assert "unreadable date" not in found


def test_irecord_export_refuses_while_rows_are_marked(lib):
    """Review 16 Oct: an exported job would strand its To check rows, so the export refuses."""
    import pytest
    tmp, conn, repo = lib
    from DataEntry import irecord_export as ie
    jid = _job(conn, repo)
    _row(conn, repo, jid)
    _row(conn, repo, jid, species_name="Badister sodalis", check_flag=1)
    out = tmp / "ir.csv"
    with pytest.raises(ValueError, match="marked to check"):
        ie.export_job(conn, repo.get_job(conn, jid), str(out), uksi_path=tmp / "none.db")
    assert not out.exists() and repo.get_job(conn, jid)["status"] == "active"


# ---------------------------------------------------------------- export for checking

def _with_photos(tmp, conn, repo, jid):
    media = tmp / "Media" / "Photos" / "_Bench"
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        (media / n).write_bytes(n.encode())
    r1 = _row(conn, repo, jid, check_flag=1, check_note="legs?", site_name="Home", sex="Male", stage="Adult")
    r2 = _row(conn, repo, jid, species_name="Badister sodalis", check_flag=1)
    r3 = _row(conn, repo, jid, species_name="Carabus nemoralis")
    pl.add_staging_link(conn, "Photos/_Bench/a.jpg", r1)
    pl.add_staging_link(conn, "Photos/_Bench/b.jpg", r2)
    pl.add_staging_link(conn, "Photos/_Bench/c.jpg", r2)
    pl.add_staging_link(conn, "Photos/_Bench/gone.jpg", r2)       # no such file
    conn.commit()
    return r1, r2, r3


def test_export_for_checking_writes_folder_sheet_and_photos(lib):
    tmp, conn, repo = lib
    from openpyxl import load_workbook
    from DataEntry import check_export as ce
    jid = _job(conn, repo)
    r1, r2, _r3 = _with_photos(tmp, conn, repo, jid)
    cols = ["Species", "Date", "Sex", "Check note"]
    res = ce.export_for_checking(conn, repo.get_job(conn, jid), [r1, r2], cols, tmp / "out")
    assert (res["rows"], res["photos_copied"], res["photos_missing"]) == (2, 3, 1)
    folder = tmp / "out" / f"Pitfalls for checking {date.today().strftime('%d-%m-%Y')}"
    assert res["folder"] == str(folder)
    assert sorted(p.name for p in (folder / "photos").iterdir()) == [
        "R001 a.jpg", "R002 b.jpg", "R002 c.jpg"]
    ws = load_workbook(folder / f"{folder.name}.xlsx").active
    head = [c.value for c in ws[1]]
    assert head == ["Ref", "Row id", "Species", "Date", "Sex", "Check note", "Photos", "Photo 2",
                    "Agree?", "Their ID", "Notes"]
    assert ws[1][0].font.bold and ws.freeze_panes == "A2"
    row2, row3 = [c.value for c in ws[2]], [c.value for c in ws[3]]
    assert row2[:7] == ["R001", r1, "Amara aenea", "05/06/2026", "Male", "legs?", "R001 a.jpg"]
    assert ws.cell(2, 7).hyperlink.target == "photos/R001%20a.jpg"
    assert unquote(ws.cell(2, 7).hyperlink.target) == "photos/R001 a.jpg"
    assert row3[0] == "R002" and row3[6] == "R002 b.jpg\nR002 c.jpg"
    assert unquote(ws.cell(3, 7).hyperlink.target) == "photos/R002 b.jpg"
    assert ws.cell(3, 8).value == "R002 c.jpg" and unquote(ws.cell(3, 8).hyperlink.target) == "photos/R002 c.jpg"
    assert row2[-3:] == [None, None, None] and row3[-3:] == [None, None, None]
    # the library is untouched and the database not written
    assert (tmp / "Media" / "Photos" / "_Bench" / "a.jpg").read_bytes() == b"a.jpg"


def test_export_never_writes_into_an_existing_folder(lib):
    tmp, conn, repo = lib
    from DataEntry import check_export as ce
    jid = _job(conn, repo)
    r1, r2, _r3 = _with_photos(tmp, conn, repo, jid)
    job = repo.get_job(conn, jid)
    a = ce.export_for_checking(conn, job, [r1], ["Species"], tmp / "out")
    b = ce.export_for_checking(conn, job, [r1], ["Species"], tmp / "out")
    c = ce.export_for_checking(conn, job, [r1], ["Species"], tmp / "out")
    assert a["folder"].endswith(date.today().strftime("%d-%m-%Y"))
    assert b["folder"].endswith("(2)") and c["folder"].endswith("(3)")
    assert len(list((tmp / "out").iterdir())) == 3


def test_export_refuses_a_folder_inside_the_photo_library(lib):
    tmp, conn, repo = lib
    from DataEntry import check_export as ce
    jid = _job(conn, repo)
    r1, _r2, _r3 = _with_photos(tmp, conn, repo, jid)
    job = repo.get_job(conn, jid)
    for inside in (tmp / "Media", tmp / "Media" / "Photos" / "exports"):
        with pytest.raises(ValueError, match="outside the photo library"):
            ce.export_for_checking(conn, job, [r1], ["Species"], inside)
    assert not (tmp / "Media" / "Photos" / "exports").exists()


def test_export_with_no_photo_has_no_extra_photo_columns(lib):
    from openpyxl import load_workbook
    tmp, conn, repo = lib
    from DataEntry import check_export as ce
    jid = _job(conn, repo)
    r = _row(conn, repo, jid)
    res = ce.export_for_checking(conn, repo.get_job(conn, jid), [r], ["Species"], tmp / "out")
    ws = load_workbook(res["xlsx"]).active
    assert [c.value for c in ws[1]] == ["Ref", "Row id", "Species", "Photos", "Agree?", "Their ID",
                                        "Notes"]
    assert res["photos_copied"] == 0 and not list((tmp / "out").glob("*/photos"))


def test_export_dialog_remembers_columns_and_defaults(named_app):
    from PySide6.QtCore import QSettings
    from DataEntry import check_export_dialog as cd
    QSettings().remove(cd.COLUMNS_KEY)
    d = cd.CheckExportDialog(None, {"id": 1, "name": "j"}, [5], [], None)
    assert d.chosen_columns() == ["Species", "Common name", "Date", "Sex", "Stage", "No.", "Check note"]
    assert d.rb_selected.isChecked() and not d.boxes["Site"].isChecked()
    d.boxes["Site"].setChecked(True)
    QSettings().setValue(cd.COLUMNS_KEY, d.chosen_columns())
    assert "Site" in cd.remembered_columns()
    QSettings().remove(cd.COLUMNS_KEY)
    assert cd.CheckExportDialog(None, {"id": 1, "name": "j"}, [5], [7], None).rb_flagged.isChecked()


# ---------------------------------------------------------------- the grid model

def test_check_toggle_and_last_row_in_the_model(lib, named_app):
    from PySide6.QtCore import Qt, QSettings
    from DataEntry import entry_grid as eg
    tmp, conn, repo = lib
    jid = _job(conn, repo)
    a, b = _row(conn, repo, jid), _row(conn, repo, jid, species_name="Badister sodalis")
    QSettings().remove(eg.LAST_ROW_KEY.format(jid))
    m = eg.StagingTableModel(conn, jid)
    flag = m.index(0, eg.COLIDX["check_flag"])
    assert m.data(flag) is None
    m.toggle_check(0)
    assert m.data(flag) == "to check" and m.flagged_count() == 1
    assert conn.execute("SELECT check_flag FROM entry_staging WHERE id=?", (a,)).fetchone()[0] == 1
    m.setData(m.index(0, eg.COLIDX["check_note"]), "legs?", Qt.ItemDataRole.EditRole)
    assert m.data(flag, Qt.ItemDataRole.ToolTipRole) == "legs?"
    m.toggle_check(0)
    assert m.data(flag) is None and m.flagged_count() == 0
    # the last row: written to row 2, found again by a new model (the job reopened)
    m.setData(m.index(1, eg.COLIDX["comment"]), "hello", Qt.ItemDataRole.EditRole)
    assert QSettings().value(eg.LAST_ROW_KEY.format(jid), type=int) == b
    assert eg.StagingTableModel(conn, jid).last_row_index() == 1
    # the row is gone: the last row with data
    repo.delete_row(conn, b)
    assert eg.StagingTableModel(conn, jid).last_row_index() == 0
    QSettings().remove(eg.LAST_ROW_KEY.format(jid))


def test_without_the_columns_nothing_is_marked(tmp_path, named_app):
    from PySide6.QtCore import Qt
    from DataEntry import entry_grid as eg
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE entry_jobs (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE entry_staging (id INTEGER PRIMARY KEY, job_id INTEGER, row_order INTEGER, "
                 "species_name TEXT, comment TEXT)")
    conn.execute("INSERT INTO entry_staging (job_id, species_name) VALUES (1, 'Amara aenea')")
    conn.commit()
    m = eg.StagingTableModel(conn, 1)
    assert not m.has_check_columns()
    m.toggle_check(0)
    m.setData(m.index(0, eg.COLIDX["check_note"]), "x", Qt.ItemDataRole.EditRole)
    assert m.data(m.index(0, eg.COLIDX["check_flag"])) is None and m.flagged_count() == 0
    assert m.data(m.index(0, eg.COLIDX["check_flag"]), Qt.ItemDataRole.ToolTipRole) == eg.CHECK_HINT


def test_filter_hides_rows_from_selection_and_paste(lib, named_app):
    """Review fix: with "To check only" on, select-all, delete, fill-down and paste reach
    only the rows shown."""
    from PySide6.QtCore import Qt
    from DataEntry import entry_grid as eg
    tmp, conn, repo = lib
    jid = _job(conn, repo)
    for name in ("Aa", "Bb", "Cc"):
        _row(conn, repo, jid, species_name=name)
    m = eg.StagingTableModel(conn, jid)
    v = eg.EntryTableView()
    v.setModel(m)
    m.toggle_check(1)
    for r in range(m.rowCount()):                     # as EntryGridPage._apply_check_filter
        v.setRowHidden(r, not m.is_flagged(r))
    assert [r for r in range(3) if v.isRowHidden(r)] == [0, 2]
    v.selectAll()
    assert v._selected_rows() == [1]
    # a two-line paste starting on the shown row skips the hidden row below it
    v._clipboard_grid = lambda: [["one"], ["two"]]
    v.setCurrentIndex(m.index(1, eg.COLIDX["comment"]))
    v.clearSelection()
    v._paste()
    comments = [r[0] for r in conn.execute("SELECT comment FROM entry_staging ORDER BY id")]
    assert comments[:3] == [None, "one", None]
    # typed or pasted values: only a clear yes marks a row
    flag = eg.COLIDX["check_flag"]
    for val, on in (("maybe", False), ("x", True), ("0", False), ("To check", True)):
        m.setData(m.index(0, flag), val, Qt.ItemDataRole.EditRole)
        assert bool(m.is_flagged(0)) is on, val


def test_ctrl_t_and_typing_mark_rows(lib, named_app):
    """17 Oct: Ctrl+T marks the selected rows from any column (again: off when all are
    marked); typing "to check" (or x, y, t) in the Check cell marks, anything else clears."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    from DataEntry import entry_grid as eg
    tmp, conn, repo = lib
    jid = _job(conn, repo)
    for name in ("Aa", "Bb", "Cc"):
        _row(conn, repo, jid, species_name=name)
    m = eg.StagingTableModel(conn, jid)
    v = eg.EntryTableView()
    v.setModel(m)
    v.setItemDelegateForColumn(eg.COLIDX["check_flag"], eg._CheckDelegate(v))

    def ctrl_t():
        v.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_T,
                                  Qt.KeyboardModifier.ControlModifier))

    v.setCurrentIndex(m.index(0, eg.COLIDX["comment"]))
    v.selectRow(0)
    m.toggle_check(1)
    from PySide6.QtCore import QItemSelectionModel
    v.selectionModel().select(m.index(1, 0), QItemSelectionModel.SelectionFlag.Select
                              | QItemSelectionModel.SelectionFlag.Rows)
    ctrl_t()                                  # one of two marked: both marked
    assert [m.is_flagged(r) for r in range(3)] == [True, True, False]
    ctrl_t()                                  # both marked: both cleared
    assert [m.is_flagged(r) for r in range(3)] == [False, False, False]
    # typing in the Check cell: the delegate's editor writes what was typed
    d = v.itemDelegateForColumn(eg.COLIDX["check_flag"])
    ix = m.index(2, eg.COLIDX["check_flag"])
    ed = d.createEditor(v.viewport(), None, ix)
    d.setEditorData(ed, ix)
    assert ed.text() == ""
    for typed, on in (("to check", True), ("", False), ("T", True), ("no", False)):
        ed.setText(typed)
        d.setModelData(ed, m, ix)
        assert m.is_flagged(2) is on, typed
    assert m.data(ix, Qt.ItemDataRole.ToolTipRole).startswith("Not marked")
