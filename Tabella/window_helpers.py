"""
Field Entry App - Window Helper Methods.

Extracted file operations and sticky bar setup for FieldEntryWindow.
"""

from pathlib import Path
from typing import Dict, TYPE_CHECKING
from datetime import datetime

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QLineEdit, 
    QComboBox, QPushButton, QFileDialog, QMessageBox, QWidget
)
from PySide6.QtCore import Qt

from .constants import (
    COLORS, COL_DATE, COL_GRID_REF, COL_LOCATION, COL_QTY,
    COL_SEX, COL_STAGE, COL_METHOD, COL_COMMENT,
    COL_CERTAINTY, COL_RECORDER, COL_DETERMINER, 
    COL_DATA_TYPE, COL_NEVER_UPLOAD,
    SEX_OPTIONS, STAGE_OPTIONS, METHOD_OPTIONS, 
    CERTAINTY_OPTIONS, DATA_TYPE_OPTIONS, NEVER_UPLOAD_OPTIONS
)
from .csv_handler import CSVHandler

if TYPE_CHECKING:
    from .settings import Settings


class WindowFileOperationsMixin:
    """Mixin providing file operations for FieldEntryWindow."""
    
    def _import_csv(self):
        """Import data from CSV file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Import CSV", "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filepath:
            return
        
        try:
            headers, mapping = CSVHandler.detect_columns(filepath)
            
            if not mapping:
                QMessageBox.warning(
                    self, "Import Error",
                    "Could not auto-detect column mapping.\n\n"
                    "Please ensure your CSV has headers like 'Taxon', 'Date', 'Grid ref', etc."
                )
                return
            
            _, preview_rows, total_rows = CSVHandler.preview_file(filepath)
            
            reply = QMessageBox.question(
                self, "Import CSV",
                f"Found {total_rows} rows in file.\n"
                f"Detected columns: {', '.join(mapping.keys())}\n\n"
                "Do you want to import this file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            rows = CSVHandler.import_file(filepath, mapping)
            
            if rows:
                if self.table.rowCount() > 0:
                    reply = QMessageBox.question(
                        self, "Import Mode",
                        "Table already has data.\n\n"
                        "Yes = Append to existing data\n"
                        "No = Replace existing data",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                    )
                    
                    if reply == QMessageBox.StandardButton.Cancel:
                        return
                    elif reply == QMessageBox.StandardButton.No:
                        self.table.setRowCount(0)
                
                for row_data in rows:
                    row = self.table.rowCount()
                    self.table.add_rows(1, with_defaults=False)
                    
                    self.table.blockSignals(True)
                    for col, value in enumerate(row_data):
                        if col < self.table.columnCount():
                            item = self.table.item(row, col)
                            if item:
                                item.setText(value)
                    self.table.blockSignals(False)
                    
                    species_item = self.table.item(row, 0)
                    if species_item and species_item.text():
                        self.table._lookup_species(row, species_item.text())
                    
                    gr_item = self.table.item(row, 6)
                    if gr_item and gr_item.text():
                        self.table._validate_and_lookup_vc(row, gr_item.text())
                
                self.table._emit_row_count()
                self._show_status(f"Imported {len(rows)} rows from {Path(filepath).name}")
            else:
                QMessageBox.warning(self, "Import", "No data found in file.")
                
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Error importing file:\n{e}")
    
    def _export_csv(self):
        """Export data to CSV file."""
        rows = self.table.get_all_rows()
        data_rows = [r for r in rows if r[0].strip()]
        
        if not data_rows:
            QMessageBox.warning(self, "Export", "No data to export.")
            return
        
        filename = CSVHandler.generate_filename()
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", filename, "CSV Files (*.csv)"
        )
        
        if not filepath:
            return
        
        try:
            exported = CSVHandler.export_file(filepath, rows)
            
            if exported > 0:
                self._show_status(f"Exported {exported} records to {Path(filepath).name}")
                QMessageBox.information(
                    self, "Export Complete",
                    f"Successfully exported {exported} records.\n\n"
                    f"File: {filepath}"
                )
            else:
                QMessageBox.warning(self, "Export", "No data was exported.")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting file:\n{e}")


class WindowQuickFillMixin:
    """Mixin providing Quick Fill bar setup for FieldEntryWindow."""
    
    def _setup_quick_fill_bar(self, layout):
        """Set up the Quick Fill bar (formerly Sticky Defaults) - compact two-row layout."""
        
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
            QLabel {{
                font-size: 10px;
                color: {COLORS['text_secondary']};
                border: none;
                background: transparent;
            }}
            QLineEdit, QComboBox {{
                font-size: 11px;
                padding: 3px 6px;
                border: 1px solid {COLORS['border']};
                border-radius: 3px;
                background: white;
                min-height: 22px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {COLORS['accent']};
            }}
        """)
        
        main_layout = QVBoxLayout(frame)
        main_layout.setContentsMargins(10, 6, 10, 6)
        main_layout.setSpacing(4)
        
        # Header row with title and buttons
        header = QHBoxLayout()
        header.setSpacing(8)
        
        title = QLabel("⚡ Quick Fill")
        title.setStyleSheet(f"font-weight: bold; color: {COLORS['accent']}; font-size: 11px;")
        header.addWidget(title)
        
        header.addStretch()
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_secondary']};
                padding: 4px 8px;
                border: 1px solid {COLORS['border']};
                border-radius: 3px;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_alt']};
                border-color: {COLORS['border_strong']};
            }}
        """)
        clear_btn.clicked.connect(self._clear_quick_fill)
        header.addWidget(clear_btn)
        
        # Apply button
        apply_btn = QPushButton("Apply to Selection")
        apply_btn.setToolTip("Apply values to selected empty cells (Ctrl+Enter)")
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: white;
                padding: 4px 12px;
                border: none;
                border-radius: 3px;
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent_hover']};
            }}
        """)
        apply_btn.clicked.connect(self._apply_sticky_to_selection)
        header.addWidget(apply_btn)
        
        main_layout.addLayout(header)
        
        # Fields in a compact grid - all on one row where possible
        fields_layout = QHBoxLayout()
        fields_layout.setSpacing(12)
        
        # Get defaults from settings
        default_recorder = self._settings.default_recorder if self._settings else ''
        default_determiner = self._settings.default_determiner if self._settings else ''
        default_certainty = self._settings.default_certainty if self._settings else 'Certain'
        default_data_type = self._settings.default_data_type if self._settings else 'Personal'
        
        # Define all fields: (col_idx, label, type, options/default, width)
        # type: 'text' or 'combo'
        fields = [
            (COL_DATE, 'Date', 'text', datetime.now().strftime('%Y-%m-%d'), 85),
            (COL_LOCATION, 'Location', 'text', '', 120),
            (COL_GRID_REF, 'Grid Ref', 'text', '', 80),
            (COL_RECORDER, 'Recorder', 'text', default_recorder, 100),
            (COL_DETERMINER, 'Determiner', 'text', default_determiner, 100),
            (COL_QTY, 'Qty', 'text', '1', 40),
            (COL_SEX, 'Sex', 'combo', SEX_OPTIONS, 70),
            (COL_STAGE, 'Stage', 'combo', STAGE_OPTIONS, 75),
            (COL_METHOD, 'Method', 'combo', METHOD_OPTIONS, 110),
            (COL_CERTAINTY, 'Certainty', 'combo', CERTAINTY_OPTIONS, 75),
            (COL_DATA_TYPE, 'Data Type', 'combo', DATA_TYPE_OPTIONS, 80),
            (COL_NEVER_UPLOAD, 'Exclude', 'combo', NEVER_UPLOAD_OPTIONS, 90),
        ]
        
        for col_idx, label, field_type, options_or_default, width in fields:
            field_container = QVBoxLayout()
            field_container.setSpacing(1)
            
            lbl = QLabel(label)
            lbl.setStyleSheet("font-size: 9px;")
            field_container.addWidget(lbl)
            
            if field_type == 'text':
                widget = QLineEdit(str(options_or_default))
                widget.setFixedWidth(width)
                widget.textChanged.connect(lambda t, c=col_idx: self._on_sticky_changed(c, t))
                self._sticky[col_idx] = str(options_or_default)
            else:  # combo
                widget = QComboBox()
                widget.addItems(options_or_default)
                widget.setFixedWidth(width)
                
                # Set default for Certainty and Data Type
                if col_idx == COL_CERTAINTY:
                    idx = widget.findText(default_certainty)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    self._sticky[col_idx] = default_certainty
                elif col_idx == COL_DATA_TYPE:
                    idx = widget.findText(default_data_type)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    self._sticky[col_idx] = default_data_type
                else:
                    self._sticky[col_idx] = ''
                
                widget.currentTextChanged.connect(lambda t, c=col_idx: self._on_sticky_changed(c, t))
            
            self._sticky_widgets[col_idx] = widget
            field_container.addWidget(widget)
            fields_layout.addLayout(field_container)
        
        fields_layout.addStretch()
        main_layout.addLayout(fields_layout)
        
        layout.addWidget(frame)
    
    def _clear_quick_fill(self):
        """Clear all Quick Fill fields to empty/default values."""
        for col_idx, widget in self._sticky_widgets.items():
            if isinstance(widget, QLineEdit):
                # Keep date as today, clear others
                if col_idx == COL_DATE:
                    widget.setText(datetime.now().strftime('%Y-%m-%d'))
                    self._sticky[col_idx] = widget.text()
                elif col_idx == COL_QTY:
                    widget.setText('1')
                    self._sticky[col_idx] = '1'
                else:
                    widget.setText('')
                    self._sticky[col_idx] = ''
            elif isinstance(widget, QComboBox):
                # Reset combos to first item (usually blank) except Certainty
                if col_idx == COL_CERTAINTY:
                    widget.setCurrentIndex(0)  # 'Certain' is first
                    self._sticky[col_idx] = widget.currentText()
                elif col_idx == COL_DATA_TYPE:
                    widget.setCurrentIndex(0)  # 'Personal' is first
                    self._sticky[col_idx] = widget.currentText()
                else:
                    widget.setCurrentIndex(0)
                    self._sticky[col_idx] = ''
        
        self._show_status("Quick Fill values cleared")
    
    def _on_sticky_changed(self, col: int, value: str):
        """Handle sticky value change."""
        self._sticky[col] = value
    
    def _apply_sticky_to_selection(self):
        """Apply sticky defaults to selected cells."""
        self.table.apply_sticky_defaults(self._sticky)


# Keep old name as alias for compatibility
WindowStickyBarMixin = WindowQuickFillMixin

