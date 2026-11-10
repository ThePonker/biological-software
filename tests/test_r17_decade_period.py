"""R17 A5: the Date Range's Decade choice in the Mapping filter panel."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from shared.maps import map_stats  # noqa: E402


@pytest.fixture(scope="module")
def panel():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.mapping.filter_panel import MapFilterPanel
    return MapFilterPanel()


def test_the_choices_are_the_export_bands():
    from src.views.mapping.date_check import decade_choices
    assert [c[0] for c in decade_choices()] == [d[0] for d in map_stats.DECADES]
    assert decade_choices()[0] == ("pre-1950", "", "1949")
    assert decade_choices()[1] == ("1950–79", "1950", "1979")
    assert decade_choices()[-1] == ("2020–", "2020", "")


def test_combo_lists_any_then_every_band(panel):
    items = [panel.decade_combo.itemText(i) for i in range(panel.decade_combo.count())]
    assert items == ["Any decade"] + [d[0] for d in map_stats.DECADES]


@pytest.mark.parametrize("i,lo,hi", [(i + 1, d[1], d[2]) for i, d in enumerate(map_stats.DECADES)])
def test_choosing_a_band_filters_to_it(panel, i, lo, hi):
    got = []
    panel.generate_requested.connect(lambda: got.append(1))
    panel.decade_combo.setCurrentIndex(i)
    panel._on_decade()
    panel.generate_requested.disconnect()
    f, err = panel.filters()
    assert err == "" and got == [1]
    assert (f.date_from or "")[:4] == (str(lo) if lo else "")
    assert (f.date_to or "")[:4] == (str(hi) if hi else "")
    if lo:
        assert f.date_from == f"{lo}-01-01"
    if hi:
        assert f.date_to == f"{hi}-12-31"


def test_typing_a_date_resets_the_choice_and_any_clears(panel):
    panel.decade_combo.setCurrentIndex(2)
    panel._on_decade()
    assert panel.date_from.text() == "1950" and panel.date_to.text() == "1979"
    panel.date_to.setText("1990")
    assert panel.decade_combo.currentIndex() == 0
    panel.decade_combo.setCurrentIndex(3)
    panel._on_decade()
    panel.decade_combo.setCurrentIndex(0)
    panel._on_decade()
    assert panel.date_from.text() == "" and panel.date_to.text() == ""
    panel.decade_combo.setCurrentIndex(4)
    panel._on_decade()
    panel.clear_all()
    assert panel.decade_combo.currentIndex() == 0 and panel.date_from.text() == ""
