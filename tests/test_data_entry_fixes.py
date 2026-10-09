"""Data Entry fixes of 9 Oct 2026 (review DE1, DE2, DE4, DE7, OBS-11): pure logic and
sqlite only -- the widget is driven in test_data_entry_widget.py."""
import csv
import datetime as dt
import sqlite3

import pytest

from DataEntry import date_utils
from DataEntry import irecord_export as ie
from DataEntry import staging_repo as repo
from DataEntry.commit_service import build_kwargs_from_row, commit_job, precommit_issues
from shared.taxon_groups import BUTTERFLY, MOTH, taxon_group

TODAY = dt.date.today()


# ---------------------------------------------------------------- shared/taxon_groups
@pytest.mark.parametrize("order, family, cls, kingdom, group", [
    ("Lepidoptera", "Pieridae", None, None, BUTTERFLY),
    ("Lepidoptera", "Riodinidae", None, None, BUTTERFLY),
    ("Lepidoptera", "Geometridae", None, None, MOTH),
    ("Lepidoptera", None, None, None, MOTH),
    ("Coleoptera", "Carabidae", None, None, "insect - beetle (Coleoptera)"),
    ("Polyxenida", None, "Diplopoda", None, "millipede"),          # class fallback
    ("Caryophyllales", None, "Magnoliopsida", "Plantae", "flowering plant"),
    ("Pezizales", None, "Pezizomycetes", "Fungi", "fungus"),       # kingdom fallback
    ("Nonsuchiformes", None, None, None, None),                    # blank, not a guess
])
def test_taxon_group(order, family, cls, kingdom, group):
    assert taxon_group(order, family, cls, kingdom) == group


# ---------------------------------------------------------------- DE1: dates
@pytest.mark.parametrize("typed, stored, kind, start", [
    ("05/06/2026", "2026-06-05", "D", "2026-06-05"),
    ("2026", "2026", "Y", "2026-01-01"),
    ("06/2026", "2026-06", "O", "2026-06-01"),
    ("Jun 2026", "2026-06", "O", "2026-06-01"),
    ("june 2026", "2026-06", "O", "2026-06-01"),
    ("2026-06", "2026-06", "O", "2026-06-01"),
])
def test_vague_dates_read(typed, stored, kind, start):
    assert date_utils.parse(typed) == (stored, kind)
    assert date_utils.start_iso(typed) == start
    assert date_utils.normalise(typed) == stored


@pytest.mark.parametrize("typed", ["31/02/2026", "summer 2026", "13/2026", "Junk 2026", "1500", "abc"])
def test_unreadable_dates(typed):
    assert not date_utils.is_readable(typed)
    assert date_utils.normalise(typed) == typed        # kept, so the cell can show it


def test_date_display_and_irecord_forms():
    assert date_utils.to_display("2026-06") == "06/2026"
    assert date_utils.to_irecord("2026-06-05") == "05/06/2026"
    assert date_utils.to_irecord("2026-06") == "Jun 2026"
    assert date_utils.to_irecord("2026") == "2026"
    assert date_utils.end_iso("2024-02") == "2024-02-29"
    assert date_utils.is_future(str(TODAY.year + 1))


def _row(**kw):
    base = dict(species_name="Philanthus triangulum", species_tvk="T1", date="2026-06-05",
                site_name="Elmley", grid_ref="TQ9368", method="Sweep", trap_number="", sex="",
                stage="Adult", recorder="Heeney, W.J.", vc_number=15, order_name="Hymenoptera",
                family="Crabronidae")
    base.update(kw)
    return base


def test_precommit_flags_dates_recorder_and_vc():
    future = (TODAY + dt.timedelta(days=3)).isoformat()
    rows = [_row(), _row(date="31/02/2026", sex="m"), _row(date=future, sex="f"),
            _row(recorder="", sex="x"), _row(vc_number=None, vice_county=None, sex="y"),
            _row(species_name="", date="rubbish")]                  # no species: not checked
    assert precommit_issues(rows) == {"unreadable date": [2], "future date": [3],
                                      "no recorder": [4], "no VC": [5]}


def test_kwargs_take_date_type_and_uksi_taxonomy():
    tax = {"taxon_group": "insect - hymenopteran", "kingdom": "Animalia", "taxon_rank": "Species",
           "superfamily": "Apoidea", "taxonomic_sort_key": 26000001}
    kw = build_kwargs_from_row(_row(date="2026"), {"mode": "Personal"}, None, tax)
    assert (kw["date"], kw["date_type"]) == ("2026-01-01", "Y")
    assert (kw["taxon_group"], kw["kingdom"], kw["taxon_rank"]) == (
        "insect - hymenopteran", "Animalia", "Species")
    kw = build_kwargs_from_row(_row(date="06/2026", order_name="Lepidoptera", family="Lycaenidae"),
                               {"mode": "Personal"})
    assert (kw["date"], kw["date_type"], kw["taxon_group"]) == ("2026-06-01", "O", BUTTERFLY)


