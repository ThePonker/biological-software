"""Lector stage B (12 Oct 2026): the desktop window (Lector/ui), offscreen.

No network: BHL is test_lector_a's FakeBHL (a slow one where a run must be caught
mid-way). Databases are temp files. No assertion depends on how wide a font
measures ("wide" doubles the letter spacing, as tests/test_window_width_r4.py).
"""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QPushButton  # noqa: E402
from test_lector_a import BRITISH, FakeBHL, _page, make_uksi  # noqa: E402


class SlowBHL(FakeBHL):
    """Each request takes a little while, so a run can be cancelled or closed mid-way."""
    delay = 0.05

    def name_metadata(self, name):
        time.sleep(self.delay)
        return super().name_metadata(name)

    def page_metadata(self, pid):
        time.sleep(self.delay)
        return super().page_metadata(pid)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def pump(qapp, until=None, timeout=10.0):
    """Process events (and deferred deletes) until until() is true or the time runs out."""
    from PySide6.QtCore import QEvent
    end = time.time() + timeout
    while True:
        qapp.processEvents()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        if until is None or until():
            return True
        if time.time() > end:
            return False
        time.sleep(0.01)


def make_env(tmp_path, client=None):
    from Lector.service import LectorService
    uksi = tmp_path / "uksi.db"
    make_uksi(uksi)
    fake = client or FakeBHL()
    svc = LectorService(db_path=tmp_path / "lector.db", uksi_db=uksi,
                        client_factory=lambda: fake, export_dir=tmp_path / "exports",
                        synonym_file=tmp_path / "syn.txt", backup_dir=tmp_path / "bk")
    return svc, fake


def make_window(qapp, svc):
    from Lector.ui.app import LectorWindow
    win = LectorWindow(svc, quiet=True)
    win.resize(1440, 900)
    win.show()
    assert win.start() is True
    pump(qapp)
    return win


@pytest.fixture
def env(tmp_path):
    return make_env(tmp_path)


@pytest.fixture
def window(qapp, env):
    win = make_window(qapp, env[0])
    yield win
    win.tasks.cancel()
    win.tasks.wait(5000)
    win.close()
    win.deleteLater()
    pump(qapp)


def run_and_wait(qapp, win, start):
    assert start() is not False
    assert pump(qapp, lambda: not win.tasks.busy)


# --- service additions (stage B) -----------------------------------------------------
def test_preview_draft_matches_saved_preview_and_counts_every_name(env):
    svc, fake = env
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    s = svc.get_search(sid)
    assert svc.preview_draft(s["names"], s["filters"]) == dict(
        svc.preview(sid), name_found=svc.preview_draft(s["names"], s["filters"])["name_found"])
    off = svc.preview_draft(s["names"], s["filters"])
    assert off["not_counted"] == ["Lamia textor", "Cerambyx textor"] and fake.request_count == 0
    on = svc.preview_draft(s["names"], s["filters"], use_network=True)
    # held-back names are counted for the builder, but only ticked names make the totals
    assert set(on["name_found"]) == {n["name"] for n in s["names"]}
    assert on["name_found"]["Lamia textor"] == 9 and on["found"] == 10
    assert on == dict(svc.preview(sid), name_found=on["name_found"])
    assert svc.default_filters()["max_pages"] == 500
    svc.default_filters()["include_words"].append("x")          # a copy, not the default
    assert svc.default_filters()["include_words"] == []
    assert [n["name"] for n in svc.family_names("Cerambycidae")] == [
        "Lamia textor", "Monochamus sutor", "Monochamus sartor", "Rhagium mordax"]


