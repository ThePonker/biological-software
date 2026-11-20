"""shared/nightly_backup: run, prune, lock, zip checks (setup script and status line are in the other two files)."""
import ast
import json
import os
from datetime import datetime, timedelta

import pyzipper
import pytest
from _backup_fixtures import NOW, PW, REPO, _members, _stamp, _env_fixture  # noqa: F401

from shared import backup_service
from shared import nightly_backup as nb


def test_zip_written_opens_with_password_only(env):
    assert nb.run(NOW) == 0
    z = env.base / "nightly" / "2026-11-19.zip"
    assert z.is_file()
    assert _members(z) >= {"observatum.db", "codex.db", "manifest.json"}
    assert "uksi.db" not in _members(z)
    with pyzipper.AESZipFile(str(z)) as zf:
        with pytest.raises(RuntimeError):
            zf.read("manifest.json")
    with pyzipper.AESZipFile(str(z)) as zf:
        zf.setpassword(b"wrong password")
        with pytest.raises(RuntimeError):
            zf.read("manifest.json")


def test_manifest_hashes(env):
    nb.run(NOW)
    with pyzipper.AESZipFile(str(env.base / "nightly" / "2026-11-19.zip")) as zf:
        zf.setpassword(PW.encode())
        m = json.loads(zf.read("manifest.json"))
        assert m["computer"] == "PC-1"
        import hashlib
        for f in m["files"]:
            body = zf.read(f["name"])
            assert hashlib.sha256(body).hexdigest() == f["sha256"] and len(body) == f["bytes"]


def test_verify_failure_no_zip_no_prune_no_stamp(env, monkeypatch):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    for d in range(1, 20):
        (nd / f"2026-10-{d:02d}.zip").write_text("old")
    monkeypatch.setattr(backup_service, "verify_copy", lambda p: "broken")
    assert nb.run(NOW) == 1
    assert not (nd / "2026-11-19.zip").exists()
    assert not list(nd.glob("*.partial"))
    assert len(list(nd.glob("*.zip"))) == 19
    assert not (env.data / "backup_status.json").exists()


def test_zip_verify_failure_keeps_old_and_does_not_prune(env, monkeypatch):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    for d in range(1, 20):
        (nd / f"2026-10-{d:02d}.zip").write_text("old")
    monkeypatch.setattr(nb, "_verify_zip", lambda p, pw: "bad")
    assert nb.run(NOW) == 1
    assert not (nd / "2026-11-19.zip").exists()
    assert len(list(nd.glob("*.zip"))) == 19
    assert not (env.data / "backup_status.json").exists()


def test_prune_keeps_newest_by_name(env):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    names = [f"2026-10-{d:02d}.zip" for d in range(1, 11)]
    for n in reversed(names):             # mtime order opposite to name order
        (nd / n).write_text("z")
    (nd / "notes.txt").write_text("keep")
    (nd / "2026-10-05.zip.partial").write_text("keep")
    (nd / "2026-10.zip").write_text("keep")
    (nd / "sub.zip").mkdir()
    other = env.drive / nb.DEFAULTS["folder_name"] / "PC-2" / "nightly"
    other.mkdir(parents=True)
    (other / "2026-01-01.zip").write_text("theirs")
    removed = nb.prune(nd, nb.NIGHTLY_RE, 3, names[-1])
    assert sorted(removed) == names[:7]
    assert sorted(p.name for p in nd.glob("2026-10-??.zip")) == names[7:]
    assert (nd / "notes.txt").exists() and (nd / "2026-10.zip").exists() and (nd / "2026-10-05.zip.partial").exists()
    assert (other / "2026-01-01.zip").exists()


def test_prune_not_below_keep_plus_one(env):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    for d in range(1, 4):
        (nd / f"2026-10-{d:02d}.zip").write_text("z")
    assert nb.prune(nd, nb.NIGHTLY_RE, 3, "2026-10-03.zip") == []
    assert len(list(nd.glob("*.zip"))) == 3


