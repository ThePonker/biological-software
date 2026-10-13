"""Round 10 B (13 Oct 2026): cleaning report tiles / copies toggle (F71) and iRecord-safe
delete, hide, come-back and edit (F72). Offscreen; small temp databases only."""
import os
import sqlite3
import sys

import pytest

pytest.importorskip("PySide6")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

HAVE_UKSI = os.path.exists(str(paths.UKSI_DB))
needs_uksi = pytest.mark.skipif(not HAVE_UKSI, reason="uksi.db copy absent")

OBS_COLS = ("id INTEGER PRIMARY KEY, irecord_id INTEGER UNIQUE, species_name TEXT, species_tvk TEXT, "
            "taxon_rank TEXT, date TEXT, date_type TEXT, grid_ref TEXT, site_name TEXT, recorder TEXT, "
            "latitude REAL, longitude REAL, source TEXT, record_type TEXT, project_name TEXT, client TEXT, "
            "site TEXT, sub_location TEXT, trap_number TEXT, visit_number TEXT, common_name TEXT, "
            "order_name TEXT, family TEXT, quantity INTEGER, sex TEXT, stage TEXT, method TEXT, "
            "determiner TEXT, vice_county TEXT, vc_number INTEGER, verification_status TEXT, "
            "created_at TEXT, updated_at TEXT")
SCHEME_COLS = ("id INTEGER PRIMARY KEY, irecord_id INTEGER, nbn_atlas_id TEXT, occurrence_id TEXT, "
               "species_name TEXT, species_tvk TEXT, taxon_rank TEXT, date TEXT, date_type TEXT, "
               "grid_ref TEXT, site_name TEXT, recorder TEXT, latitude REAL, longitude REAL, "
               "dataset_name TEXT, source TEXT")
VIEW = ("CREATE VIEW assessment_records AS SELECT 'own' AS origin, NULL AS contributor, id, "
        "record_type, project_name, client, site_name, sub_location, trap_number, visit_number, "
        "date, species_name, species_tvk, common_name, order_name, family, quantity, sex, stage, "
        "method, recorder, determiner, grid_ref, vice_county, vc_number FROM observations")


def make_db(path, with_schema=False):
    c = sqlite3.connect(path)
    c.execute(f"CREATE TABLE observations ({OBS_COLS})")
    c.execute(f"CREATE TABLE recording_scheme ({SCHEME_COLS})")
    c.execute("CREATE TABLE contributed_observations (id INTEGER PRIMARY KEY, species_name TEXT, "
              "species_tvk TEXT, taxon_rank TEXT, date TEXT, date_type TEXT, grid_ref TEXT, "
              "site_name TEXT, recorder TEXT, latitude REAL, longitude REAL, contributor TEXT)")
    c.execute(VIEW)
    # observations: 1 in iRecord with a coarse grid ref, 2 local (no iRecord ID) with no date
    c.execute("INSERT INTO observations (id, irecord_id, species_name, species_tvk, taxon_rank, date, "
              "grid_ref) VALUES (1, 5001, 'Rutpela maculata', 'NBNSYS0000011234', 'Species', "
              "'2024-06-01', 'SP43')")
    c.execute("INSERT INTO observations (id, irecord_id, species_name, species_tvk, taxon_rank, date, "
              "grid_ref) VALUES (2, NULL, 'Clytus arietis', 'NBNSYS0000011235', 'Species', NULL, "
              "'SP4331')")
    c.execute("INSERT INTO observations (id, irecord_id, species_name, species_tvk, taxon_rank, date, "
              "grid_ref) VALUES (3, 5003, 'Clytus arietis', 'NBNSYS0000011235', 'Species', "
              "'2024-06-02', 'SP4331')")
    # scheme: an iRecord row, its NBN copy (both coarse), and a plain row
    c.execute("INSERT INTO recording_scheme (id, irecord_id, species_name, species_tvk, taxon_rank, "
              "date, grid_ref, source) VALUES (10, 77, 'Rutpela maculata', 'NBNSYS0000011234', "
              "'Species', '2024-06-01', 'SP43', 'iRecord')")
    c.execute("INSERT INTO recording_scheme (id, nbn_atlas_id, occurrence_id, species_name, "
              "species_tvk, taxon_rank, date, grid_ref, dataset_name) VALUES (11, 'nbn-1', '77', "
              "'Rutpela maculata', 'NBNSYS0000011234', 'Species', '2024-06-01', 'SP43', 'NBN set')")
    c.execute("INSERT INTO recording_scheme (id, species_name, species_tvk, taxon_rank, date, "
              "grid_ref) VALUES (12, 'Clytus arietis', 'NBNSYS0000011235', 'Species', "
              "'2024-06-02', 'SP4331')")
    c.commit()
    if with_schema:
        from shared.hidden_records import ensure_schema, ensure_view
        with c:
            ensure_schema(c)
            ensure_view(c)
    c.close()
    return path


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------ shared rule

