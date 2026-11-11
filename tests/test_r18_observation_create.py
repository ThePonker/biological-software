"""R18 B5: ObservationModel.create(observation, extra=...) writes the columns its fixed list omitted
(import_notes, the survey columns, superfamily, subfamily, taxonomic_sort_key ...) in the one INSERT.

The proof: a tiny database from the real schema (scripts/reset_database.py), the OLD path (the
create() INSERT as it was, frozen below, then the second UPDATE) against the NEW path, for each caller
that used to UPDATE after create() -- Data Entry's commit_job and Quick Entry's save -- comparing
every column of every stored row."""
import importlib.util
import os
import sqlite3
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.models import observation as obs_mod  # noqa: E402
from src.models.observation import Observation, ObservationModel  # noqa: E402

_spec = importlib.util.spec_from_file_location("reset_database_for_test",
                                               os.path.join(ROOT, "scripts", "reset_database.py"))
_reset = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_reset)

STAMP = "2026-11-10T12:00:00"

# The create() INSERT as it was before R18 (frozen: this is the "old path").
OLD_COLUMNS = (
    "irecord_id, record_key, external_key, event_id, collection_code, dataset_name, institution_code, "
    "source, species_name, species_tvk, common_name, order_name, family, kingdom, taxon_group, "
    "taxon_rank, identification_qualifier, identification_remarks, recorder_certainty, date, "
    "date_type, grid_ref, grid_precision, vice_county, vc_number, site_name, site_name_local, "
    "latitude, longitude, geodetic_datum, location_id, location_remarks, "
    "georeference_verification_status, recorder, determiner, verifier, verified_on, sex, stage, "
    "quantity, individual_count, organism_quantity, organism_quantity_type, zero_abundance, method, "
    "basis_of_record, occurrence_status, comment, internal_notes, sample_comment, biotope, "
    "verification_status, verification_status_2, automated_checks, record_type, project_name, client, "
    "embargo_status, embargo_until, licence, rights_holder, images, sensitive, sensitive_site, "
    "sensitive_output_map_ref, input_on_date, last_edited_date, sync_status, never_upload_to_irecord, "
    "observatum_key, created_at, updated_at")


