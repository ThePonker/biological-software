"""Round 5 (11 Oct 2026): Home left column -- Quick Stats: All (Personal + Commercial) added
after Commercial, the Achievements card removed from Home.

The All card's figures must equal Stats > All Stats (ObservationStatsService, the same
species-counting switches): checked on a small throwaway database built from the real
schema, and on the data copy (read-only). Offscreen; nothing depends on font metrics.
"""
import os
import sqlite3
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

HAVE_DATA = all(p.exists() for p in (paths.OBSERVATUM_DB, paths.UKSI_DB))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="real data copies not present")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _left_column_widgets(home):
    lay = home.personal_stats.parentWidget().layout()
    return [lay.itemAt(i).widget() for i in range(lay.count()) if lay.itemAt(i).widget()]


def _all_stats_figures():
    """Total Species / Total Records cards and this year's row of All Stats' year table."""
    from src.models.database import get_database
    from src.services.observation_stats_service import get_observation_stats_service
    svc = get_observation_stats_service()
    svc.initialize(get_database())
    svc.refresh()
    s = svc.get_all()
    year = s.get('yearly_stats', {}).get(date.today().year, {'species': 0, 'records': 0})
    return s, {'total_species': s['total_species'], 'total_records': s['total_records'],
               'this_year_species': year['species'], 'this_year_records': year['records']}


@pytest.fixture
def counting_defaults(monkeypatch):
    """The default switches (genus, family+, agg., s.l. left out) whatever is in QSettings."""
    import shared.species_counting as sc
    monkeypatch.setattr(sc, "excluded_kinds",
                        lambda source: frozenset(sc.OFFERED[source]) if source == "observations"
                        else frozenset())


@pytest.fixture
def small_db(tmp_path, qapp, counting_defaults):
    """A throwaway observatum.db (real schema) with a few Personal and Commercial records."""
    if not HAVE_DATA:
        pytest.skip("needs the real schema from data/observatum.db")
    path = tmp_path / "observatum.db"
    src = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(path)
    for t in ("observations", "recording_scheme", "specimens"):
        dst.execute(src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                                (t,)).fetchone()[0])
    src.close()
    today = date.today()
    y = today.year
    lm_y, lm_m = (y - 1, 12) if today.month == 1 else (y, today.month - 1)
    last_month = f"{lm_y}-{lm_m:02d}-15"
    this_year = f"{y}-01-01" if (lm_y, lm_m) != (y, 1) else f"{y}-02-01"   # not last month
    rows = [
        # (record_type, name, tvk, rank, date)
        ("Personal", "Aus bus", "TA", "Species", this_year),
        ("Personal", "Aus bus", "TA", "Species", f"{y - 1}-06-01"),
        ("Personal", "Cus dus", "TB", "Species", f"{y - 2}-06-01"),
        ("Personal", "Carabus", "TG", "Genus", this_year),          # left out (genus)
        ("Commercial", "Aus bus", "TA", "Species", this_year),       # shared with Personal
        ("Commercial", "Eus fus", "TC", "Species", last_month),
        ("Commercial", "Gus hus agg.", "TD", "Species aggregate", this_year),  # left out (agg.)
    ]
    for rt, name, tvk, rank, d in rows:
        dst.execute("INSERT INTO observations (record_type, species_name, species_tvk, "
                    "taxon_rank, date, date_type, grid_ref) VALUES (?,?,?,?,?,'D','SP1234')",
                    (rt, name, tvk, rank, d))
    dst.commit()
    dst.close()
    from src.models.database import get_database
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(str(path))
    db.set_uksi_path(str(paths.UKSI_DB))
    yield db
    db._main_db_path, db._uksi_db_path = old
    from src.services.observation_stats_service import invalidate_observation_stats
    invalidate_observation_stats()


@pytest.fixture
def real_db(qapp, counting_defaults):
    if not HAVE_DATA:
        pytest.skip("real data copies not present")
    from src.models.database import get_database
    db = get_database()
    old = (db._main_db_path, db._uksi_db_path)
    db.set_main_path(str(paths.OBSERVATUM_DB))
    db.set_uksi_path(str(paths.UKSI_DB))
    yield db
    db._main_db_path, db._uksi_db_path = old
    from src.services.observation_stats_service import invalidate_observation_stats
    invalidate_observation_stats()


