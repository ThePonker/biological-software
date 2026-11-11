"""R18 B7(b): emptying an observation's grid reference clears vice_county, vc_number, latitude and
longitude (NULL) -- through the edit's own UPDATE, on a small database."""
import os
import sqlite3
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "Observatum")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.views.observations.observation_detail_mixin import ObservationDetailMixin as M  # noqa: E402


def test_emptied_grid_ref_derives_nulls_for_location_fields():
    got, note = M._derive_location_fields("", "SO539092", None)
    assert got == {"vice_county": None, "vc_number": None, "latitude": None, "longitude": None}
    assert note == ""
    assert M._derive_location_fields("", "", None) == ({}, "")                # nothing to clear
    assert M._derive_location_fields(None, None, None) == ({}, "")


def test_the_derived_nulls_reach_the_row():
    """The edit applies `derived` with `updates.update(derived)` and UPDATE ... SET k = ?: NULLs stored."""
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE observations (id INTEGER PRIMARY KEY, grid_ref TEXT, vice_county TEXT, "
              "vc_number INTEGER, latitude REAL, longitude REAL, geodetic_datum TEXT)")
    c.execute("INSERT INTO observations VALUES (1, 'SO539092', 'Gloucestershire', 34, 51.7, -2.6, 'WGS84')")
    updates = {"grid_ref": ""}
    updates.update(M._derive_location_fields("", "SO539092", None)[0])
    c.execute(f"UPDATE observations SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = 1",
              list(updates.values()))
    assert c.execute("SELECT grid_ref, vice_county, vc_number, latitude, longitude, geodetic_datum "
                     "FROM observations").fetchone() == ("", None, None, None, None, "WGS84")