def test_prune_refuses_wrong_folders(env, tmp_path):
    bad = tmp_path / "elsewhere" / "nightly"
    bad.mkdir(parents=True)
    (bad / "2026-10-01.zip").write_text("z")
    (bad / "2026-10-02.zip").write_text("z")
    with pytest.raises(ValueError):
        nb.prune(bad, nb.NIGHTLY_RE, 1, "2026-10-02.zip")
    other = env.drive / nb.DEFAULTS["folder_name"] / "PC-2" / "nightly"
    other.mkdir(parents=True)
    with pytest.raises(ValueError):
        nb.prune(other, nb.NIGHTLY_RE, 1, "x.zip")
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    with pytest.raises(ValueError):
        nb.prune(nd, nb.MONTHLY_RE, 1, "x.zip")           # pattern does not match the folder kind
    with pytest.raises(ValueError):
        nb.prune(env.base, nb.NIGHTLY_RE, 1, "x.zip")
    assert len(list(bad.glob("*.zip"))) == 2


def test_prune_never_before_new_zip_verified(env, monkeypatch):
    calls = []
    monkeypatch.setattr(nb, "prune", lambda *a: calls.append(a) or [])
    monkeypatch.setattr(nb, "_verify_zip", lambda p, pw: "bad")
    assert nb.run(NOW) == 1
    assert calls == []
    monkeypatch.setattr(nb, "_verify_zip", lambda p, pw: None)
    assert nb.run(NOW) == 0
    assert len(calls) == 2


def test_run_prunes_after_success(env):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    for d in range(1, 20):
        (nd / f"2026-10-{d:02d}.zip").write_text("old")
    assert nb.run(NOW) == 0
    assert len(list(nd.glob("*.zip"))) == 14
    assert (nd / "2026-11-19.zip").exists()


def test_leftover_partial_moved_to_failed(env):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    (nd / "2026-11-18.zip.partial").write_text("crashed")
    assert nb.run(NOW) == 0
    assert not list(nd.glob("*.partial"))
    moved = list((env.base / "_failed").iterdir())
    assert len(moved) == 1 and moved[0].read_text() == "crashed"


def test_second_run_same_day_replaces(env):
    assert nb.run(NOW) == 0
    assert nb.run(NOW + timedelta(hours=1), force=True) == 0
    assert [p.name for p in (env.base / "nightly").glob("*.zip")] == ["2026-11-19.zip"]


def test_monthly_once_per_month_with_reference_dbs(env):
    nb.run(NOW)
    mz = env.base / "monthly" / "2026-11.zip"
    assert _members(mz) >= {"uksi.db", "pantheon.db", "observatum.db", "saved_filters.json", "manifest.json"}
    stamp = json.loads((env.data / "backup_status.json").read_text())
    assert stamp["monthly"] == "2026-11.zip"
    nb.run(NOW + timedelta(days=1))
    assert [p.name for p in (env.base / "monthly").glob("*.zip")] == ["2026-11.zip"]
    assert json.loads((env.data / "backup_status.json").read_text())["monthly"] is None
    nb.run(datetime(2026, 12, 1, 19, 0))
    assert (env.base / "monthly" / "2026-12.zip").exists()


def test_away_skips_and_writes_nothing(env, monkeypatch):
    monkeypatch.setattr(nb, "away_active", lambda: True)
    before = sorted(p.name for p in env.data.iterdir())
    assert nb.run(NOW) == 0
    assert sorted(p.name for p in env.data.iterdir()) == before
    assert not env.base.exists()
    assert "away copy" in (env.local / "BiologicalSoftware" / "backup_log.txt").read_text()


def test_no_drive_skips_exit_0(env, monkeypatch):
    monkeypatch.setattr(nb, "find_backup_drive", lambda folder_name=None: None)
    assert nb.run(NOW) == 0
    assert "backup drive not connected" in (env.local / "BiologicalSoftware" / "backup_log.txt").read_text()
    assert not (env.data / "backup_status.json").exists()


def test_no_password_exit_1(env):
    env.keys.clear()
    assert nb.run(NOW) == 1
    assert "no password" in (env.local / "BiologicalSoftware" / "backup_log.txt").read_text()
    assert not (env.base / "nightly").exists()


def test_status_stamp_written(env):
    nb.run(NOW)
    s = json.loads((env.data / "backup_status.json").read_text())
    assert s["computer"] == "PC-1" and s["nightly"] == "2026-11-19.zip" and s["last_ok"].startswith("2026-11-19T19:02")
    assert "backup complete" in (env.base / "backup_log.txt").read_text()


