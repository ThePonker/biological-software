"""
Quantity Spinner Widget.

A styled quantity input with [−] and [+] buttons that matches the form theme.
Replaces QSpinBox to avoid Qt stylesheet conflicts with arrow rendering.
"""

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLineEdit
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIntValidator

from ...themes import theme


class QuantitySpinner(QWidget):
    """Custom quantity spinner with themed +/- buttons."""
    
    valueChanged = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._minimum = 1
        self._maximum = 9999
        self._value = 1
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the widget UI."""
        t = theme()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Decrement button
        self.dec_btn = QPushButton("−")  # Using minus sign (not hyphen)
        self.dec_btn.setFixedSize(32, 32)
        self.dec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dec_btn.clicked.connect(self._decrement)
        layout.addWidget(self.dec_btn)
        
        # Value input
        self.input = QLineEdit()
        self.input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input.setValidator(QIntValidator(self._minimum, self._maximum))
        self.input.setText(str(self._value))
        self.input.setMinimumHeight(32)
        self.input.editingFinished.connect(self._on_editing_finished)
        layout.addWidget(self.input, 1)
        
        # Increment button
        self.inc_btn = QPushButton("+")
        self.inc_btn.setFixedSize(32, 32)
        self.inc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.inc_btn.clicked.connect(self._increment)
        layout.addWidget(self.inc_btn)
        
        self._apply_style()
    
    def _apply_style(self):
        """Apply theme styling to all components."""
        t = theme()
        
        # Button style - matches form aesthetic
        btn_style = f"""
            QPushButton {{
                background-color: {t.get('surface_alt')};
                border: 1px solid {t.get('border')};
                color: {t.get('text_primary')};
                font-size: 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {t.get('hover')};
                border-color: {t.get('border_strong')};
            }}
            QPushButton:pressed {{
                background-color: {t.get('pressed')};
            }}
        """
        
        # Decrement button - rounded left corners
        self.dec_btn.setStyleSheet(btn_style + f"""
            QPushButton {{
                border-top-left-radius: {t.get('radius_sm')};
                border-bottom-left-radius: {t.get('radius_sm')};
                border-right: none;
            }}
        """)
        
        # Increment button - rounded right corners
        self.inc_btn.setStyleSheet(btn_style + f"""
            QPushButton {{
                border-top-right-radius: {t.get('radius_sm')};
                border-bottom-right-radius: {t.get('radius_sm')};
                border-left: none;
            }}
        """)
        
        # Input field - no rounded corners (sandwiched between buttons)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {t.get('surface')};
                border: 1px solid {t.get('border')};
                border-left: none;
                border-right: none;
                border-radius: 0;
                padding: 6px 8px;
                color: {t.get('text_primary')};
                font-size: {t.font_size('base')};
            }}
            QLineEdit:focus {{
                border-color: {t.get('focus_border')};
                border-top: 2px solid {t.get('focus_border')};
                border-bottom: 2px solid {t.get('focus_border')};
            }}
        """)
    
    def _increment(self):
        """Increment the value."""
        if self._value < self._maximum:
            self.setValue(self._value + 1)
    
    def _decrement(self):
        """Decrement the value."""
        if self._value > self._minimum:
            self.setValue(self._value - 1)
    
    def _on_editing_finished(self):
        """Handle manual input editing."""
        try:
            val = int(self.input.text())
            val = max(self._minimum, min(self._maximum, val))
            self.setValue(val)
        except ValueError:
            self.input.setText(str(self._value))
    
    # Public API (matches QSpinBox interface)
    
    def value(self) -> int:
        """Get the current value."""
        return self._value
    
    def setValue(self, value: int):
        """Set the current value."""
        value = max(self._minimum, min(self._maximum, value))
        if value != self._value:
            self._value = value
            self.input.setText(str(value))
            self.valueChanged.emit(value)
        elif self.input.text() != str(value):
            self.input.setText(str(value))
    
    def minimum(self) -> int:
        """Get the minimum value."""
        return self._minimum
    
    def setMinimum(self, minimum: int):
        """Set the minimum value."""
        self._minimum = minimum
        self.input.setValidator(QIntValidator(self._minimum, self._maximum))
        if self._value < minimum:
            self.setValue(minimum)
    
    def maximum(self) -> int:
        """Get the maximum value."""
        return self._maximum
    
    def setMaximum(self, maximum: int):
        """Set the maximum value."""
        self._maximum = maximum
        self.input.setValidator(QIntValidator(self._minimum, self._maximum))
        if self._value > maximum:
            self.setValue(maximum)
    
    def setRange(self, minimum: int, maximum: int):
        """Set the value range."""
        self._minimum = minimum
        self._maximum = maximum
        self.input.setValidator(QIntValidator(minimum, maximum))
        self.setValue(max(minimum, min(maximum, self._value)))
    
    def apply_theme(self):
        """Apply the current theme."""
        self._apply_style()