# --- every screen builds ----------------------------------------------------------------
def test_each_screen_builds(qapp, window, env):
    svc, _fake = env
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    for key, kw in (("searches", {}), ("builder", {"search_id": None}),
                    ("builder", {"search_id": sid}), ("history", {"search_id": sid}),
                    ("review", {"search_id": sid}), ("records", {}),
                    ("export", {"search_id": sid})):
        screen = window.go(key, **kw)
        pump(qapp)
        assert window.current() is screen
    assert window.messages == []
    dash = window.screens["searches"]
    window.go("searches")
    assert dash.table.rowCount() == 1 and dash.cards["pages_harvested"]._value_label.text() == "7"
    assert window.nav_buttons["searches"].isChecked()


# --- create a search, end to end -------------------------------------------------------
def test_create_search_flow(qapp, window, env):
    svc, fake = env
    b = window.go("builder", search_id=None)
    b.species_edit.setText("lamia textor")
    b.find_species()
    assert "NBNSYS0000011050" in b.matched.text()
    names = {n["name"]: n for n in b.names.names()}
    assert names["Lamia textor"]["included"] and names["Cerambyx textor"]["included"]
    assert not names["Lamia sutor"]["included"]
    assert "epithet is current in Monochamus sutor" in names["Lamia sutor"]["held_back_reason"]
    assert b.preview_values["found"].text() == "0"
    assert "Not counted yet" in b.preview_note.text()
    assert b.names.add_name("Lamia textrix") and not b.names.add_name("lamia TEXTRIX")
    b.filters.set_filters(dict(svc.default_filters(), **BRITISH))
    progress = []
    window.tasks.progressed.connect(lambda *a: progress.append(a))
    run_and_wait(qapp, window, b.refresh_counts)                  # BHL in the worker
    assert b.preview_values["found"].text() == "10"
    assert b.names._checks["Lamia textor"][1].text() == "9 pages"
    assert progress and progress[-1][0] == "count"
    b.names.remember.setChecked(True)
    b.names._toggle("Lamia sartor", True)                          # confirm a held-back name
    sid = b.save(run=True)                                         # -> history, runs
    assert sid and window.current() is window.screens["history"]
    assert pump(qapp, lambda: not window.tasks.busy)
    h = window.screens["history"]
    assert h.runs and h.runs[0]["status"] == "done" and "Run 1 finished" in h.status_line.text()
    s = svc.get_search(sid)
    assert [n["name"] for n in s["names"] if n["included"]] == [
        "Lamia textor", "Cerambyx textor", "Lamia sartor", "Lamia textrix"]
    assert s["filters"]["include_words"] == BRITISH["include_words"]
    lines = (env[0].synonym_file).read_text(encoding="utf-8").splitlines()
    assert "+ Lamia sartor @ Lamia textor | chosen in Lector" in lines
    assert "+ Lamia textrix @ Lamia textor | chosen in Lector" in lines
    assert ("page", 101) in fake.asked


def test_builder_needs_species_and_a_ticked_name(qapp, window):
    b = window.go("builder", search_id=None)
    assert b.save() is None and "Find first" in window.messages[-1]
    b.species_edit.setText("Lamia nonexistens")
    b.find_species()
    assert "not in UKSI" in b.matched.text()
    b.species_edit.setText("Lamia textor")
    b.find_species()
    for n in b.names.ticked():
        b.names._toggle(n, False)
    assert b.save() is None and "Tick at least one" in window.messages[-1]


def test_cancel_stops_a_run(qapp, tmp_path):
    svc, fake = make_env(tmp_path, SlowBHL())
    win = make_window(qapp, svc)
    try:
        sid = svc.create_search("Lamia textor", filters=BRITISH)
        win.go("history", search_id=sid, run="fetch")
        assert win.tasks.busy and win.task_bar.isVisible()
        assert pump(qapp, lambda: fake.request_count >= 3)
        win.cancel_task()
        assert pump(qapp, lambda: not win.tasks.busy)
        assert svc.list_runs(sid)[0]["status"] == "cancelled"
        assert "cancelled" in win.screens["history"].status_line.text()
        assert not win.task_bar.isVisible()
    finally:
        win.close()
        pump(qapp, lambda: not win.tasks.busy)


