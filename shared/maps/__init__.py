"""Native (QPainter) map widgets shared by Data Entry and Observatum (backlog H1/H2).

    raster_map        OS 1:250k raster window around one record
    vc_map            vice-county outlines (BRC GeoJSON) + one record
    species_dist_map  whole-GB distribution of one species, dot per square
    gb_basemap        stitched OS 1:250k GB mosaic (cached PNG)
    panzoom           scroll-zoom / drag-pan mixin
    grid_squares      pure hectad / tetrad / monad geometry and print sizing
    grid_map          the Mapping tab's square map (polygons, click, atlas export)

The old DataEntry/<name>.py modules are shims that re-export these.
"""
