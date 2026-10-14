"""Records from photos (14 Oct 2026): EXIF reading, grouping, rows, filing."""
import os
import sqlite3

import pytest

import paths
from shared import photo_files as pf
from shared import photo_intake as pi
from shared import photo_links as pl

CARAB = "Photos/Life/Insecta/Coleoptera/Carabidae"
SP = dict(species_name="Amara aenea", species_tvk="NBNSYS0000000001", common_name="Common Sun Beetle",
          order_name="Coleoptera", family="Carabidae", taxon_rank="Species")


def _dms(deg):
    deg = abs(deg)
    d = int(deg)
    m = int((deg - d) * 60)
    return (d, m, round((deg - d - m / 60) * 3600, 4))


def jpeg(path, date="2026:06:05 10:20:30", lat=None, lon=None):
    from PIL import Image
    im = Image.new("RGB", (8, 8), "green")
    ex = Image.Exif()
    if date:
        ex.get_ifd(0x8769)[0x9003] = date
    if lat is not None:
        g = ex.get_ifd(0x8825)
        g[1], g[2] = ("N" if lat >= 0 else "S"), _dms(lat)
        g[3], g[4] = ("E" if lon >= 0 else "W"), _dms(lon)
    im.save(path, exif=ex)
    return path


@pytest.fixture
def lib(tmp_path, monkeypatch):
    (tmp_path / CARAB / "Amara aenea" / "Specimen").mkdir(parents=True)
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    monkeypatch.setattr(paths, "ROOT", tmp_path / "proj")
    pf.refresh()
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "observatum.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pl.ensure_schema(conn)
    conn.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, species_tvk TEXT, "
                 "date TEXT, site_name TEXT, grid_ref TEXT)")
    conn.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, observation_id INTEGER)")
    cap = tmp_path / "capture"
    cap.mkdir()
    yield tmp_path, conn, cap, repo
    pf.refresh()


def test_read_photo_and_blanks(tmp_path):
    p = jpeg(tmp_path / "a.jpg", lat=51.75, lon=-1.26)
    r = pi.read_photo(p)
    assert r["taken"] == "2026-06-05" and r["time"] == "10:20:30"
    assert abs(r["lat"] - 51.75) < 1e-3 and abs(r["lon"] + 1.26) < 1e-3
    q = pi.read_photo(jpeg(tmp_path / "b.jpg", date=None))
    assert q["taken"] == "" and q["lat"] is None
    (tmp_path / "c.jpg").write_bytes(b"not a jpeg")
    assert pi.read_photo(tmp_path / "c.jpg")["taken"] == ""
    assert pi.read_photo(tmp_path / "missing.jpg")["lat"] is None


def test_grid_ref():
    ref = pi.grid_ref(51.75, -1.26)
    assert ref.startswith("SP") and len(ref) == 8
    assert pi.grid_ref(48.8, 2.3) is None and pi.grid_ref(None, None) is None


def test_group():
    def ph(n, lat, lon, d="2026-06-05"):
        return {"path": n, "taken": d, "time": "", "lat": lat, "lon": lon}
    a, b = ph("a", 51.75, -1.26), ph("b", 51.75027, -1.26)          # ~30 m
    c = ph("c", 51.7545, -1.26)                                      # ~500 m
    assert [len(g) for g in pi.group([a, b])] == [2]
    assert sorted(len(g) for g in pi.group([a, b, c])) == [1, 2]
    assert len(pi.group([a, ph("d", 51.75, -1.26, "2026-06-06")])) == 2
    n1, n2 = ph("n1", None, None), ph("n2", None, None)
    assert len(pi.group([n1, n2, a])) == 2


def test_existing_records(lib):
    _r, conn, _c, _repo = lib
    ref = pi.grid_ref(51.75, -1.26)
    conn.execute("INSERT INTO observations VALUES (1,'Amara aenea','T1','2026-06-05','Wood',?)", (ref,))
    conn.execute("INSERT INTO observations VALUES (2,'Amara aenea','T1','2026-06-05','Far','SU1010')")
    conn.execute("INSERT INTO observations VALUES (3,'Amara aenea',NULL,'2026-06-05','NoTvk',?)", (ref,))
    f = pi.existing_records(conn, "Amara aenea", "T1", "2026-06-05", 51.75, -1.26)
    assert [x[0] for x in f] == [1]
    assert [x[0] for x in pi.existing_records(conn, "Amara aenea", "T1", "2026-06-05")] == [1, 2]
    assert [x[0] for x in pi.existing_records(conn, "Amara aenea", None, "2026-06-05")] == [1, 2, 3]
    assert pi.existing_records(conn, "Amara aenea", "T1", "2026-06-07") == []


