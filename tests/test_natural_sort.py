"""Natural sort (14 Oct 2026): numbers sort as numbers, text naturally, blanks last --
the key itself, and the Observation Data and Insect Collection proxies."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.natural_sort import less_than, sort_key  # noqa: E402


def _order(values):
    return sorted(values, key=sort_key)


def test_numbers_sort_numerically():
    assert _order(["11", "2", "1", "3.5", "-2", "1,234", 7]) == ["-2", "1", "2", "3.5", 7, "11", "1,234"]
    assert less_than(2, 11) and not less_than("11", "2")


def test_blanks_last():
    assert _order(["b", None, "", "  ", "a", 3]) == [3, "a", "b", None, "", "  "]


def test_natural_text_case_insensitive():
    assert _order(["Trap 10", "trap 2", "Trap 1"]) == ["Trap 1", "trap 2", "Trap 10"]
    assert less_than("TQ 9", "TQ 10")


def test_mixed_types_never_raise():
    # a number sits among mixed values: 3, 5a, 12 (review 14 Oct 2026: not 3, 12, 5a)
    assert _order(["abc", "12", "A 5", 3, "5a", None, ""])[:3] == [3, "5a", "12"]
    assert _order(["10", "2a", "2", "3"]) == ["2", "2a", "3", "10"]
    assert less_than("12", "abc") and not less_than("abc", "12")


def test_obs_keys_and_grid_refs():
    assert less_than("OBS-WJH-20261014-000002", "OBS-WJH-20261014-000010")
    assert _order(["TQ 10", "TQ 9", "SP 4"]) == ["SP 4", "TQ 9", "TQ 10"]


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_observation_proxy_sorts_numbers(qapp):
    from PySide6.QtCore import Qt
    from src.views.observations.observation_tab import ObservationTab
    tab = ObservationTab()
    m = tab.table_model
    m.set_observations([{"id": i, "quantity": q} for i, q in ((1, "2"), (2, "11"), (3, "1"), (4, None))])
    tab._connect_proxy_after_load()
    col = [c[0] for c in m.COLUMNS].index("quantity")
    tab.sort_proxy.sort(col, Qt.SortOrder.AscendingOrder)
    assert [r["id"] for r in m._observations] == [3, 1, 2, 4]
    tab.sort_proxy.sort(col, Qt.SortOrder.DescendingOrder)
    assert [r["id"] for r in m._observations] == [2, 1, 3, 4]      # blank stays last


def test_insect_collection_proxy_sorts_numbers(qapp):
    from PySide6.QtCore import Qt
    from src.views.collection.insect_collection_tab import InsectCollectionTab
    tab = InsectCollectionTab()
    m = tab.table_model
    m._visible_columns.add('id')
    m.set_specimens([{"id": i, "species_name": "Philonthus spinipes"} for i in (2, 11, 1)])
    tab._connect_proxy_after_load()
    col = [c[0] for c in m.get_columns()].index('id')
    tab.sort_proxy.sort(col, Qt.SortOrder.AscendingOrder)
    ids = [m.get_specimen_at_row(tab.sort_proxy.mapToSource(tab.sort_proxy.index(r, 0)).row())["id"]
           for r in range(3)]
    assert ids == [1, 2, 11]
