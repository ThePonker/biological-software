"""Photos B2/B5 (13 Oct 2026): the record <-> photo link table, the migration and link
scripts, and a re-determination moving the record's photos -- on throwaway databases and
folders. Nothing is deleted or overwritten."""
import csv
import sqlite3

import paths
from scripts import add_photo_links_table as mig
from shared import photo_files as pf
from shared import photo_links as pl

L = "Photos/Life/Insecta/Coleoptera/Carabidae"


def _db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, species_name TEXT, observation_id INTEGER)")
    c.executemany("INSERT INTO observations VALUES (?,?)", [(1, "Amara aenea"), (2, "Amara aenea")])
    c.executemany("INSERT INTO specimens VALUES (?,?,?)", [(10, "Amara aenea", 1), (11, "Amara aenea", None)])
    c.commit()
    return c


def _lib(tmp_path, monkeypatch, files):
    root = tmp_path / "Media"
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"jpg:" + rel.encode())
    monkeypatch.setattr(paths, "MEDIA_ROOT", root)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    monkeypatch.setattr(pf, "_listeners", [])        # no window from another test is told
    pf.refresh()
    return root


def _files(root):
    return sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file())


# --- the table ------------------------------------------------------------------------------
def test_links_and_lookups(tmp_path):
    c = _db(tmp_path / "o.db")
    assert pl.photos_for_observation(c, 1) == []            # no table yet: nothing, no error
    assert pl.ensure_schema(c) is True and pl.ensure_schema(c) is False
    assert pl.add_link(c, f"{L}/Amara aenea/Specimen/a.jpg", specimen_id=10, method=pl.SPECIMEN_MATCH)
    assert not pl.add_link(c, f"{L}\\Amara aenea\\Specimen\\a.jpg", specimen_id=10)  # same link
    pl.add_link(c, f"{L}/Amara aenea/field.jpg", observation_id=1)
    assert pl.photos_for_specimen(c, 10) == [f"{L}/Amara aenea/Specimen/a.jpg"]
    assert pl.photos_for_observation(c, 1) == [f"{L}/Amara aenea/Specimen/a.jpg", f"{L}/Amara aenea/field.jpg"]
    assert pl.photos_for_observation(c, 2) == []
    assert pl.repoint(c, f"{L}/Amara aenea/field.jpg", f"{L}/X/field.jpg") == 1
    assert pl.linked_specimen_ids(c, [10, 11]) == {10}


def test_migration_dry_run_then_apply(tmp_path):
    db = tmp_path / "o.db"
    _db(db).close()
    assert mig.main(["--db", str(db), "--backup-dir", str(tmp_path / "bk")]) == 0
    c = sqlite3.connect(db)
    assert not pl.has_table(c)                                # dry run wrote nothing
    c.close()
    assert mig.main(["--db", str(db), "--backup-dir", str(tmp_path / "bk"), "--apply"]) == 0
    c = sqlite3.connect(db)
    assert pl.has_table(c) and c.execute("SELECT COUNT(*) FROM specimens").fetchone()[0] == 2
    assert len(list((tmp_path / "bk").iterdir())) == 1        # one backup, taken first
    assert mig.main(["--db", str(db), "--backup-dir", str(tmp_path / "bk"), "--apply"]) == 0
    assert len(list((tmp_path / "bk").iterdir())) == 1        # nothing to do: no new backup


def test_link_plan_takes_only_single_specimen_matches():
    from scripts.link_specimen_photos import HAVE, LINK, NO_SPECIMEN, SEVERAL, plan
    rows = [{"rel_path": "a.jpg", "specimen_count": 1, "specimen_ids": "10:C1"},
            {"rel_path": "b.jpg", "specimen_count": 1, "specimen_ids": "11:C2"},
            {"rel_path": "c.jpg", "specimen_count": 2, "specimen_ids": "10:C1;11:C2"},
            {"rel_path": "d.jpg", "specimen_count": 0, "specimen_ids": ""},
            {"rel_path": "e.jpg", "specimen_count": "", "specimen_ids": ""}]
    out = {p: (o, sid) for p, o, sid, _ in plan(rows, {("b.jpg", 11)})}
    assert out == {"a.jpg": (LINK, 10), "b.jpg": (HAVE, 11), "c.jpg": (SEVERAL, None),
                   "d.jpg": (NO_SPECIMEN, None)}


