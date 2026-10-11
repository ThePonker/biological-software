"""Round 2 (10 Oct 2026) report and data scripts, on small throwaway databases:
scheme duplicates (L12), iRecord-format sort keys (decision 6), tetrad mapping (decision 10),
specimen <-> observation links (decision 13) and the commercial embargo list (decision 14)."""
import csv
import hashlib
import importlib.util
import os
import sqlite3

import pytest

from scripts import link_specimens_to_observations as link_script
from scripts import report_commercial_embargo as emb
from scripts import report_common as rc
from scripts import report_scheme_duplicates as dup
from scripts import report_specimen_observation_links as links
from scripts import report_tetrad_mapping as tet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- report_common

def test_people_and_refs():
    assert rc.same_person("Heeney, W.J.", "Wil Heeney")
    assert rc.same_person("Heeney, Wil. Lamin, John", "Lamin, J.")
    assert not rc.same_person("Falk, S.J.", "Heeney, W.J.")
    assert not rc.comparable_people("Heeney, W.J.", "Collected")
    assert not rc.comparable_people("Heeney, W.J.", "")
    assert rc.comparable_people("Hand, Jane", "Heeney, W.J.")      # 'Hand' is a surname
    assert rc.norm_ref("sp 123 456") == "SP123456"


# ---------------------------------------------------------------- scheme duplicates

SCHEME_COLS = ("id", "irecord_id", "nbn_atlas_id", "occurrence_id", "source", "dataset_name",
               "species_name", "species_tvk", "date", "grid_ref", "site_name", "recorder")


@pytest.fixture
def scheme_db(tmp_path):
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.execute(f"CREATE TABLE recording_scheme ({', '.join(SCHEME_COLS)})")
    rows = [
        # an iRecord record and its NBN Atlas copy (blurred grid ref, no recorder)
        (1, 100, None, None, "iRecord | iRecord beetles", None, "Rutpela maculata", "T1",
         "2020-06-01", "SP58022070", "[sensitive record, location hidden]", "Smith, J."),
        (2, None, "uuid-2", "100", "Longhorn data from iRecord", "Longhorn data from iRecord",
         "Rutpela maculata", "T1", "2020-06-01", "SP52", "Wood", None),
        # an NBN row whose occurrence id collides with an iRecord id but is another record
        (3, None, "uuid-3", "100", "Other dataset", "Other dataset", "Clytus arietis", "T2",
         "1999-05-01", "TQ12", None, None),
        # the same record twice in iRecord, same recorder -> exact
        (4, 200, None, None, "iRecord | iRecord App", None, "Clytus arietis", "T2",
         "2021-05-05", "SU1234", None, "Jones, A."),
        (5, 201, None, None, "iRecord | iRecord App", None, "Clytus arietis", "T2",
         "2021-05-05", "su 12 34", None, "jones,  a"),
        # an NBN row without a recorder, same species, date and grid ref -> likely
        (6, None, "uuid-6", "999", "County data", "County data", "Clytus arietis", "T2",
         "2021-05-05", "SU1234", None, None),
        # two different recorders -> possible
        (7, 300, None, None, "iRecord | iRecord App", None, "Tetrops praeustus", "T3",
         "2022-05-05", "TL1111", None, "Brown, B."),
        (8, 301, None, None, "iRecord | iRecord App", None, "Tetrops praeustus", "T3",
         "2022-05-05", "TL1111", None, "Green, C."),
        # not compared: no date
        (9, None, "uuid-9", None, "x", "x", "Tetrops praeustus", "T3", None, "TL1111", None, None),
    ]
    c.executemany(f"INSERT INTO recording_scheme VALUES ({','.join('?' * len(SCHEME_COLS))})", rows)
    c.commit()
    c.close()
    return p


def test_scheme_duplicate_tiers(scheme_db):
    conn = rc.connect_ro(scheme_db)
    rows = dup.load(conn)
    conn.close()
    pairs = dup.find_pairs(rows)
    tiers = {k: v[0] for k, v in pairs.items()}
    assert tiers[(1, 2)] == "same iRecord id"
    assert (1, 3) not in tiers                         # id collision, different species
    assert tiers[(4, 5)] == "exact"                    # recorder spelling folded
    assert tiers[(4, 6)] == "likely" and tiers[(5, 6)] == "likely"
    assert tiers[(7, 8)] == "possible"
    assert len(pairs) == 5
    s = dup.summarise(rows, pairs)
    assert s["not_compared"] == 1
    # copies, cumulative: 2 (id) ; +5 (exact) ; +6 (likely) ; +8 (possible)
    assert [s["copies"][t] for t in dup.TIERS] == [1, 2, 3, 4]


