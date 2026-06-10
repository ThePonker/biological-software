# ==========================================================
# PERMANENT FILE - DO NOT DELETE
# Every project in Biological Software depends on this file.
# Deleting it will break Observatum, Examen, Curator, etc.
# ==========================================================

from pathlib import Path
import os


def _resolve_root():
    candidate = Path(__file__).resolve().parent
    if (candidate / 'data').is_dir():
        return candidate
    env_root = os.environ.get('BIOSOFT_ROOT')
    if env_root:
        p = Path(env_root)
        if (p / 'data').is_dir():
            return p
    home = Path.home()
    for name in ['Biological Software', 'Biological_Software']:
        for base in [home / 'OneDrive', home / 'Documents', home]:
            p = base / name
            if (p / 'data').is_dir():
                return p
    raise FileNotFoundError('Cannot find Biological Software root.')


ROOT = _resolve_root()
DATA_DIR        = ROOT / 'data'
MAPS_DIR        = DATA_DIR / 'maps'
OBSERVATUM_DB   = DATA_DIR / 'observatum.db'
UKSI_DB         = DATA_DIR / 'uksi.db'
PANTHEON_DB     = DATA_DIR / 'pantheon.db'
CODEX_DB        = DATA_DIR / 'codex.db'
VC_LOOKUP_DB    = DATA_DIR / 'vc_lookup.db'
EXAMEN_DB       = DATA_DIR / 'examen.db'
GAMIFICATION_DB = DATA_DIR / 'gamification.db'
VC_GEOJSON      = MAPS_DIR / 'vc_brc_wgs84.geojson'
SAVED_FILTERS   = DATA_DIR / 'saved_filters.json'
JNCC_DIR        = DATA_DIR / 'conservation-designations-20231206'
OBSERVATUM_DIR  = ROOT / 'Observatum'
EXAMEN_DIR      = ROOT / 'Examen'
CURATOR_DIR     = ROOT / 'Curator'
TABELLA_DIR     = ROOT / 'Tabella'
MUNIA_DIR       = ROOT / 'Munia'
SCRIPTS_DIR     = ROOT / 'scripts'
LAUNCHERS_DIR   = ROOT / 'launchers'
DOCS_DIR        = ROOT / 'docs'


def db_path(filename):
    return DATA_DIR / filename