# ---------------------------------------------------------------- commit (DE4, OBS-11)
class _Obs:
    def __init__(self, **kw):
        self.kw = kw


class _Model:
    def __init__(self, fail_at=None, falsy_at=None):
        self.made, self.fail_at, self.falsy_at = [], fail_at, falsy_at

    def create(self, obs):
        n = len(self.made) + 1
        if n == self.fail_at:
            raise RuntimeError("disk I/O error")
        if n == self.falsy_at:
            return None
        self.made.append(obs.kw)
        return 100 + n


class _Db:
    def __init__(self):
        self.writes = []

    def execute_main_write(self, sql, params):
        self.writes.append((sql, params))


@pytest.fixture
def staging(tmp_path):
    conn = sqlite3.connect(tmp_path / "obs.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    return conn


def _job(conn, mode="Commercial", n=3, **row):
    jid = repo.create_job(conn, "Hook Farm", mode, "BAM", "Hook Farm" if mode == "Commercial" else None)
    for i in range(n):
        repo.insert_row(conn, jid, _row(sex=str(i), **row))
    return repo.get_job(conn, jid)


def test_commit_writes_taxonomy_superfamily_and_sort_key(staging):
    job = _job(staging, n=1)
    tax = {"T1": {"taxon_group": "insect - hymenopteran", "kingdom": "Animalia",
                  "taxon_rank": "Species", "superfamily": "Apoidea", "taxonomic_sort_key": 26000001}}
    db, model = _Db(), _Model()
    s = commit_job(db, model, staging, job, observation_cls=_Obs, taxonomy=tax)
    assert s["committed"] == 1 and s["error"] is None
    assert model.made[0]["taxon_group"] == "insect - hymenopteran"
    sql, params = db.writes[0]
    assert "superfamily=?" in sql and "taxonomic_sort_key=?" in sql
    assert params[4:6] == ("Apoidea", 26000001)


def test_commit_part_failure_reports_what_was_written(staging):
    job = _job(staging, n=3)
    s = commit_job(_Db(), _Model(fail_at=2), staging, job, observation_cls=_Obs, taxonomy={})
    assert s["committed"] == 1 and "disk I/O error" in s["error"]
    assert s["remaining"] == 2 == repo.row_count(staging, job["id"])   # the rest stay staged
    assert repo.get_job(staging, job["id"])["status"] == "active"


def test_commit_without_an_id_keeps_the_row(staging):
    job = _job(staging, n=2)
    s = commit_job(_Db(), _Model(falsy_at=1), staging, job, observation_cls=_Obs, taxonomy={})
    assert s["committed"] == 0 and s["error"] and repo.row_count(staging, job["id"]) == 2


def test_commit_leaves_unreadable_dates_in_staging(staging):
    job = _job(staging, n=1)
    repo.insert_row(staging, job["id"], _row(date="31/02/2026"))
    s = commit_job(_Db(), _Model(), staging, job, observation_cls=_Obs, taxonomy={})
    assert (s["committed"], s["skipped_bad_date"], s["remaining"]) == (1, 1, 1)


# ---------------------------------------------------------------- DE7: Personal -> iRecord
def test_irecord_row_layout():
    assert ie.IRECORD_COLUMNS == ("Species", "TVK", "Date", "Grid reference", "Location name",
                                  "Recorder(s)", "Determiner", "Abundance", "Stage", "Sex",
                                  "Sample method", "Comment")
    line = ie.irecord_row(_row(quantity="x", determiner="Heeney, W.J.", sex="Female"), {"T1"})
    assert line == ["Philanthus triangulum", "T1", "05/06/2026", "TQ9368", "Elmley",
                    "Heeney, W.J.", "Heeney, W.J.", "1", "Adult", "Female", "Sweep", ""]
    assert ie.irecord_row(_row(), set())[1] == ""          # not an accepted TVK: left blank
    assert ie.irecord_row(_row(sex="Not recorded"))[9] == ""


def test_export_marks_awaiting_and_keeps_rows(staging, tmp_path, monkeypatch):
    monkeypatch.setattr(ie, "accepted_tvks", lambda tvks, uksi_path=None: {"T1"})
    pid = repo.ensure_personal_job(staging)
    for i in range(2):
        repo.insert_row(staging, pid, _row(sex=str(i)))
    repo.insert_row(staging, pid, {})                          # a blank spacer row
    out = tmp_path / "p.csv"
    res = ie.export_job(staging, repo.get_job(staging, pid), str(out))
    assert res["written"] == 2
    with open(out, encoding="utf-8-sig", newline="") as f:
        lines = list(csv.reader(f))
    assert lines[0] == list(ie.IRECORD_COLUMNS) and len(lines) == 3
    job = repo.get_job(staging, pid)
    assert job["status"] == repo.AWAITING_IRECORD and repo.row_count(staging, pid) == 3
    assert job["name"].startswith("Personal – exported")
    assert pid in [j["id"] for j in repo.list_jobs(staging)]          # still listed
    assert repo.ensure_personal_job(staging) != pid                   # a fresh standing job


def test_export_refuses_unreadable_dates(staging, tmp_path):
    pid = repo.ensure_personal_job(staging)
    repo.insert_row(staging, pid, _row(date="31/02/2026"))
    with pytest.raises(ValueError):
        ie.export_job(staging, repo.get_job(staging, pid), str(tmp_path / "x.csv"))
    assert repo.get_job(staging, pid)["status"] == "active"


def _o(i, **kw):
    base = dict(id=i, species_tvk="T1", species_name="Philanthus triangulum", date="2026-06-05",
                grid_ref="TQ 9368", recorder="W.J. Heeney")
    base.update(kw)
    return base


def test_match_return_strict_loose_missing():
    rows = [_row(sex="m"), _row(sex="f"), _row(species_tvk="", species_name="Odynerus spinipes"),
            _row(grid_ref="TQ9999"), {"species_name": ""}]
    obs = [_o(1), _o(2, recorder="Wil Heeney"),                    # 2: recorder written differently
           _o(3, species_tvk="X9", species_name="odynerus  spinipes"),
           _o(4, date="2026-06-06")]                               # wrong day: no match
    res = ie.match_return(rows, obs)
    assert res["total"] == 4
    assert [o["id"] for _, o in res["matched"]] == [1, 3]
    assert [o["id"] for _, o in res["matched_loose"]] == [2]
    assert [n for n, _ in res["missing"]] == [4]


def test_check_return_reads_observations_and_close(staging):
    staging.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, "
                    "species_tvk TEXT, species_name TEXT, date TEXT, grid_ref TEXT, recorder TEXT)")
    pid = repo.ensure_personal_job(staging)
    repo.insert_row(staging, pid, _row())
    repo.insert_row(staging, pid, _row(date="2026"))                  # a year-only record
    repo.update_job(staging, pid, status=repo.AWAITING_IRECORD)
    job = repo.get_job(staging, pid)
    staging.execute("INSERT INTO observations VALUES (1, NULL, 'T1', 'x', '2026-06-05', 'TQ9368', "
                    "'Heeney, W.J.')")                                 # not back yet: no iRecord ID
    assert len(ie.check_return(staging, job)["missing"]) == 2
    staging.execute("UPDATE observations SET irecord_id=555 WHERE id=1")
    staging.execute("INSERT INTO observations VALUES (2, 556, 'T1', 'x', '2026-01-01', 'TQ9368', "
                    "'Heeney, W.J.')")
    res = ie.check_return(staging, job)
    assert len(res["matched"]) == 2 and not res["missing"]
    ie.close_job(staging, job)
    assert repo.get_job(staging, pid)["status"] == repo.RETURNED_IRECORD
    assert repo.row_count(staging, pid) == 2                          # rows kept
    assert pid not in [j["id"] for j in repo.list_jobs(staging)]


