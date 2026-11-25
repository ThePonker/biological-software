"""Make specimens (25 Nov 2026): specimens made straight from staged Data Entry rows or committed
records; the Keep tick; the commit sync (rule 5); the review screen. Small purpose-made
databases only; the live data is never opened."""
import os
import sqlite3
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from DataEntry import commit_service as cs  # noqa: E402
from DataEntry import staging_repo as repo  # noqa: E402
from shared import make_specimens as ms  # noqa: E402
from shared import specimen_staging as ss  # noqa: E402

SPECIMENS = """CREATE TABLE specimens (id INTEGER PRIMARY KEY AUTOINCREMENT, specimen_code TEXT UNIQUE,
 species_name TEXT NOT NULL, species_tvk TEXT, common_name TEXT, order_name TEXT, family TEXT,
 subfamily TEXT, date_collected TEXT NOT NULL, grid_ref TEXT, vice_county TEXT, vc_number INTEGER,
 site_name TEXT, site_name_local TEXT, collector TEXT, determiner TEXT, sex TEXT, preparation_type TEXT,
 storage_location TEXT, drawer_number TEXT, condition TEXT, label_data TEXT, notes TEXT, import_notes TEXT,
 observation_id INTEGER, created_at TEXT, updated_at TEXT, superfamily TEXT, taxonomic_sort_key INTEGER,
 taxon_group TEXT, no_field_record_checked TEXT)"""
OBSERVATIONS = """CREATE TABLE observations (id INTEGER PRIMARY KEY AUTOINCREMENT, species_name TEXT, species_tvk TEXT,
 common_name TEXT, order_name TEXT, family TEXT, subfamily TEXT, superfamily TEXT, taxonomic_sort_key INTEGER,
 taxon_group TEXT, date TEXT, date_type TEXT, grid_ref TEXT, vice_county TEXT, vc_number INTEGER, site_name TEXT,
 recorder TEXT, determiner TEXT, sex TEXT, quantity INTEGER)"""
T1 = {"taxon_group": "Beetles", "kingdom": "Animalia", "taxon_rank": "Species", "superfamily": "Caraboidea",
      "subfamily": "Harpalinae", "taxonomic_sort_key": 3001, "order_name": "Coleoptera", "family": "Carabidae"}
T2 = {**T1, "subfamily": "Amarinae", "taxonomic_sort_key": 3002}
TAX = {"TVK1": T1, "TVK2": T2}


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "observatum.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    ss.ensure_schema(conn)                      # the live database has the table
    conn.execute(SPECIMENS)
    conn.execute(OBSERVATIONS)
    conn.commit()
    return types.SimpleNamespace(conn=conn, path=str(path))


def _job(db, mode="Commercial", name="Survey"):
    return repo.create_job(db.conn, name, mode, "Client", "Project" if mode == "Commercial" else None)


def _row(db, jid, **kw):
    return repo.insert_row(db.conn, jid, {
        "species_name": "Amara aenea", "species_tvk": "TVK1", "date": "2026-06-05", "quantity": 1,
        "grid_ref": "SP1234", "site_name": "Wood", "sex": "Male", "determiner": "Falk, S.J.",
        "recorder": "Heeney, W.J.", "order_name": "Coleoptera", "family": "Carabidae", **kw})


def _n(db, table, where="1"):
    return db.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]


def _make(db, jid, rids, n=None, backup=lambda p: True, **choice):
    job = repo.get_job(db.conn, jid)
    cands = ms.load_rows(db.conn, rids, job, taxonomy=TAX)
    ch = {(c["kind"], c["id"]): {**({"n": n} if n is not None else {}), **choice} for c in cands}
    plan = ms.make_plan(cands, ch)
    return cands, ms.apply(db.path, plan, linked=ms.is_linked_job(job), backup=backup)


class Model:
    """Stands in for ObservationModel.create: writes the record into this database."""
    def __init__(self, conn):
        self.conn = conn

    def create(self, o, extra=None):
        kw = {**o.kw, **(extra or {})}
        have = {r[1] for r in self.conn.execute("PRAGMA table_info(observations)")}
        kw = {k: v for k, v in kw.items() if k in have}
        cur = self.conn.execute(f"INSERT INTO observations ({','.join(kw)}) VALUES ({','.join('?' * len(kw))})",
                                list(kw.values()))
        self.conn.commit()
        return cur.lastrowid


class Obs:
    def __init__(self, **kw):
        self.kw = kw


def _commit(db, jid):
    return cs.commit_job(None, Model(db.conn), db.conn, repo.get_job(db.conn, jid),
                         observation_cls=Obs, taxonomy=TAX)


