"""Photos round 2 (14 Oct 2026): bench photo names follow a sex or date change; the camera
column's counts; deleting a record lets go of its photos (never the files); the viewer."""
import os
import sqlite3

import pytest

import paths
from shared import bench_photos as bp
from shared import photo_files as pf
from shared import photo_links as pl

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
SP = "Photos/Life/Insecta/Coleoptera/Carabidae/Amara aenea/Specimen"


def test_name_rebuilt_keeps_view_and_number():
    old = ("Amara aenea", "Male", "2026-06-05")
    assert bp._rebuilt("Amara aenea male gen 5.vi.26", old, ("Amara aenea", "Female", "2026-06-05")) \
        == "Amara aenea female gen 5.vi.26"
    assert bp._rebuilt("Amara aenea male gen 5.vi.26 2", old, ("Amara aenea", "Male", "2026-06-07")) \
        == "Amara aenea male gen 7.vi.26 2"
    assert bp._rebuilt("Amara aenea male 5.vi.26", old, ("Amara similata", "", "")) == "Amara similata"
    assert bp._rebuilt("my own name", old, ("Amara aenea", "Female", "")) is None
    # review 14 Oct: a stale date, a hand-made name, a genus-only row -- left, never guessed
    assert bp._rebuilt("Amara aenea gen 5.vi.26", ("Amara aenea", "", "2026-06-06"),
                       ("Amara aenea", "male", "2026-06-06")) is None
    assert bp._rebuilt("Amara aenea female", ("Amara aenea", "", ""), ("Amara aenea", "male", "")) is None
    assert bp._rebuilt("Amara aenea gen 5.vi.26", ("Amara", "", ""), ("Bembidion", "", "")) is None


@pytest.fixture
def lib(tmp_path, monkeypatch):
    (tmp_path / SP).mkdir(parents=True)
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    pf.refresh()
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "o.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pl.ensure_schema(conn)
    cap = tmp_path / "cap"
    cap.mkdir()
    yield tmp_path, conn, cap, repo
    pf.refresh()


def test_grid_sex_change_renames_the_bench_photo(lib):
    root, conn, cap, repo = lib
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from DataEntry.entry_grid import COLUMNS, StagingTableModel
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    rid = repo.insert_row(conn, jid, {"species_name": "Amara aenea", "sex": "Male", "date": "05/06/2026"})
    (cap / "a.jpg").write_bytes(b"x")
    bp.attach(conn, cap / "a.jpg", rid, "Amara aenea male gen 5.vi.26")
    m = StagingTableModel(conn, jid)
    col = [c[0] for c in COLUMNS].index("sex")
    assert m.setData(m.index(0, col), "Female")
    assert pl.photos_for_staging(conn, rid) == ["Photos/_Bench/Amara aenea female gen 5.vi.26.jpg"]


def _obs_db(root):
    c = sqlite3.connect(root / "o.db")
    c.execute("CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY, species_name TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS specimens (id INTEGER PRIMARY KEY, observation_id INTEGER)")
    c.executemany("INSERT INTO observations VALUES (?, 'Amara aenea')", [(1,), (2,)])
    c.execute("INSERT INTO specimens VALUES (9, 2)")
    pl.ensure_schema(c)
    for name, kw in (("a.jpg", {"observation_id": 1}), ("b.jpg", {"observation_id": 1}),
                     ("c.jpg", {"specimen_id": 9}), ("a.jpg", {"observation_id": 2})):
        (root / SP / name).write_bytes(b"x")
        pl.add_link(c, f"{SP}/{name}", **kw)
    c.commit()
    return c


def test_camera_column_counts(lib):
    root, conn, cap, repo = lib
    c = _obs_db(root)
    assert pl.observation_photo_counts(c) == {1: 2, 2: 2}
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.observations.observation_table_model import ObservationTableModel
    m = ObservationTableModel()
    m.set_observations([{"id": 1, "species_name": "Amara aenea"}, {"id": 3, "species_name": "x"}])
    m.set_photo_counts(pl.observation_photo_counts(c))
    keys = [k for k, *_ in m.get_columns()]
    if "photos" in keys:
        col = keys.index("photos")
        assert m.data(m.index(0, col)) == "\U0001F4F7 2" and m.data(m.index(1, col)) == ""


def test_deleting_a_record_lets_go_of_its_photos(lib):
    root, conn, cap, repo = lib
    c = _obs_db(root)
    by = bp.record_photos(c, [1])
    assert by == {1: [f"{SP}/a.jpg", f"{SP}/b.jpg"]}
    assert bp.release_records(c, by, True) == (0, [])          # record 1 not deleted yet
    c.execute("DELETE FROM observations WHERE id = 1")
    c.commit()
    assert bp.release_records(c, by, True) == (1, [])
    # b.jpg was record 1's only: now in _Bench; a.jpg is still record 2's: left where it is
    assert (root / "Photos/_Bench/b.jpg").is_file() and (root / SP / "a.jpg").is_file()
    assert pl.photos_for_observation(c, 2) == [f"{SP}/a.jpg", f"{SP}/c.jpg"]
    assert c.execute("SELECT COUNT(*) FROM photo_links WHERE observation_id = 1").fetchone()[0] == 0


def test_delete_leave_in_species_folder(lib):
    root, conn, cap, repo = lib
    c = _obs_db(root)
    by = bp.record_photos(c, [1])
    c.execute("DELETE FROM observations WHERE id = 1")
    c.commit()
    assert bp.release_records(c, by, False) == (0, [])
    assert (root / SP / "b.jpg").is_file()
    assert c.execute("SELECT COUNT(*) FROM photo_links WHERE observation_id = 1").fetchone()[0] == 0