# --- the library and the re-det ------------------------------------------------------------
def test_species_photos_from_the_folder(tmp_path, monkeypatch):
    root = _lib(tmp_path, monkeypatch, [
        f"{L}/Amara aenea/Amara aenea - Common Sun Beetle.jpg",
        f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg",
        f"{L}/Amara aenea/notes.txt",
        f"{L}/Drymus sylvaticus/Specimen/Drymus sylvaticus 2.i.21.jpg"])
    assert pf.species_photos("Amara aenea") == [f"{L}/Amara aenea/Amara aenea - Common Sun Beetle.jpg",
                                                f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg"]
    assert pf.species_photos("Drymus (Sylvadrymus) sylvaticus") == [
        f"{L}/Drymus sylvaticus/Specimen/Drymus sylvaticus 2.i.21.jpg"]
    assert pf.species_photos("Nothing here") == []
    assert pf.absolute(f"{L}/x.jpg") == root / L / "x.jpg"


def test_specimen_redet_moves_its_photos_and_logs(tmp_path, monkeypatch):
    root = _lib(tmp_path, monkeypatch, [
        f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg",
        f"{L}/Amara aenea/Specimen/Amara aenea male 5.v.22 2.jpg",
        f"{L}/Amara aenea/Specimen/IMG_0001.jpg",
        f"{L}/Amara ovata/Specimen/Amara ovata 1.i.20.jpg"])
    db = tmp_path / "o.db"
    c = _db(db)
    pl.ensure_schema(c)
    for f in ("Amara aenea 5.v.22.jpg", "Amara aenea male 5.v.22 2.jpg", "IMG_0001.jpg"):
        pl.add_link(c, f"{L}/Amara aenea/Specimen/{f}", specimen_id=11)
    c.commit()
    c.close()
    notes = []
    pf.add_listener(notes.append)
    res = pf.follow_redet(str(db), "specimen", 11, "Amara aenea", "Amara ovata")
    assert sorted(new for _, new in res.moved) == [
        f"{L}/Amara ovata/Specimen/Amara ovata 5.v.22.jpg",
        f"{L}/Amara ovata/Specimen/Amara ovata male 5.v.22 2.jpg"]
    assert [why for _, why in res.left] == ["name does not start with Amara aenea"]
    assert f"{L}/Amara aenea/Specimen/IMG_0001.jpg" in _files(root)
    assert len(_files(root)) == 4                            # moved, never copied or lost
    c = sqlite3.connect(db)
    assert sorted(pl.photos_for_specimen(c, 11))[0] == f"{L}/Amara aenea/Specimen/IMG_0001.jpg"
    assert f"{L}/Amara ovata/Specimen/Amara ovata 5.v.22.jpg" in pl.photos_for_specimen(c, 11)
    logs = list((tmp_path / "logs").iterdir())
    assert len(logs) == 1                                    # one log per re-det
    with open(logs[0], encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 2             # move_photos.py --reverse reads it
    assert notes and notes[-1].startswith("2 photos moved to Amara ovata")


def test_redet_leaves_shared_taken_and_new_folders(tmp_path, monkeypatch):
    root = _lib(tmp_path, monkeypatch, [
        f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg",
        f"{L}/Amara aenea/Specimen/Amara aenea 6.v.22.jpg",
        f"{L}/Amara aenea/Amara aenea - field.jpg",
        f"{L}/Amara curta/Specimen/Amara curta 6.v.22.jpg"])
    db = tmp_path / "o.db"
    c = _db(db)
    pl.ensure_schema(c)
    pl.add_link(c, f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg", observation_id=2)
    pl.add_link(c, f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg", specimen_id=11)   # shared
    pl.add_link(c, f"{L}/Amara aenea/Specimen/Amara aenea 6.v.22.jpg", observation_id=2)
    pl.add_link(c, f"{L}/Amara aenea/Amara aenea - field.jpg", observation_id=2)
    c.commit()
    c.close()
    res = pf.follow_redet(str(db), "observation", 2, "Amara aenea", "Amara curta")
    left = dict(res.left)
    assert left[f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg"] == "linked to another record too"
    assert left[f"{L}/Amara aenea/Specimen/Amara aenea 6.v.22.jpg"] == "new name already taken"
    # a field photo with no species folder yet: a new folder beside the old one
    assert res.moved == [(f"{L}/Amara aenea/Amara aenea - field.jpg", f"{L}/Amara curta/Amara curta - field.jpg")]
    assert (root / L / "Amara curta/Specimen/Amara curta 6.v.22.jpg").read_bytes().endswith(b"curta 6.v.22.jpg")


def test_observation_redet_waits_for_its_specimen(tmp_path, monkeypatch):
    _lib(tmp_path, monkeypatch, [f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg"])
    db = tmp_path / "o.db"
    c = _db(db)
    pl.ensure_schema(c)
    pl.add_link(c, f"{L}/Amara aenea/Specimen/Amara aenea 5.v.22.jpg", specimen_id=10)   # obs 1's specimen
    c.commit()
    c.close()
    res = pf.follow_redet(str(db), "observation", 1, "Amara aenea", "Amara ovata")
    assert res.moved == [] and res.left[0][1] == "its specimen still has the old name"
    assert pf.follow_redet(str(db), "observation", 1, "Amara aenea", "Amara aenea") is None


def test_no_table_or_bad_db_never_raises(tmp_path, monkeypatch):
    _lib(tmp_path, monkeypatch, [])
    db = tmp_path / "o.db"
    _db(db).close()
    assert pf.follow_redet(str(db), "specimen", 11, "Amara aenea", "Amara ovata") is None
    res = pf.follow_redet(str(tmp_path / "missing" / "x.db"), "specimen", 1, "A b", "C d")
    assert res is not None and "photos not moved" in res.left[0][1]


def test_target_keeps_the_place_under_the_species_and_skips_strays(tmp_path, monkeypatch):
    root = _lib(tmp_path, monkeypatch, [
        f"{L}/Rutpela maculata/2024/Rutpela maculata 1.vi.24.jpg",
        f"{L}/Loose/Rutpela maculata 2.vi.24.jpg"])
    db = tmp_path / "o.db"
    c = _db(db)
    pl.ensure_schema(c)
    pl.add_link(c, f"{L}/Rutpela maculata/2024/Rutpela maculata 1.vi.24.jpg", specimen_id=11)
    pl.add_link(c, f"{L}/Loose/Rutpela maculata 2.vi.24.jpg", specimen_id=11)
    c.commit()
    c.close()
    res = pf.follow_redet(str(db), "specimen", 11, "Rutpela maculata", "Stenurella melanura")
    assert res.moved == [(f"{L}/Rutpela maculata/2024/Rutpela maculata 1.vi.24.jpg",
                          f"{L}/Stenurella melanura/2024/Stenurella melanura 1.vi.24.jpg")]
    assert res.left == [(f"{L}/Loose/Rutpela maculata 2.vi.24.jpg", "not inside a folder named Rutpela maculata")]
    assert (root / L / "Loose/Rutpela maculata 2.vi.24.jpg").is_file()


def test_one_word_names_have_no_species_folder(tmp_path, monkeypatch):
    _lib(tmp_path, monkeypatch, [f"{L}/Amara aenea/a.jpg"])
    assert pf.species_photos("Carabidae") == [] and pf.species_photos("Coleoptera") == []


def test_specimen_edit_sites_read_the_old_name_first(tmp_path):
    db = tmp_path / "o.db"
    _db(db).close()
    assert pf.species_now(str(db), "specimen", 10) == "Amara aenea"
    assert pf.species_now(str(db), "observation", 2) == "Amara aenea"
    assert pf.species_now(str(db), "observation", 99) == ""
    assert pf.species_now(str(tmp_path / "none.db"), "specimen", 1) == ""
