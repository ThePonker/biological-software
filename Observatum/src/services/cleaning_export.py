"""The cleaning report as a spreadsheet (backlog B): one .xlsx, a Summary sheet and one sheet
per problem type, iRecord ID and link on every row. If openpyxl is missing, a folder of CSV
files instead (summary.csv + one per problem). Read-only on the databases; no Qt.
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
from typing import List

from shared.display_format import DATE_NUMBER_FORMAT, date_cell, dmy, dmy_time

from .cleaning_report import IRECORD_URL, OBSERVATION_ONLY, PROBLEMS, CleaningReport, irecord_url

# Sheet names: Excel allows 31 characters and no / \ ? * [ ] :
SHEET_NAMES = {
    "genus": "Genus only", "family_plus": "Family or higher", "agg": "Aggregates",
    "sl": "Sensu lato", "subsp": "Subspecies, var, form", "hybrid": "Hybrids",
    "no_tvk": "No TVK", "synonym": "Synonyms", "date": "Date", "early": "Date before 1700", "grid": "Grid ref",
    "latlon": "Lat-long not grid ref", "returned": "Came back from iRecord",
    "hidden": "Hidden here",
}
HEADERS = ["Species", "Rank", "Date", "Grid ref", "Site", "Recorder", "Problem",
           "iRecord ID", "iRecord link", "Observatum ID", "Source"]


def _row(r, real_dates: bool = False) -> list:
    """One problem row for a person to read: the date as dd/mm/yyyy (mm/yyyy for a month). In
    the workbook a whole day is a real date cell, so the column sorts and filters as dates."""
    when = date_cell(r.date) if real_dates else dmy(r.date)
    return [r.species, r.rank, when, r.grid_ref, r.site, r.recorder, r.detail,
            r.irecord_id if r.irecord_id else "", irecord_url(r.irecord_id) or "", r.record_id,
            r.dataset]


def summary_rows(report: CleaningReport) -> List[list]:
    out = [["Cleaning report", report.source_label],
           ["Made", dmy_time(_dt.datetime.now().isoformat(timespec="minutes"))],
           ["Records checked", report.total_records],
           ["Records with at least one problem", report.records_with_problem]]
    if report.source == "recording_scheme":
        out += [["NBN copies of iRecord records",
                 "included" if report.include_copies else "left out"],
                ["Marked copies in the database", report.copies_marked],
                [report.copies_note]]
    if report.source == "observations" and report.hidden_records:
        out += [["Removed here, still in iRecord (hidden, not checked)", report.hidden_records]]
    out += [[], ["Problem", "Records"]]
    counts = report.counts
    out += [[label, counts[k]] for k, label in PROBLEMS
            if report.source == "observations" or k not in OBSERVATION_ONLY]
    out += [[], ["A record with several problems is on each of their sheets."],
            ["iRecord link pattern", IRECORD_URL.format(id="<iRecord ID>")]]
    return out


def export_xlsx(report: CleaningReport, path: str) -> str:
    """Write the workbook; returns the path written."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    for row in summary_rows(report):
        ws.append(row)
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 22
    for k, _label in PROBLEMS:
        if k in OBSERVATION_ONLY and report.source != "observations":
            continue
        sh = wb.create_sheet(SHEET_NAMES[k])
        sh.append(HEADERS)
        for c in sh[1]:
            c.font = Font(bold=True)
        for r in report.rows.get(k, []):
            sh.append(_row(r, real_dates=True))
            sh.cell(row=sh.max_row, column=3).number_format = DATE_NUMBER_FORMAT
        sh.freeze_panes = "A2"
        for col, width in zip("ABCDEFGHIJK", (34, 18, 12, 14, 30, 24, 40, 12, 52, 12, 40)):
            sh.column_dimensions[col].width = width
    wb.save(path)
    wb.close()
    return path


def export_csv_folder(report: CleaningReport, folder: str) -> str:
    """The same content as CSV files in `folder` (created if needed); returns the folder."""
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(summary_rows(report))
    for k, _label in PROBLEMS:
        if k in OBSERVATION_ONLY and report.source != "observations":
            continue
        name = SHEET_NAMES[k].lower().replace(", ", "_").replace(" ", "_") + ".csv"
        with open(os.path.join(folder, name), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(HEADERS)
            w.writerows(_row(r) for r in report.rows.get(k, []))
    return folder


def have_openpyxl() -> bool:
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        return False
