"""
Dataset / provider picker for the Filter Wizard's Status card (Recording Scheme).

Decision 4 (10 Oct): the scheme bar's Source stays the import route (iRecord / NBN
Atlas / Other); this picker chooses where scheme records came from -- the NBN Atlas
data provider's dataset or the iRecord survey (stored in recording_scheme.source).
There are a few hundred, so it is a searchable tick list showing "<dataset> (n)".
The wizard key is 'dataset' (services/filter_builder.py).
"""

from typing import Iterable, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ....themes import theme


class DatasetPicker(QWidget):
    """Search box + tick list of datasets with their record counts."""

    def __init__(self, datasets: Iterable[Tuple[str, int]], accent_color: str, parent=None):
        super().__init__(parent)
        self._accent = accent_color
        self.setStyleSheet("background: transparent;")
        t = theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Dataset / provider")
        label.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; "
                            "font-size: 13px; background: transparent;")
        layout.addWidget(label)

        hint = QLabel("Where the records came from: the NBN Atlas dataset or the iRecord survey. "
                      "Tick one or more (any of them).")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 11px; background: transparent;")
        layout.addWidget(hint)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Type to narrow the list...")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 6px 10px;
                color: {t.get('text_primary')};
            }}
            QLineEdit:focus {{ border-color: {accent_color}; }}
        """)
        self.search.textChanged.connect(self._narrow)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setMinimumHeight(200)
        self.list.setStyleSheet(f"""
            QListWidget {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                color: {t.get('text_primary')};
            }}
        """)
        for name, n in datasets:
            item = QListWidgetItem(f"{name} ({n:,})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list)

    def _items(self):
        return [self.list.item(i) for i in range(self.list.count())]

    def _narrow(self, text: str):
        needle = text.strip().casefold()
        for item in self._items():
            name = str(item.data(Qt.ItemDataRole.UserRole))
            # ticked rows stay visible so a choice is never hidden by the search
            item.setHidden(bool(needle) and needle not in name.casefold()
                           and item.checkState() != Qt.CheckState.Checked)

    def set_selected(self, names: Iterable[str]):
        wanted = {str(n).casefold() for n in names or []}
        for item in self._items():
            name = str(item.data(Qt.ItemDataRole.UserRole))
            item.setCheckState(Qt.CheckState.Checked if name.casefold() in wanted
                               else Qt.CheckState.Unchecked)

    def selected(self) -> List[str]:
        return [str(item.data(Qt.ItemDataRole.UserRole)) for item in self._items()
                if item.checkState() == Qt.CheckState.Checked]

    def clear(self):
        self.search.clear()
        self.set_selected([])