# ---------------------------------------------------------------- numbers
def test_one_per_row_by_default_and_the_number_is_capped_at_the_rows_no(db):
    jid = _job(db)
    a, b, c = _row(db, jid, quantity=3), _row(db, jid, quantity=None), _row(db, jid, quantity=1)
    cands = ms.load_rows(db.conn, [a, b, c], repo.get_job(db.conn, jid), taxonomy=TAX)
    assert [(x["max"], ms.default_choice(x)["n"]) for x in cands] == [(3, 1), (1, 1), (1, 1)]
    plan = ms.make_plan(cands, {})
    assert [len(p["specimens"]) for p in plan] == [1, 1, 1]
    assert [len(p["specimens"]) for p in ms.make_plan(cands, {("row", a): {"n": 3}})][0] == 3
    for key, n in ((("row", a), 4), (("row", b), 2)):
        with pytest.raises(ValueError):
            ms.make_plan(cands, {key: {"n": n}})
    assert _n(db, "specimens") == 0                       # planning writes nothing


def test_prep_defaults_from_the_order_and_the_sex_comes_from_the_row(db):
    jid = _job(db)
    cands, res = _make(db, jid, [_row(db, jid, sex="Female")])
    s = db.conn.execute("SELECT * FROM specimens WHERE id=?", (res["ids"][0],)).fetchone()
    assert s["preparation_type"] == "Carded" and s["sex"] == "Female"       # Coleoptera -> Carded
    assert (s["storage_location"], s["drawer_number"]) == ("", "")          # may stay blank
    assert (s["species_tvk"], s["taxonomic_sort_key"], s["superfamily"]) == ("TVK1", 3001, "Caraboidea")
    assert (s["collector"], s["determiner"], s["date_collected"]) == ("Heeney, W.J.", "Falk, S.J.", "2026-06-05")


# ---------------------------------------------------------------- staged rows, commit, rule 5
def test_staged_row_specimen_is_linked_at_commit_and_takes_the_rows_final_fields(db):
    jid = _job(db)
    rid = _row(db, jid)
    _, res = _make(db, jid, [rid], preparation_type="Pinned", storage_location="Cabinet",
                   drawer_number="3", notes="mine", condition="Good")
    sid = res["ids"][0]
    assert db.conn.execute("SELECT origin FROM staging_specimens WHERE staging_id=? AND specimen_id=?",
                           (rid, sid)).fetchone()[0] == ss.ORIGIN_MADE
    assert db.conn.execute("SELECT observation_id FROM specimens WHERE id=?", (sid,)).fetchone()[0] is None
    repo.update_row(db.conn, rid, {"species_name": "Amara bifrons", "species_tvk": "TVK2",
                                   "grid_ref": "SP5678", "site_name": "New wood", "sex": "Female",
                                   "determiner": "Falk", "date": "2026-07-01"})
    s = _commit(db, jid)
    assert s["committed"] == 1 and not s["photo_problems"]
    got = db.conn.execute("SELECT * FROM specimens WHERE id=?", (sid,)).fetchone()
    assert got["observation_id"] == 1
    assert (got["species_name"], got["species_tvk"], got["subfamily"], got["taxonomic_sort_key"]) == \
        ("Amara bifrons", "TVK2", "Amarinae", 3002)
    assert (got["grid_ref"], got["site_name"], got["sex"], got["determiner"], got["date_collected"]) == \
        ("SP5678", "New wood", "Female", "Falk", "2026-07-01")
    assert (got["preparation_type"], got["storage_location"], got["drawer_number"], got["notes"],
            got["condition"]) == ("Pinned", "Cabinet", "3", "mine", "Good")      # never touched
    assert _n(db, "staging_specimens") == 0


def test_a_reverse_flow_specimen_is_linked_but_not_synced(db):
    jid = _job(db)
    db.conn.execute("INSERT INTO specimens (id, species_name, species_tvk, date_collected, grid_ref, site_name) "
                    "VALUES (7, 'Amara aenea', 'TVK1', '2026-06-05', 'SP1234', 'Old site')")
    rid = _row(db, jid, site_name="Typed differently", grid_ref="SP9999")
    ss.add(db.conn, rid, [7])                                   # as scripts/stage_records_from_specimens does
    db.conn.commit()
    assert db.conn.execute("SELECT origin FROM staging_specimens").fetchone()[0] is None
    _commit(db, jid)
    got = db.conn.execute("SELECT observation_id, site_name, grid_ref FROM specimens WHERE id=7").fetchone()
    assert tuple(got) == (1, "Old site", "SP1234")              # linked, nothing else changed


