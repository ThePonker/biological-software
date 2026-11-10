"""Lector Round 15 (25 Oct 2026): delete a search, remove not-relevant pages, hide not
relevant, fuzzy species suggestions, free-text searches, user tags, reading-list filters
and sorts, translate, and lector.db version 4.

No network (BHL is a fake; the free-text call is tested with a faked HTTP response).
Databases are temp files built with Lector's own schema; Wil's data is never opened.
"""
import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_lector_a import BRITISH, FakeBHL, _page, bhl_data  # noqa: E402
from test_lector_ui import make_env, make_window  # noqa: E402

from Lector import schema, upgrade  # noqa: E402
from Lector.bhl_client import BHLClient  # noqa: E402
from Lector.service import LectorError, LectorService  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_reading_filters():
    """Each test starts with no remembered reading-list filters: the remembered ones are keyed
    by search id, and every test's temp lector.db starts its ids at 1."""
    from shared.settings_store import app_settings
    st = app_settings()
    st.remove("lector/reading")
    st.sync()
    yield
    st.remove("lector/reading")
    st.sync()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def sutor_bhl():
    """The Lamia pages plus a second species whose list shares page 101 and has 2 of its own."""
    names, texts = bhl_data()
    names["Monochamus sutor"] = [{"Titles": [
        {"TitleID": 1, "FullTitle": "The Entomologist's monthly magazine", "Items": [
            {"ItemID": 10, "Volume": "v.7 (1870-1871)", "Year": "1870", "Pages": [_page(101, 81)]}]},
        {"TitleID": 9, "FullTitle": "The Entomologist's weekly", "Items": [
            {"ItemID": 90, "Volume": "1", "Year": "1850",
             "Pages": [_page(301, 5), _page(302, 6)]}]}]}]
    texts = {**texts, 301: "Monochamus sutor was taken at Perth.",
             302: "Monochamus sutor again, at Dunkeld."}
    return FakeBHL(names=names, texts=texts)


def two_searches(tmp_path):
    svc, fake = make_env(tmp_path, sutor_bhl())
    lam = svc.create_search("Lamia textor", name="Lamia", names=["Lamia textor"],
                            filters=dict(BRITISH, include_words=["Entomologist", "Annals"],
                                         skip_duplicates=False))
    sut = svc.create_search("Monochamus sutor", name="Sutor", names=["Monochamus sutor"],
                            filters=dict(BRITISH, include_words=["Entomologist"]))
    svc.run_search(lam)
    svc.run_search(sut)
    return svc, fake, lam, sut


def table(db, name):
    with sqlite3.connect(db) as c:
        return sorted(c.execute(f"SELECT * FROM {name}").fetchall(), key=repr)


def pages_of(svc, sid):
    return {i["page_id"]: i for i in svc.review_queue(sid, include_withdrawn=True)}


# --- 1. delete a search ------------------------------------------------------------------
def test_delete_search_removes_only_its_own_data(tmp_path):
    svc, _fake, lam, sut = two_searches(tmp_path)
    db = tmp_path / "lector.db"
    shared = 101
    assert shared in pages_of(svc, lam) and shared in pages_of(svc, sut)
    svc.set_review(lam, shared, status="relevant", notes="shared mark")
    own = next(p for p in pages_of(svc, sut) if p != shared)
    svc.set_review(sut, own, status="not_relevant", notes="mine")
    lam_pages, sut_pages = set(pages_of(svc, lam)), set(pages_of(svc, sut))
    texts_before = {r[0]: r[1] for r in table(db, "pages") and
                    sqlite3.connect(db).execute("SELECT page_id, ocr_text FROM pages")}
    runs_lam = table(db, "runs")
    info = svc.delete_search_preview(sut)
    assert info["pages"] == len(sut_pages) and info["pages_shared"] == 1
    assert info["marks"] == 1                       # page `own`; 101's mark is Lamia's, kept
    done = svc.delete_search(sut)
    bk = Path(done["backup"])
    assert bk.parent == tmp_path / "bk" and bk.name.startswith("lector_pre_delete_")
    with sqlite3.connect(bk) as c:                  # the backup is the file as it was
        assert c.execute("SELECT COUNT(*) FROM saved_searches").fetchone()[0] == 2
    assert [s["name"] for s in svc.list_searches()] == ["Lamia"]
    # the other search is untouched: pages, marks, runs
    assert set(pages_of(svc, lam)) == lam_pages
    assert pages_of(svc, lam)[shared]["review_status"] == "relevant"
    assert [r for r in table(db, "runs") if r[1] == lam] == [r for r in runs_lam if r[1] == lam]
    # every page row and text stays, also the deleted search's own pages
    with sqlite3.connect(db) as c:
        assert {r[0]: r[1] for r in c.execute("SELECT page_id, ocr_text FROM pages")} == \
            texts_before
        assert c.execute("SELECT COUNT(*) FROM runs WHERE search_id=?", (sut,)).fetchone()[0] == 0
        for t in ("search_names", "search_filters", "search_pages"):
            assert c.execute(f"SELECT COUNT(*) FROM {t} WHERE search_id=?", (sut,)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM run_pages WHERE run_id NOT IN"
                         " (SELECT run_id FROM runs)").fetchone()[0] == 0
        # the mark that belonged only to the deleted search is gone, Lamia's stays
        assert c.execute("SELECT COUNT(*) FROM page_hits WHERE accepted_name='Monochamus sutor'"
                         ).fetchone()[0] == 0
        assert c.execute("SELECT review_status FROM page_hits WHERE page_id=? AND"
                         " accepted_name='Lamia textor'", (shared,)).fetchone()[0] == "relevant"
    with pytest.raises(LectorError):
        svc.delete_search_preview(sut)


