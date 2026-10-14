"""A2 (sync guard and conflicts) and A3 (Personal jobs committed with their key), 14 Oct 2026,
on purpose-made databases."""
import csv
import sqlite3
import types

import pytest

from DataEntry import irecord_export as ie
from DataEntry import staging_repo as repo
from DataEntry.commit_service import commit_job
from shared import sync_conflicts as sc


# --- shared/sync_conflicts -------------------------------------------------------------------
def _obs_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, species_tvk TEXT, "
              "date TEXT, grid_ref TEXT, site_name TEXT, recorder TEXT, determiner TEXT, sex TEXT, "
              "stage TEXT, quantity INTEGER, comment TEXT, last_synced TEXT, last_edited_date TEXT, "
              "irecord_id INTEGER, observatum_key TEXT, updated_at TEXT)")
    c.execute("INSERT INTO observations (id, species_name, date, grid_ref, quantity, last_synced, "
              "last_edited_date, irecord_id, observatum_key) VALUES "
              "(1, 'Rhinoncus pericarpius', '2021-03-22', 'SP1234', 1, '2026-10-01T10:00:00', "
              "'01/10/2026 09:00', 555, 'OBS-WJH-20261001-000001')")
    c.commit()
    return c


def test_schema_and_mark_edited(tmp_path):
    c = _obs_db(tmp_path / "o.db")
    assert sc.mark_edited(c, [1]) == 0                   # no column yet: nothing, no error
    assert sc.ensure_schema(c) and not sc.ensure_schema(c)
    assert sc.mark_edited(c, [1], when="2026-10-14T09:00:00") == 1
    assert sc.held_row(c, 1)[sc.COLUMN] == "2026-10-14T09:00:00"


@pytest.mark.parametrize("edited, inc_edit, species, expect", [
    (None, "05/10/2026 10:00", "Rhinoncus leucostigma", sc.UPDATE),        # never edited here
    ("2026-09-30T08:00:00", "05/10/2026 10:00", "Rhinoncus leucostigma", sc.UPDATE),  # before sync
    ("2026-10-14T09:00:00", "01/10/2026 09:00", "Rhinoncus leucostigma", sc.KEEP),  # iRecord same
    ("2026-10-14T09:00:00", "05/10/2026 10:00", "Rhinoncus leucostigma", sc.CONFLICT),  # both
    ("2026-10-14T09:00:00", "05/10/2026 10:00", "Rhinoncus pericarpius", sc.UPDATE),  # agree
])
def test_decide(edited, inc_edit, species, expect):
    held = {"species_name": "Rhinoncus pericarpius", "date": "2021-03-22", "quantity": 1,
            sc.COLUMN: edited, "last_synced": "2026-10-01T10:00:00", "last_edited_date": "01/10/2026 09:00"}
    incoming = {"species_name": species, "date": "2021-03-22", "quantity": "1", "last_edited_date": inc_edit}
    action, diff = sc.decide(held, incoming)
    assert action == expect
    assert diff == ([] if expect == sc.UPDATE else ["species_name"])


def test_blank_incoming_is_never_a_difference():
    held = {"species_name": "A b", "grid_ref": "SP1234", sc.COLUMN: "2026-10-14", "last_synced": None}
    assert sc.differing(held, {"species_name": "A b", "grid_ref": ""}) == []


def test_resolve_both_ways(tmp_path):
    c = _obs_db(tmp_path / "o.db")
    sc.ensure_schema(c)
    sc.mark_edited(c, [1])
    inc = {"species_name": "Rhinoncus leucostigma", "last_edited_date": "05/10/2026 10:00"}
    sc.resolve(c, 1, "observatum", inc, ["species_name"])
    row = sc.held_row(c, 1)
    assert row["species_name"] == "Rhinoncus pericarpius" and row["last_edited_date"] == "05/10/2026 10:00"
    assert sc.decide(row, dict(inc))[0] == sc.KEEP        # next sync: kept, not asked again
    sc.resolve(c, 1, "irecord", inc, ["species_name"])
    row = sc.held_row(c, 1)
    assert row["species_name"] == "Rhinoncus leucostigma" and row["last_synced"] > row[sc.COLUMN]
    assert sc.decide(row, {"species_name": "Other x", "last_edited_date": "06/10/2026"})[0] == sc.UPDATE


