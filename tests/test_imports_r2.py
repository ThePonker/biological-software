"""Round 2 (10 Oct 2026 evening): Wil's note-36 decisions 2, 3, 7, 8, 9 and items L23, L24.

  2  shared species search: whole groups found by a common word after every species match,
     labelled "All Cerambycidae (longhorn beetles) -- group"; filters select what they did
  3  the three import wizards accept a close spelling of ONE species of the same genus
  7  Quick Entry: existing commercial projects only, hint "New projects start in Data Entry"
  8  count of 0: an error in own data (observation import, Data Entry), presence in scheme data
  9  observation import: year / month / range dates accepted with a warning, stored with their
     date type; month charts skip them
  L23 a species picked in an import says what the file had; L24 specimen status shows a tick

Offscreen; the real uksi.db read-only; small throwaway databases for anything written.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

pytestmark = pytest.mark.skipif(not paths.UKSI_DB.exists(), reason="needs data/uksi.db")
HAVE_DATA = os.path.exists(str(paths.OBSERVATUM_DB))
GROUP = " — group"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def uksi():
    conn = sqlite3.connect(f"file:{paths.UKSI_DB}?mode=ro", uri=True)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def model(qapp):
    import species_lookup_harness as h
    h.stub_webengine()
    return h.uksi_model()


# ---------------------------------------------------------------- decision 3: close spellings

def test_close_spelling_same_genus_only(uksi):
    from shared.species_lookup import LookupFailure, lookup_names
    names = ["Rutpela maculta", "Rhagium mordx", "Tetrops starki", "Carabus cf. nemorallis",
             "Rutpla maculata", "Gramoptera ruficornis", "Ab", "Clytus", "Notarealname"]
    r = lookup_names(names, uksi, close_spellings=True)
    got = {n: (r[n].taxon.scientific_name, r[n].how) if not isinstance(r[n], LookupFailure)
           else r[n].kind for n in names}
    assert got["Rutpela maculta"] == ("Rutpela maculata", "close")
    assert got["Rhagium mordx"] == ("Rhagium mordax", "close")
    assert got["Tetrops starki"] == ("Tetrops starkii", "close")
    assert got["Carabus cf. nemorallis"] == ("Carabus nemoralis", "close")
    # looser: misspelt genus, a genus-only name, nothing near -> the pick list
    assert got["Rutpla maculata"] == got["Gramoptera ruficornis"] == "not_found"
    assert got["Ab"] == got["Notarealname"] == "not_found"
    assert got["Clytus"] == ("Clytus", "exact")                    # a genus typed as a genus
    w = r["Rutpela maculta"].warnings
    assert w == ["Close spelling: 'Rutpela maculta' matched to 'Rutpela maculata'"]
    assert "cf. identification" in "; ".join(r["Carabus cf. nemorallis"].warnings)
    # Examen's Import List (the default) is unchanged: exact names and synonyms only
    assert isinstance(lookup_names(["Rutpela maculta"], uksi)["Rutpela maculta"], LookupFailure)


def test_close_spelling_two_near_species_is_not_taken(uksi):
    from shared.species_close_spelling import close_spelling
    assert close_spelling(uksi, "Bombus lucorm").scientific_name == "Bombus lucorum"
    # an epithet under 4 letters is never guessed
    assert close_spelling(uksi, "Bombus a") is None
    assert close_spelling(uksi, "Rhagium") is None                  # one word: never


def _scheme_rows(model, names, qty=None):
    from src.views.dialogs.scheme_import_wizard.validation_worker import (
        SchemeImportMode, SchemeImportRow, SchemeValidationWorker)
    raws = [{"Species": n, "Date": "01/06/2024", "Grid": "SP4537",
             **({"Qty": qty} if qty is not None else {})} for n in names]
    mapping = {"species_name": "Species", "date": "Date", "grid_ref": "Grid", "quantity": "Qty"}
    rows = [SchemeImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
    w = SchemeValidationWorker(rows=rows, import_mode=SchemeImportMode.GENERIC_CSV,
                               column_mapping=mapping, uksi_model=model, vc_db_path=None,
                               db_manager=None)
    out = []
    w.finished.connect(out.extend)
    w.run()
    return out


def _obs_rows(model, raws):
    from src.views.dialogs.observation_import_wizard.validation_worker import (
        ImportMode, ObservationImportRow, ObservationValidationWorker)
    mapping = {"species_name": "Species", "date": "Date", "recorder": "Recorder",
               "grid_ref": "Grid", "quantity": "Qty"}
    rows = [ObservationImportRow(row_number=i + 2, raw_data=r) for i, r in enumerate(raws)]
    w = ObservationValidationWorker(rows=rows, column_mapping=mapping,
                                    import_mode=ImportMode.PERSONAL_UPLOAD, uksi_model=model,
                                    vc_db_path=None, db_manager=None)
    out = []
    w.finished.connect(out.extend)
    w.run()
    return out


def _specimen_rows(model, names):
    from src.views.dialogs.specimen_import_wizard.validation_worker import ImportRow, ValidationWorker
    rows = [ImportRow(row_number=i + 2, raw_data={"Species": n, "Date": "01/06/2024",
                                                  "Grid": "SP4537"}) for i, n in enumerate(names)]
    w = ValidationWorker(rows, {"species_name": "Species", "date_collected": "Date",
                                "grid_ref": "Grid"}, model, vc_db_path=None)
    out = []
    w.finished.connect(out.extend)
    w.run()
    return out


def _obs(name="Rhagium mordax", date="01/06/2024", qty=""):
    return {"Species": name, "Date": date, "Recorder": "Heeney, W.J.", "Grid": "SP4537",
            "Qty": qty}


def test_all_three_wizards_take_a_close_spelling(model):
    for rows in (_scheme_rows(model, ["Rutpela maculta", "Rutpla maculata"]),
                 _specimen_rows(model, ["Rutpela maculta", "Rutpla maculata"]),
                 _obs_rows(model, [_obs("Rutpela maculta"), _obs("Rutpla maculata")])):
        close, loose = rows
        assert close.species_name == "Rutpela maculata" and close.species_tvk
        assert close.status.value == "warning", close.error_message
        assert any(w.startswith("Close spelling: 'Rutpela maculta'") for w in close.warnings)
        assert loose.status.value == "error" and "Species not found in UKSI" in loose.error_message


# ------------------------------------- decision 2 (groups), changed by F49: group words first

@pytest.fixture(scope="module")
def idx():
    from shared.species_search import get_index
    return get_index()


@pytest.mark.parametrize("text, group", [("longhorn", "All Cerambycidae (longhorn beetles)"),
                                         ("ladybird", "All Coccinellidae (ladybirds)"),
                                         ("beetle", "All Coleoptera (beetles)")])
def test_group_words_list_their_groups_first(idx, text, group):
    """F49 (12 Oct 2026, Wil): the typed text is a group's name -> its group comes FIRST,
    then the species; groups the word is only inside of stay after the species."""
    r = idx.search(text, limit=25)
    assert r[0]["is_group"] and r[0]["group_first"]
    assert r[0]["group_label"] == group + GROUP
    kinds = [x["is_group"] for x in r]
    n_first = sum(1 for x in r if x["group_first"])
    assert all(kinds[:n_first]) and not kinds[n_first]                  # groups, then species
    later = [i for i, x in enumerate(r) if x["is_group"] and not x["group_first"]]
    assert all(i > max(j for j, k in enumerate(kinds) if not k) for i in later)


def test_a_typed_species_is_never_pushed_down(idx):
    assert idx.search("Stag Beetle", limit=10)[0]["scientific_name"] == "Lucanus cervus"
    assert idx.search("Cerambycidae", limit=5)[0]["is_group"] is False   # typed by name


def test_filters_select_the_same_taxa():
    """The order changed, not what a filter box selects (species_filter reads the tiers)."""
    from shared.species_filter import choose_taxa
    assert [r["scientific_name"] for r in choose_taxa("beetle")] == ["Coleoptera"]
    assert [r["scientific_name"] for r in choose_taxa("ladybird")] == ["Coccinellidae"]
    assert "Cerambycidae" in {r["scientific_name"] for r in choose_taxa("longhorn")}


def test_filter_wizard_what_box_lists_group_last(qapp):
    from PySide6.QtWidgets import QLineEdit
    from src.views.components.filter_wizard.fuzzy import SpeciesCompleter
    items = {"Green Longhorn (Adela reaumurella)": "Adela reaumurella",
             "Rutpela maculata": "Rutpela maculata", "Rhagium mordax": "Rhagium mordax",
             "Stag Beetle (Lucanus cervus)": "Lucanus cervus"}
    box = QLineEdit()
    c = SpeciesCompleter(list(items), box, names=items)
    box.setCompleter(c)
    c.setCompletionPrefix("longhorn")
    m = c.completionModel()
    shown = [m.data(m.index(i, 0)) for i in range(m.rowCount())]
    assert shown == ["All Cerambycidae (longhorn beetles)" + GROUP,      # a group word: first
                     "Green Longhorn (Adela reaumurella)"]
    assert c.scientific_name(shown[0]) == "Cerambycidae"
    c.setCompletionPrefix("rhag mordx")                  # a species search: no group added
    assert [m.data(m.index(i, 0)) for i in range(m.rowCount())] == ["Rhagium mordax"]


def test_codex_and_examen_label_the_group(qapp):
    from Codex.species_tab import SpeciesTab
    from Examen.species_database_view import SpeciesDatabaseView
    from shared.species_list_delegate import HIT_ROLE, row_text
    tab = SpeciesTab()
    tab.search_input.setText("ladybird")
    tab._do_search()
    lst = tab.results_list
    texts = [row_text(lst.item(i).data(HIT_ROLE)) for i in range(lst.count())]
    assert texts[0] == "All Coccinellidae (ladybirds)" + GROUP              # F49: first
    assert any("Ladybird" in t for t in texts[1:])
    view = SpeciesDatabaseView.__new__(SpeciesDatabaseView)
    hits = SpeciesDatabaseView._search_uksi(view, "ladybird")
    assert hits[0][6] == "All Coccinellidae (ladybirds)" + GROUP and hits[1][6] == ""


# ---------------------------------------------------------------- temp database

def _schema_db(path):
    src = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(path)
    for t in ("observations", "recording_scheme", "specimens"):
        dst.execute(src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                                (t,)).fetchone()[0])
    dst.commit()
    src.close()
    return dst


@pytest.fixture
def temp_db(tmp_path, monkeypatch, qapp):
    if not HAVE_DATA:
        pytest.skip("needs the real schema from data/observatum.db")
    path = tmp_path / "observatum.db"
    _schema_db(path).close()
    from src.models.database import get_database
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(str(path))
    db.set_uksi_path(str(paths.UKSI_DB))
    monkeypatch.setattr(paths, "OBSERVATUM_DB", path)
    yield db, path
    db._main_db_path, db._uksi_db_path = old


# ---------------------------------------------------------------- decision 7: Quick Entry

def test_quick_entry_project_is_a_choice_of_existing_projects(temp_db):
    db, path = temp_db
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO observations (species_name, date, record_type, project_name, client) "
                 "VALUES ('Abax parallelus', '2024-06-01', 'Commercial', 'Hook Farm', 'BAM')")
    conn.commit()
    conn.close()
    import src.views.home.quick_entry as qe
    f = qe.QuickEntryForm()
    assert not f.project_combo.isEditable() and f.project_hint.isHidden()
    f.record_type_combo.setCurrentText("Commercial")
    assert not f.project_combo.isEditable() and not f.project_hint.isHidden()
    assert f.project_hint.text() == "New projects start in Data Entry"
    assert [f.project_combo.itemText(i) for i in range(f.project_combo.count())] == [
        "Choose a project...", "Hook Farm (BAM)"]
    f.record_type_combo.setCurrentText("Personal")
    assert f.project_hint.isHidden() and not f.project_combo.isEnabled()


# ---------------------------------------------------------------- decision 8: count of 0

def test_observation_import_count_of_zero_is_an_error(model):
    rows = _obs_rows(model, [_obs(qty="0"), _obs(qty="3"), _obs(qty="")])
    zero, three, blank = rows
    assert zero.status.value == "error" and "Count of 0 — fix the count" in zero.error_message
    assert (three.status.value, three.quantity) == ("valid", 3)
    assert (blank.status.value, blank.quantity) == ("valid", 1)


def test_count_of_zero_never_imported_even_with_everything(model):
    from src.views.dialogs.observation_import_wizard.wizard_validation_mixin import (
        WizardValidationMixin)
    zero, other = _obs_rows(model, [_obs(qty="0"), _obs(date="31/02/2024")])
    stub = type("W", (), {"_row_handling": lambda self: "everything"})()
    assert WizardValidationMixin._passes_row_handling(stub, other)        # an error row: in
    assert not WizardValidationMixin._passes_row_handling(stub, zero)     # count of 0: never


def test_scheme_import_count_of_zero_is_presence(model):
    (row,) = _scheme_rows(model, ["Rhagium mordax"], qty="0")
    assert row.quantity == 0                                # stored as received
    assert not any("Count of 0" in w for w in row.warnings)
    assert "Count of 0" not in (row.error_message or "")


def test_data_entry_count_of_zero_is_held_and_named():
    from DataEntry.commit_service import _eligibility, is_zero_qty, precommit_issues, read_qty
    assert read_qty("0") is None and is_zero_qty("0") and is_zero_qty("0.0")
    assert not is_zero_qty("c.20") and not is_zero_qty("") and not is_zero_qty("2")
    base = {"species_name": "Rhagium mordax", "date": "01/06/2024", "site_name": "x",
            "grid_ref": "SP4537", "vc_number": "23", "recorder": "W", "species_tvk": "T"}
    rows = [dict(base, quantity="0"), dict(base, quantity="c.20", sex="m"), dict(base, quantity="2", sex="f")]
    assert [_eligibility(r) for r in rows] == ["bad_qty", "bad_qty", None]
    found = precommit_issues(rows)
    assert found["count of 0"] == [1] and found["unreadable No."] == [2]


def test_quick_entry_quantity_cannot_be_zero(qapp):
    from src.views.home.quantity_spinner import QuantitySpinner
    s = QuantitySpinner()
    s.setValue(0)
    assert s.value() >= 1


# ---------------------------------------------------------------- decision 9: vague dates

def test_observation_import_accepts_vague_dates_with_a_warning(model):
    rows = _obs_rows(model, [_obs(date="2021"), _obs(date="June 2021"),
                             _obs(date="1/5/2024 to 15/5/2024"), _obs(date="01/06/2024")])
    got = [(r.status.value, r.date, r.date_type, r.warnings) for r in rows]
    assert got[0] == ("warning", "2021-01-01", "Y", ["vague date: year only"])
    assert got[1] == ("warning", "2021-06-01", "O", ["vague date: month only"])
    assert got[2] == ("warning", "2024-05-01", "DD", ["vague date: date range"])
    assert got[3] == ("valid", "2024-06-01", "D", [])
    assert "stored as 2021-01-01 with date type Y" in rows[0].import_notes


def test_month_charts_skip_vague_observation_dates(temp_db):
    db, path = temp_db
    conn = sqlite3.connect(path)
    for d, t in (("2021-06-14", "D"), ("2021-01-01", "Y"), ("2021-06-01", "O"),
                 ("2024-05-01", "DD")):
        conn.execute("INSERT INTO observations (species_name, species_tvk, date, date_type, "
                     "record_type) VALUES ('Rhagium mordax', 'NBNSYS0000010506', ?, ?, 'Personal')",
                     (d, t))
    conn.commit()
    conn.close()
    from src.repositories.observation_repository import ObservationRepository
    monthly = ObservationRepository(db).get_monthly_activity()
    assert sum(monthly) == 1 and monthly[5] == 1
    from src.views.stats.month_records_dialog import month_records
    got = month_records(lambda sql, p: db.execute_main(sql, p),
                        lambda table, name: ("species_name = ?", [name]), "Rhagium mordax", 6)
    assert [r["date"] for r in got] == ["2021-06-14"]
    from src.services.observation_stats_service import ObservationStatsService
    svc = ObservationStatsService()
    old = svc._db
    try:
        svc.initialize(db)
        svc.refresh()
        assert sum(svc.get("monthly_counts")) == 1
        assert svc.get("monthly_counts")[5] == 1
    finally:
        svc.initialize(old)
        svc.invalidate()
    # totals still count every record
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 4
    conn.close()


# ---------------------------------------------------------------- L23, L24

def test_picked_species_says_what_the_file_had():
    from shared.species_lookup_entries import apply_confirmed
    from src.views.dialogs.scheme_import_wizard.validation_worker import RowStatus, SchemeImportRow
    row = SchemeImportRow(row_number=2, raw_data={}, species_name="Rutpela maculta",
                          status=RowStatus.ERROR,
                          error_message="Species not found in UKSI: Rutpela maculta")
    apply_confirmed(row, {"scientific_name": "Rutpela maculata", "tvk": "T"}, "Rutpela maculta",
                    "picked by you")
    assert row.status == RowStatus.WARNING
    assert row.warnings == ["File had 'Rutpela maculta'; picked by you as Rutpela maculata"]
    assert row.import_notes == "Imported as 'Rutpela maculta'; picked by you as 'Rutpela maculata'"


def test_specimen_status_column_shows_ticks(qapp):
    from src.views.dialogs.specimen_import_wizard.validation_table_model import ValidationTableModel
    from src.views.dialogs.specimen_import_wizard.validation_worker import ImportRow, RowStatus
    m = ValidationTableModel()
    m.set_data([ImportRow(row_number=i, raw_data={}, status=s)
                for i, s in enumerate((RowStatus.VALID, RowStatus.WARNING, RowStatus.ERROR))])
    assert [m.data(m.index(i, 0)) for i in range(3)] == ["✓", "⚠", "✗"]
