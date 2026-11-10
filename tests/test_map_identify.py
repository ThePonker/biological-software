"""25 Oct 2026: names over see-through squares, the Small Settlements class and the Identify
tool (shared/maps/identify.py, Observatum views/mapping/identify_popup.py). Small purpose-made
layer files in tmp_path; nothing from Wil's data."""
# ruff: noqa: F811  (pytest fixtures imported from test_map_layers_r11)
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402

from shared.maps import grid_squares as gs, place_classes  # noqa: E402
from tests.test_map_extra_layers import _pt  # noqa: E402
from tests.test_map_layers_r11 import _map, _sq, _write, qapp  # noqa: E402,F401


# ---------------------------------------------------------------- names over squares

def test_name_touching_a_square_is_left_out_at_100_and_drawn_below(qapp, tmp_path):
    _write(tmp_path, "names", "gb", [_pt("City", "Oxford", 50000, 50000)], "point")
    _write(tmp_path, "names", "county", [], "point")
    m = _map(tmp_path)
    m.set_layers({"names"})
    m.set_squares({"SP55": {"count": 1, "fill": "#cc3333"}}, gs.HECTAD)
    # Oxford (50000, 50000) is in no recorded square here; put the square under it
    m.set_squares({gs.square_for_point(50000, 50000, gs.HECTAD): {"count": 1, "fill": "#cc3333"}},
                  gs.HECTAD)

    def drawn(percent):
        from PySide6.QtGui import QColor, QImage, QPainter
        m.set_square_opacity(percent)
        img = QImage(300, 300, QImage.Format.Format_RGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        m._draw_place_names(p, m.fit(), 1.0)
        p.end()
        return any(img.pixelColor(x, y) != QColor("white")
                   for x in range(0, 300) for y in range(0, 300))
    # names are far apart from the VC labels; the only thing that can leave it out is the square
    assert drawn(100) is False
    assert drawn(60) is True


# ---------------------------------------------------------------- place classes

def test_small_settlements_class():
    assert place_classes.rank_of("Small Settlements") == place_classes.rank_of("small settlement") \
        == next(i for i, c in enumerate(place_classes.PLACE_CLASSES) if c.key == "small settlement")
    new = place_classes.rank_of("Small Settlements")
    c = place_classes.PLACE_CLASSES[new]
    assert (c.max_span_m, c.pt, c.bold, c.lod) == (8_000.0, 7.0, False, "county")
    assert new == len(place_classes.PLACE_CLASSES) - 1 and new > place_classes.rank_of("hamlet")
    assert new not in place_classes.shown_at(10_000) and new in place_classes.shown_at(5_000)
    assert place_classes.shown_at(20_000) == [0, 1, 2, 3]       # hamlets unchanged
    for v in ("hamlet", "suburban area", "other settlement"):
        assert place_classes.rank_of(v) == place_classes.rank_of("hamlet")
    assert "small settlements" in place_classes.source_values("county")


# ---------------------------------------------------------------- Identify

def _click(m, e_, n_):
    x, y = m.fit().to_px(e_, n_)
    pos = QPointF(x, y)
    for kind, btn in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
                      (QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton)):
        ev = QMouseEvent(kind, pos, m.mapToGlobal(pos), btn, btn, Qt.KeyboardModifier.NoModifier)
        (m.mousePressEvent if kind == QEvent.Type.MouseButtonPress else m.mouseReleaseEvent)(ev)


def _map_with_square(tmp_path):
    m = _map(tmp_path)
    m.set_extent((400000, 200000, 500000, 300000))       # the SP 100 km square
    m.set_squares({"SP55": {"count": 7, "fill": "#cc3333"}}, gs.HECTAD)
    return m


def test_identify_off_selects_and_on_emits(qapp, tmp_path):
    m = _map_with_square(tmp_path)
    picked, asked = [], []
    m.square_clicked.connect(picked.append)
    m.identify_requested.connect(lambda e, n, g: asked.append((round(e), round(n))))
    _click(m, 455500, 255500)
    assert picked == ["SP55"] and asked == [] and m._selected == "SP55"
    m.set_selected(None)
    m.set_identify_mode(True)
    assert m.cursor().shape() == Qt.CursorShape.WhatsThisCursor
    _click(m, 455500, 255500)
    assert picked == ["SP55"] and asked == [(455500, 255500)] and m._selected is None
    m.set_identify_mode(False)
    assert m.cursor().shape() == Qt.CursorShape.OpenHandCursor


class _VC:
    def assess(self, ref):
        return {"vc_number": 23, "vc_name": "Oxfordshire", "note": "On a boundary: test"} \
            if ref.startswith("SP") else None


def _popup(m, e_, n_, squares=None):
    from src.views.mapping.identify_popup import IdentifyPopup, build_info
    info = build_info(m, e_, n_, m._squares if squares is None else squares, _VC())
    return IdentifyPopup(info), info


