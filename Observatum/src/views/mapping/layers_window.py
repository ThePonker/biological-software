"""The Mapping tab's Layers window (25 Oct 2026): replaces the Layers drop-down menu.

A non-modal tool window above the map tab's window, opened by the Layers button, that remembers
where it was (QSettings). In a scroll area: the "Base map" layers (a tick box and a colour swatch
each), then one group per Environment section. An Environment polygon layer also has an opacity
slider (remembered per layer: shared/maps/layer_opacity.py), and a classed layer (env_classes.py)
shows a key under its row while ticked: a swatch and name per class in the loaded features, and the
colour credit. The tick boxes mirror MapDisplayBar.layer_actions, which stay the state (saved,
signalled) so callers and the saved settings are unchanged; a layer whose file is not installed
is greyed out. "Reset to defaults" is the bar's. Display only.
"""
from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QDialog, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QSlider,
                               QVBoxLayout, QWidget)

from shared.maps import env_classes, env_registry as env, layer_opacity, layers

from ...themes import theme

GEOMETRY_SETTING = "mapping/layers_window/geometry"
BASE_TITLE = "Base map"
SECTION_ORDER = (env.DESIG, env.HAB, env.GEO, env.ACC, env.CLIM)


def group_title(tg) -> str:
    """The window's group a toggle belongs to ("Base map", or its Environment section)."""
    return tg.section if tg.group else BASE_TITLE


def group_members() -> Dict[str, List[str]]:
    """Group title -> the keys of its toggles, in the window's order. One source for the
    window's group switches and the bar's remembered ticks."""
    rank = {t: i for i, t in enumerate(SECTION_ORDER)}
    out: Dict[str, List[str]] = {}
    for tg in sorted(layers.visible_toggles(),
                     key=lambda tg: -1 if not tg.group else rank.get(tg.section, len(rank))):
        out.setdefault(group_title(tg), []).append(tg.key)
    return out


