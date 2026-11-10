"""ReferenceField -- the optional "Reference" line edit (26 Oct 2026; shared/data_reference.py).

Typing lists the references already used in observations, recording_scheme and
contributed_observations that contain the text (case-insensitive, anywhere), most recently
used first, at most 15, so the naming convention is followed. Disabled with a tooltip while
the data_reference column is not in the database yet.
"""
from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import QCompleter, QLineEdit

from shared import data_reference as dr


class ReferenceField(QLineEdit):
    def __init__(self, db=None, table: str = "observations", parent=None, filter_mode: bool = False):
        super().__init__(parent)
        self._db = None
        self._connected = False
        self.available = False
        self.setPlaceholderText("Contains..." if filter_mode else dr.PLACEHOLDER)
        self.setClearButtonEnabled(True)
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchContains)
        self._completer.setMaxVisibleItems(dr.MAX_SUGGESTIONS)
        self.setCompleter(self._completer)
        self.bind(db, table)

    def bind(self, db, table: str = "observations") -> bool:
        """Point the field at a database: enabled when `table` has the Reference column."""
        self._db = db
        self.available = dr.db_has_column(db, table)
        if self.available:
            self.setEnabled(True)
            self.setToolTip(dr.TOOLTIP_FIELD)
            if not self._connected:
                self.textEdited.connect(self.refresh_suggestions)
                self._connected = True
            self.refresh_suggestions(self.text())
        else:
            self.setEnabled(False)
            self.setToolTip(dr.TOOLTIP_MISSING)
        return self.available

    def refresh_suggestions(self, text: str = "") -> list:
        items = dr.db_suggestions(self._db, text)
        self._model.setStringList(items)
        return items

    def suggestions(self) -> list:
        return self._model.stringList()

    def reference(self):
        """The cleaned value, or None when empty or the column is not there."""
        return dr.clean(self.text()) if self.available else None