# --- the sync update itself -------------------------------------------------------------------
class _Db:
    def __init__(self, path):
        self.path = str(path)
        self.main_db_path = self.path

    def execute_main_write(self, sql, params=()):
        c = sqlite3.connect(self.path)
        try:
            n = c.execute(sql, params).rowcount
            c.commit()
            return n
        finally:
            c.close()

    def main_connection(self):
        import contextlib

        @contextlib.contextmanager
        def cm():
            c = sqlite3.connect(self.path)
            try:
                yield c
            finally:
                c.close()
        return cm()


def _wizard(path):
    from src.views.dialogs.observation_import_wizard.wizard_import_mixin import WizardImportMixin
    db = _Db(path)

    def get_by_id(i):
        c = sqlite3.connect(path)
        r = c.execute("SELECT species_name, irecord_id, date, grid_ref, quantity FROM observations "
                      "WHERE id=?", (i,)).fetchone()
        c.close()
        return types.SimpleNamespace(species_name=r[0], irecord_id=r[1], date=r[2], grid_ref=r[3],
                                     quantity=r[4], verification_status=None)
    w = types.SimpleNamespace(db=db, observation_model=types.SimpleNamespace(get_by_id=get_by_id),
                              _sync_conflicts=[], _sync_photo_notes=[], _import_errors=[])
    w._has_changes = lambda e, d: WizardImportMixin._has_changes(w, e, d)
    w._note_import_error = lambda *a: None
    return lambda rid, data: WizardImportMixin._update_observation(w, rid, data), w


def _incoming(species, edited):
    return {"irecord_id": 555, "species_name": species, "date": "2021-03-22", "grid_ref": "SP1234",
            "quantity": 1, "last_edited_date": edited, "last_synced": "2026-10-14T12:00:00"}


def test_sync_keeps_an_edit_made_here_and_lists_a_conflict(tmp_path):
    path = tmp_path / "o.db"
    c = _obs_db(path)
    sc.ensure_schema(c)
    sc.mark_edited(c, [1])
    c.commit()
    c.close()
    update, w = _wizard(path)
    assert update(1, _incoming("Rhinoncus leucostigma", "01/10/2026 09:00")) == sc.KEEP
    assert update(1, _incoming("Rhinoncus leucostigma", "05/10/2026 10:00")) == sc.CONFLICT
    assert w._sync_conflicts[0]["fields"] == ["species_name"]
    c = sqlite3.connect(path)
    assert c.execute("SELECT species_name FROM observations").fetchone()[0] == "Rhinoncus pericarpius"


def test_sync_updates_a_record_not_edited_here(tmp_path):
    path = tmp_path / "o.db"
    c = _obs_db(path)
    sc.ensure_schema(c)
    c.close()
    update, _ = _wizard(path)
    assert update(1, _incoming("Rhinoncus leucostigma", "05/10/2026 10:00")) is True
    c = sqlite3.connect(path)
    assert c.execute("SELECT species_name FROM observations").fetchone()[0] == "Rhinoncus leucostigma"


# --- A2: our own key is never guessed --------------------------------------------------------
def test_obs_key_on_several_records_is_held(tmp_path):
    from scripts import check_irecord_download as chk
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER, irecord_key TEXT, "
              "observatum_key TEXT, species_name TEXT, date TEXT)")
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?)", [
        (1, None, None, "OBS-WJH-20261014-000001", "Amara aenea", "2026-06-01"),
        (2, None, None, "OBS-WJH-20261014-000001", "Amara aenea", "2026-06-01"),
        (3, 900, None, "OBS-WJH-20261014-000002", "Amara ovata", "2026-06-01"),
        (4, None, None, "OBS-WJH-20261014-000003", "Amara curta", "2026-06-01")])
    c.commit()
    c.close()
    rows = [{"ID": "1001", "External key": "OBS-WJH-20261014-000001", "Taxon": "Amara aenea",
             "Date from": "01/06/2026"},
            {"ID": "1002", "External key": "OBS-WJH-20261014-000002", "Taxon": "Amara ovata",
             "Date from": "01/06/2026"},
            {"ID": "1003", "External key": "OBS-WJH-20261014-000003", "Taxon": "Amara curta",
             "Date from": "01/06/2026"},
            {"ID": "1004", "External key": "OBS-WJH-20261014-000009", "Taxon": "Amara similata",
             "Date from": "01/06/2026"}]
    df = chk.run_matching(rows, chk.ReadOnlyDb(db))
    out = {r["irecord_id"]: r for r in df.to_dict("records")}
    assert "on 2 records" in out[1001]["sync_hold"]
    assert "iRecord ID 900" in out[1002]["sync_hold"]
    assert out[1003]["is_duplicate"] and out[1003]["existing_record_id"] == 4
    assert not out[1004]["is_duplicate"]
    assert not isinstance(out[1004].get("sync_hold"), str)


