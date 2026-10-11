"""Round 3 (11 Oct 2026): editing the specimen -> field record link.

shared/specimen_links (tiers incl. "checked: no field record", candidates for the chooser),
the column / link / unlink scripts, the Edit Specimen dialog's Field record box, and the
Insect Collection's Obs ID text -- all on small throwaway databases."""
import csv
import hashlib
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from scripts import add_specimen_link_check_column as col_script  # noqa: E402
from scripts import link_specimens_to_observations as link_script  # noqa: E402
from scripts import unlink_specimens_from_observations as unlink_script  # noqa: E402
from shared import specimen_links as sl  # noqa: E402

OBS = ("id INTEGER PRIMARY KEY, species_name, species_tvk, date, grid_ref, site_name, "
       "recorder, quantity, sex, record_type, project_name")
SPEC = ("id INTEGER PRIMARY KEY, specimen_code, species_name, species_tvk, date_collected, "
        "grid_ref, collector, site_name, observation_id, sex, updated_at")


def _md5(p):
    with open(p, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.execute(f"CREATE TABLE observations ({OBS})")
    c.execute(f"CREATE TABLE specimens ({SPEC})")
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        (1, "Aa", "T1", "2025-06-01", "SP123456", "Wood", "Heeney, W.J.", 1, "Male", "Personal", None),
        (2, "Bb", "T2", "2025-06-01", "SP123456", "Wood", "Heeney, W.J.", 1, None, "Personal", None),
        (3, "Bb", "T2", "2025-06-01", "SP123456", "Wood", "Heeney, W.J.", 1, None, "Personal", None),
        (4, "Cc", "T3", "2025-06-01", "SP123456", "Wood", "Heeney, W.J.", 1, None, "Personal", None),
        (5, "Aa", "T1", "2025-06-01", "SP1234", "Field", "Heeney, W.J.", 2, "female", "Personal", None),
        (6, "Aa", "T1", "2024-07-09", "SP123456", "Wood", "Heeney, W.J.", 1, "mixed", "Personal", None),
        (7, "Dd", "T4", "2025-06-01", "SP123456", "Wood", "Heeney, W.J.", 1, None, "Personal", None),
    ])
    c.executemany("INSERT INTO specimens VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        (1, "S1", "Aa", "T1", "2025-06-01", "SP 123 456", "Wil Heeney", "Wood", None, "Male", None),
        (2, "S2", "Bb", "T2", "2025-06-01", "SP123456", "Heeney", "Wood", None, None, None),
        (3, "S3", "Cc", "T3", "2025-06-01", "SP123456", "Heeney", "Wood", None, None, None),
        (4, "S4", "Zz", "T9", "2025-06-01", "SP123456", "Heeney", "Wood", None, None, None),
        (5, "S5", "Dd", "T4", "2025-06-01", "SP123456", "Heeney", "Wood", 7, None, None),
        (6, "S6", "Dd", "T4", "2025-06-01", "SP123456", "Heeney", "Wood", None, None, None),
    ])
    c.commit()
    c.close()
    return p


def _add_column(db):
    c = sqlite3.connect(db)
    c.execute(col_script.ADD_SQL)
    c.commit()
    c.close()


