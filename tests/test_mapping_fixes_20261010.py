"""Mapping tab fixes from Wil's testing, 10 Oct 2026.

A  each chosen taxon its own colour (By taxon style, split overlap squares, chip swatches);
B  vice-county outlines: every part of a multi-part VC drawn (VC1 was one Scilly islet);
C  choosing a vice-county shows it (County view), "All" goes back to National.

Pure parts on made-up data; the outline check against the BRC shapefile and the tab on the
data copies (read-only), offscreen.
"""
import json
import os

import pytest

import paths

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAVE_DATA = paths.OBSERVATUM_DB.exists() and paths.UKSI_DB.exists()
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="needs data/observatum.db and uksi.db")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- B: VC outlines

def _square(e0, n0, size, clockwise=True):
    pts = [(e0, n0), (e0, n0 + size), (e0 + size, n0 + size), (e0 + size, n0), (e0, n0)]
    return pts if clockwise else pts[::-1]


def _latlon_ring(ring_en):
    """OSGB ring -> [lat, lon] pairs as the BRC GeoJSON stores them."""
    from shared.osgb import osgb_en_to_wgs84
    return [list(osgb_en_to_wgs84(e, n)) for e, n in ring_en]


def _geojson(tmp_path, geometry):
    path = tmp_path / "vc.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"VCNUMBER": 1}, "geometry": geometry}]}))
    return str(path)


def test_old_style_polygon_keeps_every_part_and_drops_holes(tmp_path):
    """The converter used to put islands and holes all in ONE Polygon: island first here,
    as with VC1's Scilly islet; the mainland must still be drawn, the hole not."""
    from shared.maps.vc_map import load_vc_polygons
    island = _square(100000, 10000, 3000)                 # clockwise = outer (shapefile rule)
    mainland = _square(130000, 20000, 40000)
    hole = _square(140000, 30000, 5000, clockwise=False)  # anticlockwise = hole
    geom = {"type": "Polygon", "coordinates": [_latlon_ring(r) for r in (island, mainland, hole)]}
    rings, _b = load_vc_polygons(_geojson(tmp_path, geom), tol=50.0)
    assert len(rings[1]) == 2
    spans = sorted(max(e for e, _n in r) - min(e for e, _n in r) for r in rings[1])
    assert spans[0] == pytest.approx(3000, abs=60) and spans[1] == pytest.approx(40000, abs=60)


def test_multipolygon_and_tiny_islet_kept(tmp_path):
    from shared.maps.vc_map import load_vc_polygons
    mainland = _square(200000, 200000, 30000)
    islet = _square(300000, 200000, 100)                  # smaller than the 300 m tolerance
    geom = {"type": "MultiPolygon", "coordinates": [[_latlon_ring(mainland)],
                                                    [_latlon_ring(islet)]]}
    rings, bounds = load_vc_polygons(_geojson(tmp_path, geom))
    assert len(rings[1]) == 2                              # the islet still sets the extent
    assert bounds[2] == pytest.approx(300100, abs=5)


def _shp_ok():
    try:
        import shapefile  # noqa: F401
    except ImportError:
        return False
    return (paths.MAPS_DIR / "vc_brc.shp").exists() and paths.VC_GEOJSON.exists()


