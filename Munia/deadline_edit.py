"""A deadline field that can hold any date, or nothing (review MUN-2, 9 Oct 2026).

The form used a QDateEdit whose minimum was 1 January of the season being viewed,
with the minimum itself standing for "not set". A deadline before that date could
not be shown -- Qt clamped it to the minimum -- so it read as "Not set", and saving
the project wrote "" over it.

Here "not set" is its own state: the value is "" until a date is picked or loaded,
and the earliest selectable date (1 Jan 1900) has nothing to do with the season.
A stored value that is not a yyyy-mm-dd date is kept as it is unless changed.
"""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit, QHBoxLayout, QToolButton, QWidget

from Munia.theme import STONE_BORDER, TEXT_MID, WARM_GRAY_LIGHT

_FLOOR = QDate(1900, 1, 1)      # Qt needs a minimum; it is shown as "Not set"
ISO = "yyyy-MM-dd"


class _DateBox(QDateEdit):
    """QDateEdit whose calendar opens on today's month when no date is set."""

    def mousePressEvent(self, event):
        unset = self.date() == self.minimumDate()
        super().mousePressEvent(event)
        if unset and self.calendarWidget() is not None:
            today = QDate.currentDate()
            self.calendarWidget().setCurrentPage(today.year(), today.month())


class DeadlineEdit(QWidget):
    """Date box plus a clear button. value() is 'yyyy-mm-dd' or ''."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.date_edit = _DateBox()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setMinimumDate(_FLOOR)
        self.date_edit.setMaximumDate(QDate(9999, 12, 31))
        self.date_edit.setSpecialValueText("Not set")
        self.date_edit.setFixedWidth(110)
        lay.addWidget(self.date_edit)
        self.clear_btn = QToolButton()
        self.clear_btn.setText("×")
        self.clear_btn.setToolTip("Clear this deadline")
        self.clear_btn.setStyleSheet(
            f"QToolButton {{ border: 1px solid {STONE_BORDER}; border-radius: 3px; "
            f"color: {TEXT_MID}; padding: 0 4px; }}"
            f"QToolButton:hover {{ background: {WARM_GRAY_LIGHT}; }}")
        self.clear_btn.clicked.connect(self.clear)
        lay.addWidget(self.clear_btn)
        self._unparsed = ""             # a stored value we could not read as a date
        self.date_edit.dateChanged.connect(self._on_changed)
        self.clear()

    def _on_changed(self, _d):
        self._unparsed = ""             # the user picked something: that is the value now

    def is_set(self) -> bool:
        return self.date_edit.date() != self.date_edit.minimumDate() or bool(self._unparsed)

    def value(self) -> str:
        if self.date_edit.date() != self.date_edit.minimumDate():
            return self.date_edit.date().toString(ISO)
        return self._unparsed

    def set_value(self, text) -> None:
        text = (text or "").strip()
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(self.date_edit.minimumDate())
        self.date_edit.blockSignals(False)
        self._unparsed = ""
        if not text:
            return
        d = QDate.fromString(text, ISO)
        if d.isValid() and d > self.date_edit.minimumDate():
            self.date_edit.blockSignals(True)
            self.date_edit.setDate(d)
            self.date_edit.blockSignals(False)
        else:
            self._unparsed = text       # keep it rather than save "" over it
            self.date_edit.setToolTip(f"Stored as: {text}")

    def clear(self) -> None:
        self.set_value("")
        self.date_edit.setToolTip("")
