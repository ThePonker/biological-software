"""Round 12, builder C: stored-data and wording corrections (24 Oct 2026).

Small hand-built databases in tmp_path; nothing real is touched, no figure is pinned.
"""
import importlib.util
import os
import sqlite3
import sys
from types import SimpleNamespace as S

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paths  # noqa: E402


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def uksi(tmp_path):
    p = tmp_path / "uksi.db"
    u = sqlite3.connect(p)
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, '
              'kingdom TEXT, phylum TEXT, class TEXT, "order" TEXT, family TEXT, genus TEXT, '
              'sort_code INTEGER, superfamily TEXT)')
    u.execute("CREATE TABLE common_names (tvk TEXT, common_name TEXT, preferred INTEGER)")
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [
        ("SF1", "Carabinae", "Subfamily", None, "Animalia", "Arthropoda", "Insecta", "Coleoptera",
         "Carabidae", None, 1, None),
        ("G1", "Carabus", "Genus", "SF1", "Animalia", "Arthropoda", "Insecta", "Coleoptera",
         "Carabidae", "Carabus", 2, None),
        ("OLD", "Old name", "Genus", None, "Animalia", "Arthropoda", "Arachnida", "Araneae",
         "Linyphiidae", None, 7, None),
        ("NEW", "Carabus nemoralis", "Species", "G1", "Animalia", "Arthropoda", "Insecta",
         "Coleoptera", "Carabidae", "Carabus", 18000, "Caraboidea"),
    ])
    u.execute("INSERT INTO common_names VALUES ('NEW', 'Bronze Carabid', 1)")
    u.commit()
    u.close()
    return str(p)


def _obs_db(path, rows):
    o = sqlite3.connect(path)
    o.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species_name TEXT, species_tvk TEXT, "
              "taxon_rank TEXT, kingdom TEXT, taxon_group TEXT, superfamily TEXT, subfamily TEXT, "
              "taxonomic_sort_key INTEGER)")
    o.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?)", rows)
    o.commit()
    o.close()


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "scripts", "_oneoff", name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- G1: re-determination
def test_redet_recomputes_taxonomy_fields(uksi):
    from Observatum.src.views.observations.observation_detail_mixin import with_redet_taxonomy
    updates = with_redet_taxonomy({"species_name": "Carabus nemoralis", "species_tvk": "NEW"},
                                  "OLD", uksi)
    assert updates["taxon_rank"] == "Species"
    assert updates["kingdom"] == "Animalia"
    assert updates["taxon_group"] == "insect - beetle (Coleoptera)"
    assert updates["superfamily"] == "Caraboidea"
    assert updates["subfamily"] == "Carabinae"
    assert updates["taxonomic_sort_key"] % 1000000 == 18000 and updates["taxonomic_sort_key"] > 1000000
    # same TVK: nothing added
    same = with_redet_taxonomy({"species_name": "x", "species_tvk": "NEW"}, "NEW", uksi)
    assert set(same) == {"species_name", "species_tvk"}


def test_redet_update_reaches_the_row(tmp_path, uksi):
    from Observatum.src.views.observations.observation_detail_mixin import with_redet_taxonomy
    db = str(tmp_path / "o.db")
    _obs_db(db, [(1, "Old name", "OLD", "Genus", "Animalia", "spider", None, None, 7)])
    conn = sqlite3.connect(db)
    upd = with_redet_taxonomy({"species_name": "Carabus nemoralis", "species_tvk": "NEW"}, "OLD", uksi)
    conn.execute(f"UPDATE observations SET {', '.join(k + ' = ?' for k in upd)} WHERE id = 1",
                 list(upd.values()))
    row = conn.execute("SELECT taxon_rank, taxon_group, taxonomic_sort_key FROM observations").fetchone()
    assert row[0] == "Species" and "Coleoptera" in row[1] and row[2] > 1000000


# ---------------------------------------------------------------- G1: repair script
def test_repair_dry_run_changes_nothing_and_apply_fixes(tmp_path, uksi, monkeypatch, capsys):
    from shared import backup_service
    db = str(tmp_path / "observatum.db")
    _obs_db(db, [(1, "Carabus nemoralis", "NEW", "Genus", "Animalia", "spider", "Wrongoidea", None, 7),
                 (2, "Fine", None, "x", None, None, None, None, None)])
    monkeypatch.setattr(paths, "OBSERVATUM_DB", db)
    monkeypatch.setattr(backup_service, "BACKUP_ROOT", str(tmp_path / "bk"))
    m = _load_script("repair_redet_taxonomy_20261024")
    before = open(db, "rb").read()
    assert m.main(["--db", db, "--uksi", uksi]) == 0
    assert "Nothing has been changed." in capsys.readouterr().out
    assert open(db, "rb").read() == before
    # the default writes only subfamily and sort key (no figure moves); all six on request
    assert m.main(["--db", db, "--uksi", uksi, "--apply",
                   "--fields", "taxon_rank,kingdom,taxon_group,superfamily,subfamily,taxonomic_sort_key"]) == 0
    c = sqlite3.connect(db)
    r = c.execute("SELECT taxon_rank, taxon_group, superfamily, subfamily, taxonomic_sort_key "
                  "FROM observations WHERE id = 1").fetchone()
    assert r[0] == "Species" and "Coleoptera" in r[1] and r[2] == "Caraboidea" and r[3] == "Carabinae"
    assert r[4] % 1000000 == 18000
    assert c.execute("SELECT taxon_rank FROM observations WHERE id = 2").fetchone()[0] == "x"
    assert any(f for _d, _s, fs in os.walk(tmp_path / "bk") for f in fs)       # a backup was written


