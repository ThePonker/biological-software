"""pytest set-up for the suite's tests (backlog I6; sandbox added Round 12, 24 Oct 2026).

Puts the project root on sys.path (paths, shared, DataEntry, Examen, Observatum.src...)
and Observatum on it as well, for the modules that import `src.` themselves.

Sandbox: before any test module imports app code, every worker gets its own temp folder
holding HOME, USERPROFILE, APPDATA, LOCALAPPDATA, the Qt settings store (INI files, so
QSettings never touches the Windows registry) and the photo library (BIOSOFT_MEDIA_ROOT),
so a test run cannot change Wil's real settings, home folder or photo library. A guard
fails any test that opens the live observatum.db read-write. Timing tests (marked `speed`)
only run with BIOSOFT_SPEED_TESTS=1. Tests that read Wil's live data work on copies.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Closing a main window must not start the away-copy process (shared/away_mode.py)
os.environ.setdefault("BIOSOFT_NO_AWAY_COPY", "1")

# Offscreen Qt on Windows finds no fonts, so every font measurement was wrong unless an
# earlier test had happened to start Qt the normal way (13 Oct 2026; docs/05_Rules.md
# "Measure on Wil's PC"). Point it at the Windows fonts before any test starts Qt.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR",
                          os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))

# --- per-worker sandbox (must run before anything imports paths or creates QSettings) ---
SANDBOX = tempfile.mkdtemp(prefix="flauna_pytest_" + os.environ.get("PYTEST_XDIST_WORKER", "main") + "_")
_HOME = os.path.join(SANDBOX, "home")
_APPDATA = os.path.join(SANDBOX, "appdata")
_LOCALAPPDATA = os.path.join(SANDBOX, "localappdata")
_QT = os.path.join(SANDBOX, "qtsettings")
for _d in (_HOME, _APPDATA, _LOCALAPPDATA, _QT):
    os.makedirs(_d, exist_ok=True)
for _k, _v in (("HOME", _HOME), ("USERPROFILE", _HOME), ("APPDATA", _APPDATA),
               ("LOCALAPPDATA", _LOCALAPPDATA)):
    os.environ[_k] = _v
os.environ["BIOSOFT_MEDIA_ROOT"] = os.path.join(SANDBOX, "media")   # always: never the real library
os.makedirs(os.environ["BIOSOFT_MEDIA_ROOT"], exist_ok=True)

from PySide6.QtCore import QSettings  # noqa: E402

QSettings.setDefaultFormat(QSettings.Format.IniFormat)
for _scope in (QSettings.Scope.UserScope, QSettings.Scope.SystemScope):
    QSettings.setPath(QSettings.Format.IniFormat, _scope, _QT)

import pytest  # noqa: E402

# The live observatum.db (the one under the real data folder), resolved now, before any
# test patches paths.
LIVE_OBSERVATUM_DB = None
try:
    import paths as _paths  # noqa: E402
    LIVE_OBSERVATUM_DB = os.path.normcase(os.path.realpath(str(_paths.OBSERVATUM_DB)))
except Exception:
    pass

_live_opens = []
_real_connect = None


def _live_rw_open(database, kwargs_uri):
    """True if `database` names the live observatum.db and is not opened read-only."""
    if LIVE_OBSERVATUM_DB is None:
        return False
    try:
        text = os.fspath(database)
    except TypeError:
        return False
    if isinstance(text, bytes):
        return False
    if kwargs_uri and text.startswith("file:"):
        from urllib.parse import unquote, urlsplit
        parts = urlsplit(text)
        path = unquote(parts.path)
        if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        if "mode=ro" in parts.query:
            return False
    else:
        path = text
    try:
        return os.path.normcase(os.path.realpath(path)) == LIVE_OBSERVATUM_DB
    except (OSError, ValueError):
        return False


def _install_connect_guard():
    global _real_connect
    import sqlite3
    if _real_connect is not None:
        return
    _real_connect = sqlite3.connect

    def guarded(database, *args, **kwargs):
        uri = kwargs.get("uri", args[6] if len(args) > 6 else False)
        if _live_rw_open(database, uri):
            _live_opens.append(str(database))
            raise AssertionError(f"test opened the live observatum.db read-write: {database}")
        return _real_connect(database, *args, **kwargs)

    sqlite3.connect = guarded


_install_connect_guard()


def pytest_configure(config):
    # One file's tests stay on one worker (shared QSettings names, fixtures imported from
    # other test files). Done here, not in addopts, so plain `pytest tests` without xdist works.
    opt = config.option
    if config.pluginmanager.hasplugin("xdist") and getattr(opt, "numprocesses", None) \
            and getattr(opt, "dist", "no") in ("no", "load"):
        opt.dist = "loadfile"


def pytest_collection_modifyitems(config, items):
    if os.environ.get("BIOSOFT_SPEED_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="timing test: set BIOSOFT_SPEED_TESTS=1 to run")
    for item in items:
        if "speed" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _live_observatum_never_opened_read_write():
    """Fails a test that opened the live observatum.db without mode=ro (Round 12)."""
    _live_opens.clear()
    yield
    assert not _live_opens, f"opened the live observatum.db read-write: {_live_opens}"


@pytest.fixture(scope="session")
def live_copy(tmp_path_factory):
    """A private copy of the live observatum.db (made with the backup API from a read-only
    connection). Tests that need Wil's real data open this, never paths.OBSERVATUM_DB
    read-write. Skips when there is no live database."""
    import sqlite3
    if LIVE_OBSERVATUM_DB is None or not os.path.exists(LIVE_OBSERVATUM_DB):
        pytest.skip("real data copies not present")
    dest = tmp_path_factory.mktemp("livecopy") / "observatum.db"
    src = sqlite3.connect(f"file:{LIVE_OBSERVATUM_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return dest


@pytest.fixture(autouse=True, scope="session")
def _backups_never_leave_the_test_folder(tmp_path_factory):
    """Safety net (review R4, 11 Oct 2026): a test that reaches a backup -- the database
    backup on closing the main window, Data Entry's rolling CSVs -- writes into the test
    folder, never C:\\BiologicalSoftware_Backups (on Wil's PC that would overwrite his real
    staging_backup.csv; on Linux it made a folder literally named 'C:\\Biological...').
    Tests that patch these themselves still do."""
    folder = str(tmp_path_factory.mktemp("backups"))
    os.environ["BIOSOFT_BACKUP_ROOT"] = folder
    try:
        import shared.backup_service as bs
        bs.BACKUP_ROOT = folder
    except Exception:
        pass
    try:
        import DataEntry.csv_backup as cb
        cb.BACKUP_DIR = folder
    except Exception:
        pass
    yield folder


@pytest.fixture(autouse=True)
def _application_font_restored():
    """Each test leaves the application font as it found it (13 Oct 2026). Run in parallel
    (pytest -n 6), tests share each worker's QApplication in a different order, and a main
    window applying the saved font size -- or a test's wide font -- carried into the next
    layout test (1280 px fits failed). No QApplication yet: nothing to do."""
    app = None
    if "PySide6.QtWidgets" in sys.modules:
        app = sys.modules["PySide6.QtWidgets"].QApplication.instance()
    font = None
    if app is not None:
        from PySide6.QtGui import QFont
        font = QFont(app.font())
    yield
    if font is not None:
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is app and QApplication.font() != font:
            QApplication.setFont(font)

