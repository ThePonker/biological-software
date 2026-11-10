"""Lector Round 15b (25 Oct 2026): extracted records, the BHL key guide, the free-standing
install's data folder, searching without UKSI, and the manual's pictures.

No network (BHL is a fake). Databases are temp files built with Lector's own schema; Wil's
data is never opened. PyInstaller and Inno Setup are not run here: only the path logic they
rely on is tested.
"""
import ast
import csv
import hashlib
import os
import sqlite3
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_lector_a import BRITISH  # noqa: E402
from test_lector_round15 import make_v3, table  # noqa: E402
from test_lector_ui import make_env, make_window, pump  # noqa: E402

from Lector import config, records, schema, upgrade  # noqa: E402
from Lector.bhl_client import BHLError  # noqa: E402
from Lector.service import LectorError, LectorService  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


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


def lamia(tmp_path):
    svc, fake = make_env(tmp_path)
    sid = svc.create_search("Lamia textor", name="Lamia", filters=BRITISH)
    svc.run_search(sid)
    return svc, sid, {p["page_id"]: p for p in svc.review_queue(sid)}


def fields(svc, sid, pid, **kw):
    f = svc.record_prefill(sid, pid)
    f.update(kw)
    return f


# --- 1. extracted records ---------------------------------------------------------------
def test_schema_v4_has_the_records_table_and_a_new_db_is_still_version_4(tmp_path):
    assert schema.VERSION == 4
    svc, _sid, _pages = lamia(tmp_path)
    with sqlite3.connect(tmp_path / "lector.db") as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 4
        cols = {r[1] for r in c.execute("PRAGMA table_info(extracted_records)")}
    assert {"record_id", "page_id", "search_id", "species", "date_printed", "day", "month", "year",
            "place", "vice_county", "grid_ref", "recorder", "determiner", "count", "sex", "stage",
            "comment", "citation", "source_title", "source_volume", "source_page",
            "source_year", "bhl_url", "created", "updated"} <= cols


def test_save_list_edit_and_the_page_is_marked_record_extracted(tmp_path):
    svc, sid, pages = lamia(tmp_path)
    pid = 101
    pre = svc.record_prefill(sid, pid)
    assert pre["species"] == "Lamia textor" and pre["source_year"] == 1870
    assert "Entomologist" in pre["source_title"] and pre["bhl_url"] and pre["citation"]
    assert pages[pid]["review_status"] == "unreviewed"
    rid = svc.add_record(sid, pid, fields(
        svc, sid, pid, species="lamia textor", date_printed="14th June 1870", day=14, month=6,
        year=1870, place="Black Wood", vice_county=96, grid_ref="ns 2020", recorder="Mr Smith",
        count="two", sex="female", stage="adult", comment="on willow"))
    rec = svc.get_record(rid)
    assert rec["species"] == "Lamia textor" and rec["species_tvk"]       # UKSI's name and TVK
    assert rec["grid_ref"] == "NS2020" and rec["page_id"] == pid and rec["search_id"] == sid
    assert rec["created"] and rec["updated"] and rec["source_page"]
    again = svc.review_queue(sid)
    assert next(p for p in again if p["page_id"] == pid)["review_status"] == "record_extracted"
    r2 = svc.add_record(sid, pid, fields(svc, sid, pid, place="Another wood", year=1870))
    listed = svc.list_records()
    assert [r["record_id"] for r in listed] == [r2, rid]                 # several per page
    assert listed[0]["search_name"] == "Lamia"
    assert [r["record_id"] for r in svc.list_records(search_id=sid, year=1870)] == [r2, rid]
    assert svc.list_records(year=1900) == [] and svc.list_records(species="nothing") == []
    ch = svc.record_filter_choices()
    assert ch["species"] == ["Lamia textor"] and ch["years"] == [1870]
    assert ch["searches"] == [{"search_id": sid, "name": "Lamia"}]
    svc.update_record(rid, dict(rec, place="Black Wood, Rannoch", grid_ref="NN6057"))
    assert svc.get_record(rid)["place"] == "Black Wood, Rannoch"
    assert svc.get_record(rid)["grid_ref"] == "NN6057"
    assert svc.get_record(r2)["place"] == "Another wood"                 # the other untouched