# ---------------------------------------------------------------- DE2: VC follows the grid ref
class _VC:
    def get_vc_from_grid_ref(self, gr):
        return (23, "Oxfordshire") if gr.startswith("SP") else None


@pytest.fixture
def model(staging):
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from DataEntry.entry_grid import StagingTableModel
    pid = repo.ensure_personal_job(staging)
    repo.insert_row(staging, pid, {"species_name": "Carabus nemoralis"})
    return StagingTableModel(staging, pid, _VC())


@pytest.mark.parametrize("second", ["XX123", ""])
def test_vc_clears_with_a_bad_or_cleared_grid_ref(model, second):
    from DataEntry.entry_grid import COLIDX
    from PySide6.QtCore import Qt
    idx = model.index(0, COLIDX["grid_ref"])
    model.setData(idx, "SP580207", Qt.ItemDataRole.EditRole)
    assert model.row_dict(0)["vc_number"] == 23
    model.setData(idx, second, Qt.ItemDataRole.EditRole)
    r = model.row_dict(0)
    assert r["vc_number"] is None and r["vice_county"] is None


def test_unreadable_date_is_flagged_in_the_cell(model):
    from DataEntry.entry_grid import COLIDX
    from PySide6.QtCore import Qt
    idx = model.index(0, COLIDX["date"])
    model.setData(idx, "31/02/2026", Qt.ItemDataRole.EditRole)
    assert "Can't read" in model.data(idx, Qt.ItemDataRole.ToolTipRole)
    assert model.data(idx, Qt.ItemDataRole.BackgroundRole) is not None
    model.setData(idx, "05/06/2026", Qt.ItemDataRole.EditRole)
    assert model.data(idx, Qt.ItemDataRole.BackgroundRole) is None