def test_hidden_fragment_with_and_without_column(tmp_path):
    import shared.hidden_records as hr
    db = make_db(str(tmp_path / "a.db"))
    hr.forget()
    conn = sqlite3.connect(db)
    assert hr.live_sql(conn) == ""
    assert hr.live_sql(db) == ""
    assert hr.hide(conn, 1, 5001, "Rutpela maculata") is False      # schema missing: no write
    with conn:
        assert hr.ensure_schema(conn) is True
        assert hr.ensure_schema(conn) is False                       # idempotent
        assert hr.ensure_view(conn) is True
        assert hr.ensure_view(conn) is False
    hr.forget()
    assert hr.live_sql(conn) == " AND hidden_at IS NULL"
    assert hr.live_sql(db, "o.") == " AND o.hidden_at IS NULL"
    assert hr.live_sql(lambda sql: conn.execute(sql).fetchall()) == " AND hidden_at IS NULL"
    # the counting door adds it for observations (and nothing for contributed)
    from shared.species_counting import EXPORT_INCLUDE, copies_sql, export_sql, not_excluded_sql
    assert copies_sql(conn, "observations", "o.id") == " AND o.hidden_at IS NULL"
    assert not_excluded_sql(conn, "observations", "id").endswith(" AND hidden_at IS NULL")
    assert export_sql(conn, "observations", EXPORT_INCLUDE) == " AND hidden_at IS NULL"
    assert copies_sql(conn, "contributed_observations") == ""
    conn.close()


def test_hide_show_again_and_come_back(tmp_path):
    import shared.hidden_records as hr
    db = make_db(str(tmp_path / "b.db"), with_schema=True)
    conn = sqlite3.connect(db)
    live = lambda: conn.execute("SELECT COUNT(*) FROM observations WHERE hidden_at IS NULL").fetchone()[0]  # noqa: E731
    examen = lambda: conn.execute("SELECT COUNT(*) FROM assessment_records").fetchone()[0]  # noqa: E731
    assert (live(), examen()) == (3, 3)
    assert hr.hide(conn, 1, 5001, "Rutpela maculata") is True
    assert (live(), examen()) == (2, 2)
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 3     # nothing deleted
    assert hr.hidden_ids(conn) .keys() == {"5001"}
    assert hr.returned(conn) == []
    # a download brings 5001 again (and 5003, never hidden): only 5001 is flagged
    assert hr.after_download(conn, [5001, 5003, "", None]) == 1
    back = hr.returned(conn)
    assert [(r[0], r[1]) for r in back] == [(1, "5001")]
    assert back[0][4] is not None
    assert live() == 2                                                        # still hidden
    # the record was really gone (deleted before this feature) and the download re-inserted it
    conn.execute("UPDATE observations SET hidden_at = NULL WHERE id = 1")
    assert hr.after_download(conn, [5001]) == 1
    assert conn.execute("SELECT hidden_at FROM observations WHERE id = 1").fetchone()[0]
    # Show again clears both
    assert hr.show_again(conn, 1) is True
    assert (live(), examen()) == (3, 3)
    assert hr.hidden_ids(conn) == {}
    assert hr.returned(conn) == []
    conn.close()