def test_delete_search_with_a_second_search_of_the_same_species_keeps_the_marks(tmp_path):
    svc, _fake = make_env(tmp_path)
    a = svc.create_search("Lamia textor", name="A", filters=BRITISH)
    svc.run_search(a)
    b = svc.duplicate_search(a, "B")
    svc.run_search(b)
    pid = next(iter(pages_of(svc, a)))
    svc.set_review(a, pid, status="relevant")
    assert svc.delete_search_preview(a)["marks"] == 0       # B holds the same pages and species
    svc.delete_search(a)
    assert pages_of(svc, b)[pid]["review_status"] == "relevant"


# --- 2. remove not-relevant pages ----------------------------------------------------------
def test_remove_not_relevant_touches_only_those_pages(tmp_path):
    svc, _fake, lam, sut = two_searches(tmp_path)
    db = tmp_path / "lector.db"
    def held_ids():
        with sqlite3.connect(db) as c:
            return {r[0] for r in c.execute("SELECT page_id FROM search_pages WHERE search_id=?"
                                            " AND state IN ('current','kept')", (lam,))}
    held = held_ids()
    assert {101, 102, 103, 104, 105} <= held
    svc.set_review(lam, 101, status="not_relevant")      # shared with Sutor: page stays
    svc.set_review(lam, 102, status="not_relevant")      # Lamia only: page and text go
    svc.set_review(lam, 103, status="relevant")
    svc.set_review(lam, 104, status="record_extracted")
    svc.set_review(lam, 105, notes="a note, still unreviewed")
    def state():
        with sqlite3.connect(db) as c:
            return {r[0]: (r[1], r[2]) for r in c.execute(
                "SELECT page_id, review_status, COALESCE(notes,'') FROM page_hits"
                " WHERE accepted_name='Lamia textor'")}
    before = state()
    info = svc.remove_not_relevant_preview(lam)
    assert info == {"search_id": lam, "pages": 2, "pages_shared": 1, "pages_deleted": 1}
    done = svc.remove_not_relevant(lam)
    assert Path(done["backup"]).name.startswith("lector_pre_remove_")
    assert Path(done["backup"]).parent == tmp_path / "bk"
    assert held_ids() == held - {101, 102}
    after = state()
    for p, v in after.items():                           # every other page exactly as it was
        assert v == before[p]
    assert set(after) == set(before) - {102}             # 101 keeps its row (Sutor holds it)
    with sqlite3.connect(db) as c:
        ids = {r[0] for r in c.execute("SELECT page_id FROM pages")}
        assert 102 not in ids and 101 in ids and {103, 104, 105} <= ids
        assert c.execute("SELECT COUNT(*) FROM page_hits WHERE page_id=102").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM run_pages WHERE page_id IN (101,102) AND run_id IN"
                         " (SELECT run_id FROM runs WHERE search_id=?)", (lam,)).fetchone()[0] == 0
    assert 101 in pages_of(svc, sut)                     # the other search still has it
    assert svc.remove_not_relevant_preview(lam)["pages"] == 0
    assert svc.remove_not_relevant(lam)["backup"] is None   # nothing to do, no backup made


