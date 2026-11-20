"""shared/backup_settings: settings, drive scan, password, the home screen status line."""
import json
import os
from datetime import datetime, timedelta

import pytest
from _backup_fixtures import NOW, _stamp, _env_fixture  # noqa: F401

from shared import backup_settings as bs
from shared import nightly_backup as nb


def test_status_text_five_states(env, monkeypatch):
    assert nb.status_text(NOW) == ("Backups: not set up -- see docs\\Backups.md", "grey")
    sp = nb.settings_path()
    sp.parent.mkdir(parents=True)
    sp.write_text("{}")
    assert nb.status_text(NOW) == ("Backups: set up, none made yet", "grey")
    stamp = env.data / "backup_status.json"
    stamp.write_text(json.dumps({"last_ok": "2026-11-19T19:02:00"}))
    assert nb.status_text(NOW) == ("Last backed up: Thu 19 Nov, 19:02", "ok")
    text, level = nb.status_text(NOW + timedelta(days=5))
    assert level == "red" and text == "Last backed up 5 days ago -- check the backup drive"
    monkeypatch.setattr(bs, "away_active", lambda: True)
    assert nb.status_text(NOW) == ("Backups: not needed on an away copy", "grey")


def test_settings_defaults_and_merge(env):
    assert nb.load_settings() == nb.DEFAULTS
    sp = nb.settings_path()
    sp.parent.mkdir(parents=True)
    sp.write_text(json.dumps({"keep_nightly": 5, "time": "20:30", "bogus": 1}))
    s = nb.load_settings()
    assert s["keep_nightly"] == 5 and s["time"] == "20:30" and s["keep_monthly"] == 12
    assert "bogus" not in s
    sp.write_text("{not json")
    assert nb.load_settings() == nb.DEFAULTS


def test_computer_name_sanitised(monkeypatch):
    monkeypatch.setenv("COMPUTERNAME", "My PC.local!")
    assert nb.computer_name() == "My_PC_local_"


def test_fix3_future_stamp_red(env):
    _stamp(env, last_ok="2026-11-25T10:00:00")
    assert nb.status_text(NOW) == ("Backup date is in the future -- check the computer clock", "red")
    _stamp(env, last_ok="2026-11-20T10:00:00")                       # under a day ahead: fine
    assert nb.status_text(NOW)[1] == "ok"
    _stamp(env, warning="not pruned: x")
    assert nb.status_text(NOW) == ("not pruned: x", "red")


def test_fix6_status_names_other_computer(env):
    _stamp(env, computer="OTHER-PC")
    assert nb.status_text(NOW)[0].endswith("(on OTHER-PC)")
    _stamp(env)
    assert "(on" not in nb.status_text(NOW)[0]


def test_fix7_no_backup_since_setup_red(env):
    sp = nb.settings_path()
    sp.parent.mkdir(parents=True)
    sp.write_text(json.dumps({"set_up_at": "2026-11-10T10:00:00"}))
    assert nb.status_text(NOW) == ("No backup made since setup -- check the backup drive and log", "red")
    sp.write_text(json.dumps({"set_up_at": "2026-11-18T10:00:00"}))
    assert nb.status_text(NOW) == ("Backups: set up, none made yet", "grey")


def test_fix8_real_get_password_logs_keyring_exception(tmp_path, monkeypatch):
    import keyring
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(keyring, "get_password", lambda *a: (_ for _ in ()).throw(RuntimeError("vault locked")))
    assert nb.get_password() is None
    assert "keyring error: RuntimeError: vault locked" in (tmp_path / "BiologicalSoftware" / "backup_log.txt").read_text()


def test_fix12_time_validated(env):
    sp = nb.settings_path()
    sp.parent.mkdir(parents=True)
    for bad in ("7:00", "25:00", "19:60", "19.00", 1900):
        sp.write_text(json.dumps({"time": bad}))
        assert nb.load_settings()["time"] == "19:00", bad
    sp.write_text(json.dumps({"time": "06:45"}))
    assert nb.load_settings()["time"] == "06:45"


def test_fix13_drive_filter_and_scan(tmp_path, monkeypatch):
    types = {"A:\\": 2, "D:\\": 2, "E:\\": 4, "F:\\": 5}
    mask = sum(1 << (ord(k[0]) - 65) for k in types)
    assert bs._filter_drive_roots(mask, types.get) == ["A:\\", "D:\\"]
    folder = nb.DEFAULTS["folder_name"]
    (tmp_path / folder).mkdir()
    (tmp_path / folder / nb.MARKER_NAME).write_text("{}")
    monkeypatch.setattr(bs, "_drive_roots", lambda: [str(tmp_path / "nothere"), str(tmp_path)])
    assert bs.find_backup_drive() == str(tmp_path)
    monkeypatch.setattr(bs, "_drive_roots", lambda: [])
    assert bs.find_backup_drive() is None


def test_fix17_status_dates_and_days(env):
    _stamp(env, last_ok="2026-11-05T09:05:00")
    assert nb.status_text(datetime(2026, 11, 6, 8, 0))[0] == "Last backed up: Thu 5 Nov, 09:05"
    text, level = nb.status_text(datetime(2026, 11, 9, 1, 0))          # 4 calendar days
    assert (text, level) == ("Last backed up 4 days ago -- check the backup drive", "red")
    assert nb.status_text(datetime(2026, 11, 8, 23, 59))[1] == "ok"    # 3 calendar days
    sp = nb.settings_path()
    sp.parent.mkdir(parents=True)
    sp.write_text(json.dumps({"stale_days": 1}))
    _stamp(env, last_ok="2026-11-05T23:00:00")
    assert nb.status_text(datetime(2026, 11, 6, 22, 0))[1] == "ok"
    assert nb.status_text(datetime(2026, 11, 7, 1, 0)) == (
        "Last backed up 2 days ago -- check the backup drive", "red")
    assert bs._days(1) == "1 day"


def test_fix19_atrium_label_refreshed_once_a_minute(monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from Atrium import atrium_ui
    calls = []
    monkeypatch.setattr(nb, "status_text", lambda now=None: calls.append(1) or ("hello", "red"))
    panel = atrium_ui.AtriumPanel()
    panel._backup_checked = None
    panel._refresh_backup_label()
    panel._refresh_backup_label()
    panel._refresh_backup_label()
    assert len(calls) == 1 and panel.backup_label.text() == "hello"
    panel._backup_checked -= 61
    panel._refresh_backup_label()
    assert len(calls) == 2
