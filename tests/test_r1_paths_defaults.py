"""Round 1, items 7 and 8: CSV safety-backup folders and the away-copy JNCC folder come from paths."""
import os
import subprocess
import sys
from pathlib import Path

import paths
from tests.test_dataentry_r3 import qapp  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


def test_default_csv_backup_dir_is_in_the_data_folder(monkeypatch, tmp_path):
    from src.core import config
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    assert config.default_csv_backup_dir() == str(tmp_path / "data" / "csv_backups")


def test_general_panel_uses_that_default_but_keeps_a_saved_value(qapp, monkeypatch, tmp_path):  # noqa: F811
    from PySide6.QtCore import QSettings
    from src.core.config import Settings, default_csv_backup_dir
    from src.views.settings.general_panel import GeneralSettingsPanel
    s = QSettings()
    s.remove(Settings.CSV_BACKUP_PATH)
    try:
        assert GeneralSettingsPanel().csv_backup_path.text() == default_csv_backup_dir()
        s.setValue(Settings.CSV_BACKUP_PATH, str(tmp_path / "mine"))
        assert GeneralSettingsPanel().csv_backup_path.text() == str(tmp_path / "mine")
    finally:
        s.remove(Settings.CSV_BACKUP_PATH)


def test_main_window_close_export_reads_the_same_default():
    import inspect
    from src.views import main_window
    src = inspect.getsource(main_window.MainWindow.closeEvent)
    assert "default_csv_backup_dir()" in src and "CSV_BACKUP_PATH" in src


def test_data_entry_csv_backup_dir_follows_backup_root(tmp_path):
    code = ("import DataEntry.csv_backup as cb, shared.backup_service as bs; "
            "print(cb.BACKUP_DIR == bs.BACKUP_ROOT, cb.BACKUP_DIR)")
    env = dict(os.environ, BIOSOFT_BACKUP_ROOT=str(tmp_path / "bk"),
               PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "Observatum")]))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                       cwd=str(tmp_path), timeout=60)
    assert r.stdout.strip() == f"True {tmp_path / 'bk'}", r.stdout + r.stderr


def test_away_static_dirs_use_the_jncc_folder_name():
    from shared import away_mode
    assert paths.JNCC_DIR.name in away_mode.STATIC_DIRS
    assert away_mode.STATIC_DIRS[0] == "maps"