def test_left_column_order_and_no_achievements(qapp):
    from src.views.home.home_tab import HomeTab
    from src.views.home.observation_stats_card import ObservationStatsCard
    from src.views.home.quick_stats import QuickStatsPanel
    h = HomeTab()
    widgets = _left_column_widgets(h)
    assert [type(w) for w in widgets] == [ObservationStatsCard] * 3 + [QuickStatsPanel]
    assert [w.record_type for w in widgets[:3]] == ["Personal", "Commercial", "All"]
    assert [w.query_record_type for w in widgets[:3]] == ["Personal", "Commercial", None]
    assert widgets[2] is h.all_stats
    assert h.all_stats._header_label.text() == "QUICK STATS: ALL"
    assert [r['label'].text() for r in h.all_stats.rows.values()] == [
        "Total Species", "Total Records", "This Year Species", "This Year Records",
        "Last Month Records"]
    # no Achievements card anywhere on Home
    from src.features.gamification import GamificationLauncher
    assert not h.findChildren(GamificationLauncher)
    assert not hasattr(h, "gamification_card")
    from PySide6.QtWidgets import QLabel, QPushButton
    texts = [w.text() for w in h.findChildren(QLabel) + h.findChildren(QPushButton)]
    assert not any("Achievement" in t or "View Progress" in t or "Tier " in t for t in texts)


def test_all_card_accent_from_theme(qapp):
    from src.themes import theme
    from src.views.home.home_tab import HomeTab
    h = HomeTab()
    accent = theme().get('accent_observation_dark')
    assert all(r['color'] == accent for r in h.all_stats.rows.values())
    h.apply_theme()          # survives a theme refresh
    assert accent in h.all_stats.rows['total_species']['value'].styleSheet()


def test_all_equals_all_stats_small_fixture(small_db):
    from src.repositories import ObservationRepository
    from src.views.home.home_tab import HomeTab
    repo = ObservationRepository()
    per, com, allq = (repo.get_quick_stats(rt) for rt in ("Personal", "Commercial", None))
    # genus and agg. records left out; species distinct across both (Aus bus in both)
    january = date.today().month == 1     # last month is then last year
    assert allq == {'total_species': 3, 'total_records': 5,
                    'this_year_species': 1 if january else 2,
                    'this_year_records': 2 if january else 3,
                    'last_month_records': 1}
    assert per['total_species'] + com['total_species'] == 4 != allq['total_species']
    for k in ('total_records', 'this_year_records', 'last_month_records'):
        assert per[k] + com[k] == allq[k], k
    _, figs = _all_stats_figures()
    for k, v in figs.items():
        assert allq[k] == v, k
    h = HomeTab()
    h.initialize()
    for k, v in allq.items():
        assert h.all_stats.value(k) == f"{v:,}", k
    assert h.personal_stats.value('total_species') == "2"
    assert h.commercial_stats.value('total_species') == "2"


@needs_data
def test_all_equals_all_stats_on_data_copy(real_db):
    from src.repositories import ObservationRepository
    from src.views.home.home_tab import HomeTab
    repo = ObservationRepository()
    per, com, allq = (repo.get_quick_stats(rt) for rt in ("Personal", "Commercial", None))
    s, figs = _all_stats_figures()
    for k, v in figs.items():
        assert allq[k] == v, k
    # the Personal / Commercial cards agree with All Stats' Personal / Commercial figures
    assert (per['total_species'], per['total_records']) == (s['personal_species'],
                                                           s['personal_records'])
    assert (com['total_species'], com['total_records']) == (s['commercial_species'],
                                                           s['commercial_records'])
    for k in ('total_records', 'this_year_records', 'last_month_records'):
        assert per[k] + com[k] == allq[k], k
    assert allq['total_species'] < per['total_species'] + com['total_species']
    h = HomeTab()
    h.initialize()
    for k, v in allq.items():
        assert h.all_stats.value(k) == f"{v:,}", k