def test_a_deleted_row_lets_its_specimen_stay_with_no_field_record(db):
    jid = _job(db)
    rid = _row(db, jid)
    _, res = _make(db, jid, [rid])
    repo.delete_row(db.conn, rid)
    assert _n(db, "specimens", f"id={res['ids'][0]} AND observation_id IS NULL") == 1
    assert _n(db, "staging_specimens") == 0


# ---------------------------------------------------------------- committed records
def test_committed_record_specimen_is_linked_and_a_vague_date_is_said(db):
    db.conn.execute("INSERT INTO observations (id, species_name, species_tvk, order_name, date, date_type, "
                    "grid_ref, site_name, recorder, sex, quantity, taxonomic_sort_key, superfamily) VALUES "
                    "(5, 'Amara aenea', 'TVK1', 'Coleoptera', '2026-06-01', 'O', 'SP1234', 'Wood', 'WH', "
                    "'Male', 2, 3001, 'Caraboidea')")
    db.conn.commit()
    cands = ms.load_records(db.conn, [5])
    assert cands[0]["max"] == 2 and "first day" in cands[0]["date_note"] and not cands[0]["refused"]
    res = ms.apply(db.path, ms.make_plan(cands, {("record", 5): {"n": 2}}), backup=lambda p: True)
    assert _n(db, "specimens", "observation_id=5") == 2 and len(res["ids"]) == 2
    assert _n(db, "staging_specimens") == 0
    assert db.conn.execute("SELECT date_collected, collector FROM specimens").fetchone()[:] == ("2026-06-01", "WH")


# ---------------------------------------------------------------- flags and refusals
def test_rows_and_records_that_already_have_specimens_start_at_zero(db):
    jid = _job(db)
    a, b = _row(db, jid), _row(db, jid)
    _make(db, jid, [a])
    cands = ms.load_rows(db.conn, [a, b], repo.get_job(db.conn, jid), taxonomy=TAX)
    assert [c["existing"] for c in cands] == [1, 0]
    assert [ms.default_choice(c)["n"] for c in cands] == [0, 1]
    db.conn.execute("INSERT INTO observations (id, species_name, species_tvk, date, taxonomic_sort_key) "
                    "VALUES (9, 'Amara aenea', 'TVK1', '2026-06-05', 3001)")
    db.conn.execute("INSERT INTO specimens (species_name, date_collected, observation_id) VALUES ('x','2026-06-05',9)")
    rec = ms.load_records(db.conn, [9])[0]
    assert rec["existing"] == 1 and ms.default_choice(rec)["n"] == 0


def test_no_tvk_to_check_and_unplaceable_rows_are_listed_but_cannot_be_made(db):
    jid = _job(db)
    no_tvk = _row(db, jid, species_tvk=None)
    flagged = _row(db, jid, check_flag=1)
    no_sort = _row(db, jid, species_tvk="TVK9")
    ok = _row(db, jid)
    cands = {c["id"]: c for c in ms.load_rows(db.conn, [no_tvk, flagged, no_sort, ok],
                                              repo.get_job(db.conn, jid), taxonomy=TAX)}
    assert "no TVK" in cands[no_tvk]["refused"] and "To check" in cands[flagged]["refused"]
    assert "sort position" in cands[no_sort]["refused"] and cands[ok]["refused"] is None
    assert [ms.default_choice(cands[i])["n"] for i in (no_tvk, flagged, no_sort, ok)] == [0, 0, 0, 1]
    with pytest.raises(ValueError):
        ms.make_plan(list(cands.values()), {("row", flagged): {"n": 1}})


# ---------------------------------------------------------------- the write
def test_away_mode_and_a_failed_backup_write_nothing(db, monkeypatch):
    jid = _job(db)
    rid = _row(db, jid)
    cands = ms.load_rows(db.conn, [rid], repo.get_job(db.conn, jid), taxonomy=TAX)
    plan = ms.make_plan(cands, {})
    with pytest.raises(ms.MakeRefused, match="backup failed"):
        ms.apply(db.path, plan, backup=lambda p: False)
    with pytest.raises(ms.MakeRefused, match="unavailable"):
        ms.apply(db.path, plan, backup=lambda p: 1 / 0)
    import shared.away_mode as am
    monkeypatch.setattr(am, "away_active", lambda: True)
    called = []
    with pytest.raises(ms.MakeRefused, match="away mode"):
        ms.apply(db.path, plan, backup=lambda p: called.append(p) or True)
    assert _n(db, "specimens") == 0 and _n(db, "staging_specimens") == 0 and called == []