def test_scheme_duplicates_main_read_only(scheme_db, tmp_path, capsys):
    before = _md5(scheme_db)
    out = tmp_path / "d.csv"
    assert dup.main(["--db", str(scheme_db), "--csv", str(out)]) == 0
    assert _md5(scheme_db) == before
    text = capsys.readouterr().out
    assert "Nothing has been changed." in text
    got = _csv(out)
    assert len(got) == 5
    first = got[0]
    assert first["tier"] == "same iRecord id"
    assert (first["id_a"], first["id_b"], first["route_a"], first["route_b"]) == \
        ("1", "2", "iRecord", "NBN Atlas")
    assert first["irecord_id_a"] == "100" and first["occurrence_id_b"] == "100"


# ---------------------------------------------------------------- sort keys (one-off)

def _load_oneoff(name):
    path = os.path.join(ROOT, "scripts", "_oneoff", name)
    if not os.path.exists(path):
        pytest.skip(f"{name} archived")
    spec = importlib.util.spec_from_file_location(name[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def sort_dbs(tmp_path):
    u = sqlite3.connect(tmp_path / "uksi.db")
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              '"order" TEXT, family TEXT, sort_code INTEGER, superfamily TEXT)')
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?)", [
        ("F1", "Ficaria verna", "Species", None, "Ranunculales", "Ranunculaceae", 109890, None),
        ("B1", "Sepedophilus testaceus", "Species", None, "Coleoptera", "Staphylinidae", 17478,
         "Staphylinoidea"),
    ])
    u.execute("CREATE TABLE tvk_remap (old_tvk, new_tvk, method, old_name, new_name)")
    u.execute("INSERT INTO tvk_remap VALUES ('OLD', 'B1', 'name_map', 'x', 'Sepedophilus testaceus')")
    u.commit()
    u.close()
    o = sqlite3.connect(tmp_path / "observatum.db")
    o.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, "
              "species_tvk TEXT, source TEXT, irecord_id INTEGER, taxonomic_sort_key)")
    key = "000204040N051J040C01000000000000000000000000000000"
    o.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", [
        (1, "Ficaria verna", "F1", "iRecord", 11, key),
        (2, "Sepedophilus testaceus", "B1", "iRecord", 12,
         "0002040106030306030102050L0B0C00000000000000000000"),
        (3, "Ficaria verna", "F1", None, None, 99109890),          # ours: untouched
        (4, "Ficaria verna", "F1", None, None, None),              # blank: untouched
        (5, "Something", "OLD", "iRecord", 13, key),               # TVK not in UKSI: left
        (6, "Ficaria verna", "F1", None, None, "odd text"),        # not iRecord's format: left
    ])
    o.commit()
    o.close()
    return tmp_path / "observatum.db", tmp_path / "uksi.db"


def test_sort_key_plan_and_apply(sort_dbs, tmp_path, capsys):
    m = _load_oneoff("fix_irecord_format_sort_keys_20261010.py")
    db, uksi = sort_dbs
    before = _md5(db)
    out = tmp_path / "k.csv"
    assert m.main(["--db", str(db), "--uksi", str(uksi), "--csv", str(out)]) == 0
    text = capsys.readouterr().out
    assert "DRY RUN. Nothing has been changed." in text
    assert "iRecord-format keys to recompute from the TVK: 2" in text
    assert "remap_record_tvks.py" in text
    assert _md5(db) == before
    assert len(_csv(out)) == 4

    bdir = tmp_path / "bk"
    assert m.main(["--db", str(db), "--uksi", str(uksi), "--csv", str(out), "--apply",
                   "--backup-dir", str(bdir)]) == 0
    assert len(os.listdir(bdir)) == 1
    c = sqlite3.connect(db)
    got = dict(c.execute("SELECT id, taxonomic_sort_key FROM observations"))
    c.close()
    from Observatum.src.utils.constants import compute_taxonomic_sort_key
    assert got[1] == compute_taxonomic_sort_key("Ranunculales", 109890) == 99109890
    assert got[2] == compute_taxonomic_sort_key("Coleoptera", 17478) == 19017478
    assert got[3] == 99109890 and got[4] is None
    assert got[5].startswith("0002") and got[6] == "odd text"


