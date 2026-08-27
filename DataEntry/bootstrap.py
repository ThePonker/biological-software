"""Bootstrap for DataEntry standalone mode.

Points Observatum's get_database() singleton at the chosen databases (a dev COPY of
observatum.db + the real uksi.db). Once set, everything downstream -- species search,
recorded-species boost, and the write path via ObservationModel(get_database()) -- uses
those, so a standalone run never touches the live database.

All Observatum imports are lazy and guarded: if src isn't importable (PYTHONPATH not set),
callers get a clear reason string instead of a crash.
"""
from __future__ import annotations

import glob
import os
from typing import Optional, Tuple


def resolve_suite_paths() -> Tuple[str, str, str]:
    """Return (data_dir, uksi_db, live_main_db) from paths.py, or a ./data fallback."""
    try:
        import paths
        return str(paths.DATA_DIR), str(paths.UKSI_DB), str(paths.OBSERVATUM_DB)
    except Exception:
        d = os.path.join(os.getcwd(), "data")
        return d, os.path.join(d, "uksi.db"), os.path.join(d, "observatum.db")


def newest_dev_db(data_dir: str) -> Optional[str]:
    """Newest data/observatum_dev_*.db (timestamped names sort chronologically)."""
    dev = sorted(glob.glob(os.path.join(data_dir, "observatum_dev_*.db")))
    return dev[-1] if dev else None


def init_databases(main_db: str, uksi_db: str):
    """Point the Observatum get_database() singleton at (main_db, uksi_db).

    Returns (db, error). db is the DatabaseManager on success; error is a reason string on
    failure (Observatum not importable, or a path missing).
    """
    try:
        from src.models.database import get_database
    except Exception as e:
        return None, f"Observatum src not importable ({e}). Check PYTHONPATH."
    db = get_database()
    try:
        db.set_paths(main_db=main_db, uksi_db=uksi_db)
    except FileNotFoundError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Could not set database paths: {e}"
    return db, None


def get_search_service_safe():
    """Return Observatum's SearchService singleton, or None if unavailable."""
    try:
        from src.services.search_service import get_search_service
        return get_search_service()
    except Exception as e:
        print(f"[DataEntry] search service unavailable: {e}")
        return None


def make_observation_model(db):
    """Return an ObservationModel bound to the given DatabaseManager, or None."""
    try:
        from src.models.observation import ObservationModel
        return ObservationModel(db)
    except Exception as e:
        print(f"[DataEntry] ObservationModel unavailable: {e}")
        return None


def get_database_safe():
    """Return the Observatum get_database() singleton, or None if src isn't importable."""
    try:
        from src.models.database import get_database
        return get_database()
    except Exception as e:
        print(f"[DataEntry] database unavailable: {e}")
        return None


def get_vc_service_safe():
    """Return Observatum's VCLookupService singleton, or None if unavailable.

    Tries the service's own path resolution first, then falls back to the path from paths.py.
    """
    try:
        from src.services.vc_lookup_service import get_vc_service
    except Exception as e:
        print(f"[DataEntry] VC lookup service unavailable: {e}")
        return None
    try:
        return get_vc_service()
    except Exception:
        try:
            import paths
            return get_vc_service(str(paths.VC_LOOKUP_DB))
        except Exception as e:
            print(f"[DataEntry] VC lookup service could not open its DB: {e}")
            return None
