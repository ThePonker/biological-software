"""Round 4 C (24 Nov 2026): the workbook loader keeps an unreadable Qty as typed; Observatum keys need
initials; the VC comes from the grid ref on every route and is re-checked at commit; commit writes
grid_precision and subfamily; the two one-off data scripts. Small purpose-made databases only."""
import importlib.util
import os
import sqlite3
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from DataEntry import commit_service as cs  # noqa: E402
from DataEntry import staging_repo as repo  # noqa: E402
from shared import import_core, observatum_keys  # noqa: E402
from shared import taxon_groups as tg  # noqa: E402
from shared.vc_rule import vc_for_grid_ref, vc_fields  # noqa: E402


def _script(*parts):
    path = os.path.join(ROOT, *parts)
    if not os.path.isfile(path):          # scripts/_oneoff is git-ignored (and archived later)
        pytest.skip(f"{os.path.basename(path)} not present")
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FakeVC:
    """get_vc_from_grid_ref: SP -> VC 23 Oxfordshire, TQ -> VC 21 Middlesex, ZZ -> not placed."""
    def get_vc_from_grid_ref(self, ref):
        return {"SP": (23, "Oxfordshire"), "TQ": (21, "Middlesex")}.get(ref[:2])


def _staging(tmp_path, rows, name="s.db"):
    conn = sqlite3.connect(tmp_path / name)
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    for r in rows:
        repo.insert_row(conn, jid, {"date": "05/06/2026", "quantity": "1", "recorder": "X", "site_name": "S",
                                    "species_name": "Amara aenea", **r})
    return conn, jid


# ---------------------------------------------------------------- 1. the workbook loader's Qty
def test_qty_is_stored_as_the_grid_stores_it():
    assert cs.qty_as_typed(3.0) == 3 and cs.qty_as_typed("5") == 5 and cs.qty_as_typed(" 7 ") == 7
    assert cs.qty_as_typed("c.20") == "c.20" and cs.qty_as_typed("2x") == "2x" and cs.qty_as_typed(0) == "0"
    assert cs.qty_as_typed(None) is None and cs.qty_as_typed("") is None
    from DataEntry.staging_model import StagingTableModel
    assert StagingTableModel._as_qty("c.20") == "c.20" and StagingTableModel._as_qty("4") == 4


def test_loader_keeps_unreadable_qty_and_the_commit_guard_holds_the_row(tmp_path):
    m = _script("scripts", "load_workbook_to_staging.py")
    index = {c: i for i, c in enumerate(m.COLUMN_MAP.values())}
    def row(**kw):
        r = [None] * len(index)
        for k, v in kw.items():
            r[index[k]] = v
        return r
    body = [row(species_name="A a", quantity="c.20", grid_ref="SP1234"), row(),
            row(species_name="B b", quantity=3.0, grid_ref="TQ1234"), row(species_name="C c", quantity="2x"),
            row(species_name="D d", quantity=None)]
    recs, stats = m.build_records(body, index, FakeVC())
    qty = [r.get("quantity") for r in recs]
    assert qty == ["c.20", None, 3, "2x", None]
    assert (recs[0]["vc_number"], recs[2]["vc_number"]) == (23, 21)           # VC from the grid ref
    assert stats["vc_unplaced"] == 0
    conn = sqlite3.connect(tmp_path / "w.db")
    conn.row_factory = sqlite3.Row
    jid = m.insert(conn, "wb", "Commercial", recs, "wb.xlsm")                  # through the repository
    got = repo.fetch_rows(conn, jid)
    assert [r["row_order"] for r in got] == [1, 2, 3, 4, 5] and got[1]["species_name"] is None
    assert [r["quantity"] for r in got] == ["c.20", None, 3, "2x", None]
    assert repo.get_job(conn, jid)["mode"] == "Commercial" and "wb.xlsm" in repo.get_job(conn, jid)["notes"]
    assert [cs._eligibility(dict(r, date="2026-06-05")) for r in got[:1]] == ["bad_qty"]
    assert cs._eligibility(dict(got[2], date="2026-06-05")) is None


# ---------------------------------------------------------------- 2. initials
class _Settings:
    def __init__(self, value=None):
        self.value_ = value

    def value(self, key, default=None):
        assert key == observatum_keys.INITIALS_SETTING
        return self.value_ if self.value_ is not None else default


def test_user_initials_raise_when_none():
    assert observatum_keys.user_initials(_Settings(" wjh ")) == "WJH"
    for blank in (None, "", "   "):
        with pytest.raises(observatum_keys.MissingInitials, match="initials"):
            observatum_keys.user_initials(_Settings(blank))