def test_one_transaction_a_vanished_row_rolls_everything_back(db):
    jid = _job(db)
    a, b = _row(db, jid), _row(db, jid)
    job = repo.get_job(db.conn, jid)
    plan = ms.make_plan(ms.load_rows(db.conn, [a, b], job, taxonomy=TAX), {})
    repo.delete_row(db.conn, b)                       # gone between the review and the write
    with pytest.raises(ms.MakeRefused, match="no longer there"):
        ms.apply(db.path, plan, backup=lambda p: True)
    assert _n(db, "specimens") == 0 and _n(db, "staging_specimens") == 0


def test_personal_job_links_like_any_other(db, monkeypatch, qapp):
    """Personal jobs commit too (14 Oct 2026): their specimens are linked at commit like any."""
    jid = _job(db, mode="Personal", name="Personal")
    rid = _row(db, jid)
    job = repo.get_job(db.conn, jid)
    assert ms.is_linked_job(job) and ms.is_linked_job({"mode": "Commercial"})
    _, res = _make(db, jid, [rid])
    assert _n(db, "specimens", "observation_id IS NULL") == 1 and _n(db, "staging_specimens") == 1


def test_sex_is_stored_as_the_collection_stores_it():
    from shared.specimen_vocab import specimen_sex
    assert specimen_sex("male") == "Male" and specimen_sex("Female") == "Female"
    assert specimen_sex("Not recorded") is None and specimen_sex("mixed") is None
    assert specimen_sex(None) is None


# ---------------------------------------------------------------- the review screen
@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_review_screen_lists_flags_and_makes(db, qapp):
    from shared.make_specimens_dialog import (C_COND, C_DRAWER, C_MAKE, C_NOTE, C_PREP, C_STORE,
                                              MakeSpecimensDialog)
    jid = _job(db)
    ok, flagged = _row(db, jid, quantity=2), _row(db, jid, check_flag=1)
    job = repo.get_job(db.conn, jid)
    dlg = MakeSpecimensDialog(ms.load_rows(db.conn, [ok, flagged], job, taxonomy=TAX), db.path,
                              backup=lambda p: True)
    t = dlg.table
    assert t.cellWidget(0, C_MAKE).value() == 1 and t.cellWidget(0, C_MAKE).maximum() == 2
    assert t.cellWidget(1, C_MAKE).maximum() == 0 and "CANNOT MAKE" in t.item(1, C_NOTE).text()
    assert t.cellWidget(0, C_PREP).currentText() == "Carded"
    assert t.cellWidget(0, C_COND).currentText() == "Good"              # condition starts as Good
    # picking from a Set-for-all dropdown applies at once (no Set button)
    dlg.all_store.setCurrentText("Cabinet")
    dlg.all_store.activated.emit(dlg.all_store.currentIndex())
    assert t.cellWidget(0, C_STORE).currentText() == "Cabinet"
    dlg.all_cond.setCurrentText("Damaged")
    dlg.all_cond.activated.emit(dlg.all_cond.currentIndex())
    assert t.cellWidget(0, C_COND).currentText() == "Damaged"
    dlg.all_cond.setCurrentText("Good")
    dlg.all_cond.activated.emit(dlg.all_cond.currentIndex())
    # the drawer applies only when typed in: tabbing past an empty box blanks nothing
    t.cellWidget(0, C_DRAWER).setText("D7")
    dlg.all_drawer.editingFinished.emit()
    assert t.cellWidget(0, C_DRAWER).text() == "D7"
    dlg.all_drawer.setText("D9")
    dlg.all_drawer.setModified(True)
    dlg.all_drawer.editingFinished.emit()
    assert t.cellWidget(0, C_DRAWER).text() == "D9"
    shown = []
    dlg._preview = lambda text: shown.append(text) or True
    dlg._info = lambda text: shown.append(text)
    dlg._warn = lambda text: shown.append(text)
    res = dlg._make()
    assert len(res["ids"]) == 1 and "1 specimen(s) from 1 row(s)" in shown[0]
    assert db.conn.execute("SELECT storage_location FROM specimens").fetchone()[0] == "Cabinet"


