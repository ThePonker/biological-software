"""Round 5 (14 Oct 2026, the workflow review): no record exported to iRecord twice, bench
photos only on the live database, a failed staging delete stops the commit, bench photos named
from the row at commit, photos on a record filed once it has a species from UKSI, links to
deleted records found and tidied, clears count as edits."""
import os
import sqlite3
from types import SimpleNamespace

import pytest

import paths
from shared import bench_photos as bp
from shared import irecord_exported as ie
from shared import photo_files as pf
from shared import photo_housekeeping as ph
from shared import photo_links as pl
from shared import sync_conflicts as sc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
CARAB = "Photos/Life/Insecta/Coleoptera/Carabidae"


def _obs_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY AUTOINCREMENT, species_name TEXT, "
              "species_tvk TEXT, family TEXT, order_name TEXT, sex TEXT, date TEXT, irecord_id INTEGER)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY AUTOINCREMENT, species_name TEXT, "
              "species_tvk TEXT, family TEXT, order_name TEXT, sex TEXT, date_collected TEXT, observation_id INTEGER)")
    pl.ensure_schema(c)
    return c


@pytest.fixture
def lib(tmp_path, monkeypatch):
    (tmp_path / CARAB / "Amara aenea" / "Specimen").mkdir(parents=True)
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    pf.refresh()
    bp.bench_root().mkdir(parents=True)
    c = _obs_db(tmp_path / "o.db")
    yield tmp_path, c
    c.close()
    pf.refresh()


def test_exported_records_are_remembered(tmp_path):
    from scripts import add_irecord_exported_column as mig
    c = _obs_db(tmp_path / "o.db")
    c.executemany("INSERT INTO observations (id, species_name, irecord_id) VALUES (?,?,?)",
                  [(1, "A b", None), (2, "C d", None), (3, "E f", 555)])
    c.commit()
    c.close()
    args = ["--db", str(tmp_path / "o.db"), "--backup-dir", str(tmp_path / "bk")]
    assert mig.main(args) == 0 and mig.main(args + ["--apply"]) == 0
    c = sqlite3.connect(tmp_path / "o.db")
    assert ie.has_column(c) and ie.waiting(c, [1, 2, 3]) == {}
    assert ie.stamp(c, [1, 3], "2026-10-14") == 2
    assert ie.waiting(c, [1, 2, 3]) == {1: "2026-10-14"}          # 3 came back from iRecord


def test_photo_button_only_on_live_database(tmp_path):
    from DataEntry.entry_grid import EntryGridPage
    for name, live in (("observatum.db", True), ("observatum_dev_20261014.db", False)):
        conn = sqlite3.connect(tmp_path / name)
        assert EntryGridPage._on_live_db(SimpleNamespace(_conn=conn)) is live
        conn.close()


