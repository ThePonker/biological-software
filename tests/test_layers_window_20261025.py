"""The Layers window, classed drawing and Identify details (25 Oct 2026). Small purpose-made
layer files in tmp_path; nothing from Wil's data."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import layer_opacity, layers  # noqa: E402
from tests.test_map_identify import _VC  # noqa: E402
from tests import test_map_layers_r11 as r11  # noqa: E402
from tests.test_map_layers_r11 import _map, _pixel, _sq, _write  # noqa: E402

qapp, settings_sandbox = r11.qapp, r11.settings_sandbox      # the shared fixtures


def _bar(m=None):
    from src.views.mapping.display_bar import MapDisplayBar
    bar = MapDisplayBar()
    if m is not None:
        bar.attach_map(m)
    return bar


def _typed(e0, n0, e1, n1, t, **extra):
    f = _sq(e0, n0, e1, n1)
    f["t"] = t
    f.update(extra)
    return f


# ---------------------------------------------------------------- the window

def test_rows_match_the_toggles_and_sections(qapp, settings_sandbox):
    win = _bar().layers_window()
    vis = layers.visible_toggles()
    assert set(win.checks) == {t.key for t in vis} and len(win.checks) == len(vis)
    assert all(win.checks[t.key].text() == t.label for t in vis)
    # base map first, then Designated sites ... Climate last (not the drawing stack's order)
    assert win.group_titles == ["Base map", "Designated sites", "Woodland and habitats",
                                "Geology and soils", "Access land", "Climate, 1991–2020 averages"]
    assert "sssi" in win.sliders and "woodland" not in win.sliders       # opacity: Environment polygons
    assert "haduk_rain" not in win.sliders and "haduk_rain" not in win.swatches
    assert "geology_bedrock" not in win.swatches and "geology_bedrock" in win.key_boxes


def test_tick_box_ticks_the_action_and_emits(qapp, settings_sandbox):
    from src.views.mapping.display_bar import saved_layers
    bar = _bar()
    win = bar.layers_window()
    seen = []
    bar.layers_changed.connect(seen.append)
    win.checks["woodland"].setChecked(True)
    assert bar.layer_actions["woodland"].isChecked() and seen[-1] == {"water", "woodland"}
    assert saved_layers() == {"water", "woodland"}
    bar.layer_actions["woodland"].setChecked(False)         # the other way: the box follows
    assert not win.checks["woodland"].isChecked()


def test_the_button_opens_the_window_and_it_remembers_its_place(qapp, settings_sandbox):
    from PySide6.QtCore import QSettings
    bar = _bar()
    assert bar.layers_button.menu() is None
    bar.layers_button.click()
    win = bar.layers_window()
    assert win.isVisible() and not win.isModal()
    win.move(123, 77)
    win.hide()
    assert QSettings().value("mapping/layers_window/geometry") is not None


def test_opacity_is_remembered_and_repaints(qapp, settings_sandbox):
    from PySide6.QtCore import QSettings
    bar = _bar()
    win = bar.layers_window()
    seen = []
    bar.layer_colours_changed.connect(lambda: seen.append(1))
    assert win.sliders["sssi"].value() == layer_opacity.default_opacity("sssi") == 43   # alpha 110
    win.sliders["sssi"].setValue(80)
    assert QSettings().value("mapping/layer_opacity/sssi", type=int) == 80 and seen
    assert layer_opacity.opacity("sssi") == 80 and layer_opacity.alpha("sssi") == 204
    assert _bar().layers_window().sliders["sssi"].value() == 80          # remembered


def test_key_shows_the_classes_present_in_palette_order(qapp, tmp_path, settings_sandbox):
    _write(tmp_path, "geology_bedrock", "county",
           [_typed(0, 0, 10, 10, "Jurassic"), _typed(20, 0, 30, 10, "Neogene"),
            _typed(40, 0, 50, 10, "Odd new class")])
    m = _map(tmp_path)
    bar = _bar(m)
    win = bar.layers_window()
    box = win.key_boxes["geology_bedrock"]
    assert not box.isVisibleTo(win)
    win.checks["geology_bedrock"].setChecked(True)
    assert box.isVisibleTo(win)
    from PySide6.QtWidgets import QLabel
    names = [lab.text() for lab in box.findChildren(QLabel)
             if lab.text() and not lab.text().startswith("Colours:")]
    assert names == ["Neogene", "Jurassic", "Odd new class"]
    assert any("Chronostratigraphic" in lab.text() for lab in box.findChildren(QLabel))
    win.checks["geology_bedrock"].setChecked(False)
    assert not box.isVisibleTo(win)


def test_unavailable_row_is_greyed_with_the_reason(qapp, tmp_path, settings_sandbox):
    _write(tmp_path, "woodland", "gb", [_sq(0, 0, 10, 10)])
    bar = _bar(_map(tmp_path))
    win = bar.layers_window()
    assert win.rows["woodland"].isEnabled() and not win.rows["towns"].isEnabled()
    assert win.rows["towns"].toolTip() == layers.NOT_INSTALLED
    bar.set_layers_available({"towns", "woodland"})              # it follows later changes
    assert win.rows["towns"].isEnabled()


def test_reset_restores_defaults_and_opacities(qapp, settings_sandbox, monkeypatch):
    from PySide6.QtGui import QColor
    bar = _bar()
    win = bar.layers_window()
    win.checks["woodland"].setChecked(True)
    win.sliders["sssi"].setValue(10)
    layers.set_colour("roads", QColor("#010203"))
    win.reset_button.click()
    assert bar.layers() == {"water"} and not win.checks["woodland"].isChecked()
    assert layer_opacity.saved_opacity("sssi") is None and win.sliders["sssi"].value() == 43
    assert layers.saved_colour("roads") is None


def test_colour_swatch_uses_set_colour(qapp, settings_sandbox, monkeypatch):
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QColorDialog
    win = _bar().layers_window()
    monkeypatch.setattr(QColorDialog, "getColor", lambda *a, **k: QColor("#00aa00"))
    win.swatches["towns"].click()
    assert layers.saved_colour("towns").name() == "#00aa00"


# ---------------------------------------------------------------- drawing

def test_classed_layer_builds_one_path_per_class_and_draws_their_colours(qapp, tmp_path,
                                                                           settings_sandbox):
    _write(tmp_path, "geology_bedrock", "county",
           [_typed(10000, 10000, 40000, 40000, "Jurassic"),
            _typed(50000, 10000, 80000, 40000, "Cretaceous"),
            _typed(10000, 50000, 20000, 60000, "Jurassic")])
    m = _map(tmp_path)
    m.set_layers({"geology_bedrock"})
    m.grab()
    paths = {c[3]: p for c, p in m._layer_cache.items() if c[0] == "geology_bedrock"}
    assert set(paths) == {"Jurassic", "Cretaceous"}
    assert paths["Jurassic"].boundingRect().width() == 30000 and \
        paths["Cretaceous"].boundingRect().left() == 50000
    assert m._layer_classes(m.fit(), "geology_bedrock") == ["Jurassic", "Cretaceous"]
    a, b = _pixel(m, 25000, 25000), _pixel(m, 65000, 25000)
    assert a != b and a != _pixel(m, 90000, 90000)           # two classes, two colours


def test_remembered_opacity_changes_the_drawing(qapp, tmp_path, settings_sandbox):
    _write(tmp_path, "sssi", "county", [_typed(10000, 10000, 80000, 80000, "SSSI")])
    m = _map(tmp_path)
    m.set_layers({"sssi"})
    pale = _pixel(m, 45000, 45000)
    layer_opacity.set_opacity("sssi", 100)
    m.refresh_layer_colours()
    assert _pixel(m, 45000, 45000) != pale


def test_designated_sites_and_common_land_get_an_outline(qapp, tmp_path, settings_sandbox):
    _write(tmp_path, "common_land", "county", [_typed(10000, 10000, 80000, 80000, "Common")])
    m = _map(tmp_path)
    m.set_layers({"common_land"})
    edge = _pixel(m, 10000 + 100, 45000)
    inside = _pixel(m, 45000, 45000)
    from PySide6.QtGui import QColor
    assert QColor(edge).lightness() < QColor(inside).lightness()


# ---------------------------------------------------------------- identify

def test_identify_details_carry_details_and_link(qapp, tmp_path, settings_sandbox):
    site = _typed(10000, 10000, 20000, 20000, "SSSI", n="Ashen Bank",
                  a=[["Code", "1006159"], ["Area", "84.4 ha"]], u="https://example.org/site/1")
    plain = _typed(10000, 10000, 20000, 20000, "SSSI", n="Other")
    _write(tmp_path, "sssi", "county", [site, plain])
    _write(tmp_path, "towns", "county", [_sq(10000, 10000, 20000, 20000)])
    m = _map(tmp_path)
    m.set_layers({"sssi", "towns"})
    got = m.identify_details(12000, 12000)
    assert [g["label"] for g in got] == [lab for lab, _t in m.identify_at(12000, 12000)] == ["Towns", "SSSI"]
    items = got[1]["items"]
    assert items[0] == {"text": "Ashen Bank", "details": [("Code", "1006159"), ("Area", "84.4 ha")],
                        "link": "https://example.org/site/1"}
    assert items[1] == {"text": "Other", "details": [], "link": None}
    assert m.identify_details(90000, 90000) == []


def _popup_for(m, e, n):
    from src.views.mapping.identify_popup import IdentifyPopup, build_info
    return IdentifyPopup(build_info(m, e, n, {}, _VC()))


def test_popup_shows_details_and_a_link_button_only_with_a_link(qapp, tmp_path, settings_sandbox,
                                                                monkeypatch):
    from PySide6.QtGui import QDesktopServices
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    site = _typed(10000, 10000, 20000, 20000, "SSSI", n="Ashen Bank",
                  a=[["Code", "1006159"], ["Area", "84.4 ha"]], u="https://example.org/site/1")
    _write(tmp_path, "sssi", "county", [site])
    _write(tmp_path, "towns", "county", [_sq(10000, 10000, 20000, 20000)])
    m = _map(tmp_path)
    m.set_layers({"sssi", "towns"})
    pop = _popup_for(m, 12000, 12000)
    assert [lab.text() for lab in pop.layer_labels] == ["Towns", "SSSI: Ashen Bank"]
    assert [lab.text() for lab in pop.detail_labels] == ["Code 1006159 · Area 84.4 ha"]
    assert [b.text() for b in pop.link_buttons] == ["Open site page"]
    pop.link_buttons[0].click()
    assert opened == ["https://example.org/site/1"]
    m.set_layers({"towns"})
    pop2 = _popup_for(m, 12000, 12000)
    assert pop2.link_buttons == [] and pop2.detail_labels == []
