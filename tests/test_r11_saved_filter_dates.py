"""F78 (13 Oct, Wil): loading the 'This Year' saved filter set Date To to 01/01/1900, which
since OBS-14 is a real date, so the table showed nothing. A saved filter without a date must
leave the date box blank."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_this_year_preset_leaves_date_to_blank():
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.views.observations.observation_filter_bar import ObservationFilterBar
    bar = ObservationFilterBar()
    bar._apply_saved_filter({"date_from": "THIS_YEAR"})
    f = bar.get_filters()
    assert f["date_from"] == f"{QDate.currentDate().year()}-01-01"
    assert f["date_to"] is None
    bar._apply_saved_filter({})
    f = bar.get_filters()
    assert f["date_from"] is None and f["date_to"] is None
