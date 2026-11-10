"""Round 13: vice-county name aliases, the scheme importer's fallback, and the one-off backfill of
recording_scheme.vc_number. Purpose-made databases in tmp_path; backups go to a temporary root."""
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "Observatum"), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SCRIPT = ROOT / "scripts" / "_oneoff" / "backfill_scheme_vc_numbers_20261024.py"


def _script():
    spec = importlib.util.spec_from_file_location("r13_backfill_vc", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _resolver():
    from Observatum.src.views.dialogs.scheme_import_wizard.validation_worker import (
        resolve_vc_number_from_text)
    return resolve_vc_number_from_text


ROWS = [
    # (vice_county, vc_number)
    ("Leicestershire", None),                       # alias -> 55
    ("Glamorganshire", None),                       # alias -> 41
    ("Channel Isles", 0),                           # alias -> 113, 0 counts as empty
    ("Surrey", ""),                                 # full name -> 17, blank counts as empty
    ("Antrim", None),                               # Irish: stays empty
    ("Surrey | Middlesex", None),                   # conflicting names: not changed
    ("Leicestershire | Antrim", None),              # one name not understood: left empty
    ("Oxfordshire", 23),                            # already filled: never touched
    ("Oxfordshire", 99),                            # filled (even if odd): never touched
    (None, None),                                   # no text
]


def _make_db(path):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE recording_scheme (id INTEGER PRIMARY KEY, vice_county TEXT, "
              "vc_number INTEGER, species_name TEXT)")
    for i, (vc, n) in enumerate(ROWS, start=1):
        c.execute("INSERT INTO recording_scheme VALUES (?,?,?,?)", (i, vc, n, f"sp{i}"))
    c.commit()
    c.close()
    return path


def _dump(path):
    c = sqlite3.connect(path)
    try:
        return c.execute("SELECT * FROM recording_scheme ORDER BY id").fetchall()
    finally:
        c.close()


@pytest.fixture
def backup_root(tmp_path, monkeypatch):
    from shared import backup_service
    root = tmp_path / "backups"
    root.mkdir()
    monkeypatch.setattr(backup_service, "BACKUP_ROOT", str(root))
    monkeypatch.setenv("BIOSOFT_BACKUP_ROOT", str(root))
    return root


def test_aliases_point_at_the_suites_own_numbers():
    from Observatum.src.core.vc_shortnames import VC_FULL_NAMES, VC_NAME_ALIASES
    expect = {"leicestershire": 55, "glamorganshire": 41, "westmorland": 69,
              "east inverness-shire": 96, "moray": 95, "west perthshire": 87,
              "west cornwall": 1, "channel isles": 113,
              "fifeshire": 85, "fife": 85, "north ebudes": 104, "mid ebudes": 103,
              "south ebudes": 102, "angus": 90, "forfarshire": 90, "argyll": 98,
              "main argyll": 98, "north northumberland": 68}
    assert VC_NAME_ALIASES == expect
    for alias, number in VC_NAME_ALIASES.items():
        assert alias == alias.lower()
        assert str(number) in VC_FULL_NAMES          # a real, British, numbered vice county
    assert not any(str(v).startswith("H") for v in VC_NAME_ALIASES.values())


def test_resolver_full_names_aliases_and_irish():
    r = _resolver()
    assert r("Surrey") == 17
    assert r("  west   CORNWALL ") == 1
    assert r("Leicestershire | Derbyshire") == 55          # the first name only
    assert r("Moray") == 95
    assert r("Antrim") is None and r("Down") is None       # no Irish numbers in the suite
    assert r("") is None and r(None) is None


def test_importer_fallback_uses_the_alias_table():
    import inspect
    from Observatum.src.views.dialogs.scheme_import_wizard import validation_worker as vw
    assert "resolve_vc_number_unambiguous(validated_row.vice_county)" in inspect.getsource(
        vw.SchemeValidationWorker)
    assert vw._find_vc_database() in (None, str(vw.paths.VC_LOOKUP_DB))


def test_dry_run_changes_nothing(tmp_path, capsys):
    db = _make_db(str(tmp_path / "o.db"))
    before = _dump(db)
    assert _script().main(["--db", db]) == 0
    out = capsys.readouterr().out
    assert _dump(db) == before
    assert "Nothing has been changed." in out
    assert "Total rows that would change: 4" in out


def test_plan_counts(tmp_path):
    m = _script()
    p = m.plan(_make_db(str(tmp_path / "o.db")))
    assert p["total"] == 7
    assert sorted((rid, n) for rid, _t, n in p["fills"]) == [(1, 55), (2, 41), (3, 113), (4, 17)]
    assert dict(p["unresolved"]) == {"Antrim": 1}
    assert [c[0] for c in p["conflicts"]] == [6, 7]   # 7: 'Leicestershire | Antrim' (review 24 Oct)


def test_apply_fills_only_empty_ones_with_a_backup(tmp_path, backup_root):
    db = _make_db(str(tmp_path / "o.db"))
    before = _dump(db)
    assert _script().main(["--db", db, "--apply"]) == 0
    after = _dump(db)
    got = {row[0]: row[2] for row in after}
    assert got[1] == 55 and got[2] == 41 and got[3] == 113 and got[4] == 17 and got[7] is None
    assert got[5] is None            # Irish stays NULL
    assert got[6] is None            # conflicting multi-name row not changed
    assert got[8] == 23 and got[9] == 99 and got[10] is None
    for b, a in zip(before, after):  # nothing but vc_number differs
        assert (b[0], b[1], b[3]) == (a[0], a[1], a[3])
    kept = list(backup_root.rglob("*pre-backfill-scheme-vc*"))
    assert kept, "a kept backup copy must exist"
    # second run: nothing left to fill that resolves
    assert _script().plan(db)["fills"] == []


def test_apply_refuses_when_backup_fails(tmp_path, backup_root, monkeypatch, capsys):
    from shared import backup_service
    db = _make_db(str(tmp_path / "o.db"))
    before = _dump(db)
    monkeypatch.setattr(backup_service, "backup_file_written", lambda *a, **k: False)
    assert _script().main(["--db", db, "--apply"]) == 1
    assert _dump(db) == before
    assert "Nothing has been changed." in capsys.readouterr().out


def test_importer_leaves_a_multi_county_record_without_a_number():
    from src.views.dialogs.scheme_import_wizard.validation_worker import (
        resolve_vc_number_unambiguous as r)
    assert r("Shropshire | Worcestershire") is None
    assert r("Leicestershire") == 55
    assert r("Warwickshire | Warwickshire") == 38


def test_review_aliases_and_partly_understood_texts():
    from src.views.dialogs.scheme_import_wizard.validation_worker import (
        resolve_vc_number_unambiguous as r)
    assert r("Fifeshire") == 85 and r("North Ebudes") == 104
    assert r("West Perthshire | Fifeshire") is None       # two VCs
    assert r("West Perthshire | Antrim") is None          # one name not understood
