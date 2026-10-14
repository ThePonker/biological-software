"""Photos round 4 (14 Oct 2026): OTHER RECORD photos in orange, column widths kept by column,
dialogs remember their size, camera columns follow link changes, _Bench clean-up buttons."""
import os
import sqlite3

import pytest

import paths
from shared import photo_files as pf
from shared import photo_housekeeping as ph
from shared import photo_links as pl

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SP = "Photos/Life/Insecta/Coleoptera/Staphylinidae/Philonthus spinipes/Specimen"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def named_app(qapp):
    """QSettings() needs an organisation name on Windows (the apps set one; a bare test
    QApplication has none, so nothing would be stored)."""
    old = (qapp.organizationName(), qapp.applicationName())
    qapp.setOrganizationName("FlaunaTest")
    qapp.setApplicationName("Round4Test")
    yield qapp
    qapp.setOrganizationName(old[0])
    qapp.setApplicationName(old[1])


@pytest.fixture
def lib(tmp_path, monkeypatch, qapp):
    (tmp_path / SP).mkdir(parents=True)
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    monkeypatch.setattr(paths, "ROOT", tmp_path / "proj")
    pf.refresh()
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, observation_id INTEGER, species_name TEXT)")
    c.execute("INSERT INTO specimens VALUES (5, 1, 'Philonthus spinipes')")
    pl.ensure_schema(c)
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        (tmp_path / SP / n).write_bytes(b"x")
    pl.add_link(c, f"{SP}/a.jpg", observation_id=1)
    pl.add_link(c, f"{SP}/b.jpg", observation_id=2)            # another record's
    pl.add_link(c, f"{SP}/c.jpg", specimen_id=5)                # record 1's own specimen
    c.commit()
    c.close()
    yield tmp_path, db
    pf.refresh()


def test_other_records_photos_are_marked(lib):
    root, db = lib
    from src.views.dialogs.photos_window import PhotosWindow
    w = PhotosWindow("Philonthus spinipes", [f"{SP}/a.jpg", f"{SP}/c.jpg"], record_kind="observation",
                     record_id=1, db_path=str(db))
    assert w._others == {f"{SP}/b.jpg": "record 2"}
    tips = [w.list.item(i).toolTip() for i in range(w.list.count())]
    assert any("Linked to another record: record 2" in t for t in tips)
    w2 = PhotosWindow("Philonthus spinipes", [f"{SP}/c.jpg"], record_kind="specimen", record_id=5,
                      db_path=str(db))
    assert set(w2._others) == {f"{SP}/a.jpg", f"{SP}/b.jpg"}


def test_link_change_tells_every_table(lib):
    root, db = lib
    from src.views.dialogs.photos_window import PhotosWindow, follow_links
    calls = []
    follow_links(lambda: calls.append(1))
    w = PhotosWindow("Philonthus spinipes", [f"{SP}/a.jpg"], record_kind="observation", record_id=1,
                     db_path=str(db))
    w.list.setCurrentRow(w.paths.index(f"{SP}/b.jpg"))
    w._link()
    assert calls


def test_column_widths_kept_by_column(named_app):
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QStandardItemModel
    from PySide6.QtWidgets import QTableView
    from src.views.components.column_widths import ColumnWidthKeeper
    cols = [("checkbox", "", 30, True), ("species_name", "Species", 160, True), ("photos", "x", 44, False)]
    m = QStandardItemModel(2, 3)
    v = QTableView()
    v.setModel(m)
    prefix = "test_round4_columns"
    QSettings().remove(prefix)
    k = ColumnWidthKeeper(v, lambda: cols, prefix)
    k.apply()
    assert v.columnWidth(2) == 44
    v.setColumnWidth(2, 61)                       # Wil drags it
    assert QSettings().value(f"{prefix}/photos") in (61, "61")
    k._applying = True                            # a refill puts a default width back ...
    v.setColumnWidth(2, 100)
    k._applying = False
    m.beginResetModel()
    m.endResetModel()
    k.apply()                                     # ... after a refill it is put back
    assert v.columnWidth(2) == 61
    QSettings().remove(prefix)