# ---------------------------------------------------------------- Data Entry: Keep tick and button
def test_keep_column_comes_from_the_backed_up_script_and_the_tick_persists(db, qapp):
    """An older database gets keep_flag from scripts/add_staging_check_columns.py (backup first),
    never silently when Data Entry opens (review 25 Nov, CLAUDE.md rule 3); a new table has it."""
    import importlib.util
    old = sqlite3.connect(":memory:")
    old.execute("CREATE TABLE entry_staging (id INTEGER PRIMARY KEY, job_id INTEGER, species_name TEXT)")
    repo.ensure_schema(old)
    assert not repo.has_keep_column(old)                         # opening never alters an old table
    spec = importlib.util.spec_from_file_location(
        "add_staging_check_columns", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                  "scripts", "add_staging_check_columns.py"))
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert ("keep_flag", "INTEGER") in script.COLUMNS
    assert ("keep_flag", "INTEGER") in script.missing_columns(old)
    assert repo.has_keep_column(db.conn)                         # a new table is made with it
    from DataEntry.grid_columns import _CSV_COLUMNS, COLIDX
    assert "keep_flag" in COLIDX and "keep_flag" not in [c[0] for c in _CSV_COLUMNS]
    from DataEntry.staging_model import StagingTableModel
    jid = _job(db)
    a, b = _row(db, jid), _row(db, jid)
    m = StagingTableModel(db.conn, jid)
    m.toggle_keep(1)
    assert m.kept_ids() == [b] and m.is_kept(1) and not m.is_kept(0)
    assert db.conn.execute("SELECT keep_flag FROM entry_staging WHERE id=?", (b,)).fetchone()[0] == 1
    assert StagingTableModel(db.conn, jid).kept_ids() == [b]     # persisted
    m.clear_keep([b, a])
    assert m.kept_ids() == []
    assert cs.is_blank_row({"species_name": None, "keep_flag": 0, "check_flag": 0})      # an unset tick is blank
    assert not cs.is_blank_row({"species_name": None, "keep_flag": 1})


def test_old_staging_specimens_table_gains_origin_and_old_callers_still_work(db):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE staging_specimens (staging_id INTEGER NOT NULL, specimen_id INTEGER NOT NULL, "
              "PRIMARY KEY (staging_id, specimen_id))")
    c.execute("INSERT INTO staging_specimens VALUES (1, 2)")
    ss.add(c, 3, [4])                                            # the reverse flow's call
    assert ss.for_row(c, 1) == [2] and ss.for_row(c, 3) == [4] and ss.made_from_row(c, 3) == []
    ss.add(c, 5, [6], ss.ORIGIN_MADE)
    assert ss.made_from_row(c, 5) == [6] and ss.staged(c) == {2: 1, 4: 3, 6: 5}


def test_grid_button_makes_specimens_from_keep_rows_and_clears_the_ticks(tmp_path, monkeypatch, qapp):
    from PySide6.QtWidgets import QMessageBox
    from DataEntry.data_entry_widget import DataEntryWidget
    from DataEntry.entry_grid import EntryGridPage
    from shared.make_specimens_dialog import MakeSpecimensDialog
    path = tmp_path / "observatum.db"
    c = sqlite3.connect(path)
    c.execute(SPECIMENS)
    c.execute(OBSERVATIONS)
    c.commit()
    c.close()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    w = DataEntryWidget(str(path), embedded=True, allow_commit=False)
    jid = repo.create_job(w._conn, "Survey", "Commercial", "C", "P")
    r1 = repo.insert_row(w._conn, jid, {"species_name": "Amara aenea", "species_tvk": "TVK1", "date": "2026-06-05",
                                        "order_name": "Coleoptera"})
    r2 = repo.insert_row(w._conn, jid, {"species_name": "Amara bifrons", "species_tvk": "TVK2", "date": "2026-06-05"})
    w._open_job(jid)
    g = w._job_host.findChildren(EntryGridPage)[-1]
    assert g._make_btn.text() == "Make specimens…"
    g._model.toggle_keep(0)
    g._check_changed()
    assert g._make_btn.text() == "Make specimens… (1)"
    monkeypatch.setattr(ms, "_default_backup", lambda p: True)
    real_load = ms.load_rows
    monkeypatch.setattr(ms, "load_rows", lambda *a, **k: real_load(*a, taxonomy=TAX, **k))
    seen = []

    def run(self):
        seen.append([x["id"] for x in self._cands])
        self._preview = lambda t: True
        self._info = lambda t: None
        return self._make() and 1
    monkeypatch.setattr(MakeSpecimensDialog, "exec", run)
    g._make_btn.click()
    assert seen == [[r1]] and r2 not in seen[0]
    assert g._model.kept_ids() == [] and g._make_btn.text() == "Make specimens…"
    chk = sqlite3.connect(path)
    assert chk.execute("SELECT COUNT(*) FROM staging_specimens WHERE staging_id=?", (r1,)).fetchone()[0] == 1
    chk.close()


