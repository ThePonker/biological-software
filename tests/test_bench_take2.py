"""Bench photos take 2 (14 Oct 2026): photos wait in Photos/_Bench until commit; a species
change renames them there (no library folder for a typing slip); commit files them only for a
species picked from the list; deleted rows leave no link behind; the Photos housekeeping list."""
import sqlite3

import pytest

import paths
from shared import bench_photos as bp
from shared import photo_files as pf
from shared import photo_housekeeping as ph
from shared import photo_links as pl

CARAB = "Photos/Life/Insecta/Coleoptera/Carabidae"


@pytest.fixture
def lib(tmp_path, monkeypatch):
    (tmp_path / CARAB / "Amara aenea" / "Specimen").mkdir(parents=True)
    (tmp_path / CARAB / "Amara aenea" / "Specimen" / "Amara aenea gen 1.i.20.jpg").write_bytes(b"x")
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    monkeypatch.setattr(paths, "ROOT", tmp_path / "proj")
    pf.refresh()
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "o.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pl.ensure_schema(conn)
    cap = tmp_path / "capture"
    cap.mkdir()
    yield tmp_path, conn, cap, repo
    pf.refresh()


def _photo(cap, name="a.jpg"):
    f = cap / name
    f.write_bytes(b"jpg")
    return f


def _job_row(conn, repo, **kw):
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    return jid, repo.insert_row(conn, jid, {"species_name": "sde eff", "date": "05/06/2026",
                                            "quantity": "1", "recorder": "Heeney, W.J.", **kw})


def test_typing_slip_leaves_nothing_in_the_library(lib):
    root, conn, cap, repo = lib
    _jid, rid = _job_row(conn, repo)
    p = bp.attach(conn, _photo(cap), rid, "sde eff male gen 5.vi.26")
    assert p == "Photos/_Bench/sde eff male gen 5.vi.26.jpg"
    res = bp.rename_for_species(conn, rid, "sde eff", "Amara aenea")
    assert res.moved and not res.left
    assert pl.photos_for_staging(conn, rid) == ["Photos/_Bench/Amara aenea male gen 5.vi.26.jpg"]
    assert not (root / "Photos/Life/sde eff").exists() and ph.empty_folders() == []


def test_commit_files_photo_only_with_tvk(lib):
    root, conn, cap, repo = lib
    _jid, rid = _job_row(conn, repo)
    bp.attach(conn, _photo(cap), rid, "Amara aenea male gen 5.vi.26")
    row = {"species_name": "Amara aenea", "species_tvk": "NBNSYS0000010000", "family": "Carabidae"}
    assert bp.file_on_commit(conn, rid, row, 77) == (True, [])
    conn.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, observation_id INTEGER)")
    assert pl.photos_for_observation(conn, 77) == [
        f"{CARAB}/Amara aenea/Specimen/Amara aenea male gen 5.vi.26.jpg"]
    assert not list((root / "Photos/_Bench").iterdir())

    _jid, rid2 = _job_row(conn, repo)
    bp.attach(conn, _photo(cap, "b.jpg"), rid2, "sde eff male 5.vi.26")
    safe, notes = bp.file_on_commit(conn, rid2, {"species_name": "sde eff", "species_tvk": ""}, 78)
    assert safe and "stays in Photos/_Bench" in notes[0]
    assert pl.photos_for_observation(conn, 78) == ["Photos/_Bench/sde eff male 5.vi.26.jpg"]
    assert ph.bench_waiting(conn)[0][1] == "on a record whose species was not picked from the list"


def test_commit_service_files_the_photo(lib):
    root, conn, cap, repo = lib
    from DataEntry.commit_service import commit_job
    jid, rid = _job_row(conn, repo, species_name="Amara aenea", species_tvk="NBNSYS0000010000",
                        family="Carabidae")
    bp.attach(conn, _photo(cap), rid, "Amara aenea gen 5.vi.26")

    class Obs:
        def __init__(self, **kw):
            pass

    class Model:
        def create(self, o):
            return 91

    class Db:
        def execute_main_write(self, sql, params):
            return 1

    s = commit_job(Db(), Model(), conn, repo.get_job(conn, jid), observation_cls=Obs, taxonomy={})
    assert s["committed"] == 1 and s["photo_problems"] == []
    assert (root / CARAB / "Amara aenea/Specimen/Amara aenea gen 5.vi.26.jpg").is_file()


def test_deleted_row_keeps_the_photo_drops_the_link(lib):
    root, conn, cap, repo = lib
    _jid, rid = _job_row(conn, repo)
    bp.attach(conn, _photo(cap), rid, "sde eff gen")
    repo.delete_row(conn, rid)
    assert (root / "Photos/_Bench/sde eff gen.jpg").is_file()
    assert conn.execute("SELECT COUNT(*) FROM photo_links").fetchone()[0] == 0
    assert ph.bench_waiting(conn) == [("Photos/_Bench/sde eff gen.jpg",
                                       "not linked to anything (its row was deleted)")]


def test_release_sends_photos_back(lib):
    root, conn, cap, repo = lib
    jid, rid = _job_row(conn, repo)
    bp.attach(conn, _photo(cap), rid, "sde eff gen")
    assert bp.count_for_rows(conn, [rid]) == 1
    assert bp.release(conn, [rid], cap) == (1, [])
    assert [p.name for p in cap.iterdir()] == ["sde eff gen.jpg"]
    repo.delete_job(conn, jid)
    assert conn.execute("SELECT COUNT(*) FROM photo_links").fetchone()[0] == 0


