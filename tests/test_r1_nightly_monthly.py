"""Round 1, item 6: the monthly set leaves out safety copies (_pre_ / _prelive_) and side files."""
from _backup_fixtures import NOW, _db, _env_fixture, _members  # noqa: F401

from shared import nightly_backup as nb


def test_monthly_leaves_out_safety_copies_and_logs_them(env):
    for name in ("observatum_pre_import_20261101.db", "munia_PRE_delete.db",
                 "observatum_prelive_20261110.db", "Codex_PreLive_x.db"):
        _db(env.data / name)
    (env.data / "observatum.db-wal").write_text("x")
    (env.data / "observatum.db-shm").write_text("x")
    (env.data / "unpre_fixed.db").write_text("")      # "_pre" without the trailing underscore: kept
    _db(env.data / "unpre_fixed.db")
    assert nb.run(NOW) == 0
    members = _members(env.base / "monthly" / "2026-11.zip")
    assert members >= {"observatum.db", "munia.db", "uksi.db", "pantheon.db", "unpre_fixed.db"}
    assert not [m for m in members if "_pre_" in m.lower() or "_prelive_" in m.lower()]
    assert not [m for m in members if m.endswith(("-wal", "-shm"))]
    log = (env.base / "backup_log.txt").read_text()
    for name in ("observatum_pre_import_20261101.db", "munia_PRE_delete.db",
                 "observatum_prelive_20261110.db", "Codex_PreLive_x.db"):
        assert name in log
    assert "safety copies not included" in log


def test_no_skip_line_when_nothing_skipped(env):
    nb.run(NOW)
    assert "safety copies" not in (env.base / "backup_log.txt").read_text()
