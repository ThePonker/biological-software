"""R20: saved column widths follow the table text size. Widths saved at 13 px text (Rounds 19
and before) are scaled once to the 14 px text, so Wil's columns keep showing what they did."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _keeper(tmp_path, monkeypatch, prefix="r20_cols"):
    from PySide6.QtCore import QSettings
    from PySide6.QtGui import QStandardItemModel
    from PySide6.QtWidgets import QTableView
    import src.views.components.column_widths as cw
    ini = str(tmp_path / "w.ini")
    monkeypatch.setattr(cw, "QSettings", lambda: QSettings(ini, QSettings.Format.IniFormat))
    m = QStandardItemModel(1, 3)
    v = QTableView()
    v.setModel(m)
    k = cw.ColumnWidthKeeper(v, lambda: [("a", "A", 100), ("b", "B", 85), ("c", "C", 50)], prefix)
    return v, k, (lambda: QSettings(ini, QSettings.Format.IniFormat))


def test_widths_saved_at_13px_are_scaled_once(qapp, tmp_path, monkeypatch):
    from shared.text_sizes import font_px
    v, k, settings = _keeper(tmp_path, monkeypatch)
    s = settings()
    s.setValue("r20_cols/a", 130)          # Wil's own width, saved before R20 (no _text_px)
    s.sync()
    k.apply()
    now = font_px("small")
    assert v.columnWidth(0) == round(130 * now / 13)
    assert int(settings().value("r20_cols/_text_px")) == now
    k.apply()                              # a second apply does not scale again
    assert v.columnWidth(0) == round(130 * now / 13)


def test_fresh_settings_use_the_scaled_defaults(qapp, tmp_path, monkeypatch):
    from shared.table_text import scaled_width
    v, k, _s = _keeper(tmp_path, monkeypatch)
    k.apply()
    assert v.columnWidth(0) == scaled_width(100) and v.columnWidth(1) == scaled_width(85)
