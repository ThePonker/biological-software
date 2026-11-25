"""location_map -- the small "Location" map shown beside a record or specimen (25 Nov 2026).

One place for what Edit Specimen did inline, so Record Detail shows the same map: the raster
map when its tiles are there, else the vice-county outline map, else nothing (best effort --
a missing map never stops a window opening).
"""
from __future__ import annotations

from typing import Optional


def make_location_map(vc_service=None):
    """A mini-map widget ready for update_for_row({...grid_ref...}), or None when no map data."""
    import paths
    try:
        from shared.maps.raster_map import RasterMiniMap, find_tiles_dir
        m = RasterMiniMap(find_tiles_dir(str(paths.MAPS_DIR)), vc_service)
        if m.has_data():
            return m
        m.deleteLater()
    except Exception:  # noqa: BLE001 -- best effort
        pass
    try:
        from shared.maps.vc_map import MiniMap
        m = MiniMap(str(paths.VC_GEOJSON), vc_service)
        if m.has_data():
            return m
        m.deleteLater()
    except Exception:  # noqa: BLE001 -- best effort
        pass
    return None


def show_location(m, record: dict) -> None:
    """Point the map at the record's grid ref (no-op without a map or a grid ref)."""
    grid = (record.get("grid_ref") or record.get("gridRef") or "").strip().upper()
    if m is None or not grid:
        return
    try:
        m.update_for_row({"grid_ref": grid})
    except Exception:  # noqa: BLE001 -- best effort
        pass


def vc_service_or_none() -> Optional[object]:
    """The suite's VC lookup service, or None when it cannot be opened."""
    try:
        from src.services.vc_lookup_service import VCLookupService
        return VCLookupService()
    except Exception:  # noqa: BLE001
        return None