def test_popup_shows_refs_vc_and_records(qapp, tmp_path):
    m = _map_with_square(tmp_path)
    pop, info = _popup(m, 445035, 235025)       # SP 4503 3502 (no square here)
    assert [r for _n, r in info.refs] == ["SP43", "SP4535", "SP450350"]
    texts = [lab.text() for lab in pop.ref_labels]
    assert "SP43" in texts[0] and "SP4535" in texts[1] and "SP450350" in texts[2]
    assert "VC23 Oxfordshire" in pop.vc_label.text() and "test" in pop.note_label.text()
    assert pop.records_label.text() == "No records here" and pop.open_btn is None
    from PySide6.QtWidgets import QApplication
    pop.copy_btn.click()
    assert QApplication.clipboard().text() == "SP450350"
    pop2, info2 = _popup(m, 455500, 255500)      # inside SP55? easting 455500 -> SP55 hectad
    assert info2.square == "SP55" and info2.count == 7
    assert "7" in pop2.records_label.text() and pop2.open_btn is not None
    got = []
    pop2.open_records.connect(got.append)
    pop2.open_btn.click()
    assert got == ["SP55"]


def test_popup_closes_on_escape(qapp, tmp_path):
    from PySide6.QtTest import QTest
    m = _map_with_square(tmp_path)
    pop, _i = _popup(m, 445035, 235025)
    pop.show()
    assert pop.isVisible()
    QTest.keyClick(pop, Qt.Key.Key_Escape)
    assert not pop.isVisible()


def test_controller_toggle_and_new_click_moves_popup(qapp, tmp_path):
    from src.views.mapping.identify_popup import IdentifyController
    from src.views.mapping.toolbar import MapToolbar
    m = _map_with_square(tmp_path)
    tb = MapToolbar()
    ctl = IdentifyController(m, tb, lambda: m._squares, vc_service=_VC())
    assert not m.identify_mode() and not tb.identify_btn.isChecked()
    tb.identify_btn.click()
    assert m.identify_mode()
    ctl.identify(455500, 255500, QPoint(100, 100))
    first = ctl.popup()
    assert first is not None
    ctl.identify(460500, 260500, QPoint(150, 150))
    assert ctl.popup() is not first and ctl.popup() is not None
    tb.identify_btn.click()
    assert not m.identify_mode() and ctl.popup() is None


def test_escape_on_the_map_closes_the_popup(qapp, tmp_path):
    """After a click the map has focus, not the pop-up: Esc there closes it too."""
    from src.views.mapping.identify_popup import IdentifyController
    from src.views.mapping.toolbar import MapToolbar
    m = _map_with_square(tmp_path)
    tb = MapToolbar()
    ctl = IdentifyController(m, tb, lambda: m._squares, vc_service=_VC())
    tb.identify_btn.click()
    ctl.identify(455500, 255500, QPoint(100, 100))
    assert ctl.popup() is not None
    ctl._map_esc.activated.emit()
    assert ctl.popup() is None


def test_polygon_layer_hit_lists_the_menu_label_and_name(qapp, tmp_path):
    wood = _sq(10000, 10000, 20000, 20000, hole=(14000, 14000, 16000, 16000))
    wood["name"] = "Big Wood"
    _write(tmp_path, "woodland", "county", [wood, _sq(60000, 60000, 70000, 70000)])
    _write(tmp_path, "towns", "county", [_sq(10000, 10000, 20000, 20000)])
    m = _map(tmp_path)
    m.set_layers({"woodland"})                  # towns not ticked
    assert m.identify_at(12000, 12000) == [("Woodland", "Big Wood")]
    assert m.identify_at(15000, 15000) == []    # in the hole
    assert m.identify_at(90000, 90000) == []
    m.set_layers({"woodland", "towns"})
    assert [lab for lab, _n in m.identify_at(12000, 12000)] == ["Woodland", "Towns"]
    pop, _i = _popup(m, 12000, 12000, {})
    assert any(t.text() == "Woodland: Big Wood" for t in pop.layer_labels)
    assert any(t.text() == "Towns" for t in pop.layer_labels)


def test_nearest_place_within_2km(qapp, tmp_path):
    _write(tmp_path, "names", "gb", [], "point")
    _write(tmp_path, "names", "county", [_pt("Hamlet", "Near Hamlet", 50600, 50000),
                                         _pt("Hamlet", "Nearer Hamlet", 50000, 51000),
                                         _pt("Hamlet", "Far Hamlet", 50000, 53000)], "point")
    m = _map(tmp_path)
    m.set_layers({"names"})
    m.set_extent((42000, 42000, 58000, 58000))      # a 16 km view: hamlets are shown
    assert m.identify_at(50000, 50000) == [("Place", "Near Hamlet, 0.6 km E")]
    m.set_layers(set())
    assert m.identify_at(50000, 50000) == []


def test_nearest_place_follows_the_classes_drawn(qapp, tmp_path):
    _write(tmp_path, "names", "gb", [], "point")
    _write(tmp_path, "names", "county", [_pt("Small Settlements", "Tiny", 50300, 50000)], "point")
    m = _map(tmp_path)
    m.set_layers({"names"})
    m.set_extent((42000, 42000, 58000, 58000))      # 16 km across: small settlements not drawn
    assert m.identify_at(50000, 50000) == []
    m.set_extent((47000, 47000, 53000, 53000))      # about 7.5 km: drawn
    assert m.identify_at(50000, 50000) == [("Place", "Tiny, 0.3 km E")]
