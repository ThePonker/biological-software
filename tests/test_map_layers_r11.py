"""Mapping tab, Round 11 (17 Oct 2026): the map background layers (shared/maps/layers.py) and
the "Layers" menu. Small purpose-made layer files in tmp_path; nothing from Wil's data.
"""
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import layers  # noqa: E402

ATTR = layers.OS_CREDIT
BOX = (0, 0, 100000, 100000)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings_sandbox(qapp):
    from PySide6.QtCore import QCoreApplication, QSettings
    org = QCoreApplication.organizationName()
    QCoreApplication.setOrganizationName("ObservatumTests_map_layers_r11")
    QSettings().clear()
    yield
    QSettings().clear()
    QCoreApplication.setOrganizationName(org)


def _write(maps_dir, key, lod, features, kind="polygon"):
    d = maps_dir / "layers"
    d.mkdir(exist_ok=True)
    (d / f"{key}_{lod}.json").write_text(json.dumps(
        {"layer": key, "lod": lod, "kind": kind, "attribution": ATTR, "features": features}),
        encoding="utf-8")


def _sq(e0, n0, e1, n1, hole=None):
    rings = [[[e0, n0], [e1, n0], [e1, n1], [e0, n1], [e0, n0]]]
    if hole:
        h0, k0, h1, k1 = hole
        rings.append([[h0, k0], [h0, k1], [h1, k1], [h1, k0], [h0, k0]])
    return {"bbox": [e0, n0, e1, n1], "rings": rings}


def _map(maps_dir):
    from shared.maps.grid_map import GridMap
    m = GridMap(geojson_path=None, maps_dir=str(maps_dir))
    m.resize(300, 300)
    m.set_extent(BOX)
    return m


def _pixel(m, e, n):
    img = m.grab().toImage()
    x, y = m.fit().to_px(e, n)
    return img.pixelColor(int(x), int(y)).name()


# ---------------------------------------------------------------- loader

def test_lod_rule_matches_the_grid_rule():
    assert layers.lod_for_extent((0, 0, 250000, 10)) == "county"
    assert layers.lod_for_extent((0, 0, 250001, 10)) == "gb"
    assert layers.lod_for_extent((0, 0, 10, 300000)) == "gb"


def test_load_cache_and_bbox_filter(tmp_path):
    _write(tmp_path, "woodland", "county", [_sq(0, 0, 10, 10), _sq(500, 500, 600, 600)])
    a = layers.load(tmp_path, "woodland", "county")
    assert len(a) == 2 and layers.load(tmp_path, "woodland", "county") is a   # cached
    assert len(layers.features_in(a, (5, 5, 20, 20))) == 1
    assert len(layers.features_in(a, (0, 0, 1000, 1000))) == 2
    assert layers.features_in(a, (2000, 2000, 3000, 3000)) == []
    assert len(layers.features_in([{"rings": [[[0, 0]]]}], (5, 5, 6, 6))) == 1   # no bbox: kept


def test_missing_lod_falls_back_to_the_other(tmp_path):
    _write(tmp_path, "towns", "gb", [_sq(0, 0, 10, 10)])
    assert len(layers.load(tmp_path, "towns", "county")) == 1
    _write(tmp_path, "roads", "county", [{"bbox": [0, 0, 5, 5], "line": [[0, 0], [5, 5]]}], "line")
    assert len(layers.load(tmp_path, "roads", "gb")) == 1
    assert layers.available(tmp_path) == {"towns", "roads"}


def test_missing_folder_or_bad_file_gives_nothing(tmp_path):
    assert layers.available(tmp_path) == set() and layers.load(tmp_path, "land", "gb") == []
    assert layers.available(None) == set() and layers.load(None, "land", "gb") == []
    (tmp_path / "layers").mkdir()
    (tmp_path / "layers" / "land_gb.json").write_text("{not json", encoding="utf-8")
    assert layers.load(tmp_path, "land", "gb") == []