def test_hide_not_relevant_is_on_by_default_and_toggles(qapp, tmp_path):
    svc, _fake = make_env(tmp_path)
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    win = make_window(qapp, svc)
    try:
        bad = next(iter(pages_of(svc, sid)))
        svc.set_review(sid, bad, status="not_relevant")
        r = win.go("review", search_id=sid, status="all")
        assert r.filters.hide_nr.isChecked()
        assert bad not in {i["page_id"] for i in r.shown}           # hidden...
        assert bad in {i["page_id"] for i in r.items}               # ...but kept
        assert bad in pages_of(svc, sid)
        r.filters.hide_nr.setChecked(False)
        assert bad in {i["page_id"] for i in r.shown}
        r.filters.hide_nr.setChecked(True)
        r.show_box.setCurrentIndex(r.show_box.findData("not_relevant"))
        r.reload()                                                  # asked for by status: shown
        assert [i["page_id"] for i in r.shown] == [bad]
    finally:
        win.close()


# --- 3. fuzzy suggestions ---------------------------------------------------------------------
def test_fuzzy_suggestions_tolerate_typos_and_partial_words(tmp_path):
    svc, _fake = make_env(tmp_path)
    first = lambda text: [s["name"] for s in svc.suggest_taxa(text)][:1]  # noqa: E731
    assert first("Lamia textor") == ["Lamia textor"]
    assert first("Lmaia textor") == ["Lamia textor"]          # letters swapped
    assert first("lamia tektor") == ["Lamia textor"]          # wrong letter
    assert first("monochamus sutr") == ["Monochamus sutor"]   # missing letter
    assert first("rhag mor") == ["Rhagium mordax"]            # partial words
    assert first("textor") == ["Lamia textor"]                # one word of the name
    names = [s["name"] for s in svc.suggest_taxa("monochamus")]
    assert set(names[:2]) == {"Monochamus sutor", "Monochamus sartor"}
    assert svc.suggest_taxa("z") == [] and svc.suggest_taxa("qqqqqq") == []
    assert all("score" in s and s["tvk"] for s in svc.suggest_taxa("lamia"))


def test_builder_offers_suggestions_under_the_species_box(qapp, tmp_path):
    svc, _fake = make_env(tmp_path)
    win = make_window(qapp, svc)
    try:
        b = win.go("builder", search_id=None)
        b.species_edit.setText("Lmaia textr")
        b.show_suggestions()
        assert b.completer.model().stringList()[0] == "Lamia textor"
        b._suggestion_chosen("Lamia textor")
        assert b.target["tvk"] and b.names.ticked()
    finally:
        win.close()


# --- 4. free-text search ------------------------------------------------------------------------
class FakeHTTP:
    """urlopen double: serves queued JSON bodies and remembers each URL."""
    def __init__(self, bodies):
        self.bodies, self.urls = list(bodies), []

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        body = json.dumps(self.bodies.pop(0)).encode()

        class Resp:
            def read(self_inner):
                return body

            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *a):
                return False
        return Resp()


def pub(i, kind="Item", **kw):
    base = {"BHLType": kind, "FoundIn": "Text", "ItemID": 1000 + i, "TitleID": 50,
            "Title": f"Book {i}", "Date": "1871", "Volume": "v.3",
            "ItemUrl": f"https://www.biodiversitylibrary.org/item/{1000 + i}"}
    if kind == "Part":
        base.update(PartID=7000 + i, Title="Notes from Rannoch", ContainerTitle="Scottish Naturalist",
                    Authors=[{"Name": "Waterhouse, E. A."}], FoundIn="Metadata",
                    PartUrl=f"https://www.biodiversitylibrary.org/part/{7000 + i}")
    return dict(base, **kw)


