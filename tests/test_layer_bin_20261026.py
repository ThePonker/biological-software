"""Binary map layers (shared/maps/layer_bin.py), the Identify prefilter, settings kept in memory and
the separate layers picture (26 Oct 2026). Small purpose-made layer files in tmp_path."""
import json
# ruff: noqa: F811  (pytest fixtures imported from test_map_layers_r11)
import os
import random
from itertools import chain

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QDataStream, QIODevice, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QPainterPath, QPolygonF  # noqa: E402

from shared.maps import layer_bin, layer_opacity, layers  # noqa: E402
from tests.test_map_layers_r11 import (_map, _sq, _write, qapp,  # noqa: E402,F401
                                       settings_sandbox)


def _random_features(n=60, seed=3):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        e0, n0 = rnd.randrange(0, 90000), rnd.randrange(0, 90000)
        w, h = rnd.randrange(50, 9000), rnd.randrange(50, 9000)
        f = _sq(e0, n0, e0 + w, n0 + h, hole=(e0 + w // 4, n0 + h // 4, e0 + w // 2, n0 + h // 2) if i % 3 == 0 else None)
        if i % 2:
            f["t"] = ("Ancient", "Replanted", "")[i % 3]
        if i % 5 == 0:
            f["n"] = f"Wood {i}"
        if i % 7 == 0:
            f["a"] = [["Area", f"{i} ha"]]
            f["u"] = f"https://example.org/{i}"
        out.append(f)
    return out


def _old_path(feats, line=False):
    """What map_layers._build_path did before (a QPointF per point)."""
    path = QPainterPath()
    if line:
        for f in feats:
            path.addPolygon(QPolygonF([QPointF(e, n) for e, n in f["line"]]))
        return path
    path.setFillRule(Qt.FillRule.WindingFill)
    for f in feats:
        for ring in f["rings"]:
            path.addPolygon(QPolygonF([QPointF(e, n) for e, n in ring]))
            path.closeSubpath()
    return path


def _same(a, b):
    assert a.elementCount() == b.elementCount() and a.boundingRect() == b.boundingRect()
    assert a.fillRule() == b.fillRule()
    for i in range(a.elementCount()):
        x, y = a.elementAt(i), b.elementAt(i)
        assert (x.type, x.x, x.y) == (y.type, y.x, y.y)


def _make(tmp_path, key, lod, feats, kind="polygon"):
    _write(tmp_path, key, lod, feats, kind)
    jp = tmp_path / "layers" / f"{key}_{lod}.json"
    doc = json.loads(jp.read_text(encoding="utf-8"))
    layer_bin.write(jp, doc["features"], {k: v for k, v in doc.items() if k != "features"})
    return jp


# ---------------------------------------------------------------- the format

def test_every_kind_round_trips(tmp_path):
    feats = _random_features() + [
        {"bbox": [0, 0, 5, 5], "line": [[0, 0], [5, 5]], "n": "Road", "t": "A"},
        {"bbox": [7, 7, 7, 7], "pt": [7, 7], "n": "Hamlet", "t": "village"},
        {"bbox": [1, 1, 9, 9], "rings": [[[1, 1], [9, 1], [9, 9]]], "name": "Cherwell"},     # an open ring
        {"bbox": [0, 0, 1.5, 1.5], "rings": [[[0, 0], [1.5, 0], [1.5, 1.5], [0, 0]]]}]   # not whole metres
    jp = _make(tmp_path, "sssi", "county", feats)
    data = layer_bin.read(jp)
    assert data is not None and len(data) == len(feats)
    assert [dict(f) for f in data] == feats and data[0] == feats[0] and data[-1] == feats[-1]
    assert data.header["layer"] == "sssi" and data.header["lod"] == "county"
    assert data.coords.dtype == np.float64            # the half metre made the points floats
    jp2 = _make(tmp_path, "woodland", "county", _random_features())
    assert layer_bin.read(jp2).coords.dtype == np.int32


def test_a_stale_or_partial_binary_is_ignored(tmp_path):
    jp = _make(tmp_path, "woodland", "county", [_sq(0, 0, 10, 10)])
    assert isinstance(layers.load(tmp_path, "woodland", "county"), layer_bin.LayerBin)
    layers.forget("woodland")
    _write(tmp_path, "woodland", "county", [_sq(0, 0, 10, 10), _sq(20, 20, 30, 30)])   # JSON rebuilt alone
    got = layers.load(tmp_path, "woodland", "county")
    assert isinstance(got, list) and len(got) == 2
    layers.forget("woodland")
    jp = _make(tmp_path, "woodland", "county", [_sq(0, 0, 10, 10)])
    layer_bin.array_path(jp, "bbox").write_bytes(b"junk")
    assert layer_bin.read(jp) is None and isinstance(layers.load(tmp_path, "woodland", "county"), list)
    layers.forget("woodland")


def test_json_only_gives_the_same_dicts_as_before(tmp_path):
    feats = _random_features(10)
    _write(tmp_path, "towns", "county", feats)
    assert layers.load(tmp_path, "towns", "county") == feats
    layers.forget("towns")


# ---------------------------------------------------------------- paths

@pytest.mark.parametrize("box", [(0, 0, 100000, 100000), (10000, 10000, 40000, 50000),
                                 (80000, 80000, 90000, 90000), (500000, 0, 600000, 10)])
def test_paths_equal_the_old_builder(tmp_path, box):
    feats = _random_features(200, seed=9)
    jp = _make(tmp_path, "woodland", "county", feats)
    data = layer_bin.read(jp)
    idx = data.in_box(box)
    old = _old_path(layers.features_in(feats, box))
    _same(data.path(idx), old)
    _same(layer_bin.lists_path([r for f in layers.features_in(feats, box) for r in f["rings"]], True), old)
    assert [f["bbox"] for f in layers.features_in(data, box)] == [f["bbox"] for f in layers.features_in(feats, box)]


def test_the_stream_bytes_are_qts_own(tmp_path):
    feats = _random_features(30)
    mine = layer_bin.read(_make(tmp_path, "woodland", "county", feats)).path()

    def ser(p):
        ba = QByteArray()
        s = QDataStream(ba, QIODevice.OpenModeFlag.WriteOnly)
        s << p
        return bytes(ba)
    assert ser(mine) == ser(_old_path(feats))


def test_lines_and_open_rings_and_districts(tmp_path):
    lines = [{"bbox": [0, 0, 9, 9], "line": [[0, 0], [5, 5], [9, 0]]},
             {"bbox": [2, 2, 8, 8], "line": [[2, 2], [8, 8]]}]
    data = layer_bin.read(_make(tmp_path, "roads", "county", lines, "line"))
    _same(data.path(closed=False), _old_path(lines, line=True))
    openr = [{"bbox": [0, 0, 9, 9], "rings": [[[0, 0], [9, 0], [9, 9]], [[1, 1], [2, 2]]]}]
    _same(layer_bin.read(_make(tmp_path, "towns", "county", openr)).path(), _old_path(openr))
    from shared.maps.map_layers import BasemapLayersMixin
    d = [_sq(0, 0, 10, 10), _sq(10, 0, 20, 10)]
    data = layer_bin.read(_make(tmp_path, "districts", "county", d))
    _same(BasemapLayersMixin._build_path_bin("districts", data, data.in_box((0, 0, 20, 10))),
          BasemapLayersMixin._build_path("districts", d))
    _same(BasemapLayersMixin._build_path("roads", lines), _old_path(lines, line=True))


def test_the_map_draws_the_same_from_json_and_binary(qapp, tmp_path, settings_sandbox):
    feats = _random_features(80, seed=5)
    for f in feats:
        f["t"] = f.get("t") or "Ancient"
    jdir, bdir = tmp_path / "j", tmp_path / "b"
    jdir.mkdir()
    bdir.mkdir()
    for d, binary in ((jdir, False), (bdir, True)):
        (_make if binary else _write)(d, "land", "county", [_sq(0, 0, 100000, 100000)])
        (_make if binary else _write)(d, "ancient_woodland", "county", feats)
    mj, mb = _map(jdir), _map(bdir)
    assert isinstance(layers.load(str(bdir), "land", "county"), layer_bin.LayerBin)
    for key in ("land", "ancient_woodland"):
        _same(mb._layer_shape(mb.fit(), key), mj._layer_shape(mj.fit(), key))
    mj.set_layers({"ancient_woodland"})
    mb.set_layers({"ancient_woodland"})
    assert mb._layer_classes(mb.fit(), "ancient_woodland") == mj._layer_classes(mj.fit(), "ancient_woodland")
    for c in mb._layer_classes(mb.fit(), "ancient_woodland"):
        _same(mb._layer_shape(mb.fit(), "ancient_woodland", cls=c),
              mj._layer_shape(mj.fit(), "ancient_woodland", cls=c))
    assert mb.grab().toImage() == mj.grab().toImage()


def test_no_point_objects_are_made_for_a_big_polygon():
    pts = [[i, (i * 7) % 1000] for i in range(50000)]
    p = layer_bin.lists_path([pts], True)
    assert p.elementCount() >= 50000


# ---------------------------------------------------------------- identify prefilter

def test_candidates_hold_the_point_and_hits_do_not_change(tmp_path):
    from shared.maps.identify import feature_covers
    feats = _random_features(300, seed=11)
    jp = _make(tmp_path, "woodland", "county", feats)
    data = layer_bin.read(jp)
    rnd = random.Random(1)
    for _ in range(200):
        e, n = rnd.randrange(0, 100000), rnd.randrange(0, 100000)
        want = [f for f in feats if feature_covers(f, e, n)]
        assert [dict(f) for f in layers.candidates(feats, e, n) if feature_covers(f, e, n)] == want
        assert [dict(f) for f in layers.candidates(data, e, n) if feature_covers(f, e, n)] == want
        assert all(f["bbox"][0] <= e <= f["bbox"][2] for f in layers.candidates(feats, e, n))
    assert layers.candidates([], 1, 1) == []
    assert len(layers.candidates([{"rings": [[[0, 0]]]}], 5, 5)) == 1       # no bbox: kept


# ---------------------------------------------------------------- settings in memory

def test_colours_and_opacities_are_kept_in_memory(qapp, settings_sandbox, monkeypatch):
    from PySide6.QtCore import QSettings
    assert layers.saved_colour("woodland") is None
    layers.set_colour("woodland", "#336699")
    layer_opacity.set_opacity("sssi", 33)
    assert layers.saved_colour("woodland").name() == "#336699" and layer_opacity.opacity("sssi") == 33
    assert layers.saved_colours()[[t.key for t in layers.TOGGLES].index("woodland")] == "#336699"
    layers.reset_colours()
    layer_opacity.reset_opacities()
    assert layers.saved_colour("woodland") is None and layer_opacity.saved_opacity("sssi") is None
    assert QSettings().value("mapping/layer_opacity/sssi") is None
    layers.set_colour("roads", "#010203")
    layer_opacity.set_opacity("sssi", 150)
    assert layer_opacity.opacity("sssi") == 100

    made = []
    real = QSettings

    class Counting(real):
        def __init__(self, *a, **k):
            made.append(1)
            super().__init__(*a, **k)
    monkeypatch.setattr(layers, "QSettings", Counting)
    monkeypatch.setattr(layer_opacity, "QSettings", Counting)
    for _ in range(5):
        layers.saved_colours(), layer_opacity.saved_opacities(), layers.style("woodland")
        layer_opacity.alpha("sssi")
    assert made == []


def test_a_paint_does_not_read_settings(qapp, tmp_path, settings_sandbox, monkeypatch):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    m = _map(tmp_path)
    m.grab()
    made = []
    from PySide6.QtCore import QSettings as real

    class Counting(real):
        def __init__(self, *a, **k):
            made.append(1)
            super().__init__(*a, **k)
    monkeypatch.setattr(layers, "QSettings", Counting)
    monkeypatch.setattr(layer_opacity, "QSettings", Counting)
    m.set_squares({"SP5020": {"count": 1, "fill": "#a63d40"}}, 10000)
    m.grab()
    m.grab()
    assert made == []


# ---------------------------------------------------------------- the layers picture

def test_squares_opacity_and_labels_do_not_redraw_the_layers(qapp, tmp_path, settings_sandbox, monkeypatch):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    _write(tmp_path, "woodland", "county", [_sq(10000, 10000, 40000, 40000)])
    m = _map(tmp_path)
    m.set_layers({"woodland"})
    calls = []
    real = m.draw_base
    monkeypatch.setattr(m, "draw_base", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    m.grab()
    assert len(calls) == 1 and m.layer_renders == 1 and m.picture_renders == 1
    m.set_squares({"SP5020": {"count": 1, "fill": "#a63d40"}}, 10000)
    m.grab()
    m.set_square_opacity(50)
    m.grab()
    m.set_vc_labels(True)
    m.grab()
    m.set_outlined_vc(23)
    m.grab()
    assert len(calls) == 1 and m.layer_renders == 1 and m.picture_renders >= 3
    m.set_layers({"woodland", "water"})
    m.grab()
    assert len(calls) == 2 and m.layer_renders == 2
    layers.set_colour("woodland", "#ff0000")
    m.grab()
    assert m.layer_renders == 3


def test_the_squares_are_drawn_over_the_kept_layers(qapp, tmp_path, settings_sandbox):
    _write(tmp_path, "land", "county", [_sq(0, 0, 100000, 100000)])
    m = _map(tmp_path)
    m.grab()
    before = m.grab().toImage()
    from shared.maps import grid_squares as gs
    lab = gs.square_for_point(25500, 25500, 10000)
    m.set_squares({lab: {"count": 1, "fill": "#a63d40"}}, 10000)
    after = m.grab().toImage()
    assert before != after and m.layer_renders == 1
    e, n = 25500, 25500
    x, y = m.fit().to_px(e, n)
    assert after.pixelColor(int(x), int(y)) != before.pixelColor(int(x), int(y))


# ---------------------------------------------------------------- converter

def test_converter_dry_run_changes_nothing_and_apply_writes(tmp_path, capsys):
    from scripts import convert_layers_bin as conv
    _write(tmp_path, "woodland", "county", _random_features(20))
    (tmp_path / "layers" / "relief_gb.json").write_text(json.dumps({"layer": "relief", "kind": "image"}))
    d = tmp_path / "layers"
    before = {p.name: p.read_bytes() for p in d.iterdir()}
    assert conv.main(["--dir", str(d)]) == 0
    out = capsys.readouterr().out
    assert "Nothing has been changed." in out and "woodland_county.json: would write" in out
    assert {p.name for p in d.iterdir()} == set(before)
    assert conv.main(["--dir", str(d), "--apply"]) == 0
    assert "relief_gb.json: no features" in capsys.readouterr().out
    assert all(p.is_file() for p in layer_bin.all_paths(d / "woodland_county.json"))
    assert all((d / n).read_bytes() == b for n, b in before.items())      # the JSON is untouched
    assert not list(d.glob("*.tmp"))
    assert isinstance(layers.load(tmp_path, "woodland", "county"), layer_bin.LayerBin)
    layers.forget("woodland")


def test_write_doc_writes_the_binary_too(tmp_path):
    from scripts.build_map_layers import write_doc
    feats = [_sq(0, 0, 10, 10)]
    write_doc(tmp_path, "woodland", "gb", "polygon", "src", "attr", 25, 1000, feats, 1)
    assert layer_bin.exists(tmp_path / "woodland_gb.json")
    assert [dict(f) for f in layer_bin.read(tmp_path / "woodland_gb.json")] == feats
    assert list(chain.from_iterable([[]])) == []
