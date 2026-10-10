"""Contributed tab -- read-only browse of contributed records (backlog K1, 9 Oct 2026).

Records other people sent Wil live in `contributed_observations` (scripts/
import_contributed.py). Stats, mapping and iRecord never see them; this tab is the one
place in Observatum to look at them. Left: a tree Contributor > Project > Import batch
with counts. Right: a filter box, a count line and the records. Nothing here edits or
deletes; the database is opened read-only for each load.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QSplitter, QTableView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from shared.display_format import dmy
from ...core.config import TabColors
from ...models.database import get_database
from ...repositories.contributed_repository import (
    COLUMNS, fetch_records, has_table, list_groups, open_ro,
)
from ...themes import theme
from ..components.filter_debounce import debounce_text
from ..components.filter_styles import get_input_style

ACCENT, ACCENT_LIGHT = TabColors.OBSERVATION, TabColors.OBSERVATION_LIGHT
DATE_COLUMNS = {"date", "received_date"}
NUMERIC_COLUMNS = {"quantity"}
NO_PROJECT, NO_BATCH = "(no project)", "(no batch)"
SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class ContributedTab(QWidget):
    """Read-only browser for contributed_observations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filters = []          # tree node index -> (contributor, project, batch)
        self._current = (None, ..., ...)
        self._initialized = False
        self._setup_ui()

    # ------------------------------------------------------------------ UI
    def _setup_ui(self):
        t = theme()
        self.setStyleSheet(f"background-color: {t.get('background')};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QFrame()
        bar.setStyleSheet(f"background-color: {t.get('surface')}; "
                          f"border-bottom: 1px solid {t.get('border')};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 16, 8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter: species, site, recorder, project, file...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(320)
        self.search_edit.setStyleSheet(get_input_style())
        debounce_text(self.search_edit, self._load_records)   # once typing pauses
        bl.addWidget(self.search_edit)
        note = QLabel("Read only - records other people sent you. Not in stats, maps or iRecord.")
        note.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: {t.font_size('sm')}; "
                           "border: none;")
        bl.addWidget(note)
        bl.addStretch()
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color: {t.get('text_secondary')}; "
                                       f"font-size: {t.font_size('sm')}; border: none;")
        bl.addWidget(self.count_label)
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reload_btn.setStyleSheet(self._button_style(t))
        self.reload_btn.clicked.connect(self.refresh)
        bl.addWidget(self.reload_btn)
        layout.addWidget(bar)

        content = QWidget()
        content.setStyleSheet(f"background-color: {ACCENT_LIGHT};")
        cl = QHBoxLayout(content)
        cl.setContentsMargins(16, 16, 16, 16)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._make_tree(t))
        splitter.addWidget(self._make_table(t))
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 1000])
        cl.addWidget(splitter)
        layout.addWidget(content, 1)

    def _make_tree(self, t):
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Contributor / project / batch", "Records"])
        self.tree.setColumnCount(2)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
            }}
            QTreeWidget::item {{ padding: 3px 2px; }}
            QTreeWidget::item:selected {{ background-color: {ACCENT_LIGHT};
                                          color: {t.get('text_primary')}; }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')}; padding: 6px; border: none;
                border-bottom: 1px solid {t.get('border')}; font-weight: 600;
            }}
        """)
        self.tree.currentItemChanged.connect(self._on_node_changed)
        return self.tree

    def _make_table(self, t):
        self.model = QStandardItemModel(0, len(COLUMNS), self)
        self.model.setHorizontalHeaderLabels([h for _, h in COLUMNS])
        self.model.setSortRole(SORT_ROLE)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: {t.get('radius_lg')};
                gridline-color: {t.get('border')};
                alternate-background-color: {t.get('surface_alt')};
            }}
            QTableView::item {{ padding: 4px 8px; border: none; }}
            QTableView::item:selected {{ background-color: {ACCENT_LIGHT};
                                         color: {t.get('text_primary')}; }}
            QHeaderView::section {{
                background-color: {t.get('surface_alt')}; padding: 8px; border: none;
                border-bottom: 1px solid {t.get('border')}; font-weight: 600;
            }}
        """)
        return self.table

    @staticmethod
    def _button_style(t):
        return f"""
            QPushButton {{
                padding: 6px 12px; border: 1px solid {ACCENT};
                border-radius: {t.get('radius_sm')}; background: {t.get('surface')};
                color: {ACCENT}; font-size: {t.font_size('sm')};
            }}
            QPushButton:hover {{ background-color: {ACCENT_LIGHT}; }}
        """

    # ------------------------------------------------------------------ data
    def initialize(self):
        """Load on first visit (main window calls this lazily)."""
        if not self._initialized:
            self._initialized = True
            self.refresh()

    def refresh(self):
        """Re-read the tree and records, keeping the selected node where possible."""
        groups = self._read(list_groups)
        if groups is None:
            return
        keep = self._current
        self.tree.blockSignals(True)
        self.tree.clear()
        self._filters = []
        total = sum(g["n"] for g in groups)
        root = self._add_node(self.tree, "All contributed records", total, (None, ..., ...))
        select = root
        by_contrib, by_project = {}, {}
        for g in groups:
            c, p, b = g["contributor"], g["project_name"], g["import_batch"]
            if c not in by_contrib:
                by_contrib[c] = self._add_node(root, c, 0, (c, ..., ...))
            if (c, p) not in by_project:
                by_project[(c, p)] = self._add_node(by_contrib[c], p or NO_PROJECT, 0, (c, p, ...))
            label = self._batch_label(g)
            node = self._add_node(by_project[(c, p)], label, g["n"], (c, p, b))
            node.setToolTip(0, f"Import batch: {b or NO_BATCH}\nSource file: "
                               f"{g['source_file'] or '-'}\nReceived: {dmy(g['received_date']) or '-'}")
            for parent in (by_contrib[c], by_project[(c, p)]):
                parent.setText(1, str(int(parent.text(1)) + g["n"]))
        for i, f in enumerate(self._filters):
            if f == keep:
                select = self._item_for(i) or root
        self.tree.expandAll()
        self.tree.blockSignals(False)
        self.tree.setCurrentItem(select)
        self._current = self._filters[select.data(0, Qt.ItemDataRole.UserRole)]
        self._load_records()

    def _add_node(self, parent, text, n, flt):
        item = QTreeWidgetItem(parent, [text, str(n)])
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setData(0, Qt.ItemDataRole.UserRole, len(self._filters))
        self._filters.append(flt)
        return item

    def _item_for(self, index):
        it = self.tree.invisibleRootItem()
        stack = [it.child(i) for i in range(it.childCount())]
        while stack:
            item = stack.pop()
            if item.data(0, Qt.ItemDataRole.UserRole) == index:
                return item
            stack.extend(item.child(i) for i in range(item.childCount()))
        return None

    @staticmethod
    def _batch_label(g):
        """'02/10/2026 - Birmingham_Wheels.xlsx' (received date and file), else the batch."""
        parts = [dmy(g["received_date"]) if g["received_date"] else "", g["source_file"] or ""]
        label = " - ".join(p for p in parts if p)
        return label or g["import_batch"] or NO_BATCH

    def _on_node_changed(self, current, _previous):
        if current is None:
            return
        self._current = self._filters[current.data(0, Qt.ItemDataRole.UserRole)]
        self._load_records()

    def _load_records(self):
        c, p, b = self._current
        rows = self._read(fetch_records, contributor=c, project=p, batch=b,
                          text=self.search_edit.text())
        if rows is None:
            return
        self.table.setSortingEnabled(False)
        self.model.setRowCount(0)
        for r in rows:
            self.model.appendRow([self._cell(key, r.get(key)) for key, _ in COLUMNS])
        self.table.setSortingEnabled(True)
        species = len({r["species_name"] for r in rows})
        self.count_label.setText(f"{len(rows):,} records  •  {species:,} species")
        if rows and not getattr(self, "_sized", False):
            self._sized = True
            self.table.resizeColumnsToContents()
            for col in range(len(COLUMNS)):
                if self.table.columnWidth(col) > 260:
                    self.table.setColumnWidth(col, 260)

    @staticmethod
    def _cell(key, value):
        if value is None:
            item = QStandardItem("")
            item.setData(-1 if key in NUMERIC_COLUMNS else "", SORT_ROLE)
        elif key in DATE_COLUMNS:
            item = QStandardItem(dmy(value))
            item.setData(str(value), SORT_ROLE)
        elif isinstance(value, (int, float)):
            item = QStandardItem(str(value))
            item.setData(value, SORT_ROLE)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            item = QStandardItem(str(value))
            item.setData(str(value).lower(), SORT_ROLE)
            item.setToolTip(str(value))
        item.setEditable(False)
        return item

    def _read(self, fn, **kwargs):
        """Run one repository function on a fresh read-only connection; None on failure."""
        db_path = get_database().main_db_path
        if not db_path or not db_path.exists():
            self.count_label.setText("No database connected")
            return None
        conn = open_ro(db_path)
        try:
            if not has_table(conn):
                self.count_label.setText("This database has no contributed records table")
                return None
            return fn(conn, **kwargs)
        except Exception as e:
            print(f"[Contributed] Could not read contributed records: {e}")
            self.count_label.setText("Could not read contributed records")
            return None
        finally:
            conn.close()