# ---------------------------------------------------------------- G3: dates
def test_parse_display_date_is_day_first_only():
    from Observatum.src.utils.date_utils import parse_display_date
    assert parse_display_date("06/13/2024") is None
    assert parse_display_date("13/06/2024") == "2024-06-13"
    assert parse_display_date("13 June 2024") == "2024-06-13"
    assert parse_display_date("13-06-2024") == "2024-06-13"
    assert parse_display_date("2024-06-13") == "2024-06-13"


# ---------------------------------------------------------------- G4: scheme VC fallback
def test_scheme_vc_fallback_import_resolves():
    # the import the validation worker makes (three dots from the worker was the wrong package)
    import inspect
    from Observatum.src.views.dialogs.scheme_import_wizard import validation_worker
    assert "from ....core.vc_shortnames import VC_FULL_NAMES" in inspect.getsource(validation_worker)
    from Observatum.src.core.vc_shortnames import VC_FULL_NAMES
    names = {v.lower().strip(): int(k) for k, v in VC_FULL_NAMES.items() if k.isdigit()}
    assert names["east cornwall"] == 2
    m = _load_script("check_scheme_vc_missing_20261024")
    assert callable(m.count_missing)


def test_scheme_vc_check_counts(tmp_path):
    db = str(tmp_path / "o.db")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, vice_county TEXT, vc_number INTEGER)")
    c.executemany("INSERT INTO recording_scheme (vice_county, vc_number) VALUES (?,?)", [
        ("East Cornwall | South Devon", None), ("Nowhereshire", None), ("East Cornwall", 2), (None, None)])
    c.commit()
    c.close()
    total, resolved, unresolved = _load_script("check_scheme_vc_missing_20261024").count_missing(db)
    assert (total, resolved) == (2, 1) and unresolved["Nowhereshire"] == 1


# ---------------------------------------------------------------- G7: scheme dashboard common names
def test_scheme_stats_service_returns_common_names(tmp_path, uksi, monkeypatch):
    from src.services.recording_scheme_stats_service import RecordingSchemeStatsService
    db = tmp_path / "o.db"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, species_name TEXT, species_tvk TEXT, "
              "vc_number INTEGER, date TEXT, date_type TEXT DEFAULT 'D', recorder TEXT)")
    c.execute("INSERT INTO recording_scheme (species_name, species_tvk, vc_number, date, recorder) "
              "VALUES ('Carabus nemoralis', 'NEW', 2, '2001-05-01', 'A')")
    c.commit()
    c.close()

    class Db:
        def execute_main(self, sql, params=()):
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            try:
                return conn.execute(sql, params).fetchall()
            finally:
                conn.close()
    svc = RecordingSchemeStatsService()
    old_db = svc._db
    monkeypatch.setattr(paths, "UKSI_DB", uksi)
    for meth in ("_get_exclusion_clause", "_get_family_clause", "_copies_out"):
        monkeypatch.setattr(svc, meth, lambda prefix="": "")
    try:
        svc.initialize(Db())
        res = svc.get_vc_details(2)
    finally:
        svc._db = old_db
    assert res["species_list"][0]["common_name"] == "Bronze Carabid"
    assert res["county_firsts"][0]["common_name"] == "Bronze Carabid"
    assert res["recording_gaps"][0]["common_name"] == "Bronze Carabid"


