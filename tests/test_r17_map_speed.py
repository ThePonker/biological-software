"""R17 A7: map speed leftovers: the GB outline's disk cache. Made-up outline in tmp_path."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from shared.maps import species_dist_map as sdm  # noqa: E402


@pytest.fixture(scope="module")
def qapp_a7():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _outline(d, rings, bounds=(0, 0, 700000, 1300000)):
    (d / "gb_outline.json").write_text(json.dumps({"rings": rings, "bounds": list(bounds)}),
                                       encoding="utf-8")


def _fresh(d):
    sdm._OUTLINE_CACHE.clear()
    return sdm._load_gb_outline(str(d))


def test_outline_second_read_comes_from_the_cache_and_is_identical(tmp_path, monkeypatch):
    monkeypatch.delenv("BIOSOFT_NO_MAP_CACHE", raising=False)
    rings = [[[1.5, 2.5], [10, 2.5], [10, 9], [1.5, 2.5]], [[100, 100], [200, 100], [200, 200]]]
    _outline(tmp_path, rings)
    first = _fresh(tmp_path)
    assert (tmp_path / "cache" / "gb_outline.rings.npz").is_file()
    real_open = open

    def no_json(path, *a, **k):
        assert not str(path).endswith("gb_outline.json"), "JSON was read again"
        return real_open(path, *a, **k)
    monkeypatch.setattr("builtins.open", no_json)
    second = _fresh(tmp_path)
    monkeypatch.undo()
    assert second == first
    assert first[0][0][0] == [(1.5, 2.5), (10.0, 2.5), (10.0, 9.0), (1.5, 2.5)]
    assert first[1] == (0.0, 0.0, 700000.0, 1300000.0)


def test_changed_json_is_read_again(tmp_path, monkeypatch):
    monkeypatch.delenv("BIOSOFT_NO_MAP_CACHE", raising=False)
    _outline(tmp_path, [[[1, 1], [2, 2], [3, 1]]])
    _fresh(tmp_path)
    _outline(tmp_path, [[[5, 5], [6, 6], [7, 5], [5, 5]]], bounds=(1, 2, 3, 4))
    os.utime(tmp_path / "gb_outline.json", ns=(1, 1_700_000_000_000_000_000))   # a new mtime
    rings, bounds = _fresh(tmp_path)
    assert rings[0][0][0] == (5.0, 5.0) and bounds == (1.0, 2.0, 3.0, 4.0)


def test_unreadable_cache_falls_back_to_the_json(tmp_path, monkeypatch):
    monkeypatch.delenv("BIOSOFT_NO_MAP_CACHE", raising=False)
    _outline(tmp_path, [[[1, 1], [2, 2], [3, 1]]])
    _fresh(tmp_path)
    (tmp_path / "cache" / "gb_outline.rings.npz").write_bytes(b"not a zip")
    assert _fresh(tmp_path)[0][0][0] == [(1.0, 1.0), (2.0, 2.0), (3.0, 1.0)]


def _old_land_raster(rings, cell):
    """land_raster as it was before R17 (one QPointF per point, drawPolygon per ring)."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
    from shared.maps import coast
    w, h = int(coast.GB_E / cell) + 2, int(coast.GB_N / cell) + 2
    img = QImage(w, h, QImage.Format.Format_Grayscale8)
    img.fill(0)
    p = QPainter(img)
    p.setPen(QPen(QColor(255, 255, 255), 1.5 * cell))
    p.setBrush(QColor(255, 255, 255))
    p.scale(1 / cell, -1 / cell)
    p.translate(0, -coast.GB_N)
    for r in rings:
        p.drawPolygon(QPolygonF([QPointF(e, n) for e, n in r]))
    p.end()
    return bytes(img.constBits()), img.bytesPerLine(), w, h


def _pixels(raster):
    """(width, height, the real pixels row by row): a line's padding bytes past the width are
    never read (coast.classify) and QImage leaves them unset, so they are not compared."""
    bits, bpl, w, h = raster
    return w, h, bpl, b"".join(bits[y * bpl:y * bpl + w] for y in range(h))


def test_land_raster_is_identical_to_the_per_point_version(qapp_a7):
    from shared.maps import coast
    rings = [
        [(20000.0, 20000.0), (400000.0, 30000.0), (380000.0, 500000.0), (30000.0, 450000.0),
         (20000.0, 20000.0)],
        [(100000.0, 100000.0), (200000.0, 100000.0), (150000.0, 220000.0)],       # open ring
        [(500000.0, 600000.0), (520000.0, 640000.0)],                              # two points
        [(600000.0, 900000.0)],                                                    # one point
        [(250000.0, 700000.0), (300000.5, 700000.25), (300000.5, 900000.75), (250000.0, 900000.0)],
    ]
    for cell in (250.0, 1000.0):
        assert _pixels(coast.land_raster(rings, cell)) == _pixels(_old_land_raster(rings, cell))
    assert _pixels(coast.land_raster([], 1000.0)) == _pixels(_old_land_raster([], 1000.0))