def _tiers(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {s["id"]: s["tier"] for s in sl.match(*sl.load(c))["specimens"]}
    finally:
        c.close()


# ---------------------------------------------------------------- tiers

def test_tiers_without_and_with_check_column(db):
    # 6 would be "certain" on observation 7, but 5 is already linked to it (quantity 1)
    assert _tiers(db) == {1: "certain", 2: "ambiguous", 3: "certain", 4: "no match",
                          5: "linked", 6: "quantity short"}
    _add_column(db)
    c = sqlite3.connect(db)
    c.execute(f"UPDATE specimens SET {sl.CHECK_COLUMN} = '2026-10-11T10:00:00' WHERE id = 3")
    c.commit()
    c.close()
    assert _tiers(db)[3] == "checked: no field record"


# ---------------------------------------------------------------- chooser candidates

def test_candidates_order_counts_and_hints(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    spec = {"id": 1, "species_tvk": "T1", "species_name": "Aa", "date_collected": "2025-06-01",
            "grid_ref": "SP 123 456", "collector": "Wil Heeney", "sex": "Male"}
    same_day = sl.candidates(c, spec)
    assert [r["id"] for r in same_day] == [1, 5]          # same grid ref before the 1 km square
    assert same_day[0]["rule"] and same_day[0]["sex_hint"] == "yes"
    assert same_day[1]["sex_hint"] == "no" and not same_day[1]["same_ref"]
    every = sl.candidates(c, spec, any_date=True)
    assert [r["id"] for r in every] == [1, 5, 6] and every[2]["sex_hint"] == "maybe"
    assert [r["id"] for r in sl.candidates(c, spec, any_date=True, text="field")] == [5]
    # specimens already on an observation are counted (this one left out)
    other = sl.candidates(c, {"id": 6, "species_tvk": "T4", "date_collected": "2025-06-01",
                              "grid_ref": "SP123456"})
    assert [(r["id"], r["linked"]) for r in other] == [(7, 1)]
    assert sl.candidates(c, {"species_tvk": None}) == []
    c.close()


# ---------------------------------------------------------------- scripts

def test_column_script_dry_run_apply_idempotent(db, tmp_path, capsys):
    before = _md5(db)
    assert col_script.main(["--db", str(db)]) == 0
    assert "DRY RUN. Nothing has been changed." in capsys.readouterr().out
    assert _md5(db) == before
    bk = tmp_path / "bk"
    assert col_script.main(["--db", str(db), "--apply", "--backup-dir", str(bk)]) == 0
    assert len(os.listdir(bk)) == 1
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    assert sl.has_check_column(c)
    c.close()
    assert col_script.main(["--db", str(db), "--apply", "--backup-dir", str(bk)]) == 0
    assert "already there" in capsys.readouterr().out
    assert len(os.listdir(bk)) == 1                       # second run: no backup, no change


def test_link_then_unlink_round_trip(db, tmp_path, capsys):
    _add_column(db)
    bk = tmp_path / "bk"
    set_csv = tmp_path / "set.csv"
    assert link_script.main(["--db", str(db), "--apply", "--backup-dir", str(bk),
                             "--csv", str(set_csv)]) == 0
    rows = _csv(set_csv)
    assert sorted((r["specimen_id"], r["observation_id"]) for r in rows) == [("1", "1"), ("3", "4")]
    c = sqlite3.connect(db)
    c.execute("UPDATE specimens SET observation_id = 2 WHERE id = 3")   # changed by hand since
    c.commit()
    c.close()
    before = _md5(db)
    assert unlink_script.main(["--db", str(db), "--csv", str(set_csv)]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN. Nothing has been changed." in out and "specimen 3: now observation 2" in out
    assert _md5(db) == before
    assert unlink_script.main(["--db", str(db), "--csv", str(set_csv), "--apply",
                               "--backup-dir", str(bk), "--out", str(tmp_path / "rm.csv")]) == 0
    c = sqlite3.connect(db)
    got = dict(c.execute("SELECT id, observation_id FROM specimens"))
    c.close()
    assert got == {1: None, 2: None, 3: 2, 4: None, 5: 7, 6: None}
    assert unlink_script.main(["--db", str(db), "--code", "S5", "--id", "3", "--apply",
                               "--backup-dir", str(bk), "--out", str(tmp_path / "rm2.csv")]) == 0
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(observation_id) FROM specimens").fetchone()[0] == 0
    c.close()
    assert len(os.listdir(bk)) == 3


def test_link_script_skips_checked(db, tmp_path):
    _add_column(db)
    c = sqlite3.connect(db)
    c.execute(f"UPDATE specimens SET {sl.CHECK_COLUMN} = 'x' WHERE id = 1")
    c.commit()
    c.close()
    conn = sqlite3.connect(db)
    done = link_script.apply(conn, [(1, 1), (3, 4)])           # even if asked directly
    conn.close()
    assert done == [(3, 4)]


# ---------------------------------------------------------------- the dialog

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _dialog(db, sid):
    from src.views.dialogs.add_specimen_dialog import AddSpecimenDialog
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    spec = dict(c.execute("SELECT * FROM specimens WHERE id = ?", (sid,)).fetchone())
    c.close()
    return AddSpecimenDialog(None, None, None, existing_specimen=spec, obs_db_path=str(db))


def test_field_record_box_without_column(qapp, db):
    d = _dialog(db, 5)
    box = d.field_record
    assert "observation 7" in box.summary.text() and "Wood" in box.summary.text()
    assert not box.check.isVisibleTo(d) and "add_specimen_link_check_column" in box.hint.text()
    assert "observation_id" not in d.get_specimen_data()     # untouched: link not rewritten
    box.clear_btn.click()
    assert d.get_specimen_data()["observation_id"] is None
    assert sl.CHECK_COLUMN not in d.get_specimen_data()


def test_field_record_box_link_check_clear(qapp, db):
    from src.views.dialogs.field_record_picker import FieldRecordPicker
    _add_column(db)
    d = _dialog(db, 1)
    box = d.field_record
    assert box.summary.text() == "Not linked." and box.check.isVisibleTo(d)
    p = FieldRecordPicker(dict(box._context(), id=1), str(db), None, None)
    assert p.table.rowCount() == 2 and p.table.item(0, 0).text() == "1"
    assert p.table.item(0, 8).text() == "agrees" and p.table.item(1, 8).text() == "differs"
    p.table.selectRow(1)
    p._on_link()
    box.set_link(p.chosen()["id"])
    assert "observation 5" in box.summary.text()
    assert box.changes() == {"observation_id": 5}
    box.check.setChecked(True)                                # mutually exclusive
    ch = box.changes()
    assert "observation_id" not in ch and ch[sl.CHECK_COLUMN]
    assert "checked, no field record" in box.summary.text()
    box.set_link(1)
    assert box.changes() == {"observation_id": 1} and not box.check.isChecked()


def test_picker_falls_back_to_any_date(qapp, db):
    from src.views.dialogs.field_record_picker import FieldRecordPicker
    p = FieldRecordPicker({"id": 9, "species_tvk": "T1", "species_name": "Aa",
                           "date_collected": "2023-01-01", "grid_ref": "SP123456"},
                          str(db), None, 6)
    assert p.any_date.isChecked() and p.table.rowCount() == 3
    assert "showing every date" in p.note.text()


def test_obs_id_column_text(qapp):
    from src.views.collection.specimen_table_model import SpecimenTableModel
    m = SpecimenTableModel()
    m._visible_columns.add("observation_id")
    m._setup_headers()
    m.set_specimens([{"id": 1, "observation_id": None, sl.CHECK_COLUMN: "2026-10-11T10:00:00"},
                     {"id": 2, "observation_id": 42}, {"id": 3, "observation_id": None}])
    j = [k for k, *_ in m.get_columns()].index("observation_id")
    assert [m.item(r, j).text() for r in range(3)] == ["checked, none", "42", ""]
    assert "no field record" in m.item(0, j).toolTip()
