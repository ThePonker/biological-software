"""The grid's cell delegates and the species picker (split from entry_grid.py, R13)."""
from __future__ import annotations


from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QStyledItemDelegate, QComboBox, QSpinBox, QLineEdit, QListWidget, QListWidgetItem, QDialog, QDialogButtonBox,
)

from DataEntry import theme


def _select_all(editor):
    if isinstance(editor, QLineEdit):
        editor.selectAll()
    elif isinstance(editor, QSpinBox):
        editor.selectAll()
    elif isinstance(editor, QComboBox) and editor.lineEdit() is not None:
        editor.lineEdit().selectAll()


class _EnterMovesDown:
    """Mixin: pressing Enter in an editor commits the cell and moves DOWN a row (Excel-style).

    If a combo's dropdown popup is open, Enter is left to the combo (to pick the item) instead.
    """
    def eventFilter(self, editor, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if isinstance(editor, QComboBox) and editor.view().isVisible():
                return super().eventFilter(editor, event)  # let the popup take Enter
            self.commitData.emit(editor)
            self.closeEditor.emit(editor)
            view = self.parent()
            mover = getattr(view, "move_down_from_editor", None)
            if callable(mover):
                mover()
            return True
        return super().eventFilter(editor, event)


class _TextDelegate(_EnterMovesDown, QStyledItemDelegate):
    """Plain text cell, but selects existing text on edit so you can type over it."""
    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)
        _select_all(editor)


class _OptionDelegate(_EnterMovesDown, QStyledItemDelegate):
    def __init__(self, options, parent=None, default=""):
        super().__init__(parent)
        self._options = list(options)
        self._default = default

    def createEditor(self, parent, option, index):
        cb = QComboBox(parent)
        cb.setEditable(True)
        cb.addItem("")
        cb.addItems([str(o) for o in self._options])
        return cb

    def setEditorData(self, editor, index):
        editor.setCurrentText(index.data(Qt.ItemDataRole.EditRole) or self._default)
        _select_all(editor)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class _CheckDelegate(_EnterMovesDown, QStyledItemDelegate):
    """The Check cell: double-click, Space or Ctrl+T toggles it (EntryTableView); typing opens
    a small editor -- "to check" (or x, y, t) marks the row, anything else clears it."""
    def createEditor(self, parent, option, index):
        from PySide6.QtWidgets import QCompleter, QLineEdit
        ed = QLineEdit(parent)
        comp = QCompleter(["to check"], ed)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        ed.setCompleter(comp)
        return ed

    def setEditorData(self, editor, index):
        editor.setText("")

    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)


class _NumberDelegate(_TextDelegate):
    """No. / VC No.: typed as text. A spin box turned anything it could not read ('c.20',
    '0') into 1 without a word (review DE9); now the model keeps what was typed and flags
    it, and the row stays in staging until it is a whole number."""


from shared.species_rank import resolve_name   # one decision for every species search


def _to_species_dict(r):
    return {
        "scientific_name": r.get("scientific_name"),
        "tvk": r.get("tvk"),
        "common_name": r.get("common_name"),
        "family": r.get("family"),
        "order": r.get("order"),
        "rank": r.get("rank"),
    }


class _PickList(QListWidget):
    """List for the picker: digits 1-9 quick-pick, Enter activates current."""
    def keyPressEvent(self, event):
        k = event.key()
        if Qt.Key.Key_1 <= k <= Qt.Key.Key_9:
            idx = k - Qt.Key.Key_1
            if idx < self.count():
                self.setCurrentRow(idx)
                self.itemActivated.emit(self.item(idx))
                return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            it = self.currentItem()
            if it:
                self.itemActivated.emit(it)
                return
        super().keyPressEvent(event)


