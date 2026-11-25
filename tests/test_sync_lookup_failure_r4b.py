"""R4B: a failed match lookup in the iRecord sync holds the row; nothing is added as new."""
import sqlite3

import pytest

from scripts import check_irecord_download as chk


class _Db:
    """execute_main on a real small database; SQL containing `fail_on` raises."""

    def __init__(self, path, fail_on=None):
        self.conn = sqlite3.connect(path)
        self.fail_on = fail_on

    def execute_main(self, sql, params=()):
        if self.fail_on and self.fail_on in sql:
            raise sqlite3.OperationalError("simulated lookup failure")
        return self.conn.execute(sql, params).fetchall()


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "o.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, irecord_id INTEGER UNIQUE, "
              "irecord_key TEXT, observatum_key TEXT, species_name TEXT, date TEXT)")
    c.execute("INSERT INTO observations VALUES (1, 900, NULL, 'OBS-A-1', 'Amara aenea', '2026-06-01')")
    c.execute("INSERT INTO observations VALUES (2, NULL, '901', 'OBS-A-2', 'Amara ovata', '2026-06-01')")
    c.commit()
    c.close()
    return p


ROWS = [{"ID": "900", "Taxon": "Amara aenea", "Date from": "01/06/2026"},
        {"ID": "901", "Taxon": "Amara ovata", "Date from": "01/06/2026"},
        {"ID": "950", "Taxon": "Amara curta", "Date from": "01/06/2026"},
        {"ID": "", "External key": "OBS-A-2", "Taxon": "Amara ovata", "Date from": "01/06/2026"}]


def _held(row):
    return isinstance(row.get("sync_hold"), str) and "not imported, to be safe" in row["sync_hold"]


def test_working_lookups_match_and_add_new(db_path):
    df = chk.run_matching(ROWS[:3], _Db(db_path))
    out = {r["irecord_id"]: r for r in df.to_dict("records")}
    assert out[900]["is_duplicate"] and out[901]["is_duplicate"]
    assert not out[950]["is_duplicate"] and not _held(out[950])


@pytest.mark.parametrize("fail_on", ["SELECT irecord_id, id", "SELECT irecord_key, id"])
def test_failed_id_or_key_lookup_holds_unmatched_rows(db_path, fail_on):
    before = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    df = chk.run_matching(ROWS[:3], _Db(db_path, fail_on))
    out = {r["irecord_id"]: r for r in df.to_dict("records")}
    assert _held(out[950])                      # would have been added as new
    assert not out[950]["is_duplicate"]
    assert sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM observations").fetchone()[0] == before


def test_failed_external_key_lookup_holds_the_row(db_path):
    df = chk.run_matching([ROWS[3]], _Db(db_path, "observatum_key"))
    assert _held(df.to_dict("records")[0])
