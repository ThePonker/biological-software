"""Round A: visit weather module and the Visits & weather dialog (temporary databases)."""
import sqlite3

import pytest

import paths
from shared import visit_weather as vw

DDL = """CREATE TABLE visit_weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_name TEXT NOT NULL, client TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL, temperature TEXT NOT NULL DEFAULT '', wind TEXT NOT NULL DEFAULT '',
    cloud TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', updated_at TEXT,
    UNIQUE(project_name, client, date))"""


@pytest.fixture
def db(tmp_path, monkeypatch):
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.execute(DDL)
    c.commit()
    c.close()
    monkeypatch.setattr(paths, "OBSERVATUM_DB", p)
    monkeypatch.setattr("shared.away_mode.away_active", lambda: False)
    return p


def row(d, temperature="", wind="", cloud="", notes=""):
    return {"date": d, "temperature": temperature, "wind": wind, "cloud": cloud, "notes": notes}


def test_round_trip_and_upsert(db):
    assert vw.table_ready()
    vw.save_weather("P", "C", [row("2026-06-01", "30–32 °C", "Beaufort 1–2", "1–3 oktas")])
    got = vw.weather_for("P", "C")
    assert got["2026-06-01"]["wind"] == "Beaufort 1–2"
    assert vw.weather_for("P", "C", ["2026-07-01"]) == {}
    assert vw.weather_for("P", "other") == {}
    vw.save_weather("P", "C", [row("2026-06-01", "20 °C", notes="dry")])
    got = vw.weather_for("P", "C")
    assert got["2026-06-01"]["temperature"] == "20 °C" and got["2026-06-01"]["wind"] == ""
    n = sqlite3.connect(db).execute("SELECT COUNT(*) FROM visit_weather").fetchone()[0]
    assert n == 1


def test_blank_rows_not_written_or_deleted(db):
    assert vw.save_weather("P", "", [row("2026-06-01"), row("2026-06-02", " ", "", "", "")]) == 0
    assert vw.weather_for("P", "") == {}
    vw.save_weather("P", "", [row("2026-06-01", "10 °C")])
    vw.save_weather("P", "", [row("2026-06-01")])
    assert vw.weather_for("P", "")["2026-06-01"]["temperature"] == "10 °C"


def test_missing_table(tmp_path, monkeypatch):
    p = tmp_path / "o.db"
    sqlite3.connect(p).close()
    monkeypatch.setattr(paths, "OBSERVATUM_DB", p)
    monkeypatch.setattr("shared.away_mode.away_active", lambda: False)
    assert not vw.table_ready()
    assert vw.weather_for("P", "C") == {}
    with pytest.raises(RuntimeError):
        vw.save_weather("P", "C", [row("2026-06-01", "1")])
    names = sqlite3.connect(p).execute("SELECT name FROM sqlite_master").fetchall()
    assert names == []


def test_away_refuses(db, monkeypatch):
    monkeypatch.setattr("shared.away_mode.away_active", lambda: True)
    with pytest.raises(RuntimeError):
        vw.save_weather("P", "C", [row("2026-06-01", "1")])
    assert vw.weather_for("P", "C") == {}


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _conn():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE entry_staging (id INTEGER PRIMARY KEY, job_id INT, species_name TEXT, date TEXT)")
    c.executemany("INSERT INTO entry_staging (job_id, species_name, date) VALUES (?,?,?)",
                  [(1, "a", "2026-07-02"), (1, "b", "2026-06-01"), (1, "c", "2026-07-02"),
                   (1, "d", ""), (2, "e", "2026-01-01")])
    return c


def test_dialog_lists_dates_and_saves(db, qapp, monkeypatch):
    from DataEntry.visit_weather_dialog import VisitWeatherDialog
    vw.save_weather("Proj", "Cl", [row("2026-05-05", "9 °C")])
    d = VisitWeatherDialog(_conn(), {"id": 1, "name": "J", "project": "Proj", "client": "Cl"})
    assert d.dates == ["2026-05-05", "2026-06-01", "2026-07-02"]
    assert [d.table.item(r, 0).text() for r in range(3)] == ["05/05/2026", "01/06/2026", "02/07/2026"]
    assert d.table.item(0, 1).text() == "9 °C"
    assert d.save_btn.isEnabled()
    d.table.item(1, 2).setText("Beaufort 2")
    seen = {}
    monkeypatch.setattr(vw, "save_weather", lambda p, c, rows: seen.update(p=p, c=c, rows=rows))
    d._save()
    assert seen["p"] == "Proj" and seen["c"] == "Cl"
    assert seen["rows"][1] == row("2026-06-01", wind="Beaufort 2")


def test_dialog_project_falls_back_to_name_and_disables(tmp_path, qapp, monkeypatch):
    from DataEntry.visit_weather_dialog import MISSING_MSG, VisitWeatherDialog
    p = tmp_path / "o.db"
    sqlite3.connect(p).close()
    monkeypatch.setattr(paths, "OBSERVATUM_DB", p)
    monkeypatch.setattr("shared.away_mode.away_active", lambda: False)
    d = VisitWeatherDialog(_conn(), {"id": 1, "name": "Job name", "project": "", "client": None})
    assert d.project == "Job name" and d.client == ""
    assert not d.save_btn.isEnabled() and d.note.text() == MISSING_MSG


def test_dialog_away_disables(db, qapp, monkeypatch):
    from DataEntry.visit_weather_dialog import VisitWeatherDialog
    monkeypatch.setattr("shared.away_mode.away_active", lambda: True)
    d = VisitWeatherDialog(_conn(), {"id": 1, "name": "J", "project": "P", "client": ""})
    assert not d.save_btn.isEnabled() and "Away" in d.note.text()


@pytest.mark.parametrize("col,typed,stored", [
    (1, "30 - 32", "30–32 °C"), (1, "30-32 °C", "30–32 °C"), (1, "18C", "18 °C"),
    (2, "1 - 2", "Beaufort 1–2"), (2, "Beaufort 3-4", "Beaufort 3–4"), (2, "beaufort 2", "Beaufort 2"),
    (3, "1 - 3", "1–3 oktas"), (3, "2 - 6 Oktas", "2–6 oktas"), (3, "1", "1 okta"),
    (1, "", ""), (4, "traps set 1 - 2", "traps set 1 - 2"),
])
def test_unit_added(col, typed, stored):
    from DataEntry.visit_weather_dialog import with_unit
    assert with_unit(col, typed) == stored
    assert with_unit(col, stored) == stored            # never added twice


def test_dialog_adds_unit_when_cell_left(db, qapp):
    from DataEntry.visit_weather_dialog import VisitWeatherDialog
    d = VisitWeatherDialog(_conn(), {"id": 1, "name": "J", "project": "Proj", "client": "Cl"})
    d.table.item(0, 1).setText("30 - 32")
    d.table.item(0, 2).setText("1 - 2")
    d.table.item(0, 3).setText("1 - 3")
    assert [d.table.item(0, c).text() for c in (1, 2, 3)] == [
        "30–32 °C", "Beaufort 1–2", "1–3 oktas"]