def test_client_publication_search_is_throttled_counted_and_paged(monkeypatch):
    import urllib.request
    bodies = [{"Status": "ok", "Result": [pub(i) for i in range(200)]},
              {"Status": "ok", "Result": [pub(300, "Part")]}]
    http = FakeHTTP(bodies)
    monkeypatch.setattr(urllib.request, "urlopen", http)
    client = BHLClient("KEY", interval=0.0)
    waits = []
    real = client._throttle
    client._throttle = lambda: (waits.append(1), real())
    from Lector import freetext
    pubs = freetext.search_term(client, "Waterhouse")
    assert client.request_count == 2 and len(waits) == 2          # one counted request a page
    q = dict(x.split("=", 1) for x in http.urls[0].split("?", 1)[1].split("&"))
    assert q["op"] == "PublicationSearch" and q["searchterm"] == "Waterhouse"
    assert q["searchtype"] == "F" and q["page"] == "1" and "page=2" in http.urls[1]
    assert len(pubs) == 201
    part = next(p for p in pubs if p["part_id"])
    assert part["page_id"] < 0 and part["authors"] == "Waterhouse, E. A."
    assert part["article_title"] == "Notes from Rannoch" and part["title"] == "Scottish Naturalist"
    assert part["page_url"].endswith("/part/7300") and part["year"] == 1871
    item = next(p for p in pubs if not p["part_id"])
    assert item["item_id"] == 1000 + 0 and item["page_url"].endswith("/item/1000")
    assert len({p["page_id"] for p in pubs}) == 201                # ids never collide


class FakeTextBHL(FakeBHL):
    def __init__(self):
        super().__init__()
        self.terms = []

    def publication_search(self, term, page=1):
        self.request_count += 1
        self.terms.append((term, page))
        return [pub(1), pub(2, "Part"), pub(3, FoundIn="Both")] if term == "Waterhouse" else []


def test_free_text_search_stores_publications_without_uksi_checks(tmp_path):
    fake = FakeTextBHL()
    svc = LectorService(db_path=tmp_path / "lector.db", uksi_db=tmp_path / "no_uksi.db",
                        client_factory=lambda: fake, export_dir=tmp_path / "x",
                        synonym_file=tmp_path / "syn.txt", backup_dir=tmp_path / "bk")
    sid = svc.create_search(None, name="Waterhouse", kind="text",
                            names=["Waterhouse", "Rannoch"], filters={"max_pages": 0})
    s = svc.get_search(sid)
    assert s["kind"] == "text" and [n["name"] for n in s["names"]] == ["Waterhouse", "Rannoch"]
    assert svc.list_searches()[0]["kind"] == "text"
    pre = svc.preview(sid, use_network=True)
    assert pre["found"] == 3 and pre["to_download"] == 0
    run = svc.run_search(sid)
    assert run["status"] == "done" and run["kept"] == 3 and run["name_requests"] == 2
    assert run["text_requests"] == 0 and not [a for a in fake.asked if a[0] == "page"]
    assert fake.terms.count(("Waterhouse", 1)) >= 1
    q = svc.review_queue(sid)
    assert len(q) == 3 and all(i["page_id"] < 0 and not i["has_text"] for i in q)
    assert {i["matched_names"] for i in q} == {"Waterhouse"}
    part = next(i for i in q if i["authors"])
    assert part["bhl_url"].endswith("/part/7002") and "found in Metadata" in part["page_type"]
    with sqlite3.connect(tmp_path / "lector.db") as c:
        row = c.execute("SELECT item_id, part_id, title_id FROM pages WHERE page_id<0 AND"
                        " part_id IS NOT NULL").fetchone()
        assert row == (1002, 7002, 50)
        assert c.execute("SELECT kind, text_search FROM saved_searches").fetchone() == ("list", 1)
    # nothing to download, and review marks work as for any page
    assert svc.list_searches()[0]["pages_without_text"] == 0
    assert svc.fetch_missing_text(sid)["missing"] == 0
    svc.set_review(sid, part["page_id"], status="relevant")
    assert svc.review_queue(sid, status="relevant")[0]["page_id"] == part["page_id"]
    calls = len(fake.terms)
    svc.run_search(sid, refresh=False)                                  # BHL's answer is reused
    assert len(fake.terms) == calls
    assert svc.preview_draft(["Waterhouse"], text=True)["found"] == 3


