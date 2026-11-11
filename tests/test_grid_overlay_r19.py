"""R19 B2: the grid-square overlay: which levels draw at which scale, the squares' names, the two
ticks (Base map group, off by default, remembered, in the group switch), and the export's "Grid" tick."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import grid_overlay as go, layers  # noqa: E402
from tests import test_map_layers_r11 as r11  # noqa: E402

qapp, settings_sandbox = r11.qapp, r11.settings_sandbox


def test_spacing_follows_scale_and_never_denser_than_8px():
    gb = go.plan(0.0009, True, True)           # all GB on ~1000 px: 100 km is 90 px
    assert (gb.km100, gb.km10, gb.km1, gb.tetrad) == (True, False, False, False)
    assert gb.label100 and not gb.label10
    county = go.plan(0.003, True, True)        # 10 km = 30 px, 2 km = 6 px
    assert (county.km10, county.km1, county.tetrad, county.label10) == (True, False, False, False)
    near = go.plan(0.0125, True, True)         # 1 km = 12.5 px, 2 km = 25 px
    assert (near.km1, near.tetrad, near.letters) == (False, True, False)
    close = go.plan(0.03, True, True)          # 1 km = 30 px, 2 km = 60 px
    assert close.km1 and close.tetrad and close.letters and not close.label1
    assert go.plan(0.08, True, True).label1     # 1 km = 80 px
    assert go.plan(0.03, True, False).tetrad is False       # no Tetrads tick, no tetrads
    assert go.plan(0.03, False, True).km1 is False and go.plan(0.03, False, True).tetrad
    for eff in (0.0009, 0.003, 0.0125, 0.03, 0.08, 0.3):
        p = go.plan(eff, True, True)
        for on, step in ((p.km100, go.KM100), (p.km10, go.KM10), (p.km1, go.KM1), (p.tetrad, go.KM2)):
            assert not on or step * eff >= 8


def test_square_names():
    assert go.square_name(452500, 220500, go.KM10) == "SP52"      # SP 52500 20500
    assert go.square_name(452500, 220500, go.KM100) == "SP"
    assert go.square_name(458000, 220000, go.KM2) == "SP52V"      # tetrad of SP5820
    assert go.square_name(458500, 220500, go.KM1) == "SP5820"


def test_line_path_is_one_path_cut_to_the_box_and_skips_coarser_lines():
    path = go.line_path((450000, 210000, 480000, 230000), go.KM10, skip=go.KM100)
    # verticals at 450, 460, 470, 480 km; horizontals at 210, 220, 230 km: 7 lines, 7 subpaths
    assert len(path.toSubpathPolygons()) == 7
    assert path.boundingRect().left() == 450000 and path.boundingRect().bottom() == 230000
    off = go.line_path((-50000, -50000, 20000, 20000), go.KM10)
    assert off.boundingRect().left() == 0 and off.boundingRect().top() == 0   # not outside the grid


def test_two_ticks_in_base_map_group_off_by_default(qapp, settings_sandbox):
    from src.views.mapping.layers_window import group_members
    keys = group_members()["Base map"]
    assert "grid_lines" in keys and "grid_tetrads" in keys
    t = {x.key: x for x in layers.TOGGLES}
    assert t["grid_lines"].label == "Grid lines (100 km / 10 km / 1 km)" and t["grid_tetrads"].label == "Tetrads"
    assert not t["grid_lines"].default and not t["grid_tetrads"].default
    assert layers.toggle_available(set(), t["grid_lines"])         # needs no file


def test_ticks_persist_and_follow_the_group_switch(qapp, settings_sandbox):
    from src.views.mapping.display_bar import MapDisplayBar, saved_layers
    bar = MapDisplayBar()
    assert not bar.layer_actions["grid_lines"].isChecked()
    bar.layer_actions["grid_lines"].setChecked(True)
    bar.layer_actions["grid_tetrads"].setChecked(True)
    assert {"grid_lines", "grid_tetrads"} <= saved_layers()
    bar.set_group_on("Base map", False)
    assert not bar.layers() & {"grid_lines", "grid_tetrads", "water"}
    bar.set_group_on("Base map", True)
    assert {"grid_lines", "grid_tetrads", "water"} <= bar.layers()
    assert {"grid_lines", "grid_tetrads"} <= MapDisplayBar().layers()    # a new start


def test_export_has_a_grid_tick_off_by_default():
    from src.views.mapping.atlas_export import EXPORT_DEFAULTS, EXPORT_OPTIONS, EXTRAS_OPTIONS
    assert ("grid", "Grid (square lines and names)") in EXPORT_OPTIONS
    assert EXPORT_DEFAULTS["grid"] is False and "grid" not in EXTRAS_OPTIONS


def _map(tmp_path):
    from tests.test_map_picture import _map as mk
    return mk(tmp_path)


def test_page_has_the_grid_only_when_asked(qapp, tmp_path):
    m = _map(tmp_path)
    m.set_layers({"grid_lines", "grid_tetrads"})          # ticked on the screen
    seen = []
    real = go.draw
    import shared.maps.map_layers as ml
    ml.grid_overlay.draw = lambda *a: seen.append(a[-2:]) or real(*a)
    try:
        m.render_sheet("t", dpi=60)
        assert seen == []                                  # the page says no grid: none drawn
        m.render_sheet("t", dpi=60, grid=True)
        assert seen == [(True, True)]                      # same overlay; Tetrads tick followed
        m.set_layers({"grid_lines"})
        m.render_sheet("t", dpi=60, grid=True)
        assert seen[-1] == (True, False)
    finally:
        ml.grid_overlay.draw = real
    assert m._grid_force is None