def test_an_old_name_is_stored_as_the_current_one_and_kept_in_the_comment(tmp_path):
    svc, sid, _pages = lamia(tmp_path)
    rid = svc.add_record(sid, 101, fields(svc, sid, 101, species="Cerambyx textor", comment="x"))
    rec = svc.get_record(rid)
    assert rec["species"] == "Lamia textor" and "Name as printed: Cerambyx textor" in rec["comment"]


@pytest.mark.parametrize("bad, text", [
    ({"species": ""}, "species"),
    ({"grid_ref": "ZZ99"}, "grid reference"),
    ({"day": 31, "month": 2, "year": 1870}, "does not exist"),
    ({"day": 5}, "month and a year"),
    ({"month": 5}, "needs a year"),
    ({"month": 13, "year": 1870}, "between 1 and 12"),
    ({"vice_county": 200}, "between 1 and 112"),
    ({"year": "abc"}, "whole number"),
])
def test_a_field_that_fails_its_check_saves_nothing(tmp_path, bad, text):
    svc, sid, _pages = lamia(tmp_path)
    with pytest.raises(LectorError, match=text):
        svc.add_record(sid, 101, fields(svc, sid, 101, **bad))
    assert svc.list_records() == []
    assert next(p for p in svc.review_queue(sid) if p["page_id"] == 101)["review_status"] \
        == "unreviewed"


def test_remove_deletes_only_that_row_after_a_backup(tmp_path):
    svc, sid, _pages = lamia(tmp_path)
    a = svc.add_record(sid, 101, fields(svc, sid, 101, place="A"))
    b = svc.add_record(sid, 102, fields(svc, sid, 102, place="B"))
    db = tmp_path / "lector.db"
    keep = svc.get_record(b)
    other = {t: table(db, t) for t in ("pages", "page_hits", "search_pages", "saved_searches",
                                       "runs")}
    done = svc.remove_record(a)
    bk = Path(done["backup"])
    assert bk.parent == tmp_path / "bk" and bk.name.startswith("lector_pre_remove_record_")
    with sqlite3.connect(bk) as c:                       # the copy still has both records
        assert c.execute("SELECT COUNT(*) FROM extracted_records").fetchone()[0] == 2
    assert [r["record_id"] for r in svc.list_records()] == [b]
    assert svc.get_record(b) == keep
    for t, rows in other.items():                        # nothing else changed
        assert table(db, t) == rows, t
    with pytest.raises(LectorError):
        svc.remove_record(a)
    with pytest.raises(LectorError):
        svc.get_record(a)


# --- 2. the CSV against scripts/import_contributed.py -----------------------------------------
def importer_columns(header):
    """Run the importer's own heading matcher (its HEADINGS table and the loop that fills
    `col`, taken out of scripts/import_contributed.py without running the script)."""
    tree = ast.parse((ROOT / "scripts" / "import_contributed.py").read_text(encoding="utf-8-sig"))
    headings = next(ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "HEADINGS")
    loop = next(n for n in tree.body if isinstance(n, ast.For)
                and isinstance(n.iter, ast.Call) and getattr(n.iter.func, "id", "") == "enumerate"
                and getattr(n.iter.args[0], "id", "") == "header")
    ns = {"header": list(header), "col": {}, "HEADINGS": headings}
    exec(compile(ast.Module([loop], []), "import_contributed", "exec"), ns)  # noqa: S102
    return ns["col"]