# --- 5. user tags -----------------------------------------------------------------------------
def test_user_tags_add_rename_hide_and_in_use_cannot_be_deleted(tmp_path):
    svc, _fake = make_env(tmp_path)
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    assert [t["key"] for t in svc.list_tags()] == ["record", "biology", "mention", "index"]
    key = svc.add_tag("  Specimen   data ")
    spare = svc.add_tag("Spare")
    with pytest.raises(LectorError):
        svc.add_tag("specimen data")                     # same name
    with pytest.raises(LectorError):
        svc.add_tag("Record")                            # a standard name
    pid = next(iter(pages_of(svc, sid)))
    svc.set_review(sid, pid, tag=key)
    assert pages_of(svc, sid)[pid]["review_tag"] == key
    assert pages_of(svc, sid)[pid]["review_tag_label"] == "Specimen data"
    svc.rename_tag(key, "Locality data")
    assert pages_of(svc, sid)[pid]["review_tag_label"] == "Locality data"
    assert pages_of(svc, sid)[pid]["review_tag"] == key         # the stored key never changes
    with pytest.raises(LectorError, match="hide it instead"):
        svc.delete_tag(key)                                      # in use: only hidden
    svc.hide_tag(key)
    assert key not in [t["key"] for t in svc.list_tags(include_hidden=False)]
    assert pages_of(svc, sid)[pid]["review_tag_label"] == "Locality data"
    svc.hide_tag(key, False)
    assert key in [t["key"] for t in svc.list_tags(include_hidden=False)]
    svc.delete_tag(spare)                                        # unused: can go
    assert spare not in [t["key"] for t in svc.list_tags()]
    for std in ("record", "index"):
        with pytest.raises(LectorError):
            svc.rename_tag(std, "x")
        with pytest.raises(LectorError):
            svc.hide_tag(std)
    with pytest.raises(LectorError):
        svc.set_review(sid, pid, tag="u99")                      # no such tag


def test_review_pane_and_manage_tags_dialog(qapp, tmp_path):
    from Lector.ui.tags_dialog import TagsDialog
    svc, _fake = make_env(tmp_path)
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    win = make_window(qapp, svc)
    try:
        r = win.go("review", search_id=sid, status="all")
        assert list(r.panel.tag_buttons) == ["record", "biology", "mention", "index"]
        dlg = TagsDialog(svc)
        dlg.edit.setText("Larval food plant")
        dlg.add()
        key = dlg.current()["key"]
        assert dlg.current()["label"] == "Larval food plant" and key.startswith("u")
        dlg.edit.setText("Host plant")
        dlg.rename()
        assert svc.list_tags()[-1]["label"] == "Host plant"
        assert dlg.rename_btn.isEnabled()
        r.panel.set_tags(svc.list_tags())
        assert list(r.panel.tag_buttons)[-1] == key
        r.panel.tag_buttons[key].click()                          # tag the current page
        assert r.current_item()["review_tag"] == key
        assert "Host plant" in r.list.currentItem().text()
        dlg.reload(key)
        assert not dlg.delete_btn.isEnabled()                     # in use
        dlg.toggle()
        assert svc.list_tags()[-1]["hidden"]
        r.panel.set_tags(svc.list_tags())
        r.panel.show_item(r.current_item())
        assert key in r.panel.tag_buttons                         # shown while a page carries it
        r.panel.show_item(None)
        assert key not in r.panel.tag_buttons
        assert {sc.key().toString() for sc in r.shortcuts} == {"J", "K", "1", "2", "3", "4"}
        # (the pane has no tag shortcuts, so none were added for the first nine tags)
    finally:
        win.close()


# --- 6. filters and sorts ----------------------------------------------------------------------------
def fake_items():
    def it(pid, year, title, status="unreviewed", tag=None, found=None, article=None, copies=0):
        return {"page_id": pid, "year": year, "title": title, "journal": title, "state": "current",
                "review_status": status, "review_tag": tag, "found_at": found,
                "article_title": article, "copies": [{}] * copies}
    return [it(1, 1870, "Zoologist", found="2026-10-03"), it(2, 1841, "Annals", "relevant", "record",
                                                              "2026-10-01", "Beetles", 1),
            it(3, None, "Annals", "not_relevant", found="2026-10-02"),
            it(4, 1900, "Naturalist", "record_extracted", "u1", None, "Aardvarks"),
            it(5, 1935, "Zoologist", found="2026-10-03")]


