"""Bench photos (14 Oct 2026): the specimen-photo name standard, the rename of old names,
a Data Entry row's photos following it into its record at commit, and one key per record."""
import sqlite3

import paths
from scripts import renumber_duplicate_keys as rk
from scripts import standardise_specimen_names as sn
from shared import photo_files as pf
from shared import photo_links as pl
from shared.photo_names import lower_after_genus, specimen_photo_stem, specimen_stem

L = "Photos/Life/Insecta/Coleoptera/Staphylinidae"


def test_name_standard():
    assert specimen_photo_stem("Amara aenea", "Male", "gen", "2026-06-05") == "Amara aenea male gen 5.vi.26"
    assert specimen_photo_stem("Amara aenea", "not recorded", "", "") == "Amara aenea"
    assert specimen_photo_stem("Drymus sylvaticus", "", "HEAD", "2021-01-02") == "Drymus sylvaticus head 2.i.21"
    assert specimen_stem("Philonthus decorus GEN 16.iv.19") == "Philonthus decorus gen 16.iv.19"
    assert specimen_stem("Bembidion dentellum 5.5cm HEAD 18.11.16") == "Bembidion dentellum 5.5cm head 18.xi.16"
    assert lower_after_genus("Lathrobium fulvipenne GEN (2) 18.ii.16") == "Lathrobium fulvipenne gen (2) 18.ii.16"
    assert lower_after_genus("P1050002 WJH") == "P1050002 WJH"                    # not a species name
    assert lower_after_genus("Philonthus (Philonthus) decorus GEN") == "Philonthus (Philonthus) decorus gen"


def _lib(tmp_path, monkeypatch, files):
    root = tmp_path / "Media"
    for rel in files:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"jpg:" + rel.encode())
    monkeypatch.setattr(paths, "MEDIA_ROOT", root)
    monkeypatch.setattr(paths, "PHOTO_MOVES_DIR", tmp_path / "logs")
    pf.refresh()
    return root


def test_rename_old_names_and_links_follow(tmp_path, monkeypatch):
    root = _lib(tmp_path, monkeypatch, [
        f"{L}/Philonthus decorus/Specimen/Philonthus decorus GEN 16.iv.19.jpg",
        f"{L}/Philonthus decorus/Specimen/Philonthus decorus 16.iv.19.jpg",
        f"{L}/Philonthus decorus/Philonthus decorus - Rove Beetle.jpg"])       # field photo: left
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, species_name TEXT, observation_id INTEGER)")
    pl.ensure_schema(c)
    pl.add_link(c, f"{L}/Philonthus decorus/Specimen/Philonthus decorus GEN 16.iv.19.jpg", specimen_id=1)
    c.commit()
    c.close()
    args = ["--root", str(root), "--db", str(db), "--backup-dir", str(tmp_path / "bk")]
    assert sn.main(args) == 0
    assert (root / L / "Philonthus decorus/Specimen/Philonthus decorus GEN 16.iv.19.jpg").is_file()  # dry run
    assert sn.main(args + ["--apply"]) == 0
    files = sorted(p.name for p in (root / L / "Philonthus decorus").rglob("*.jpg"))
    assert files == ["Philonthus decorus - Rove Beetle.jpg", "Philonthus decorus 16.iv.19.jpg",
                     "Philonthus decorus gen 16.iv.19.jpg"]
    c = sqlite3.connect(db)
    assert pl.photos_for_specimen(c, 1) == [f"{L}/Philonthus decorus/Specimen/Philonthus decorus gen 16.iv.19.jpg"]


def test_row_photos_become_the_records_at_commit(tmp_path):
    from DataEntry import staging_repo as repo
    from DataEntry.commit_service import commit_job
    conn = sqlite3.connect(tmp_path / "o.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    pl.ensure_schema(conn)
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    rid = repo.insert_row(conn, jid, {"species_name": "Amara aenea", "date": "05/06/2026",
                                      "quantity": "1", "recorder": "Heeney, W.J."})
    pl.add_staging_link(conn, "Photos/Life/x/Specimen/Amara aenea gen 5.vi.26.jpg", rid)
    conn.commit()
    assert pl.staging_counts(conn, [rid]) == {rid: 1}

    class Obs:
        def __init__(self, **kw):
            pass

    class Model:
        def create(self, o):
            return 77

    class Db:
        def execute_main_write(self, sql, params):
            return 1

    s = commit_job(Db(), Model(), conn, repo.get_job(conn, jid), observation_cls=Obs, taxonomy={})
    assert s["committed"] == 1
    conn.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, observation_id INTEGER)")
    assert pl.photos_for_observation(conn, 77) == ["Photos/Life/x/Specimen/Amara aenea gen 5.vi.26.jpg"]
    assert pl.photos_for_staging(conn, rid) == []


def test_old_photo_links_table_gets_the_staging_column(tmp_path):
    c = sqlite3.connect(tmp_path / "o.db")
    c.execute("CREATE TABLE photo_links (id INTEGER PRIMARY KEY, photo_path TEXT NOT NULL, specimen_id "
              "INTEGER, observation_id INTEGER, method TEXT, created_at TEXT, "
              "UNIQUE(photo_path, specimen_id, observation_id))")
    assert not pl.has_staging_column(c)
    assert pl.ensure_schema(c) is True and pl.has_staging_column(c)
    assert pl.ensure_schema(c) is False


def test_renumber_gives_every_record_its_own_key(tmp_path):
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, observatum_key TEXT, external_key TEXT)")
    c.executemany("INSERT INTO observations VALUES (?,?,?)", [
        (1, "OBS-WJH-20260325-10001", None), (2, "OBS-WJH-20260325-10001", None),
        (3, "OBS-WJH-20260325-10001", "OBS-WJH-20260325-10001"),            # its iRecord key: left
        (4, "OBS-WJH-20260325-0005", None), (5, "uuid-a", "uuid-a"), (6, "uuid-a", "uuid-a")])
    c.commit()
    c.close()
    args = ["--db", str(db), "--backup-dir", str(tmp_path / "bk"), "--csv", str(tmp_path / "r.csv")]
    assert rk.main(args) == 0
    assert rk.main(args + ["--apply"]) == 0
    c = sqlite3.connect(db)
    keys = dict(c.execute("SELECT id, observatum_key FROM observations"))
    assert keys[3] == "OBS-WJH-20260325-10001"         # its iRecord External key: it keeps it
    assert len({keys[1], keys[2], keys[3]}) == 3 and keys[1].startswith("OBS-WJH-")
    assert keys[5] == keys[6] == "uuid-a"                                 # iRecord app keys untouched
    assert len(list((tmp_path / "bk").iterdir())) == 1
