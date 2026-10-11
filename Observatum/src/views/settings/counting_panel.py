"""Settings > Species counting (backlog A, 10 Oct 2026).

Which kinds of name each data source leaves out of its counts, maps and lists. Two sets:
Observations and Recording Scheme. The Scheme dashboard's chips change the same Recording
Scheme settings; a change in either place shows in the other at once.

The rule itself is shared/species_counting.py (kinds from shared/record_kinds.py).
"""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QFrame, QGroupBox, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from shared.species_counting import (OFFERED, excluded_kinds, kind_label, notifier,
                                     set_excluded)

from ...themes import theme

_INTRO = ("Records with incomplete names (genus only, aggregates and so on) are always kept "
          "and always listed. Ticked kinds are left out of counts, statistics, maps and "
          "species lists. On the Observation Data and Recording Scheme tables they are shown "
          "dimmed, and \"Show only excluded\" on the filter bar lists just them.")

_NOTES = {
    "observations": ("Subspecies and \"s.s.\" records always count, as their species: a "
                     "species and its subspecies count as one. Hybrids count as their own "
                     "taxon. Contributed records and the Insect Collection are never left out."),
    "recording_scheme": ("The chips on the Recording Scheme dashboard change these same "
                         "settings."),
}

_TITLES = {"observations": "Observations (Home, Observation Data, Stats, Mapping...)",
           "recording_scheme": "Recording Scheme"}


class SpeciesCountingPanel(QScrollArea):
    """Two sets of tick boxes, saved as soon as they change."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._boxes = {}           # (source, kind) -> QCheckBox
        self._setup_ui()
        self.load_settings()
        notifier().changed.connect(self._on_changed_elsewhere)

    def _setup_ui(self):
        t = theme()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 20, 20)
        layout.setSpacing(16)

        intro = QLabel(_INTRO)
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {t.get('text_secondary')};")
        layout.addWidget(intro)

        for source in OFFERED:
            group = QGroupBox(_TITLES[source])
            gl = QVBoxLayout(group)
            gl.addWidget(QLabel("Leave out:"))
            for kind in OFFERED[source]:
                box = QCheckBox(kind_label(kind))
                box.toggled.connect(lambda _on, s=source: self._save(s))
                gl.addWidget(box)
                self._boxes[(source, kind)] = box
            note = QLabel(_NOTES[source])
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px;")
            gl.addWidget(note)
            layout.addWidget(group)

        layout.addStretch()
        self.setWidget(content)

    def load_settings(self):
        for source in OFFERED:
            self._show(source)

    def _show(self, source: str):
        on = excluded_kinds(source)
        for kind in OFFERED[source]:
            box = self._boxes[(source, kind)]
            box.blockSignals(True)
            box.setChecked(kind in on)
            box.blockSignals(False)

    def _save(self, source: str):
        set_excluded(source, [k for k in OFFERED[source] if self._boxes[(source, k)].isChecked()])

    def _on_changed_elsewhere(self, source: str):
        if source in OFFERED:
            self._show(source)

    def apply_theme(self):
        pass
