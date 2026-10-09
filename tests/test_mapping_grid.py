"""Mapping tab (backlog H1-H6): square geometry, click lookup, print sizing, styling, shims."""
import os

import pytest

from shared import osgb
from shared.maps import grid_squares as gs

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------- squares (H3)

@pytest.mark.parametrize("ref, size, out", [
    ("SP580207", gs.HECTAD, "SP52"), ("SP580207", gs.MONAD, "SP5820"),
    ("SP580207", gs.TETRAD, "SP52V"),          # 8 km E, 0.7 km N in SP52 -> column 5, row 1
    ("SP5820", gs.TETRAD, "SP52V"), ("SP 58123 20999", gs.MONAD, "SP5820"),
    ("SP0000", gs.TETRAD, "SP00A"), ("SP0008", gs.TETRAD, "SP00E"), ("SP0200", gs.TETRAD, "SP00F"),
    ("SP58A", gs.TETRAD, "SP58A"), ("SP58A", gs.HECTAD, "SP58"),
])
def test_square_for_ref(ref, size, out):
    assert gs.square_for_ref(ref, size) == out


@pytest.mark.parametrize("ref, size", [("SP58", gs.TETRAD), ("SP58", gs.MONAD),
                                       ("SP58A", gs.MONAD), ("J1588", gs.HECTAD), ("", gs.HECTAD)])
def test_too_coarse_or_unparsed_is_none(ref, size):
    assert gs.square_for_ref(ref, size) is None


