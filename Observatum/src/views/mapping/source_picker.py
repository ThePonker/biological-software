"""The Mapping tab's data sources as tick boxes (L8, 10 Oct 2026): Personal, Commercial,
Insect Collection, Recording Scheme, Contributed, and "All" (= every box ticked). Several at
once, e.g. Personal + Contributed. Was one drop-down in the toolbar.

The sources are the suite's split (services/map_selection.py): Personal = your own
non-Commercial observations; specimens are under Insect Collection (decision 13).
"""
from typing import List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel, QVBoxLayout, QWidget

from ...services.map_selection import BASE_SOURCES, normalise_sources
from ...themes import theme

DEFAULT_SOURCES = ("personal",)
SHORT_LABELS = {"personal": "Personal", "commercial": "Commercial",
                "collection": "Insect Collection", "scheme": "Recording Scheme",
                "contributed": "Contributed"}
TIPS = {
    "personal": "Your own observations that are not Commercial (specimens are under "
                "Insect Collection)",
    "commercial": "Commercial survey observations (embargoed ones only if the box below is "
                  "ticked)",
    "collection": "Specimens in your Insect Collection",
    "scheme": "The Recording Scheme dataset",
    "contributed": "Records contributed by other people",
}


def sources_label(sources) -> str:
    """'Personal records', 'Personal + Contributed records', 'All records' (the subtitle)."""
    srcs = normalise_sources(sources)
    if not srcs:
        return "No data source"
    if srcs == BASE_SOURCES:
        return "All records"
    if len(srcs) == 1 and srcs[0] in ("collection", "scheme"):
        return SHORT_LABELS[srcs[0]]
    return " + ".join(SHORT_LABELS[s] for s in srcs) + " records"


class MapSourcePicker(QWidget):
    """Tick boxes for the data sources. sources_changed carries the ticked keys."""

    sources_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        t = theme()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        head = QLabel("Data sources")
        head.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {t.get('text_secondary')};")
        lay.addWidget(head)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        self.boxes = {}
        for i, key in enumerate(BASE_SOURCES):
            box = QCheckBox(SHORT_LABELS[key])
            box.setToolTip(TIPS[key])
            box.toggled.connect(self._on_box)
            grid.addWidget(box, i // 2, i % 2)
            self.boxes[key] = box
        self.all_box = QCheckBox("All")
        self.all_box.setToolTip(
            "Every source, each record once: a specimen with its own observation, and a "
            "scheme record that is one of your observations, appear as the observation.")
        self.all_box.clicked.connect(self._on_all)
        grid.addWidget(self.all_box, 2, 1)
        lay.addLayout(grid)
        self.set_sources(DEFAULT_SOURCES, emit=False)

    def sources(self) -> List[str]:
        return [k for k in BASE_SOURCES if self.boxes[k].isChecked()]

    def set_sources(self, sources, emit: bool = True):
        """Tick exactly these ('all' or keys); one sources_changed at most."""
        wanted = set(normalise_sources(sources))
        before = self.sources()
        for k, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(k in wanted)
            box.blockSignals(False)
        self._sync_all()
        if emit and self.sources() != before:
            self.sources_changed.emit(self.sources())

    def reset(self, emit: bool = True):
        self.set_sources(DEFAULT_SOURCES, emit=emit)

    def _on_all(self, checked: bool):
        """All ticked -> every source; unticked -> back to the default (Personal)."""
        self.set_sources(BASE_SOURCES if checked else DEFAULT_SOURCES)

    def _on_box(self, _checked: bool):
        self._sync_all()
        self.sources_changed.emit(self.sources())

    def _sync_all(self):
        self.all_box.blockSignals(True)
        self.all_box.setChecked(len(self.sources()) == len(BASE_SOURCES))
        self.all_box.blockSignals(False)