def test_the_csv_columns_are_the_ones_the_importer_finds(tmp_path):
    svc, sid, _pages = lamia(tmp_path)
    svc.add_record(sid, 101, fields(
        svc, sid, 101, date_printed="14th June 1870", day=14, month=6, year=1870,
        place="Black Wood", grid_ref="NS2020", recorder="Mr Smith", determiner="Dr Jones",
        count="2", sex="f", stage="adult", comment="on willow", vice_county=96))
    svc.add_record(sid, 102, fields(svc, sid, 102, year=1841, count="several", species="Lamia textor"))
    out = svc.export_records_csv(tmp_path / "out" / "records.csv")
    assert out["rows"] == 2
    with (tmp_path / "out" / "records.csv").open(encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        rows = list(rd)
        header = rd.fieldnames
    assert tuple(header) == records.CSV_COLUMNS
    col = importer_columns(header)
    want = {"species": "species", "date": "date", "site": "site", "determiner": "determiner",
            "recorder": "recorder", "quantity": "count", "sex": "sex", "stage": "stage",
            "grid": "grid ref", "comment": "notes"}
    assert {k: header[i] for k, i in col.items()} == want            # none stolen by an extra column
    full = next(r for r in rows if r["date"] == "1870-06-14")
    assert full["species"] == "Lamia textor" and full["site"] == "Black Wood"
    assert full["grid ref"] == "NS2020" and full["count"] == "2" and full["determiner"] == "Dr Jones"
    assert "Date as printed: 14th June 1870" in full["notes"] and "on willow" in full["notes"]
    assert full["data_reference"].startswith("BHL: ") and "1870" in full["data_reference"]
    year_only = next(r for r in rows if r["date"] == "1841")
    assert year_only["count"] == "" and "Count as printed: several" in year_only["notes"]
    with pytest.raises(LectorError):
        svc.export_records_csv(tmp_path / "none.csv", year=1)             # nothing to export


# --- 3. schema v4 upgrade from v3 -----------------------------------------------------------------
def test_v3_upgrade_keeps_every_row_and_adds_the_records_table(tmp_path):
    db = tmp_path / "lector.db"
    make_v3(db)
    old = ["pages", "page_hits", "saved_searches", "search_names", "search_pages", "runs",
           "search_filters", "searches"]
    rows = {t: table(db, t) for t in old}
    digest = hashlib.sha256(db.read_bytes()).hexdigest()
    rep = upgrade.dry_run(db)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == digest
    assert rep["before"]["extracted_records"] is None and rep["after"]["extracted_records"] == 0
    assert "extracted_records" in upgrade.format_report(rep)
    done = upgrade.apply(db, tmp_path / "bk")
    assert Path(done["backup"]).name.startswith("lector_pre_v4_")       # still version 4, not 5
    with sqlite3.connect(db) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 4
        assert c.execute("SELECT COUNT(*) FROM extracted_records").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM user_tags").fetchone()[0] == 0
    for t in old:
        after = table(db, t)
        if t == "saved_searches":
            after = [r[:-1] for r in after]
        if t == "runs":
            after = [r[:len(rows[t][0])] for r in after]
        assert after == rows[t], t
    svc = LectorService(db_path=db, uksi_db=tmp_path / "u.db", backup_dir=tmp_path / "bk")
    rid = svc.add_record(1, 5, {"species": "Lamia textor", "place": "somewhere"})
    assert svc.get_record(rid)["place"] == "somewhere"


# --- 4. the BHL key guide ---------------------------------------------------------------------------
class KeyClient:
    def __init__(self, ok):
        self.ok = ok

    def check_key(self):
        if not self.ok:
            raise BHLError("GetLanguages: status='error' Invalid API key")
        return []


def key_service(tmp_path, ok=True, seen=None):
    def factory(key):
        if seen is not None:
            seen.append(key)
        return KeyClient(ok)
    svc, _fake = make_env(tmp_path)
    svc._key_client_factory = factory
    return svc


def test_the_key_test_asks_bhl_once_and_save_writes_the_file(tmp_path, monkeypatch, qapp):
    key_file = tmp_path / "data" / "bhl_api_key.txt"
    monkeypatch.setattr(config, "KEY_FILE", key_file)
    monkeypatch.delenv(config.API_KEY_ENV, raising=False)
    seen = []
    svc = key_service(tmp_path, True, seen)
    assert svc.settings_info()["api_key_set"] is False
    from Lector.ui.apikey_dialog import ApiKeyDialog
    dlg = ApiKeyDialog(svc, first_run=True)
    assert not dlg.test_btn.isEnabled() and not dlg.save_btn.isEnabled()
    dlg.key_edit.setText("  abc123  ")
    assert dlg.test_btn.isEnabled()
    assert dlg.test() is True and "accepted" in dlg.message.text() and seen == ["abc123"]
    assert not key_file.exists()                                  # testing saves nothing
    assert dlg.save() is True
    assert key_file.read_text(encoding="utf-8").strip() == "abc123" and dlg.saved
    assert svc.settings_info()["api_key_set"] is True
    assert config.load_api_key() == "abc123"
    assert "getapikey" in config.API_KEY_URL and dlg.open_btn.toolTip().endswith("in your browser")


def test_a_key_bhl_refuses_is_reported_and_a_blank_or_spaced_key_is_not_saved(tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(config, "KEY_FILE", tmp_path / "data" / "k.txt")
    svc = key_service(tmp_path, ok=False)
    from Lector.ui.apikey_dialog import ApiKeyDialog
    dlg = ApiKeyDialog(svc)
    dlg.key_edit.setText("badkey")
    assert dlg.test() is False and "did not accept" in dlg.message.text()
    dlg.key_edit.setText("two words")
    assert dlg.save() is False and not (tmp_path / "data" / "k.txt").exists()
    assert svc.test_api_key("") == {"ok": False, "message": "Paste the key into the box first."}


def test_the_window_offers_the_guide_only_without_a_key_and_the_menu_line_opens_it(
        tmp_path, monkeypatch, qapp):
    monkeypatch.setattr(config, "KEY_FILE", tmp_path / "none" / "key.txt")
    monkeypatch.delenv(config.API_KEY_ENV, raising=False)
    svc = key_service(tmp_path)
    win = make_window(qapp, svc)
    try:
        assert win.key_dialog is not None and win.key_link.text() == "BHL API key: not set"
        win.key_dialog = None
        win.key_link.click()
        assert win.key_dialog is not None                        # the menu foot opens it too
        monkeypatch.setenv(config.API_KEY_ENV, "fromenv")
        win.key_dialog = None
        win._update_nav_info()
        assert win.key_link.text() == "BHL API key: set"
        assert win.show_key_guide(first_run=True) is None        # a key is found: no guide
        assert win.show_key_guide() is not None                  # but the link still opens it
    finally:
        win.close()
        pump(qapp)


# --- 5. the free-standing install's data folder -------------------------------------------------------
def test_frozen_data_folder_is_documents_lector_data(tmp_path, monkeypatch):
    docs = tmp_path / "Documents"
    exe = tmp_path / "AppData" / "Local" / "Programs" / "Lector" / "Lector.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setitem(sys.modules, "paths", sys.modules["paths"])      # restored afterwards
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(config, "documents_dir", lambda: docs)
    monkeypatch.delenv(config.DATA_DIR_ENV, raising=False)
    assert config.frozen() and config._inside_suite() is None
    stub = config._import_paths()
    assert stub.DATA_DIR == docs / "Lector" / "data" and stub.DATA_DIR.is_dir()
    assert stub.UKSI_DB == docs / "Lector" / "data" / "uksi.db" and not stub.UKSI_DB.exists()
    assert stub.LECTOR_DB == stub.DATA_DIR / "lector.db" and stub.AWAY_MODE is False
    assert sys.modules["paths"] is stub                                # shared.* modules find it


def test_the_data_folder_can_be_chosen_and_an_existing_one_is_used_as_it_is(tmp_path, monkeypatch):
    mine = tmp_path / "mine"
    (mine).mkdir()
    (mine / "lector.db").write_bytes(b"keep")                          # not touched
    monkeypatch.setitem(sys.modules, "paths", sys.modules["paths"])
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "x" / "Lector.exe"))
    monkeypatch.setenv(config.DATA_DIR_ENV, str(mine))
    stub = config._import_paths()
    assert stub.DATA_DIR == mine and (mine / "lector.db").read_bytes() == b"keep"