def test_defaults_rivers_and_lakes_only():
    assert layers.defaults() == {"water"}
    assert [t.label for t in layers.TOGGLES] == ["Woodland", "Towns", "Rivers and lakes",
                                                 "Main roads"]


# ---------------------------------------------------------------- the map

def test_without_layer_files_the_map_is_as_before(qapp, tmp_path):
    m = _map(tmp_path)
    assert not m.has_basemap() and not m.has_districts() and m.layers_drawn() == []
    m.grab()                                             # draws without a fault
    assert ATTR not in m.credit_line("x") and "Produced" in m.credit_line("x")


def test_land_comes_from_the_layer_file_with_holes_and_coast(qapp, tmp_path, monkeypatch):
    _write(tmp_path, "land", "county", [_sq(20000, 20000, 80000, 80000, (40000, 40000, 60000, 60000))])
    m = _map(tmp_path)
    assert m.has_basemap() and m.layers_drawn() == ["land"]
    seen = []
    for name in ("_draw_land", "_draw_layer_land"):
        real = getattr(m, name)
        monkeypatch.setattr(m, name, lambda *a, _n=name, _r=real, **k: (seen.append(_n), _r(*a, **k))[1])
    land_c, sea_c = "#e7ece3", "#dbe9f4"
    assert _pixel(m, 35500, 35500) == land_c
    assert _pixel(m, 55500, 55500) == sea_c               # the hole is not filled
    assert _pixel(m, 15500, 15500) == sea_c
    assert set(seen) == {"_draw_layer_land"}
    shape = m._layer_shape(m.fit(), "land")
    assert shape.elementCount() >= 8                       # both rings: the hole's edge is coast too


def test_layers_draw_when_ticked_and_in_registry_order(qapp, tmp_path):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "woodland", "county", [_sq(10000, 10000, 40000, 40000)])
    _write(tmp_path, "water", "county", [_sq(60000, 60000, 90000, 90000)])
    m = _map(tmp_path)
    plain = _pixel(m, 25500, 25500)
    assert m.layers_drawn() == ["land", "water"]           # defaults: rivers and lakes on
    assert _pixel(m, 75500, 75500) != plain                 # water is drawn
    m.set_layers({"water", "woodland"})
    assert m.layers_drawn() == ["land", "woodland", "water"]
    assert _pixel(m, 25500, 25500) != plain                 # woodland now
    m.set_layers(set())
    assert m.layers_drawn() == ["land"] and _pixel(m, 25500, 25500) == plain
    m.set_layers({"roads"})                                 # ticked but not installed: nothing
    assert m.layers_drawn() == ["land"]


def test_layer_districts_switch_and_each_edge_once(qapp, tmp_path):
    _write(tmp_path, "districts", "county", [
        {**_sq(0, 0, 50000, 100000), "name": "A"}, {**_sq(50000, 0, 100000, 100000), "name": "B"}])
    m = _map(tmp_path)
    assert m.has_districts() and m.layers_drawn() == []
    m.set_districts(True)
    assert m.layers_drawn() == ["districts"]
    chains = m._layer_shape(m.fit(), "districts")
    edges = sum(c.count() - 1 for c in chains)
    assert edges == 7                                       # 8 edges, the shared one once
    m.grab()


def test_credit_line_is_built_from_what_is_drawn(qapp, tmp_path):
    from shared.maps.atlas_sheet import COAST_CREDIT
    _write(tmp_path, "land", "gb", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "woodland", "gb", [_sq(0, 0, 1000, 1000)])
    m = _map(tmp_path)
    c = m.credit_line("foot")
    assert c.count(ATTR) == 1 and COAST_CREDIT not in c and c.startswith("foot")
    m.set_layers({"water", "woodland"})
    assert m.credit_line().count(ATTR) == 1                 # once, however many layers


