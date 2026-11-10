"""Warm-up fixes, 13 Oct 2026: the scheme month chart's never-built species drop-down retired
(backlog 10, Q64); "Local authority districts" (Q39, test_mapping_r4); Species lookup <->
Home > Species Info linked both ways (backlog 13, Q55)."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import paths  # noqa: E402

HAVE_DATA = paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_month_chart_has_no_species_filter(qapp):
    import inspect
    from src.views.stats.stat_widgets import MonthlyActivityChart
    assert "show_species_filter" not in inspect.signature(MonthlyActivityChart.__init__).parameters
    assert not hasattr(MonthlyActivityChart, "set_species_list")
    assert not hasattr(MonthlyActivityChart, "species_changed")
    c = MonthlyActivityChart("Monthly Distribution of Records")
    c.set_data(list(range(12)))
    from src.views.stats.scheme_dashboard import SchemeDashboard
    assert not hasattr(SchemeDashboard, "_on_monthly_species_changed")


def test_species_info_link_emits_name_and_tvk(qapp):
    from src.views.home.species_info import SpeciesInfoPanel
    p = SpeciesInfoPanel()
    got = []
    p.lookup_clicked.connect(lambda n, t: got.append((n, t)))
    p.set_species({"scientific_name": "Rutpela maculata", "tvk": "NHMSYS0020152216",
                   "common_name": "Black-and-yellow Longhorn", "record_count": 3})
    assert p.lookup_btn.isVisibleTo(p)
    p.lookup_btn.click()
    assert got == [("Rutpela maculata", "NHMSYS0020152216")]


@pytest.mark.skipif(not HAVE_DATA, reason="data copies absent")
def test_lookup_opens_a_species_and_shows_it_on_home(qapp):
    from PySide6.QtWidgets import QPushButton
    from src.views.stats.species_dashboard import SpeciesDashboard
    conn = sqlite3.connect(f"file:{paths.OBSERVATUM_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    class Db:
        def execute_main(self, sql, params=()):
            return conn.execute(sql, params).fetchall()

    d = SpeciesDashboard()
    d._db = Db()
    assert d.show_species("Rutpela maculata") is True
    assert d._selected_species["species"] == "Rutpela maculata"
    assert d._selected_species["tvk"]
    assert d.species_search.text() == "Rutpela maculata"
    assert d.show_species("Nothing like this name at all") is False
    homes = []
    d.show_on_home.connect(homes.append)
    btn = next(b for b in d.findChildren(QPushButton) if b.text() == "Show on Home")
    btn.click()
    assert homes and homes[0]["scientific_name"] == "Rutpela maculata"
    assert homes[0]["tvk"] == d._selected_species["tvk"]
    conn.close()
