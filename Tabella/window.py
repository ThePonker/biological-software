"""
Field Entry App - Main Window.

Main application window with Quick Fill bar, table, and toolbar.
"""

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QStatusBar, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut

from .constants import COLORS
from .table import FieldEntryTable
from .find_dialog import FindDialog
from .find_replace_dialog import FindReplaceDialog
from .column_dialog import ColumnDialog
from .auto_save import AutoSave
from .uksi_lookup import UKSILookup
from .vc_lookup import VCLookup
from .settings import Settings
from .window_helpers import WindowFileOperationsMixin, WindowQuickFillMixin


class FieldEntryWindow(WindowFileOperationsMixin, WindowQuickFillMixin, QMainWindow):
    """
    Main window for Field Entry application.
    
    Provides:
    - Quick Fill bar for bulk applying values
    - Excel-like table for data entry
    - CSV import/export
    - Find & Replace
    - Column management
    - Auto-save recovery
    """
    
    def __init__(self, uksi: UKSILookup, vc_lookup: VCLookup, 
                 settings: Settings = None, data_dir: Path = None):
        super().__init__()
        
        self._uksi = uksi
        self._vc_lookup = vc_lookup
        self._settings = settings or Settings()
        self._data_dir = data_dir or Path('data')
        self._sticky: Dict[int, str] = {}
        self._sticky_widgets: Dict[int, QWidget] = {}
        self._find_dialog: Optional[FindDialog] = None
        self._find_replace_dialog: Optional[FindReplaceDialog] = None
        self._column_dialog: Optional[ColumnDialog] = None
        
        # Auto-save
        self._auto_save = AutoSave(
            self._data_dir, 
            self._settings.auto_save_interval,
            self
        )
        
        self.setWindowTitle("Observatum Field Entry")
        self.setMinimumSize(1400, 800)
        
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_auto_save()
        self._update_row_count(0, 0)
        
        # Check for recovery file and add startup rows
        QTimer.singleShot(100, self._on_startup)
    
    def _on_startup(self):
        """Handle startup - check recovery and add rows."""
        # Check for recovery
        recovery_info = self._auto_save.check_for_recovery()
        if recovery_info:
            reply = QMessageBox.question(
                self, "Recovery Available",
                f"{recovery_info}\n\nDo you want to restore this data?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                rows = self._auto_save.load_recovery()
                if rows:
                    self.table.set_rows(rows)
                    self._show_status("Data restored from recovery file")
                    return
        
        # No recovery or declined - add startup rows (at bottom)
        startup_rows = self._settings.startup_rows
        if startup_rows > 0:
            self.table.add_startup_rows(startup_rows)
            self._show_status(f"Ready - {startup_rows} rows")
    
    def _setup_auto_save(self):
        """Set up auto-save."""
        self._auto_save.set_data_callback(self.table.get_all_rows)
        self._auto_save.save_triggered.connect(
            lambda: self._show_status("Auto-saved", timeout=2000)
        )
        
        if self._settings.auto_save_enabled:
            self._auto_save.start()
        
        # Mark dirty on changes
        self.table.cellChanged.connect(lambda: self._auto_save.mark_dirty())
    
    def _setup_ui(self):
        """Set up the main UI."""
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background-color: {COLORS['bg']};")
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        self._setup_header(layout)
        self._setup_quick_fill_bar(layout)
        self._setup_table(layout)
        self._setup_buttons(layout)
        self._setup_status_bar()
    
    def _setup_header(self, layout: QVBoxLayout):
        """Set up header with title and info."""
        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)
        
        title = QLabel("Field Entry")
        title.setFont(QFont("", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']}; border: none;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        self.row_count_label = QLabel("No data")
        self.row_count_label.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        header_layout.addWidget(self.row_count_label)
        
        layout.addWidget(header)
    
    def _setup_table(self, layout: QVBoxLayout):
        """Set up the main data table."""
        self.table = FieldEntryTable(self._uksi, self._vc_lookup, self)
        self.table.row_count_changed.connect(self._update_row_count)
        self.table.status_message.connect(self._show_status)
        
        # Apply saved column settings
        self._apply_column_settings()
        
        layout.addWidget(self.table, 1)
    
    def _apply_column_settings(self):
        """Apply saved column order and visibility."""
        hidden = self._settings.hidden_columns
        for col in hidden:
            if 0 <= col < self.table.columnCount():
                self.table.setColumnHidden(col, True)
    
    def _setup_buttons(self, layout: QVBoxLayout):
        """Set up button bar."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        
        btn_layout = QHBoxLayout(frame)
        btn_layout.setContentsMargins(12, 6, 12, 6)
        btn_layout.setSpacing(8)
        
        # Left side - row management (add empty rows at top)
        add_rows_btn = QPushButton("+ Add 100")
        add_rows_btn.setStyleSheet(self._get_primary_btn_style())
        add_rows_btn.clicked.connect(lambda: self.table.add_rows(100))
        btn_layout.addWidget(add_rows_btn)
        
        add_10_btn = QPushButton("+ Add 10")
        add_10_btn.setStyleSheet(self._get_secondary_btn_style())
        add_10_btn.clicked.connect(lambda: self.table.add_rows(10))
        btn_layout.addWidget(add_10_btn)
        
        clear_btn = QPushButton("Clear All Data")
        clear_btn.setStyleSheet(self._get_danger_btn_style())
        clear_btn.clicked.connect(self._on_clear_all)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        
        # Center - file operations
        import_btn = QPushButton("📂 Import")
        import_btn.setStyleSheet(self._get_secondary_btn_style())
        import_btn.clicked.connect(self._import_csv)
        btn_layout.addWidget(import_btn)
        
        export_btn = QPushButton("💾 Export")
        export_btn.setStyleSheet(self._get_primary_btn_style())
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)
        
        btn_layout.addStretch()
        
        # Right side - tools
        columns_btn = QPushButton("⚙ Columns")
        columns_btn.setStyleSheet(self._get_secondary_btn_style())
        columns_btn.clicked.connect(self._show_column_dialog)
        btn_layout.addWidget(columns_btn)
        
        find_btn = QPushButton("🔍 Find")
        find_btn.setStyleSheet(self._get_secondary_btn_style())
        find_btn.clicked.connect(self._show_find_dialog)
        btn_layout.addWidget(find_btn)
        
        replace_btn = QPushButton("Replace")
        replace_btn.setStyleSheet(self._get_secondary_btn_style())
        replace_btn.clicked.connect(self._show_find_replace_dialog)
        btn_layout.addWidget(replace_btn)
        
        layout.addWidget(frame)
    
    def _get_primary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                padding: 6px 14px;
                border: none;
                border-radius: 4px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_hover']}; }}
        """
    
    def _get_secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                padding: 6px 14px;
                border: 1px solid {COLORS['border_strong']};
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {COLORS['surface_alt']}; }}
        """
    
    def _get_danger_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['error_text']};
                padding: 6px 14px;
                border: 1px solid {COLORS['error_text']};
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {COLORS['error_bg']}; }}
        """
    
    def _setup_status_bar(self):
        """Set up status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.setStyleSheet(f"""
            QStatusBar {{
                background-color: {COLORS['surface']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        QShortcut(QKeySequence.StandardKey.Find, self, self._show_find_dialog)
        QShortcut(QKeySequence("Ctrl+H"), self, self._show_find_replace_dialog)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._apply_sticky_to_selection)
        QShortcut(QKeySequence("Ctrl+Enter"), self, self._apply_sticky_to_selection)
        QShortcut(QKeySequence("Ctrl+O"), self, self._import_csv)
        QShortcut(QKeySequence("Ctrl+S"), self, self._on_export)
    
    def _update_row_count(self, total: int, data_rows: int):
        """Update row count display."""
        if total == 0:
            self.row_count_label.setText("No data")
        else:
            self.row_count_label.setText(f"{data_rows} of {total} rows with data")
    
    def _show_status(self, message: str, timeout: int = 5000):
        """Show status bar message."""
        self.status_bar.showMessage(message, timeout)
    
    def _on_clear_all(self):
        """Handle clear all with warning and auto-save cleanup."""
        # Count rows with data
        data_count = 0
        for row in range(self.table.rowCount()):
            species_item = self.table.item(row, 0)
            if species_item and species_item.text().strip():
                data_count += 1
        
        if data_count > 0:
            reply = QMessageBox.warning(
                self, "Clear All Data",
                f"This will clear ALL data in the current window.\n\n"
                f"You have {data_count} row(s) with data.\n\n"
                "This action cannot be undone. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.table.clear_all()
        self._auto_save.clear_recovery()
        self._show_status("All data cleared")
    
    def _on_export(self):
        """Handle export with auto-save cleanup."""
        self._export_csv()
        # Clear recovery after successful export
        self._auto_save.clear_recovery()
        self._auto_save.mark_clean()
    
    # =========================================================================
    # Find
    # =========================================================================
    
    def _show_find_dialog(self):
        """Show the find dialog."""
        if not self._find_dialog:
            self._find_dialog = FindDialog(self)
            self._find_dialog.find_next.connect(self._on_find_next)
            self._find_dialog.find_previous.connect(self._on_find_previous)
            self._find_dialog.find_all.connect(self._on_find_all)
        
        self._find_dialog.show()
        self._find_dialog.raise_()
        self._find_dialog.activateWindow()
    
    def _on_find_next(self, text: str, case_sensitive: bool, whole_word: bool):
        found = self.table.find_next(text, case_sensitive, whole_word)
        self._find_dialog.set_status("Found" if found else "Not found", is_error=not found)
    
    def _on_find_previous(self, text: str, case_sensitive: bool, whole_word: bool):
        found = self.table.find_previous(text, case_sensitive, whole_word)
        self._find_dialog.set_status("Found" if found else "Not found", is_error=not found)
    
    def _on_find_all(self, text: str, case_sensitive: bool, whole_word: bool):
        count = self.table.find_all(text, case_sensitive, whole_word)
        self._find_dialog.set_status(f"Found {count} match(es)")
    
    # =========================================================================
    # Find & Replace
    # =========================================================================
    
    def _show_find_replace_dialog(self):
        """Show the find & replace dialog."""
        if not self._find_replace_dialog:
            self._find_replace_dialog = FindReplaceDialog(self)
            self._find_replace_dialog.find_next.connect(self._on_replace_find_next)
            self._find_replace_dialog.find_previous.connect(self._on_replace_find_prev)
            self._find_replace_dialog.replace_one.connect(self._on_replace_one)
            self._find_replace_dialog.replace_all.connect(self._on_replace_all)
        
        self._find_replace_dialog.show()
        self._find_replace_dialog.raise_()
        self._find_replace_dialog.activateWindow()
    
    def _on_replace_find_next(self, find: str, replace: str, case: bool, whole: bool):
        found = self.table.find_next(find, case, whole)
        self._find_replace_dialog.set_status("Found" if found else "Not found", is_error=not found)
    
    def _on_replace_find_prev(self, find: str, replace: str, case: bool, whole: bool):
        found = self.table.find_previous(find, case, whole)
        self._find_replace_dialog.set_status("Found" if found else "Not found", is_error=not found)
    
    def _on_replace_one(self, find: str, replace: str, case: bool, whole: bool):
        replaced = self.table.replace_current(find, replace, case, whole)
        if replaced:
            # Move to next match
            found = self.table.find_next(find, case, whole)
            self._find_replace_dialog.set_status("Replaced" if found else "Replaced (no more)")
        else:
            self._find_replace_dialog.set_status("No match at cursor", is_error=True)
    
    def _on_replace_all(self, find: str, replace: str, case: bool, whole: bool):
        count = self.table.replace_all(find, replace, case, whole)
        self._find_replace_dialog.set_status(f"Replaced {count} occurrence(s)")
        self._auto_save.mark_dirty()
    
    # =========================================================================
    # Column Management
    # =========================================================================
    
    def _show_column_dialog(self):
        """Show column management dialog."""
        current_order = self._settings.column_order or list(range(self.table.columnCount()))
        hidden = self._settings.hidden_columns or []
        
        dialog = ColumnDialog(current_order, hidden, self)
        dialog.columns_changed.connect(self._on_columns_changed)
        dialog.exec()
    
    def _on_columns_changed(self, order: list, hidden: list):
        """Handle column visibility/order changes."""
        # Save settings
        self._settings.column_order = order
        self._settings.hidden_columns = hidden
        
        # Apply visibility
        for col in range(self.table.columnCount()):
            self.table.setColumnHidden(col, col in hidden)
        
        self._show_status("Column settings updated")
    
    # =========================================================================
    # Window Events
    # =========================================================================
    
    def showEvent(self, event):
        """Handle show event - maximize window."""
        super().showEvent(event)
        self.showMaximized()
    
    def closeEvent(self, event):
        """Handle close - save if dirty."""
        self._auto_save.save_now()
        self._auto_save.stop()
        event.accept()
