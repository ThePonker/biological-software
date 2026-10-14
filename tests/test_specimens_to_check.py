"""Insect Collection > Specimens to check: tabs, Make record, Link, Change date, the live-db guard
(14 Oct 2026). A small purpose-made observatum.db; no live figures are pinned."""
import os
import shutil
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from Observatum.src.views.dialogs.specimens_to_check_dialog import SpecimensToCheckDialog  # noqa: E402
from shared import backup_service  # noqa: E402

OBS = ("id INTEGER PRIMARY KEY, species_name, species_tvk, date, grid_ref, recorder, site_name, "
       "record_type, project_name, client, embargo_status, embargo_until, quantity, sex, irecord_id")
SPEC = ("id INTEGER PRIMARY KEY, specimen_code, species_name, species_tvk, common_name, order_name, "
        "family, date_collected, grid_ref, site_name, collector, determiner, sex, observation_id, "
        "updated_at, no_field_record_checked")
ME = "Heeney, W.J."


def _spec(i, code, name, tvk, date, ref, site):
    return (i, code, name, tvk, None, None, None, date, ref, site, ME, None, None, None, None, None)


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "observatum.db"
    c = sqlite3.connect(p)
    c.execute(f"CREATE TABLE observations ({OBS})")
    c.execute(f"CREATE TABLE specimens ({SPEC})")
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        (10, "Zz zz", "T9", "2025-06-01", "SP123456", ME, "Wood", "Personal", None, None, None, None, 1, None, None),
        (11, "Bb bb", "T2", "2025-06-03", "SP123456", ME, "Wood", "Personal", None, None, None, None, 1, None, 555),
        (12, "Genus beta", "T7", "2025-07-01", "SP200200", ME, "Heath", "Personal", None, None, None, None, 1, None, None),
    ])
    c.executemany("INSERT INTO specimens VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
        _spec(1, "S1", "Aa aa", "T1", "2025-06-01", "SP123456", "Wood"),          # ready (2 specimens)
        _spec(2, "S2", "Aa aa", "T1", "2025-06-01", "SP123456", "Wood"),
        _spec(3, "S3", "Bb bb", "T2", "2025-06-01", "SP123456", "Wood"),          # near miss of obs 11
        _spec(5, "S5", "Cc cc", None, "2025-06-01", "SP123456", "Heath"),         # missing TVK
        _spec(6, "S6", "Genus alpha", "T6", "2025-07-01", "SP200200", "Heath"),   # re-identification
    ])
    c.commit()
    c.close()
    return p


@pytest.fixture
def win(db, monkeypatch):
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(backup_service, "backup_main_only", lambda label="": True)
    w = SpecimensToCheckDialog(str(db), None)
    w.messages = []
    w.info = w.messages.append
    w.confirm = lambda text: True
    return w


def _tab(w, key):
    from shared import specimens_to_check as stc
    w.tabs.setCurrentIndex(stc.KEYS.index(key))
    return w.tables[key]


def _q(db, sql, *a):
    c = sqlite3.connect(db)
    try:
        return c.execute(sql, a).fetchall()
    finally:
        c.close()


def test_tab_counts(win):
    assert {k: len(v) for k, v in win._rows.items()} == {
        "near": 1, "reid": 1, "ready": 1, "season": 0, "held": 1, "missing": 1, "onrow": 0}
    assert win.tabs.tabText(0) == "Near misses (1)"
    assert win._rows["ready"][0]["cells"][4] == 2          # quantity = specimens


def test_make_record_on_ready_item(win, db):
    t = _tab(win, "ready")
    t.selectRow(0)
    assert win.btn_make.isEnabled()
    win.make_record()
    assert len(_q(db, "SELECT id FROM entry_staging")) == 1
    assert sorted(r[0] for r in _q(db, "SELECT specimen_id FROM staging_specimens")) == [1, 2]
    assert len(win._rows["onrow"]) == 2 and len(win._rows["ready"]) == 0
    assert "Made 1 row(s) in Data Entry" in win.messages[-1]


def test_make_record_from_near_miss_asks_for_job(win, db):
    _tab(win, "near").selectRow(0)
    win.choose = lambda items: "Personal"
    win.make_record()
    assert _q(db, "SELECT specimen_id FROM staging_specimens") == [(3,)]


def test_link_sets_observation(win, db):
    _tab(win, "near").selectRow(0)
    win.pick_record = lambda spec: 11
    win.link_selected()
    assert _q(db, "SELECT observation_id FROM specimens WHERE id=3") == [(11,)]
    assert len(win._rows["near"]) == 0


def test_irecord_button_uses_irecord_id(win):
    _tab(win, "near").selectRow(0)
    assert win.btn_irecord.isEnabled()
    urls = []
    win.open_url = urls.append
    win.open_irecord()
    assert urls == ["https://irecord.org.uk/record-details?occurrence_id=555"]


def test_change_date_only_selected_and_refuses_mixed(win, db):
    t = _tab(win, "ready")
    t.selectRow(0)
    win.ask_date = lambda rows: "2025-06-02"
    win.change_visit_date()
    assert _q(db, "SELECT id, date_collected FROM specimens ORDER BY id") == [
        (1, "2025-06-02"), (2, "2025-06-02"), (3, "2025-06-01"), (5, "2025-06-01"),
        (6, "2025-07-01")]
    # a row standing for S5 (Heath) and S3 (Wood): two site names, refused
    win.ask_date = lambda rows: pytest.fail("should have refused")
    win.messages.clear()
    win._rows["missing"][0]["ids"] = [5, 3]
    _tab(win, "missing").selectRow(0)
    win.change_visit_date()
    assert "more than one site" in win.messages[-1]
    assert _q(db, "SELECT date_collected FROM specimens WHERE id IN (3,5)") == [("2025-06-01",)] * 2


def test_checked_sets_column(win, db):
    _tab(win, "missing").selectRow(0)
    assert win.btn_check.isEnabled()
    win.mark_checked()
    assert _q(db, "SELECT no_field_record_checked FROM specimens WHERE id=5")[0][0]


def test_writes_refused_on_copy(db, tmp_path, monkeypatch):
    other = tmp_path / "copy.db"
    shutil.copy(db, other)
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(backup_service, "backup_main_only", lambda label="": True)
    w = SpecimensToCheckDialog(str(other), None)
    w.messages = []
    w.info = w.messages.append
    w.confirm = lambda text: True
    w.pick_record = lambda spec: 11
    _tab(w, "near").selectRow(0)
    w.link_selected()
    _tab(w, "ready").selectRow(0)
    w.make_record()
    assert len(w.messages) == 2 and all("live database" in m for m in w.messages)
    assert _q(other, "SELECT observation_id FROM specimens WHERE id=3") == [(None,)]
    assert _q(other, "SELECT name FROM sqlite_master WHERE name='entry_staging'") == []


def test_dates_shown_day_first_and_sorted_as_dates(win):
    """14 Oct: dates read dd/mm/yyyy, as everywhere else in the suite."""
    import re
    texts = [win.tables[k].item(r, c).text() for k in win.tables for r in range(win.tables[k].rowCount())
             for c in range(win.tables[k].columnCount()) if win.tables[k].item(r, c)]
    assert any(re.fullmatch(r"\d{2}/\d{2}/\d{4}", t) for t in texts)
    assert not any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", t) for t in texts)