def test_the_model_never_falls_back_to_usr_and_commit_refuses_to_start(tmp_path):
    from PySide6.QtCore import QSettings
    from src.core.config import Settings
    from test_r18_observation_create import Db
    from src.models.observation import ObservationModel
    assert Settings.USER_INITIALS == observatum_keys.INITIALS_SETTING
    s = QSettings()
    s.remove(Settings.USER_INITIALS)
    db = Db(str(tmp_path / "o.db"))
    model = ObservationModel(db)
    with pytest.raises(observatum_keys.MissingInitials):
        model._generate_observatum_key()
    conn, jid = _staging(tmp_path, [{"grid_ref": "SP1234"}])
    with pytest.raises(ValueError, match="initials"):
        cs.commit_job(db, model, conn, repo.get_job(conn, jid), taxonomy={})
    assert db.rows() == [] and repo.row_count(conn, jid) == 1                 # nothing written
    s.setValue(Settings.USER_INITIALS, "WJH")
    try:
        assert model._generate_observatum_key().startswith("OBS-WJH-")
        assert cs.commit_job(db, model, conn, repo.get_job(conn, jid), taxonomy={})["committed"] == 1
        assert db.rows()[0]["observatum_key"].startswith("OBS-WJH-")
    finally:
        s.remove(Settings.USER_INITIALS)


# ---------------------------------------------------------------- 3. VC from the grid ref
def test_the_vc_rule():
    assert vc_for_grid_ref(FakeVC(), "SP1234") == (23, "Oxfordshire")
    assert vc_for_grid_ref(FakeVC(), "ZZ1234") == (None, None) and vc_for_grid_ref(FakeVC(), "") == (None, None)
    assert vc_for_grid_ref(None, "SP1234") is None and vc_for_grid_ref(None, " ") == (None, None)
    assert vc_fields(None, "SP1234") == {} and vc_fields(FakeVC(), "TQ1")["vc_number"] == 21

    class Broken:
        def get_vc_from_grid_ref(self, ref):
            raise RuntimeError("db gone")
    assert vc_for_grid_ref(Broken(), "SP1234") == (None, None)


def test_photo_intake_rows_get_their_vc(tmp_path):
    from shared import photo_intake as pi
    conn = sqlite3.connect(tmp_path / "p.db")
    conn.row_factory = sqlite3.Row
    repo.ensure_schema(conn)
    jid = repo.create_job(conn, "Personal", "Personal", None, None)
    ref = pi.grid_ref(51.75, -1.26)
    g = [{"path": str(tmp_path / "missing.jpg"), "taken": "2026-06-05", "time": "", "lat": 51.75, "lon": -1.26}]
    failures = []
    pi.make_rows(conn, jid, [g], {"species_name": "Amara aenea"}, failures=failures, vc_service=FakeVC())
    row = repo.fetch_rows(conn, jid)[0]
    assert row["grid_ref"] == ref and (row["vc_number"], row["vice_county"]) == (23, "Oxfordshire")


def test_commit_works_out_the_vc_again_and_holds_an_unplaceable_grid_ref(tmp_path):
    conn, jid = _staging(tmp_path, [
        {"grid_ref": "SP1234", "vc_number": 99, "vice_county": "Stale"},    # a changed ref kept the old VC
        {"grid_ref": "TQ1234"},                                             # no VC (photo / workbook row)
        {"grid_ref": "ZZ1234", "vc_number": 23},                            # cannot be placed: stays
        {"grid_ref": None, "vc_number": 5, "vice_county": "Five"}])          # no ref: as staged
    made = []

    class Model:
        def create(self, o, extra=None):
            made.append(o.kw)
            return len(made)

    class Obs:
        def __init__(self, **kw):
            self.kw = kw

    s = cs.commit_job(None, Model(), conn, repo.get_job(conn, jid), observation_cls=Obs, taxonomy={},
                      vc_service=FakeVC())
    assert s["committed"] == 3 and s["skipped_no_vc"] == 1 and s["no_vc_rows"] == [1] and s["error"] is None
    assert [(k["vc_number"], k["vice_county"]) for k in made] == [
        (23, "Oxfordshire"), (21, "Middlesex"), (5, "Five")]
    assert s["vc_corrected"] == 2
    left = repo.fetch_rows(conn, jid)
    assert [r["grid_ref"] for r in left] == ["ZZ1234"]                      # held in staging


