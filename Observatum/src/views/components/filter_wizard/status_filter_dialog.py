"""
Status Filter Dialog.

Filter by verification status and record type with checkboxes.
"""

from typing import Dict, Any, Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QCheckBox, QWidget
)
from PySide6.QtCore import Qt

from ....themes import theme
from ....core.config import ButtonColors


# Verification statuses from iRecord data
VERIFICATION_STATUSES = [
    'Accepted',
    'Unconfirmed',
    'Rejected',
]

# Record types
RECORD_TYPES = [
    'Personal',
    'Commercial',
]


class StatusFilterDialog(QDialog):
    """
    Dialog for filtering by verification status and record type.
    
    Simple checkbox interface (not chips since there's a small fixed set).
    """
    
    def __init__(
        self,
        accent_color: str = None,
        current_values: Dict[str, Any] = None,
        status_list: List[str] = None,
        type_list: List[str] = None,
        parent=None
    ):
        super().__init__(parent)
        self._accent_color = accent_color or "#5f8575"
        self._current = current_values or {}
        
        self._status_list = status_list or VERIFICATION_STATUSES
        self._type_list = type_list or RECORD_TYPES
        
        self.setWindowTitle("Filter by Status")
        self.setMinimumWidth(450)
        self.setMinimumHeight(380)
        self.setModal(True)
        
        self._setup_ui()
        self._load_current_values()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        t = theme()
        
        self.setStyleSheet(f"background-color: {t.get('background')};")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel("✓ Status to Include")
        header.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 600;
                color: {self._accent_color};
                background: transparent;
            }}
        """)
        layout.addWidget(header)
        
        desc = QLabel("Filter by verification status and record type")
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {t.get('text_secondary')}; font-size: 12px; background: transparent;")
        layout.addWidget(desc)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {t.get('border')};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        
        # === VERIFICATION STATUS SECTION ===
        status_section = self._create_status_section()
        layout.addWidget(status_section)
        
        # === RECORD TYPE SECTION ===
        type_section = self._create_type_section()
        layout.addWidget(type_section)
        
        layout.addStretch()
        
        # === BUTTON ROW ===
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {t.get('text_secondary')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
            }}
        """)
        button_layout.addWidget(cancel_btn)
        
        # Apply button
        apply_btn = QPushButton("Apply Filters")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.clicked.connect(self.accept)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ButtonColors.PRIMARY};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(ButtonColors.PRIMARY)};
            }}
        """)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
    
    def _create_status_section(self) -> QWidget:
        """Create verification status section."""
        t = theme()
        
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Label
        label = QLabel("Verification Status")
        label.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        layout.addWidget(label)
        
        # Checkboxes in frame
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
            }}
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(16, 12, 16, 12)
        frame_layout.setSpacing(8)
        
        self._status_checkboxes: Dict[str, QCheckBox] = {}
        
        for status in self._status_list:
            cb = QCheckBox(status)
            self._style_checkbox(cb)
            self._status_checkboxes[status] = cb
            frame_layout.addWidget(cb)
        
        layout.addWidget(frame)
        
        return section
    
    def _create_type_section(self) -> QWidget:
        """Create record type section."""
        t = theme()
        
        section = QWidget()
        section.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Label
        label = QLabel("Record Type")
        label.setStyleSheet(f"font-weight: 600; color: {t.get('text_primary')}; font-size: 13px; background: transparent;")
        layout.addWidget(label)
        
        # Checkboxes in frame
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-radius: 4px;
            }}
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(16, 12, 16, 12)
        frame_layout.setSpacing(8)
        
        self._type_checkboxes: Dict[str, QCheckBox] = {}
        
        for rec_type in self._type_list:
            cb = QCheckBox(rec_type)
            self._style_checkbox(cb)
            self._type_checkboxes[rec_type] = cb
            frame_layout.addWidget(cb)
        
        layout.addWidget(frame)
        
        return section
    
    def _clear_all(self):
        """Clear all selections."""
        for cb in self._status_checkboxes.values():
            cb.setChecked(False)
        for cb in self._type_checkboxes.values():
            cb.setChecked(False)
    
    def _load_current_values(self):
        """Load existing filter values."""
        if not self._current:
            return
        
        # Verification status
        for status in self._current.get('verification_status', []):
            if status in self._status_checkboxes:
                self._status_checkboxes[status].setChecked(True)
        
        # Record type
        for rec_type in self._current.get('record_type', []):
            if rec_type in self._type_checkboxes:
                self._type_checkboxes[rec_type].setChecked(True)
    
    def get_values(self) -> Dict[str, Any]:
        """Get the filter values."""
        result = {}
        
        # Get selected verification statuses
        statuses = []
        for status, cb in self._status_checkboxes.items():
            if cb.isChecked():
                statuses.append(status)
        if statuses:
            result['verification_status'] = statuses
        
        # Get selected record types
        types = []
        for rec_type, cb in self._type_checkboxes.items():
            if cb.isChecked():
                types.append(rec_type)
        if types:
            result['record_type'] = types
        
        return result
    
    def _style_checkbox(self, cb: QCheckBox):
        """Style checkboxes to match Home tab."""
        t = theme()
        cb.setStyleSheet(f"""
            QCheckBox {{
                color: {t.get('text_primary')};
                font-size: 13px;
                spacing: 10px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid {t.get('border')};
                background-color: {t.get('surface')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {self._accent_color};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self._accent_color};
                border-color: {self._accent_color};
            }}
        """)
    
    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Darken a hex color."""
        hex_color = hex_color.lstrip('#')
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