def test_tidy_orphan_links(lib, tmp_path):
    root, conn, cap, repo = lib
    from scripts import tidy_bench_links as tb
    _jid, rid = _job_row(conn, repo)
    pl.add_staging_link(conn, "Photos/_Bench/x.jpg", rid)
    pl.add_staging_link(conn, "Photos/_Bench/y.jpg", 9999)             # its row was deleted
    pl.add_link(conn, "Photos/Life/z.jpg", observation_id=5)
    conn.commit()
    args = ["--db", str(root / "o.db"), "--backup-dir", str(tmp_path / "bk")]
    assert tb.main(args) == 0 and len(pl.orphan_staging_links(conn)) == 1
    assert tb.main(args + ["--apply"]) == 0
    assert pl.orphan_staging_links(conn) == []
    assert conn.execute("SELECT COUNT(*) FROM photo_links").fetchone()[0] == 2
    assert len(list((tmp_path / "bk").iterdir())) == 1


def test_empty_folders_listed_and_archived(lib):
    root, conn, cap, repo = lib
    (root / CARAB / "Gone sp" / "Specimen").mkdir(parents=True)
    (root / CARAB / "Gone sp" / "Specimen" / "desktop.ini").write_text("x")
    (root / CARAB / "Also gone").mkdir()
    assert ph.empty_folders() == [f"{CARAB[12:]}/Also gone", f"{CARAB[12:]}/Gone sp"]
    moved, notes, log = ph.archive_empty_folders(ph.empty_folders())
    assert len(moved) == 2 and notes == [] and log.is_file()
    assert ph.empty_folders() == []
    arch = next((root / "proj" / "_archive").iterdir())
    assert (arch / CARAB[12:] / "Gone sp" / "Specimen" / "desktop.ini").is_file()
    assert (root / CARAB / "Amara aenea/Specimen/Amara aenea gen 1.i.20.jpg").is_file()


def test_missing_files_and_names(lib):
    root, conn, cap, repo = lib
    pl.add_link(conn, "Photos/Life/nowhere.jpg", observation_id=3)
    conn.commit()
    assert ph.missing_files(conn) == [("Photos/Life/nowhere.jpg", "record 3")]
    (root / CARAB / "Amara aenea/Specimen/Amara aenea GEN 2.i.20.jpg").write_bytes(b"x")
    assert [d.name for _s, d in ph.nonstandard_names()] == ["Amara aenea gen 2.i.20.jpg"]


def test_photos_dialog(lib, monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    root, conn, cap, repo = lib
    from src.views.stats.photo_housekeeping_dialog import PhotoHousekeepingDialog
    (root / CARAB / "Empty sp").mkdir()
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    dlg = PhotoHousekeepingDialog(str(root / "o.db"))
    assert dlg.tables["empty"].rowCount() == 1 and dlg.btn_archive.isEnabled()
    dlg.confirm = lambda text: True
    dlg.archive_empty()
    assert dlg.tables["empty"].rowCount() == 0 and not (root / CARAB / "Empty sp").exists()


def test_send_back_only_for_rows_really_deleted(lib):
    root, conn, cap, repo = lib
    _jid, rid = _job_row(conn, repo)
    _jid2, keep = _job_row(conn, repo)
    bp.attach(conn, _photo(cap), rid, "sde eff gen")
    bp.attach(conn, _photo(cap, "b.jpg"), keep, "sde eff head")
    by_row = bp.photos_by_row(conn, [rid, keep])
    repo.delete_row(conn, rid)                                  # `keep` was not deleted
    assert bp.send_back(conn, by_row, cap) == (1, [])
    assert [p.name for p in cap.iterdir()] == ["sde eff gen.jpg"]
    assert pl.photos_for_staging(conn, keep) == ["Photos/_Bench/sde eff head.jpg"]


def test_commit_keeps_links_when_they_cannot_move(lib, monkeypatch):
    root, conn, cap, repo = lib
    from DataEntry.commit_service import commit_job
    jid, rid = _job_row(conn, repo, species_name="Amara aenea", species_tvk="NBNSYS0000010000")
    bp.attach(conn, _photo(cap), rid, "Amara aenea gen")

    def boom(*a):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(pl, "promote_staging", boom)

    class Obs:
        def __init__(self, **kw):
            pass

    class Model:
        def create(self, o):
            return 92

    class Db:
        def execute_main_write(self, sql, params):
            return 1

    s = commit_job(Db(), Model(), conn, repo.get_job(conn, jid), observation_cls=Obs, taxonomy={})
    assert s["committed"] == 1 and "database is locked" in s["photo_problems"][0]
    assert pl.photos_for_staging(conn, rid) == ["Photos/_Bench/Amara aenea gen.jpg"]   # kept


def test_tidy_tail_keeps_a_row_with_photos(lib):
    root, conn, cap, repo = lib
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from DataEntry.entry_grid import StagingTableModel
    jid, rid = _job_row(conn, repo)
    bp.attach(conn, _photo(cap), rid, "sde eff gen")
    repo.update_row(conn, rid, {k: None for k in ("species_name", "date", "quantity", "recorder")})
    m = StagingTableModel(conn, jid)
    assert m.trim_empty_tail() == 0 and m.real_count() == 1
