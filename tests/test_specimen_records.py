"""Records from specimens (14 Oct 2026): specimens with no field record become Data Entry rows
(shared/specimen_records.py); committing a row links its specimens to the new record and
deleting it lets them go (shared/specimen_staging.py); scripts/stage_records_from_specimens.py
sorts them by the 12 Oct rules."""
import sqlite3

import pytest

from shared import specimen_records as sr
from shared import specimen_staging as ss

SPEC_COLS = ("id INTEGER PRIMARY KEY, specimen_code TEXT, species_name TEXT, species_tvk TEXT, "
             "common_name TEXT, order_name TEXT, family TEXT, date_collected TEXT, grid_ref TEXT, "
             "site_name TEXT, collector TEXT, determiner TEXT, sex TEXT, observation_id INTEGER, "
             "no_field_record_checked INTEGER, updated_at TEXT")
OBS_COLS = ("id INTEGER PRIMARY KEY, species_tvk TEXT, species_name TEXT, date TEXT, grid_ref TEXT, "
            "recorder TEXT, site_name TEXT, record_type TEXT, project_name TEXT, client TEXT, "
            "embargo_status TEXT, embargo_until TEXT, sex TEXT, quantity INTEGER")
WIL = "Heeney, W.J."


@pytest.fixture
def db(tmp_path):
    from DataEntry import staging_repo as repo
    path = tmp_path / "observatum.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(f"CREATE TABLE specimens ({SPEC_COLS})")
    conn.execute(f"CREATE TABLE observations ({OBS_COLS})")
    repo.ensure_schema(conn)
    yield path, conn, repo
    conn.close()


def _spec(conn, sid, name="Amara aenea", tvk="T1", date="2024-06-05", ref="SP5000050000",
          sex="Male", obs=None, collector=WIL, site="Wood"):
    conn.execute("INSERT INTO specimens (id, specimen_code, species_name, species_tvk, order_name, "
                 "family, date_collected, grid_ref, site_name, collector, determiner, sex, "
                 "observation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (sid, f"C{sid}", name, tvk, "Coleoptera", "Carabidae", date, ref, site,
                  collector, WIL, sex, obs))


def test_stage_makes_one_row_and_remembers_the_specimens(db):
    _path, conn, repo = db
    _spec(conn, 1)
    _spec(conn, 2, sex="Female")
    _spec(conn, 3, obs=50)                        # already has a field record: left out
    jid = sr.find_or_make_job(conn, "Personal")
    assert sr.find_or_make_job(conn, "Personal") == jid
    rid = sr.stage(conn, jid, [1, 2, 3])
    conn.commit()
    row = repo.fetch_rows(conn, jid)[0]
    assert row["id"] == rid and row["quantity"] == 2 and row["species_tvk"] == "T1"
    assert row["date"] == "2024-06-05" and row["recorder"] == WIL and row["sex"] is None
    assert "count is a minimum" in row["comment"] and "1 female" in row["comment"]
    assert ss.for_row(conn, rid) == [1, 2]
    assert sr.stage(conn, jid, [1, 2]) is None    # already on a row


def test_commercial_job_takes_the_year_terms(db):
    _path, conn, repo = db
    jid = sr.find_or_make_job(conn, "Commercial", "Site X", {"client": "C", "embargo_until": "2028-01-03"}, "2025")
    job = repo.get_job(conn, jid)
    assert job["name"] == "Site X 2025: records from specimens" and job["mode"] == "Commercial"
    assert job["project"] == "Site X" and job["client"] == "C" and job["embargo_until"] == "2028-01-03"
    assert sr.find_or_make_job(conn, "season", "Site X", {}, "2025") != jid


def test_commit_links_the_specimens(db):
    _path, conn, repo = db
    from DataEntry.commit_service import commit_job
    _spec(conn, 1)
    _spec(conn, 2)
    jid = sr.find_or_make_job(conn, "Personal")
    sr.stage(conn, jid, [1, 2])
    conn.commit()

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
    assert [r[0] for r in conn.execute("SELECT observation_id FROM specimens ORDER BY id")] == [91, 91]
    assert ss.staged(conn) == {}


def test_deleted_row_lets_the_specimens_go(db):
    _path, conn, repo = db
    _spec(conn, 1)
    jid = sr.find_or_make_job(conn, "Personal")
    rid = sr.stage(conn, jid, [1])
    conn.commit()
    repo.delete_row(conn, rid)
    assert ss.staged(conn) == {}
    assert conn.execute("SELECT observation_id FROM specimens").fetchone()[0] is None
    assert sr.stage(conn, jid, [1]) is not None   # free again


