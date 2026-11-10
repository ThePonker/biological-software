"""R17 A2: one on/off switch per group in the Layers window. Settings go to the test sandbox."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from shared.maps import env_registry as env, layers  # noqa: E402
from tests import test_map_layers_r11 as r11  # noqa: E402

qapp, settings_sandbox = r11.qapp, r11.settings_sandbox


def _bar():
    from src.views.mapping.display_bar import MapDisplayBar
    return MapDisplayBar()


def _env_keys(section):
    return [t.key for t in layers.visible_toggles() if t.group and t.section == section]


def test_every_group_has_a_switch(qapp, settings_sandbox):
    win = _bar().layers_window()
    assert list(win.group_checks) == win.group_titles
    assert win.group_checks["Base map"].isChecked()          # water is a default layer


def test_off_hides_the_group_and_on_restores_exactly_the_ticked_ones(qapp, settings_sandbox):
    from src.views.mapping.display_bar import saved_layers
    bar = _bar()
    win = bar.layers_window()
    for k in ("woodland", "roads"):
        bar.layer_actions[k].setChecked(True)
    assert bar.layers() == {"water", "woodland", "roads"}
    seen = []
    bar.layers_changed.connect(seen.append)
    win.group_checks["Base map"].setChecked(False)
    assert bar.layers() == set() and seen == [set()]                 # one redraw, not one per layer
    assert not any(win.checks[k].isChecked() for k in ("water", "woodland", "roads"))
    assert saved_layers() == set()
    win.group_checks["Base map"].setChecked(True)
    assert bar.layers() == {"water", "woodland", "roads"} and len(seen) == 2
    assert not bar.layer_actions["towns"].isChecked()
    assert saved_layers() == {"water", "woodland", "roads"}


def test_state_and_memory_persist_like_the_ticks(qapp, settings_sandbox):
    bar = _bar()
    bar.layer_actions["rail"].setChecked(True)
    bar.set_group_on("Base map", False)
    bar2 = _bar()                                       # a new start reads the settings
    assert bar2.layers() == set() and not bar2.group_ticked("Base map")
    bar2.set_group_on("Base map", True)
    assert bar2.layers() == {"water", "rail"}


def test_other_groups_are_untouched(qapp, settings_sandbox):
    bar = _bar()
    key = _env_keys(env.DESIG)[0]
    bar.layer_actions[key].setChecked(True)
    bar.set_group_on("Base map", False)
    assert bar.layers() == {key}
    assert bar.layers_window().group_checks[env.DESIG].isChecked()


def test_unticked_group_switched_on_uses_defaults_else_all(qapp, settings_sandbox):
    bar = _bar()
    bar.set_group_on("Base map", False)
    bar.set_group_on("Base map", True)                  # nothing remembered: the group's defaults
    assert bar.layers() == layers.defaults() & set(bar.layer_actions) & {"water"}
    keys = _env_keys(env.GEO)
    assert not set(keys) & layers.defaults()
    bar.set_group_on(env.GEO, True)                     # no default in the group: all of them
    assert {k for k in bar.layers() if k in keys} == {k for k in keys if bar.layer_actions[k].isEnabled()}


def test_manual_unticking_everything_shows_the_switch_off(qapp, settings_sandbox):
    bar = _bar()
    win = bar.layers_window()
    bar.layer_actions["water"].setChecked(False)
    assert not win.group_checks["Base map"].isChecked()
    win.checks["water"].setChecked(True)
    assert win.group_checks["Base map"].isChecked()


def test_reset_clears_the_memory(qapp, settings_sandbox):
    bar = _bar()
    bar.layer_actions["roads"].setChecked(True)
    bar.set_group_on("Base map", False)
    bar.reset_layers()
    assert bar.layers() == layers.defaults() & set(bar.layer_actions)
    bar.set_group_on("Base map", False)
    bar.set_group_on("Base map", True)
    assert "roads" not in bar.layers()


def test_group_switch_redraws_the_map_once(qapp, settings_sandbox, tmp_path):
    bar = _bar()
    calls = []
    bar.layers_changed.connect(lambda ks: calls.append(set(ks)))
    for k in ("woodland", "roads", "rail"):
        bar.layer_actions[k].setChecked(True)
    calls.clear()
    bar.set_group_on("Base map", False)
    bar.set_group_on("Base map", True)
    assert len(calls) == 2