# --- A3: Personal jobs committed, with their key in the iRecord file ---------------------------
def _row(**kw):
    base = {"species_name": "Amara aenea", "species_tvk": "T1", "date": "05/06/2026",
            "grid_ref": "SP4033", "site_name": "South Newington", "recorder": "Heeney, W.J.",
            "determiner": "Heeney, W.J.", "quantity": "1", "sex": "male"}
    base.update(kw)
    return base


class _Obs:
    def __init__(self, **kw):
        self.kw = kw


def test_personal_commit_returns_rows_and_the_file_carries_keys(tmp_path):
    conn = sqlite3.connect(tmp_path / "s.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    for d in ("05/06/2026", "06/2026"):
        repo.insert_row(conn, jid, _row(date=d))
    obs = sqlite3.connect(tmp_path / "o.db")
    obs.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, observatum_key TEXT)")

    class Model:
        n = 0

        def create(self, o):
            Model.n += 1
            obs.execute("INSERT INTO observations VALUES (?, ?)", (Model.n, f"OBS-WJH-20261014-{Model.n:06d}"))
            return Model.n

    class Db:
        def execute_main_write(self, sql, params):
            return 1

        def execute_main(self, sql, params=()):
            return obs.execute(sql, params).fetchall()

    s = commit_job(Db(), Model(), conn, repo.get_job(conn, jid), observation_cls=_Obs, taxonomy={})
    assert s["committed"] == 2 and len(s["committed_rows"]) == 2 and repo.row_count(conn, jid) == 0
    assert repo.get_job(conn, jid)["status"] == "active"     # the standing Personal job stays
    out = tmp_path / "irecord.csv"
    assert ie.write_committed_csv(Db(), s["committed_rows"], str(out), accepted={"T1"}) == 2
    with open(out, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert [r["External key"] for r in rows] == ["OBS-WJH-20261014-000001", "OBS-WJH-20261014-000002"]
    assert [r["Date"] for r in rows] == ["05/06/2026", "Jun 2026"]   # the date as typed, not widened
    assert rows[0]["TVK"] == "T1" and rows[0]["Sex"] == "male"


def test_file_refuses_a_record_without_a_key(tmp_path):
    class Db:
        def execute_main(self, sql, params=()):
            return [(7, None)]
    with pytest.raises(ValueError, match="no Observatum key"):
        ie.write_committed_csv(Db(), [(_row(), 7)], str(tmp_path / "x.csv"))


# --- review fixes, 14 Oct 2026 ----------------------------------------------------------------
def test_next_key_is_the_numeric_maximum(tmp_path):
    from shared.observatum_keys import last_sequence, make_key
    c = sqlite3.connect(tmp_path / "o.db")
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, observatum_key TEXT)")
    p = "OBS-WJH-20260325-"
    c.executemany("INSERT INTO observations (observatum_key) VALUES (?)",
                  [(p + "9999",), (p + "10005",), (p + "0120",), ("OBS-WJH-IRTEST-20261013-0046",)])
    assert last_sequence(c, p) == 10005                     # text order would say 9999
    assert make_key(p, 10006) == p + "010006"
    assert last_sequence(c, "OBS-WJH-20261014-") == 0


def test_keep_and_conflict_still_take_verification(tmp_path):
    path = tmp_path / "o.db"
    c = _obs_db(path)
    c.execute("ALTER TABLE observations ADD COLUMN verification_status TEXT")
    sc.ensure_schema(c)
    sc.mark_edited(c, [1])
    c.commit()
    c.close()
    update, w = _wizard(path)
    data = dict(_incoming("Rhinoncus leucostigma", "05/10/2026 10:00"), verification_status="Accepted")
    assert update(1, data) == sc.CONFLICT
    c = sqlite3.connect(path)
    assert c.execute("SELECT species_name, verification_status FROM observations").fetchone() == (
        "Rhinoncus pericarpius", "Accepted")
    assert w._sync_conflicts[0]["incoming_all"]["species_name"] == "Rhinoncus leucostigma"


