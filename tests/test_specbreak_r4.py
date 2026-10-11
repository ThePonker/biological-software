"""Round 4 (11 Oct 2026): specimens with no field record, sorted into what could become a
record -- scripts/specimen_breakdown.py and scripts/report_specimens_without_records.py, on
small throwaway databases (no UKSI: exact TVKs)."""
import csv
import hashlib
import sqlite3

import pytest

from scripts import report_specimens_without_records as rep
from scripts import specimen_breakdown as sb

OBS = ("id INTEGER PRIMARY KEY, species_name, species_tvk, date, grid_ref, site_name, recorder, "
       "quantity INTEGER, sex, record_type, project_name, client, embargo_status, embargo_until")
SPEC = ("id INTEGER PRIMARY KEY, specimen_code, species_name, species_tvk, date_collected, "
        "grid_ref, collector, determiner, site_name, observation_id, sex")
OTHER = "id INTEGER PRIMARY KEY, species_name, species_tvk, date, grid_ref, site_name, recorder"

W = "Heeney, W.J."
OBS_ROWS = [
    # a Personal visit at SP4040 on 2025-06-01
    (1, "Aa aa", "T1", "2025-06-01", "SP404404", "Home", W, 1, None, "Personal", None, None, None, None),
    # a Commercial survey (Proj X) at SU1010 on 2025-07-01
    (2, "Bb bb", "T2", "2025-07-01", "SU101101", "Proj site", W, 1, None, "Commercial", "Proj X",
     "Client", "Active", "2028-01-01"),
    # same species as specimen 5, same day, 10-figure ref inside its 6-figure square
    (3, "Cc cc", "T3", "2025-06-01", "SP4041240412", "Home", W, 1, None, "Personal", None, None, None, None),
    # same species as specimen 6, three days earlier, 300 m away
    (4, "Dd dd", "T4", "2025-05-29", "SP404407", "Home", W, 1, None, "Personal", None, None, None, None),
    # Personal record on another date near TL1010
    (5, "Ee ee", "T5", "2020-05-01", "TL101101", "Fen", W, 1, None, "Personal", None, None, None, None),
]
SPEC_ROWS = [
    # group 1, Personal (same visit), two specimens -> one record of quantity 2
    (1, "S1", "Zz one", "T9", "2025-06-01", "SP404404", W, W, "Home", None, "Male"),
    (2, "S2", "Zz one", "T9", "2025-06-01", "SP 404 404", "Wil J. Heeney", "Falk, S.", "Home", None, None),
    # group 1, Commercial Proj X: same day, survey nearby
    (3, "S3", "Yy two", "T8", "2025-07-01", "SU101102", "Heeeney, WJ.", W, "Proj site", None, None),
    # group 1, Commercial Proj X by season (20 days later, no records that day)
    (4, "S4", "Yy two", "T8", "2025-07-21", "SU101101", W, W, "Proj site", None, None),
    # group 2: same day, same place at another precision
    (5, "S5", "Cc cc", "T3", "2025-06-01", "SP404404", W, W, "Home", None, None),
    # group 2: 3 days later, 300 m away
    (6, "S6", "Dd dd", "T4", "2025-06-01", "SP404404", "Lamin, J., Heeney, W.J.", W, "Home", None, None),
    # group 3: no grid ref; no date
    (7, "S7", "Xx", "T7", "2025-06-01", "", W, W, "Home", None, None),
    (8, "S8", "Xx", "T7", "", "SP404404", W, W, "Home", None, None),
    # group 4: someone else's, historic and recent
    (9, "S9", "Vv", "T6", "1985-06-01", "TQ101101", "Mann, D.J.", "Mann, D.J.", "Wood", None, None),
    (10, "S10", "Vv", "T6", "2015-06-01", "TQ101101", "Lamin, J.", W, "Wood", None, None),
    # group 1, Personal presumed (only Personal records nearby, other dates); in the scheme
    (11, "S11", "Uu", "T10", "2021-06-01", "TL101101", W, W, "Fen", None, None),
    # group 1, unknown: no records of any kind nearby
    (12, "S12", "Uu", "T10", "2026-06-01", "NZ101101", W, W, "Scunthorpe", None, None),
    # linked already: not in the report
    (13, "S13", "Aa aa", "T1", "2025-06-01", "SP404404", W, W, "Home", 1, None),
    # group 1 with a note: another species of the genus (Aa aa) recorded there that day
    (14, "S14", "Aa bb", "T11", "2025-06-01", "SP404404", W, W, "Home", None, None),
]


def _make(path, check_column):
    c = sqlite3.connect(path)
    c.execute(f"CREATE TABLE observations ({OBS})")
    c.execute(f"CREATE TABLE specimens ({SPEC}{', no_field_record_checked' if check_column else ''})")
    c.execute(f"CREATE TABLE recording_scheme ({OTHER})")
    c.execute(f"CREATE TABLE contributed_observations ({OTHER})")
    c.executemany(f"INSERT INTO observations VALUES ({','.join('?' * 14)})", OBS_ROWS)
    n = 12 if check_column else 11
    rows = [r + ((None,) if check_column else ()) for r in SPEC_ROWS]
    c.executemany(f"INSERT INTO specimens VALUES ({','.join('?' * n)})", rows)
    c.execute("INSERT INTO recording_scheme VALUES (1, 'Uu', 'T10', '2021-06-01', 'TL101101', 'Fen', 'Heeney, Wil')")
    c.execute("INSERT INTO contributed_observations VALUES (1, 'Vv', 'T6', '2015-06-03', 'TQ101101', 'Wood', 'Lamin, J.')")
    c.commit()
    c.close()


