"""Database path resolution for standalone or suite use.

Priority:
1. Environment variables (BIOSOFT_DATA_DIR, CODEX_DB, etc.)
2. import paths (suite mode ? paths.py at project root)
3. Auto-discovery (look for data/ relative to script location)
"""
import os
from pathlib import Path

_cache = {}

def _find_data_dir():
    # 1. Environment variable
    env = os.environ.get('BIOSOFT_DATA_DIR')
    if env and Path(env).is_dir():
        return Path(env)
    
    # 2. Try import paths (suite mode)
    try:
        import paths
        return paths.DATA_DIR
    except ImportError:
        pass
    
    # 3. Auto-discover: walk up from this file looking for data/
    check = Path(__file__).resolve().parent
    for _ in range(5):
        candidate = check / 'data'
        if candidate.is_dir() and (candidate / 'uksi.db').exists():
            return candidate
        check = check.parent
    
    raise FileNotFoundError("Cannot find data directory. Set BIOSOFT_DATA_DIR or run from suite root.")

def data_dir() -> Path:
    if 'data_dir' not in _cache:
        _cache['data_dir'] = _find_data_dir()
    return _cache['data_dir']

def db_path(name: str) -> Path:
    """Resolve a database path. Checks env var first, then data_dir()."""
    env_key = name.upper().replace('.', '_')
    env = os.environ.get(env_key)
    if env and Path(env).exists():
        return Path(env)
    return data_dir() / name

# Convenience constants (lazy ? resolved on first access)
class _DBPaths:
    @property
    def OBSERVATUM_DB(self): return db_path('observatum.db')
    @property
    def UKSI_DB(self): return db_path('uksi.db')
    @property
    def CODEX_DB(self): return db_path('codex.db')
    @property
    def PANTHEON_DB(self): return db_path('pantheon.db')
    @property
    def VC_LOOKUP_DB(self): return db_path('vc_lookup.db')
    @property
    def EXAMEN_DB(self): return db_path('examen.db')
    @property
    def GAMIFICATION_DB(self): return db_path('gamification.db')
    @property
    def MUNIA_DB(self): return db_path('munia.db')

db = _DBPaths()
