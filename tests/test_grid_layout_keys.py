"""Data Entry grid layout by column key (16 Oct 2026): a layout saved before the Check columns
existed keeps its order, widths and hidden columns; new columns land after their neighbour."""
import os
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _view(n):
    from PySide6.QtGui import QStandardItemModel
    from PySide6.QtWidgets import QApplication, QTableView
    QApplication.instance() or QApplication([])
    v = QTableView()
    v.setModel(QStandardItemModel(0, n))
    return v


def test_legacy_layout_survives_new_columns():
    from DataEntry import entry_grid as eg
    legacy = eg.EntryGridPage._LEGACY_KEYS
    old = _view(len(legacy))
    hh = old.horizontalHeader()
    i_site, i_date, i_vc = legacy.index("site_name"), legacy.index("date"), legacy.index("vice_county")
    hh.moveSection(hh.visualIndex(i_site), 1)          # Wil moved Site next to Species
    hh.resizeSection(i_date, 177)
    old.setColumnHidden(i_vc, True)
    state = hh.saveState()

    layout = eg.EntryGridPage._legacy_layout(state, legacy)
    new = _view(len(eg.COLUMNS))
    obj = types.SimpleNamespace(_view=new)
    assert eg.EntryGridPage._apply_layout(obj, layout)
    nh = new.horizontalHeader()
    C = eg.COLIDX
    assert nh.visualIndex(C["site_name"]) == 1
    assert nh.sectionSize(C["date"]) == 177
    assert new.isColumnHidden(C["vice_county"]) and not new.isColumnHidden(C["check_flag"])
    # the new columns follow Comment, as in COLUMNS
    assert nh.visualIndex(C["check_flag"]) == nh.visualIndex(C["comment"]) + 1
    assert nh.visualIndex(C["check_note"]) == nh.visualIndex(C["check_flag"]) + 1