class LayersWindow(QDialog):
    """Tick boxes, colours, opacities and keys for the map's layers. `bar`: the MapDisplayBar."""

    def __init__(self, bar, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowTitleHint
                         | Qt.WindowType.WindowCloseButtonHint)
        self.bar = bar
        self.setWindowTitle("Layers")
        self.setModal(False)
        t = theme()
        self.setStyleSheet(
            f"QDialog {{ background-color: {t.get('background')}; }}"
            f"QGroupBox {{ color: {t.get('text_heading')}; font-weight: 600; "
            f"border: 1px solid {t.get('border')}; border-radius: {t.get('radius_sm')}; "
            f"margin-top: 10px; padding-top: 6px; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}"
            f"QCheckBox, QLabel {{ color: {t.get('text_primary')}; font-size: 12px; }}"
            f"QLabel#muted {{ color: {t.get('text_secondary')}; font-size: {t.get('font_size_xs')}pt; }}"
            f"QCheckBox:disabled, QLabel:disabled {{ color: {t.get('disabled_text')}; }}")
        self.checks: Dict[str, QCheckBox] = {}
        self.swatches: Dict[str, QPushButton] = {}
        self.sliders: Dict[str, QSlider] = {}
        self.slider_values: Dict[str, QLabel] = {}
        self.key_boxes: Dict[str, QWidget] = {}
        self.rows: Dict[str, QWidget] = {}
        self.group_titles: List[str] = []
        self.group_checks: Dict[str, QCheckBox] = {}      # one on/off switch per group header
        self.key_group: Dict[str, str] = {}
        outer = QVBoxLayout(self)
        holder = QWidget()
        body = QVBoxLayout(holder)
        body.setContentsMargins(4, 4, 8, 4)
        groups: Dict[str, QVBoxLayout] = {}
        # base map first, then the Environment sections in SECTION_ORDER (the registry's own
        # order is the drawing stack, which puts Climate first)
        rank = {t: i for i, t in enumerate(SECTION_ORDER)}
        toggles = sorted(layers.visible_toggles(),
                         key=lambda tg: -1 if not tg.group else rank.get(tg.section, len(rank)))
        for tg in toggles:
            title = group_title(tg)
            if title not in groups:
                box = QGroupBox()
                groups[title] = QVBoxLayout(box)
                groups[title].setSpacing(3)
                groups[title].addWidget(self._group_switch(title))
                body.addWidget(box)
                self.group_titles.append(title)
            self.key_group[tg.key] = title
            groups[title].addWidget(self._row(tg))
        body.addStretch()
        scroll = QScrollArea()
        scroll.setWidget(holder)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)
        foot = QHBoxLayout()
        self.reset_button = QPushButton("Reset to defaults")
        self.reset_button.setStyleSheet(t.button_cancel_style())
        self.reset_button.setToolTip("Back to the default layers, colours and opacities")
        self.reset_button.clicked.connect(self.reset)
        foot.addWidget(self.reset_button)
        foot.addStretch()
        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet(t.button_cancel_style())
        self.close_button.clicked.connect(self.close)
        foot.addWidget(self.close_button)
        outer.addLayout(foot)
        for key, act in bar.layer_actions.items():
            act.toggled.connect(lambda _on, k=key: self.sync_row(k))
        self.setMinimumWidth(min(holder.minimumSizeHint().width() + 34, 640))   # no clipped rows
        self.resize(max(self.minimumWidth(), 440), 560)
        try:
            geom = QSettings().value(GEOMETRY_SETTING)
            if geom:
                self.restoreGeometry(geom)
        except Exception:
            pass
        self.sync()

    # ---------------------------------------------------------------- building
    def _group_switch(self, title: str) -> QCheckBox:
        """The group's header: one switch that turns all its layers off, and back on."""
        t = theme()
        cb = QCheckBox(title)
        cb.setStyleSheet(f"QCheckBox {{ color: {t.get('text_heading')}; font-weight: 600; }}")
        cb.setToolTip(f"Switch every layer in \u201c{title}\u201d off or on. Switching it on again "
                      f"brings back the layers that were ticked.")
        cb.setAccessibleName(f"{title} on or off")
        cb.toggled.connect(lambda on, ti=title: self.bar.set_group_on(ti, on))
        self.group_checks[title] = cb
        return cb

    def _row(self, tg) -> QWidget:
        """One layer: tick box (its label), colour swatch, opacity slider, then its key."""
        t = theme()
        wrap = QWidget()
        col = QVBoxLayout(wrap)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        line = QHBoxLayout()
        line.setSpacing(6)
        cb = QCheckBox(tg.label)
        cb.toggled.connect(lambda on, k=tg.key: self._ticked(k, on))
        self.checks[tg.key] = cb
        line.addWidget(cb, 1)
        if tg.colour and not env_classes.is_classed(tg.key):
            sw = QPushButton()
            sw.setFixedSize(34, 18)
            sw.setToolTip(f"Choose the colour of {tg.label.lower()}")
            sw.setAccessibleName(f"{tg.label} colour")
            sw.clicked.connect(lambda _c=False, k=tg.key: self.choose_colour(k))
            self.swatches[tg.key] = sw
            line.addWidget(sw)
        if layer_opacity.has_opacity(tg.key):
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(0, 100)
            sl.setSingleStep(5)
            sl.setPageStep(10)
            sl.setFixedWidth(84)
            sl.setToolTip(f"How solid {tg.label.lower()} is drawn. Remembered.")
            sl.setAccessibleName(f"{tg.label} opacity")
            sl.setStyleSheet(
                f"QSlider::groove:horizontal {{ height: 4px; background: {t.get('border')}; "
                f"border-radius: 2px; }}"
                f"QSlider::sub-page:horizontal {{ background: {t.get('primary')}; "
                f"border-radius: 2px; }}"
                f"QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; "
                f"border-radius: 6px; background: {t.get('primary')}; }}")
            sl.setValue(layer_opacity.opacity(tg.key))
            sl.valueChanged.connect(lambda v, k=tg.key: self._opacity(k, v))
            val = QLabel(f"{sl.value()}%")
            val.setMinimumWidth(32)
            self.sliders[tg.key] = sl
            self.slider_values[tg.key] = val
            line.addWidget(sl)
            line.addWidget(val)
        col.addLayout(line)
        if env_classes.is_classed(tg.key):
            box = QWidget()
            QVBoxLayout(box).setContentsMargins(22, 0, 0, 4)
            box.hide()
            self.key_boxes[tg.key] = box
            col.addWidget(box)
        self.rows[tg.key] = wrap
        return wrap

    # ---------------------------------------------------------------- state
    def sync(self):
        """Bring every row in line with the bar's actions (ticks, availability) and the
        remembered colours."""
        for key in self.checks:
            self.sync_row(key)
        self.refresh_colours()

    def sync_row(self, key: str):
        act = self.bar.layer_actions.get(key)
        cb = self.checks.get(key)
        if act is None or cb is None:
            return
        cb.blockSignals(True)
        cb.setChecked(act.isChecked())
        cb.blockSignals(False)
        ok = act.isEnabled()
        self.rows[key].setEnabled(ok)
        self.rows[key].setToolTip("" if ok else act.toolTip() or layers.NOT_INSTALLED)
        if key in self.key_boxes:
            self.refresh_key(key)
        self.sync_group(self.key_group.get(key, ""))

    def sync_group(self, title: str):
        """The group switch shows whether any of its layers is ticked."""
        cb = self.group_checks.get(title)
        if cb is None:
            return
        cb.blockSignals(True)
        cb.setChecked(self.bar.group_ticked(title))
        cb.blockSignals(False)

    def refresh_colours(self):
        t = theme()
        for key, btn in self.swatches.items():
            c = layers.saved_colour(key) or layers.default_colour(key)
            btn.setStyleSheet(f"background-color: {QColor(c).name()}; "
                              f"border: 1px solid {t.get('border_strong')}; border-radius: 3px;")
        for key, sl in self.sliders.items():
            sl.blockSignals(True)
            sl.setValue(layer_opacity.opacity(key))
            sl.blockSignals(False)
            self.slider_values[key].setText(f"{sl.value()}%")

    def classes_in(self, key: str) -> List[str]:
        """The classes of a layer in its loaded features at the map's level of detail."""
        m = self.bar.attached_map()
        maps_dir = getattr(m, "_maps_dir", None)
        if m is None or not maps_dir:
            return []
        try:
            lod = layers.lod_for_extent(m.visible_extent())
            feats = layers.load(maps_dir, key, lod)
            if hasattr(feats, "classes"):           # a binary layer: one array read, no points
                return [str(c) for c in set(feats.classes().tolist())]
            return [str(f.get("t") or "") for f in feats]
        except Exception:
            return []

    def refresh_key(self, key: str):
        """The key under a classed layer's row: shown while the layer is ticked."""
        box = self.key_boxes[key]
        lay = box.layout()
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        on = self.checks[key].isChecked()
        entries = env_classes.key_entries(key, self.classes_in(key)) if on else []
        src = env_classes.SOURCES.get(key, "")
        t = theme()
        grid = QWidget()
        g = QGridLayout(grid)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(2)
        for i, (cls, hexcol) in enumerate(entries):
            sw = QLabel()
            sw.setFixedSize(14, 14)
            sw.setStyleSheet(f"background: {hexcol}; border: 1px solid {t.get('border_strong')};")
            g.addWidget(sw, i, 0)
            name = QLabel(cls or "(no class)")
            name.setWordWrap(True)
            name.setMinimumWidth(40)
            g.addWidget(name, i, 1)
        g.setColumnStretch(1, 1)
        lay.addWidget(grid)
        if src:
            lab = QLabel(src)
            lab.setObjectName("muted")
            lab.setWordWrap(True)
            lab.setMinimumWidth(40)
            lay.addWidget(lab)
        box.setVisible(on and bool(entries or src))

    # ---------------------------------------------------------------- user actions
    def _ticked(self, key: str, on: bool):
        act = self.bar.layer_actions.get(key)
        if act is not None and act.isEnabled():
            act.setChecked(on)              # saves and signals, as the menu did

    def choose_colour(self, key: str):
        c = QColorDialog.getColor(layers.saved_colour(key) or layers.default_colour(key),
                                  self, "Choose a colour")
        if c.isValid():
            self.set_colour(key, c)

    def set_colour(self, key: str, colour):
        layers.set_colour(key, colour)
        self.refresh_colours()
        self.bar.layer_colours_changed.emit()

    def _opacity(self, key: str, value: int):
        layer_opacity.set_opacity(key, value)
        self.slider_values[key].setText(f"{value}%")
        self.bar.layer_colours_changed.emit()

    def reset(self):
        self.bar.reset_layers()
        self.sync()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.sync()                         # the map's level of detail may have changed

    def _remember(self):
        try:
            QSettings().setValue(GEOMETRY_SETTING, self.saveGeometry())
        except Exception as e:
            print(f"[LayersWindow] geometry not saved: {e}")

    def hideEvent(self, ev):
        self._remember()
        super().hideEvent(ev)
