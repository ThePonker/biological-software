"""Reading a HadUK-Grid NetCDF file for scripts/build_env_layers.py (25 Oct 2026).

NetCDF4 is HDF5, so h5py reads it (pip install h5py; imported only here, and only when a grid is
built: the app reads the compact value_grid format and needs neither). The file must be on the
British National Grid (EPSG:27700): HadUK-Grid is, with projection_x_coordinate /
projection_y_coordinate in metres; anything else is refused. Returns a float array (NaN = no data,
row 0 north) and the OSGB extent of its cell edges. Read only.
"""
import numpy as np


class NotBritishGrid(ValueError):
    pass


def _attr(obj, name, default=None):
    v = obj.attrs.get(name, default)
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray) and v.size == 1:
        v = v.item()
    return v


def _check_crs(f, var):
    """Refuse a file that is not a transverse Mercator on the OSGB origin (49N 2W, 400 km, -100 km)."""
    gm = _attr(f[var], "grid_mapping")
    if gm is None or gm not in f:
        raise NotBritishGrid(f"{var} names no grid_mapping variable: EPSG:27700 cannot be confirmed")
    g = f[gm]
    ok = (_attr(g, "grid_mapping_name") == "transverse_mercator"
          and abs(float(_attr(g, "false_easting", 0)) - 400000) < 1
          and abs(float(_attr(g, "false_northing", 0)) + 100000) < 1
          and abs(float(_attr(g, "longitude_of_central_meridian", 0)) + 2) < 1e-6)
    if not ok:
        raise NotBritishGrid(f"grid mapping {gm} is not the British National Grid (EPSG:27700)")


def variables(path):
    """The names of the file's data variables (for the dry run)."""
    import h5py
    with h5py.File(path, "r") as f:
        return [k for k in f if len(f[k].shape) >= 2]


def read_grid(path, var):
    """(values, extent, cell_m, units): the variable's first time slice, no-data as NaN."""
    import h5py
    with h5py.File(path, "r") as f:
        if var not in f:
            raise ValueError(f"{path}: no variable {var} (it has {variables(path)})")
        _check_crs(f, var)
        x = np.asarray(f["projection_x_coordinate"][...], dtype="float64")
        y = np.asarray(f["projection_y_coordinate"][...], dtype="float64")
        ds = f[var]
        arr = np.asarray(ds[...])
        while arr.ndim > 2:
            arr = arr[0]
        arr = arr.astype("float64")
        for fill in (_attr(ds, "_FillValue"), _attr(ds, "missing_value")):
            if fill is not None:
                arr[arr == float(fill)] = np.nan
        arr[np.abs(arr) > 1e15] = np.nan
        arr = arr * float(_attr(ds, "scale_factor", 1.0)) + float(_attr(ds, "add_offset", 0.0))
        units = str(_attr(ds, "units", ""))
    cell = float(np.median(np.diff(x)))
    if y[0] < y[-1]:                        # stored south to north: flip so row 0 is the north edge
        y, arr = y[::-1], arr[::-1]
    extent = (float(x.min() - cell / 2), float(y.min() - cell / 2),
              float(x.max() + cell / 2), float(y.max() + cell / 2))
    return arr, extent, cell, units
