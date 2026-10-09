"""
Map Data Service for Observatum V2.

Queries observation/specimen/recording_scheme data and aggregates
records into grid squares for map display. Handles grid ref truncation,
time period banding, and coordinate conversion.

Usage:
    from src.services.map_data_service import MapDataService

    svc = MapDataService(db_path, grid_converter)
    grid_data = svc.aggregate_species("Bombus terrestris", "10km", "personal")
    vc_summary = svc.vc_summary("Bombus terrestris", "personal")
"""

import sqlite3
from typing import Optional

from .grid_converter_service import get_grid_converter
import paths
from shared.db_open import connect_ro  # D9: reference data, read-only


# Default time period bands
DEFAULT_BANDS = [
    {"name": "historical", "label": "Pre-2000", "max_year": 1999},
    {"name": "recent", "label": "2000–2019", "max_year": 2019},
    {"name": "current", "label": "2020+", "max_year": 9999},
]


class MapDataService:
    """Service for preparing map display data from the database."""

    def __init__(self, db_path: Optional[str] = None,
                 vc_db_path: Optional[str] = None):
        project_root = paths.OBSERVATUM_DIR
        self._db_path = db_path or str(paths.OBSERVATUM_DB)
        self._vc_db_path = vc_db_path or str(paths.VC_LOOKUP_DB)
        self._converter = get_grid_converter()
        self._coord_cache = {}  # grid_ref → (sw_lat, sw_lon, ne_lat, ne_lon)
        self._bands = DEFAULT_BANDS

    def set_bands(self, bands: list):
        """
        Set custom time period bands.
        bands: list of {"name": str, "label": str, "max_year": int}
        """
        self._bands = sorted(bands, key=lambda b: b["max_year"])

    # -------------------------------------------------------------------------
    # Grid ref utilities
    # -------------------------------------------------------------------------

    def _truncate_grid_ref(self, grid_ref: str, grid_size: str) -> Optional[str]:
        """
        Truncate a grid reference to the target precision.

        grid_size: '100km' → 2 chars, '10km' → 4 chars,
                   '1km' → 6 chars, '100m' → 8 chars
        """
        if not grid_ref:
            return None

        gr = grid_ref.replace(" ", "").upper()
        if len(gr) < 2 or not gr[:2].isalpha():
            return None

        letters = gr[:2]
        digits = gr[2:]

        target_digits = {
            "100km": 0,
            "10km": 2,
            "2km": 2,   # Tetrad — handled separately if needed
            "1km": 4,
            "100m": 6,
        }.get(grid_size, 2)

        if target_digits == 0:
            return letters

        if len(digits) < target_digits:
            return None

        half = target_digits // 2
        easting_digits = digits[: len(digits) // 2][:half]
        northing_digits = digits[len(digits) // 2:][:half]

        return f"{letters}{easting_digits}{northing_digits}"

    def _grid_ref_to_bounds(self, grid_ref: str, grid_size: str) -> Optional[dict]:
        """
        Convert a truncated grid ref to SW/NE lat-lon bounds.
        Uses GridConverterService and caches results.
        """
        cache_key = f"{grid_ref}_{grid_size}"
        if cache_key in self._coord_cache:
            return self._coord_cache[cache_key]

        if not self._converter.is_available():
            return None

        # Grid ref gives the SW corner. Build the full ref for that corner.
        letters = grid_ref[:2]
        digits = grid_ref[2:]

        if len(digits) == 0:
            # 100km square — too coarse for accurate conversion here
            return None

        half = len(digits) // 2
        easting = digits[:half]
        northing = digits[half:]

        # SW corner: the grid ref as-is (padded with zeros for precision)
        precision = len(digits)  # 2=10km, 4=1km, 6=100m
        pad_len = 5 - half  # OS grid refs have 5 digits per axis at 1m
        sw_ref = f"{letters}{easting.ljust(5, '0')}{northing.ljust(5, '0')}"

        # NE corner: increment the last digit of each axis
        step = 10 ** pad_len  # metres to add
        try:
            e_int = int(easting.ljust(5, "0")) + step
            n_int = int(northing.ljust(5, "0")) + step
            ne_ref = f"{letters}{str(e_int).zfill(5)}{str(n_int).zfill(5)}"
        except (ValueError, OverflowError):
            return None

        sw_lat, sw_lon = self._converter.grid_to_latlon(sw_ref)
        ne_lat, ne_lon = self._converter.grid_to_latlon(ne_ref)

        if sw_lat is None or ne_lat is None:
            return None

        result = {
            "sw_lat": sw_lat, "sw_lon": sw_lon,
            "ne_lat": ne_lat, "ne_lon": ne_lon,
        }
        self._coord_cache[cache_key] = result
        return result

    def year_to_band(self, year: Optional[int]) -> str:
        """The time-period band name for a year (public; used by the native map, H3)."""
        return self._year_to_band(year)

    def _year_to_band(self, year: Optional[int]) -> str:
        """Assign a year to a time period band name."""
        if year is None:
            return self._bands[-1]["name"]  # Default to most recent
        for band in self._bands:
            if year <= band["max_year"]:
                return band["name"]
        return self._bands[-1]["name"]

    # -------------------------------------------------------------------------
    # Data queries
    # -------------------------------------------------------------------------

    def _query_records(self, species_name: Optional[str],
                       data_source: str,
                       date_from: str = None,
                       date_to: str = None) -> list:
        """
        Query records from the selected data source(s).
        Returns list of (grid_ref, year) tuples.
        """
        conn = sqlite3.connect(self._db_path)
        results = []

        tables = []
        if data_source in ("personal", "all"):
            tables.append(("observations", "grid_ref", "date"))
            tables.append(("specimens", "grid_ref", "date_collected"))
        if data_source in ("scheme", "all"):
            tables.append(("recording_scheme", "grid_ref", "date"))

        for table, grid_col, date_col in tables:
            try:
                if species_name:
                    date_clause = ""
                    params = [species_name]
                    if date_from:
                        date_clause += f" AND {date_col} >= ?"
                        params.append(date_from)
                    if date_to:
                        date_clause += f" AND {date_col} <= ?"
                        params.append(date_to + "-12-31" if len(date_to) == 4 else date_to)
                    query = f"""
                        SELECT {grid_col}, {date_col}
                        FROM {table}
                        WHERE species_name = ?
                          AND {grid_col} IS NOT NULL
                          AND {grid_col} != ''
                          {date_clause}
                    """
                    rows = conn.execute(query, params).fetchall()
                else:
                    date_clause = ""
                    params = []
                    if date_from:
                        date_clause += f" AND {date_col} >= ?"
                        params.append(date_from)
                    if date_to:
                        date_clause += f" AND {date_col} <= ?"
                        params.append(date_to + "-12-31" if len(date_to) == 4 else date_to)
                    query = f"""
                        SELECT {grid_col}, {date_col}
                        FROM {table}
                        WHERE {grid_col} IS NOT NULL
                          AND {grid_col} != ''
                          {date_clause}
                    """
                    rows = conn.execute(query, params).fetchall()

                for grid_ref, date_str in rows:
                    year = None
                    if date_str:
                        try:
                            year = int(str(date_str)[:4])
                        except (ValueError, IndexError):
                            pass
                    results.append((grid_ref, year))
            except sqlite3.OperationalError:
                # Table might not exist or have different columns
                pass

        conn.close()
        return results

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def aggregate_species(self, species_name: Optional[str],
                          grid_size: str = "10km",
                          data_source: str = "personal",
                          date_from: str = None,
                          date_to: str = None) -> list:
        """
        Aggregate records for a species into grid squares.

        Args:
            species_name: Scientific name, or None for all records
            grid_size: "100km", "10km", "2km", "1km"
            data_source: "personal", "scheme", "all"

        Returns:
            List of dicts ready for MapWidget.set_species():
            [{grid, sw_lat, sw_lon, ne_lat, ne_lon, count, band, years}, ...]
        """
        records = self._query_records(species_name, data_source, date_from, date_to)

        # Group by truncated grid ref
        grid_groups = {}  # truncated_ref → [years]
        for grid_ref, year in records:
            truncated = self._truncate_grid_ref(grid_ref, grid_size)
            if truncated:
                if truncated not in grid_groups:
                    grid_groups[truncated] = []
                grid_groups[truncated].append(year)

        # Build output
        result = []
        for grid_ref, years in grid_groups.items():
            bounds = self._grid_ref_to_bounds(grid_ref, grid_size)
            if not bounds:
                continue

            valid_years = [y for y in years if y is not None]
            min_year = min(valid_years) if valid_years else None
            max_year = max(valid_years) if valid_years else None

            # Band is determined by the most recent record
            band = self._year_to_band(max_year)

            years_str = ""
            if min_year and max_year:
                if min_year == max_year:
                    years_str = str(min_year)
                else:
                    years_str = f"{min_year}–{max_year}"

            result.append({
                "grid": grid_ref,
                "count": len(years),
                "band": band,
                "years": years_str,
                **bounds,
            })

        return result

    def vc_summary(self, species_name: Optional[str],
                   data_source: str = "personal") -> list:
        """
        Vice county summary for a species — which VCs have records.

        Returns list of dicts:
            [{vc_number, vc_name, record_count, first_year, last_year, has_records}, ...]
        """
        # Get all VC names from vc_lookup.db
        vc_conn = connect_ro(self._vc_db_path)
        vc_names = {}
        try:
            rows = vc_conn.execute(
                "SELECT vc_number, vc_name FROM vc_names"
            ).fetchall()
            for num, name in rows:
                vc_names[num] = name
        except sqlite3.OperationalError:
            pass
        vc_conn.close()

        # Get records with VC info
        conn = sqlite3.connect(self._db_path)
        vc_records = {}  # vc_number → [years]

        tables = []
        if data_source in ("personal", "all"):
            tables.append(("observations", "vc_number", "date"))
        if data_source in ("scheme", "all"):
            tables.append(("recording_scheme", "vc_number", "date"))
        # Specimens use vice_county name, not number — handle separately
        if data_source in ("personal", "all"):
            tables.append(("specimens", "vc_number", "date_collected"))

        for table, vc_col, date_col in tables:
            try:
                if species_name:
                    query = f"""
                        SELECT {vc_col}, {date_col}
                        FROM {table}
                        WHERE species_name = ?
                          AND {vc_col} IS NOT NULL
                    """
                    rows = conn.execute(query, (species_name,)).fetchall()
                else:
                    query = f"""
                        SELECT {vc_col}, {date_col}
                        FROM {table}
                        WHERE {vc_col} IS NOT NULL
                    """
                    rows = conn.execute(query).fetchall()

                for vc_val, date_str in rows:
                    try:
                        vc_num = int(vc_val) if vc_val else None
                    except (ValueError, TypeError):
                        continue
                    if vc_num is None:
                        continue

                    year = None
                    if date_str:
                        try:
                            year = int(str(date_str)[:4])
                        except (ValueError, IndexError):
                            pass

                    if vc_num not in vc_records:
                        vc_records[vc_num] = []
                    vc_records[vc_num].append(year)
            except sqlite3.OperationalError:
                pass

        conn.close()

        # Build summary for all known VCs
        result = []
        for vc_num in sorted(vc_names.keys()):
            years = vc_records.get(vc_num, [])
            valid_years = [y for y in years if y is not None]

            result.append({
                "vc_number": vc_num,
                "vc_name": vc_names.get(vc_num, f"VC{vc_num}"),
                "record_count": len(years),
                "first_year": min(valid_years) if valid_years else None,
                "last_year": max(valid_years) if valid_years else None,
                "has_records": len(years) > 0,
            })

        return result

    def get_band_config(self) -> tuple:
        """Return current band colours and labels for the map widget."""
        colors = {}
        labels = {}
        # Default terracotta palette
        palette = {
            "historical": "#e8d5c4",
            "recent": "#c2956e",
            "current": "#9a7555",
        }
        for band in self._bands:
            name = band["name"]
            colors[name] = palette.get(name, "#c2956e")
            labels[name] = band["label"]
        return colors, labels
