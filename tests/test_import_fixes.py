"""Import wizard fixes of 9 Oct 2026 (review IMP-1, -2, -3, -4, -5, -8, IMP-14/15, SRCH5/EXA8).

The validation workers are run directly (no thread), on a made-up UKSI in memory and a
made-up observatum.db in memory -- no real database is touched."""
import os
import sqlite3

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pandas")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import species_lookup_harness as h  # noqa: E402
from test_species_lookup import _uksi  # noqa: E402

h.stub_webengine()

from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeUKSIModel:
    """Just enough of UKSIModel: .db.execute_uksi over the in-memory UKSI."""

    def __init__(self):
        conn = _uksi()

        class DB:
            def execute_uksi(self, sql, params=()):
                cur = conn.execute(sql, params)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
        self.db = DB()

    def search_species(self, text, limit=20):
        return []


class FakeMain:
    """A recording_scheme / observations table for the duplicate checks."""

    def __init__(self):
        self.c = sqlite3.connect(":memory:")
        self.c.executescript("""
            CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, irecord_id INTEGER,
                record_key TEXT, nbn_atlas_id TEXT);
            INSERT INTO recording_scheme VALUES (7, 555, 'iBRC555', 'N-HELD');
            CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, date TEXT,
                grid_ref TEXT, irecord_id INTEGER, irecord_key TEXT, observatum_key TEXT);
        """)

    def execute_main(self, sql, params=()):
        return self.c.execute(sql, params).fetchall()


def _run(worker):
    got = []
    worker.finished.connect(lambda rows: got.extend(rows))
    worker.run()
    return got


# ------------------------------------------------------------------ IMP-2


@pytest.mark.parametrize("mode, raw, dup", [
    ("IRECORD", [{"ID": "555", "Taxon": "Rutpela maculata", "Date interpreted": "01/06/2024",
                  "Output map ref": "SP4433"},
                 {"ID": "556", "Taxon": "Rutpela maculata", "Date interpreted": "02/06/2024",
                  "Output map ref": "SP4433"}], 0),
    ("NBN_ATLAS", [{"recordID": "N-HELD", "scientificName": "Rutpela maculata", "eventDate": "2024-06-01",
                    "gridReference": "SP4433"},
                   {"recordID": "N-NEW", "scientificName": "Rutpela maculata", "eventDate": "2024-06-02",
                    "gridReference": "SP4433"}], 0),
    ("GENERIC_CSV", [{"Name": "Rutpela maculata", "When": "01/06/2024", "Where": "SP4433"},
                     {"Name": "Carabus nemoralis", "When": "02/06/2024", "Where": "SP4433"}], None),
])
def test_scheme_duplicate_check_skips_id_columns_the_file_lacks(app, mode, raw, dup):
    from src.views.dialogs.scheme_import_wizard.validation_worker import (
        SchemeImportMode, SchemeImportRow, SchemeValidationWorker)
    rows = [SchemeImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raw)]
    w = SchemeValidationWorker(rows=rows, import_mode=SchemeImportMode[mode],
                               column_mapping={"species_name": "Name", "date": "When", "grid_ref": "Where"},
                               uksi_model=FakeUKSIModel(), vc_db_path=None, db_manager=FakeMain())
    got = _run(w)
    assert len(got) == 2
    assert not any("Duplicate check failed" in (r.error_message or "") for r in got)
    assert all(r.status.name != "ERROR" for r in got), [r.error_message for r in got]
    assert [r.is_duplicate for r in got] == [i == dup for i in range(2)]
    assert got[0].species_name == "Rutpela maculata" and got[0].species_tvk == "RM"


# ------------------------------------------------------------------ observation worker


