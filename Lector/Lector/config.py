"""Lector configuration: paths, API settings, API-key loading.

Single source for Lector constants. Paths come from the suite's paths.py;
add LECTOR_DB to paths.py later if you want it registered centrally - the
getattr fallback means nothing here needs to change when you do.
"""
import os
import sys
from pathlib import Path

ROOT_FILE = Path(__file__).with_name("biosoft_root.txt")   # optional override


def _import_paths():
    """Import the suite's paths.py, wherever Lector itself is sitting.

    Order: already importable -> BIOSOFT_ROOT env var -> Lector/biosoft_root.txt
    -> folder above Lector -> common Biological Software locations.
    """
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