def test_make_rows(lib):
    root, conn, cap, repo = lib
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    p1 = jpeg(cap / "1.jpg", lat=51.75, lon=-1.26)
    p2 = jpeg(cap / "2.jpg", lat=51.75027, lon=-1.26)
    p3 = jpeg(cap / "3.jpg", date=None)
    groups = pi.group([pi.read_photo(p) for p in (p1, p2, p3)])
    ids = pi.make_rows(conn, jid, groups, SP, {"recorder": "Heeney, W.J.", "site_name": "Wood"})
    assert len(ids) == 2
    rows = {r["id"]: r for r in repo.fetch_rows(conn, jid)}
    dated = next(r for r in rows.values() if r["date"])
    assert dated["date"] == "2026-06-05" and dated["grid_ref"].startswith("SP") and len(dated["grid_ref"]) == 8
    assert int(dated["quantity"]) == 1 and dated["recorder"] == "Heeney, W.J." and dated["site_name"] == "Wood"
    assert dated["species_tvk"] == SP["species_tvk"]
    undated = next(r for r in rows.values() if not r["date"])
    assert not undated["grid_ref"]
    assert sorted(pl.photos_for_staging(conn, dated["id"])) == sorted([
        "Photos/_Bench/Amara aenea - Common Sun Beetle 5.vi.26.jpg",
        "Photos/_Bench/Amara aenea - Common Sun Beetle 5.vi.26 2.jpg"])
    assert (root / "Photos/_Bench/Amara aenea - Common Sun Beetle 5.vi.26.jpg").is_file()
    assert not p1.exists() and not p3.exists()


def test_attach_to_record_and_species_folder(lib):
    root, conn, cap, _repo = lib
    conn.execute("INSERT INTO observations VALUES (1,'Amara aenea','T1','2026-06-05','Wood','SP4599')")
    stored = pi.attach_to_record(conn, jpeg(cap / "x.jpg"), 1, SP, "2026-06-05")
    assert stored == f"{CARAB}/Amara aenea/Amara aenea - Common Sun Beetle 5.vi.26.jpg"
    assert "Specimen" not in stored and (root / stored).is_file()
    assert pl.photos_for_observation(conn, 1) == [stored]
    s2 = pi.to_species_folder(conn, jpeg(cap / "y.jpg"), SP, "2026-06-05")
    assert s2 == f"{CARAB}/Amara aenea/Amara aenea - Common Sun Beetle 5.vi.26 2.jpg"
    assert pl.link_count(conn, s2) == 0
    assert (root / s2).is_file()


def test_dialog_smoke(lib, monkeypatch):
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    _r, conn, cap, _repo = lib
    jpeg(cap / "1.jpg", lat=51.75, lon=-1.26)
    jpeg(cap / "2.jpg")
    from DataEntry import photo_attach
    monkeypatch.setattr(photo_attach, "capture_folder", lambda: cap)
    from DataEntry import photo_intake_dialog as d
    monkeypatch.setattr(d, "capture_folder", lambda: cap)
    dlg = d.PhotoIntakeDialog(conn, None, search_service=object())
    assert dlg.list.count() == 2 and dlg.job_box.count() >= 1
    assert not dlg.make_btn.isEnabled()
    dlg.list.selectAll()
    dlg.set_species({"scientific_name": "Amara aenea", "tvk": "T1", "common_name": "Common Sun Beetle",
                     "order": "Coleoptera", "family": "Carabidae", "rank": "Species"})
    assert dlg.make_btn.isEnabled()
    # one backup per window, before the first write; a failed backup changes nothing
    import shared.backup_service as bs
    calls = []
    monkeypatch.setattr(bs, "backup_main_only", lambda label: calls.append(label) or False)
    monkeypatch.setattr(d.QMessageBox, "warning", lambda *a, **k: None)
    rows_before = conn.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0]
    dlg._make_records()
    assert calls == ["pre-photo-intake"]
    assert conn.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0] == rows_before
    assert sorted(p.name for p in cap.iterdir()) == ["1.jpg", "2.jpg"]
    monkeypatch.setattr(bs, "backup_main_only", lambda label: calls.append(label) or True)
    assert dlg._backup() and dlg._backup() and calls == ["pre-photo-intake"] * 2


def test_field_photo_without_common_name_stays_a_field_photo(tmp_path, monkeypatch):
    """Review 14 Oct: a phone photo is known by its link (method FIELD), not its name, so one
    with no common name, or renamed for a new species, still goes to the species folder."""
    import sqlite3
    import paths
    from shared import bench_photos as bp
    from shared import photo_files as pf
    from shared import photo_links as pl
    from DataEntry import staging_repo as repo
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    pf.refresh()
    conn = sqlite3.connect(tmp_path / "o.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pl.ensure_schema(conn)
    cap = tmp_path / "cap"
    cap.mkdir()
    (cap / "a.jpg").write_bytes(b"x")
    jid = repo.create_job(conn, "P", "Personal", None, None)
    rid = repo.insert_row(conn, jid, {"species_name": "Amara aenea", "date": "2026-10-14"})
    p = bp.attach(conn, cap / "a.jpg", rid, "Amara aenea 14.x.26", field=True)
    assert pl.is_field_link(conn, p)
    res = bp.rename_for_row(conn, rid, ("Amara aenea", "", "2026-10-14"), ("Amara similata", "", "2026-10-14"))
    assert res.moved and res.moved[0][1].endswith("Amara similata 14.x.26.jpg")
    row = {"species_name": "Amara similata", "species_tvk": "T", "family": "Carabidae",
           "order_name": "Coleoptera", "date": "2026-10-14", "common_name": ""}
    safe, notes = bp.file_on_commit(conn, rid, row, 5)
    assert safe and notes == []
    got = conn.execute(f"SELECT photo_path FROM {pl.TABLE} WHERE observation_id = 5").fetchone()[0]
    assert got.endswith("/Amara similata/Amara similata 14.x.26.jpg") and "/Specimen/" not in got
    pf.refresh()
