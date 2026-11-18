"""Round A: the Key Species benchmark -- default inclusion rule, saved choices, summary
statistics, refusal to save. Purpose-made databases only."""
import sqlite3

import pytest
from _round_a_fixture import RECORDS, add_committed, build

import paths
from Examen import benchmark as bm
from Examen import examen_data as ed
from Examen.examen_data import AnalysisMode

DDL = ("CREATE TABLE benchmark_choices (project_name TEXT NOT NULL, client TEXT NOT NULL DEFAULT '', "
       "survey_year TEXT NOT NULL DEFAULT '', included INTEGER NOT NULL, updated_at TEXT, "
       "PRIMARY KEY(project_name, client, survey_year))")
THREE = [(n, t, d, s, 22) for (n, t, _, s, _vc), d in
         zip(RECORDS[:3] + RECORDS[3:6], ["2026-05-10", "2026-06-11", "2026-07-12"] * 2)]


@pytest.fixture()
def world(tmp_path, monkeypatch):
    build(tmp_path, monkeypatch)
    add_committed(tmp_path, "Three Visits", "Acme", THREE)          # 3 dates, VC 22 (England)
    add_committed(tmp_path, "Two Visits", "Acme",
                  [(n, t, d, s, 22) for n, t, d, s, _ in RECORDS])        # 2 dates
    add_committed(tmp_path, "Welsh Three", "Acme", [(n, t, d, s, 41) for n, t, d, s, _ in THREE])
    return tmp_path


def _make_table(world):
    c = sqlite3.connect(str(paths.EXAMEN_DB))
    c.execute(DDL)
    c.commit()
    c.close()


def _by_name(rows):
    return {r["project"]: r for r in rows}


def test_default_rule(world):
    rows = _by_name(bm.benchmark_rows(AnalysisMode.CODEX_FULL))
    assert rows["Three Visits"]["country"] == "England" and rows["Three Visits"]["visits"] == 3
    assert rows["Three Visits"]["included"] is True
    assert rows["Two Visits"]["included"] is False                  # fewer than 3 visit dates
    assert rows["Welsh Three"]["country"] == "Wales" and rows["Welsh Three"]["included"] is False
    assert rows["Three Visits"]["type"] == bm.TYPE_NOT_RECORDED
    assert rows["Three Visits"]["pct"] is not None


def test_default_included_function():
    assert bm.default_included("England", 3)
    assert not bm.default_included("England", 2)
    assert not bm.default_included("Scotland", 5)
    assert not bm.default_included("England", 5, deadwood=True)
    assert not bm.default_included("England", 5, targeted=True)


def test_pct_equals_workbook_summary(world):
    from Examen.report_model import build_report
    detail = ed.load_project_detail("Three Visits", "Acme", survey_year="2026")
    rep = build_report(detail.analysis, detail, None, jurisdiction=detail.jurisdiction)
    fig = next(v for lab, v, _ in rep["figures"] if lab == "% Key Species (status only)")
    assert fig == f"{bm.status_only_pct(detail.analysis)}%"


def test_saved_choices_override_default(world):
    _make_table(world)
    c = sqlite3.connect(str(paths.EXAMEN_DB))
    c.executemany("INSERT INTO benchmark_choices VALUES (?,?,?,?,NULL)",
                  [("Three Visits", "Acme", "2026", 0), ("Two Visits", "Acme", "2026", 1)])
    c.commit()
    c.close()
    rows = _by_name(bm.benchmark_rows(AnalysisMode.CODEX_FULL))
    assert rows["Three Visits"]["included"] is False and rows["Three Visits"]["default"] is True
    assert rows["Two Visits"]["included"] is True and rows["Two Visits"]["default"] is False
    assert rows["Welsh Three"]["included"] is False


