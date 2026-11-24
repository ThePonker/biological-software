"""Photo health check (Wil's list 11 Nov 2026, item 9): every check finds what it should on a small
purpose-made library and database, and nothing is changed."""
import hashlib
import importlib.util
import os
import sqlite3
from pathlib import Path

import pytest

import paths
from shared import photo_files as pf
from shared import photo_links as pl

ROOT = Path(__file__).resolve().parents[1]
CARAB = "Photos/Life/Insecta/Coleoptera/Carabidae"


def _load():
    spec = importlib.util.spec_from_file_location("check_photo_health", ROOT / "scripts" / "check_photo_health.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(root, rel, data=b"jpg"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return rel


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(paths, "ROOT", tmp_path / "proj")
    spec = f"{CARAB}/Amara aenea/Specimen"
    good = _write(tmp_path, f"{spec}/Amara aenea male gen 1.i.20.jpg", b"one")
    loose = _write(tmp_path, f"{spec}/Amara aenea gen 2.i.20.jpg", b"two!")
    _write(tmp_path, f"{spec}/IMG_1234.jpg", b"three")                            # camera name, unlinked
    _write(tmp_path, f"{spec}/Amara aenea Male gen 6.I.20.jpg", b"four44")         # not to the standard
    _write(tmp_path, f"{CARAB}/Amara aenea/Amara aenea 3.i.20 (2).jpg", b"dup")   # bracket number
    _write(tmp_path, f"{CARAB}/Amara aenea/Amara aenea 3.i.20.jpg", b"dup")       # same size, same folder
    (tmp_path / CARAB / "Empty species").mkdir(parents=True)
    bench = _write(tmp_path, "Photos/_Bench/waiting gen 4.i.20.jpg")
    pf.refresh()
    conn = sqlite3.connect(tmp_path / "o.db")
    conn.executescript("""
        CREATE TABLE observations(id INTEGER PRIMARY KEY, species_name TEXT);
        CREATE TABLE specimens(id INTEGER PRIMARY KEY, species_name TEXT);
        INSERT INTO observations VALUES (1,'Amara aenea'),(2,'Amara aenea');
        INSERT INTO specimens VALUES (5,'Amara aenea');""")
    pl.ensure_schema(conn)
    pl.add_link(conn, good, specimen_id=5)
    pl.add_link(conn, good, observation_id=1)
    pl.add_link(conn, good, observation_id=2)                         # one photo on two records
    pl.add_link(conn, f"{CARAB}/Gone/Specimen/gone.jpg", observation_id=1)   # file missing
    pl.add_link(conn, loose, observation_id=99)                       # record deleted
    conn.execute(f"INSERT INTO {pl.TABLE}(photo_path, observation_id, method) VALUES (?,?,?)",
                 (good.replace("/", "\\"), 1, "by hand"))             # stored with backslashes
    conn.commit()
    yield tmp_path, conn, bench
    conn.close()
    pf.refresh()


def _digest(root):
    h = hashlib.sha256()
    for d, _ds, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            p = Path(d) / f
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def test_every_check_finds_its_case_and_nothing_changes(lib, tmp_path):
    root, conn, bench = lib
    mod = _load()
    before_db = list(conn.iterdump())
    before_files = _digest(root)
    lines = []
    items, summary = mod.run(conn, root / "proj" / "out.csv", out=lines.append)
    kinds = {}
    for check, path, _detail in items:
        kinds.setdefault(check, []).append(path)
    assert kinds["missing file"] == [f"{CARAB}/Gone/Specimen/gone.jpg"]
    assert any("Amara aenea gen 2.i.20.jpg" in p for p in kinds["dead link"])
    assert len(kinds["non-standard link path"]) == 1
    assert len(kinds["photo on several records"]) == 1
    assert sorted(Path(p).name for p in kinds["specimen photo not linked"]) == ["Amara aenea Male gen 6.I.20.jpg",
                                                                                "IMG_1234.jpg"]
    assert kinds["on the bench"] == [bench]
    assert kinds["empty folder"] == ["Insecta/Coleoptera/Carabidae/Empty species"]
    assert [Path(p).name for p in kinds["non-standard name"]] == ["Amara aenea Male gen 6.I.20.jpg"]
    assert [Path(p).name for p in kinds["bracket number in name"]] == ["Amara aenea 3.i.20 (2).jpg"]
    assert len(kinds["possible duplicate"]) == 2
    assert summary["library photos"] == 6 and summary["links"] == 6
    # read only: database and library untouched; the CSV is the only file written
    assert list(conn.iterdump()) == before_db
    os.remove(root / "proj" / "out.csv")
    os.rmdir(root / "proj")
    assert _digest(root) == before_files


def test_no_link_table_and_no_library_still_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "MEDIA_ROOT", tmp_path / "nowhere")
    pf.refresh()
    mod = _load()
    conn = sqlite3.connect(":memory:")
    lines = []
    items, summary = mod.run(conn, None, out=lines.append)
    assert items == [] and summary["library photos"] == 0
    text = "\n".join(lines)
    assert "Photos\\Life was not found" in text and "photo_links table was not found" in text
    pf.refresh()


def test_script_says_read_only_and_never_deletes():
    src = (ROOT / "scripts" / "check_photo_health.py").read_text(encoding="utf-8")
    assert "READ ONLY. Nothing has been changed." in src
    assert "mode=ro" in src
    for bad in ("os.remove", "unlink(", "rmtree", "os.rename", "DELETE", "UPDATE ", "INSERT "):
        assert bad not in src