class Db:
    """The bits of DatabaseManager the model, commit_job and Quick Entry use, over one sqlite file."""

    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_reset.CREATE_OBSERVATIONS)

    def execute_main(self, query, params=()):
        return self.conn.execute(query, params).fetchall()

    def execute_main_write(self, query, params=()):
        cur = self.conn.execute(query, params)
        self.conn.commit()
        return cur.lastrowid if cur.lastrowid else cur.rowcount

    def rows(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM observations ORDER BY id")]


def old_create(db, o):
    """create() as it was: the fixed INSERT, nothing else."""
    cols = [c.strip() for c in OLD_COLUMNS.split(",")]
    key = f"OBS-TEST-{db.execute_main('SELECT COUNT(*) FROM observations')[0][0] + 1}"
    vals = {c: getattr(o, c, None) for c in cols}
    vals.update(observatum_key=key, created_at=STAMP, updated_at=STAMP)
    return db.execute_main_write(
        f"INSERT INTO observations ({OLD_COLUMNS}) VALUES ({', '.join('?' * len(cols))})",
        tuple(vals[c] for c in cols))


@pytest.fixture
def fixed(monkeypatch):
    """The same timestamp and observatum_key whichever path writes a record."""
    class _DT:
        @staticmethod
        def now():
            import datetime
            return datetime.datetime.fromisoformat(STAMP)
    monkeypatch.setattr(obs_mod, "datetime", _DT)
    monkeypatch.setattr(ObservationModel, "_generate_observatum_key", lambda self: (
        f"OBS-TEST-{self.db.execute_main('SELECT COUNT(*) FROM observations')[0][0] + 1}"))


def _make(tmp_path, name):
    return Db(str(tmp_path / f"{name}.db"))


# ---------------------------------------------------------------- create itself
def test_create_without_extra_is_the_old_insert(tmp_path, fixed):
    a, b = _make(tmp_path, "a"), _make(tmp_path, "b")
    o = Observation(species_name="Rutpela maculata", species_tvk="T1", date="2024-06-15",
                    grid_ref="SP4433", vc_number=23, kingdom="Animalia", taxon_group="beetle",
                    taxon_rank="Species", recorder="W", comment="c", record_type="Commercial")
    assert old_create(a, o) == ObservationModel(b).create(o) == 1
    assert a.rows() == b.rows()


def test_create_writes_extra_columns_in_the_same_insert(tmp_path, fixed):
    db = _make(tmp_path, "a")
    extra = {"import_notes": "n", "sub_location": "N", "trap_number": "3", "visit_number": "2",
             "superfamily": "Apoidea", "subfamily": "Crabroninae", "taxonomic_sort_key": 5,
             "latitude": 51.5}
    new_id = ObservationModel(db).create(Observation(species_name="X y", date="2024-01-01"), extra)
    row = db.rows()[0]
    assert new_id == 1 and {k: row[k] for k in extra} == extra


def test_unknown_or_reserved_keys_are_refused_and_nothing_is_written(tmp_path, fixed):
    db = _make(tmp_path, "a")
    m = ObservationModel(db)
    o = Observation(species_name="X y", date="2024-01-01")
    with pytest.raises(ValueError, match="no column.*not_a_column"):
        m.create(o, {"superfamily": "S", "not_a_column": 1})
    for reserved in ("id", "observatum_key", "created_at", "updated_at"):
        with pytest.raises(ValueError, match="itself"):
            m.create(o, {reserved: "x"})
    assert db.rows() == []


# ---------------------------------------------------------------- caller 1: Data Entry commit_job
def test_commit_job_stores_the_same_rows_as_create_then_update(tmp_path, fixed):
    from DataEntry import staging_repo as repo
    from DataEntry.commit_service import build_kwargs_from_row, commit_job
    conn = sqlite3.connect(tmp_path / "s.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "Hook Farm", "Commercial", "BAM", "Hook Farm")
    base = dict(species_tvk="T1", date="2026-06-05", site_name="Elmley", grid_ref="TQ9368",
                method="Sweep", stage="Adult", recorder="Heeney, W.J.", vc_number=15,
                order_name="Hymenoptera", family="Crabronidae")
    repo.insert_row(conn, jid, dict(base, species_name="Philanthus triangulum", sex="f",
                                    sub_location="North", trap_number="T3", visit_number="2"))
    repo.insert_row(conn, jid, dict(base, species_name="Cerceris rybyensis", species_tvk="T2"))
    job = repo.get_job(conn, jid)
    tax = {"T1": {"taxon_group": "insect - hymenopteran", "kingdom": "Animalia", "taxon_rank": "Species",
                  "superfamily": "Apoidea", "taxonomic_sort_key": 26000001}}      # T2: none (NULL)
    rows = repo.fetch_rows(conn, jid)

    new_db = _make(tmp_path, "new")
    s = commit_job(new_db, ObservationModel(new_db), conn, job, taxonomy=tax)
    assert s["committed"] == 2 and s["error"] is None

    old_db = _make(tmp_path, "old")
    for row in rows:                                    # the old commit_job body: create, then UPDATE
        t = tax.get((row.get("species_tvk") or "").strip()) or {}
        new_id = old_create(old_db, Observation(**build_kwargs_from_row(row, job, None, t)))
        old_db.execute_main_write(
            "UPDATE observations SET sub_location=?, trap_number=?, visit_number=?, import_notes=?, "
            "superfamily=?, taxonomic_sort_key=? WHERE id=?",
            (row.get("sub_location") or None, row.get("trap_number") or None,
             row.get("visit_number") or None, s["batch"],
             t.get("superfamily"), t.get("taxonomic_sort_key"), new_id))

    assert new_db.rows() == old_db.rows()
    first = new_db.rows()[0]
    assert (first["sub_location"], first["trap_number"], first["visit_number"]) == ("North", "T3", "2")
    assert first["superfamily"] == "Apoidea" and first["import_notes"] == s["batch"]
    assert new_db.rows()[1]["superfamily"] is None


# ---------------------------------------------------------------- caller 2: Quick Entry
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("tax", [{"superfamily": "Cerambycoidea", "taxonomic_sort_key": 123,
                                  "kingdom": "Animalia", "taxon_rank": "Species"},
                                 {"superfamily": None, "taxonomic_sort_key": 77},
                                 {}])
def test_quick_entry_stores_the_same_row_as_create_then_update(tmp_path, fixed, qapp, monkeypatch, tax):
    import src.views.home.quick_entry as qe
    monkeypatch.setattr(qe, "get_vc_service", lambda: type("V", (), {
        "get_vice_county": lambda self, g: {"name": "Oxfordshire", "number": 23}})())
    monkeypatch.setattr(qe.QuickEntryForm, "_taxonomy", staticmethod(lambda tvk: dict(tax)))
    monkeypatch.setattr(qe, "get_search_service", lambda: type("S", (), {
        "add_recorded_tvk": lambda self, t: None})())
    new_db = _make(tmp_path, "new")
    monkeypatch.setattr(qe, "get_database", lambda: new_db)
    f = qe.QuickEntryForm()
    f.set_species({"scientific_name": "Rhagium mordax", "tvk": "NBNSYS0000010506",
                   "common_name": "", "order": "Coleoptera", "family": "Cerambycidae"})
    f.grid_ref_edit.setText("SP4537")
    f.location_edit.setText("Hook Farm")
    f.recorder_edit.setText("Heeney, W.J.")
    f.determiner_edit.setText("Heeney, W.J.")
    form_data = f._collect_form_data()
    old_observation = f._create_observation(form_data, dict(tax))
    f._on_save_clicked()
    assert len(new_db.rows()) == 1

    old_db = _make(tmp_path, "old")                     # the old save: create, then the UPDATE
    new_id = old_create(old_db, old_observation)
    if tax.get("superfamily") or tax.get("taxonomic_sort_key"):
        old_db.execute_main_write("UPDATE observations SET superfamily=?, taxonomic_sort_key=? WHERE id=?",
                                  (tax.get("superfamily"), tax.get("taxonomic_sort_key"), new_id))
    assert new_db.rows() == old_db.rows()
    assert new_db.rows()[0]["taxonomic_sort_key"] == tax.get("taxonomic_sort_key")