def test_run_history_shows_new_and_withdrawn(qapp, window, env):
    svc, fake = env
    sid = svc.create_search("Lamia textor", filters=BRITISH, with_synonyms=False)
    h = window.go("history", search_id=sid, run="fetch")
    assert pump(qapp, lambda: not window.tasks.busy)
    assert "first run" in h.settings_changed.text()
    # a newly scanned page and a narrower filter
    fake.names["Lamia textor"][0]["Titles"][0]["Items"][1]["Pages"].append(_page(110, 302))
    fake.texts[110] = "More on Lamia textor at Rannoch."
    svc.update_search(sid, filters={"to_year": 1930})
    h.refresh_check.setChecked(True)
    run_and_wait(qapp, window, lambda: h.run("fetch"))
    d = h.diff
    assert [p["page_id"] for p in d["new"]] == [110]
    assert [p["page_id"] for p in d["withdrawn"]] == [109]
    assert h.tabs.tabText(0) == "New (1)" and h.tabs.tabText(1) == "No longer matched (1)"
    assert "to year: any" in h.settings_changed.text()
    keep = h.tables["withdrawn"].cellWidget(0, 2)
    keep.click()
    assert h.tables["withdrawn"].cellWidget(0, 2).text() == "Kept"
    assert 109 in {i["page_id"] for i in svc.review_queue(sid)}
    h._read_row("new", 0)
    r = window.screens["review"]
    assert window.current() is r and r.current_item()["page_id"] == 110


def test_search_without_recorded_filters_asks_for_them(qapp, window, env):
    """Searches made from fetches before 12 Oct have no filters: set them, then run."""
    svc, _fake = env
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid, mode="count")
    svc.update_search(sid, filters={"recorded": False})
    dash = window.go("searches")
    texts = [b.text() for b in dash.table.cellWidget(0, 5).findChildren(QPushButton)]
    assert "Set filters" in texts and "Run again" not in texts
    h = window.go("history", search_id=sid)
    assert h.run("fetch") is False and window.current() is window.screens["builder"]
    assert "Set its filters" in window.messages[-1]
    window.screens["builder"].save(run=True)
    assert pump(qapp, lambda: not window.tasks.busy)
    assert svc.list_runs(sid)[0]["mode"] == "fetch" and svc.list_runs(sid)[0]["status"] == "done"


# --- reading list -------------------------------------------------------------------------
def test_review_status_tag_notes_persist(qapp, window, env):
    svc, _fake = env
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    r = window.go("review", search_id=sid, status="all")
    first = r.current_item()["page_id"]
    keys = {sc.key().toString(): sc for sc in r.shortcuts}
    keys["2"].activated.emit()                          # not relevant, and on to the next page
    assert r.current_item()["page_id"] != first
    keys["K"].activated.emit()
    r.panel.tag_buttons["mention"].click()
    r.panel.notes.setPlainText("Probably a misidentification")
    keys["J"].activated.emit()                                      # next page saves the notes
    assert r.current_item()["page_id"] != first
    keys["K"].activated.emit()
    assert r.current_item()["page_id"] == first
    q = {i["page_id"]: i for i in svc.review_queue(sid)}
    assert q[first]["review_status"] == "not_relevant" and q[first]["review_tag"] == "mention"
    assert q[first]["notes"] == "Probably a misidentification"
    # autosave without leaving the page
    def notes_of(pid):
        return {i["page_id"]: i for i in svc.review_queue(sid)}[pid]["notes"]
    r.panel.notes.setPlainText("Second thoughts")
    assert notes_of(first) == "Probably a misidentification"       # not yet: a pause first
    assert pump(qapp, lambda: notes_of(first) == "Second thoughts", timeout=3)
    keys["3"].activated.emit()                          # record extracted, and on (Round 8)
    assert {i["page_id"]: i for i in svc.review_queue(sid)}[first]["review_status"] == \
        "record_extracted"
    assert r.current_item()["page_id"] != first
    assert f"1 of {len(r.items)} reviewed" in r.subtitle.text()
    # filter list: Show = Record extracted
    r.show_box.setCurrentIndex(r.show_box.findData("record_extracted"))
    r.reload()
    assert [i["page_id"] for i in r.shown] == [first]


