"""Dates read dd/mm/yyyy wherever a person reads them (16 Oct 2026); STORED dates stay ISO.

The one helper is shared/display_format (dmy, dmy_time, date_cell). Three changed places are
checked here: the cleaning report's table (shows dd/mm/yyyy, still sorts as a date), its
workbook (a real date cell), and the photo review sheet's "Photo date" column.
"""
import datetime
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.display_format import DATE_NUMBER_FORMAT, date_cell, dmy, dmy_time  # noqa: E402


# --- the helper -------------------------------------------------------------------------

def test_dmy_iso_date_and_blank():
    assert dmy("2026-10-14") == "14/10/2026"
    assert dmy("") == "" and dmy(None) == ""


def test_dmy_iso_datetime_drops_the_time_and_dmy_time_keeps_it():
    assert dmy("2026-10-14T21:14:07") == "14/10/2026"
    assert dmy_time("2026-10-14T21:14:07") == "14/10/2026 21:14"
    assert dmy_time("2026-10-14 09:05") == "14/10/2026 09:05"
    assert dmy_time("2026-10-14") == "14/10/2026"          # no time to show
    assert dmy_time(None) == ""


def test_dmy_year_only_and_month():
    assert dmy("2021") == "2021"                            # a year is already what it is
    assert dmy("2021-06") == "06/2021"                      # a month: mm/yyyy
    assert dmy("2021-13") == "2021-13"                      # not a month: left alone


def test_dmy_garbage_is_left_as_is():
    for text in ("Spring", "2024-05-01/2024-05-15", "14/10/2026", "soon"):
        assert dmy(text) == text
        assert dmy_time(text) == text


def test_date_cell_is_a_real_date_only_for_a_whole_day():
    assert date_cell("2026-10-14") == datetime.date(2026, 10, 14)
    assert date_cell("2021-06") == "06/2021" and date_cell("2021") == "2021"
    assert date_cell("2026-02-30") == "30/02/2026"          # not a day: shown as text, not lost
    assert date_cell(None) == ""
    assert DATE_NUMBER_FORMAT == "DD/MM/YYYY"


# --- a table cell shows dd/mm/yyyy and still sorts as a date -----------------------------

def _row(rid, date):
    from src.services.cleaning_report import CleaningRow
    return CleaningRow(record_id=rid, species="Amara aenea", rank="Species", date=date,
                       grid_ref="SP5822", site="Bicester", recorder="WJH", irecord_id=None,
                       problem="date", detail="d")


def test_cleaning_table_shows_dmy_and_sorts_by_the_iso_date():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from src.views.stats.cleaning_table import CleaningRowModel, CleaningTableView
    _app = QApplication.instance() or QApplication([])
    # 31/12/2025 sorts AFTER 05/06/2026 as text; as dates it comes first
    model = CleaningRowModel([_row(1, "2026-06-05"), _row(2, "2025-12-31"), _row(3, "1956-06")])
    view = CleaningTableView(model)
    col = 2
    shown = [model.index(r, col).data(Qt.ItemDataRole.DisplayRole) for r in range(3)]
    assert shown == ["05/06/2026", "31/12/2025", "06/1956"]
    assert model.index(0, col).data(Qt.ItemDataRole.EditRole) == "2026-06-05"   # sort key stays ISO
    view.proxy.sort(col, Qt.SortOrder.AscendingOrder)
    ordered = [view.proxy.index(r, col).data(Qt.ItemDataRole.DisplayRole) for r in range(3)]
    assert ordered == ["06/1956", "31/12/2025", "05/06/2026"]


# --- the cleaning workbook and CSV -------------------------------------------------------

def test_cleaning_export_writes_dmy_and_real_date_cells():
    from src.services import cleaning_export as ce
    rows = [_row(1, "2026-06-05"), _row(2, "1956-06")]
    assert ce._row(rows[0])[2] == "05/06/2026" and ce._row(rows[1])[2] == "06/1956"
    cell = ce._row(rows[0], real_dates=True)[2]
    assert cell == datetime.date(2026, 6, 5)
    # the model's own value is untouched: stored/sorted as ISO
    assert rows[0].date == "2026-06-05"


# --- photo review sheet ------------------------------------------------------------------

def test_photo_review_sheet_writes_the_photo_date_dmy(tmp_path):
    from openpyxl import load_workbook
    from scripts import photo_review_sheet as prs
    base = {c: "" for c in prs.COLS}
    rows = [dict(base, Species="Amara aenea", **{"Photo date": "2026-06-05"}, Photo="a.jpg",
                 _uri="file:///a.jpg"),
            dict(base, Species="Amara aenea", **{"Photo date": "2021-06"}, Photo="b.jpg",
                 _uri="file:///b.jpg")]
    path = tmp_path / "sheet.xlsx"
    prs.write_xlsx(rows, [("Photos to review", 2)], path)
    ws = load_workbook(path)["Review"]
    col = prs.COLS.index("Photo date") + 1
    first, second = ws.cell(2, col), ws.cell(3, col)
    assert first.value == datetime.datetime(2026, 6, 5) and first.number_format == "DD/MM/YYYY"
    assert second.value == "06/2021"                         # not a whole day: text
    assert rows[0]["Photo date"] == "2026-06-05"             # the rows keep the ISO date


# --- a screen with its own date formatter ------------------------------------------------

def test_lector_times_read_dmy():
    pytest.importorskip("PySide6")
    from Lector.ui.style import fmt_when
    assert fmt_when("2026-10-12T10:41:48") == "12/10/2026 10:41"
    assert fmt_when("2026-10-12T10:41:48", day_only=True) == "12/10/2026"
    assert fmt_when("") == ""
