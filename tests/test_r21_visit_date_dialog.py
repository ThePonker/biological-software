"""R21: the Visit Date dialog (Specimens to check) raised AttributeError when built: the table loop
reused `v`, the dialog's layout, for each cell's text. It now builds and shows the rows."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_visit_date_dialog_builds_with_rows(qapp):
    from PySide6.QtWidgets import QTableWidget
    from src.views.dialogs.visit_date_dialog import VisitDateDialog
    rows = [{"specimen_code": "S1", "species_name": "Amara fulva", "date_collected": "2026-09-07",
             "site_name": "Alsager"},
            {"specimen_code": "S2", "species_name": "Aus bus", "date_collected": "", "site_name": ""}]
    d = VisitDateDialog(rows)
    t = d.findChild(QTableWidget)
    assert t.rowCount() == 2 and t.item(0, 1).text() == "Amara fulva"
    assert t.item(1, 2).text() == ""