def test_review_shows_names_bold_copies_and_copyright(qapp, window, env):
    svc, _fake = env
    sid = svc.create_search("Lamia textor", filters=dict(BRITISH, include_words=[]))
    svc.run_search(sid)
    r = window.go("review", search_id=sid, status="all")
    items = {i["page_id"]: i for i in r.items}
    grouped = next(i for i in items.values() if i["copies"])
    r.reload(grouped["page_id"])
    assert "<b>" in r.page.text.toHtml() or "font-weight" in r.page.text.toHtml()
    assert "Same text also at" in r.page.copies.text()
    late = next(i for i in items.values() if (i["year"] or 0) > 1930)
    r.reload(late["page_id"])
    assert r.page.copyright.isVisibleTo(r.page) and "copyright" in r.page.copyright.text()
    r.page.toggle_full()
    assert "Show excerpts" == r.page.full_btn.text()


# --- export ---------------------------------------------------------------------------------
def test_export_writes_files(qapp, window, env):
    svc, _fake = env
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    e = window.go("export", search_id=sid)
    info = svc.settings_info()
    for fmt, cb in e.fmt_checks.items():
        cb.setChecked(fmt in ("txt", "docx", "xlsx") and cb.isEnabled())
    run_and_wait(qapp, window, e.export)
    files = {x["kind"]: x["path"] for x in svc.list_exports(sid)}
    assert os.path.exists(files["txt"])
    if info["docx_available"]:
        assert os.path.exists(files["docx"]) and "DOCX:" in e.result.text()
    if info["docx_available"] and info["xlsx_available"]:
        assert os.path.exists(files["xlsx"])
    assert e.exports.count() >= 1 and "pages" in e.exports.item(0).text()


def test_export_explains_missing_packages(qapp, window, env, monkeypatch):
    svc, _fake = env
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    real = svc.settings_info()
    monkeypatch.setattr(svc, "settings_info", lambda: dict(real, docx_available=False,
                                                            xlsx_available=False))
    e = window.go("export", search_id=sid)
    assert not e.fmt_checks["docx"].isEnabled() and not e.fmt_checks["xlsx"].isEnabled()
    assert "pip install python-docx" in e.fmt_notes["docx"].text()
    assert "pip install" in e.fmt_notes["xlsx"].text()
    assert e.fmt_checks["txt"].isChecked()


# --- database update ---------------------------------------------------------------------
def test_older_database_is_updated_only_after_asking(qapp, env, monkeypatch):
    from Lector.ui.app import LectorWindow
    svc, _fake = env
    report = {"before": {"pages": 3}, "after": {"pages": 3, "saved_searches": 1},
              "searches_made": [{"search_id": 1, "name": "Lamia textor",
                                 "names": ["Lamia textor"], "pages": 3}], "backup": None}
    done = []
    monkeypatch.setattr(svc, "needs_update", lambda: report)
    monkeypatch.setattr(svc, "update_database",
                        lambda: done.append(1) or dict(report, backup="x.db", applied=True))
    win = LectorWindow(svc, quiet=True)
    win.answers = [False]
    assert win.start() is None and done == []                     # declined: nothing changed
    assert "dry run" in win.messages[0] and "saved_searches: - -> 1" in win.messages[0]
    assert "Nothing has been changed" in win.messages[-1]
    win.answers = [True]
    assert win.start() is True and done == [1]
    assert "x.db" in win.messages[-1]
    win.close()