def test_dialogs_remember_their_size(qapp):
    from PySide6.QtWidgets import QDialog, QMessageBox
    from shared import dialog_geometry as dg

    class SizedTestDialog(QDialog):
        pass
    d = SizedTestDialog()
    d.resize(640, 410)
    dg.save(d)
    d2 = SizedTestDialog()
    d2.resize(200, 200)
    assert dg.restore(d2) and (d2.width(), d2.height()) == (640, 410)
    f = dg.DialogSizes()
    mb = QMessageBox()
    from PySide6.QtCore import QEvent
    assert f.eventFilter(mb, QEvent(QEvent.Type.Show)) is False and not mb.property(dg._FLAG)
    dg._settings().remove(dg.key_for(d))


def test_bench_photos_back_and_to_archive(lib, monkeypatch):
    root, db = lib
    from shared import bench_photos as bp
    bench = bp.bench_root()
    bench.mkdir(parents=True)
    for n in ("x.jpg", "y.jpg", "z.jpg"):
        (bench / n).write_bytes(b"x")
    c = sqlite3.connect(db)
    pl.add_link(c, "Photos/_Bench/z.jpg", observation_id=9)            # still a record's
    c.commit()
    cap = root / "cap"
    moved, notes = ph.move_bench_photos(c, ["Photos/_Bench/x.jpg", "Photos/_Bench/z.jpg"], cap)
    assert moved == ["Photos/_Bench/x.jpg"] and "still linked" in notes[0]
    assert (cap / "x.jpg").is_file() and (bench / "z.jpg").is_file()
    moved, _ = ph.move_bench_photos(c, ["Photos/_Bench/y.jpg"], ph.bench_archive_folder())
    assert moved and (ph.bench_archive_folder() / "y.jpg").is_file()
    c.close()


def test_bench_tab_buttons(lib, monkeypatch):
    root, db = lib
    from PySide6.QtWidgets import QMessageBox
    from shared import bench_photos as bp
    bp.bench_root().mkdir(parents=True)
    (bp.bench_root() / "x.jpg").write_bytes(b"x")
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    from src.views.stats.photo_housekeeping_dialog import PhotoHousekeepingDialog
    dlg = PhotoHousekeepingDialog(str(db))
    t = dlg.tables["bench"]
    assert t.rowCount() == 1 and not dlg.btn_bench_archive.isEnabled()
    t.selectRow(0)
    assert dlg.btn_bench_archive.isEnabled()
    dlg.bench_archive()
    assert t.rowCount() == 0 and (ph.bench_archive_folder() / "x.jpg").is_file()


def test_stretched_last_column_not_saved_and_plain_dialogs_skipped(named_app):
    qapp = named_app
    from PySide6.QtCore import QEvent, QSettings
    from PySide6.QtGui import QStandardItemModel
    from PySide6.QtWidgets import QDialog, QTableView
    from shared import dialog_geometry as dg
    from src.views.components.column_widths import ColumnWidthKeeper
    cols = [("a", "A", 50, True), ("b", "B", 60, True)]
    m = QStandardItemModel(1, 2)
    v = QTableView()
    v.setModel(m)
    v.horizontalHeader().setStretchLastSection(True)
    prefix = "test_round4_stretch"
    QSettings().remove(prefix)
    ColumnWidthKeeper(v, lambda: cols, prefix)
    v.resize(900, 300)
    v.show()
    qapp.processEvents()
    assert QSettings().value(f"{prefix}/b") is None
    QSettings().remove(prefix)
    d = QDialog()
    assert dg.DialogSizes().eventFilter(d, QEvent(QEvent.Type.Show)) is False and not d.property(dg._FLAG)
    v.close()


def test_bench_move_refused_without_links(lib):
    root, db = lib
    moved, notes = ph.move_bench_photos(None, ["Photos/_Bench/x.jpg"], root / "cap")
    assert moved == [] and "nothing was moved" in notes[0]
