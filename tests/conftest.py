"""pytest set-up for the suite's tests (backlog I6).

Puts the project root on sys.path (paths, shared, DataEntry, Examen, Observatum.src...)
and Observatum on it as well, for the modules that import `src.` themselves.
Tests here touch no database: they exercise pure functions only.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)


import pytest  # noqa: E402


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