def test_a_frozen_program_inside_the_suite_uses_the_suite(tmp_path, monkeypatch):
    suite = tmp_path / "Biological Software"
    (suite / "dist" / "Lector").mkdir(parents=True)
    (suite / "paths.py").write_text("DATA_DIR = None\n")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(suite / "dist" / "Lector" / "Lector.exe"))
    assert config._inside_suite() == suite.resolve()


def test_not_frozen_nothing_changes_and_documents_dir_is_a_real_folder_name():
    assert config.frozen() is False
    assert config.documents_dir().name == "Documents" or os.name == "nt"
    assert config.DATA_DIR == Path(sys.modules["paths"].DATA_DIR)


def test_the_packaging_files_are_there_and_windows_safe():
    pk = ROOT / "packaging" / "lector"
    for name in ("lector.spec", "lector.iss", "build_lector.ps1", "BUILD.md", "lector_entry.py"):
        assert (pk / name).is_file(), name
    ps = (pk / "build_lector.ps1").read_bytes()
    assert b"\r\n" in ps and b"\n" not in ps.replace(b"\r\n", b"")      # CRLF throughout
    assert all(b < 128 for b in ps) and b"\xef\xbb\xbf" not in ps       # plain ASCII for PS 5.1
    assert b"Remove-Item" not in ps and b"rmdir" not in ps.lower()      # nothing deleted
    iss = (pk / "lector.iss").read_text()
    assert "PrivilegesRequired=lowest" in iss and r"{localappdata}\Programs\Lector" in iss
    assert r"{userdocs}\Lector\data" in iss and "uninsneveruninstall" in iss
    spec = (pk / "lector.spec").read_text()
    ast.parse(spec)
    assert '"paths"' in spec and "uksi_synonym_corrections.csv" in spec       # stand-in paths; data
    for mod in ("shared.osgb", "shared.crash_log", "src.views.components.hscroll_strip"):
        assert mod in spec, mod


