# ruff: noqa: F811  (cli: a fixture imported from test_lector_a)
"""Round 8 review (12 Oct 2026): fixes found reviewing the merged Round 8, and R2a-c.

Offscreen, temp DBs (the real VC outline file read-only for the map check); no network
(test_lector_a's FakeBHL); no assertion depends on font metrics.
"""
import json
import math
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402
from test_lector_a import BRITISH, cli, make_uksi  # noqa: E402,F401
from test_lector_r8 import _migrated_the_old_way  # noqa: E402
from test_lector_ui import SlowBHL, make_env, make_window, pump  # noqa: E402

from Lector import saved  # noqa: E402
from Lector.store import LectorStore  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --- R2a: the VC boundary layer is the same before and after a first paint ------------------
def _km(chains):
    return sum(math.dist(c[i], c[i + 1]) for c in chains for i in range(len(c) - 1)) / 1000


@pytest.mark.skipif(not paths.VC_GEOJSON.exists(), reason="needs the VC outline file")
def test_vc_boundaries_not_taken_from_the_land_after_a_paint(qapp, tmp_path, monkeypatch):
    """With no gb_outline.json the land is the VC rings, and its coast split was cached
    under the VC boundary layer's key: after one paint (coast first) every map's VC
    boundaries were the land's unsnapped borders, each shared border twice."""
    from shared.maps import coast
    from shared.maps.grid_map import GridMap
    monkeypatch.setattr(coast, "_SPLIT_CACHE", {})
    m = GridMap(geojson_path=str(paths.VC_GEOJSON), maps_dir=str(tmp_path))  # no outline
    assert m._land_source[0] == "vc"
    m.resize(300, 400)
    m.grab()                                         # draws coast, then the VC boundaries
    after = m._chains("vc_inland")
    monkeypatch.setattr(coast, "_SPLIT_CACHE", {})
    fresh = GridMap(geojson_path=str(paths.VC_GEOJSON))._chains("vc_inland")
    assert round(_km(after)) == round(_km(fresh))
    seen = {}
    for c in after:
        for a, b in zip(c, c[1:]):
            k = (a, b) if a <= b else (b, a)
            seen[k] = seen.get(k, 0) + 1
    assert max(seen.values()) == 1


# --- R2b: "-" lines in your own synonym list -------------------------------------------------
def test_minus_line_reason_says_your_own_list(tmp_path):
    from Lector.species_source import UksiLookup
    from Lector.synonyms import SynonymRules, candidate_names, on_list
    make_uksi(tmp_path / "uksi.db")
    syn = tmp_path / "syn.txt"
    syn.write_text("- Cerambyx textor | doubtful\n", encoding="utf-8")
    u = UksiLookup(tmp_path / "uksi.db")
    try:
        from test_lector_a import TEXTOR
        names = {c["name"]: c for c in candidate_names(u, "Lamia textor", TEXTOR,
                                                       SynonymRules.load(syn, suite_csv=None))}
    finally:
        u.close()
    assert names["Cerambyx textor"]["held_back_reason"] == \
        "Held back: on your own list (doubtful)"
    assert on_list("suite corrections list") == "on the suite corrections list"


# --- R2c: the console leaves a saved search's names and filters alone ----------------------
def _search(tmp):
    st = LectorStore(tmp / "lector.db")
    try:
        sid = saved.find_search(st.conn, "Lamia textor")
        return sid, saved.get_search(st.conn, sid)
    finally:
        st.close()


def test_console_fetch_keeps_the_saved_search_unless_told(cli, capsys):
    m, _fake, tmp = cli
    m.main(["fetch", str(tmp / "sp.txt"), "--synonyms", "--include-title", "Annals",
            "--max-pages", "0"])
    assert "New saved search" in capsys.readouterr().out
    sid, s = _search(tmp)
    # in the window: Cerambyx textor unticked, filters changed to Entomologist
    st = LectorStore(tmp / "lector.db")
    names = [dict(n, included=n["name"] != "Cerambyx textor") for n in s["names"]]
    saved.set_names(st.conn, sid, names)
    saved.set_filters(st.conn, sid, {**s["filters"], "include_words": ["Entomologist"]})
    st.close()
    m.main(["fetch", str(tmp / "sp.txt"), "--synonyms", "--include-title", "Annals",
            "--max-pages", "0"])
    out = capsys.readouterr().out
    _sid, s2 = _search(tmp)
    assert s2["filters"]["include_words"] == ["Entomologist"]
    assert not {n["name"]: n for n in s2["names"]}["Cerambyx textor"]["included"]
    assert "kept as it is" in out and "--replace-search" in out
    assert "Filters: Your title words (1)" in out and "Cerambyx textor: not ticked" in out
    m.main(["fetch", str(tmp / "sp.txt"), "--synonyms", "--include-title", "Annals",
            "--max-pages", "0", "--replace-search"])
    out = capsys.readouterr().out
    _sid, s3 = _search(tmp)
    assert s3["filters"]["include_words"] == ["Annals"] and "replaced" in out
    assert {n["name"]: n for n in s3["names"]}["Cerambyx textor"]["included"]