# --- window size and closing ---------------------------------------------------------------
@pytest.fixture
def metrics_font(qapp, request):
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    before = QFont(QApplication.font())
    if getattr(request, "param", "default") == "wide":
        f = QFont(before)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 200)
        QApplication.setFont(f)
    yield
    QApplication.setFont(before)


@pytest.mark.parametrize("metrics_font", ["default", "wide"], indirect=True)
def test_window_fits_1280x720(qapp, metrics_font, tmp_path):
    svc, _fake = make_env(tmp_path)
    sid = svc.create_search("Lamia textor", filters=dict(BRITISH, journal_preset=None))
    svc.run_search(sid)
    svc.create_search("Cerambycidae", kind="family")
    win = make_window(qapp, svc)
    try:
        for key, kw in (("searches", {}), ("builder", {"search_id": sid}),
                        ("history", {"search_id": sid}), ("review", {"search_id": sid}),
                        ("records", {}), ("export", {"search_id": sid})):
            win.go(key, **kw)
            pump(qapp)
            hint = win.minimumSizeHint().expandedTo(win.minimumSize())
            assert hint.width() <= 1280 and hint.height() <= 720, (key, hint)
        win.resize(1280, 720)
        pump(qapp)
        assert (win.width(), win.height()) == (1280, 720)
    finally:
        win.close()


def test_closing_during_a_run_cancels_and_closes(qapp, tmp_path):
    svc, fake = make_env(tmp_path, SlowBHL())
    win = make_window(qapp, svc)
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    win.go("history", search_id=sid, run="fetch")
    assert pump(qapp, lambda: fake.request_count >= 2)
    win.answers = [True]                                           # "Stop and close" (Round 8)
    assert win.close() is False                                    # waits for the run to stop
    assert "A run is still going" in win.messages[-1]
    assert pump(qapp, lambda: not win.isVisible() and not win.tasks.busy)
    assert svc.list_runs(sid)[0]["status"] == "cancelled"
    n = fake.request_count
    pump(qapp, timeout=0.3)
    assert fake.request_count == n                                 # nothing more asked


# --- launchers ---------------------------------------------------------------------------------
def test_atrium_lector_tile_opens_the_window(qapp, monkeypatch):
    from Atrium import process_manager as pm
    from Atrium.atrium_ui import ASSETS, AtriumPanel
    from Lector.ui.app import WINDOW_TITLE
    panel = AtriumPanel()
    tile = next(b for b in panel._buttons if b._app.name == "Lector")
    app = tile._app
    assert app.module == "Lector" and app.args == ("gui",) and not app.console
    assert app.window_title == WINDOW_TITLE and app.icon_file == "book.png"
    assert (ASSETS / "book.png").exists()
    assert pm.command_for(app)[1:] == ["-m", "Lector", "gui"]
    started = []
    monkeypatch.setattr(pm.subprocess, "Popen", lambda cmd, **kw: started.append(cmd) or
                        type("P", (), {"poll": lambda self: None})())
    monkeypatch.setattr(pm, "_visible_windows", lambda: [])
    monkeypatch.setattr(app, "process", None)
    assert pm.launch_app(app)[0] == pm.LAUNCHED and started[-1][1:] == ["-m", "Lector", "gui"]
    console = next(a for a in pm.APPS if a.name == "Lector console")
    assert console.console and pm.command_for(console)[2:4] == ["Atrium.console_launch", "Lector"]
    assert panel.lector_console_btn.text() == "Lector console"


def test_gui_launcher_and_command():
    from pathlib import Path

    from Lector.__main__ import build_parser
    root = Path(__file__).resolve().parents[1]
    bat = (root / "launchers" / "run_lector_gui.bat").read_text(encoding="ascii")
    assert "pyw -3.14 -m Lector gui" in bat and "PYTHONPATH=%CD%;%CD%\\Observatum" in bat
    args = build_parser().parse_args(["gui"])
    assert args.func.__name__ == "cmd_gui"