# --- 6. without UKSI -----------------------------------------------------------------------------------
def test_without_uksi_a_name_is_searched_as_typed(tmp_path, qapp):
    svc, fake = make_env(tmp_path)
    svc.uksi_db = tmp_path / "missing" / "uksi.db"
    t = svc.resolve_taxon("  lamia   TEXTOR ")
    assert t["found"] and t["name"] == "Lamia textor" and t["tvk"] is None and t["uksi_missing"]
    assert svc.resolve_taxon("NBNSYS0000011050")["found"] is False       # a TVK needs UKSI
    assert [c["name"] for c in svc.candidate_names(None, "Lamia textor")] == ["Lamia textor"]
    assert svc.suggest_taxa("lamia") == []
    sid = svc.create_search("lamia textor", name="No UKSI", filters=BRITISH)
    res = svc.run_search(sid)
    assert res["status"] == "done" and res["kept"] > 0
    pid = svc.review_queue(sid)[0]["page_id"]
    rid = svc.add_record(sid, pid, fields(svc, sid, pid, species="Lamia textor"))
    assert svc.get_record(rid)["species_tvk"] is None                    # kept as typed
    assert svc.settings_info()["uksi_found"] is False
    win = make_window(qapp, svc)
    try:
        win.go("builder", search_id=None)
        b = win.screens["builder"]
        b.species_edit.setText("rutpela maculata")
        b.find_species()
        assert "not installed" in b.matched.text() and "Rutpela maculata" in b.matched.text()
        assert [n["name"] for n in b.names.names()] == ["Rutpela maculata"]
        assert "UKSI: not installed" in win.nav_info.text()
    finally:
        win.close()
        pump(qapp)