def test_a_test_copy_job_is_refused(db, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from DataEntry import grid_specimens
    said = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: said.append(a[2])))
    jid = _job(db, name="TEST copy of Survey")
    rid = _row(db, jid, keep_flag=1)
    page = types.SimpleNamespace(_conn=db.conn, _job_id=jid, _job=repo.get_job(db.conn, jid),
                                 _model=types.SimpleNamespace(kept_ids=lambda: [rid], has_keep_column=lambda: True))
    assert grid_specimens.open_for_grid(page) is None
    assert said and "test copy" in said[0] and _n(db, "specimens") == 0


# ---------------------------------------------------------------- Observation Data
def test_observation_data_button_and_action(db, monkeypatch, qapp):
    from PySide6.QtWidgets import QMessageBox
    from shared.make_specimens_dialog import MakeSpecimensDialog
    from src.views.observations import observation_make_specimens as oms
    from src.views.observations.observation_toolbar import ObservationToolbar
    tb = ObservationToolbar()
    assert not tb.make_specimens_btn.isEnabled()
    tb.set_selected_count(2)
    assert tb.make_specimens_btn.isEnabled()
    db.conn.execute("INSERT INTO observations (id, species_name, species_tvk, date, taxonomic_sort_key, "
                    "order_name) VALUES (4, 'Amara aenea', 'TVK1', '2026-06-05', 3001, 'Coleoptera')")
    db.conn.commit()
    from PySide6.QtWidgets import QWidget

    class Tab(QWidget):                       # the parts of ObservationTab that open_for_tab uses
        e = 0
        table_model = types.SimpleNamespace(get_checked_observations=lambda: [{"id": 4}])
        records_changed = types.SimpleNamespace(emit=lambda: setattr(Tab, "e", Tab.e + 1))
    tab = Tab()
    monkeypatch.setattr("src.models.database.get_database",
                        lambda: types.SimpleNamespace(main_db_path=db.path))
    monkeypatch.setattr(ms, "_default_backup", lambda p: True)

    def run(self):
        self._preview, self._info = (lambda t: True), (lambda t: None)
        return self._make() and 1
    monkeypatch.setattr(MakeSpecimensDialog, "exec", run)
    assert oms.open_for_tab(tab).result_info is not None
    assert _n(db, "specimens", "observation_id=4") == 1 and tab.e == 1
    said = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: said.append(a[2])))
    Tab.table_model = types.SimpleNamespace(get_checked_observations=lambda: [])
    assert oms.open_for_tab(tab) is None and said


# ---------------------------------------------------------------- the sandbox
def _live(tmp_path):
    src = tmp_path / "live" / "data"
    src.mkdir(parents=True)
    for name, n in (("observatum.db", 3), ("uksi.db", 5)):
        c = sqlite3.connect(src / name)
        c.execute("CREATE TABLE t (x)")
        c.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(n)])
        c.commit()
        c.close()
    (src / "saved_filters.json").write_text("{}")
    return src


def _sizes(folder):
    return {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.iterdir()}