def test_script_plan_and_apply(db, tmp_path, capsys):
    path, conn, _repo = db
    from scripts import stage_records_from_specimens as st
    # Personal visit: Wil recorded another beetle there that day
    conn.execute("INSERT INTO observations (id, species_tvk, species_name, date, grid_ref, recorder, "
                 "site_name, record_type) VALUES (1, 'X9', 'Carabus nemoralis', '2024-06-05', "
                 "'SP5000050000', ?, 'Wood', 'Personal')", (WIL,))
    _spec(conn, 1)
    _spec(conn, 2)
    # Commercial visit (2025, embargoed)
    conn.execute("INSERT INTO observations (id, species_tvk, species_name, date, grid_ref, recorder, "
                 "site_name, record_type, project_name, client, embargo_status, embargo_until) "
                 "VALUES (2, 'X9', 'Carabus nemoralis', '2025-07-01', 'TQ3000030000', ?, 'Farm', "
                 "'Commercial', 'Farm Survey', 'Client A', 'Active', '2028-01-03')", (WIL,))
    _spec(conn, 3, name="Nebria brevicollis", tvk="T2", date="2025-07-01", ref="TQ3000030000", site="Farm")
    # nothing anywhere near: held (Q24)
    _spec(conn, 4, name="Pterostichus niger", tvk="T3", date="2023-05-01", ref="NZ1000010000", site="Moor")
    # someone else's: not staged here
    _spec(conn, 5, collector="Lamin, J.")
    conn.commit()

    assert st.main(["--db", str(path), "--uksi", str(tmp_path / "none.db"),
                    "--csv", str(tmp_path / "plan.csv")]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN. Nothing has been changed." in out
    assert conn.execute("SELECT COUNT(*) FROM entry_staging").fetchone()[0] == 0

    assert st.main(["--apply", "--db", str(path), "--uksi", str(tmp_path / "none.db"),
                    "--csv", str(tmp_path / "plan.csv"), "--backup-dir", str(tmp_path / "bk")]) == 0
    assert len(list((tmp_path / "bk").iterdir())) == 1
    rows = {r["name"]: (r["n"], r["embargo_until"]) for r in conn.execute(
        "SELECT j.name, j.embargo_until, COUNT(s.id) n FROM entry_jobs j "
        "JOIN entry_staging s ON s.job_id = j.id GROUP BY j.id")}
    assert rows == {"Records from specimens": (1, None),
                    "Farm Survey 2025: records from specimens": (1, "2028-01-03")}
    assert sorted(ss.staged(conn)) == [1, 2, 3]

    assert st.main(["--db", str(path), "--uksi", str(tmp_path / "none.db"),
                    "--csv", str(tmp_path / "plan2.csv")]) == 0
    out = capsys.readouterr().out
    assert "already on a Data Entry row" in out and "unknown Personal/Commercial" in out


def test_apply_refuses_another_database(db, tmp_path):
    _path, conn, _repo = db
    from scripts import stage_records_from_specimens as st
    other = tmp_path / "copy.db"
    conn.execute(f"VACUUM INTO '{other}'")
    assert st.main(["--apply", "--db", str(other), "--uksi", str(tmp_path / "none.db"),
                    "--csv", str(tmp_path / "p.csv"), "--backup-dir", str(tmp_path / "bk")]) == 2


def test_fill_sort_keys_from_the_final_species(tmp_path):
    """F34: imports take the final species' sort key, superfamily and subfamily."""
    from types import SimpleNamespace
    from shared.import_core import fill_sort_keys
    u = tmp_path / "uksi.db"
    c = sqlite3.connect(u)
    c.execute('CREATE TABLE taxa (tvk TEXT, sort_code INTEGER, "order" TEXT, superfamily TEXT, '
              'family TEXT, parent_tvk TEXT, rank TEXT, scientific_name TEXT)')
    c.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?)", [
        ("SF", 0, "Coleoptera", "Caraboidea", "Carabidae", None, "Subfamily", "Harpalinae"),
        ("G", 0, "Coleoptera", "Caraboidea", "Carabidae", "SF", "Genus", "Amara"),
        ("SP", 1234, "Coleoptera", "Caraboidea", "Carabidae", "G", "Species", "Amara aenea")])
    c.commit()
    c.close()
    rows = [SimpleNamespace(species_tvk="SP", taxonomic_sort_key=None, superfamily="", subfamily=""),
            SimpleNamespace(species_tvk="NOPE", taxonomic_sort_key=7, superfamily="x", subfamily="")]
    assert fill_sort_keys(rows, u) == 1
    assert rows[0].taxonomic_sort_key and rows[0].superfamily == "Caraboidea"
    assert rows[0].subfamily == "Harpalinae"
    assert (rows[1].taxonomic_sort_key, rows[1].superfamily) == (7, "x")
    assert fill_sort_keys(rows, tmp_path / "missing" / "u.db") == 0     # failure: rows left