@pytest.fixture(params=[True, False], ids=["check-column", "no-check-column"])
def db(tmp_path, request):
    p = tmp_path / "observatum.db"
    _make(p, request.param)
    return p


def _gather(p):
    c = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        return rep.gather(c, None)
    finally:
        c.close()


def _by_id(g):
    return {s["id"]: s for s in g["specs"]}


@pytest.mark.parametrize("name", ["Heeney, W.J.", "W.J. Heeney", "Wil J. Heeney", "Heeeney, WJ.",
                                  "Heeney. W.J., Lamin, L.", "Dhara, M., Heeney, W.J.", "WJH",
                                  "Heeney W.J.", "Heeney"])
def test_is_wil_yes(name):
    assert sb.is_wil(name)


@pytest.mark.parametrize("name", ["Lamin, J.", "Mann, D.J.", "Falk, S.J.", "Sweeney, Marion",
                                  "Helen Seeney", "", None, "Beeney, Allan"])
def test_is_wil_no(name):
    assert not sb.is_wil(name)


def test_owner_falls_back_to_determiner():
    assert sb.owner("", "Heeney, W.J.") == "wil"
    assert sb.owner("Lamin, J.", "Heeney, W.J.") == "other"


def test_missing():
    assert sb.missing("T1", "2025-06-01", "SP4040") == []
    assert sb.missing(None, "2025", "SP") == ["no species TVK", "vague or unreadable date '2025'",
                                              "grid ref coarser than 1 km 'SP'"]
    assert sb.missing("T1", "", "XX12") == ["no date", "unreadable grid ref 'XX12'"]


def test_groups(db):
    s = _by_id(_gather(db))
    assert 13 not in s                                   # linked: not in the report
    assert {i: s[i]["group"] for i in s} == {1: 1, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 3, 8: 3,
                                             9: 4, 10: 4, 11: 1, 12: 1, 14: 1}
    assert s[14].get("genus_note") and "NB" in s[14]["reason"] and not s[1].get("genus_note")
    assert (s[1]["sub"], s[3]["sub"], s[3]["project"]) == ("Personal", "Commercial", "Proj X")
    assert s[1]["reason"].startswith("same visit")
    assert (s[4]["sub"], s[4]["project"]) == ("Commercial", "Proj X")
    assert "within 30 days" in s[4]["reason"]
    assert s[11]["sub"] == "Personal" and "presumed" in s[11]["reason"]
    assert s[12]["sub"] == "unknown"
    assert s[5]["sub"] == "same day, same place at another grid-ref precision"
    assert s[6]["sub"] == "within 7 days" and s[6]["near"][0][0]["id"] == 4
    assert s[7]["reason"] == "no grid ref" and s[8]["reason"] == "no date"
    assert (s[9]["sub"], s[10]["sub"]) == ("likely historic", "recent")


def test_records_grouped_with_quantity(db):
    g = _gather(db)
    recs = g["records"]
    assert len(recs) == 6                                # specimens 1+2 share one record
    r = recs["T9|2025-06-01|SP404404"]
    assert (r["quantity"], r["sub"], r["recorder"]) == (2, "Personal", "Heeney, W.J.")
    assert recs["T8|2025-07-01|SU101102"]["project"] == "Proj X"
    assert g["rule"].terms["Proj X"]["embargo_status"] == "Active"


def test_elsewhere(db):
    s = _by_id(_gather(db))
    assert [(e[0], e[1]) for e in s[11]["elsewhere"]] == [("scheme", "exact")]
    assert [(e[0], e[1]) for e in s[10]["elsewhere"]] == [("contributed", "close")]
    assert s[1]["elsewhere"] == []


def test_checked_specimen_counts_and_skips_near_miss(tmp_path):
    p = tmp_path / "o.db"
    _make(p, True)
    c = sqlite3.connect(p)
    c.execute("UPDATE specimens SET no_field_record_checked = '2026-10-11T10:00:00' WHERE id = 6")
    c.commit()
    c.close()
    s = _by_id(_gather(p))
    assert s[6]["tier"] == "checked: no field record" and s[6]["group"] == 1


def test_main_writes_csv_and_changes_nothing(db, tmp_path, capsys):
    before = hashlib.md5(db.read_bytes()).hexdigest()
    out = tmp_path / "out.csv"
    assert rep.main(["--db", str(db), "--uksi", str(tmp_path / "none.db"), "--csv", str(out)]) == 0
    assert hashlib.md5(db.read_bytes()).hexdigest() == before
    text = capsys.readouterr().out
    assert "Nothing has been changed" in text
    assert "6 new observation records covering 7 specimens" in text
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 13
    one = [r for r in rows if r["specimen_id"] == "2"][0]
    assert (one["group"], one["record_key"], one["record_quantity"]) == ("1", "T9|2025-06-01|SP404404", "2")
    com = [r for r in rows if r["specimen_id"] == "3"][0]
    assert (com["record_type"], com["project_name"], com["embargo_status"]) == ("Commercial", "Proj X", "Active")
    oth = [r for r in rows if r["specimen_id"] == "10"][0]
    assert (oth["record_type"], oth["recorder"], oth["record_determiner"]) == ("contributed", "Lamin, J.", W)