def test_make_sandbox_dry_run_writes_nothing_and_apply_copies_through_backup(tmp_path, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_sandbox", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "scripts", "make_sandbox.py"))
    sb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sb)
    src, dest = _live(tmp_path), tmp_path / "sandbox"
    before = _sizes(src)
    assert sb.main(["--source", str(src), "--dest", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "observatum.db" in out and "READ ONLY" in out and not dest.exists()
    assert sb.main(["--source", str(src), "--dest", str(dest), "--apply"]) == 0
    # the databases, plus the plain extras present (saved filters); photos never copied
    assert sorted(p.name for p in (dest / "data").iterdir()) == ["observatum.db", "saved_filters.json", "uksi.db"]
    assert (dest / "Media" / "Photos" / "Life").is_dir() and not any((dest / "Media").rglob("*.*"))
    assert (dest / "backups").is_dir() and not list((dest / "backups").iterdir())
    chk = sqlite3.connect(dest / "data" / "uksi.db")
    try:
        assert chk.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 5
    finally:
        chk.close()                      # Windows will not move a folder holding an open database
    assert _sizes(src) == before                                          # live data untouched
    assert sb.main(["--source", str(src), "--dest", str(dest), "--apply"]) == 1      # never overwrites
    assert "already holds a sandbox" in capsys.readouterr().out
    assert sb.main(["--source", str(src), "--dest", str(dest), "--apply", "--refresh"]) == 0
    olds = [p for p in dest.iterdir() if p.name.startswith("_old_")]
    assert len(olds) == 1 and (olds[0] / "observatum.db").is_file()       # moved aside, not deleted
    assert sb.main(["--source", str(src), "--dest", str(src / "inside")]) == 1       # not inside live data
    text = open(spec.origin).read()
    import inspect
    db_copy = inspect.getsource(sb.copy_database)          # databases: read-only + conn.backup, never shutil
    assert "shutil" not in db_copy and ".backup(" in db_copy and "mode=ro" in db_copy
    assert all(not n.endswith(".db") for n in sb.EXTRAS)   # shutil is only for the plain extras


def test_the_window_title_says_sandbox_only_for_a_root_that_is_not_the_code_folder(tmp_path, monkeypatch):
    import subprocess
    import sys
    from shared import sandbox
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    box = tmp_path / "sb"
    (box / "data").mkdir(parents=True)
    env = {**os.environ, "BIOSOFT_ROOT": str(box), "BIOSOFT_SANDBOX": "1", "PYTHONPATH": os.pathsep.join([root, os.path.join(root, "Observatum")])}
    out = subprocess.run([sys.executable, "-c", "import paths; from shared import sandbox as s; "
                          "print(paths.DATA_DIR); print(s.window_title('Observatum V2'))"],
                         env=env, capture_output=True, text=True, cwd=str(tmp_path)).stdout.splitlines()
    assert out[0] == str(box / "data") and "SANDBOX" in out[1]            # DATA_DIR points into the sandbox
    monkeypatch.delenv("BIOSOFT_ROOT", raising=False)      # not set at all on Wil's PC
    assert sandbox.sandbox_root() is None and sandbox.window_title("Observatum V2") == "Observatum V2"
    monkeypatch.setenv("BIOSOFT_ROOT", str(box))           # a test root without the marker: not a sandbox
    monkeypatch.delenv("BIOSOFT_SANDBOX", raising=False)
    assert sandbox.sandbox_root() is None and sandbox.sandbox_capture_folder() is None


def test_main_window_title_goes_through_window_title():
    import inspect
    from src.views import main_window as mw
    assert 'window_title("Observatum V2")' in inspect.getsource(mw.MainWindow.__init__)


def test_commit_says_when_a_kept_row_had_no_specimens_made(db):
    jid = _job(db)
    kept = _row(db, jid, keep_flag=1)
    made = _row(db, jid, keep_flag=1, species_name="Amara bifrons", species_tvk="TVK2")
    _make(db, jid, [made])
    s = _commit(db, jid)
    assert s["committed"] == 2
    notes = [p for p in s["photo_problems"] if "ticked Keep" in p]
    assert len(notes) == 1 and "Amara aenea" in notes[0]


def test_making_again_is_capped_by_what_is_left_of_the_no(db):
    jid = _job(db)
    rid = _row(db, jid, quantity=3)
    _make(db, jid, [rid], n=2)
    job = repo.get_job(db.conn, jid)
    c = ms.load_rows(db.conn, [rid], job, taxonomy=TAX)[0]
    assert (c["existing"], c["max"], c["refused"]) == (2, 1, None)
    _make(db, jid, [rid], n=1)
    c = ms.load_rows(db.conn, [rid], job, taxonomy=TAX)[0]
    assert c["max"] == 0 and "as many as its No." in c["refused"]
    db.conn.execute("DELETE FROM specimens WHERE id = (SELECT MIN(id) FROM specimens)")   # one deleted
    db.conn.commit()
    c = ms.load_rows(db.conn, [rid], job, taxonomy=TAX)[0]
    assert (c["existing"], c["max"], c["refused"]) == (2, 1, None)        # a gone specimen is not counted


def test_commit_sync_never_blanks_a_specimen(db):
    jid = _job(db)
    rid = _row(db, jid)
    sid = _make(db, jid, [rid])[1]["ids"][0]
    repo.update_row(db.conn, rid, {"sex": "Not recorded", "determiner": "", "site_name": "Ridge"})
    _commit(db, jid)
    got = db.conn.execute("SELECT sex, determiner, site_name FROM specimens WHERE id=?", (sid,)).fetchone()
    assert tuple(got) == ("Male", "Falk, S.J.", "Ridge")


def test_a_sandbox_takes_photos_only_from_inside_itself(tmp_path, monkeypatch):
    import paths
    from shared import sandbox
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setenv("BIOSOFT_ROOT", str(tmp_path))
    monkeypatch.setenv("BIOSOFT_SANDBOX", "1")
    assert sandbox.sandbox_capture_folder() == tmp_path.resolve() / "capture"
    from DataEntry import photo_attach
    assert photo_attach.capture_folder() == tmp_path.resolve() / "capture"


def test_make_sandbox_refresh_says_so_when_the_sandbox_is_in_use(tmp_path, capsys, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "make_sandbox", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "scripts", "make_sandbox.py"))
    sb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sb)
    src, dest = _live(tmp_path), tmp_path / "sandbox"
    assert sb.main(["--source", str(src), "--dest", str(dest), "--apply"]) == 0

    def locked(a, b):
        raise PermissionError(13, "Access is denied")
    monkeypatch.setattr(sb.os, "rename", locked)
    assert sb.main(["--source", str(src), "--dest", str(dest), "--apply", "--refresh"]) == 1
    out = capsys.readouterr().out
    assert "Close the sandbox" in out and "Nothing has been changed" in out
    assert (dest / "data" / "observatum.db").is_file()                    # the sandbox is left as it was