def test_remove_only_in_prune_and_release_lock():
    forbidden = ("remove", "unlink", "rmtree", "rmdir")
    found = {}
    for mod in ("nightly_backup", "backup_settings", "backup_zip"):
        tree = ast.parse((REPO / "shared" / f"{mod}.py").read_text(encoding="utf-8"))
        for top in tree.body:
            inside = top.name if isinstance(top, ast.FunctionDef) else "<module>"
            for node in ast.walk(top):
                if isinstance(node, ast.Attribute) and node.attr in forbidden:
                    found.setdefault((mod, inside), []).append(node.attr)
                if isinstance(node, ast.Name) and node.id in forbidden:
                    found.setdefault((mod, inside), []).append(node.id)
    assert set(found) == {("nightly_backup", "prune"), ("nightly_backup", "release_lock")}, found


def test_nothing_names_a_person_or_business():
    needle = "fla" + "una"
    for rel in ("shared/nightly_backup.py", "shared/backup_settings.py", "shared/backup_zip.py",
                "scripts/setup_nightly_backup.py", "docs/Backups.md", "requirements.txt",
                "tests/_backup_fixtures.py", "tests/test_nightly_backup.py",
                "tests/test_nightly_backup_status.py", "tests/test_setup_nightly_backup.py"):
        assert needle not in (REPO / rel).read_text(encoding="utf-8").lower(), rel


def test_fix1_prune_protects_and_stops_on_future_files(env):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    for n in ("2026-11-17.zip", "2026-11-18.zip", "2026-11-19.zip", "2027-01-01.zip"):
        (nd / n).write_text("z")
    assert nb.prune(nd, nb.NIGHTLY_RE, 1, "2026-11-19.zip") == []
    assert len(list(nd.glob("*.zip"))) == 4
    assert "not pruned: 2027-01-01.zip is dated after today -- check the computer clock" in (
        env.base / "backup_log.txt").read_text()
    with pytest.raises(ValueError):
        nb.prune(nd, nb.NIGHTLY_RE, 1, "")
    with pytest.raises(ValueError):
        nb.prune(nd, nb.NIGHTLY_RE, 1, "2026-01-01.zip")        # not in the folder


def test_fix1_run_with_future_file_does_not_prune_and_stamps_warning(env):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    for d in range(1, 20):
        (nd / f"2026-10-{d:02d}.zip").write_text("old")
    (nd / "2027-01-01.zip").write_text("future")
    assert nb.run(NOW) == 0
    assert len(list(nd.glob("*.zip"))) == 21
    stamp = json.loads((env.data / "backup_status.json").read_text())
    assert "dated after today" in stamp["warning"]
    text, level = nb.status_text(NOW)
    assert level == "red" and "check the computer clock" in text


def test_fix2_observatum_missing_fails(env):
    (env.data / "observatum.db").rename(env.data / "elsewhere.dbx")
    assert nb.run(NOW) == 1
    assert not list((env.base / "nightly").glob("*.zip")) and not (env.data / "backup_status.json").exists()
    assert "FAILED: observatum.db is missing" in (env.local / "BiologicalSoftware" / "backup_log.txt").read_text()


def test_fix2_other_absent_dbs_logged_by_name(env):
    (env.data / "lector.db").rename(env.data / "elsewhere.dbx")
    assert nb.run(NOW) == 0
    assert "lector.db" in (env.base / "backup_log.txt").read_text()
    assert "lector.db" not in _members(env.base / "nightly" / "2026-11-19.zip")


def test_fix4_lock_held_exits_0(env):
    env.base.mkdir(parents=True)
    (env.base / nb.LOCK_NAME).write_text(json.dumps({"pid": 1, "time": "now"}))
    assert nb.run(NOW) == 0
    assert "another backup is running" in (env.base / "backup_log.txt").read_text()
    assert not (env.base / "nightly").exists() or not list((env.base / "nightly").glob("*.zip"))
    assert (env.base / nb.LOCK_NAME).exists()                        # not ours: left alone