def test_credit_keeps_the_ons_line_only_while_gb_outline_is_drawn(qapp, tmp_path):
    from shared.maps.atlas_sheet import COAST_CREDIT
    (tmp_path / "gb_outline.json").write_text(json.dumps(
        {"bounds": [0, 0, 100000, 100000],
         "rings": [[[0, 0], [50000, 0], [50000, 50000], [0, 50000], [0, 0]]]}), encoding="utf-8")
    m = _map(tmp_path)
    assert COAST_CREDIT in m.credit_line() and ATTR not in m.credit_line()   # as today
    _write(tmp_path, "land", "gb", [_sq(0, 0, 100000, 100000)])
    m2 = _map(tmp_path)
    assert m2.has_districts()                               # gb_outline.json's districts remain
    assert COAST_CREDIT not in m2.credit_line() and ATTR in m2.credit_line()
    m2.set_districts(True)                                  # drawn from gb_outline.json
    assert COAST_CREDIT in m2.credit_line()
    m2.grab()


# ---------------------------------------------------------------- the menu

def test_menu_items_disabled_when_not_installed_and_remembered(qapp, tmp_path, settings_sandbox):
    from PySide6.QtCore import QSettings
    from src.views.mapping.display_bar import MapDisplayBar, saved_layers
    _write(tmp_path, "woodland", "gb", [_sq(0, 0, 10, 10)])
    m = _map(tmp_path)
    bar = MapDisplayBar()
    bar.attach_map(m)
    acts = bar.layer_actions
    assert [a.text() for a in bar.layers_menu.actions() if a.text()] == [
        "Woodland", "Towns", "Rivers and lakes", "Main roads", "Reset to defaults"]
    assert acts["woodland"].isEnabled() and not acts["towns"].isEnabled()
    assert acts["towns"].toolTip() == "Not installed: run scripts\\build_map_layers.py"
    assert bar.layers() == {"water"} and saved_layers() == {"water"}
    acts["woodland"].setChecked(True)
    assert QSettings().value("mapping/layers/woodland", False, type=bool) is True
    assert saved_layers() == {"water", "woodland"} and m._layers_on == {"water", "woodland"}
    assert MapDisplayBar().layers() == {"water", "woodland"}              # remembered
    bar.reset_layers()
    assert bar.layers() == {"water"} and m._layers_on == {"water"} and saved_layers() == {"water"}


def test_batch_renderer_uses_the_remembered_choices(qapp, tmp_path, monkeypatch, settings_sandbox):
    import paths
    from PySide6.QtCore import QSettings
    from src.services.batch_maps import BatchSettings
    from src.views.mapping.batch_render import BatchRenderer
    monkeypatch.setattr(paths, "MAPS_DIR", tmp_path)
    QSettings().setValue("mapping/layers/towns", True)
    r = BatchRenderer(BatchSettings())
    assert r.map._layers_on == {"water", "towns"}


def test_zoomed_in_on_the_gb_view_uses_county_detail_round_the_view(qapp, tmp_path):
    """17 Oct: the level of detail follows what is on screen, and county detail is only
    taken for the area round the view."""
    _write(tmp_path, "woodland", "gb", [_sq(0, 0, 50000, 50000)])
    _write(tmp_path, "woodland", "county", [_sq(100000, 100000, 110000, 110000),
                                            _sq(600000, 600000, 610000, 610000)])
    m = _map(tmp_path)
    m.set_extent((0, 0, 700000, 700000))
    m.set_layers({"woodland"})
    fit = m.fit()
    m._layer_view = fit.extent                         # the whole GB view: gb detail
    whole = m._layer_shape(fit, "woodland").boundingRect()
    x0, _y = fit.to_px(0, 0)
    assert abs(whole.left() - x0) < 2
    m._layer_view = (90000, 90000, 140000, 140000)     # zoomed in on one 50 km area
    near = m._layer_shape(fit, "woodland")
    xb, _y = fit.to_px(100000, 0)
    assert abs(near.boundingRect().left() - xb) < 2
    assert near.elementCount() == 5                     # only the nearby county feature