# ---------------------------------------------------------------- G10: delete_rows
def test_delete_rows_reports_a_failure(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from DataEntry import entry_grid as eg
    from DataEntry import staging_repo as repo
    conn = sqlite3.connect(tmp_path / "observatum.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "J", "Personal", None, None)
    a = repo.insert_row(conn, jid, {"species_name": "Amara aenea", "quantity": "1"})
    repo.insert_row(conn, jid, {"species_name": "Badister sodalis", "quantity": "1"})
    m = eg.StagingTableModel(conn, jid)
    real = repo.delete_row

    def flaky(c, rid):
        if rid == a:
            raise sqlite3.OperationalError("database is locked")
        return real(c, rid)
    monkeypatch.setattr(eg.repo, "delete_row", flaky)
    assert m.delete_rows([0, 1]) == 1
    assert [n for n, _why in m.delete_failures] == [1]
    assert "locked" in m.delete_failures[0][1]
    assert m.delete_rows([5]) == 0 and m.delete_failures == []


# ---------------------------------------------------------------- G11: Windows-1252 files
def test_specimen_file_saved_as_cp1252_loads(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Observatum.src.views.dialogs.specimen_import_wizard.wizard_file_mixin import WizardFileMixin
    p = tmp_path / "s.csv"
    p.write_bytes("Species,Site\nAmara aenea,Café Wood – north\n".encode("cp1252"))

    class Lbl:
        text = ""

        def setText(self, t):
            self.text = t

        def setStyleSheet(self, _s):
            pass
    stub = S(file_path_label=Lbl(), file_info_label=Lbl(), next_btn=S(setEnabled=lambda _b: None),
             _update_preview_table=lambda: None)
    WizardFileMixin._load_file(stub, str(p))
    assert stub.raw_rows[0]["Site"] == "Café Wood – north"
    assert "Windows-1252" in stub.file_info_label.text
    p.write_bytes("Species,Site\nAmara aenea,Café\n".encode("utf-8-sig"))
    WizardFileMixin._load_file(stub, str(p))
    assert stub.raw_rows[0]["Site"] == "Café" and "Windows-1252" not in stub.file_info_label.text


# ---------------------------------------------------------------- G6: Commercial colour
def test_commercial_row_colour_is_a_real_theme_colour():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.observations.observation_table_model import ObservationTableModel
    m = ObservationTableModel()
    m.set_observations([{"id": 1, "record_type": "Commercial", "species_name": "x"}])
    col = [i for i, c in enumerate(m.get_columns()) if c[0] == "record_type"]
    if not col:
        pytest.skip("record_type is not a default column")
    colour = m.data(m.index(0, col[0]), Qt.ItemDataRole.ForegroundRole)
    assert colour.name().lower() != "#ff00ff"


# ---------------------------------------------------------------- G8: Lector
def test_lector_user_plus_beats_suite_minus(tmp_path):
    from Lector import synonyms as syn
    suite = tmp_path / "suite.csv"
    suite.write_text("action,synonym,tvk,reason\nexclude,Cerambyx textor,T1,wrong\n"
                     "exclude,Lamia sartor,T1,wrong\n", encoding="utf-8")
    user = tmp_path / "user.txt"
    user.write_text("+ Cerambyx textor @ T1 | my call\n", encoding="utf-8")
    rules = syn.SynonymRules.load(user_file=user, suite_csv=suite)
    assert rules.excluded("Cerambyx textor", "Lamia textor", "T1") is None
    assert rules.excluded("Lamia sartor", "Lamia textor", "T1") is not None
    # the suite file is found from the code, not the data root
    assert syn.SUITE_CORRECTIONS.name == "uksi_synonym_corrections.csv"
    assert str(syn.SUITE_CORRECTIONS.parent).startswith(ROOT)


# ---------------------------------------------------------------- G2: CIEEM bands
def test_summary_basis_carries_the_cieem_bands(tmp_path, monkeypatch):
    pytest.importorskip("openpyxl")
    from Examen import workbook_export as we
    seen = {}
    monkeypatch.setattr(we, "_contributions", lambda *a, **k: None)
    monkeypatch.setattr(we, "_codex_provenance", lambda: [])
    monkeypatch.setattr(we, "_reference_counts", lambda: {})
    monkeypatch.setattr(we, "_sat_thresholds", lambda: {})
    monkeypatch.setattr(we, "_mark_derived", lambda *a, **k: None)
    monkeypatch.setattr(we, "_sheet_summary", lambda wb, r, d, p, stamp: (wb.create_sheet("Summary"), seen.update(stamp=stamp)))
    for n in ("_sheet_key_species", "_sheet_appendix", "_sheet_taxonomic", "_sheet_compartments",
              "_sheet_habitats", "_sheet_assemblages", "_sheet_saproxylic", "_sheet_guilds", "_sheet_status"):
        monkeypatch.setattr(we, n, lambda *a, **k: None)
    we.export_workbook(S(mode=""), S(site=S(site_name="S")), S(project_name="P", client="C"),
                       str(tmp_path / "w.xlsx"))
    text = dict(seen["stamp"]["basis"])["Survey validity"]
    for part in ("under 12 months", "12-18 months", "18 months to 3 years", "over 3 years",
                 "unlikely to be valid", "CIEEM, 2019"):
        assert part in text
    assert "Two years" not in text


def test_dialogs_refuse_an_unreadable_full_date():
    """Review 24 Oct: with the US fallback gone, '06/13/2024' must be refused, not stored as typed."""
    from src.utils.date_utils import unreadable_full_date
    assert unreadable_full_date("06/13/2024")
    assert unreadable_full_date("31/02/2024")
    assert not unreadable_full_date("13/06/2024")
    assert not unreadable_full_date("2024")          # a vague date is left as before
    assert not unreadable_full_date("")
