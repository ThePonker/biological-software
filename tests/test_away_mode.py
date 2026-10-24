"""Away mode (18 Oct 2026): the nightly away copy, the read-only laptop copy, the guards.

Small purpose-made databases in tmp_path; LOCALAPPDATA, the home folder and BIOSOFT_ROOT are
all pointed into it, so nothing here touches real data. On Linux as root, chmod read-only does
not stop a write, so the read-only checks also open the copy with mode=ro.
"""
import json
import os
import sqlite3
import stat
import hashlib
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import paths
from scripts import make_away_copy as mac
from shared import away_mode, backup_service

REPO = Path(__file__).resolve().parent.parent


def _db(path, wal=True, rows=3):
    c = sqlite3.connect(str(path))
    if wal:
        c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, species TEXT)")
    c.executemany("INSERT INTO observations (species) VALUES (?)", [("x",)] * rows)
    c.commit()
    c.close()


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A fake desktop: root/data with databases, a home folder, a LOCALAPPDATA."""
    root = tmp_path / "root"
    data = root / "data"
    (data / "maps" / "layers").mkdir(parents=True)
    (data / "_backups").mkdir()
    for n in away_mode.CHANGING_DBS[:3]:
        _db(data / n)
    for n in ("codex.db", "uksi.db"):
        _db(data / n, wal=False)
    (data / "maps" / "vc.geojson").write_text("{}")
    (data / "maps" / "layers" / "a.json").write_text("[]")
    (data / "saved_filters.json").write_text("{}")
    (data / "old.mdb").write_text("x")
    (data / "observatum_pre_import_1.db").write_text("x")
    (data / "_backups" / "b.db").write_text("x")
    home = tmp_path / "home"
    home.mkdir()
    local = tmp_path / "local"
    local.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(paths, "ROOT", root)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "AWAY_MODE", False)
    return dict(root=root, data=data, home=home, local=local,
                away=home / "OneDrive" / "Observatum away copy")


def _journal(path):
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return c.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        c.close()


# ---- make_away_copy -------------------------------------------------------------------------

def _manifest(world):
    return json.loads((world["away"] / "manifest.json").read_text())


def test_copy_is_delete_mode_checked_and_has_manifest(world, capsys):
    assert mac.main([]) == 0
    away = world["away"]
    assert "done." in capsys.readouterr().out
    m = _manifest(world)
    assert m["slot"] == "A"
    slot = away / "A"
    assert sorted(p.name for p in slot.iterdir()) == [
        "codex.db", "examen.db", "gamification.db", "observatum.db", "uksi.db"]
    assert sorted(p.name for p in away.iterdir()) == ["A", "manifest.json"]
    for p in slot.iterdir():
        assert _journal(p) == "delete"
        assert not list(slot.glob("*-wal")) and not list(slot.glob("*-shm"))
    assert m["observation_rows"] == 3 and m["source_host"]
    for f in m["files"]:
        data = (slot / f["name"]).read_bytes()
        assert f["size"] == len(data) and f["sha256"] == hashlib.sha256(data).hexdigest()
    datetime.fromisoformat(m["made_at"])
    assert _journal(world["data"] / "observatum.db") == "wal"       # source untouched


def test_copy_alternates_slots_and_replaces(world):
    mac.main([])
    c = sqlite3.connect(str(world["data"] / "observatum.db"))
    c.execute("INSERT INTO observations (species) VALUES ('new')")
    c.commit()
    c.close()
    mac.main([])
    m = _manifest(world)
    assert m["slot"] == "B" and m["observation_rows"] == 4
    assert (world["away"] / "A" / "observatum.db").is_file()       # the other slot is left
    mac.main([])
    assert _manifest(world)["slot"] == "A"
    assert not list(world["away"].rglob("*.tmp"))


def test_reference_databases_copied_only_when_changed(world, capsys):
    mac.main([])
    first = {f["name"]: f["sha256"] for f in _manifest(world)["files"]}
    capsys.readouterr()
    mac.main([])
    out = capsys.readouterr().out
    assert "codex.db unchanged" in out and "Copying observatum.db" in out
    assert {f["name"]: f["sha256"] for f in _manifest(world)["files"]}["codex.db"] == first["codex.db"]
    assert (world["away"] / "B" / "codex.db").is_file()             # the full set is in each slot
    c = sqlite3.connect(str(world["data"] / "codex.db"))
    c.execute("INSERT INTO observations (species) VALUES ('changed')")
    c.commit()
    c.close()
    capsys.readouterr()
    mac.main([])
    assert "Copying codex.db" in capsys.readouterr().out


def test_lock_blocks_a_second_run_and_free_or_stale_is_taken(world, capsys):
    work = mac.default_work_dir()
    work.mkdir(parents=True)
    (work / "lock").write_text("123 running")
    assert mac.main([]) == 0
    assert "another copy is running" in capsys.readouterr().out
    assert not world["away"].exists()
    old = (work / "lock").stat().st_mtime - 3 * 3600
    os.utime(work / "lock", (old, old))                             # stale: taken over
    assert mac.main([]) == 0 and world["away"].exists()
    assert (work / "lock").read_text() == "free"                    # released, not deleted
    assert mac.main([]) == 0                                        # 'free' counts as unlocked


def test_if_older_than_skips_a_young_copy_and_remakes_an_old_one(world, capsys):
    mac.main([])
    before = (world["away"] / "manifest.json").read_text()
    capsys.readouterr()
    assert mac.main(["--if-older-than", "20"]) == 0
    assert "nothing to do" in capsys.readouterr().out
    assert (world["away"] / "manifest.json").read_text() == before
    m = json.loads(before)
    m["made_at"] = (datetime.now().astimezone() - timedelta(hours=30)).isoformat(timespec="seconds")
    (world["away"] / "manifest.json").write_text(json.dumps(m))
    assert mac.main(["--if-older-than", "20"]) == 0
    assert (world["away"] / "manifest.json").read_text() != json.dumps(m)


def test_dry_run_writes_nothing(world, capsys):
    assert mac.main(["--dry-run"]) == 0
    assert not world["away"].exists()
    assert "Nothing has been changed" in capsys.readouterr().out


def test_refuses_in_away_mode_and_off_the_live_folder(world, tmp_path, capsys):
    other = tmp_path / "elsewhere"
    other.mkdir()
    paths.DATA_DIR = other                       # restored by the fixture's monkeypatch
    assert mac.main([]) == 1
    assert "not the live data folder" in capsys.readouterr().out
    paths.DATA_DIR = world["data"]
    marker = away_mode.marker_path()
    marker.parent.mkdir(parents=True)
    marker.write_text("{}")
    assert mac.main([]) == 1
    assert "away machine" in capsys.readouterr().out
    assert not world["away"].exists()


def test_task_command_is_printed_not_run(world, capsys):
    assert mac.main(["--show-task-command"]) == 0
    out = capsys.readouterr().out
    assert "Register-ScheduledTask" in out and "Observatum away copy" in out
    assert "-StartWhenAvailable" in out and "--if-older-than 20" in out and "2:00AM" in out


# ---- paths in away mode ---------------------------------------------------------------------

def test_paths_in_away_mode_never_point_at_root_data(tmp_path):
    root = tmp_path / "root"
    (root / "data").mkdir(parents=True)
    local = tmp_path / "local"
    (local / "Flauna").mkdir(parents=True)
    (local / "Flauna" / "away_machine.json").write_text("{}")
    code = ("import paths, json; print(json.dumps(dict(mode=paths.AWAY_MODE, "
            "data=str(paths.DATA_DIR), root=str(paths.ROOT), db=str(paths.OBSERVATUM_DB), "
            "codex=str(paths.CODEX_DB), maps=str(paths.MAPS_DIR), man=str(paths.AWAY_MANIFEST))))")
    env = dict(os.environ, LOCALAPPDATA=str(local), BIOSOFT_ROOT=str(root))
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env,
                         capture_output=True, text=True, check=True).stdout
    r = json.loads(out.strip().splitlines()[-1])
    away_data = local / "Flauna" / "away_data"
    live = Path(r["root"]) / "data"
    assert r["mode"] is True
    assert Path(r["data"]) == away_data and Path(r["data"]) != live
    for k in ("db", "codex", "maps", "man"):
        assert Path(r[k]).is_relative_to(away_data)
    env["LOCALAPPDATA"] = str(tmp_path / "nowhere")          # no marker: unchanged behaviour
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env,
                         capture_output=True, text=True, check=True).stdout
    r = json.loads(out.strip().splitlines()[-1])
    assert r["mode"] is False and Path(r["data"]) == Path(r["root"]) / "data"


# ---- refresh_local_copy ---------------------------------------------------------------------

def _refresh(world):
    mac.main([])
    dest = world["local"] / "Flauna" / "away_data"
    made = away_mode.refresh_local_copy(root=world["root"], away=world["away"], dest=dest)
    return dest, made


def test_refresh_copies_skips_and_verifies(world):
    dest, made = _refresh(world)
    assert made == _manifest(world)["made_at"]
    for n in ("codex.db", "uksi.db", "observatum.db", "examen.db", "gamification.db",
              "saved_filters.json", "manifest.json"):
        assert (dest / n).is_file(), n
    assert (dest / "maps" / "vc.geojson").is_file() and (dest / "maps" / "layers" / "a.json").is_file()
    assert not (dest / "old.mdb").exists()
    assert not (dest / "observatum_pre_import_1.db").exists()
    assert not (dest / "_backups").exists()
    for n in ("codex.db", "observatum.db"):
        assert _journal(dest / n) == "delete"
    assert os.stat(dest / "observatum.db").st_mode & stat.S_IWUSR      # not chmod'd read-only
    assert not list(dest.rglob("*.tmp"))


def test_laptop_never_opens_anything_in_root_data(world, monkeypatch):
    opened = []
    real = sqlite3.connect
    monkeypatch.setattr(sqlite3, "connect",
                        lambda *a, **k: (opened.append(str(a[0])), real(*a, **k))[1])
    mac.main([])
    opened.clear()
    away_mode.refresh_local_copy(root=world["root"], away=world["away"],
                                 dest=world["local"] / "Flauna" / "away_data")
    assert opened and not [o for o in opened if str(world["data"]) in o]


def test_unverified_set_keeps_the_previous_local_copy(world, capsys):
    dest, made1 = _refresh(world)
    c = sqlite3.connect(str(world["data"] / "observatum.db"))
    c.execute("INSERT INTO observations (species) VALUES ('later')")
    c.commit()
    c.close()
    mac.main([])
    m = _manifest(world)
    capsys.readouterr()
    (world["away"] / m["slot"] / "examen.db").write_bytes(b"still syncing")   # half-arrived
    made2 = away_mode.refresh_local_copy(root=world["root"], away=world["away"], dest=dest)
    out = capsys.readouterr().out
    assert "the newest away copy is still arriving; using the copy from" in out
    assert made2 == made1 and away_mode.read_manifest(dest)["made_at"] == made1
    n = sqlite3.connect(f"file:{dest / 'observatum.db'}?mode=ro", uri=True).execute(
        "SELECT COUNT(*) FROM observations").fetchone()[0]
    assert n == 3                                                   # nothing was replaced
    # a bad checksum on a never-copied laptop is an error, not a half copy
    with pytest.raises(RuntimeError):
        away_mode.refresh_local_copy(root=world["root"], away=world["away"],
                                     dest=world["local"] / "fresh")


def test_second_refresh_takes_the_new_copy(world):
    dest, _ = _refresh(world)
    c = sqlite3.connect(str(world["data"] / "observatum.db"))
    c.execute("INSERT INTO observations (species) VALUES ('later')")
    c.commit()
    c.close()
    mac.main([])
    away_mode.refresh_local_copy(root=world["root"], away=world["away"], dest=dest)
    n = sqlite3.connect(f"file:{dest / 'observatum.db'}?mode=ro", uri=True).execute(
        "SELECT COUNT(*) FROM observations").fetchone()[0]
    assert n == 4


def test_database_manager_opens_read_only_in_away_mode(world, monkeypatch):
    from src.models.database import DatabaseManager
    dest, _ = _refresh(world)
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    dm = DatabaseManager()
    dm.set_paths(str(dest / "observatum.db"), str(dest / "uksi.db"))
    assert len(dm.execute_main("SELECT * FROM observations")) == 3
    with dm.main_connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO observations (species) VALUES ('no')")
    assert not list(dest.glob("*-wal")) and not list(dest.glob("*-shm"))


def test_munia_opens_read_only_in_away_mode(world, monkeypatch, tmp_path):
    from Munia import munia_data
    db = tmp_path / "munia.db"
    _db(db, wal=False)
    monkeypatch.setattr(munia_data, "DB_PATH", db)
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    conn = munia_data.get_connection()
    munia_data.ensure_schema(conn)                                  # a no-op: nothing written
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 3
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("INSERT INTO observations (species) VALUES ('no')")
    conn.close()
    assert not list(tmp_path.glob("munia.db-*"))


def test_scripts_that_write_refuse_in_away_mode(world, monkeypatch):
    from scripts import report_common
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    with pytest.raises(RuntimeError, match="away mode"):
        report_common.backup(world["data"] / "observatum.db", "x", backup_dir=str(world["local"]))
    assert not list(world["local"].glob("*pre_x*"))
    for name in ("build_vc_splits", "convert_vc_shapefile", "build_gb_basemap", "load_atlases",
                 "prepare_ne_reviews", "organise_reviews", "build_map_layers"):
        src = (REPO / "scripts" / f"{name}.py").read_text(encoding="utf-8")
        assert f'refuse_if_away("{name}")' in src, name
    with pytest.raises(SystemExit):
        away_mode.refuse_if_away("x")


def test_refresh_refuses_without_an_away_copy_and_the_live_folder(world):
    with pytest.raises(FileNotFoundError):
        away_mode.refresh_local_copy(root=world["root"], away=world["away"],
                                     dest=world["local"] / "x")
    with pytest.raises(RuntimeError):
        away_mode.refresh_local_copy(root=world["root"], away=world["away"],
                                     dest=world["root"] / "data")


def test_setup_script_dry_run_then_apply(world, capsys, monkeypatch):
    from scripts import setup_away_laptop as setup
    assert setup.main([]) == 1                              # no away copy yet
    mac.main([])
    capsys.readouterr()
    assert setup.main(["--apply"]) == 1                     # this is the desktop
    assert "desktop that makes the copies" in capsys.readouterr().out
    assert not away_mode.marker_path().exists()
    def from_desktop():                                     # the copies were made elsewhere
        m = _manifest(world)
        m["source_host"] = "desktop-pc"
        (world["away"] / "manifest.json").write_text(json.dumps(m))
    from_desktop()
    assert setup.main([]) == 0
    assert not away_mode.marker_path().exists()
    m = _manifest(world)
    (world["away"] / m["slot"] / "examen.db").write_bytes(b"x")     # not verified: no marker
    assert setup.main(["--apply"]) == 1
    assert not away_mode.marker_path().exists()
    mac.main([])
    from_desktop()
    assert setup.main(["--apply"]) == 0
    marker = json.loads(away_mode.marker_path().read_text())
    assert marker["machine"] and marker["date"]
    assert (away_mode.local_data_dir() / "observatum.db").is_file()


# ---- guards ---------------------------------------------------------------------------------

def test_backup_service_does_nothing_in_away_mode(world, tmp_path, monkeypatch, capsys):
    root = tmp_path / "bk"
    monkeypatch.setattr(backup_service, "BACKUP_ROOT", str(root))
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    monkeypatch.setattr(paths, "OBSERVATUM_DB", world["data"] / "observatum.db")
    assert backup_service.backup_working("x") is False
    assert backup_service.backup_main_only("pre-x") is False
    assert backup_service.backup_reference() is False
    assert backup_service.write_kept_copy(str(world["data"] / "observatum.db"), "x") is None
    assert not root.exists()
    assert "away mode: no backup made" in capsys.readouterr().out


def test_data_entry_refuses_in_away_mode(world, monkeypatch):
    from DataEntry import embed
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    with pytest.raises(embed.AwayModeError):
        embed.make_data_entry_tab(go_live=True)


def test_background_copy_respects_the_switches(world, monkeypatch):
    started = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: started.append((a, k)))
    (world["root"] / "scripts").mkdir()
    (world["root"] / "scripts" / "make_away_copy.py").write_text("")
    monkeypatch.setenv("BIOSOFT_NO_AWAY_COPY", "1")
    assert away_mode.start_away_copy_in_background() is False and not started
    monkeypatch.delenv("BIOSOFT_NO_AWAY_COPY")
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    assert away_mode.start_away_copy_in_background() is False and not started
    monkeypatch.setattr(paths, "AWAY_MODE", False)
    assert away_mode.start_away_copy_in_background() is True
    cmd = started[0][0][0]
    assert cmd[0] == sys.executable and cmd[-2:] == ["--if-older-than", "20"]
    if sys.platform == "win32":              # detached, no window (24 Oct: was Linux-only)
        assert started[0][1].get("creationflags")
    else:
        assert started[0][1].get("start_new_session") is True


def test_close_event_calls_the_hook_and_conftest_sets_the_switch():
    src = (REPO / "Observatum" / "src" / "views" / "main_window.py").read_text(encoding="utf-8")
    close = src[src.index("def closeEvent"):]
    assert "start_away_copy_in_background()" in close and "AWAY_MODE" in close
    assert os.environ.get("BIOSOFT_NO_AWAY_COPY") == "1"


def test_banner_shown_only_in_away_mode(world, monkeypatch):
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
    from src.views.main_window import MainWindow
    app = QApplication.instance() or QApplication([])      # noqa: F841
    local = away_mode.local_data_dir()
    local.mkdir(parents=True)
    (local / "manifest.json").write_text(json.dumps({"made_at": "2026-10-18T02:00:05+01:00"}))
    monkeypatch.setattr(paths, "AWAY_MANIFEST", local / "manifest.json")

    class Stub:
        pass
    holder = QWidget()
    lay = QVBoxLayout(holder)
    MainWindow._add_away_banner(Stub(), lay)
    assert lay.count() == 0
    monkeypatch.setattr(paths, "AWAY_MODE", True)
    stub = Stub()
    MainWindow._add_away_banner(stub, lay)
    text = lay.itemAt(0).widget().text()
    assert text.startswith("Read-only copy from Sun 18 Oct 2026 02:00.")
    assert "record in a workbook and import at home." in text
