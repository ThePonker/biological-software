"""Import wizards, Tier 2 review findings fixed 10 Oct 2026: IMP-6, -7, -9, -11, -12, -13, -16, -18.

Workers run directly (no thread) on the made-up UKSI of test_species_lookup; imports write to
small tables in memory. No real database is written; the VC lookup copy is only read, and
those tests are skipped when it is absent."""
import datetime as dt
import os
import sqlite3

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pandas")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import species_lookup_harness as h  # noqa: E402

h.stub_webengine()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from shared.import_core import (auto_map_columns, parse_record_date,  # noqa: E402
                                quantity_or_default, summary_lines, vc_for_grid_refs)
from test_import_fixes import FakeUKSIModel  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VC_DB = os.path.join(ROOT, "data", "vc_lookup.db")
TODAY = dt.date(2026, 10, 10)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def quiet(monkeypatch):
    """Message boxes answer Yes / No without showing; the pre-import backup 'succeeds'."""
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: pytest.fail(str(a[2:]))))
    import shared.backup_service as bs
    monkeypatch.setattr(bs, "backup_main_only", lambda *a, **k: True)


class MemDB:
    """execute_main / _write / _many over tables made in memory with the columns asked for."""

    def __init__(self, tables):
        self.c = sqlite3.connect(":memory:")
        self.c.row_factory = sqlite3.Row
        for name, cols in tables.items():
            extra = ", ".join(f"{c}" for c in cols if c != "id")
            self.c.execute(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, {extra})")

    def execute_main(self, sql, params=()):
        return [dict(r) for r in self.c.execute(sql, params).fetchall()]

    def execute_main_write(self, sql, params=()):
        return self.c.execute(sql, params).rowcount

    def execute_main_many(self, sql, params):
        self.c.executemany(sql, params)
        return len(params)

    def rows(self, table, cols="*"):
        return [dict(r) for r in self.c.execute(f"SELECT {cols} FROM {table} ORDER BY id")]


def _run(worker):
    got = []
    worker.finished.connect(lambda rows: got.extend(rows))
    worker.run()
    return got


# ================================================================== shared pieces


@pytest.mark.parametrize("text, want", [
    ("01/06/2024", ("2024-06-01", "D")),
    ("2024-06-01", ("2024-06-01", "D")),
    ("2024-06-01T00:00:00Z", ("2024-06-01", "D")),
    ("6.vi.2021", ("2021-06-06", "D")),              # IMP-13: roman-numeral month
    ("6.VI.21", ("2021-06-06", "D")),
    ("6 vi 1985", ("1985-06-06", "D")),
    ("6 June 2021", ("2021-06-06", "D")),
    ("6-Jun-21", ("2021-06-06", "D")),
    ("1.6.85", ("1985-06-01", "D")),                  # a two-digit year is never still to come
    ("2019", ("2019-01-01", "Y")),                    # IMP-12: a year keeps its date type
    ("2021-06", ("2021-06-01", "O")),
    ("June 2021", ("2021-06-01", "O")),
    ("vi.2021", ("2021-06-01", "O")),
    ("06/2021", ("2021-06-01", "O")),
    ("2024-05-01/2024-05-15", ("2024-05-01", "DD")),  # IMP-12: a range is not an exact date
    ("1/5/2024 to 15/5/2024", ("2024-05-01", "DD")),
    ("2019-2021", ("2019-01-01", "YY")),
    ("2024-06/2024-07", ("2024-06-01", "OO")),
    ("2024-06-01/2024-06-01", ("2024-06-01", "D")),
])
def test_dates_as_the_suite_stores_them(text, want):
    p = parse_record_date(text, today=TODAY)
    assert (p.date, p.date_type, p.error) == (*want, "")
    # a period or range says so; so does a two-digit year (the century it was read as)
    assert bool(p.note) == (want[1] != "D" or text in ("6.VI.21", "6-Jun-21", "1.6.85"))


@pytest.mark.parametrize("text, error", [
    ("01/06/2030", "Date is in the future"),           # IMP-13
    ("2026-11", "Date is in the future"),
    ("2026-11-01/2026-12-31", "Date is in the future"),   # a range that starts after today
    ("31/02/2024", "Unreadable date"),
    ("summer", "Unreadable date"),
    ("15/05/2024 - 01/05/2024", "Date range ends before it starts"),
])
def test_dates_that_cannot_be_stored(text, error):
    p = parse_record_date(text, today=TODAY)
    assert p.date == "" and p.error.startswith(error)


