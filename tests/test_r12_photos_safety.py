"""Round 12 (24 Oct 2026): photo numbering, away mode for photos, move_photos keeping links,
the bracket-number rename script, and Data Entry's commit / delete safety."""
import csv
import importlib.util
import sqlite3
from pathlib import Path

import pytest

import paths
from shared import bench_photos as bp
from shared import photo_files as pf
from shared import photo_links as pl

L = "Photos/Life/Coleoptera/Carabidae/Amara aenea"
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def lib(tmp_path, monkeypatch):
    root = tmp_path / "Media"
    root.mkdir()
    monkeypatch.setattr(paths, "MEDIA_ROOT", root)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    monkeypatch.setenv("BIOSOFT_MEDIA_ROOT", str(root))
    monkeypatch.setenv("BIOSOFT_BACKUP_ROOT", str(tmp_path / "bk"))
    monkeypatch.setattr(paths, "AWAY_MODE", False, raising=False)
    pf.refresh()
    return root


def _file(root, rel):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x:" + rel.encode())
    return p


def _db(tmp_path, name="o.db"):
    c = sqlite3.connect(tmp_path / name)
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, species_name TEXT, observation_id INTEGER)")
    pl.ensure_schema(c)
    c.commit()
    return c


def _backup_ok(monkeypatch, result=True, calls=None):
    import shared.backup_service as bs

    def fake(label=""):
        if calls is not None:
            calls.append(label)
        return result
    monkeypatch.setattr(bs, "backup_main_only", fake)
    monkeypatch.setattr(bs, "backup_file_written", lambda _path, label="": fake(label))


# --- numbering ---------------------------------------------------------------------------
def test_free_path_counts_any_extension(tmp_path):
    (tmp_path / "X.tif").write_bytes(b"1")
    assert pf.free_path(tmp_path, "X", ".jpg") == tmp_path / "X 2.jpg"
    (tmp_path / "x 2.TIF").write_bytes(b"1")                       # case-insensitive
    assert pf.free_path(tmp_path, "X", ".jpg") == tmp_path / "X 3.jpg"
    assert pf.free_path(tmp_path, "Y", ".jpg") == tmp_path / "Y.jpg"
    assert pf.free_path(tmp_path / "nope", "Y", ".jpg") == tmp_path / "nope" / "Y.jpg"


def test_strip_bench_number_only_a_separate_digit_word():
    assert pf.strip_bench_number("Maro lepidus male 19.x.26 2") == "Maro lepidus male 19.x.26"
    assert pf.strip_bench_number("Maro lepidus male 19.x.26") == "Maro lepidus male 19.x.26"
    assert pf.strip_bench_number("Maro lepidus 2") == "Maro lepidus"


def _commit_setup(tmp_path, lib, bench_names, folder_names=()):
    for n in folder_names:
        _file(lib, f"{L}/Specimen/{n}")
    conn = _db(tmp_path)
    for n in bench_names:
        rel = f"Photos/_Bench/{n}"
        _file(lib, rel)
        pl.add_staging_link(conn, rel, 5)
    conn.commit()
    row = {"species_name": "Amara aenea", "species_tvk": "T1", "family": "Carabidae",
           "order_name": "Coleoptera", "sex": "", "date": ""}
    return conn, row


def test_commit_numbers_afresh_in_the_specimen_folder(tmp_path, lib):
    stem = "Amara aenea male 19.x.26"
    conn, row = _commit_setup(tmp_path, lib, [f"{stem}.jpg", f"{stem} 2.jpg"],
                              [f"{stem}.jpg", f"{stem} 2.jpg"])
    ok, notes = bp.file_on_commit(conn, 5, row, 77)
    assert ok and not notes
    names = sorted(p.name for p in (lib / L / "Specimen").iterdir())
    assert names == [f"{stem} 2.jpg", f"{stem} 3.jpg", f"{stem} 4.jpg", f"{stem}.jpg"]
    assert not any(n.endswith(" 2 2.jpg") for n in names)
    moved = {p for (p,) in conn.execute(f"SELECT photo_path FROM {pl.TABLE} WHERE observation_id = 77")}
    assert moved == {f"{L}/Specimen/{stem} 3.jpg", f"{L}/Specimen/{stem} 4.jpg"}


def test_jpg_and_tif_of_one_view_get_two_numbers(tmp_path, lib):
    stem = "Amara aenea male 19.x.26"
    (lib / L / "Specimen").mkdir(parents=True)
    conn, row = _commit_setup(tmp_path, lib, [f"{stem}.jpg", f"{stem}.tif"])
    ok, notes = bp.file_on_commit(conn, 5, row, 77)
    assert ok and not notes
    assert sorted(p.name for p in (lib / L / "Specimen").iterdir()) == [f"{stem} 2.tif", f"{stem}.jpg"]