def test_filters_and_sorts_and_the_count_follows():
    from Lector.ui.reading_filters import (NO_TAG, count_text, filter_items, load_filters,
                                           save_filters, sort_items)
    items = fake_items()

    def ids(f, status="all"):
        return [i["page_id"] for i in sort_items(filter_items(items, f, status), "year")]
    base = {"hide_not_relevant": False}
    assert ids(base) == [2, 1, 4, 5, 3]                      # no year last
    assert ids(dict(base, from_year=1860, to_year=1910)) == [1, 4]
    assert ids(dict(base, from_year=1900)) == [4, 5]
    assert ids(dict(base, journals=["Annals", "Naturalist"])) == [2, 4, 3]
    assert ids(dict(base, tag="record")) == [2] and ids(dict(base, tag=NO_TAG)) == [1, 5, 3]
    assert ids(dict(base, hide_not_relevant=True)) == [2, 1, 4, 5]
    assert ids(dict(base, hide_not_relevant=True), "not_relevant") == [3]  # asked for: shown
    assert ids({"hide_not_relevant": True}, "relevant") == [2]
    srt = lambda k: [i["page_id"] for i in sort_items(items, k)]  # noqa: E731
    assert srt("year") == [2, 1, 4, 5, 3] and srt("year_desc") == [5, 4, 1, 2, 3]
    assert srt("journal") == [2, 3, 4, 1, 5]
    assert srt("title") == [4, 3, 2, 1, 5]                   # article title, else journal
    assert srt("found") == [2, 3, 1, 5, 4]                   # never found last
    shown = filter_items(items, dict(base, from_year=1860), "all")
    assert count_text(shown, items) == "3 of 6 pages"        # page 2 holds 2 scans
    assert count_text(items, items) == "6 of 6 pages"
    save_filters(987654, {"from_year": 1850, "journals": ["Annals"], "sort": "found"})
    got = load_filters(987654)
    assert got["from_year"] == 1850 and got["journals"] == ["Annals"] and got["sort"] == "found"
    assert got["hide_not_relevant"] is True and load_filters(987655)["from_year"] == 0


def test_reading_list_filters_are_remembered_per_search(qapp, tmp_path):
    svc, _fake = make_env(tmp_path)
    a = svc.create_search("Lamia textor", name="A", filters=dict(BRITISH, include_words=[]))
    svc.run_search(a)
    b = svc.duplicate_search(a, "B")
    svc.run_search(b)
    win = make_window(qapp, svc)
    try:
        r = win.go("review", search_id=a, status="all")
        total = len(r.shown)
        assert r.filters.count.text() == f"{total} of {total} pages".replace(
            str(total), str(sum(1 + len(i["copies"]) for i in r.shown)))
        r.filters.from_year.setValue(1900)
        n = len(r.shown)
        assert 0 < n < total and r.filters.count.text().startswith(
            f"{sum(1 + len(i['copies']) for i in r.shown)} of ")
        assert all((i["year"] or 0) >= 1900 for i in r.shown)
        r.order_box.setCurrentIndex(r.order_box.findData("year_desc"))
        r._filters_changed()
        years = [i["year"] for i in r.shown if i["year"]]
        assert years == sorted(years, reverse=True)
        win.go("review", search_id=b, status="all")
        assert r.filters.from_year.value() == 0 and len(r.shown) == total   # B has its own
        win.go("review", search_id=a, status="all")
        assert r.filters.from_year.value() == 1900 and r.order_box.currentData() == "year_desc"
        assert len(r.shown) == n
        r.filters.clear()
        assert len(r.shown) == total
        j = r.filters.menu.actions()
        assert j[0].text() == "All journals" and any("Entomologist" in a.text() for a in j)
    finally:
        win.close()


# --- 7. translate ----------------------------------------------------------------------------------------
def test_translate_url_is_cut_at_a_sentence():
    from urllib.parse import parse_qs, urlparse

    from Lector.translate import cut_at_sentence, translate_url
    url, cut = translate_url("Une courte phrase.")
    u = urlparse(url)
    q = parse_qs(u.query)
    assert (u.scheme, u.netloc) == ("https", "translate.google.com") and not cut
    assert q["sl"] == ["auto"] and q["tl"] == ["en"] and q["op"] == ["translate"]
    assert q["text"] == ["Une courte phrase."]
    long = "Ceci est une phrase assez longue. " * 300
    text, cut = cut_at_sentence(long)
    assert cut and len(text) <= 4500 and text.endswith("longue.") and long.startswith(text)
    assert parse_qs(urlparse(translate_url(long)[0]).query)["text"] == [text]
    assert cut_at_sentence("x" * 6000)[0] == "x" * 4500       # no break at all: cut at the limit