def test_k_on_the_keep_cell_ticks_it(db, qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    from DataEntry.staging_model import StagingTableModel
    from DataEntry.entry_table_view import EntryTableView
    from DataEntry.grid_columns import COLIDX
    jid = _job(db)
    rid = _row(db, jid)
    m = StagingTableModel(db.conn, jid)
    v = EntryTableView()
    v.setModel(m)
    v.setCurrentIndex(m.index(0, COLIDX["keep_flag"]))
    for _ in range(2):                                   # K twice: still ticked (K never un-ticks)
        v.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_K, Qt.KeyboardModifier.NoModifier, "k"))
        assert m.kept_ids() == [rid]
    m.setData(m.index(0, COLIDX["keep_flag"]), "", Qt.ItemDataRole.EditRole)
    m.setData(m.index(0, COLIDX["keep_flag"]), "k", Qt.ItemDataRole.EditRole)   # typed "k" + Enter
    assert m.kept_ids() == [rid]


def test_the_data_entry_banner_says_sandbox_in_a_sandbox():
    import inspect
    from DataEntry import data_entry_widget as dew
    src = inspect.getsource(dew.DataEntryWidget._safety_banner)
    assert src.index("SANDBOX") < src.index("LIVE \\u2014") and "sandbox_root()" in src


def test_the_preview_shows_recorder_determiner_and_curation(db):
    jid = _job(db)
    rid = _row(db, jid, determiner="Falk, S.J.")
    job = repo.get_job(db.conn, jid)
    cands = ms.load_rows(db.conn, [rid], job, taxonomy=TAX)
    text = ms.describe(ms.make_plan(cands, {("row", rid): {"storage_location": "Cabinet"}}))
    assert "det. Falk, S.J." in text and "rec. " in text and "Good" in text and "Cabinet" in text


def test_the_keep_cell_shows_made_n_after_making(db, qapp):
    from PySide6.QtCore import Qt
    from DataEntry.staging_model import StagingTableModel
    from DataEntry.grid_columns import COLIDX
    jid = _job(db)
    rid, other = _row(db, jid, quantity=3, keep_flag=1), _row(db, jid)
    m = StagingTableModel(db.conn, jid)
    keep = lambda r, role=Qt.ItemDataRole.DisplayRole: m.data(m.index(r, COLIDX["keep_flag"]), role)  # noqa: E731
    assert keep(0) == "keep" and keep(1) is None
    _make(db, jid, [rid], n=2)
    m.clear_keep([rid])
    m.refresh_made_counts()
    assert keep(0) == "made 2" and "2 specimen(s) already made" in keep(0, Qt.ItemDataRole.ToolTipRole)
    assert keep(1) is None
    m.toggle_keep(0)
    assert keep(0) == "keep"                                   # ticked again: shows the tick
    db.conn.execute("DELETE FROM specimens WHERE id = (SELECT MIN(id) FROM specimens)")
    db.conn.commit()
    m.toggle_keep(0)
    m.refresh_made_counts()
    assert keep(0) == "made 1"                                 # a deleted specimen is not counted


def test_sorting_the_keep_column_puts_made_rows_first(db, qapp):
    from DataEntry.staging_model import StagingTableModel
    from DataEntry.grid_columns import COLIDX
    jid = _job(db)
    plain = _row(db, jid)
    made1 = _row(db, jid, quantity=3)
    ticked = _row(db, jid, keep_flag=1)
    made2 = _row(db, jid, quantity=3)
    _make(db, jid, [made1], n=1)
    _make(db, jid, [made2], n=2)
    m = StagingTableModel(db.conn, jid)
    m.sort_rows(COLIDX["keep_flag"])
    assert [r["id"] for r in m._rows if r.get("id")] == [made2, made1, ticked, plain]