class SpeciesPickerDialog(QDialog):
    """Tabella-style pick box: shown only when 2+ matches. Keyboard-first."""
    def __init__(self, term, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Species lookup")
        self.setMinimumWidth(460)
        self.chosen = None
        self.setStyleSheet(theme.input_qss())

        v = QVBoxLayout(self)
        lbl = QLabel(f"{'Multiple matches' if len(results) > 1 else 'A close match'} for "
                     f"\u201c{term}\u201d \u2014 choose one:")
        lbl.setStyleSheet(f"color: {theme.INK}; font-size: 13px;")
        lbl.setWordWrap(True)
        v.addWidget(lbl)

        self.listw = _PickList()
        self.listw.setStyleSheet(
            f"QListWidget {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
            f" font-size: 13px; outline: none; }}"
            f"QListWidget::item {{ padding: 4px 6px; }}"
            f"QListWidget::item:selected {{ background: {theme.SLATE}; color: {theme.PAPER}; }}"
        )
        for i, r in enumerate(results[:50], 1):
            label = f"{i}.  {r.get('scientific_name', '')}"
            cn = r.get("common_name")
            fam = r.get("family")
            if cn:
                label += f"   ({cn})"
            if fam:
                label += f"   [{fam}]"
            if r.get("old_name"):            # shared species search: a hit through an old name
                label += f"   \u2014 old name: {r['old_name']}"
            elif r.get("match_type") == "fuzzy":
                label += "   \u2014 close spelling"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r)
            self.listw.addItem(it)
        self.listw.setCurrentRow(0)
        self.listw.itemActivated.connect(self._accept_item)
        self.listw.itemDoubleClicked.connect(self._accept_item)
        v.addWidget(self.listw)

        hint = QLabel("Up/Down + Enter, type the number, or double-click. Esc to cancel.")
        hint.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px;")
        v.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept_current)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)
        self.listw.setFocus()

    def _accept_item(self, item):
        self.chosen = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _accept_current(self):
        it = self.listw.currentItem()
        if it:
            self._accept_item(it)


class SpeciesCascadeDelegate(_EnterMovesDown, QStyledItemDelegate):
    """Type a name; on commit run Tabella's cascade:
       exact -> fill silent; one fuzzy -> fill silent; 2+ -> modal picker; none -> unresolved.
    """
    def __init__(self, search_service, parent=None):
        super().__init__(parent)
        self._service = search_service

    def createEditor(self, parent, option, index):
        return QLineEdit(parent)

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.ItemDataRole.EditRole) or "")
        editor.selectAll()
        editor._original = index.data(Qt.ItemDataRole.EditRole) or ""

    def _resolve(self, text):
        try:
            return list(self._service.search_species(text, limit=25) or [])
        except Exception:
            return []

    def decide(self, text, interactive=True):
        """Return one of: ('fill', dict) | ('pick', ranked_list) | ('unresolved', text).

        The rules are shared.species_rank.resolve_name (B4/B6): a paste (interactive=False)
        never guesses, and a hit through part of a common name is never filled silently.
        """
        if not self._service:
            return ("unresolved", text)
        action, payload = resolve_name(text, self._resolve(text), interactive=interactive)
        if action == "fill":
            return ("fill", _to_species_dict(payload))
        if action == "pick":
            return ("pick", payload)
        return ("unresolved", text)

    def setModelData(self, editor, model, index):
        text = editor.text().strip()
        original = (getattr(editor, "_original", "") or "")
        if text == original:
            return
        if not text:
            model.setData(index, {"scientific_name": None}, Qt.ItemDataRole.EditRole)
            return
        action, payload = self.decide(text)
        if action == "fill":
            model.setData(index, payload, Qt.ItemDataRole.EditRole)
        elif action == "pick":
            parent = self.parent()
            dlg = SpeciesPickerDialog(text, payload, parent if isinstance(parent, QWidget) else None)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.chosen:
                model.setData(index, _to_species_dict(dlg.chosen), Qt.ItemDataRole.EditRole)
            else:
                model.setData(index, {"scientific_name": text}, Qt.ItemDataRole.EditRole)  # unresolved
        else:  # unresolved
            model.setData(index, {"scientific_name": text}, Qt.ItemDataRole.EditRole)
