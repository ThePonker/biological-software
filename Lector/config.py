"""Lector configuration: paths, API settings, API-key loading.

Single source for Lector constants. Paths come from the suite's paths.py;
add LECTOR_DB to paths.py later if you want it registered centrally - the
getattr fallback means nothing here needs to change when you do.
"""
import os
import sys
import types
from pathlib import Path

ROOT_FILE = Path(__file__).with_name("biosoft_root.txt")   # optional override
DATA_DIR_ENV = "LECTOR_DATA_DIR"        # standalone install: use this data folder instead


def frozen():
    """True in the free-standing install (a PyInstaller build, packaging/lector)."""
    return bool(getattr(sys, "frozen", False))


def documents_dir():
    """The user's Documents folder (Windows: asks the shell, so a OneDrive-redirected
    Documents is found; elsewhere ~/Documents)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.c_wchar_p()
            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            guid = (ctypes.c_ubyte * 16)(*bytes.fromhex("d09ad3fd8f23af46adb46c85480369c7"))
            if ctypes.windll.shell32.SHGetKnownFolderPath(
                    ctypes.byref(guid), 0, wintypes.HANDLE(0), ctypes.byref(buf)) == 0:
                return Path(buf.value)
        except Exception:  # noqa: BLE001 - fall back to the plain folder
            pass
    return Path.home() / "Documents"


def standalone_data_dir():
    """Where the free-standing install keeps its data: Documents\\Lector\\data (or the
    folder in the LECTOR_DATA_DIR environment variable)."""
    env = os.environ.get(DATA_DIR_ENV, "").strip()
    return Path(env) if env else documents_dir() / "Lector" / "data"


def _inside_suite():
    """The Biological Software folder (with paths.py) that holds the running program, or
    None. A frozen build looks upward from its own folder only."""
    here = Path(sys.executable).resolve().parent
    for base in (here, *here.parents):
        if (base / "paths.py").exists():
            return base
    return None


def _standalone_paths():
    """Stand-in for the suite's paths.py when Lector runs on its own: data in the user's
    folder, no uksi.db (names are then searched as typed), never an away machine."""
    data = standalone_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    mod = types.ModuleType("paths")
    mod.ROOT = data.parent
    mod.DATA_DIR = data
    mod.UKSI_DB = data / "uksi.db"
    mod.LECTOR_DB = data / "lector.db"
    mod.SCRIPTS_DIR = Path(getattr(sys, "_MEIPASS", data.parent)) / "scripts"
    mod.AWAY_MODE = False
    mod.STANDALONE = True
    sys.modules["paths"] = mod
    return mod


def _import_paths():
    """Import the suite's paths.py, wherever Lector itself is sitting.

    Order: already importable -> BIOSOFT_ROOT env var -> Lector/biosoft_root.txt
    -> folder above Lector -> common Biological Software locations.
    """
    if frozen():
        # the install: the suite is used only when the program sits inside it
        suite = _inside_suite()
        if suite is None:
            return _standalone_paths()
        sys.path.insert(0, str(suite))
    try:
        import paths
        return paths
    except ImportError:
        pass
    home = Path.home()
    candidates = [os.environ.get("BIOSOFT_ROOT", "")]
    if ROOT_FILE.exists():
        candidates.append(ROOT_FILE.read_text(encoding="utf-8-sig").strip())
    candidates.append(str(Path(__file__).resolve().parent.parent))
    for base in (home / "OneDrive", home / "OneDrive" / "Documents",
                 home / "Documents", home / "Desktop", home):
        candidates.append(str(base / "Biological Software"))
    for c in candidates:
        if c and (Path(c) / "paths.py").exists():
            sys.path.insert(0, str(Path(c)))
            import paths
            return paths
    raise SystemExit(
        "✗ Could not find the Biological Software folder (the one with paths.py).\n"
        f"  Put its full path, on one line, in:\n    {ROOT_FILE}\n"
        "  or set the BIOSOFT_ROOT environment variable.")


paths = _import_paths()

# --- Paths ------------------------------------------------------------------
DATA_DIR = Path(paths.DATA_DIR)
LECTOR_DB = Path(getattr(paths, "LECTOR_DB", DATA_DIR / "lector.db"))
UKSI_DB = Path(paths.UKSI_DB)
KEY_FILE = DATA_DIR / "bhl_api_key.txt"          # data/ is git-ignored
EXPORT_DIR = DATA_DIR / "lector_exports"
SYNONYM_FILE = DATA_DIR / "lector_synonyms.txt"   # your synonym corrections (synonyms.py)
BACKUP_DIR = DATA_DIR / "_backups"                # copy taken before lector.db is updated

# --- BHL API ----------------------------------------------------------------
API_BASE = "https://www.biodiversitylibrary.org/api3"
API_KEY_URL = "https://www.biodiversitylibrary.org/getapikey.aspx"
API_KEY_ENV = "BHL_API_KEY"
USER_AGENT = "Lector/0.1 (Biological Software suite; biodiversity research)"

REQUEST_INTERVAL = 1.0     # seconds between requests - be polite to BHL
REQUEST_TIMEOUT = 60       # seconds
MAX_RETRIES = 4            # per request, with exponential backoff
RETRY_STATUS = (429, 500, 502, 503, 504)

# --- Harvest defaults -------------------------------------------------------
DEFAULT_MAX_PAGES = 500    # per searched name; guards against huge hit lists

# The desktop window's title (Lector/ui/app.py); Atrium finds the open window by it
GUI_TITLE = "Lector — Biodiversity Heritage Library"


def load_api_key(cli_key=None):
    """Return the BHL API key: --key, then env var, then data/bhl_api_key.txt."""
    key = (cli_key or os.environ.get(API_KEY_ENV, "")).strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8-sig").strip()
    if not key:
        raise SystemExit(
            "✗ No BHL API key found.\n"
            f"  Get a free key at {API_KEY_URL}\n"
            f"  then save it (key only, one line) to:\n    {KEY_FILE}\n"
            f"  or set the {API_KEY_ENV} environment variable, or pass --key."
        )
    return key
