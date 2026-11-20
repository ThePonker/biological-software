"""scripts/setup_nightly_backup: dry run, apply, task XML, drive checks."""
import json
from pathlib import Path

import pytest
from _backup_fixtures import _env_fixture  # noqa: F401

import paths
from scripts import setup_nightly_backup as setup
from shared import nightly_backup as nb


def test_setup_dry_run_changes_nothing(env, capsys, monkeypatch):
    monkeypatch.setattr(setup, "validate_drive", lambda d: None)
    monkeypatch.setattr(setup, "create_task", lambda x: pytest.fail("task created"))
    monkeypatch.setattr(setup, "delete_task", lambda: pytest.fail("task deleted"))
    before = sorted(p.name for p in env.drive.rglob("*"))
    assert setup.main(["--drive", str(env.drive)]) == 0
    assert setup.main(["--remove"]) == 0
    assert sorted(p.name for p in env.drive.rglob("*")) == before
    assert not nb.settings_path().exists()
    assert "Nothing has been changed" in capsys.readouterr().out


def test_setup_apply_refuses_on_away(env, monkeypatch):
    monkeypatch.setattr(setup, "validate_drive", lambda d: None)
    monkeypatch.setattr(setup, "away_active", lambda: True)
    monkeypatch.setattr(setup, "create_task", lambda x: pytest.fail("task created"))
    assert setup.main(["--drive", str(env.drive), "--apply"]) == 1


def test_setup_apply_creates_files(env, monkeypatch):
    monkeypatch.setattr(setup, "validate_drive", lambda d: None)
    stored = {}
    monkeypatch.setattr(setup, "away_active", lambda: False)
    monkeypatch.setattr(setup, "_keyring_get", lambda: stored.get("pw"))
    monkeypatch.setattr(setup, "_keyring_set", lambda pw: stored.update(pw=pw))
    monkeypatch.setattr(setup, "_ask_password", lambda: "longenough")
    monkeypatch.setattr(setup, "_yes", lambda p: False)
    xml = []
    monkeypatch.setattr(setup, "create_task", lambda x: xml.append(x) or 0)
    assert setup.main(["--drive", str(env.drive), "--apply"]) == 0
    base = env.drive / nb.DEFAULTS["folder_name"]
    assert (base / "HOW TO RESTORE.txt").is_file() and (base / "PC-1").is_dir()
    assert json.loads(nb.settings_path().read_text())["set_up_at"]
    assert nb.settings_path().is_file() and stored["pw"] == "longenough" and len(xml) == 1
    assert setup.main(["--drive", str(env.drive), "--apply"]) == 0     # idempotent


def test_setup_different_restore_text_left_alone(tmp_path):
    p = tmp_path / "HOW TO RESTORE.txt"
    p.write_text("mine")
    assert setup.write_if_absent_or_same(p, setup.RESTORE_TEXT) == "already there (different; left alone)"
    assert p.read_text() == "mine"


def test_task_xml():
    xml = setup.build_task_xml("19:00", r"C:\Py\pythonw.exe", r"C:\Biological Software", "me")
    assert "<StartWhenAvailable>true</StartWhenAvailable>" in xml
    assert "<LogonType>InteractiveToken</LogonType>" in xml
    assert "HighestAvailable" not in xml and "PT2H" in xml
    assert "-m shared.nightly_backup" in xml and "T19:00:00" in xml
    import xml.dom.minidom as md
    md.parseString(xml.split("?>", 1)[1])


def test_fix9_task_has_logon_trigger():
    xml = setup.build_task_xml("19:00", "p.exe", "C:\\x", "PCDOM\\me")
    assert "<LogonTrigger>" in xml and "<Delay>PT10M</Delay>" in xml and "PCDOM\\me" in xml


def test_fix10_drive_validation(monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR", Path("D:\\data"))
    monkeypatch.setenv("SystemDrive", "C:")
    assert setup.validate_drive("E:") is None and setup.validate_drive("e:\\") is None
    for bad in ("D:", "C:", "E", "E:\\x", "EE:", "", "/tmp"):
        assert setup.validate_drive(bad), bad


def test_fix10_main_refuses_bad_drive(env, monkeypatch, capsys):
    monkeypatch.setattr(setup, "create_task", lambda x: pytest.fail("created"))
    assert setup.main(["--drive", "nonsense", "--apply"]) == 1


def test_fix15_task_user(monkeypatch):
    monkeypatch.setenv("USERDOMAIN", "MYPC")
    monkeypatch.setenv("USERNAME", "me")
    assert setup.task_user() == "MYPC\\me"
    assert "<UserId>MYPC\\me</UserId>" in setup.build_task_xml("19:00", "p", "w", setup.task_user())


def test_fix18_restore_text_has_no_hardcoded_counts():
    assert "last 14" not in setup.RESTORE_TEXT and "last 12" not in setup.RESTORE_TEXT
    assert "most recent" in setup.RESTORE_TEXT
