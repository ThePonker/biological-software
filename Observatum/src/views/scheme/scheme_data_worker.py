"""Background worker for loading Recording Scheme data.

Runs the SQL query and dict conversion in a background thread
to keep the GUI responsive during the 98k+ row load.
"""

import threading
from PySide6.QtCore import QThread, Signal

from ...services.filter_builder import SCHEME_SOURCES, date_clauses, status_match


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
        self.cancelled = False           # cancel(): a newer load replaced this one
        self._conn = None

    def cancel(self):
        """A newer filter replaced this load: stop its query and drop its results.
        (The tab waited up to 2 s for the old load instead -- QThread.quit() does not
        stop run() -- and Clear All could leave nine full loads running at once.)"""
        self.cancelled = True
        conn = self._conn
        if conn is not None:
            try:
                conn.interrupt()         # safe from another thread; the query raises
            except Exception:
                pass

    def run(self):
        """Execute query in background thread with fast dict conversion."""
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            self._conn = conn
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
                    else:   # by TVK through the shared species search (10 Oct 2026)
                        from shared.species_filter import sql_for_table
                        clause, sp_params = sql_for_table(
                            filters['species'], lambda q, p=(): conn.execute(q, p).fetchall(),
                            "recording_scheme")
                        query += " AND " + clause
                        params.extend(sp_params)
                if filters.get('location'):
                    query += " AND site_name LIKE ?"
                    params.append(f"%{filters['location']}%")
                if filters.get('vice_county'):
                    query += " AND vc_number = ?"
                    params.append(filters['vice_county'])
                if filters.get('subfamily'):
                    query += " AND subfamily = ? COLLATE NOCASE"
                    params.append(filters['subfamily'])
                if filters.get('recorder'):
                    query += " AND recorder LIKE ?"
                    params.append(f"%{filters['recorder']}%")
                # Source = how the record came in (iRecord / NBN Atlas import): the stored
                # source is a dataset name, so "= 'irecord'" matched nothing (SRCH8)
                source = filters.get('source')
                if source in SCHEME_SOURCES:
                    query += f" AND ({SCHEME_SOURCES[source]})"
                # "Accepted" includes "Accepted - correct" etc. (SRCH8: 42,781 missed)
                if filters.get('status'):
                    sql, p = status_match('verification_status', filters['status'])
                    query += f" AND {sql}"
                    params.extend(p)
                # Undated records ('') no longer pass a "Date To" (OBS-14)
                parts, p = date_clauses('date', filters.get('date_from'), filters.get('date_to'))
                for part in parts:
                    query += f" AND {part}"
                params.extend(p)
                # The Filter Wizard's filters (services/filter_builder.build_where)
                if filters.get('_wizard_sql'):
                    sql, p = filters['_wizard_sql']
                    query += f" AND ({sql})"
                    params.extend(p)

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

            if self.cancelled:
                conn.close()
                return
            cursor.execute(query, params)
            rows = cursor.fetchall()
            if self.cancelled:
                conn.close()
                return

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

            # Store results and signal ready (bypasses Qt event queue). The tab polls
            # results_ready; nothing listens to `finished`, and emitting it converted
            # every record to a Qt map: 7 of the 9 s of a full 110,510-record load, and
            # about 0.9 GB held (speed review 10 Oct 2026) -- so it is no longer emitted.
            self.results = (records, species_count)
            self.results_ready.set()

        except Exception as e:
            if self.cancelled:           # interrupted on purpose: not an error
                return
            import traceback
            traceback.print_exc()
            self.error_message = str(e) or e.__class__.__name__
            self.results_ready.set()     # an error is an outcome too: nobody waits forever
            self.error.emit(self.error_message)
        finally:
            if self._conn is not None:
                try:
                    self._conn.close()       # also after an interrupt
                except Exception:
                    pass
                self._conn = None
            self.results_ready.set()
