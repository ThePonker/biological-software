"""
Status Bar Component.

Status bar for showing success/error messages in forms.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel
from PySide6.QtCore import QTimer

from ...themes import theme


class StatusBar(QFrame):
    """Status bar widget for showing form feedback."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._timer = QTimer()
        self._timer.timeout.connect(self._hide)
        self._timer.setSingleShot(True)
    
    def _setup_ui(self):
        t = theme()
        
        self.setVisible(False)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        self._icon_label = QLabel()
        layout.addWidget(self._icon_label)
        
        self._message_label = QLabel()
        self._message_label.setStyleSheet(f"font-size: {t.font_size('sm')};")
        layout.addWidget(self._message_label)
        
        layout.addStretch()
    
    def show_success(self, message: str, timeout: int = 5000):
        """Show a success message."""
        t = theme()
        
        self.setStyleSheet(f"""
            background-color: {t.get('success_bg')};
            border-radius: {t.get('radius_sm')};
        """)
        self._icon_label.setText("✓")
        self._icon_label.setStyleSheet(f"color: {t.get('success_text')}; font-weight: bold;")
        self._message_label.setText(message)
        self._message_label.setStyleSheet(f"color: {t.get('success_text')}; font-size: {t.font_size('sm')};")
        
        self.setVisible(True)
        
        if timeout > 0:
            self._timer.start(timeout)
    
    def show_error(self, message: str, timeout: int = 5000):
        """Show an error message."""
        t = theme()
        
        self.setStyleSheet(f"""
            background-color: {t.get('error_bg')};
            border-radius: {t.get('radius_sm')};
        """)
        self._icon_label.setText("✕")
        self._icon_label.setStyleSheet(f"color: {t.get('error_text')}; font-weight: bold;")
        self._message_label.setText(message)
        self._message_label.setStyleSheet(f"color: {t.get('error_text')}; font-size: {t.font_size('sm')};")
        
        self.setVisible(True)
        
        if timeout > 0:
            self._timer.start(timeout)
    
    def show_warning(self, message: str, timeout: int = 5000):
        """Show a warning message."""
        t = theme()
        
        self.setStyleSheet(f"""
            background-color: {t.get('warning_bg')};
            border-radius: {t.get('radius_sm')};
        """)
        self._icon_label.setText("⚠")
        self._icon_label.setStyleSheet(f"color: {t.get('warning_text')}; font-weight: bold;")
        self._message_label.setText(message)
        self._message_label.setStyleSheet(f"color: {t.get('warning_text')}; font-size: {t.font_size('sm')};")
        
        self.setVisible(True)
        
        if timeout > 0:
            self._timer.start(timeout)
    
    def show_info(self, message: str, timeout: int = 5000):
        """Show an info message."""
        t = theme()
        
        self.setStyleSheet(f"""
            background-color: {t.get('info_bg')};
            border-radius: {t.get('radius_sm')};
        """)
        self._icon_label.setText("ℹ")
        self._icon_label.setStyleSheet(f"color: {t.get('info_text')}; font-weight: bold;")
        self._message_label.setText(message)
        self._message_label.setStyleSheet(f"color: {t.get('info_text')}; font-size: {t.font_size('sm')};")
        
        self.setVisible(True)
        
        if timeout > 0:
            self._timer.start(timeout)
    
    def _hide(self):
        """Hide the status bar."""
        self.setVisible(False)
    
    def clear(self):
        """Clear and hide the status bar."""
        self._timer.stop()
        self.setVisible(False)
