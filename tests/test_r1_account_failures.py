"""Round 1, item 1: species accounts are never silently blank when the read FAILED.
Purpose-made databases only."""
import sqlite3

import pytest
from _round_a_fixture import NAMES, T_RARE, T_SCARCE, T_VU, add_committed, build

pytest.importorskip("openpyxl")

from shared import species_accounts as sa  # noqa: E402
from Examen import examen_data as ed  # noqa: E402
from Examen import workbook_export as we  # noqa: E402


def _codex(path, ddl, rows=()):
    c = sqlite3.connect(str(path))
    c.executescript(ddl)
    for r in rows:
        c.execute(*r)
    c.commit()
    c.close()


NEW = ("CREATE TABLE species_profiles (id INTEGER PRIMARY KEY, tvk TEXT, species_name TEXT, "
       "profile_text TEXT, source TEXT, review_id INTEGER);"
       "CREATE TABLE reviews (id INTEGER PRIMARY KEY, review_name TEXT, author TEXT, "
       "date_published TEXT, licence TEXT, supersedes_id INTEGER);")


def test_old_schema_still_falls_back(tmp_path):
    db = tmp_path / "codex.db"
    _codex(db, "CREATE TABLE species_profiles (tvk TEXT, profile_text TEXT, source TEXT);",
           [("INSERT INTO species_profiles VALUES ('T1','Old text','Lane')",)])
    out = sa._review_accounts("T1", None, str(db))
    assert [r.text for r in out] == ["Old text"]


def test_missing_codex_is_visible(tmp_path):
    with pytest.raises(sqlite3.Error):
        sa._review_accounts("T1", None, str(tmp_path / "nope.db"))
    acc = sa.get_species_accounts("T1", None, codex_db=str(tmp_path / "nope.db"),
                                  observatum_db=str(tmp_path / "nope2.db"))
    assert acc.read_error and not acc.reviews


def test_locked_error_is_not_swallowed(tmp_path, monkeypatch):
    db = tmp_path / "codex.db"
    _codex(db, NEW)

    class Conn:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("database is locked")

        def close(self):
            pass
    monkeypatch.setattr(sa, "_ro", lambda p: Conn())
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        sa._review_accounts("T1", None, str(db))
    acc = sa.get_species_accounts("T1", codex_db=str(db), observatum_db=str(tmp_path / "x.db"))
    assert "locked" in acc.read_error


def test_genuinely_no_account_has_no_error(tmp_path):
    db = tmp_path / "codex.db"
    _codex(db, NEW)
    acc = sa.get_species_accounts("T1", codex_db=str(db), observatum_db=str(tmp_path / "x.db"))
    assert acc.read_error is None and not acc.reviews


def test_profiles_collects_problems(monkeypatch):
    def fake(tvk, *a, **k):
        acc = sa.SpeciesAccounts(tvk=tvk)
        if tvk == "A":
            acc.read_error = "database is locked"
        elif tvk == "B":
            raise RuntimeError("boom")
        return acc
    monkeypatch.setattr(sa, "get_species_accounts", fake)
    problems = []
    out = we._profiles({"A", "B", "C"}, problems)
    assert out == {}
    assert {t for t, _ in problems} == {"A", "B"}      # C has no account: normal, no note


def test_problem_line_wording():
    line = we._accounts_problem_line([("A", "locked"), ("B", "locked")], {"A": "Alpha", "B": "Beta"})
    assert "Accounts could not be read for 2 species: Alpha, Beta (locked)." in line
    assert "Re-export when Codex is not in use." in line
    once = we._accounts_problem_line(
        [("A", "unable to open database file"), ("B", "unable to open database file")], {"A": "Alpha"})
    assert once.count("unable to open database file") == 1 and "could not be opened" in once
    assert "Codex could not be opened (unable to open database file)" in once
    assert "could not be read: " not in once and "(Codex could not be read" not in once
    assert we._accounts_problem_line([], {}) == ""


def _sheet_text(path):
    from openpyxl import load_workbook
    ws = load_workbook(path)["Key species"]
    return [str(c.value) for row in ws.iter_rows() for c in row if c.value]


def _export(tmp_path, monkeypatch, name):
    build(tmp_path, monkeypatch)
    add_committed(tmp_path)
    d = ed.load_project_detail("Notts Park", "Acme", survey_year="2026")
    out = str(tmp_path / name)
    we.export_workbook(d.analysis, d, None, out)
    return out


def test_workbook_notes_unreadable_accounts(tmp_path, monkeypatch):
    def locked(tvk, species_name, codex_db):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(sa, "_review_accounts", locked)
    text = _sheet_text(_export(tmp_path, monkeypatch, "locked.xlsx"))
    notes = [t for t in text if t.startswith("Accounts could not be read")]
    assert len(notes) == 1
    assert "database is locked" in notes[0] and "Re-export when Codex is not in use." in notes[0]
    assert any(NAMES[t] in notes[0] for t in (T_RARE, T_VU, T_SCARCE))
    assert we.LAST_EXPORT_WARNINGS == notes


def test_workbook_no_note_when_accounts_simply_absent(tmp_path, monkeypatch):
    text = _sheet_text(_export(tmp_path, monkeypatch, "fine.xlsx"))
    assert not [t for t in text if t.startswith("Accounts could not be read")]
    assert we.LAST_EXPORT_WARNINGS == []