def test_take_irecord_writes_the_whole_sync_set(tmp_path):
    c = _obs_db(tmp_path / "o.db")
    c.execute("ALTER TABLE observations ADD COLUMN common_name TEXT")
    sc.ensure_schema(c)
    sc.resolve(c, 1, "irecord", {"species_name": "Rhinoncus leucostigma", "common_name": "A weevil",
                                 "last_edited_date": "05/10/2026"})
    assert c.execute("SELECT species_name, common_name FROM observations").fetchone() == (
        "Rhinoncus leucostigma", "A weevil")


def test_agreeing_again_marks_synced(tmp_path):
    path = tmp_path / "o.db"
    c = _obs_db(path)
    sc.ensure_schema(c)
    sc.mark_edited(c, [1])
    c.commit()
    c.close()
    update, _ = _wizard(path)
    assert update(1, _incoming("Rhinoncus pericarpius", "07/10/2026 08:00")) == "skipped"
    c = sqlite3.connect(path)
    row = sc.held_row(c, 1)
    assert row["last_synced"] > row[sc.COLUMN] and row["last_edited_date"] == "07/10/2026 08:00"


def test_file_refuses_repeated_keys(tmp_path):
    class Db:
        def execute_main(self, sql, params=()):
            return [(7, "OBS-X-1"), (8, "OBS-X-1")]
    with pytest.raises(ValueError, match="different Observatum keys"):
        ie.write_committed_csv(Db(), [(_row(), 7), (_row(), 8)], str(tmp_path / "x.csv"))


def test_first_sync_of_a_committed_personal_record_fills_its_irecord_id(tmp_path):
    path = tmp_path / "o.db"
    c = _obs_db(path)
    sc.ensure_schema(c)
    c.execute("UPDATE observations SET irecord_id = NULL, last_synced = NULL, last_edited_date = NULL")
    c.commit()
    c.close()
    update, _ = _wizard(path)
    assert update(1, _incoming("Rhinoncus pericarpius", "15/10/2026 08:00")) is True
    c = sqlite3.connect(path)
    assert c.execute("SELECT irecord_id, species_name FROM observations").fetchone() == (
        555, "Rhinoncus pericarpius")


def test_sync_redet_brings_the_new_species_sort_key(tmp_path, monkeypatch):
    """Review 14 Oct: a re-determination from iRecord takes the new species' sort key,
    superfamily and subfamily; the same species leaves them alone."""
    import shared.import_core as ic
    path = tmp_path / "o.db"
    c = _obs_db(path)
    for col in ("taxonomic_sort_key INTEGER", "superfamily TEXT", "subfamily TEXT"):
        c.execute(f"ALTER TABLE observations ADD COLUMN {col}")
    c.execute("UPDATE observations SET species_tvk='OLD', taxonomic_sort_key=11, superfamily='Curculionoidea', "
              "subfamily='Ceutorhynchinae'")
    c.commit()
    sc.ensure_schema(c)
    c.close()
    looked = []

    def fake(tvks, uksi_path=None):
        tvks = list(tvks)
        looked.extend(tvks)
        return {"NEW": {"sort_key": 99, "superfamily": "Chrysomeloidea", "subfamily": ""}}
    monkeypatch.setattr(ic, "taxonomy_for_tvks", fake)
    update, w = _wizard(path)
    w.observation_model.get_by_id = (lambda f: (lambda i: types.SimpleNamespace(
        **vars(f(i)), species_tvk="OLD")))(w.observation_model.get_by_id)
    inc = dict(_incoming("Rhinoncus pericarpius", "05/10/2026 10:00"), species_tvk="OLD", quantity=2)
    assert update(1, inc) is True and looked == []           # same species: not looked up
    inc = dict(_incoming("Other species", "06/10/2026 10:00"), species_tvk="NEW")
    assert update(1, inc) is True and looked == ["NEW"]
    c = sqlite3.connect(path)
    assert c.execute("SELECT taxonomic_sort_key, superfamily, subfamily FROM observations").fetchone() == (
        99, "Chrysomeloidea", None)
