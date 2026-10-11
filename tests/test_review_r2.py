"""Independent review of the merged round 2 (10 Oct 2026): regressions found after the merge.

1. Mapping: a specimen whose observation is under an active embargo is held back with it, even
   when the species-counting switches leave that observation out (e.g. an "agg." record).
   After the merge the embargo test only looked at counted observations, so such a specimen
   was mapped on its own under Insect Collection / All records.
2. Species lookup: the phenology month dialog lists the records its bar counts (switches).
"""
import datetime as dt
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

needs_data = pytest.mark.skipif(not (paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()),
                                reason="needs data/observatum.db and uksi.db")


@pytest.fixture
def settings():
    """Isolated QSettings with the default switches; the counting caches reset after."""
    from PySide6.QtCore import QCoreApplication, QSettings
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import shared.species_counting as sc
    org, app = QCoreApplication.organizationName(), QCoreApplication.applicationName()
    QCoreApplication.setOrganizationName("ObservatumTests")
    QCoreApplication.setApplicationName("review_r2")
    QSettings().clear()
    sc.invalidate()
    yield sc
    QSettings().clear()
    sc.invalidate()
    QCoreApplication.setOrganizationName(org)
    QCoreApplication.setApplicationName(app)


@needs_data
def test_specimen_of_embargoed_excluded_observation_held_back(settings, tmp_path):
    sc = settings
    dst = str(tmp_path / "observatum.db")
    src = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    src.backup(out)
    src.close()
    today = dt.date.today().isoformat()
    excluded = sc.excluded_ids(dst, "observations")
    emb = [r for r in out.execute(
        "SELECT id, species_name, species_tvk, date, grid_ref FROM observations "
        "WHERE COALESCE(embargo_status,'')='Active' AND COALESCE(embargo_until,'') > ? "
        "AND COALESCE(grid_ref,'') <> ''", (today,)) if r[0] in excluded]
    if not emb:
        pytest.skip("no embargoed observation the switches leave out")
    oid, name, tvk, date, gr = emb[0]
    out.execute("INSERT INTO specimens (species_name, species_tvk, date_collected, grid_ref, "
                "observation_id) VALUES (?, ?, ?, ?, ?)", (name, tvk, date, gr, oid))
    sid = out.execute("SELECT last_insert_rowid()").fetchone()[0]
    out.commit()
    out.close()
    from src.services import map_selection as ms
    for source in ("collection", "all", ["personal", "commercial", "collection"]):
        res = ms.fetch([], source, ms.MapFilters(), db_path=dst)
        assert not any(r["table"] == "specimens" and r["id"] == sid for r in res.records), source
    with_emb = ms.fetch([], "collection", ms.MapFilters(include_embargoed=True), db_path=dst)
    assert any(r["table"] == "specimens" and r["id"] == sid for r in with_emb.records)


@needs_data
def test_phenology_month_dialog_lists_what_the_bar_counts(settings):
    """2. Species lookup: clicking a phenology month lists the records the bar counts. The
    bar follows the counting switches; the dialog did not (Leiopus, default switches: June
    and July bars 3 records short of their dialogs; with scheme agg/genus left out, 225 vs
    2,089)."""
    sc = settings
    from src.models.database import get_database
    from src.views.stats.month_records_dialog import month_records
    from src.views.stats.species_dashboard import SpeciesDashboard
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(str(paths.OBSERVATUM_DB))
    db.set_uksi_path(str(paths.UKSI_DB))
    try:
        d = SpeciesDashboard.__new__(SpeciesDashboard)
        d._db = db
        for scheme_kinds in ((), ("agg", "genus")):
            sc.set_excluded("recording_scheme", scheme_kinds)
            bars = d._get_phenology_data("Leiopus")
            got = [len(month_records(db.execute_main, d._by_species, "Leiopus", m, d._counted))
                   for m in range(1, 13)]
            assert got == bars, scheme_kinds
    finally:
        db._main_db_path, db._uksi_db_path = old
