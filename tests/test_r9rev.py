"""Round 9 review (12 Oct): small fixes found reviewing Round 9.

- The Pantheon bridge corrections CSV is still read when saved from Excel on Windows (ANSI /
  cp1252, not UTF-8): before, a UnicodeDecodeError escaped load_corrections and stopped the
  bridge loading.
- County firsts on the Scheme dashboard join back to recording_scheme to find the record; the
  join now leaves the marked NBN copies out too, so a first never points at a copy (Q59).
"""
import os
import sqlite3
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_bridge_corrections_read_from_an_ansi_file(tmp_path):
    from shared.repositories.pantheon_repository import load_corrections
    p = tmp_path / "corr.csv"
    p.write_bytes("action,pantheon_tvk,pantheon_name,uksi_tvk,uksi_name,reason\r\n"
                  "unlink,P1,Sympetrum nigrescens,U1,Sympetrum striolatum,Highland Darter – café\r\n"
                  .encode("cp1252"))
    rows = load_corrections(p)
    assert [(a, pan, uk) for a, pan, uk, _n in rows] == [("unlink", "P1", "U1")]


def test_bridge_corrections_utf8_with_bom(tmp_path):
    from shared.repositories.pantheon_repository import load_corrections
    p = tmp_path / "corr.csv"
    p.write_bytes("action,pantheon_tvk,pantheon_name,uksi_tvk,uksi_name,reason\n"
                  "unlink,P1,Sympetrum nigrescens,U1,S. striolatum,\"a, b\"\n".encode("utf-8-sig"))
    assert [(a, pan, uk) for a, pan, uk, _n in load_corrections(p)] == [("unlink", "P1", "U1")]


def test_county_first_joins_leave_copies_out(tmp_path):
    from shared import scheme_duplicates as sd
    from src.services.recording_scheme_stats_service import RecordingSchemeStatsService
    db = str(tmp_path / "s.db")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, species_tvk TEXT)")
    c.commit()
    c.close()
    sd.forget()
    svc = RecordingSchemeStatsService.__new__(RecordingSchemeStatsService)
    svc._db = SimpleNamespace(main_db_path=db)
    assert svc._copies_out("rs.") == ""                   # column not there yet: no change
    c = sqlite3.connect(db)
    c.execute("ALTER TABLE recording_scheme ADD COLUMN duplicate_of INTEGER")
    c.commit()
    c.close()
    assert svc._copies_out("rs.") == " AND rs.duplicate_of IS NULL"
    sd.forget()
    src = open(os.path.join(ROOT, "Observatum", "src", "services",
                            "recording_scheme_stats_service.py"), encoding="utf-8").read()
    assert src.count("{self._copies_out('rs.')}") == 2   # both joins back to the table