@pytest.mark.skipif(not _shp_ok(), reason="needs pyshp, vc_brc.shp and vc_brc_wgs84.geojson")
def test_every_vc_outline_matches_the_shapefile():
    """All 112 VCs: drawn area within 10 % and extent within 5 km of the shapefile's."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "scripts"))
    import check_vc_outlines
    rows = check_vc_outlines.check()
    assert len(rows) == 112
    assert [r[0] for r in rows if not r[4]] == []


# ---------------------------------------------------------------- A: colours per taxon

def test_squares_record_their_chips():
    from src.services import map_square_service as s
    recs = [{"grid_ref": "SP4030", "year": 2020, "species": "a", "chips": [0]},
            {"grid_ref": "SP4131", "year": 2021, "species": "b", "chips": [0, 1]},
            {"grid_ref": "SP9090", "year": 2021, "species": "b", "chips": [1]}]
    squares, _c, _u = s.squares_for(recs, 10000, lambda y: "current")
    assert squares["SP43"]["chips"] == [0, 1] and squares["SP99"]["chips"] == [1]


def test_by_taxon_style_splits_overlaps_and_legend():
    from src.views.mapping.square_style import colour_squares, default_taxon_colour, TAXON_PALETTE
    sq = {"A": {"count": 1, "chips": [0]}, "B": {"count": 2, "chips": [0, 1]},
          "C": {"count": 1, "chips": [1]}}
    taxa = [("Coleoptera", "#0072b2"), ("Lucanus cervus", "#1a9641")]
    legend = colour_squares(sq, "taxon", {}, {}, "#eeeeee", "#333333", taxa=taxa)
    assert sq["A"]["fill"] == "#0072b2" and "fills" not in sq["A"]
    assert sq["B"]["fills"] == ["#0072b2", "#1a9641"]
    assert sq["C"]["fill"] == "#1a9641"
    assert [lab for _c, lab in legend][:2] == ["Coleoptera", "Lucanus cervus"]
    assert isinstance(legend[2][0], tuple) and legend[2][1].startswith("Overlap")
    # another style clears the split; one taxon's Presence map is in its colour
    colour_squares(sq, "presence", {}, {}, "#eeeeee", "#333333", taxa=taxa)
    assert "fills" not in sq["B"] and sq["A"]["fill"] == "#333333"
    one = {"A": {"count": 1, "chips": [0]}}
    assert colour_squares(one, "presence", {}, {}, "#eee", "#333", taxa=taxa[:1]) == \
        [("#0072b2", "Coleoptera")]
    assert one["A"]["fill"] == "#0072b2"
    assert default_taxon_colour([TAXON_PALETTE[0].lower()]) == TAXON_PALETTE[1]


def test_split_square_is_drawn_in_both_colours(qapp):
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from shared.maps.grid_map import draw_split
    img = QImage(40, 40, QImage.Format.Format_RGB32)
    img.fill(QColor("#ffffff"))
    p = QPainter(img)
    draw_split(p, QRectF(0, 0, 40, 40), ["#ff0000", "#0000ff"], Qt.PenStyle.NoPen)
    p.end()
    assert img.pixelColor(5, 5).name() == "#ff0000"          # upper left half
    assert img.pixelColor(35, 35).name() == "#0000ff"        # lower right half


# ---------------------------------------------------------------- the tab (A and C)

@pytest.fixture(scope="module")
def tab(qapp):
    if not HAVE_DATA:
        pytest.skip("needs data copies")
    from PySide6.QtCore import QCoreApplication, QSettings
    org = QCoreApplication.organizationName()
    QCoreApplication.setOrganizationName("ObservatumTests_mapfix_20261010")
    QSettings().clear()
    from src.views.mapping.mapping_tab import MappingTab
    t = MappingTab()
    t.toolbar.data_combo.setCurrentIndex(t.toolbar.data_combo.findData("all"))
    yield t
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)


def _add(sb, text, rank):
    sb.rank_combo.setCurrentIndex(sb.rank_combo.findData(rank))
    sb.search.setText(text)
    sb.run_search()
    sb.add([r for r in sb.results() if r["scientific_name"] == text][0])


@needs_data
def test_tab_two_taxa_by_taxon_colours(tab):
    sb = tab.filter_panel.selection_box
    sb.clear()
    _add(sb, "Coleoptera", "order")
    assert tab.display_bar.style() == "presence"
    assert tab._legend == [(sb.colours()[0], "Coleoptera")]        # its own colour
    _add(sb, "Lucanus cervus", "species")
    assert tab.display_bar.style() == "taxon"                       # default with two taxa
    assert sb.colours()[0] != sb.colours()[1]
    records = tab._records
    sb.set_chip_colour(1, "#1a9641")                                # recolour, no new query
    assert tab._records is records
    assert ("#1a9641", "Lucanus cervus") in tab._legend
    split = [k for k, sq in tab._squares.items() if sq.get("fills")]
    assert split and all("#1a9641" in tab._squares[k]["fills"] for k in split)
    assert all("Lucanus cervus" in tab._squares[k]["tip"] for k in split)
    assert "Lucanus cervus" in tab.display_bar.legend_labels()
    img = tab.render_atlas()                                        # legend + colours
    assert img.width() == 2480
    # the colour is remembered for the taxon
    sb.remove(1)
    assert tab.display_bar.style() == "presence"
    _add(sb, "Lucanus cervus", "species")
    assert sb.colours()[1] == "#1a9641"
    sb.clear()


@needs_data
def test_tab_vc_choice_switches_view(tab):
    fp = tab.filter_panel
    sb = fp.selection_box
    sb.clear()
    _add(sb, "Coleoptera", "order")
    i = fp.vc_combo.findData(23)
    assert i > 0
    fp.vc_combo.setCurrentIndex(i)
    assert tab.toolbar.get_view() == "county"
    if tab.map_widget.vc_extent(23) is None:          # no vc_brc_wgs84.geojson here
        pytest.skip("needs data/maps/vc_brc_wgs84.geojson")
    assert tab.map_widget._extent == tab.map_widget.vc_extent(23)
    assert {r["vc"] for r in tab._records} == {23}                   # still a filter
    fp.vc_combo.setCurrentIndex(0)
    assert tab.toolbar.get_view() == "national"
    assert len({r["vc"] for r in tab._records}) > 1
    sb.clear()