# --- away mode ---------------------------------------------------------------------------
def test_photo_moves_and_connect_rw_refuse_when_away(tmp_path, lib, monkeypatch):
    src = _file(lib, "Photos/Life/a/X.jpg")
    conn = _db(tmp_path)
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    with pytest.raises(OSError, match="Away mode: photos can't be moved"):
        pf.move_photo(conn, src, src.parent / "Y.jpg")
    with pytest.raises(OSError, match="Away mode"):
        pf.move_for_redet(conn, ["Photos/Life/a/X.jpg"], "Aaa bbb", "Ccc ddd")
    with pytest.raises(OSError, match="Away mode"):
        bp.attach(conn, src, 1, "Z")
    with pytest.raises(OSError, match="Away mode"):
        bp.send_back(conn, {}, tmp_path)
    assert src.is_file()
    from shared.db_open import AwayReadOnly, connect_rw
    with pytest.raises(AwayReadOnly):
        connect_rw(tmp_path / "o.db")
    res = pf.follow_redet(tmp_path / "o.db", "specimen", 1, "Aaa bbb", "Ccc ddd")
    assert res is not None and res.left and not res.moved
    monkeypatch.setattr(paths, "AWAY_MODE", False)
    assert connect_rw(tmp_path / "o.db").execute("SELECT 1").fetchone() == (1,)


# --- the bracket-number rename script ----------------------------------------------------
def _script(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_rename_bracket_numbers_dry_run_then_apply(tmp_path, lib, monkeypatch, capsys):
    rn = _script("rename_bracket", "scripts/_oneoff/rename_bracket_numbers_20261024.py")
    f = "Photos/Life/Pterostichus madidus/Specimen"
    _file(lib, f"{f}/Pterostichus madidus 21.iii.18 (3).jpg")
    _file(lib, f"{f}/Pterostichus madidus 21.iii.18 3.tif")            # taken (other extension)
    _file(lib, f"{f}/Pterostichus madidus 5.v.19 (2).jpg")
    _file(lib, f"{f}/Pterostichus madidus 6.v.19 (2).jpg")             # not linked
    conn = _db(tmp_path)
    pl.add_link(conn, f"{f}/Pterostichus madidus 21.iii.18 (3).jpg", specimen_id=1)
    pl.add_link(conn, f"{f}/Pterostichus madidus 5.v.19 (2).jpg", specimen_id=2)
    conn.commit()
    conn.close()
    before = sorted(p.name for p in (lib / f).iterdir())
    assert rn.main(["--db", str(tmp_path / "o.db")]) == 0
    out = capsys.readouterr().out
    assert "to rename: 2" in out and "unlinked '(N)' files in the same folders (not renamed): 1" in out
    assert out.strip().endswith("Nothing has been changed.")
    assert sorted(p.name for p in (lib / f).iterdir()) == before

    calls = []
    _backup_ok(monkeypatch, True, calls)
    assert rn.main(["--db", str(tmp_path / "o.db"), "--apply"]) == 0
    assert calls == ["pre-rename-bracket-numbers"]
    names = sorted(p.name for p in (lib / f).iterdir())
    assert "Pterostichus madidus 21.iii.18 4.jpg" in names           # 3 was taken by the .tif
    assert "Pterostichus madidus 5.v.19 2.jpg" in names
    assert "Pterostichus madidus 6.v.19 (2).jpg" in names             # unlinked: left
    c = sqlite3.connect(tmp_path / "o.db")
    assert pl.photos_for_specimen(c, 1) == [f"{f}/Pterostichus madidus 21.iii.18 4.jpg"]
    assert pl.photos_for_specimen(c, 2) == [f"{f}/Pterostichus madidus 5.v.19 2.jpg"]


def test_rename_apply_refuses_when_the_backup_fails(tmp_path, lib, monkeypatch):
    rn = _script("rename_bracket2", "scripts/_oneoff/rename_bracket_numbers_20261024.py")
    f = "Photos/Life/P/Specimen"
    _file(lib, f"{f}/P p 1.i.20 (2).jpg")
    conn = _db(tmp_path)
    pl.add_link(conn, f"{f}/P p 1.i.20 (2).jpg", specimen_id=1)
    conn.commit()
    conn.close()
    _backup_ok(monkeypatch, False)
    assert rn.main(["--db", str(tmp_path / "o.db"), "--apply"]) == 1
    assert (lib / f / "P p 1.i.20 (2).jpg").is_file()


# --- move_photos keeps links -------------------------------------------------------------
def test_move_photos_apply_and_reverse_keep_links(tmp_path, lib, monkeypatch):
    mp = _script("move_photos_mod", "scripts/move_photos.py")
    _file(lib, "Photos/old/A.jpg")
    conn = _db(tmp_path)
    pl.add_link(conn, "Photos/old/A.jpg", specimen_id=1)
    conn.commit()
    conn.close()
    moves = tmp_path / "moves.csv"
    with open(moves, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "destination"])
        w.writerow(["Photos/old/A.jpg", "Photos/new/A.jpg"])
    calls = []
    _backup_ok(monkeypatch, True, calls)
    log = tmp_path / "log.csv"
    base = ["--root", str(lib), "--db", str(tmp_path / "o.db")]
    assert mp.main(base + ["--moves", str(moves), "--apply", "--log", str(log)]) == 0
    assert calls == ["pre-move-photos"] and (lib / "Photos/new/A.jpg").is_file()
    c = sqlite3.connect(tmp_path / "o.db")
    assert pl.photos_for_specimen(c, 1) == ["Photos/new/A.jpg"]
    c.close()
    rlog = tmp_path / "rlog.csv"
    assert mp.main(base + ["--reverse", str(log), "--apply", "--log", str(rlog)]) == 0
    c = sqlite3.connect(tmp_path / "o.db")
    assert pl.photos_for_specimen(c, 1) == ["Photos/old/A.jpg"]
    assert (lib / "Photos/old/A.jpg").is_file() and not (lib / "Photos/new/A.jpg").exists()


