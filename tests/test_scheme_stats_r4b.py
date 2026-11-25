"""R4B: Recording Scheme statistics -- species counted by TVK like the observation stats,
gaps follow the same scope, family names are parameters, a failed refresh keeps the last figures."""
import sqlite3

import pytest

from src.services import recording_scheme_stats_service as svc_mod
from src.services.recording_scheme_stats_service import RecordingSchemeStatsService, scheme_totals


class Db:
    def __init__(self, path):
        self.main_db_path = str(path)
        self.fail = False

    def execute_main(self, sql, params=()):
        if self.fail:
            raise sqlite3.OperationalError("simulated failure")
        c = sqlite3.connect(self.main_db_path)
        c.row_factory = sqlite3.Row
        try:
            return c.execute(sql, params).fetchall()
        finally:
            c.close()


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = tmp_path / "o.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, species_name TEXT, species_tvk TEXT, "
              "taxon_rank TEXT, family TEXT, date TEXT, date_type TEXT, vc_number INTEGER, vice_county TEXT, "
              "grid_ref TEXT, duplicate_of INTEGER)")
    rows = [
        (1, "Amara aenea", "T1", None, "Carabidae", "2010-05-01", "D", 1, "A", "SP1111", None),
        (2, "Amara aenea var. x", "T1", None, "Carabidae", "2011-05-01", "D", 1, "A", "SP1111", None),  # same TVK
        (3, "Amara ovata", "T2", None, "Carabidae", "2012-05-01", "D", 1, "A", "SP1111", None),
        (4, "Amara ovata", "T2", None, "Carabidae", "2025-05-01", "D", 1, "A", "SP1111", 3),   # NBN copy, recent
        (5, "Rhagium inquisitor", "T3", None, "Cerambycidae", "2024-05-01", "D", 2, "B", "SP2222", None),
        (6, "Leiopus nebulosus", "T4", None, "Cerambycidae", "2015-05-01", "D", 2, "B", "SP2222", None),
        (7, "Leiopus linnei", None, None, "Cerambycidae", "2025-05-01", "D", 2, "B", "SP2222", None),
        (8, "Obrienia o'brieni", "T5", None, "O'Brien", "2014-05-01", "D", 2, "B", "SP2222", None),
        (9, "Undated thing", "T6", None, "Carabidae", "", "D", 2, "B", "SP2222", None),
    ]
    c.executemany("INSERT INTO recording_scheme VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()
    monkeypatch.setattr(svc_mod, "scheme_families", lambda: [])
    d = Db(p)
    s = RecordingSchemeStatsService()
    old = (s._db, s._cache, s._valid, s.last_error)
    s.initialize(d)
    s.invalidate()
    yield d, s
    s._db, s._cache, s._valid, s.last_error = old


def test_species_counted_by_taxon_not_name(db):
    d, s = db
    # 9 rows, 8 names: T1 under two names counts once; a row with no TVK adds no taxon;
    # the NBN copy (id 4) is not counted
    t = scheme_totals(d)
    assert t["total_species"] == 6                 # T1 T2 T3 T4 T5 T6
    assert t["total_records"] == 8                 # the copy is out
    s.refresh()
    assert s.get("total_species") == 6             # the dashboard and Home agree
    assert sum(r["species"] for r in s.get("records_by_vc")) == 6


def test_family_scope_uses_parameters(db, monkeypatch):
    d, s = db
    monkeypatch.setattr(svc_mod, "scheme_families", lambda: ["Cerambycidae", "O'Brien"])
    assert "O'Brien" not in s._get_family_clause()           # never pasted into the SQL
    assert s._get_family_clause().count("?") == 2
    t = scheme_totals(d)
    assert t["total_species"] == 3 and t["total_records"] == 4     # T3 T4 T5 (no-TVK row adds a record only)
    s.refresh()
    assert s.last_error is None and s.get("total_species") == 3
    assert s.get_monthly_counts_by_species("Rhagium inquisitor")[4] == 1
    assert s.get_vc_details(2)["species"] == 3


def test_gaps_follow_the_same_scope(db, monkeypatch):
    d, s = db
    s.refresh()
    gaps = {g["species"] for g in s.get("recording_gaps")}
    # Amara ovata: its recent record is an NBN copy, so the species' last counted record is 2012;
    # the undated species is not a gap; Leiopus linnei has a recent record
    assert "Amara ovata" in gaps and "Undated thing" not in gaps and "Leiopus linnei" not in gaps
    # a counting switch: record 7 and 6 out -> Leiopus nebulosus no longer counted at all
    monkeypatch.setattr(svc_mod, "counted_clause",
                        lambda src, prefix="", db=None: " AND id NOT IN (6)")
    s.refresh()
    gaps = {g["species"] for g in s.get("recording_gaps")}
    assert "Leiopus nebulosus" not in gaps
    monkeypatch.setattr(svc_mod, "scheme_families", lambda: ["Carabidae"])
    s.refresh()
    assert {g["species"] for g in s.get("recording_gaps")} <= {"Amara aenea", "Amara aenea var. x", "Amara ovata"}


def test_failed_refresh_keeps_last_figures_and_retries(db):
    d, s = db
    s.refresh()
    good = s.get("total_species")
    assert good == 6 and s.last_error is None
    d.fail = True
    s.refresh()
    assert s.get("total_species", None) == good or s._cache["total_species"] == good
    assert s._valid is False                      # tries again on the next read
    assert "simulated failure" in s.last_error
    from shared.stats_refresh import pending_errors
    assert pending_errors(s)
    d.fail = False
    s.refresh()
    assert s._valid is True and s.last_error is None and s._cache["total_species"] == good