def test_translate_button_opens_the_browser_and_offers_the_rest(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication
    svc, fake = make_env(tmp_path)
    long = "Lamia textor fut pris au bois noir. " * 200
    fake.texts[101] = long
    sid = svc.create_search("Lamia textor", filters=BRITISH)
    svc.run_search(sid)
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    win = make_window(qapp, svc)
    try:
        r = win.go("review", search_id=sid, page_id=101, status="all")
        assert r.current_item()["page_id"] == 101
        r.page.translate_btn.click()
        assert len(opened) == 1 and opened[0].startswith("https://translate.google.com/?sl=auto&tl=en&text=")
        assert opened[0].endswith("&op=translate")
        assert r.page.translate_note.isVisibleTo(r.page) and "first part" in r.page.translate_note.text()
        assert r.page.copy_btn.isVisibleTo(r.page)
        r.page.copy_btn.click()
        assert QApplication.clipboard().text() == long
        r.reload(102)                                         # a short page: all of it, no note
        r.page.translate_btn.click()
        assert len(opened) == 2 and not r.page.translate_note.isVisibleTo(r.page)
        assert not r.page.copy_btn.isVisibleTo(r.page)
    finally:
        win.close()


# --- 8. schema version 4 --------------------------------------------------------------------------------------
def make_v3(path):
    """A lector.db as version 3 made it (Lector's own tables, without the version 4 ones)."""
    c = sqlite3.connect(path)
    c.executescript(schema.LEGACY)
    schema._add_columns(c, schema.NEW_COLUMNS)
    c.executescript(schema.V2)
    schema._add_columns(c, schema.V3_COLUMNS)
    c.execute("INSERT INTO saved_searches (name, target_name, kind, status, created)"
              " VALUES ('S','Lamia textor','species','active','2026-10-12T10:00:00')")
    c.execute("INSERT INTO search_names VALUES (1,'Lamia textor','accepted',1,NULL,'Lamia textor',"
              "'T1',0)")
    c.execute("INSERT INTO pages (page_id, title, year, ocr_text, fetched_at) VALUES"
              " (5,'Annals',1841,'Lamia textor here','2026-10-12T10:00:00')")
    c.execute("INSERT INTO page_hits (page_id, accepted_name, query_name, review_status, notes,"
              " review_tag) VALUES (5,'Lamia textor','Lamia textor','relevant','n','mention')")
    c.execute("INSERT INTO search_pages VALUES (1,5,'current','Lamia textor',NULL,NULL)")
    c.execute("INSERT INTO runs (search_id, started, mode, settings, status) VALUES"
              " (1,'2026-10-12T10:00:00','fetch','{}','done')")
    c.execute("PRAGMA user_version = 3")
    c.commit()
    c.close()


def test_version_4_dry_run_changes_nothing_and_apply_keeps_every_row(tmp_path):
    assert schema.VERSION == 4
    db = tmp_path / "lector.db"
    make_v3(db)
    old_tables = ["pages", "page_hits", "saved_searches", "search_names", "search_pages",
                  "runs", "search_filters", "searches"]
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    rows = {t: table(db, t) for t in old_tables}
    assert upgrade.status(db) == {"exists": True, "version": 3, "needs_update": True}
    rep = upgrade.dry_run(db)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest        # not one byte changed
    assert rep["applied"] is False and rep["backup"] is None
    assert rep["before"]["user_tags"] is None and rep["after"]["user_tags"] == 0
    assert rep["after"]["pages"] == rep["before"]["pages"] == 1
    assert "user_tags" in upgrade.format_report(rep)
    done = upgrade.apply(db, tmp_path / "bk")
    bk = Path(done["backup"])
    assert bk.name.startswith("lector_pre_v4_") and done["applied"] and bk.exists()
    assert hashlib.sha256(bk.read_bytes()).hexdigest() != ""
    with sqlite3.connect(bk) as c:                                      # the backup is version 3
        assert c.execute("PRAGMA user_version").fetchone()[0] == 3
    assert upgrade.status(db) == {"exists": True, "version": 4, "needs_update": False}
    with sqlite3.connect(db) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(saved_searches)")}
        assert "text_search" in cols
        assert c.execute("SELECT text_search FROM saved_searches").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM user_tags").fetchone()[0] == 0
    for t in old_tables:
        after = table(db, t)
        if t == "saved_searches":                  # the same rows, with the new column's 0 added
            after = [r[:-1] for r in after]
        if t == "runs":
            after = [r[:len(rows[t][0])] for r in after]
        assert after == rows[t], t
    svc = LectorService(db_path=db, uksi_db=tmp_path / "u.db", backup_dir=tmp_path / "bk")
    assert svc.get_search(1)["kind"] == "species" and svc.needs_update() is None
    assert svc.review_queue(1)[0]["review_tag"] == "mention"


def test_a_new_database_is_version_4_with_the_new_table(tmp_path):
    svc, _fake = make_env(tmp_path)
    svc.list_searches()
    with sqlite3.connect(tmp_path / "lector.db") as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 4
        assert c.execute("SELECT name FROM sqlite_master WHERE name='user_tags'").fetchone()


# --- review fix: what is deleted is worked out inside the transaction -------------------
def _slip_in(monkeypatch, db, action):
    """Run `action(connection)` from another connection just before the transaction starts:
    after the confirmation's estimate, as a run in another window could."""
    from Lector import removal
    real = removal._in_one_transaction

    def wrapped(conn, work):
        with sqlite3.connect(db) as other:
            action(other)
        return real(conn, work)
    monkeypatch.setattr(removal, "_in_one_transaction", wrapped)


def test_remove_not_relevant_uses_the_rows_found_inside_the_transaction(tmp_path, monkeypatch):
    svc, _fake, lam, _sut = two_searches(tmp_path)
    db = tmp_path / "lector.db"
    svc.set_review(lam, 102, status="not_relevant")
    assert svc.remove_not_relevant_preview(lam)["pages"] == 1

    def slip(c):          # another window marks 103 not relevant meanwhile
        c.execute("UPDATE page_hits SET review_status='not_relevant' WHERE page_id=103")
        c.commit()
    _slip_in(monkeypatch, db, slip)
    done = svc.remove_not_relevant(lam)
    assert done["estimate"]["pages"] == 1 and done["estimate_differed"]
    assert done["pages"] == 2                               # 102 and the one that slipped in
    with sqlite3.connect(db) as c:
        held = {r[0] for r in c.execute("SELECT page_id FROM search_pages WHERE search_id=?",
                                        (lam,))}
        assert 103 not in held and 102 not in held and 104 in held
    with sqlite3.connect(done["backup"]) as c:              # the backup holds the state deleted
        assert c.execute("SELECT review_status FROM page_hits WHERE page_id=103").fetchone()[0] \
            == "not_relevant"


def test_delete_search_uses_the_rows_found_inside_the_transaction(tmp_path, monkeypatch):
    svc, _fake, lam, sut = two_searches(tmp_path)
    db = tmp_path / "lector.db"
    own = next(p for p in pages_of(svc, sut) if p != 101)
    assert svc.delete_search_preview(sut)["marks"] == 0

    def slip(c):          # a mark is added meanwhile, and a new page link
        c.execute("UPDATE page_hits SET review_status='relevant', notes='late' WHERE page_id=?"
                  " AND accepted_name='Monochamus sutor'", (own,))
        c.commit()
    _slip_in(monkeypatch, db, slip)
    done = svc.delete_search(sut)
    assert done["estimate"]["marks"] == 0 and done["marks"] == 1 and done["estimate_differed"]
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM page_hits WHERE accepted_name='Monochamus sutor'"
                         ).fetchone()[0] == 0
    with sqlite3.connect(done["backup"]) as c:
        assert c.execute("SELECT notes FROM page_hits WHERE page_id=? AND accepted_name="
                         "'Monochamus sutor'", (own,)).fetchone()[0] == "late"
    monkeypatch.undo()
    (tmp_path / "again").mkdir()
    svc2, _f, a, _b = two_searches(tmp_path / "again")
    assert svc2.delete_search(a)["estimate_differed"] is False
