"""Year-by-Year CSV exports for the Personal / Commercial / All stats dashboards.

The "Export All Years CSV" and per-year "CSV" buttons on YearByYearTable emitted signals
that nothing was connected to (review OBS-19). wire_year_exports() connects them:

- All years: the table as shown -- Year, Species, Records, New.
- One year: the records counted in that year's "Records" figure -- dated, with a TVK,
  the same species-exclusion setting as the table, and the dashboard's record type.
"""
import csv
from typing import Dict, List, Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ...services.observation_stats_service import get_observation_exclusion_clause

# Real observations columns, in export order, with their CSV headers
YEAR_RECORD_COLUMNS = [
    ('species_name', 'Species'), ('common_name', 'Common Name'), ('species_tvk', 'TVK'),
    ('date', 'Date'), ('site_name', 'Site'), ('grid_ref', 'Grid Ref'),
    ('vc_number', 'VC'), ('vice_county', 'Vice County'), ('recorder', 'Recorder'),
    ('determiner', 'Determiner'), ('sex', 'Sex'), ('stage', 'Stage'),
    ('quantity', 'Quantity'), ('method', 'Method'), ('record_type', 'Record Type'),
    ('project_name', 'Project'), ('client', 'Client'), ('comment', 'Comment'),
    ('verification_status', 'Verification'),
]


def year_records(db, year: int, record_type: Optional[str]) -> List[Dict]:
    """The records behind one row of the Year-by-Year table (same WHERE as its count)."""
    cols = ", ".join(c for c, _ in YEAR_RECORD_COLUMNS)
    sql = f"""
        SELECT {cols} FROM observations
        WHERE date IS NOT NULL AND species_tvk IS NOT NULL
          AND strftime('%Y', date) = ?
          {get_observation_exclusion_clause()}
    """
    params: list = [str(year)]
    if record_type:
        sql += " AND record_type = ?"
        params.append(record_type)
    sql += " ORDER BY date, species_name"
    return [dict(r) for r in (db.execute_main(sql, tuple(params)) or [])]


def write_year_records_csv(path: str, rows: List[Dict]) -> int:
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow([h for _, h in YEAR_RECORD_COLUMNS])
        for r in rows:
            w.writerow(['' if r.get(c) is None else r.get(c) for c, _ in YEAR_RECORD_COLUMNS])
    return len(rows)


def write_all_years_csv(path: str, data: Dict) -> int:
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['Year', 'Species', 'Records', 'New'])
        for year in sorted(data, reverse=True):
            s = data[year]
            w.writerow([year, s.get('species', 0), s.get('records', 0), s.get('newSpecies', 0)])
    return len(data)


def _ask_path(parent, default_name: str) -> str:
    path, _ = QFileDialog.getSaveFileName(parent, "Export CSV", default_name, "CSV Files (*.csv)")
    if path and not path.lower().endswith('.csv'):
        path += '.csv'
    return path


def wire_year_exports(table, record_type: Optional[str], label: str, parent) -> None:
    """Connect a YearByYearTable's export buttons. record_type None = all records."""

    def export_all():
        data = getattr(table, '_data', None) or {}
        if not data:
            QMessageBox.information(parent, "Export", "There are no years to export.")
            return
        path = _ask_path(parent, f"{label.lower()}_year_by_year.csv")
        if not path:
            return
        try:
            n = write_all_years_csv(path, data)
            QMessageBox.information(parent, "Export", f"Exported {n} years to:\n{path}")
        except OSError as e:
            QMessageBox.critical(parent, "Export failed", str(e))

    def export_year(year: str):
        from ...models.database import get_database
        try:
            rows = year_records(get_database(), int(year), record_type)
        except Exception as e:
            QMessageBox.critical(parent, "Export failed", str(e))
            return
        if not rows:
            QMessageBox.information(parent, "Export", f"No {label.lower()} records in {year}.")
            return
        path = _ask_path(parent, f"{label.lower()}_records_{year}.csv")
        if not path:
            return
        try:
            n = write_year_records_csv(path, rows)
            QMessageBox.information(parent, "Export", f"Exported {n:,} records for {year} to:\n{path}")
        except OSError as e:
            QMessageBox.critical(parent, "Export failed", str(e))

    table.export_all_clicked.connect(export_all)
    table.export_year_clicked.connect(export_year)