def test_move_photos_apply_refuses_when_backup_fails_or_away(tmp_path, lib, monkeypatch):
    mp = _script("move_photos_mod2", "scripts/move_photos.py")
    _file(lib, "Photos/old/A.jpg")
    conn = _db(tmp_path)
    conn.close()
    moves = tmp_path / "moves.csv"
    moves.write_text("source,destination\nPhotos/old/A.jpg,Photos/new/A.jpg\n", encoding="utf-8")
    args = ["--root", str(lib), "--db", str(tmp_path / "o.db"), "--moves", str(moves), "--apply",
            "--log", str(tmp_path / "l.csv")]
    _backup_ok(monkeypatch, False)
    assert mp.main(args) == 1 and (lib / "Photos/old/A.jpg").is_file()
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    with pytest.raises(SystemExit):
        mp.main(args)
    assert (lib / "Photos/old/A.jpg").is_file()


# --- Data Entry: embargo with the record, delete job needs the backup --------------------
def test_embargo_status_is_written_with_the_record():
    from DataEntry import staging_repo as repo
    from DataEntry.commit_service import build_kwargs_from_row, commit_job

    row = dict(species_name="Amara aenea", species_tvk="T1", date="2026-06-05", site_name="S",
               grid_ref="TQ9368", sex="", stage="Adult", recorder="R", vc_number=15,
               order_name="Coleoptera", family="Carabidae")
    kw = build_kwargs_from_row(row, {"mode": "Commercial", "project": "P", "client": "C"}, "2027-01-01")
    assert (kw["embargo_status"], kw["embargo_until"]) == ("Active", "2027-01-01")
    assert build_kwargs_from_row(row, {"mode": "Personal"}, "2027-01-01")["embargo_status"] is None

    class Obs:
        def __init__(self, **kw):
            self.kw = kw

    class Model:
        made = []

        def create(self, o):
            self.made.append(o.kw)
            return 9

    class Db:                                   # the second UPDATE fails: embargo must not depend on it
        def execute_main_write(self, sql, params):
            raise RuntimeError("locked")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "Hook Farm", "Commercial", "BAM", "Hook Farm")
    repo.insert_row(conn, jid, row)
    model = Model()
    commit_job(Db(), model, conn, repo.get_job(conn, jid), "2027-01-01", observation_cls=Obs, taxonomy={})
    assert model.made[0]["embargo_status"] == "Active"


def test_delete_job_refuses_when_the_backup_fails(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    QApplication.instance() or QApplication([])
    from DataEntry import staging_repo as repo
    from DataEntry.jobs_list_page import JobsListPage

    conn = sqlite3.connect(tmp_path / "s.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    repo.ensure_personal_job(conn)
    jid = repo.create_job(conn, "Hook Farm", "Commercial", "BAM", "Hook Farm")
    repo.insert_row(conn, jid, {"species_name": "Amara aenea", "date": "2026-06-05"})
    page = JobsListPage(conn)
    page._select_job(jid)
    shown = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[1:3]))
    import DataEntry.photo_attach as photo_attach
    monkeypatch.setattr(photo_attach, "ask_about_photos", lambda *a, **k: (lambda: None))
    calls = []
    _backup_ok(monkeypatch, False, calls)
    page._delete_selected()
    assert calls == ["pre-delete-job"] and shown
    assert repo.get_job(conn, jid) is not None and repo.row_count(conn, jid) == 1
    _backup_ok(monkeypatch, True, calls)
    page._delete_selected()
    assert repo.get_job(conn, jid) is None


def test_bench_redet_numbers_afresh_not_x_2_2(tmp_path, lib):
    """Review 24 Oct: a re-det inside _Bench into a name already used there gave 'X 2 2'."""
    conn = _db(tmp_path)
    bench = lib / "Photos" / "_Bench"
    for n in ("Amara aenea.tif", "Amara aenea 2.tif"):            # row 1's photos
        _file(lib, f"Photos/_Bench/{n}")
        pl.add_staging_link(conn, f"Photos/_Bench/{n}", 1)
    for n in ("Amara similata.tif", "Amara similata 2.tif"):      # row 2's photos
        _file(lib, f"Photos/_Bench/{n}")
        pl.add_staging_link(conn, f"Photos/_Bench/{n}", 2)
    conn.commit()
    res = bp.rename_for_species(conn, 2, "Amara similata", "Amara aenea")
    assert len(res.moved) == 2
    names = sorted(p.name for p in bench.iterdir())
    assert names == ["Amara aenea 2.tif", "Amara aenea 3.tif", "Amara aenea 4.tif", "Amara aenea.tif"]
