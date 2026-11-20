"""Shared helpers for the nightly-backup tests: small databases, a fake drive, patched names."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pyzipper
import pytest

import paths
from shared import backup_settings as bs
from shared import nightly_backup as nb

REPO = Path(__file__).resolve().parent.parent
PW = "correct horse"
NOW = datetime(2026, 11, 19, 19, 2, 0)


def _db(path, value="x"):
    c = sqlite3.connect(str(path))
    c.execute("CREATE TABLE t (v TEXT)")
    c.execute("INSERT INTO t VALUES (?)", (value,))
    c.commit()
    c.close()


@pytest.fixture(name="env")
def _env_fixture(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for n in ("observatum", "munia", "examen", "gamification", "lector", "codex", "uksi", "pantheon"):
        _db(data / f"{n}.db", n)
    (data / "saved_filters.json").write_text("{}")
    drive = tmp_path / "drive"
    (drive / nb.DEFAULTS["folder_name"]).mkdir(parents=True)
    (drive / nb.DEFAULTS["folder_name"] / nb.MARKER_NAME).write_text("{}")
    local = tmp_path / "local"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("COMPUTERNAME", "PC-1")
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(nb, "find_backup_drive", lambda folder_name=None: str(drive))
    monkeypatch.setattr(nb, "away_active", lambda: False)          # looked up by run()
    monkeypatch.setattr(bs, "away_active", lambda: False)          # looked up by status_text()
    keys = {"pw": PW}
    monkeypatch.setattr(nb, "get_password", lambda: keys.get("pw"))
    base = drive / nb.DEFAULTS["folder_name"] / "PC-1"
    return type("E", (), {"data": data, "drive": drive, "base": base, "local": local, "keys": keys})


def _members(zpath, pw=PW):
    with pyzipper.AESZipFile(str(zpath)) as zf:
        zf.setpassword(pw.encode())
        return {i.filename for i in zf.infolist()}


def _stamp(env, **kw):
    d = {"last_ok": "2026-11-19T19:02:00", "computer": "PC-1"}
    d.update(kw)
    (env.data / "backup_status.json").write_text(json.dumps(d))