def test_fix4_stale_lock_moved_and_lock_released(env):
    env.base.mkdir(parents=True)
    lock = env.base / nb.LOCK_NAME
    lock.write_text(json.dumps({"pid": 1, "time": "old"}))
    old = os.path.getmtime(lock) - 4 * 3600
    os.utime(lock, (old, old))
    assert nb.run(NOW) == 0
    assert (env.base / "nightly" / "2026-11-19.zip").exists()
    assert not lock.exists()
    assert any("stale" in p.name for p in (env.base / "_failed").iterdir())


def test_fix4_lock_released_after_failure_and_partial_name_has_pid(env, monkeypatch):
    seen = []
    real = nb._write_zip
    monkeypatch.setattr(nb, "_write_zip", lambda partial, *a: seen.append(partial.name) or real(partial, *a))
    monkeypatch.setattr(nb, "_verify_zip", lambda p, pw: "bad")
    assert nb.run(NOW) == 1
    assert not (env.base / nb.LOCK_NAME).exists()
    assert seen[0] == f"2026-11-19.zip.{os.getpid()}.partial"


def test_fix4_release_lock_only_removes_own(env):
    env.base.mkdir(parents=True)
    lock = env.base / nb.LOCK_NAME
    lock.write_text(json.dumps({"pid": os.getpid() + 1}))
    nb.release_lock(env.base)
    assert lock.exists()
    lock.write_text(json.dumps({"pid": os.getpid()}))
    nb.release_lock(env.base)
    assert not lock.exists()


def test_fix5_fsync_partial_and_final(env, monkeypatch):
    calls = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: calls.append(fd) or real(fd))
    assert nb.run(NOW) == 0
    assert len(calls) >= 4                                            # 2 partials + 2 finals
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError("x")))
    nb._fsync_file(env.data / "observatum.db", strict=False)           # ignored
    with pytest.raises(OSError):
        nb._fsync_file(env.data / "observatum.db", strict=True)


def test_fix6_stamp_retry_and_complete_logged_first(env, monkeypatch):
    attempts, sleeps = [], []
    monkeypatch.setattr(nb, "_write_status", lambda st: attempts.append(1) or (_ for _ in ()).throw(OSError("busy")))
    monkeypatch.setattr(nb, "_sleep", lambda n: sleeps.append(n))
    assert nb.run(NOW) == 0
    assert len(attempts) == 5 and len(sleeps) == 4
    log = (env.base / "backup_log.txt").read_text()
    assert "backup made; status stamp not written" in log
    assert log.index("backup complete") < log.index("status stamp not written")


def test_fix8_failed_lines_go_to_local_log(env, monkeypatch):
    monkeypatch.setattr(nb, "_verify_zip", lambda p, pw: "bad")
    nb.run(NOW)
    assert "FAILED" in (env.local / "BiologicalSoftware" / "backup_log.txt").read_text()


def test_fix8_main_logs_traceback(env, monkeypatch):
    def boom(**k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(nb, "run", boom)
    assert nb.main([]) == 1
    assert "kaboom" in (env.local / "BiologicalSoftware" / "backup_log.txt").read_text()


def test_fix9_already_done_today_unless_force(env):
    assert nb.run(NOW) == 0
    z = env.base / "nightly" / "2026-11-19.zip"
    before = z.stat().st_mtime_ns
    assert nb.run(NOW + timedelta(hours=1)) == 0
    assert z.stat().st_mtime_ns == before
    assert "already done today" in (env.base / "backup_log.txt").read_text()
    assert nb.run(NOW + timedelta(hours=1), force=True) == 0
    assert z.stat().st_mtime_ns != before
    assert "missed night" in (REPO / "docs" / "Backups.md").read_text()


def test_fix14_failed_folder_documented():
    assert "_failed" in (REPO / "docs" / "Backups.md").read_text() and "safe to empty" in (
        REPO / "docs" / "Backups.md").read_text()


def test_fix16_prune_casefold(env):
    nd = env.base / "nightly"
    nd.mkdir(parents=True)
    for n in ("2026-10-01.ZIP", "2026-10-02.zip", "2026-10-03.zip"):
        (nd / n).write_text("z")
    assert nb.prune(nd, nb.NIGHTLY_RE, 2, "2026-10-03.ZIP") == ["2026-10-01.ZIP"]


def test_fix20_unencrypted_member_fails_verification(tmp_path):
    import zipfile
    z = tmp_path / "plain.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"files": []}))
    why = nb._verify_zip(z, PW)
    assert why and "not encrypted" in why