def test_grid_leaves_the_vc_with_no_service_and_works_it_out_with_one(tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from DataEntry.staging_model import StagingTableModel
    conn, jid = _staging(tmp_path, [{"grid_ref": "SP1234", "vc_number": 23, "vice_county": "Oxfordshire"}])
    m = StagingTableModel(conn, jid, None)
    m._rows[0]["grid_ref"] = "TQ9999"
    m._derive_vc(0)       # nothing can be checked: left as it was (cleared only by an empty ref)
    assert (m._rows[0]["vc_number"], m._rows[0]["vice_county"]) == (23, "Oxfordshire")
    m2 = StagingTableModel(conn, jid, FakeVC())
    m2._rows[0]["grid_ref"] = "TQ9999"
    m2._derive_vc(0)
    assert (m2._rows[0]["vc_number"], m2._rows[0]["vice_county"]) == (21, "Middlesex")


# ---------------------------------------------------------------- 4. grid_precision and subfamily
VALID_REFS = ["TQ12", "TQ1234", "TQ123456", "TQ12345678", "TQ1234567890", "TQ13A", "SU 12 34"]


def test_import_core_gives_a_precision_for_every_valid_grid_ref():
    got = {r: import_core.grid_precision(r) for r in VALID_REFS}
    assert all(got.values()), got
    assert [got[r] for r in VALID_REFS[:5]] == [10000, 1000, 100, 10, 1] and got["TQ13A"] == 2000
    assert import_core.grid_precision("XX99") is None and import_core.grid_precision("") is None


def test_every_record_writing_route_stores_grid_precision(tmp_path, monkeypatch):
    """Data Entry's commit (real ObservationModel, real INSERT) for every valid grid ref."""
    from test_r18_observation_create import Db
    from src.models.observation import ObservationModel
    monkeypatch.setattr(ObservationModel, "_generate_observatum_key",
                        lambda self: f"OBS-T-{len(self.db.execute_main('SELECT id FROM observations')) + 1}")
    db = Db(str(tmp_path / "o.db"))
    conn, jid = _staging(tmp_path, [{"grid_ref": r} for r in VALID_REFS] + [{"grid_ref": None}])
    s = cs.commit_job(db, ObservationModel(db), conn, repo.get_job(conn, jid), taxonomy={})
    assert s["committed"] == len(VALID_REFS) + 1 and s["error"] is None
    stored = {r["grid_ref"]: r["grid_precision"] for r in db.rows()}
    assert stored.pop(None) is None                                        # no ref: no precision
    assert all(stored[r] is not None and stored[r] == import_core.grid_precision(r) for r in VALID_REFS), stored


def test_commit_carries_subfamily_and_taxonomy_for_tvks_supplies_it(tmp_path, monkeypatch):
    path = str(tmp_path / "uksi.db")
    u = sqlite3.connect(path)
    u.execute('CREATE TABLE taxa (tvk TEXT, scientific_name TEXT, rank TEXT, parent_tvk TEXT, kingdom TEXT, '
              'phylum TEXT, class TEXT, "order" TEXT, family TEXT, sort_code INTEGER, superfamily TEXT)')
    u.executemany("INSERT INTO taxa VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
        ("SP1", "Cerambyx cerdo", "Species", "GEN", "Animalia", "Arthropoda", "Insecta", "Coleoptera",
         "Cerambycidae", 5, "Chrysomeloidea"),
        ("GEN", "Cerambyx", "Genus", "SUB", None, None, None, None, None, 4, None),
        ("SUB", "Cerambycinae", "Subfamily", None, None, None, None, None, None, 3, None)])
    u.commit()
    u.close()
    tax = tg.taxonomy_for_tvks(["SP1"], path)
    assert tax["SP1"]["subfamily"] == "Cerambycinae"
    conn, jid = _staging(tmp_path, [{"species_tvk": "SP1", "grid_ref": "SP1234"}])
    seen = []

    class Model:
        def create(self, o, extra=None):
            seen.append((o.kw, extra))
            return 1

    class Obs:
        def __init__(self, **kw):
            self.kw = kw

    cs.commit_job(None, Model(), conn, repo.get_job(conn, jid), observation_cls=Obs, taxonomy=tax)
    kw, extra = seen[0]
    assert extra["subfamily"] == "Cerambycinae" and kw["grid_precision"] == 1000


# ---------------------------------------------------------------- the one-off data scripts
def _obs_db(tmp_path, name, rows, extra_table=False):
    p = tmp_path / name
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, observatum_key TEXT, external_key TEXT, "
              "irecord_exported_on TEXT, grid_ref TEXT, grid_precision INTEGER, updated_at TEXT)")
    c.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,?)", rows)
    if extra_table:
        c.execute("CREATE TABLE photo_links (id INTEGER PRIMARY KEY, note TEXT)")
        c.execute("INSERT INTO photo_links VALUES (1, 'see OBS-USR-20261110-000002')")
    c.commit()
    c.close()
    return str(p)


def _keys(path):
    c = sqlite3.connect(path)
    try:
        return [r[0] for r in c.execute("SELECT observatum_key FROM observations ORDER BY id")]
    finally:
        c.close()