def test_blank_date_is_no_date_and_no_error():
    assert parse_record_date("  ") == parse_record_date(None) == parse_record_date("")
    assert parse_record_date("").error == ""


@pytest.mark.parametrize("text, want", [
    ("c.20", (20, "c.20")), ("0", (0, None)), ("", (1, None)), ("3", (3, None)), ("many", (1, "many")),
])
def test_quantity_a_count_of_nought_stays_nought(text, want):
    assert quantity_or_default(text) == want


PATTERNS = {
    "species_name": ["species", "taxon", "scientific name", "=name"],
    "site_name": ["site name", "site"],
    "grid_ref": ["grid ref", "grid reference", "grid"],
    "quantity": ["quantity", "count", "=number"],
    "sex": ["sex"],
    "stage": ["stage"],
}


def test_column_mapping_takes_whole_words_only():
    cols = ["Site name", "Vice County", "Species", "VC number", "Quantity", "Grid Ref"]
    m = auto_map_columns(cols, PATTERNS)
    assert m["species_name"] == "Species" and m["site_name"] == "Site name"     # not 'Site name'
    assert m["quantity"] == "Quantity"                                          # not 'Vice County'
    assert "VC number" not in m.values()
    # no exact column: still no part-words, and each heading is used once
    m = auto_map_columns(["Site name", "Vice County", "Count of sex or stage", "OS grid reference"], PATTERNS)
    assert "species_name" not in m and m["site_name"] == "Site name"
    assert m["quantity"] == "Count of sex or stage" and "Vice County" not in m.values()
    assert m["grid_ref"] == "OS grid reference" and len(set(m.values())) == len(m)
    assert auto_map_columns(["Name"], PATTERNS) == {"species_name": "Name"}


def test_summary_lines_list_only_what_happened():
    order = (("new", "New"), ("dup", "Duplicates skipped"), ("err", "Errors left out"))
    assert summary_lines({"new": 0, "dup": 2}, order) == ["New: 0", "Duplicates skipped: 2"]


class FakeVCService:
    """get_vc_batch reads only all-digit references (as VCLookupService does); assess reads tetrads."""

    def get_vc_batch(self, refs):
        return {g: {"vc_number": 23, "vc_name": "Oxfordshire", "warning": "", "error": ""} for g in refs}

    def assess(self, g):
        return {"vc_number": 38, "vc_name": "Warwickshire", "boundary": False, "vcs": [(38, 100)], "note": ""}


def test_tetrads_get_a_vice_county():
    got = vc_for_grid_refs(FakeVCService(), ["SP46Q", "SP4433", "SP46Q"])
    assert got["SP46Q"]["vc_number"] == 38 and got["SP46Q"]["error"] == ""
    assert got["SP4433"]["vc_number"] == 23


@pytest.mark.skipif(not os.path.exists(VC_DB), reason="no vc_lookup.db copy")
def test_tetrad_sp46q_with_the_real_lookup():
    from src.services.vc_lookup_service import VCLookupService
    vc = VCLookupService(VC_DB)
    try:
        assert vc.get_vc_batch(["SP46Q"])["SP46Q"]["error"]          # the service alone: rejected
        got = vc_for_grid_refs(vc, ["SP46Q", "SP4565"])
        assert got["SP46Q"]["vc_number"] == got["SP4565"]["vc_number"] == 38
    finally:
        vc.close()


# ================================================================== workers