def test_interactive_console_keeps_the_saved_search(cli, capsys, monkeypatch):
    m, _fake, tmp = cli
    m.main(["fetch", str(tmp / "sp.txt"), "--include-title", "Annals", "--max-pages", "0"])
    capsys.readouterr()
    answers = iter(["Lamia textor", "y", ""])
    monkeypatch.setattr("builtins.input", lambda _p="": next(answers))
    m.main([])
    out = capsys.readouterr().out
    _sid, s = _search(tmp)
    assert s["filters"]["include_words"] == ["Annals"] and "kept as it is" in out
    assert (tmp / "exports" / "Lamia_textor_all_pages.txt").exists()


def test_console_exports_do_not_overwrite_the_windows(cli, capsys):
    m, _fake, tmp = cli
    m.main(["fetch", str(tmp / "sp.txt"), "--include-title", "Annals", "--max-pages", "0"])
    m.main(["export", "--name", "Lamia textor"])
    out = tmp / "exports"
    assert (out / "Lamia_textor_all_pages.txt").exists()
    assert (out / "Lamia_textor_all_pages_index.csv").exists()
    assert not (out / "Lamia_textor.txt").exists()
    pytest.importorskip("docx")
    m.main(["export", "--name", "Lamia textor", "--docx"])
    assert (out / "Lamia_textor_all_pages_dossier.docx").exists()
    assert not (out / "Lamia_textor_dossier.docx").exists()


# --- review: keys 1-4 work while the page text has the focus --------------------------------
def test_keys_work_with_the_page_text_focused(qapp, tmp_path):
    svc, _fake = make_env(tmp_path)
    win = make_window(qapp, svc)
    try:
        sid = svc.create_search("Lamia textor", filters=BRITISH)
        svc.run_search(sid)
        r = win.go("review", search_id=sid, status="all")
        keys = {sc.key().toString(): sc for sc in r.shortcuts}
        win.activateWindow()
        r.page.text.setFocus()
        pump(qapp)
        from PySide6.QtWidgets import QApplication
        if QApplication.focusWidget() is not r.page.text:
            pytest.skip("no keyboard focus offscreen here")
        first = r.current_item()["page_id"]
        keys["1"].activated.emit()
        assert r.current_item()["page_id"] != first
    finally:
        win.close()


# --- review: "Stop and close" when the run ends while the question is open ------------------
def test_stop_and_close_after_the_run_ended_meanwhile(qapp, tmp_path):
    svc, fake = make_env(tmp_path, SlowBHL())
    win = make_window(qapp, svc)
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    win.go("history", search_id=sid, run="fetch")
    assert pump(qapp, lambda: fake.request_count >= 1)

    def answer_after_the_run(text, yes, no, title="Lector"):
        assert pump(qapp, lambda: not win.tasks.busy, 30)    # finished while asking
        return True                                         # "Stop and close"
    win.choose = answer_after_the_run
    win.close()
    assert pump(qapp, lambda: not win.isVisible(), 5)


# --- review: the fix script leaves a held-back name you ticked yourself ---------------------
def test_fix_script_leaves_a_held_back_name_you_ticked(tmp_path, capsys):
    from scripts import fix_lector_name_choices as fix
    make_uksi(tmp_path / "uksi.db")
    db = _migrated_the_old_way(tmp_path)
    with sqlite3.connect(db) as c:      # Lamia sartor: ticked by you in Edit (reason kept)
        c.execute("UPDATE search_names SET held_back_reason='Held back: epithet is current"
                  " in Monochamus sartor' WHERE name='Lamia sartor'")
        settings = json.loads(c.execute("SELECT settings FROM runs").fetchone()[0])
    assert "Lamia sartor" in settings["names"]
    kw = dict(db=db, uksi_db=tmp_path / "uksi.db", synonym_file=tmp_path / "syn.txt",
              backup_dir=tmp_path / "bk")
    fix.main(["--apply"], **kw)
    out = capsys.readouterr().out
    assert "untick 1 name " in out and "Lamia sutor" in out and "Lamia sartor  -" not in out
    with sqlite3.connect(db) as c:
        ticked = {r[0] for r in c.execute("SELECT name FROM search_names WHERE included=1")}
    assert "Lamia sartor" in ticked and "Lamia sutor" not in ticked


# --- review: the dashboard filter matches the Scope words ("Any journal") -------------------
def test_dashboard_filter_matches_the_scope_words(qapp, tmp_path):
    svc, _fake = make_env(tmp_path)
    win = make_window(qapp, svc)
    try:
        british = svc.create_search("Lamia textor", name="British", filters=BRITISH)
        anyj = svc.create_search("Lamia textor", name="Everything",
                                 filters={"include_words": [], "max_pages": 0})
        dash = win.go("searches")
        dash.filter_box.setText("any journal")
        shown = {s["search_id"] for r, s in enumerate(dash.rows)
                 if not dash.table.isRowHidden(r)}
        assert shown == {anyj} and british not in shown
    finally:
        win.close()


def test_page_without_text_points_to_fetch_missing_text(qapp):
    from Lector.ui.review_panes import PageView
    v = PageView(None)
    v.item = {"has_text": False}
    v._show_excerpts()
    assert "Fetch missing text" in v.text.toPlainText()
