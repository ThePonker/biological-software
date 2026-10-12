"""
Species Search Component with manual popup.
Uses QListWidget popup for full keyboard control.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt, QTimer, QPoint

from shared.species_list_delegate import HIT_ROLE, SpeciesListDelegate, hit_from_result
from ...themes import theme

MAX_ROWS = 15      # rows shown before the list scrolls


def species_note(r):
    """'old name: X' for a hit through a UKSI synonym, 'close spelling' for a typing slip."""
    if r.get('old_name'):
        return "\u2014 old name: " + r['old_name']
    if r.get('match_type') == 'fuzzy':
        return "\u2014 close spelling"
    return ""


class SpeciesSearch(QWidget):
    species_selected = Signal(dict)
    search_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_service = None
        self._selected_species = None
        self._results = []
        self._is_selecting = False
        self._search_delay = 250
        self._min_chars = 2
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search species (scientific or common name)...")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.installEventFilter(self)
        layout.addWidget(self.search_input)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._popup = QListWidget()
        self._popup.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        t = theme()
        # one plain line per species, its height from the font (F49, 12 Oct 2026: a fixed
        # 32 px row cut the tails of g, p and y on Windows)
        self._popup.setItemDelegate(SpeciesListDelegate(
            self._popup, secondary=t.get('text_secondary'), selected_text=t.get('text_primary')))
        self._popup.setMouseTracking(True)
        self._popup.itemClicked.connect(self._on_popup_clicked)
        self._popup.setStyleSheet(
            f"QListWidget {{ border: 1px solid {t.get('border')}; border-radius: 4px; "
            f"background: {t.get('surface')}; color: {t.get('text_primary')}; }}"
            f"QListWidget::item:hover {{ background: {t.get('hover')}; }}"
            f"QListWidget::item:selected {{ background: {t.get('surface_alt')}; "
            f"color: {t.get('text_primary')}; }}"
        )

    def _setup_timer(self):
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_search)

    def set_search_service(self, service):
        self._search_service = service

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj == self.search_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if self._popup.isVisible():
                if key == Qt.Key.Key_Down:
                    row = self._popup.currentRow()
                    if row < self._popup.count() - 1:
                        self._popup.setCurrentRow(row + 1)
                    return True
                elif key == Qt.Key.Key_Up:
                    row = self._popup.currentRow()
                    if row > 0:
                        self._popup.setCurrentRow(row - 1)
                    return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                    current = self._popup.currentItem()
                    if current:
                        self._select_item(current)
                    return True
                elif key == Qt.Key.Key_Escape:
                    self._popup.hide()
                    return True
        return super().eventFilter(obj, event)

    def _on_text_changed(self, text):
        if self._is_selecting:
            return
        if self._selected_species:
            n = self._selected_species.get('scientific_name', '')
            if text != n:
                self._selected_species = None
        if len(text) >= self._min_chars:
            self._timer.start(self._search_delay)
        else:
            self._popup.hide()
            self._results.clear()
            if not text:
                self.search_cleared.emit()

    def _do_search(self):
        if self._is_selecting:
            return
        text = self.search_input.text().strip()
        if len(text) < self._min_chars:
            self._popup.hide()
            return
        svc = self._search_service
        if not svc:
            from ...services.search_service import get_search_service
            svc = get_search_service()
        if not svc:
            return
        results = svc.search_species(search_term=text, limit=40, boost_recorded=True)
        try:   # the Data Entry grid's ranking: "rut mac" -> Rutpela maculata first
            from shared.species_rank import rank_matches
            results = rank_matches(text, results or [])[:15]
        except Exception as e:
            print(f"[SpeciesSearch] ranking unavailable: {e}")
            results = (results or [])[:15]
        if results:
            self._results = results
            self._show_popup(results)
        else:
            self._results.clear()
            self._popup.hide()

    def _show_popup(self, results):
        self._popup.clear()
        for r in results:
            sci = r.get('label') or r.get('scientific_name', '')
            fam = r.get('family', '')
            rec = r.get('is_recorded', False)
            parts = [sci]
            if fam:
                parts.append("- " + fam)
            if rec:
                parts.append("\u2605")
            if species_note(r):
                parts.append(species_note(r))
            item = QListWidgetItem(" ".join(parts))
            item.setData(Qt.ItemDataRole.UserRole, r)
            item.setData(HIT_ROLE, hit_from_result(r, family=True))
            self._popup.addItem(item)
        pos = self.search_input.mapToGlobal(QPoint(0, self.search_input.height()))
        self._popup.setFixedWidth(self.search_input.width())
        self._popup.setFixedHeight(self.popup_height())
        self._popup.move(pos)
        self._popup.setCurrentRow(0)
        self._popup.show()

    def popup_height(self) -> int:
        """The list's height: its rows as the font draws them (up to MAX_ROWS), plus frame."""
        n = min(self._popup.count(), MAX_ROWS)
        rows = sum(self._popup.sizeHintForRow(i) for i in range(n))
        return rows + 2 * self._popup.frameWidth() + 2

    def _on_popup_clicked(self, item):
        self._select_item(item)

    def _select_item(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        self._is_selecting = True
        self._timer.stop()
        self._popup.hide()
        self._selected_species = data
        sci = data.get('scientific_name', '')
        com = data.get('common_name', '')
        display = com + " (" + sci + ")" if com else sci
        self.search_input.blockSignals(True)
        self.search_input.setText(display)
        self.search_input.blockSignals(False)
        self.species_selected.emit(data)
        self.search_input.focusNextChild()
        self._is_selecting = False

    def set_species(self, data):
        self._is_selecting = True
        self._selected_species = data
        sci = data.get('scientific_name', '')
        com = data.get('common_name', '')
        display = com + " (" + sci + ")" if com else sci
        self.search_input.setText(display)
        self._is_selecting = False

    def set_species_by_name(self, name):
        self._is_selecting = True
        self._selected_species = {'scientific_name': name}
        self.search_input.setText(name)
        self._is_selecting = False

    def clear(self):
        self._is_selecting = True
        self._selected_species = None
        self.search_input.clear()
        self._popup.hide()
        self._results.clear()
        self._is_selecting = False
        self.search_cleared.emit()

    def get_selected_species(self):
        return self._selected_species

    def get_selected_tvk(self):
        if self._selected_species:
            return self._selected_species.get('tvk')
        return None

    def get_selected_name(self):
        if self._selected_species:
            return self._selected_species.get('scientific_name', '')
        return self.search_input.text()

    def has_valid_selection(self):
        return self._selected_species is not None and 'tvk' in self._selected_species

    def set_placeholder(self, text):
        self.search_input.setPlaceholderText(text)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.search_input.setEnabled(enabled)