def _scheme(mode, raws, mapping=None, vc=None, db=None):
    from src.views.dialogs.scheme_import_wizard.validation_worker import (
        SchemeImportMode, SchemeImportRow, SchemeValidationWorker)
    rows = [SchemeImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
    w = SchemeValidationWorker(rows=rows, import_mode=SchemeImportMode[mode], column_mapping=mapping or GEN,
                               uksi_model=FakeUKSIModel(), vc_db_path=None, db_manager=db)
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


class VC(FakeVCService):
    def close(self):
        pass


GEN = {"species_name": "Species", "date": "Date", "grid_ref": "Grid Ref", "quantity": "Quantity",
       "site_name": "Site name"}
OK = {"Species": "Rutpela maculata", "Grid Ref": "SP4433", "Date": "01/06/2024"}


def test_imp12_scheme_counts_c20_and_nought(app):
    got = _scheme("GENERIC_CSV", [dict(OK, Quantity=q) for q in ("c.20", "0", "", "3")])
    assert [(r.quantity, r.organism_quantity) for r in got] == [(20, "c.20"), (0, ""), (1, ""), (3, "")]
    assert "Count of 0" in got[1].error_message and got[1].status.name == "WARNING"


def test_imp12_nbn_year_range_month_and_recorded_by(app):
    base = {"scientificName": "Rutpela maculata", "gridReference": "SP4433"}
    got = _scheme("NBN_ATLAS", [
        dict(base, year="2019", recordedBy="J. Moore"),
        dict(base, eventDate="2024-05-01/2024-05-15", recordedBy="J. Moore"),
        dict(base, eventDate="2024-05-01", eventDateEnd="2024-05-15"),
        dict(base, eventDate="2024-06"),
        dict(base, year="2019", month="6", day="5"),
        dict(base, eventDate="2024-06-03")])
    assert [(r.date, r.date_type) for r in got] == [
        ("2019-01-01", "Y"), ("2024-05-01", "DD"), ("2024-05-01", "DD"), ("2024-06-01", "O"),
        ("2019-06-05", "D"), ("2024-06-03", "D")]
    assert got[0].recorder == got[1].recorder == "J. Moore"
    assert "2024-05-15" in got[1].import_notes                  # the end of the range is noted


def test_imp12_irecord_keeps_its_own_date_type(app):
    got = _scheme("IRECORD", [{"ID": "1", "Taxon": "Rutpela maculata", "TaxonVersionKey": "RM",
                               "Date interpreted": "2015", "Date type": "Y", "Output map ref": "SP4433"}])
    assert (got[0].date, got[0].date_type, got[0].status.name) == ("2015-01-01", "Y", "VALID")


def test_imp13_scheme_future_roman_and_unreadable_dates(app):
    got = _scheme("GENERIC_CSV", [dict(OK, Date=d) for d in ("01/06/2030", "6.vi.2021", "31/02/2024")])
    assert got[0].status.name == "ERROR" and "Date is in the future" in got[0].error_message
    assert (got[1].status.name, got[1].date) == ("VALID", "2021-06-06")
    # was saved valid with no date (NaN was read as a date)
    assert got[2].status.name == "ERROR" and "Unreadable date: '31/02/2024'" in got[2].error_message
    nbn = _scheme("NBN_ATLAS", [{"scientificName": "Rutpela maculata", "gridReference": "SP4433",
                                 "eventDate": "2031-01-01"}])
    assert nbn[0].status.name == "ERROR" and "future" in nbn[0].error_message


def test_imp13_scheme_tetrad(app):
    got = _scheme("GENERIC_CSV", [dict(OK, **{"Grid Ref": "SP46Q"})], vc=VC())
    assert (got[0].status.name, got[0].vc_number) == ("VALID", 38)


def test_imp11_wood_a_is_a_site_not_a_species(app):
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    w = SchemeImportWizard(parent=None, uksi_model=None, vc_service=None, db=None)
    w.columns = ["Site name", "Vice County", "Species", "Date", "Grid Ref", "Quantity"]
    mapping = w._fuzzy_match_columns()
    assert mapping["species_name"] == "Species" and mapping["quantity"] == "Quantity"
    got = _scheme("GENERIC_CSV", [{"Site name": "Wood A", "Vice County": "Oxfordshire",
                                   "Species": "Rutpela maculata", "Date": "01/06/2024",
                                   "Grid Ref": "SP4433", "Quantity": "2"}], mapping=mapping)
    assert (got[0].species_name, got[0].site_name, got[0].quantity) == ("Rutpela maculata", "Wood A", 2)
    w.deleteLater()


PERSONAL = {"species_name": "Species", "date": "Date", "recorder": "Recorder", "grid_ref": "Grid Ref",
            "quantity": "Quantity"}


def _obs(raws, mode="PERSONAL_UPLOAD", vc=None):
    from src.views.dialogs.observation_import_wizard.validation_worker import (
        ImportMode, ObservationImportRow, ObservationValidationWorker)
    rows = [ObservationImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
    w = ObservationValidationWorker(rows=rows, column_mapping=PERSONAL, import_mode=ImportMode[mode],
                                    uksi_model=FakeUKSIModel(), vc_db_path=None, db_manager=None)
    if vc is not None:
        w.run = _with_vc(w, vc)
    return _run(w)


OBS = dict(OK, Recorder="W")


def test_imp12_13_observation_counts_dates_and_tetrads(app):
    got = _obs([dict(OBS, Quantity="c.20"), dict(OBS, Quantity="0"), dict(OBS, Date="01/06/2030"),
                dict(OBS, Date="6.vi.2021"), dict(OBS, **{"Grid Ref": "SP46Q"}), dict(OBS, Date="2019")],
               vc=VC())
    assert (got[0].quantity, got[0].organism_quantity) == (20, "c.20")
    assert got[1].quantity == 0 and got[1].status.name == "WARNING"
    assert got[2].status.name == "ERROR" and "Date is in the future" in got[2].error_message
    assert (got[3].status.name, got[3].date) == ("VALID", "2021-06-06")
    assert (got[4].status.name, got[4].vc_number) == ("VALID", 38) and got[4].latitude
    # your own records need the day (unchanged rule; the message now says why)
    assert got[5].status.name == "ERROR" and "is a year, not a day" in got[5].error_message
    irec = _obs([{"ID": "1", "Taxon": "Rutpela maculata", "TaxonVersionKey": "RM", "Output map ref": "SP4433",
                  "Date interpreted": "01/06/2024 to 05/06/2024", "Date type": "DD"}], mode="IRECORD_SYNC")
    assert (irec[0].date, irec[0].date_type, irec[0].status.name) == ("2024-06-01", "DD", "VALID")


SMAP = {"species_name": "Taxon", "date_collected": "Date", "grid_ref": "Grid Ref", "sex": "Sex",
        "specimen_code": "Code"}
SPEC = {"Taxon": "Rutpela maculata", "Grid Ref": "SP4433", "Date": "01/06/2024"}


def _spec(raws, db=None, vc=None):
    from src.views.dialogs.specimen_import_wizard.validation_worker import ImportRow, ValidationWorker
    rows = [ImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
    w = ValidationWorker(rows, SMAP, FakeUKSIModel(), None, db_manager=db)
    w.run = _with_vc(w, vc or VC())
    return _run(w)


def _held_specimens():
    db = MemDB({"specimens": ["specimen_code", "species_name", "species_tvk", "date_collected", "grid_ref",
                              "sex", "vice_county", "vc_number", "site_name", "collector", "determiner",
                              "common_name", "order_name", "family", "subfamily", "taxonomic_sort_key",
                              "taxon_group", "superfamily", "preparation_type", "storage_location",
                              "drawer_number", "condition", "label_data", "notes", "import_notes",
                              "created_at", "updated_at"]})
    for code, sex in (("", "Male"), ("", "Male"), ("WJH-7", None)):
        db.c.execute("INSERT INTO specimens (specimen_code, species_name, species_tvk, date_collected, grid_ref, sex)"
                     " VALUES (?, 'Rutpela maculata', 'RM', '2024-06-01', 'SP4433', ?)", (code or None, sex))
    return db


def test_imp7_specimen_sex_and_duplicates(app):
    db = _held_specimens()
    got = _spec([dict(SPEC, Sex="m"), dict(SPEC, Sex="M"), dict(SPEC, Sex="male"),     # 2 males held
                 dict(SPEC, Sex="F"), dict(SPEC, Sex="worker"),
                 dict(SPEC, Code="WJH-7"), dict(SPEC, Code="WJH-8")], db=db)
    assert [r.sex for r in got] == ["Male", "Male", "Male", "Female", "worker", "", ""]
    assert [r.is_duplicate for r in got] == [True, True, False, False, False, True, False]
    assert {got[0].existing_record_id, got[1].existing_record_id} == {1, 2}
    assert got[5].existing_record_id == 3 and "Already in the collection" in got[5].error_message
    assert "Non-standard sex: worker" in got[4].warnings


def test_imp13_specimen_dates_and_tetrads(app):
    got = _spec([dict(SPEC, Date="01/06/2030"), dict(SPEC, Date="6.vi.2021"),
                 dict(SPEC, **{"Grid Ref": "SP46Q"}), dict(SPEC, Date="2019")])
    assert got[0].status.name == "ERROR" and "Date is in the future" in got[0].error_message
    assert got[1].date_collected == "2021-06-06" and "date" not in got[1].error_message.lower()
    assert got[2].vc_number == 38 and "grid" not in got[2].error_message.lower()
    assert got[3].status.name == "ERROR" and "a specimen needs the day" in got[3].error_message


def test_imp11_imp7_specimen_mapping_offers_sex(app):
    from src.views.dialogs.specimen_import_wizard import SpecimenImportWizard
    w = SpecimenImportWizard(parent=None, uksi_model=None, vc_service=None, db=None)
    w.columns = ["Site name", "Taxon", "Date", "Grid Ref", "Sex", "Collector", "ID"]
    w._setup_column_mapping()
    m = {k: c.currentData() for k, c in w.mapping_combos.items() if c.currentData()}
    assert m == {"species_name": "Taxon", "date_collected": "Date", "grid_ref": "Grid Ref",
                 "site_name": "Site name", "collector": "Collector", "sex": "Sex", "specimen_code": "ID"}
    w.deleteLater()


# ================================================================== IMP-6 inline edits


class FakePicker:
    """Stands in for the species search dialog: the user picks Rutpela maculata."""
    picked = {"scientific_name": "Rutpela maculata", "tvk": "RM", "common_name": "Spotted Longhorn",
              "order_name": "Coleoptera", "family": "Cerambycidae", "kingdom": "Animalia"}

    def __init__(self, *a, **k):
        pass

    def exec(self):
        return 1

    def get_selected_species(self):
        return dict(self.picked)


def _scheme_wizard(rows, mode="generic_csv", db=None):
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    w = SchemeImportWizard(parent=None, uksi_model=FakeUKSIModel(), vc_service=None, db=db)
    for card in w.mode_cards:
        if card.mode_id == mode:
            w._select_mode_card(card)
    w.columns = list(GEN.values())
    w._populate_mapping_page()
    for field, col in GEN.items():
        w.mapping_combos[field].setCurrentIndex(w.mapping_combos[field].findData(col))
    w.raw_rows = [r.raw_data for r in rows]
    w._setup_validation_table()
    w._on_validation_finished(rows)
    return w


def test_imp6_scheme_edits_are_kept_and_revalidated(app, quiet):
    rows = _scheme("GENERIC_CSV", [dict(OK, Date="31/02/2024"), dict(OK)])
    assert rows[0].status.name == "ERROR"
    w = _scheme_wizard(rows)
    model = w.validation_model
    assert not model.flags(model.index(0, 2)) & Qt.ItemIsEditable          # species: double-click
    assert model.setData(model.index(0, 3), "01/07/2024", Qt.EditRole)
    assert w.validated_rows[0].date == "01/07/2024" and not w.next_btn.isEnabled()
    assert model.data(model.index(0, 3)) == "01/07/2024"
    w._revalidate_edited_rows()
    r = w.validated_rows[0]
    assert (r.status.name, r.date) == ("VALID", "2024-07-01") and w.next_btn.isEnabled()
    assert w.validated_rows[1] is rows[1]                                  # untouched rows stay
    w.deleteLater()


def test_imp6_scheme_irecord_rows_are_not_edited(app, quiet):
    rows = _scheme("IRECORD", [{"ID": "1", "Taxon": "Rutpela maculata", "TaxonVersionKey": "RM",
                                "Date interpreted": "01/06/2024", "Output map ref": "SP4433"}])
    w = _scheme_wizard(rows, mode="irecord")
    assert not w.validation_model.flags(w.validation_model.index(0, 3)) & Qt.ItemIsEditable
    w.deleteLater()


def test_imp6_scheme_species_double_click_picks_and_keeps_other_errors(app, quiet, monkeypatch):
    import src.views.dialogs.scheme_import_wizard.wizard_validation_mixin as m
    monkeypatch.setattr(m, "SpeciesSearchDialog", FakePicker)
    rows = _scheme("GENERIC_CSV", [dict(OK, Species="Rutpela maculta"),
                                   dict(OK, Species="Rutpela maculta", Date="31/02/2024")])
    w = _scheme_wizard(rows)
    w._on_cell_double_clicked(0, 2)                       # crashed: QTableView has no item()
    w._on_cell_double_clicked(1, 2)
    a, b = w.validated_rows
    assert (a.species_name, a.species_tvk, a.status.name) == ("Rutpela maculata", "RM", "WARNING")
    assert "picked by you" in a.import_notes
    assert b.species_tvk == "RM" and b.status.name == "ERROR" and "31/02/2024" in b.error_message
    # a revalidation does not lose the pick
    w.validation_model.setData(w.validation_model.index(1, 3), "01/06/2024", Qt.EditRole)
    w._revalidate_edited_rows()
    assert (w.validated_rows[1].species_tvk, w.validated_rows[1].status.name) == ("RM", "WARNING")
    assert "Imported as 'Rutpela maculta'" in w.validated_rows[1].import_notes
    w.deleteLater()


def _spec_wizard(rows, db=None):
    from src.views.dialogs.specimen_import_wizard import SpecimenImportWizard
    w = SpecimenImportWizard(parent=None, uksi_model=FakeUKSIModel(), vc_service=VC(), db=db)
    w.column_mapping = dict(SMAP)
    w.validated_rows = rows
    w._setup_validation_table()
    w._on_validation_finished(rows)
    return w


def test_imp6_specimen_edits_kept_pick_keeps_date_error(app, quiet, monkeypatch):
    import src.views.dialogs.specimen_import_wizard.wizard_validation_mixin as m
    monkeypatch.setattr(m, "SpeciesSearchDialog", FakePicker)
    rows = _spec([dict(SPEC, Date="31/02/2024"), dict(SPEC, Taxon="Rutpela maculta", Date="31/02/2024")])
    w = _spec_wizard(rows)
    assert w.export_problems_btn.isEnabled()                 # IMP-18: was never enabled
    w._on_cell_double_clicked(1, 2)
    assert rows[1].species_tvk == "RM" and rows[1].status.name == "ERROR"   # used to become VALID
    model = w.validation_model
    assert model.setData(model.index(0, 3), "6.vi.2021", Qt.EditRole)
    assert model.setData(model.index(0, 4), "sp 46 q", Qt.EditRole)
    assert rows[0].grid_ref == "SP46Q" and not w.next_btn.isEnabled() and w.revalidate_btn.isEnabled()
    w._revalidate_edited_rows()
    assert (rows[0].date_collected, rows[0].vc_number) == ("2021-06-06", 38)
    assert rows[0].status.name != "ERROR" and w.next_btn.isEnabled()
    w.deleteLater()


# ================================================================== IMP-9 / IMP-16 / IMP-7 imports

SCHEME_COLS = ["irecord_id", "nbn_atlas_id", "occurrence_id", "record_key", "external_key", "event_id",
               "collection_code", "dataset_name", "institution_code", "source", "species_name", "species_tvk",
               "common_name", "taxon_author", "order_name", "family", "subfamily", "genus", "kingdom", "phylum",
               "class_name", "taxon_group", "taxon_rank", "identification_qualifier", "identification_remarks",
               "recorder_certainty", "date", "date_type", "grid_ref", "grid_precision", "vice_county",
               "vc_number", "site_name", "site_name_local", "country", "state_province", "latitude", "longitude",
               "geodetic_datum", "location_id", "location_remarks", "georeference_verification_status",
               "sensitive", "sensitive_site", "sensitive_output_map_ref", "recorder", "determiner", "verifier",
               "verified_on", "sex", "stage", "quantity", "individual_count", "organism_quantity",
               "organism_quantity_type", "zero_abundance", "method", "basis_of_record", "occurrence_status",
               "comment", "internal_notes", "import_notes", "superfamily", "taxonomic_sort_key",
               "sample_comment", "biotope", "verification_status", "verification_status_2", "automated_checks",
               "licence", "rights_holder", "images", "input_on_date", "last_edited_date", "sync_status",
               "created_at", "updated_at"]


def _scheme_rows_for_import():
    from src.views.dialogs.row_status import RowStatus
    from src.views.dialogs.scheme_import_wizard.validation_worker import SchemeImportRow
    base = dict(raw_data={}, date="2024-06-01", grid_ref="SP4433")
    return [
        SchemeImportRow(row_number=2, species_name="Rutpela maculata", species_tvk="RM", status=RowStatus.VALID,
                        quantity=0, date_type="Y", **base),
        SchemeImportRow(row_number=3, species_name="Nosuch name", status=RowStatus.ERROR,
                        error_message="Species not found", **base),
        SchemeImportRow(row_number=4, species_name="Rutpela maculata", species_tvk="RM", status=RowStatus.WARNING,
                        is_duplicate=True, existing_record_id=1, verification_status="Accepted", **base),
        SchemeImportRow(row_number=5, species_name="Carabus nemoralis", species_tvk="CN", status=RowStatus.WARNING,
                        warnings=["x"], **base),
        SchemeImportRow(row_number=6, species_name="Rutpela maculata", species_tvk="RM", status=RowStatus.WARNING,
                        is_duplicate=True, existing_record_id=1, **base)]


def _scheme_import(errors, warnings=True, update=False):
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    db = MemDB({"recording_scheme": SCHEME_COLS})
    db.c.execute("INSERT INTO recording_scheme (species_name, species_tvk, date) "
                 "VALUES ('Rutpela maculata', 'RM', '2024-06-01')")
    w = SchemeImportWizard(parent=None, uksi_model=None, vc_service=None, db=db)
    w.validated_rows = _scheme_rows_for_import()
    w.import_errors_checkbox.setChecked(errors)
    w.import_warnings_checkbox.setChecked(warnings)
    w.update_duplicates_checkbox.setChecked(update)
    w.stack.setCurrentIndex(3)
    w._go_next()                                    # to the options page
    ready = w.confirm_status_label.text()
    w._go_next()                                    # Import
    w._go_next()                                    # Summary
    out = (db.rows("recording_scheme", "species_name, quantity, date_type, verification_status")[1:],
           w.summary_stats.text(), ready)
    w.deleteLater()
    return out


def test_imp9_16_scheme_rows_with_errors_and_the_summary(app, quiet):
    written, summary, ready = _scheme_import(errors=False)
    assert [r["species_name"] for r in written] == ["Rutpela maculata", "Carabus nemoralis"]
    assert written[0]["quantity"] == 0 and written[0]["date_type"] == "Y"           # IMP-12
    assert summary.splitlines() == ["New records: 2", "Duplicates skipped: 2", "Rows with errors, not imported: 1"]
    assert ready == "Ready to import 2 new record(s); 3 row(s) left out"
    written, summary, _ = _scheme_import(errors=True)                                # IMP-9: was 2
    assert [r["species_name"] for r in written] == ["Rutpela maculata", "Nosuch name", "Carabus nemoralis"]
    assert summary.splitlines() == ["New records: 3", "Duplicates skipped: 2"]
    written, summary, _ = _scheme_import(errors=False, warnings=False)               # was ignored
    assert [r["species_name"] for r in written] == ["Rutpela maculata"]
    assert summary.splitlines() == ["New records: 1", "Duplicates skipped: 2",
                                    "Rows with errors, not imported: 1", "Rows with warnings, not imported: 1"]
    written, summary, ready = _scheme_import(errors=False, update=True)
    assert summary.splitlines() == ["New records: 2", "Updated records: 1",
                                    "Duplicates already up to date (not changed): 1",
                                    "Rows with errors, not imported: 1"]
    assert "update 2 held" in ready


def test_imp18_scheme_options_page_has_no_dead_progress_bar(app):
    from src.views.dialogs.scheme_import_wizard import SchemeImportWizard
    w = SchemeImportWizard(parent=None, uksi_model=None, vc_service=None, db=None)
    assert w.stack.indexOf(w.import_progress.parentWidget()) == 5
    assert w.stack.indexOf(w.import_status_label.parentWidget()) == 5
    assert w.stack.indexOf(w.confirm_status_label.parentWidget()) == 4
    w.deleteLater()


def _obs_import(radio):
    from src.views.dialogs.observation_import_wizard import ObservationImportWizard
    from src.views.dialogs.observation_import_wizard.validation_worker import ObservationImportRow
    from src.views.dialogs.row_status import RowStatus
    w = ObservationImportWizard(parent=None, uksi_model=None, vc_service=None, db=None, observation_model=object())
    for card in w.mode_cards:
        if card.mode_id == "personal_upload":
            w._select_mode_card(card)
    base = dict(raw_data={}, date="2024-06-01", grid_ref="SP4433", recorder="W")
    w.validated_rows = [
        ObservationImportRow(row_number=2, species_name="Rutpela maculata", species_tvk="RM",
                             status=RowStatus.VALID, quantity=20, organism_quantity="c.20", **base),
        ObservationImportRow(row_number=3, species_name="Nosuch name", status=RowStatus.ERROR,
                             error_message="Species not found", **base),
        ObservationImportRow(row_number=4, species_name="Rutpela maculata", species_tvk="RM", status=RowStatus.VALID,
                             is_duplicate=True, existing_record_id=5, **base),
        ObservationImportRow(row_number=5, species_name="Carabus nemoralis", species_tvk="CN",
                             status=RowStatus.WARNING, warnings=["w"], quantity=0, **base)]
    cols = list(w._row_to_observation_dict(w.validated_rows[0], w._get_selected_mode()))
    db = MemDB({"observations": cols})
    w.db = db
    w.stack.setCurrentIndex(4)
    w._update_step_ui()
    w._update_confirmation_counts()
    getattr(w, radio).setChecked(True)
    button = w.next_btn.text()
    w._go_next()
    out = db.rows("observations", "species_name, quantity, organism_quantity"), w.summary_stats.text(), button
    w.deleteLater()
    return out


def test_imp9_16_observation_row_handling_and_summary(app, quiet):
    rows, summary, button = _obs_import("import_warnings_checkbox")        # "...including errors"
    assert [r["species_name"] for r in rows] == ["Rutpela maculata", "Nosuch name", "Carabus nemoralis"]
    assert summary.splitlines() == ["New records: 3", "Duplicates skipped: 1"]
    assert button == "Import 3 Records (1 skipped)"
    assert (rows[0]["quantity"], rows[0]["organism_quantity"], rows[2]["quantity"]) == (20, "c.20", 0)  # IMP-12
    rows, summary, button = _obs_import("import_all_checkbox")
    assert len(rows) == 2 and button == "Import 2 Records (2 skipped)"
    assert summary.splitlines() == ["New records: 2", "Duplicates skipped: 1", "Rows with errors, not imported: 1"]
    rows, summary, _ = _obs_import("import_valid_only_checkbox")
    assert [r["species_name"] for r in rows] == ["Rutpela maculata"]
    assert summary.splitlines() == ["New records: 1", "Duplicates skipped: 1", "Rows with errors, not imported: 1",
                                    "Rows with warnings, not imported: 1"]


def test_imp18_observation_rows_are_not_marked_edited_by_filling_the_table(app):
    from src.views.dialogs.observation_import_wizard import ObservationImportWizard
    from src.views.dialogs.observation_import_wizard.validation_worker import ImportMode, ObservationImportRow
    from src.views.dialogs.row_status import RowStatus
    w = ObservationImportWizard(parent=None, uksi_model=None, vc_service=None, db=None)
    for card in w.mode_cards:
        if card.mode_id == "personal_upload":
            w._select_mode_card(card)
    w._setup_validation_table(ImportMode.PERSONAL_UPLOAD)
    rows = [ObservationImportRow(row_number=i + 2, raw_data={}, status=RowStatus.VALID, species_name="X",
                                 date="2024-06-01") for i in range(5)]
    w.next_btn.setEnabled(True)
    for i, r in enumerate(rows):
        w._on_row_validated(i, r)
    w.validated_rows = rows
    w._update_table_row_display(0, rows[0], ImportMode.PERSONAL_UPLOAD)
    assert w._edited_row_indices == set() and w.next_btn.isEnabled()        # was all 5, Next off
    w.validation_table.item(3, 3).setText("02/06/2024")                     # a real edit still counts
    assert w._edited_row_indices == {5}
    assert not hasattr(w, "include_errors_checkbox")                        # the parentless box is gone
    w.deleteLater()


def test_imp7_9_16_specimen_import_skips_held_writes_sex(app, quiet):
    db = _held_specimens()
    rows = _spec([dict(SPEC, Sex="m"), dict(SPEC, Sex="F"), dict(SPEC, Date="31/02/2024")], db=db)
    for r in rows:
        r.taxonomic_sort_key = 5                       # the made-up TVKs are not in the real UKSI
    w = _spec_wizard(rows, db=db)
    w.stack.setCurrentIndex(3)
    w._go_next()
    new = db.rows("specimens", "species_name, sex, date_collected")[3:]
    assert new == [{"species_name": "Rutpela maculata", "sex": "Female", "date_collected": "2024-06-01"}]
    assert w.summary_stats.text().splitlines() == [
        "Specimens imported: 1", "Already in the collection, skipped: 1", "Rows with errors, not imported: 1"]
    w.deleteLater()


def test_imp7_specimen_held_on_another_tvk_of_the_name_is_still_found(app):
    db = _held_specimens()
    db.c.execute("INSERT INTO specimens (species_name, species_tvk, date_collected, grid_ref) "
                 "VALUES ('Andrena proxima', 'APL', '2024-06-01', 'SP4433')")      # held on the s.l. TVK
    got = _spec([dict(SPEC, Taxon="Andrena proxima"), dict(SPEC, Taxon="Andrena proxima")], db=db)
    assert got[0].species_tvk == "APS"                                           # species over s.l.
    assert [r.is_duplicate for r in got] == [True, False] and got[0].existing_record_id == 4
