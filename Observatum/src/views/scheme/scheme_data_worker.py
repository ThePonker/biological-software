"""Background worker for loading Recording Scheme data.

Runs the SQL query and dict conversion in a background thread
to keep the GUI responsive during the 98k+ row load.
"""

import threading
from PySide6.QtCore import QThread, Signal


class SchemeDataWorker(QThread):
    """Worker thread for loading scheme records."""

    finished = Signal(list, int)  # records list, species_count
    error = Signal(str)

    def __init__(self, db_path: str, filters=None, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._filters = filters
        # Thread-safe result storage (bypass Qt signal queue)
        self.results = None
        self.error_message = None        # set if run() raised; results stay None
        # Set when run() ends, success or not -- startup waits on it (OBS-02)
        self.results_ready = threading.Event()

    def run(self):
        """Execute query in background thread with fast dict conversion."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT *
                FROM recording_scheme
                WHERE 1=1
            """
            params = []
            filters = self._filters

            if filters:
                # Scheme family scope (from settings)
                if filters.get('_scheme_families'):
                    fams = filters['_scheme_families']
                    placeholders = ','.join(['?' for _ in fams])
                    query += f" AND family IN ({placeholders})"
                    params.extend(fams)

                if filters.get('species'):
                    if filters.get('species_exact'):
                        query += " AND species_name = ?"
                        params.append(filters['species'])
                    else:
                        query += " AND (species_name LIKE ? OR common_name LIKE ?)"
                        search = f"%{filters['species']}%"
                        params.extend([search, search])
                if filters.get('location'):
                    query += " AND site_name LIKE ?"
                    params.append(f"%{filters['location']}%")
                if filters.get('vice_county'):
                    query += " AND vc_number = ?"
                    params.append(filters['vice_county'])
                if filters.get('subfamily'):
                    query += " AND subfamily = ?"
                    params.append(filters['subfamily'])
                if filters.get('recorder'):
                    query += " AND recorder LIKE ?"
                    params.append(f"%{filters['recorder']}%")
                source = filters.get('source', '')
                if source and source.lower() != 'all' and source != '':
                    query += " AND LOWER(source) = ?"
                    params.append(source.lower())
                if filters.get('status'):
                    query += " AND verification_status = ?"
                    params.append(filters['status'])
                if filters.get('date_from'):
                    query += " AND date >= ?"
                    params.append(filters['date_from'])
                if filters.get('date_to'):
                    query += " AND date <= ?"
                    params.append(filters['date_to'])

            # Apply stats exclusion filters from QSettings
            from PySide6.QtCore import QSettings
            settings = QSettings()

            if settings.value("stats/scheme_exclude_family", False, type=bool):
                query += " AND species_name NOT LIKE '%idae' AND species_name NOT LIKE '%inae'"

            if settings.value("stats/scheme_exclude_genus", False, type=bool):
                query += """ AND (
                    (species_name LIKE '%idae' OR species_name LIKE '%inae')
                    OR (
                        species_name LIKE '% %'
                        AND species_name NOT GLOB '*([a-z]*)'
                        AND species_name NOT LIKE '% sp.%'
                        AND species_name NOT LIKE '% sp'
                        AND species_name NOT LIKE '%indet%'
                    )
                )"""

            if settings.value("stats/scheme_exclude_ss", False, type=bool):
                query += " AND species_name NOT LIKE '%s.s.%' AND species_name NOT LIKE '%sensu stricto%'"

            if settings.value("stats/scheme_exclude_sl", False, type=bool):
                query += " AND species_name NOT LIKE '%s.l.%' AND species_name NOT LIKE '%sensu lato%'"

            if settings.value("stats/scheme_exclude_agg", False, type=bool):
                query += " AND species_name NOT LIKE '%agg.%' AND species_name NOT LIKE '%agg %' AND species_name NOT LIKE '% agg'"

            query += " ORDER BY date DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Fast dict conversion
            if rows:
                col_names = [desc[0] for desc in cursor.description]
                records = [dict(zip(col_names, row)) for row in rows]
            else:
                records = []

            species_set = set()
            for r in records:
                sp = r.get("species_name")
                if sp:
                    species_set.add(sp)
            species_count = len(species_set)


            conn.close()

            # Store results and signal ready (bypasses Qt event queue)
            self.results = (records, species_count)
            self.results_ready.set()

            # Also emit Qt signal as fallback
            self.finished.emit(records, species_count)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_message = str(e) or e.__class__.__name__
            self.results_ready.set()     # an error is an outcome too: nobody waits forever
            self.error.emit(self.error_message)
        finally:
            self.results_ready.set()
