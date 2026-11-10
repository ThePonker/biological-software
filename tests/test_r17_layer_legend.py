"""R17 A3: the background-layer legend on the atlas page. Small made-up layer files in tmp_path."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import env_classes, layer_legend, layers  # noqa: E402
from shared.maps import grid_squares as gs  # noqa: E402
from tests import test_map_layers_r11 as r11  # noqa: E402
from tests.test_export_preview_20261026 import ALL, NONE, make_host  # noqa: E402

qapp, settings_sandbox = r11.qapp, r11.settings_sandbox

SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_r17_shots")
os.makedirs(SHOTS, exist_ok=True)
CLASSES = list(env_classes.BEDROCK)[:14]          # 14 classes: more than the 12 shown


def _maps(tmp_path, far_class=True):
    r11._write(tmp_path, "land", "county", [r11._sq(0, 0, 700000, 1300000)])
    r11._write(tmp_path, "woodland", "county", [r11._sq(430000, 200000, 450000, 230000)])
    r11._write(tmp_path, "rivers", "county", [{"bbox": [430000, 200000, 450000, 230000],
                                              "line": [[430000, 200000], [450000, 230000]]}],
               kind="line")
    feats = []
    for i, c in enumerate(CLASSES):
        f = r11._sq(430000 + i * 1000, 200000, 431000 + i * 1000, 205000)
        f["t"] = c
        feats.append(f)
    if far_class:
        f = r11._sq(600000, 900000, 610000, 910000)       # far from the page
        f["t"] = "Precambrian"
        feats.append(f)
    r11._write(tmp_path, "geology_bedrock", "county", feats)
    return tmp_path


def _host(qapp, tmp_path, ticks):
    from shared.maps.grid_map import GridMap
    h = make_host(qapp)
    m = GridMap(geojson_path=None, maps_dir=str(tmp_path))
    m.resize(800, 800)
    m.set_squares(h._squares, gs.HECTAD)
    m.set_layers(ticks)
    h.map_widget = m
    return h


def _box(h):
    return h.map_widget.sheet_view("full", dpi=300, legend=h._legend)[1]


def test_plain_and_classed_groups(qapp, tmp_path, settings_sandbox):
    h = _host(qapp, _maps(tmp_path), {"woodland", "geology_bedrock"})
    groups = h.map_widget.layer_legend_groups(_box(h))
    by = {g.name: g for g in groups}
    wood, geo = by["Woodland"], by["Bedrock geology (BGS 625k)"]
    assert not wood.classed and len(wood.swatches) == 1 and wood.swatches[0][1] == "Woodland"
    assert wood.swatches[0][0].lower() == layer_legend._plain_colour(
        next(t for t in layers.visible_toggles() if t.key == "woodland")).lower()
    assert geo.classed and len(geo.swatches) == 12 and geo.more == 3     # 15 classes on the full page, 12 shown
    assert all(hx == env_classes.class_colour("geology_bedrock", c) for hx, c in geo.swatches)


def test_only_classes_inside_the_extent(qapp, tmp_path, settings_sandbox):
    h = _host(qapp, _maps(tmp_path), {"geology_bedrock"})
    near = (435000, 202000, 437000, 204000)
    (g,) = layer_legend.build(str(tmp_path), {"geology_bedrock"}, h.map_widget._layer_files, near)
    assert 1 <= len(g.swatches) <= 5 and g.more == 0
    assert "Precambrian" not in [lab for _h, lab in g.swatches]        # its feature is far away


def test_unticked_layers_are_not_listed(qapp, tmp_path, settings_sandbox):
    h = _host(qapp, _maps(tmp_path), {"woodland"})
    assert [g.name for g in h.map_widget.layer_legend_groups(_box(h))] == ["Woodland"]
    h.map_widget.set_layers(set())
    assert h.map_widget.layer_legend_groups(_box(h)) == []


def test_option_off_leaves_the_page_as_it_was(qapp, tmp_path, settings_sandbox):
    h = _host(qapp, _maps(tmp_path), {"woodland", "geology_bedrock"})
    off = h.render_atlas("full", NONE, dpi=100)
    on = h.render_atlas("full", {**NONE, "layer_legend": True}, dpi=100)
    assert on != off
    plain = _host(qapp, _maps(tmp_path), set())
    assert plain.render_atlas("full", {**NONE, "layer_legend": True}, dpi=100) \
        == plain.render_atlas("full", NONE, dpi=100)


@pytest.mark.parametrize("opts", [{**ALL, "layer_legend": True}, {**NONE, "layer_legend": True},
                                  {**ALL, "layer_legend": False}, NONE])
def test_legend_does_not_overlap_anything(qapp, tmp_path, settings_sandbox, opts):
    """Measure the blocks under the map on a 300 dpi page: the squares' legend, the layer
    legend and the credits must stack without overlapping, and the map keeps its size."""
    from PySide6.QtGui import QImage
    from shared.maps import extras_panel
    h = _host(qapp, _maps(tmp_path), {"woodland", "water", "rivers", "geology_bedrock"})
    mw = h.map_widget
    ext, shown = mw.sheet_view("full", dpi=300, legend=h._legend)
    extras = h.export_extras(opts, "full", shown)
    groups = mw.layer_legend_groups(shown) if opts.get("layer_legend") else ()
    w, hpx, _l = mw._sheet_size(mw.resolve_extent("full"), "A4", 300)
    dev = QImage(1, 1, QImage.Format.Format_RGB32)
    mm = 300 / 25.4
    footer = h.atlas_footer("full", shown)
    reserve = mw._reserve_mm(w, 300, h._legend, footer, dev, groups)
    extras_mm = extras_panel.height_mm(extras, w, 300, dev) if extras else 0.0
    total = reserve + extras_mm
    legend_rows = mw._legend_rows(h._legend, w, mm, dev)
    lrows = layer_legend.rows_mm(groups, dev, mm, w - 24 * mm) / layer_legend.ROW_MM
    block_end = 4 + extras_mm + (legend_rows + lrows) * 6 - 2        # mm under the map's bottom
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QFontMetricsF
    from shared.maps.atlas_sheet import _font
    ch = QFontMetricsF(_font(7), dev).boundingRect(
        QRectF(0, 0, w - 2 * 12 * mm, 10 ** 6),
        int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
        mw.credit_line(footer)).height() / mm
    credit_top = total - ch
    assert block_end <= credit_top, (block_end, credit_top)
    img = h.render_atlas("full", opts, dpi=100)
    assert img.width() > 0
    img.save(os.path.join(SHOTS, f"legend_{sum(opts.values())}_{int(bool(opts.get('layer_legend')))}.png"))
