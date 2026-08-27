"""EntryPage -- the hot loop: species -> stage -> sex -> number -> Enter -> commit.

Dependency-injected so it can be tested without Observatum: it takes a species-search
widget, a write callable, a delete callable, and a quantity-update callable. On the real
machine these are Observatum's SpeciesSearch and the write_service; in tests they're fakes.

Keyboard flow: selecting a species advances to Stage (Adult default, Enter passes through);
Enter on Stage->Sex, Sex->Number, Number commits. Repeat clones the last species and lands
on Sex (for same-species sex-splits). Committed rows appear in the running session list,
newest first; double-click Qty to correct a count, or remove a row (deletes the record).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog, QAbstractItemView,
)

from DataEntry import theme


class EntryPage(QWidget):
    def __init__(
        self,
        header,
        species_search: QWidget,
        write_fn: Callable[[dict, str, str, int], Optional[int]],
        delete_fn: Callable[[int], None],
        update_qty_fn: Callable[[int, int], None],
        stage_options,
        sex_options,
        writable: bool = True,
        reason: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._header = header
        self._search = species_search
        self._write_fn = write_fn
        self._delete_fn = delete_fn
        self._update_qty_fn = update_qty_fn
        self._stage_options = list(stage_options)
        self._sex_options = list(sex_options)
        self._writable = writable
        self._reason = reason
        self._last_species: Optional[dict] = None
        self._count = 0
        self._build_ui()

    # -- ui --------------------------------------------------------------
    def _build_ui(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        if not self._writable:
            note = QLabel(self._reason or "Recording disabled.")
            note.setStyleSheet(
                f"color: {theme.PAPER}; background: {theme.GOLD}; font-size: 12px;"
                f"font-weight: 600; padding: 6px 10px; border-radius: 4px;"
            )
            note.setWordWrap(True)
            v.addWidget(note)

        # Entry row
        rowc = QFrame()
        rowc.setStyleSheet(
            f"background: {theme.CARD}; border: 1px solid {theme.LINE}; border-radius: 6px;"
        )
        row = QHBoxLayout(rowc)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)

        row.addWidget(self._search, 3)
        self._search.species_selected.connect(self._on_species_selected)

        self._stage = QComboBox()
        self._stage.setEditable(True)
        self._stage.addItems(self._stage_options)
        self._stage.setCurrentText(self._header.stage_default or "Adult")
        self._stage.setToolTip("Stage (Enter to pass through)")
        row.addWidget(self._stage, 1)

        self._sex = QComboBox()
        self._sex.setEditable(True)
        self._sex.addItem("")
        self._sex.addItems(self._sex_options)
        self._sex.setCurrentText("")
        self._sex.setToolTip("Sex")
        row.addWidget(self._sex, 1)

        self._number = QSpinBox()
        self._number.setMinimumWidth(70)
        self._number.setRange(1, 100000)
        self._number.setValue(1)
        self._number.setToolTip("Number (Enter to record)")
        self._number.installEventFilter(self)
        row.addWidget(self._number)

        self._add_btn = QPushButton("Record  \u21b5")
        self._add_btn.setStyleSheet(
            f"background: {theme.MOSS}; color: {theme.PAPER}; font-weight: 600;"
            f"padding: 6px 14px; border: none; border-radius: 5px;"
        )
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.clicked.connect(self._commit)
        self._add_btn.setEnabled(self._writable)
        row.addWidget(self._add_btn)

        v.addWidget(rowc)

        # Species confirmation + repeat
        confrow = QHBoxLayout()
        self._species_label = QLabel("Type a species to begin\u2026")
        self._species_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        self._species_label.setWordWrap(True)
        confrow.addWidget(self._species_label, 1)

        self._repeat_btn = QPushButton("Repeat species  \u27f2")
        self._repeat_btn.setStyleSheet(
            f"background: transparent; color: {theme.SLATE}; border: 1px solid {theme.SLATE};"
            f"padding: 4px 10px; border-radius: 5px; font-size: 12px;"
        )
        self._repeat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._repeat_btn.clicked.connect(self._repeat_last)
        self._repeat_btn.setEnabled(False)
        confrow.addWidget(self._repeat_btn)
        v.addLayout(confrow)

        # Stage/Sex Enter-advance wiring
        if self._stage.lineEdit():
            self._stage.lineEdit().returnPressed.connect(self._sex.setFocus)
        if self._sex.lineEdit():
            self._sex.lineEdit().returnPressed.connect(self._focus_number)

        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._repeat_last)

        # Running session list
        list_title = QLabel("This session")
        list_title.setStyleSheet(
            f"color: {theme.SLATE}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        v.addWidget(list_title)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Species", "Stage", "Sex", "Qty"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
            f"  border-radius: 6px; font-size: 12px; }}"
            f"QHeaderView::section {{ background: {theme.PAPER}; padding: 4px; border: none;"
            f"  border-bottom: 1px solid {theme.LINE}; font-weight: 600; }}"
        )
        v.addWidget(self._table, 1)

        botrow = QHBoxLayout()
        self._count_label = QLabel("0 records this session")
        self._count_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        botrow.addWidget(self._count_label, 1)
        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.setStyleSheet(
            f"background: transparent; color: {theme.CLAY}; border: 1px solid {theme.CLAY};"
            f"padding: 4px 10px; border-radius: 5px; font-size: 12px;"
        )
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.clicked.connect(self._remove_selected)
        botrow.addWidget(self._remove_btn)
        v.addLayout(botrow)

        if self._writable:
            self._search.setFocus()

    # -- behaviour -------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self._number and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._commit()
                return True
        return super().eventFilter(obj, event)

    def _focus_number(self):
        self._number.setFocus()
        self._number.selectAll()

    def _on_species_selected(self, data: dict):
        self._show_species(data)
        self._stage.setFocus()

    def _show_species(self, data: dict):
        sci = data.get("scientific_name", "")
        com = data.get("common_name") or ""
        fam = data.get("family") or ""
        order = data.get("order") or ""
        bits = [f"<i>{sci}</i>"]
        if com:
            bits.append(f"({com})")
        tail = " \u00b7 ".join(x for x in (order, fam) if x)
        label = " ".join(bits) + (f" &mdash; <span style='color:{theme.MUTED}'>{tail}</span>" if tail else "")
        self._species_label.setTextFormat(Qt.TextFormat.RichText)
        self._species_label.setText(label)

    def _current_species(self) -> Optional[dict]:
        getter = getattr(self._search, "get_selected_species", None)
        return getter() if callable(getter) else None

    def _commit(self):
        if not self._writable:
            return
        species = self._current_species()
        if not species or not species.get("tvk"):
            self._species_label.setText(
                f"<span style='color:{theme.CLAY}'>Select a species from the list first.</span>"
            )
            self._search.setFocus()
            return
        stage = self._stage.currentText().strip() or (self._header.stage_default or "")
        sex = self._sex.currentText().strip()
        qty = int(self._number.value())

        try:
            new_id = self._write_fn(species, stage, sex, qty)
        except Exception as e:
            self._species_label.setText(
                f"<span style='color:{theme.CLAY}'>Write failed: {e}</span>"
            )
            return
        if not new_id:
            self._species_label.setText(
                f"<span style='color:{theme.CLAY}'>Write returned no id \u2014 not saved.</span>"
            )
            return

        self._add_list_row(new_id, species.get("scientific_name", ""), stage, sex, qty)
        self._last_species = species
        self._repeat_btn.setEnabled(True)
        self._count += 1
        self._count_label.setText(f"{self._count} record{'s' if self._count != 1 else ''} this session")

        # reset for next record
        clearer = getattr(self._search, "clear", None)
        if callable(clearer):
            clearer()
        self._stage.setCurrentText(self._header.stage_default or "Adult")
        self._sex.setCurrentText("")
        self._number.setValue(1)
        self._species_label.setText("Type a species to begin\u2026")
        self._search.setFocus()

    def _repeat_last(self):
        if not self._last_species or not self._writable:
            return
        setter = getattr(self._search, "set_species", None)
        if callable(setter):
            setter(self._last_species)
        self._show_species(self._last_species)
        self._sex.setFocus()

    def _add_list_row(self, rec_id, species_name, stage, sex, qty):
        self._table.insertRow(0)
        cells = [species_name, stage, sex or "\u2014", str(qty)]
        for col, txt in enumerate(cells):
            item = QTableWidgetItem(txt)
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, rec_id)
                f = item.font(); f.setItalic(True); item.setFont(f)
            self._table.setItem(0, col, item)

    def _selected_row_id(self):
        r = self._table.currentRow()
        if r < 0:
            return None, -1
        item = self._table.item(r, 0)
        return (item.data(Qt.ItemDataRole.UserRole) if item else None), r

    def _remove_selected(self):
        rec_id, r = self._selected_row_id()
        if rec_id is None:
            return
        try:
            self._delete_fn(rec_id)
        except Exception as e:
            self._species_label.setText(f"<span style='color:{theme.CLAY}'>Delete failed: {e}</span>")
            return
        self._table.removeRow(r)
        self._count = max(0, self._count - 1)
        self._count_label.setText(f"{self._count} record{'s' if self._count != 1 else ''} this session")

    def _on_cell_double_clicked(self, row, col):
        if col != 3:  # only Qty is editable inline
            return
        id_item = self._table.item(row, 0)
        qty_item = self._table.item(row, 3)
        if not id_item or not qty_item:
            return
        rec_id = id_item.data(Qt.ItemDataRole.UserRole)
        try:
            current = int(qty_item.text())
        except ValueError:
            current = 1
        new_qty, ok = QInputDialog.getInt(self, "Correct count", "Quantity:", current, 1, 100000)
        if not ok:
            return
        try:
            self._update_qty_fn(rec_id, new_qty)
        except Exception as e:
            self._species_label.setText(f"<span style='color:{theme.CLAY}'>Update failed: {e}</span>")
            return
        qty_item.setText(str(new_qty))