def test_migration_script_dry_run_and_apply(tmp_path, capsys):
    db = make_db(str(tmp_path / "m.db"))
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import add_hidden_at_column as script
    assert script.main(["--db", db, "--backup-dir", str(tmp_path / "bk")]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN. Nothing has been changed" in out
    assert "add column observations.hidden_at" in out and "rebuild view assessment_records" in out
    c = sqlite3.connect(db)
    assert "hidden_at" not in {r[1] for r in c.execute("PRAGMA table_info(observations)")}
    c.close()
    assert script.main(["--db", db, "--backup-dir", str(tmp_path / "bk"), "--apply"]) == 0
    out = capsys.readouterr().out
    assert "backed up to" in out and "done." in out
    assert len(os.listdir(tmp_path / "bk")) == 1
    c = sqlite3.connect(db)
    assert "hidden_at" in {r[1] for r in c.execute("PRAGMA table_info(observations)")}
    assert {r[1] for r in c.execute("PRAGMA table_info(hidden_irecord_ids)")} == {
        "irecord_id", "hidden_at", "species_name", "returned_at"}
    assert "WHERE hidden_at IS NULL" in c.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'assessment_records'").fetchone()[0]
    assert c.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 3
    c.close()
    assert script.main(["--db", db, "--backup-dir", str(tmp_path / "bk"), "--apply"]) == 0
    assert "nothing to do. Nothing has been changed" in capsys.readouterr().out
    assert len(os.listdir(tmp_path / "bk")) == 1                          # no second backup


def test_repository_search_skips_hidden(tmp_path):
    from src.models.database import DatabaseManager
    from src.repositories.observation_repository import ObservationRepository
    import shared.hidden_records as hr
    db = make_db(str(tmp_path / "r.db"), with_schema=True)
    hr.forget()
    dbm = DatabaseManager()
    dbm.set_main_path(db)
    repo = ObservationRepository(dbm)
    assert sorted(o.id for o in repo.search(limit=100)) == [1, 2, 3]
    c = sqlite3.connect(db)
    hr.hide(c, 1, 5001, "Rutpela maculata")
    c.close()
    assert sorted(o.id for o in repo.search(limit=100)) == [2, 3]
    assert sorted(o.id for o in repo.find_all(limit=100)) == [2, 3]
    assert [o.id for o in repo.find_by_species("NBNSYS0000011234")] == []


# ------------------------------------------------------------------ cleaning report

@needs_uksi
def test_cleaning_report_copies_toggle_and_returned(tmp_path):
    from src.services.cleaning_report import build_report
    from src.services.cleaning_export import summary_rows
    import shared.hidden_records as hr
    import shared.scheme_duplicates as sd
    db = make_db(str(tmp_path / "c.db"), with_schema=True)
    uksi = str(paths.UKSI_DB)
    hr.forget()
    sd.forget()
    # no duplicate_of column: nothing changes, the note says so
    rep = build_report(db, uksi, "recording_scheme")
    assert (rep.total_records, rep.copies_marked, rep.counts["grid"]) == (3, 0, 2)
    assert "none marked" in rep.copies_note
    assert ["NBN copies of iRecord records", "left out"] in summary_rows(rep)
    # mark the copy (as scripts/mark_scheme_irecord_duplicates.py does)
    c = sqlite3.connect(db)
    c.execute("ALTER TABLE recording_scheme ADD COLUMN duplicate_of INTEGER")
    c.execute("UPDATE recording_scheme SET duplicate_of = 10 WHERE id = 11")
    c.commit()
    sd.forget()
    rep = build_report(db, uksi, "recording_scheme")
    assert (rep.total_records, rep.copies_marked, rep.counts["grid"]) == (2, 1, 1)
    assert "left out: 1 marked" in rep.copies_note
    rep2 = build_report(db, uksi, "recording_scheme", include_copies=True)
    assert (rep2.total_records, rep2.counts["grid"], rep2.include_copies) == (3, 2, True)
    assert ["NBN copies of iRecord records", "included"] in summary_rows(rep2)
    assert "returned" not in [r[0] for r in summary_rows(rep2) if r]
    # observations: a hidden record is not checked; one that came back is listed under returned
    rep = build_report(db, uksi, "observations")
    assert (rep.total_records, rep.counts["grid"], rep.counts["returned"]) == (3, 1, 0)
    hr.hide(c, 1, 5001, "Rutpela maculata")
    rep = build_report(db, uksi, "observations")
    assert (rep.total_records, rep.hidden_records, rep.counts["grid"], rep.counts["returned"]) == (2, 1, 0, 0)
    hr.after_download(c, [5001])
    rep = build_report(db, uksi, "observations")
    assert (rep.total_records, rep.counts["returned"]) == (2, 1)
    row = rep.rows["returned"][0]
    assert (row.record_id, row.irecord_id, row.species) == (1, 5001, "Rutpela maculata")
    assert "came back from iRecord" in row.detail and rep.records_with_problem == 1
    assert ["Removed here, still in iRecord (hidden, not checked)", 1] in summary_rows(rep)
    c.close()


@needs_uksi
def test_dashboard_tiles_links_buttons_and_show_again(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from src.views.stats.cleaning_dashboard import CleaningDashboard, NO_ID_TIP, NO_ROW_TIP
    from src.views.stats.cleaning_table import IRECORD_COLUMN
    import shared.hidden_records as hr
    db = make_db(str(tmp_path / "d.db"), with_schema=True)
    hr.forget()
    d = CleaningDashboard(main_db=db, uksi_db=str(paths.UKSI_DB))
    assert not hasattr(d, "tabs")                                      # the tab strip is gone
    d.refresh()
    assert d._tiles["grid"].text() == "No grid ref or coarse (10 km+)\n1"
    assert d._tiles["date"].text() == "No date or vague date\n1"
    assert d.btn_irecord.isEnabled() is False and d.btn_irecord.toolTip() == NO_ROW_TIP
    d._tiles["grid"].click()
    assert d.current_key() == "grid" and d._tiles["grid"].isChecked() and not d._tiles["date"].isChecked()
    view = d.current_view()
    idx = view.model().index(0, IRECORD_COLUMN)
    assert idx.data() == "5001" and idx.data(Qt.ItemDataRole.FontRole).underline()
    assert idx.data(Qt.ItemDataRole.ForegroundRole) is not None and view.is_link(idx)
    view.setCurrentIndex(view.model().index(0, 0))
    assert d.btn_irecord.isEnabled() is True
    d._tiles["date"].click()                                           # record 2: no iRecord ID
    view = d.current_view()
    idx = view.model().index(0, IRECORD_COLUMN)
    assert idx.data() == "" and idx.data(Qt.ItemDataRole.FontRole) is None and not view.is_link(idx)
    view.setCurrentIndex(view.model().index(0, 0))
    assert d.btn_irecord.isEnabled() is False and d.btn_irecord.toolTip() == NO_ID_TIP
    assert d.btn_show_again.isVisibleTo(d) is False
    # the copies box only matters for the scheme
    assert d.chk_copies.isEnabled() is False
    d.cmb_source.setCurrentIndex(1)
    assert d.chk_copies.isEnabled() is True and d._tiles["returned"].isVisibleTo(d) is False
    d.cmb_source.setCurrentIndex(0)
    # a record came back: the tile, its list, Show again
    c = sqlite3.connect(db)
    hr.hide(c, 1, 5001, "Rutpela maculata")
    hr.after_download(c, [5001])
    c.close()
    d.mark_stale()
    d.refresh()
    assert d._tiles["returned"].text().endswith("\n1") and d._tiles["returned"].isVisibleTo(d)
    d._tiles["returned"].click()
    view = d.current_view()
    view.setCurrentIndex(view.model().index(0, 0))
    assert d.btn_show_again.isVisibleTo(d) and d.btn_show_again.isEnabled()
    d.show_selected_again()
    assert d._tiles["returned"].text().endswith("\n0")
    c = sqlite3.connect(db)
    assert c.execute("SELECT hidden_at FROM observations WHERE id = 1").fetchone()[0] is None
    c.close()
    d.deleteLater()


# ------------------------------------------------------------------ delete flow

def test_detail_dialog_delete_box_and_edit_note(qapp, monkeypatch):
    from PySide6.QtWidgets import QPushButton
    from src.views.components import irecord_delete
    from src.views.dialogs.record_detail_dialog import RecordDetailDialog
    rec = {"id": 1, "irecord_id": 5001, "species_name": "Rutpela maculata", "date": "2024-06-01",
           "grid_ref": "SP43"}
    dlg = RecordDetailDialog(record=rec, record_type="observation")
    btns = {b.text(): b for b in dlg.findChildren(QPushButton)}
    assert btns["Edit"].isEnabled() and btns["Delete"].isEnabled()      # no longer greyed out
    assert dlg.edit_note is not None and dlg.edit_note.text().startswith("Change this in iRecord")
    hidden, deleted, opened = [], [], []
    dlg.hide_requested.connect(lambda r: hidden.append(r["id"]))
    dlg.delete_requested.connect(lambda r: deleted.append(r["id"]))
    monkeypatch.setattr(irecord_delete, "open_url", lambda u: opened.append(u.toString()))
    monkeypatch.setattr(irecord_delete, "ask", lambda parent, n=1: irecord_delete.OPEN)
    dlg._on_delete()
    assert opened == ["https://irecord.org.uk/record-details?occurrence_id=5001"]
    assert hidden == [] and deleted == [] and dlg.isVisible() is False
    monkeypatch.setattr(irecord_delete, "ask", lambda parent, n=1: irecord_delete.CANCEL)
    dlg._on_delete()
    assert hidden == [] and deleted == []
    monkeypatch.setattr(irecord_delete, "ask", lambda parent, n=1: irecord_delete.HIDE)
    dlg._on_delete()
    assert hidden == [1] and deleted == []
    # no iRecord ID: the plain confirmation as before, no note
    dlg2 = RecordDetailDialog(record={"id": 2, "species_name": "Clytus arietis"}, record_type="observation")
    assert dlg2.edit_note is None
    dlg.deleteLater()
    dlg2.deleteLater()


def test_ask_box_buttons(qapp):
    """The box has the three buttons and returns what was clicked (driven offscreen)."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from src.views.components import irecord_delete
    seen, results = [], []

    def click(text):
        def go():
            for w in QApplication.topLevelWidgets():
                if isinstance(w, QMessageBox) and w.isVisible():
                    seen.append((w.windowTitle(), w.text(), {b.text() for b in w.buttons()}))
                    hit = [b for b in w.buttons() if b.text() == text]
                    (hit[0] if hit else w.buttons()[0]).click()
                    return
            QTimer.singleShot(10, go)
        QTimer.singleShot(0, go)
    for text in ("Open in iRecord", "Deleted in iRecord \u2014 remove here", "Cancel"):
        click(text)
        results.append(irecord_delete.ask(None, 1))
    assert results == [irecord_delete.OPEN, irecord_delete.HIDE, irecord_delete.CANCEL]
    assert len(seen) == 3
    assert seen[0][0] == "Also in iRecord" and "Delete it there first" in seen[0][1]
    assert seen[0][2] == {"Open in iRecord", "Deleted in iRecord \u2014 remove here", "Cancel"}


def test_hide_records_backs_up_then_hides(qapp, tmp_path, monkeypatch):
    from src.models.database import DatabaseManager
    from src.views.components import irecord_delete
    import src.views.components.delete_guard as guard
    import shared.hidden_records as hr
    db = make_db(str(tmp_path / "h.db"), with_schema=True)
    dbm = DatabaseManager()
    dbm.set_main_path(db)
    backups = []
    monkeypatch.setattr(guard, "backup_before_delete", lambda parent, title="Delete": backups.append(title) or True)
    recs = [{"id": 1, "irecord_id": 5001, "species_name": "Rutpela maculata"},
            {"id": 2, "irecord_id": None, "species_name": "Clytus arietis"}]
    assert irecord_delete.with_irecord(recs) == [recs[0]]
    assert irecord_delete.hide_records(None, recs, db=dbm, title="Remove here") == 1
    assert backups == ["Remove here"]
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM observations WHERE hidden_at IS NOT NULL").fetchone()[0] == 1
    assert hr.hidden_ids(c).keys() == {"5001"}
    c.close()
    # backup fails: nothing hidden
    monkeypatch.setattr(guard, "backup_before_delete", lambda parent, title="Delete": False)
    assert irecord_delete.hide_records(None, [{"id": 3, "irecord_id": 5003}], db=dbm) is None
    c = sqlite3.connect(db)
    assert c.execute("SELECT hidden_at FROM observations WHERE id = 3").fetchone()[0] is None
    c.close()
    # schema missing: says so, nothing written
    db2 = make_db(str(tmp_path / "h2.db"))
    dbm2 = DatabaseManager()
    dbm2.set_main_path(db2)
    monkeypatch.setattr(irecord_delete.QMessageBox, "warning", lambda *a, **k: None)
    assert irecord_delete.hide_records(None, [{"id": 1, "irecord_id": 5001}], db=dbm2) is None


# ------------------------------------------------------------------ item 4: the sync
# updates a record it already holds (same iRecord ID) rather than skipping it

def test_irecord_sync_updates_held_record(tmp_path):
    from src.models.database import DatabaseManager
    from src.models.observation import ObservationModel
    from src.views.dialogs.observation_import_wizard.wizard_import_mixin import WizardImportMixin
    from src.views.dialogs.observation_import_wizard.validation_worker import ImportMode
    db = make_db(str(tmp_path / "s.db"), with_schema=True)
    dbm = DatabaseManager()
    dbm.set_main_path(db)

    class Host(WizardImportMixin):
        def __init__(self):
            self.db = dbm
            self.observation_model = ObservationModel(dbm)
    host = Host()
    before = dict(sqlite3.connect(db).execute(
        "SELECT species_name, date, grid_ref FROM observations WHERE id = 1").fetchone() and
        zip(("species_name", "date", "grid_ref"), sqlite3.connect(db).execute(
            "SELECT species_name, date, grid_ref FROM observations WHERE id = 1").fetchone()))
    assert before == {"species_name": "Rutpela maculata", "date": "2024-06-01", "grid_ref": "SP43"}
    incoming = {"irecord_id": 5001, "species_name": "Rutpela maculata", "species_tvk": "NBNSYS0000011234",
                "date": "2024-06-03", "grid_ref": "SP4332", "verification_status": "Accepted", "quantity": 1}
    assert host._update_observation(1, dict(incoming)) is True
    assert host._update_observation(1, dict(incoming)) == "skipped"       # already up to date
    after = dict(zip(("species_name", "date", "grid_ref", "verification_status"), sqlite3.connect(db).execute(
        "SELECT species_name, date, grid_ref, verification_status FROM observations WHERE id = 1").fetchone()))
    assert after == {"species_name": "Rutpela maculata", "date": "2024-06-03", "grid_ref": "SP4332",
                     "verification_status": "Accepted"}
    # a hidden record that comes back stays hidden and is flagged (the hook the sync calls)
    c = sqlite3.connect(db)
    import shared.hidden_records as hr
    hr.hide(c, 1, 5001, "Rutpela maculata")
    c.close()

    class Row:
        irecord_id = 5001
    assert host._keep_hidden_after_sync([Row()], ImportMode.IRECORD_SYNC) == 1
    assert host._keep_hidden_after_sync([Row()], ImportMode.PERSONAL_UPLOAD) == 0
    c = sqlite3.connect(db)
    assert c.execute("SELECT hidden_at FROM observations WHERE id = 1").fetchone()[0]
    assert c.execute("SELECT returned_at FROM hidden_irecord_ids").fetchone()[0]
    c.close()