def test_failed_staging_delete_stops_the_commit(tmp_path, monkeypatch):
    from DataEntry import commit_service as cs
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "o.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    for sp in ("Amara aenea", "Amara similata"):
        repo.insert_row(conn, jid, {"species_name": sp, "date": "05/06/2026", "quantity": "1",
                                    "recorder": "Heeney, W.J."})

    def locked(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(repo, "delete_row", locked)

    class Model:
        n = 0

        def create(self, o):
            Model.n += 1
            return 100 + Model.n

    class Db:
        def execute_main_write(self, sql, params):
            return 1
    s = cs.commit_job(Db(), Model(), conn, repo.get_job(conn, jid),
                      observation_cls=lambda **kw: None, taxonomy={})
    assert s["committed"] == 1 and "Delete that row by hand" in s["error"]


def test_name_from_the_row_at_commit():
    row = {"species_name": "Amara similata", "sex": "Female", "date": "2026-06-07"}
    assert bp.name_for_commit("Amara aenea male gen 5.vi.26", row) == "Amara similata female gen 7.vi.26"
    assert bp.name_for_commit("Amara similata head", row) == "Amara similata head"


def test_photo_on_a_record_filed_once_species_picked(lib):
    root, c = lib
    c.execute("INSERT INTO observations (id, species_name, species_tvk, family, date) "
              "VALUES (1, 'Amara aenea', '', 'Carabidae', '2026-06-05')")
    (bp.bench_root() / "Amara aenea gen.jpg").write_bytes(b"x")
    pl.add_link(c, "Photos/_Bench/Amara aenea gen.jpg", observation_id=1)
    c.commit()
    assert bp.file_record_photos(c, [1]) == ([], [])                   # no TVK yet: stays
    assert ph.bench_waiting(c)[0][1] == ph.ON_RECORD
    c.execute("UPDATE observations SET species_tvk = 'NBNSYS0000010000' WHERE id = 1")
    c.commit()
    moved, notes = bp.file_record_photos(c, [1])
    assert moved == [("Photos/_Bench/Amara aenea gen.jpg", f"{CARAB}/Amara aenea/Specimen/Amara aenea gen.jpg")]
    assert not notes and pl.photos_for_observation(c, 1) == [moved[0][1]]


def test_redet_files_a_bench_photo(lib):
    root, c = lib
    (root / CARAB / "Amara similata").mkdir()
    c.execute("INSERT INTO observations (id, species_name, species_tvk, family) "
              "VALUES (1, 'Amara similata', 'T2', 'Carabidae')")
    (bp.bench_root() / "Amara aenea gen.jpg").write_bytes(b"x")
    pl.add_link(c, "Photos/_Bench/Amara aenea gen.jpg", observation_id=1)
    c.commit()
    res = pf.follow_redet(str(root / "o.db"), "observation", 1, "Amara aenea", "Amara similata", notify=False)
    assert res.moved and not res.left
    assert pl.photos_for_observation(c, 1) == [f"{CARAB}/Amara similata/Specimen/Amara similata gen.jpg"]


def test_deleted_specimen_photos_and_dead_links(lib, tmp_path):
    root, c = lib
    from scripts import tidy_bench_links as tb
    c.execute("INSERT INTO specimens (id, species_name) VALUES (5, 'Amara aenea')")
    (root / CARAB / "Amara aenea/Specimen/a.jpg").write_bytes(b"x")
    pl.add_link(c, f"{CARAB}/Amara aenea/Specimen/a.jpg", specimen_id=5)
    pl.add_link(c, f"{CARAB}/Amara aenea/Specimen/a.jpg", observation_id=77)    # record 77 is gone
    c.commit()
    assert ph.dead_links(c) == [(f"{CARAB}/Amara aenea/Specimen/a.jpg", "record 77")]
    by = bp.record_photos(c, [5], "specimen")
    c.execute("DELETE FROM specimens WHERE id = 5")
    c.commit()
    assert bp.release_records(c, by, True, "specimen") == (0, [])     # still linked (to 77)
    assert pl.photos_for_specimen(c, 5) == []
    args = ["--db", str(root / "o.db"), "--backup-dir", str(tmp_path / "bk")]
    assert tb.main(args) == 0 and tb.main(args + ["--apply"]) == 0
    assert ph.dead_links(c) == [] and (root / CARAB / "Amara aenea/Specimen/a.jpg").is_file()


def test_a_cleared_field_is_an_edit():
    assert sc.cleared({"comment": "under log"}, {"comment": ""}) == ["comment"]
    assert sc.cleared({"comment": ""}, {"comment": ""}) == []


def test_bench_tab_files_photo_with_its_record(lib, monkeypatch):
    root, c = lib
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    c.execute("INSERT INTO observations (id, species_name, species_tvk, family) "
              "VALUES (1, 'Amara aenea', 'T1', 'Carabidae')")
    (bp.bench_root() / "Amara aenea gen.jpg").write_bytes(b"x")
    pl.add_link(c, "Photos/_Bench/Amara aenea gen.jpg", observation_id=1)
    c.commit()
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    from src.views.stats.photo_housekeeping_dialog import PhotoHousekeepingDialog
    dlg = PhotoHousekeepingDialog(str(root / "o.db"))
    dlg.tables["bench"].selectRow(0)
    assert dlg.btn_bench_file.isEnabled() and not dlg.btn_bench_archive.isEnabled()
    dlg.bench_file()
    assert dlg.tables["bench"].rowCount() == 0
    assert (root / CARAB / "Amara aenea/Specimen/Amara aenea gen.jpg").is_file()