def _obs(mode, raws, mapping=None, vc=None, model=None):
    from src.views.dialogs.observation_import_wizard.validation_worker import (
        ImportMode, ObservationImportRow, ObservationValidationWorker)
    rows = [ObservationImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
    w = ObservationValidationWorker(rows=rows, column_mapping=mapping or {}, import_mode=ImportMode[mode],
                                    uksi_model=model or FakeUKSIModel(), vc_db_path=None, db_manager=None)
    if vc is not None:
        w.run = _with_vc(w, vc)
    return _run(w)


def _with_vc(w, vc):
    original = type(w).run

    def run():
        import src.services.vc_lookup_service as vls
        saved = vls.VCLookupService
        vls.VCLookupService = lambda *a, **k: vc
        try:
            w.vc_db_path = "fake"
            original(w)
        finally:
            vls.VCLookupService = saved
    return run


class FakeVC:
    def get_vc_batch(self, refs):
        return {g: ({"vc_number": 23, "vc_name": "Oxfordshire", "error": "",
                     "warning": "On the boundary of VC23 and VC24" if g == "SP60" else ""}
                    if g.startswith("SP") else
                    {"vc_number": None, "vc_name": "", "error": "Invalid grid reference: x", "warning": ""})
                for g in refs}

    def parse_grid_ref(self, g):
        return None

    def close(self):
        pass


PERSONAL = {"species_name": "Species", "date": "Date", "recorder": "Recorder", "grid_ref": "Grid"}


def test_imp1_vice_county_is_set_and_boundary_notes_shown(app):
    got = _obs("PERSONAL_UPLOAD", [
        {"Species": "Rutpela maculata", "Date": "01/06/2024", "Recorder": "W", "Grid": "SP4433"},
        {"Species": "Rutpela maculata", "Date": "01/06/2024", "Recorder": "W", "Grid": "SP60"},
        {"Species": "Rutpela maculata", "Date": "01/06/2024", "Recorder": "W", "Grid": "XX12"}],
        PERSONAL, vc=FakeVC())
    assert (got[0].vc_number, got[0].vice_county, got[0].status.name) == (23, "Oxfordshire", "VALID")
    assert got[1].vc_number == 23 and "On the boundary of VC23 and VC24" in got[1].warnings
    assert got[2].status.name == "ERROR" and "Invalid grid reference" in got[2].error_message


def test_imp3_unreadable_dates_are_errors_naming_the_text(app):
    got = _obs("PERSONAL_UPLOAD", [
        {"Species": "Rutpela maculata", "Date": "31/02/2024", "Recorder": "W"},
        {"Species": "Rutpela maculata", "Date": "2024", "Recorder": "W"},
        {"Species": "Rutpela maculata", "Date": "", "Recorder": "W"},
        {"Species": "Rutpela maculata", "Date": "01/06/2024", "Recorder": "W"}], PERSONAL)
    assert [r.status.name for r in got] == ["ERROR", "ERROR", "ERROR", "VALID"]
    assert "Unreadable date: '31/02/2024'" in got[0].error_message
    assert "Unreadable date: '2024'" in got[1].error_message
    assert "Date is required" in got[2].error_message and got[3].date == "2024-06-01"
    irec = _obs("IRECORD_SYNC", [{"ID": "1", "Taxon": "Rutpela maculata", "TaxonVersionKey": "RM",
                                  "Date interpreted": "sometime"}])
    assert irec[0].status.name == "ERROR" and "Unreadable date: 'sometime'" in irec[0].error_message


def test_imp4_missing_tvk_only_on_the_rows_without_one(app):
    base = {"Date interpreted": "01/06/2024", "Output map ref": "SP4433"}
    got = _obs("IRECORD_SYNC", [
        dict(base, ID="1", Taxon="Rutpela maculata", TaxonVersionKey="RM"),
        dict(base, ID="2", Taxon="Carabus nemoralis", TaxonVersionKey="CN"),
        dict(base, ID="3", Taxon="Nosuch name", TaxonVersionKey="")])
    assert [any("Missing TVK" in w for w in r.warnings) for r in got] == [False, False, True]
    assert got[2].import_notes == ""             # the warning is not written into the note twice


def test_imp15_the_uksi_name_is_stored_and_the_typed_name_noted(app):
    got = _obs("PERSONAL_UPLOAD", [
        {"Species": "strangalia  MACULATA", "Date": "01/06/2024", "Recorder": "W"},
        {"Species": "Andrena proxima", "Date": "01/06/2024", "Recorder": "W"},
        {"Species": "Carabus nemoralis agg", "Date": "01/06/2024", "Recorder": "W"},
        {"Species": "alba", "Date": "01/06/2024", "Recorder": "W"}], PERSONAL)
    assert got[0].species_name == "Rutpela maculata" and "strangalia  MACULATA" in got[0].import_notes
    assert got[1].species_tvk == "APS" and "matched to the species" in got[1].import_notes
    assert got[2].species_tvk == "CN" and got[2].taxon_rank == "Species" and got[2].kingdom == "Animalia"
    assert "no aggregate in UKSI" in "; ".join(got[2].warnings)
    assert got[3].status.name == "ERROR" and got[3].species_tvk == ""      # never Populus alba
    assert "Populus alba" in got[3].error_message


# ------------------------------------------------------------------ IMP-8


def test_imp8_commercial_mode_offers_skip_duplicates_and_no_update(app):
    from src.views.dialogs.observation_import_wizard import ObservationImportWizard
    from src.views.dialogs.observation_import_wizard.validation_worker import ObservationImportRow
    from src.views.dialogs.row_status import RowStatus
    w = ObservationImportWizard(parent=None, uksi_model=None, vc_service=None, db=None)
    for card in w.mode_cards:
        if card.mode_id == "commercial_upload":
            w._select_mode_card(card)
    w.validated_rows = [
        ObservationImportRow(row_number=2, raw_data={}, status=RowStatus.VALID),
        ObservationImportRow(row_number=3, raw_data={}, status=RowStatus.VALID, is_duplicate=True,
                             existing_record_id=9)]
    w.stack.setCurrentIndex(4)
    w._update_step_ui()
    w._update_confirmation_counts()
    labels = lambda f: [x.text() for x in f.findChildren(type(w.valid_label))]  # noqa: E731
    assert w.skip_duplicates_checkbox.isVisibleTo(w) and w.skip_duplicates_checkbox.isChecked()
    assert labels(w.update_count_frame) == ["1", "Duplicates found"]
    assert labels(w.new_count_frame)[0] == "1" and labels(w.skip_count_frame)[0] == "1"
    assert not w.view_updates_btn.isVisibleTo(w)
    assert w.next_btn.text() == "Import 1 Records (1 skipped)"
    w.skip_duplicates_checkbox.setChecked(False)              # added again, as its own record
    assert labels(w.new_count_frame)[0] == "2" and w.next_btn.text() == "Import 2 Records"
    w.deleteLater()


# ------------------------------------------------------------------ IMP-5


def test_imp5_rematch_updates_every_row_and_keeps_other_errors(app):
    from src.views.dialogs.scheme_import_wizard.validation_worker import SchemeImportRow
    from src.views.dialogs.row_status import RowStatus
    from src.views.dialogs.species_match_report_dialog import SpeciesMatchReportDialog
    rows = [SchemeImportRow(row_number=i, raw_data={"Name of taxon": "Rutpela maculta"},
                            species_name="Rutpela maculta", status=RowStatus.ERROR,
                            error_message="Species not found in UKSI: Rutpela maculta — closest: Rutpela maculata")
            for i in range(7)]
    rows[3].error_message += "; Invalid date format: 31/02/2024"
    d = SpeciesMatchReportDialog(rows, None, uksi_model=None, name_columns=["Name of taxon"])
    assert [m["original"] for m in d._match_data] == ["Rutpela maculta"]     # found via the mapping
    d._apply_rematch("Rutpela maculta", {"scientific_name": "Rutpela maculata", "tvk": "RM",
                                         "kingdom": "Animalia"})
    assert d.changed_rows() == 7
    assert all(r.species_tvk == "RM" and r.species_name == "Rutpela maculata" for r in rows)
    assert [r.status for r in rows].count(RowStatus.WARNING) == 6
    assert rows[3].status == RowStatus.ERROR and rows[3].error_message == "Invalid date format: 31/02/2024"
    d.deleteLater()


# ------------------------------------------------------------------ resolution flow


def test_resolve_species_offers_not_found_and_ambiguous_names(app):
    from shared.species_lookup import is_unresolved_error
    from shared.species_lookup_entries import entry
    from shared.species_lookup import lookup_names
    uksi = _uksi()
    errs = [entry(r)["error"] for r in lookup_names(["Ab", "Cheilosia semifasciata"], uksi).values()]
    assert all(is_unresolved_error(e) for e in errs)
    assert not is_unresolved_error("Unreadable date: '2024'")


def test_bulk_dialog_no_longer_saves_aliases(app):
    from src.views.dialogs.specimen_import_wizard.bulk_resolution_dialog import BulkSpeciesResolutionDialog
    from PySide6.QtWidgets import QCheckBox
    d = BulkSpeciesResolutionDialog(None, uksi_model=None, unmatched_species=["Ab"])
    assert not d.findChildren(QCheckBox) and d.get_aliases_to_save() == {}
    d.deleteLater()


# ------------------------------------------------------------------ SRCH5 / EXA8


def test_examen_import_list_rules(app):
    from Examen.import_species_dialog import ImportSpeciesDialog, resolve_names, unique_names
    names, dropped = unique_names(["﻿Rutpela maculata", "Lotus", "rutpela  maculata", "",
                                   "Cheilosia semifasciata", "Strangalia maculata", "Andrena proxima", "alba"])
    assert names[0] == "Rutpela maculata" and dropped == 1
    res = {r["input"]: r for r in resolve_names(names, _uksi())}
    assert res["Rutpela maculata"]["status"] == "matched" and res["Rutpela maculata"]["tvk"] == "RM"
    assert res["Lotus"]["status"] == "needs choice" and res["Lotus"]["tvk"] == ""   # genus: never made specific
    assert res["Cheilosia semifasciata"]["status"] == "needs choice"
    assert {c["tvk"] for c in res["Cheilosia semifasciata"]["choices"]} == {"CS1", "CS2"}
    assert res["Strangalia maculata"]["tvk"] == "RM" and res["Andrena proxima"]["tvk"] == "APS"
    assert res["alba"]["tvk"] == "" and res["alba"]["choices"][0]["tvk"] == "PA"
    dlg = ImportSpeciesDialog()
    dlg._resolved = list(res.values())
    dlg._refresh_table()
    tvks, by_tvk = dlg.get_results()
    assert tvks == ["RM", "APS"] and by_tvk["RM"] == "Rutpela maculata"   # RM once, not twice
    dlg.deleteLater()


def test_examen_csv_with_a_byte_order_mark(app, tmp_path, monkeypatch):
    from Examen import import_species_dialog as isd
    p = tmp_path / "list.csv"
    p.write_bytes("﻿species\nRutpela maculata\n".encode("utf-8"))
    monkeypatch.setattr(isd.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(p), "")))
    dlg = isd.ImportSpeciesDialog()
    dlg._on_load_csv()
    assert dlg.text_edit.toPlainText() == "Rutpela maculata"      # the header was recognised
    dlg.deleteLater()
