"""Typing in a filter box waits for a pause before the table reloads (speed, 10 Oct 2026).

Every keystroke in a filter-bar text box used to reload the table: "Rhagium mordx" on the
Recording Scheme tab was 13 reloads of up to 110,510 records. Now:

  * typing (textEdited -- the user's own keys) reloads once, DEBOUNCE_MS after the last key;
  * Enter applies at once;
  * text set by the program (setText / clear: navigation, saved filters, Clear All) applies
    at once, as before -- Qt sends textEdited only for the user's keys, before textChanged.

    debounce_text(self.species_edit, self._emit_filters)
"""
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLineEdit

DEBOUNCE_MS = 350


def debounce_text(edit: QLineEdit, slot: Callable[[], None], ms: int = DEBOUNCE_MS,
                  apply_on_enter: bool = True) -> QTimer:
    """Call slot() once typing in `edit` pauses (see module doc). Returns the timer, which
    is also kept as edit._filter_debounce (tests and flush_pending use it).

    apply_on_enter=False when the box already applies on Enter itself (returnPressed is
    connected elsewhere): Enter then only cancels the pending reload, so it runs once."""
    timer = QTimer(edit)
    timer.setSingleShot(True)
    timer.setInterval(ms)
    timer.timeout.connect(lambda: slot())

    def on_changed(_text):
        if not timer.isActive():          # set by the program: apply now
            slot()

    def on_enter():
        if timer.isActive():
            timer.stop()
            if apply_on_enter:
                slot()

    edit.textEdited.connect(lambda _text: timer.start())   # restarts on every key
    edit.textChanged.connect(on_changed)
    edit.returnPressed.connect(on_enter)
    edit._filter_debounce = timer
    return timer


def cancel_pending(*edits: QLineEdit) -> None:
    """Drop any reload still waiting on these boxes (a Clear All applies once itself)."""
    for e in edits:
        timer = getattr(e, "_filter_debounce", None)
        if timer is not None:
            timer.stop()


__all__ = ["DEBOUNCE_MS", "debounce_text", "cancel_pending"]