def test_viewer_steps_and_sizes(tmp_path):
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.dialogs.photo_viewer import PhotoViewer
    files = []
    for n in ("a.png", "b.png"):
        assert QImage(40, 30, QImage.Format.Format_RGB32).save(str(tmp_path / n))
        files.append(tmp_path / n)
    v = PhotoViewer(files, 1)
    assert "b.png" in v.title.text() and "2 of 2" in v.title.text() and not v.next_btn.isEnabled()
    v.step(-1)
    assert "a.png" in v.title.text() and not v.prev_btn.isEnabled()
    v.toggle_size()
    assert v.image.pixmap().width() == 40 and v.size_btn.text() == "Fit to window"


def test_camera_cell_double_click_opens_photos(monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.observations.observation_tab import ObservationTab
    tab = ObservationTab()
    tab.table_model.photo_count_provider = lambda: {12: 3}
    tab.table_model._visible_columns.add('photos')
    tab.table_model._update_columns()
    tab.table_model.set_observations([{"id": 11, "species_name": "A b"}, {"id": 12, "species_name": "C d"}])
    tab._connect_proxy_after_load()
    opened, detail = [], []
    monkeypatch.setattr(tab, "_open_record_photos", lambda r: opened.append(r["id"]))
    monkeypatch.setattr(tab, "_show_record_detail", lambda r: detail.append(r["id"]))
    col = [c[0] for c in tab.table_model.get_columns()].index('photos')
    src = tab.table_model.index(1, col)
    assert tab.table_model.data(src) == "\U0001F4F7 3"
    tab._on_row_double_clicked(tab.sort_proxy.mapFromSource(src))
    tab._on_row_double_clicked(tab.sort_proxy.mapFromSource(tab.table_model.index(0, col)))
    assert opened == [12] and detail == [11]


def test_take_a_photo_off_a_row(lib):
    root, conn, cap, repo = lib
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    rid = repo.insert_row(conn, jid, {"species_name": "Amara aenea"})
    (cap / "a.jpg").write_bytes(b"x")
    bp.attach(conn, cap / "a.jpg", rid, "Amara aenea head")
    dst = bp.detach(conn, rid, "Photos/_Bench/Amara aenea head.jpg", cap)
    assert dst == cap / "Amara aenea head.jpg" and dst.is_file()
    assert pl.photos_for_staging(conn, rid) == []
    with pytest.raises(ValueError):
        bp.detach(conn, rid, "Photos/_Bench/Amara aenea head.jpg", cap)


def test_attach_dialog_takes_a_photo_off(lib):
    root, conn, cap, repo = lib
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from DataEntry import photo_attach
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    rid = repo.insert_row(conn, jid, {"species_name": "Amara aenea"})
    assert QImage(8, 8, QImage.Format.Format_RGB32).save(str(cap / "a.jpg"))
    s = QSettings("Flauna", "Observatum")
    old = s.value(photo_attach.KEY_FOLDER)
    s.setValue(photo_attach.KEY_FOLDER, str(cap))
    try:
        dlg = photo_attach.PhotoAttachDialog(conn, {"id": rid, "species_name": "Amara aenea"})
        dlg.list.selectAll()
        dlg._attach()
        assert dlg.row_list.count() == 1 and dlg.list.count() == 0
        dlg.row_list.selectAll()
        dlg._detach()
        assert dlg.row_list.count() == 0 and dlg.list.count() == 1
    finally:
        if old is None:
            s.remove(photo_attach.KEY_FOLDER)
        else:
            s.setValue(photo_attach.KEY_FOLDER, old)


def test_camera_column_sorts_by_count():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.observations.observation_tab import ObservationTab
    tab = ObservationTab()
    tab.table_model.photo_count_provider = lambda: {12: 3, 13: 12}
    tab.table_model._visible_columns.add('photos')
    tab.table_model._update_columns()
    tab.table_model.set_observations([{"id": i, "species_name": "A b"} for i in (11, 12, 13)])
    tab._connect_proxy_after_load()
    col = [c[0] for c in tab.table_model.get_columns()].index('photos')
    tab.sort_proxy.sort(col, Qt.SortOrder.DescendingOrder)
    assert [r["id"] for r in tab.table_model._observations] == [13, 12, 11]      # 12 before 3


def test_insect_collection_camera_column(monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.collection.insect_collection_tab import InsectCollectionTab
    tab = InsectCollectionTab()
    m = tab.table_model
    m.photo_count_provider = lambda: {2: 12, 3: 3}
    m._visible_columns.add('photos')
    m.set_specimens([{"id": i, "species_name": "Philonthus spinipes"} for i in (1, 2, 3)])
    tab._connect_proxy_after_load()
    col = [c[0] for c in m.get_columns()].index('photos')
    assert m.item(1, col).text() == "\U0001F4F7 12" and m.item(0, col).text() == ""
    tab.sort_proxy.sort(col, Qt.SortOrder.DescendingOrder)
    ids = [m.get_specimen_at_row(tab.sort_proxy.mapToSource(tab.sort_proxy.index(r, 0)).row())["id"]
           for r in range(3)]
    assert ids == [2, 3, 1]
    opened, detail = [], []
    monkeypatch.setattr(tab, "_open_specimen_photos", lambda s: opened.append(s["id"]))
    monkeypatch.setattr(tab, "_show_specimen_detail", lambda s: detail.append(s["id"]))
    tab._on_row_double_clicked(tab.sort_proxy.index(0, col))
    tab._on_row_double_clicked(tab.sort_proxy.index(2, col))
    assert opened == [2] and detail == [1]


def test_specimen_photo_counts(lib):
    root, conn, cap, repo = lib
    c = _obs_db(root)
    assert pl.specimen_photo_counts(c) == {9: 1}