# ---------------------------------------------------------------- tetrads

def test_tetrad_new_squares():
    data = {"recording_scheme": [
        ("A", "Species A", "SP46Q"),       # tetrad
        ("A", "Species A", "SP4060"),      # 1 km in SP46A: same hectad, different tetrad
        ("A", "Species A", "SP46A"),       # tetrad, already occupied by the 1 km record
        ("B", "Species B", "SP46Q"),       # tetrad only: new tetrad and new hectad
        ("C", "Species C", "TL11"),        # hectad record only
        ("C", "Species C", "TL11A"),       # tetrad: hectad not new, tetrad new
    ], "observations": [
        ("B", "Species B", "SP469699"),    # in SP46 (tetrad U), not in Q
    ]}
    res = tet.analyse(data)
    r = res["tables"]["recording_scheme"]
    assert r["A"]["records"] == 2 and r["A"]["tetrads"] == {"SP46Q", "SP46A"}
    assert r["A"]["new_t"] == {"SP46Q"} and r["A"]["new_h"] == set()
    assert r["B"]["new_t"] == {"SP46Q"} and r["B"]["new_h"] == {"SP46"}
    # with every source together, B's observation at SP469699 already holds SP46 and its tetrad
    from shared.maps.grid_squares import TETRAD, square_for_ref
    obs_tetrad = square_for_ref("SP469699", TETRAD)
    assert r["B"]["new_h_all"] == set()
    assert r["B"]["new_t_all"] == ({"SP46Q"} - {obs_tetrad})
    assert r["C"]["new_h"] == set() and r["C"]["new_t"] == {"TL11A"}
    assert res["vc_dropped"] == 4                       # the old parser reads no tetrad


def test_tetrad_main_read_only(scheme_db, tmp_path, capsys):
    c = sqlite3.connect(scheme_db)
    c.execute("UPDATE recording_scheme SET grid_ref = 'SP46Q' WHERE id = 9")
    c.commit()
    c.close()
    before = _md5(scheme_db)
    out = tmp_path / "t.csv"
    assert tet.main(["--db", str(scheme_db), "--csv", str(out)]) == 0
    assert _md5(scheme_db) == before
    assert "READ ONLY. Nothing has been changed." in capsys.readouterr().out
    rows = _csv(out)
    assert len(rows) == 1 and rows[0]["species_tvk"] == "T3" and rows[0]["new_hectads"] == "1"


# ---------------------------------------------------------------- specimen links

@pytest.fixture
def link_db(tmp_path):
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_tvk, date, grid_ref, "
              "recorder, record_type, project_name, site_name, sex, quantity)")
    c.execute("CREATE TABLE specimens (id INTEGER PRIMARY KEY, specimen_code, species_name, "
              "species_tvk, date_collected, grid_ref, collector, site_name, observation_id, sex)")
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (1, "T1", "2025-06-01", "SP123456", "Heeney, Wil", "Personal", None, "A", None, 1),
        (2, "T2", "2025-06-01", "SP123456", "Heeney, W.J.", "Personal", None, "A", None, 1),
        (3, "T2", "2025-06-01", "SP123456", "Wil Heeney", "Personal", None, "A", None, 1),
        (4, "T3", "2025-06-01", "SP123456", "Heeney, W.J.", "Commercial", "P", "A", None, 1),
        (5, "T4", "2025-06-01", "SP123456", "Collected", "Personal", None, "A", None, 1),
        (6, "T5", "2025-06-01", "SP123456", "Heeney, W.J.", "Personal", None, "A", None, 1),
        (7, "T6", "2025-06-01", "SP123456", "Heeney, W.J.", "Personal", None, "A", None, 2),
    ])
    c.executemany("INSERT INTO specimens VALUES (?,?,?,?,?,?,?,?,?,?)", [
        (1, None, "a", "T1", "2025-06-01", "sp 123 456", "Heeney, W.J.", "A", None, None),  # certain
        (2, None, "b", "T2", "2025-06-01", "SP123456", "Heeney, W.J.", "A", None, None),    # ambiguous
        (3, None, "c", "T3", "2025-06-01", "SP123456", "Falk, S.J.", "A", None, None),      # differs
        (4, None, "d", "T4", "2025-06-01", "SP123456", "Heeney, W.J.", "A", None, None),    # certain
        (5, None, "e", "T5", "2025-06-01", "SP123456", "Heeney, W.J.", "A", None, None),    # qty short
        (6, None, "e", "T5", "2025-06-01", "SP123456", "Heeney, W.J.", "A", None, None),    # qty short
        (7, None, "f", "T6", "2025-06-01", "SP123456", "Heeney, W.J.", "A", None, None),    # certain
        (8, None, "f", "T6", "2025-06-01", "SP123456", "Heeney, W.J.", "A", None, None),    # certain
        (9, None, "g", "T9", "2025-06-01", "SP123456", "Heeney, W.J.", "A", None, None),    # none
        (10, None, "a", "T1", "2025-06-01", "SP123456", "Heeney, W.J.", "A", 1, None),      # linked
    ])
    c.commit()
    c.close()
    return p