def test_summary_statistics_known_numbers():
    rows = [{"included": True, "pct": p} for p in (2.0, 4.0, 6.0, 8.0)]
    rows += [{"included": False, "pct": 99.0}, {"included": True, "pct": None}]
    s = bm.benchmark_summary(rows)
    assert (s["n"], s["median"], s["q1"], s["q3"], s["min"], s["max"]) == (4, 5.0, 3.5, 6.5, 2.0, 8.0)
    assert bm.summary_line(s) == "n = 4, median 5.0%, IQR 3.5–6.5%, range 2.0–8.0%"
    one = bm.benchmark_summary([{"included": True, "pct": 7.5}])
    assert (one["n"], one["q1"], one["q3"], one["median"]) == (1, 7.5, 7.5, 7.5)
    none = bm.benchmark_summary([])
    assert none["n"] == 0 and none["median"] is None
    assert bm.summary_line(none).startswith("n = 0")


def test_save_upserts_and_reads_back(world):
    _make_table(world)
    rows = bm.benchmark_rows(AnalysisMode.CODEX_FULL)
    for r in rows:
        if r["project"] == "Three Visits":
            r["included"] = False                                   # differs from default
    assert bm.save_choices(rows) == 1                               # only the changed one
    assert bm.load_choices() == {("Three Visits", "Acme", "2026"): False}
    for r in rows:
        if r["project"] == "Three Visits":
            r["included"] = True                                    # back to default: row kept, updated
    assert bm.save_choices(rows) == 1
    assert bm.load_choices() == {("Three Visits", "Acme", "2026"): True}


def test_save_refused_when_table_missing(world):
    rows = bm.benchmark_rows(AnalysisMode.CODEX_FULL)
    rows[0]["included"] = not rows[0]["included"]
    with pytest.raises(bm.BenchmarkError, match="add_report_tables"):
        bm.save_choices(rows)
    assert bm.load_choices() == {}


def test_save_refused_on_away_machine(world, monkeypatch):
    _make_table(world)
    monkeypatch.setattr("shared.away_mode.away_active", lambda: True)
    rows = bm.benchmark_rows(AnalysisMode.CODEX_FULL)
    rows[0]["included"] = not rows[0]["included"]
    with pytest.raises(bm.BenchmarkError, match="Away"):
        bm.save_choices(rows)
    assert bm.load_choices() == {}


def test_the_survey_being_reported_is_never_in_its_own_benchmark(world):
    cur = ("Three Visits", "Acme", "2026")
    rows = _by_name(bm.benchmark_rows(AnalysisMode.CODEX_FULL, current=cur))
    mine = rows["Three Visits"]
    assert mine["this_survey"] is True and mine["included"] is False and mine["default"] is True
    assert not any(r["this_survey"] for n, r in rows.items() if n != "Three Visits")
    summary = bm.benchmark_summary(list(rows.values()))
    assert summary["n"] == 0                                        # the only default survey was itself
    # a saved "include" choice does not bring it back, and it is never saved
    _make_table(world)
    plain = bm.benchmark_rows(AnalysisMode.CODEX_FULL)
    for r in plain:
        if r["project"] == "Two Visits":
            r["included"] = True
    bm.save_choices(plain)
    rows = bm.benchmark_rows(AnalysisMode.CODEX_FULL, current=cur)
    assert bm.benchmark_summary(rows)["n"] == 1
    for r in rows:
        r["included"] = True
    bm.save_choices(rows)
    assert ("Three Visits", "Acme", "2026") not in bm.load_choices()


def test_dialog_shows_this_survey_without_a_tick_box(world):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Examen.benchmark_dialog import THIS_SURVEY, BenchmarkDialog
    rows = bm.benchmark_rows(AnalysisMode.CODEX_FULL, current=("Three Visits", "Acme", "2026"))
    dlg = BenchmarkDialog(rows)
    i = next(i for i, r in enumerate(rows) if r["this_survey"])
    assert dlg.table.item(i, 1).text().endswith(THIS_SURVEY)
    assert not dlg.table.item(i, 0).flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert rows[i]["included"] is False
    assert dlg.summary.text().startswith("n = 0")
