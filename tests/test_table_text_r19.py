"""R19: one setting for the main data tables' text: cells 13 px, headers 13 px semi-bold, rows 26 px."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_helper_uses_small_token_and_26_rows(qapp):
    from PySide6.QtWidgets import QTableView
    from shared.table_text import TABLE_ROW_PX, apply_table_rows, scaled_width, table_text_css
    from shared.text_sizes import font_px
    css = table_text_css()
    assert f"QTableView {{ font-size: {font_px('small')}px; }}" in css
    assert f"QHeaderView::section {{ font-size: {font_px('small')}px; font-weight: 600; }}" in css
    assert font_px("small") == 13 and TABLE_ROW_PX == 26
    v = QTableView()
    apply_table_rows(v)
    assert v.verticalHeader().defaultSectionSize() == 26
    assert scaled_width(100) == 108 and scaled_width(85) == 92


def _check(view):
    view.ensurePolished()
    assert view.verticalHeader().defaultSectionSize() == 26
    assert view.fontInfo().pixelSize() == 13
    css = view.styleSheet()
    assert "QHeaderView::section { font-size: 13px; font-weight: 600; }" in css
    assert css.rstrip().endswith("}")


def test_each_main_table_uses_it(qapp):
    from src.views.observations.observation_tab import ObservationTab
    from src.views.scheme.recording_scheme_tab import RecordingSchemeTab
    from src.views.collection.insect_collection_tab import InsectCollectionTab
    from src.views.contributed.contributed_tab import ContributedTab
    _check(ObservationTab().table_view)
    _check(RecordingSchemeTab().table_view)
    _check(InsectCollectionTab().table_view)
    _check(ContributedTab().table)


def test_default_column_widths_grow_with_text(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QTableView
    from PySide6.QtCore import QSettings
    from src.views.components.column_widths import ColumnWidthKeeper
    import src.views.components.column_widths as cw
    monkeypatch.setattr(cw, "QSettings", lambda: QSettings(str(tmp_path / "w.ini"), QSettings.Format.IniFormat))
    from PySide6.QtGui import QStandardItemModel
    m = QStandardItemModel(1, 2)
    v = QTableView()
    v.setModel(m)
    keeper = ColumnWidthKeeper(v, lambda: [("a", "A", 100), ("b", "B", 85)], "r19_test_cols")
    keeper.apply()
    assert v.columnWidth(0) == 108