def test_specimen_match_tiers(link_db):
    conn = rc.connect_ro(link_db)
    found = links.match(*links.load(conn))
    conn.close()
    tier = {s["id"]: s["tier"] for s in found["specimens"]}
    assert tier == {1: "certain", 2: "ambiguous", 3: "recorder differs", 4: "certain",
                    5: "quantity short", 6: "quantity short", 7: "certain", 8: "certain",
                    9: "no match", 10: "linked"}
    assert found["rule"] == 9 and found["raw_text"] == 8   # 'sp 123 456' only by the rule
    assert sorted(links.certain_links(found)) == [(1, 1), (4, 5), (7, 7), (8, 7)]


def test_link_dry_run_and_apply(link_db, tmp_path, capsys):
    before = _md5(link_db)
    assert link_script.main(["--db", str(link_db)]) == 0
    assert "DRY RUN. Nothing has been changed." in capsys.readouterr().out
    assert _md5(link_db) == before
    bdir = tmp_path / "bk"
    assert link_script.main(["--db", str(link_db), "--apply", "--backup-dir", str(bdir)]) == 0
    assert len(os.listdir(bdir)) == 1
    c = sqlite3.connect(link_db)
    got = dict(c.execute("SELECT id, observation_id FROM specimens"))
    c.close()
    assert got == {1: 1, 2: None, 3: None, 4: 5, 5: None, 6: None, 7: 7, 8: 7, 9: None, 10: 1}


# ---------------------------------------------------------------- commercial embargo

def test_commercial_embargo(tmp_path, capsys):
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, record_type, project_name, "
              "client, embargo_status, embargo_until, date)")
    c.executemany("INSERT INTO observations (record_type, project_name, client, embargo_status, "
                  "embargo_until, date) VALUES (?,?,?,?,?,?)", [
                      ("Commercial", "Bicester", "W", "Active", "2028-01-03", "2025-06-01"),
                      ("Commercial", "Bicester", "W", None, None, "2023-06-01"),
                      ("Commercial", "Derby ", "AJ", "Active", "2026-01-01", "2025-06-01"),
                      ("Commercial", "Elmley", "RW", None, None, "2026-05-18"),
                      ("commercial", "Elmley", "RW", None, None, "2026-06-19"),
                      ("Personal", None, None, None, None, "2026-06-19"),
                  ])
    c.commit()
    c.close()
    before = _md5(p)
    out = tmp_path / "e.csv"
    assert emb.main(["--db", str(p), "--csv", str(out), "--today", "2026-10-10"]) == 0
    assert _md5(p) == before
    text = capsys.readouterr().out
    assert "READ ONLY. Nothing has been changed." in text
    assert "not embargoed: 4 = no embargo set 3 + embargo date passed 1 + other status 0" in text
    assert "unembargoed by choice (Elmley): 2; for Wil to decide: 2" in text
    assert "the review counted 1,226" in text
    rows = {r["project"]: r for r in _csv(out)}
    assert rows["Bicester"]["note"] == "mixed" and rows["Bicester"]["embargoed"] == "1"
    assert rows["Elmley"]["note"] == "unembargoed by choice"
    assert rows["Elmley"]["records"] == "2" and rows["Elmley"]["earliest_date"] == "2026-05-18"
    assert "name stored with spaces" in rows["Derby"]["note"]
    assert emb.classify("Active", "2026-10-11", "2026-10-10") == "embargoed"
    assert emb.classify("Active", "2026-10-10", "2026-10-10") == "expired"