def test_review_fixes_vc_project_name_and_staged_guards(db, tmp_path):
    """Review 14 Oct: the row carries the specimens' VC; a Commercial job keeps the project
    name exactly as stored; a staged specimen can't be linked or re-dated; one date per visit."""
    path, conn, repo = db
    conn.execute("ALTER TABLE specimens ADD COLUMN vice_county TEXT")
    conn.execute("ALTER TABLE specimens ADD COLUMN vc_number INTEGER")
    _spec(conn, 1)
    conn.execute("UPDATE specimens SET vice_county='Oxfordshire', vc_number=23")
    jid = sr.find_or_make_job(conn, "Commercial", "Derby", {"project_name": "Derby ", "client": "C"}, "2025")
    assert repo.get_job(conn, jid)["project"] == "Derby "
    rid = sr.stage(conn, jid, [1])
    row = repo.fetch_rows(conn, jid)[0]
    assert (row["id"], row["vice_county"], row["vc_number"]) == (rid, "Oxfordshire", 23)

    from shared import specimens_to_check as stc
    assert stc.link(path, 1, 99) == 0
    assert stc.change_date(path, [1], "2024-06-06") == 0
    assert conn.execute("SELECT observation_id, date_collected FROM specimens").fetchone()[:] == (None, "2024-06-05")
    assert "more than one date" in stc.visit_problem([{"site_name": "W", "grid_ref": "SP50", "date_collected": "2024-06-05"},
                                                     {"site_name": "W", "grid_ref": "SP50", "date_collected": "2024-06-07"}])


def test_irish_gps_gives_no_grid_ref():
    from shared.photo_intake import grid_ref
    assert grid_ref(54.597, -5.930) is None          # Belfast
    assert grid_ref(53.35, -6.26) is None            # Dublin
    assert grid_ref(55.30, -5.80)                    # Kintyre
    assert grid_ref(51.5007, -0.1246) == "TQ302796"  # Big Ben


def test_held_while_its_survey_is_still_in_data_entry(db, tmp_path, capsys):
    """A find that may be a record still being entered in Data Entry is held: the same species
    within a week, or a Commercial job's rows within 2 km and 30 days (any species)."""
    path, conn, repo = db
    from scripts import stage_records_from_specimens as st
    conn.execute("INSERT INTO observations (id, species_tvk, species_name, date, grid_ref, recorder, "
                 "site_name, record_type) VALUES (1, 'X9', 'Carabus nemoralis', '2024-06-05', "
                 "'SP5000050000', ?, 'Wood', 'Personal')", (WIL,))
    _spec(conn, 1)                                                  # same species in a Personal job
    _spec(conn, 2, name="Nebria brevicollis", tvk="T2")             # near an open survey
    conn.execute("INSERT INTO observations (id, species_tvk, species_name, date, grid_ref, recorder, "
                 "site_name, record_type) VALUES (2, 'X9', 'Carabus nemoralis', '2024-08-20', "
                 "'SP5000050000', ?, 'Wood', 'Personal')", (WIL,))
    _spec(conn, 3, name="Pterostichus niger", tvk="T3", date="2024-08-20")   # > 30 days: stays Personal
    pj = repo.create_job(conn, "Me", "Personal")
    repo.insert_row(conn, pj, {"species_tvk": "T1", "species_name": "Amara aenea", "date": "06/06/2024"})
    sj = repo.create_job(conn, "Notts", "Commercial", "C", "NBP")
    repo.insert_row(conn, sj, {"species_tvk": "Z", "species_name": "Other", "date": "20/06/2024",
                               "grid_ref": "SP5050050500"})
    conn.commit()
    assert st.main(["--db", str(path), "--uksi", str(tmp_path / "none.db"),
                    "--csv", str(tmp_path / "plan.csv")]) == 0
    out = capsys.readouterr().out
    assert "same species in Data Entry, not yet committed (Me)" in out
    assert "near a survey still being entered in Data Entry (Notts)" in out
    assert "stage: 1 records" in out


def test_undo_takes_out_only_the_jobs_it_made(db, tmp_path, capsys):
    path, conn, repo = db
    from scripts import stage_records_from_specimens as st
    _spec(conn, 1)
    _spec(conn, 2, name="Nebria brevicollis", tvk="T2")
    jid = sr.find_or_make_job(conn, "Personal")
    sr.stage(conn, jid, [1])
    mixed = repo.create_job(conn, "Records from specimens", "Commercial", "C", "P")   # same name, own row
    sr.stage(conn, mixed, [2])
    repo.insert_row(conn, mixed, {"species_name": "Wil's own row"})
    own = repo.create_job(conn, "Hook", "Commercial", "C", "Hook")
    repo.insert_row(conn, own, {"species_name": "Amara aenea"})
    conn.commit()
    args = ["--undo", "--db", str(path), "--backup-dir", str(tmp_path / "bk")]
    assert st.main(args) == 0 and "1 rows in 1 job(s)" in capsys.readouterr().out
    assert len(ss.staged(conn)) == 2                         # dry run: nothing changed
    assert st.main(args + ["--apply"]) == 0
    assert len(list((tmp_path / "bk").iterdir())) == 1
    assert sorted(ss.staged(conn)) == [2]                    # the mixed job is left alone
    assert repo.get_job(conn, jid)["status"] == "discarded" and repo.fetch_rows(conn, jid) == []
    assert len(repo.fetch_rows(conn, own)) == 1 and len(repo.fetch_rows(conn, mixed)) == 2