def test_tetrad_label_agrees_with_shared_osgb():
    # every DINTY letter round-trips: the label's south-west corner is the square we built it from
    for i, letter in enumerate("ABCDEFGHIJKLMNPQRSTUVWXYZ"):
        e = 450000 + (i // 5) * 2000 + 500
        n = 220000 + (i % 5) * 2000 + 500
        lab = gs.square_for_point(e, n, gs.TETRAD)
        assert lab == "SP52" + letter
        assert osgb.gridref_to_en(lab) == (e - 500, n - 500, 2000)


def test_square_polygon():
    assert gs.square_polygon("SP5820") == [(458000, 220000), (459000, 220000),
                                           (459000, 221000), (458000, 221000)]
    assert gs.square_polygon("SP52V") == [(458000, 220000), (460000, 220000),
                                          (460000, 222000), (458000, 222000)]
    assert gs.square_polygon("nonsense") is None


def test_aggregate_counts_and_reasons():
    recs = [("SP580207", 2001), ("SP5820", 1999), ("SP58", 2020), ("J1588", 2010),
            ("SP581209", None)]
    squares, coarse, unparsed = gs.aggregate(recs, gs.MONAD)
    assert squares == {"SP5820": {"count": 3, "first_year": 1999, "last_year": 2001}}
    assert (coarse, unparsed) == (1, 1)
    squares, coarse, _u = gs.aggregate(recs, gs.HECTAD)
    assert squares["SP52"]["count"] == 3 and squares["SP58"]["count"] == 1 and coarse == 0


# ---------------------------------------------------------------- click lookup (H4)

def test_mapfit_round_trip_and_click():
    fit = gs.MapFit(gs.GB_LAND, 400, 700)
    x, y = fit.to_px(458500, 220500)
    e, n = fit.to_en(x, y)
    assert abs(e - 458500) < 1e-6 and abs(n - 220500) < 1e-6
    assert gs.square_at_pixel(fit, x, y, gs.HECTAD) == "SP52"
    # zoomed 4x and panned: the same ground point is at pan + zoom * x
    zx, zy = -300 + 4 * x, -900 + 4 * y
    assert gs.square_at_pixel(fit, zx, zy, gs.MONAD, pan=(-300, -900), zoom=4) == "SP5820"


def test_mapfit_north_up_and_centred():
    fit = gs.MapFit((0, 0, 100, 200), 300, 400, pad=0)
    assert fit.to_px(0, 0) == (50.0, 400.0)       # equal aspect: 2 px per metre, centred in x
    assert fit.to_px(100, 200) == (250.0, 0.0)


def test_visible_extent_unzoomed_and_zoomed():
    fit = gs.MapFit((0, 0, 100, 100), 100, 100, pad=0)
    assert gs.visible_extent(fit) == (0, 0, 100, 100)
    assert gs.visible_extent(fit, (-50, -50), 2.0) == (25, 25, 75, 75)


def test_extent_of_squares():
    e0, n0, e1, n1 = gs.extent_of(["SP5820", "SP6020"], margin=0, min_span=0)
    assert (e0, e1) == (458000, 461000) and n1 - n0 == 3000


# ---------------------------------------------------------------- print sizing (H5)

def test_print_sizes():
    assert gs.print_size_px("A4", 300) == (2480, 3508)
    assert gs.print_size_px("A4", 300, landscape=True) == (3508, 2480)
    assert gs.print_size_px("A3", 150) == (1754, 2480)
    assert gs.dots_per_metre(300) == 11811


# ---------------------------------------------------------------- styling and ranking

def test_square_style_classes():
    from src.views.mapping.square_style import colour_squares, density_class, style_key
    assert [density_class(n) for n in (1, 2, 4, 5, 19, 20, 500)] == [0, 1, 1, 2, 2, 3, 3]
    assert style_key("Density (colour gradient)") == "density"
    assert style_key("Date classes (time period)") == "date"
    sq = {"A": {"count": 1, "band": "recent"}, "B": {"count": 30, "band": "current"}}
    legend = colour_squares(sq, "date", {"historical": "#111111", "recent": "#222222",
                                         "current": "#333333"},
                            {"recent": "2000-2019", "current": "2020+"}, "#ffffff", "#000000")
    assert sq["A"]["fill"] == "#222222" and [lab for _c, lab in legend] == ["2000-2019", "2020+"]
    legend = colour_squares(sq, "presence", {}, {}, "#ffffff", "#000000")
    assert legend == [("#000000", "Recorded")] and sq["B"]["fill"] == "#000000"


def test_rank_species_scientific_prefix_first():
    from src.services.map_square_service import rank_species
    res = [{"scientific_name": "Hydrometra stagnorum", "common_name": "Water Measurer", "records": 2},
           {"scientific_name": "Dorcus parallelipipedus", "common_name": "Lesser Stag Beetle",
            "records": 37},
           {"scientific_name": "Lucanus cervus", "common_name": "Stag Beetle", "records": 3}]
    out = [r["scientific_name"] for r in rank_species("stag beetle", res)]
    assert out[0] == "Lucanus cervus"          # common name starts with the text
    assert out[1] == "Dorcus parallelipipedus"


def test_records_in_square_uses_map_rule():
    from src.services.map_square_service import records_in_square
    recs = [{"grid_ref": "SP580207"}, {"grid_ref": "SP58"}, {"grid_ref": "SP5920"}]
    assert records_in_square(recs, "SP5820", gs.MONAD) == [recs[0]]
    assert len(records_in_square(recs, "SP52", gs.HECTAD)) == 2


# ---------------------------------------------------------------- widgets and shims (H1, H2)

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_data_entry_shims_are_the_shared_modules():
    import DataEntry._panzoom as a1
    import DataEntry.gb_basemap as a2
    import DataEntry.raster_map as a3
    import DataEntry.species_dist_map as a4
    import DataEntry.vc_map as a5
    from shared.maps import gb_basemap, panzoom, raster_map, species_dist_map, vc_map
    with open(a1.__file__, encoding="utf-8") as f:
        if "shared.maps" not in f.read():
            pytest.skip("the Data Entry map shims have not landed yet (held while Wil enters data)")
    assert a1.PanZoomMixin is panzoom.PanZoomMixin
    assert a2.gb_basemap_path is gb_basemap.gb_basemap_path and a2._BASENAME == gb_basemap._BASENAME
    assert a3.RasterMiniMap is raster_map.RasterMiniMap and a3._CACHE is raster_map._CACHE
    assert a4.DistributionMiniMap is species_dist_map.DistributionMiniMap
    assert a4.SOURCE_ORDER is species_dist_map.SOURCE_ORDER
    assert a5.load_vc_polygons is vc_map.load_vc_polygons


def test_grid_map_click_and_sheet(qapp):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent
    from shared.maps.grid_map import GridMap
    m = GridMap()
    m.resize(400, 700)
    m.set_squares({"SP5820": {"count": 3, "fill": "#9a7555"}}, gs.MONAD)
    m.set_extent((455000, 217000, 462000, 224000))
    got = []
    m.square_clicked.connect(got.append)
    x, y = m.fit().to_px(458500, 220500)
    for kind, btns in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
                       (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
        ev = QMouseEvent(kind, QPointF(x, y), QPointF(x, y), Qt.MouseButton.LeftButton, btns,
                         Qt.KeyboardModifier.NoModifier)
        (m.mousePressEvent if kind == QEvent.Type.MouseButtonPress else m.mouseReleaseEvent)(ev)
    assert got == ["SP5820"]
    img = m.render_sheet("Test", legend=[("#9a7555", "Recorded")])
    assert (img.width(), img.height()) == (2480, 3508)
    assert img.dotsPerMeterX() == gs.dots_per_metre(300)