def test_renumber_usr_keys_dry_run_apply_and_refusals(tmp_path, capsys):
    m = _script("scripts", "_oneoff", "renumber_usr_keys_20261124.py")
    bk = str(tmp_path / "bk")
    rows = [(1, "OBS-USR-20261110-000001", None, None, None, None, "t"),
            (2, "OBS-USR-20261110-000002", None, None, None, None, "t"),
            (3, "OBS-WJH-20261110-000009", None, None, None, None, "t")]
    db = _obs_db(tmp_path, "a.db", rows)
    assert m.main(["--db", db, "--backup-dir", bk]) == 0                      # dry run
    assert "Nothing has been changed" in capsys.readouterr().out
    assert _keys(db)[0].startswith("OBS-USR-") and not os.path.exists(bk)
    assert m.main(["--db", db, "--backup-dir", bk, "--apply"]) == 0
    assert "Done." in capsys.readouterr().out
    assert _keys(db) == ["OBS-WJH-20261110-000001", "OBS-WJH-20261110-000002", "OBS-WJH-20261110-000009"]
    c = sqlite3.connect(db)
    assert c.execute("SELECT updated_at FROM observations WHERE id=1").fetchone()[0] == "t"
    c.close()
    assert len(os.listdir(bk)) == 1
    assert m.main(["--db", db, "--backup-dir", bk, "--apply"]) == 0           # again: nothing to do
    assert len(os.listdir(bk)) == 1

    cases = {
        "collision": [(1, "OBS-USR-20261110-000001", None, None, None, None, ""),
                      (2, "OBS-WJH-20261110-000001", None, None, None, None, "")],
        "exported": [(1, "OBS-USR-20261110-000001", None, "2026-11-11", None, None, "")],
        "odd key": [(1, "OBS-USR-test", None, None, None, None, "")],
        "same key twice": [(1, "OBS-USR-20261110-000001", None, None, None, None, ""),
                           (2, "OBS-USR-20261110-000001", None, None, None, None, "")],
        "other column": [(1, "OBS-USR-20261110-000001", "OBS-USR-20261110-000001", None, None, None, "")]}
    for name, r in cases.items():
        db = _obs_db(tmp_path, f"{name.replace(' ', '_')}.db", r)
        assert m.main(["--db", db, "--backup-dir", bk, "--apply"]) == 1, name
        assert "REFUSED" in capsys.readouterr().out and _keys(db)[0].startswith("OBS-USR-"), name
    db = _obs_db(tmp_path, "other_table.db", rows[:2], extra_table=True)
    assert m.main(["--db", db, "--backup-dir", bk, "--apply"]) == 1
    assert "photo_links.note" in capsys.readouterr().out and _keys(db)[0].startswith("OBS-USR-")
    assert len(os.listdir(bk)) == 1                                            # refusals back up nothing


def test_fill_grid_precision_dry_run_apply_and_guard(tmp_path, capsys):
    m = _script("scripts", "_oneoff", "fill_grid_precision_20261124.py")
    bk = str(tmp_path / "bk")
    rows = [(1, "k1", None, None, "TQ123456", None, "t"), (2, "k2", None, None, "SP12", None, "t"),
            (3, "k3", None, None, "TQ13A", None, "t"), (4, "k4", None, None, "nonsense", None, "t"),
            (5, "k5", None, None, None, None, "t"), (6, "k6", None, None, "TQ1234", 7, "t")]
    db = _obs_db(tmp_path, "g.db", rows)

    def precisions():
        c = sqlite3.connect(db)
        try:
            return [r[0] for r in c.execute("SELECT grid_precision FROM observations ORDER BY id")]
        finally:
            c.close()
    assert m.main(["--db", db, "--backup-dir", bk]) == 0
    out = capsys.readouterr().out
    assert "to fill (readable grid ref): 3" in out and "Nothing has been changed" in out
    assert precisions() == [None] * 5 + [7]
    assert m.main(["--db", db, "--backup-dir", bk, "--apply"]) == 0
    assert "Done." in capsys.readouterr().out
    assert precisions() == [100, 10000, 2000, None, None, 7]                   # a set value is never touched
    assert len(os.listdir(bk)) == 1
    assert m.main(["--db", db, "--backup-dir", bk, "--apply"]) == 0
    assert len(os.listdir(bk)) == 1


def test_commit_keeps_a_staged_vc_the_boundary_square_touches():
    from DataEntry.commit_service import _staged_vc_fits

    class Boundary:
        def assess(self, ref):
            return {"vcs": [(22, 54.0), (23, 46.0)]}
    assert _staged_vc_fits(Boundary(), "SU6477", 23) is True       # recorder's side kept
    assert _staged_vc_fits(Boundary(), "SU6477", 30) is False      # not in this square: replaced
    assert _staged_vc_fits(Boundary(), "SU6477", None) is False
    assert _staged_vc_fits(object(), "SU6477", 23) is False        # no assess(): the rule decides