# --- 7. the windows --------------------------------------------------------------------------------------
def test_record_button_dialog_screen_and_remove_in_the_window(tmp_path, qapp):
    svc, fake = make_env(tmp_path)
    sid = svc.create_search("Lamia textor", name="Lamia", filters=BRITISH)
    svc.run_search(sid)
    win = make_window(qapp, svc)
    try:
        r = win.go("review", search_id=sid, page_id=101, status="all")
        assert r.panel.record_btn.isEnabled()
        r.record_from_page()
        dlg = r._dialog
        assert dlg.edits["species"].text() == "Lamia textor" and dlg.citation.toPlainText()
        dlg.edits["place"].setText("Black Wood")
        dlg.edits["grid_ref"].setText("ZZ99")
        assert dlg.save() is None and "grid reference" in dlg.message.text()
        dlg.edits["grid_ref"].setText("NN 6057")
        dlg.day.setValue(14)
        dlg.month.setValue(6)
        dlg.year.setValue(1870)
        assert dlg.save() is not None
        assert r.current_item()["review_status"] == "record_extracted"
        assert r.panel.status_buttons["record_extracted"].isChecked()
        screen = win.go("records")
        assert [x["place"] for x in screen.rows] == ["Black Wood"]
        assert screen.table.rowCount() == 1 and screen.table.item(0, 3).text() == "NN6057"
        assert screen.export_btn.isEnabled() and not screen.remove_btn.isEnabled()
        screen.table.selectRow(0)
        assert screen.edit_btn.isEnabled() and screen.remove_btn.isEnabled()
        screen.edit()
        screen.dialog.edits["place"].setText("Black Wood, Rannoch")
        screen.dialog.save()
        assert screen.rows[0]["place"] == "Black Wood, Rannoch"
        screen.export_path = str(tmp_path / "exp.csv")
        done = screen.export_csv()
        assert done["rows"] == 1 and (tmp_path / "exp.csv").exists()
        screen.table.selectRow(0)
        win.answers[:] = [False]                                   # Keep it
        assert screen.remove() is None and len(svc.list_records()) == 1
        win.answers[:] = [True]
        done = screen.remove()
        assert Path(done["backup"]).exists() and svc.list_records() == []
        assert screen.empty.text().startswith("No records yet")
        # the page keeps its mark: removing a record never changes the page
        assert next(p for p in svc.review_queue(sid) if p["page_id"] == 101)["review_status"] \
            == "record_extracted"
    finally:
        win.close()
        pump(qapp)


# --- 8. the manual's pictures ------------------------------------------------------------------------------
def test_make_screens_runs_offscreen_and_writes_the_pictures(tmp_path, qapp):
    sys.path.insert(0, str(ROOT / "Lector" / "docs" / "manual"))
    try:
        import make_screens
        out = tmp_path / "shots"
        res = make_screens.make_screens(out, work_dir=tmp_path / "demo")
    finally:
        sys.path.remove(str(ROOT / "Lector" / "docs" / "manual"))
    assert set(res) == set(make_screens.SHOTS)
    from PySide6.QtGui import QImage
    for shot, info in res.items():
        png = out / f"{shot}.png"
        assert png.is_file() and png.stat().st_size > 5000, shot
        img = QImage(str(png))
        assert img.width() >= 300 and img.height() >= 200, shot
        assert info["callouts"] and not info["missing"], (shot, info["missing"])
    # every callout in the table was drawn on the screen it names, numbers once each, in order
    import callouts
    for shot, info in res.items():
        want = [n for s, _t, n, _l in callouts.CALLOUTS if s == shot]
        assert [n for n, _l in info["callouts"]] == want, shot
    with sqlite3.connect(tmp_path / "demo" / "lector.db") as c:        # the demo data is the demo's
        assert c.execute("SELECT COUNT(*) FROM extracted_records").fetchone()[0] == 2
    manual = (ROOT / "Lector" / "docs" / "manual" / "manual.md").read_text(encoding="utf-8")
    for shot in make_screens.SHOTS:
        assert f"screens/{shot}.png" in manual, shot
