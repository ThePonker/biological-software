"""
Theme Manager - Centralized theming for Observatum V2.

Provides a singleton that manages the Naturalist theme and
provides access to theme colors and preset styles.

Usage:
    from src.themes import theme
    
    # Get a color value
    bg = theme().get('background')
    
    # Get a tab accent color
    obs_color = theme().get('accent_observations')
    
    # Use preset styles
    style = theme().button_primary_style()
"""

from typing import Dict, Optional
from PySide6.QtCore import QObject, Signal


class ThemeManager(QObject):
    """
    Singleton theme manager for the application.
    
    Provides access to the Naturalist theme colors and preset styles.
    """
    
    # Kept for compatibility (unused in single-theme mode)
    theme_changed = Signal()
    
    _instance: Optional['ThemeManager'] = None
    
    def __new__(cls) -> 'ThemeManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._load_theme()
    
    def _load_theme(self) -> None:
        """Load the Naturalist theme."""
        from .naturalist import NATURALIST_THEME
        self._theme: Dict = NATURALIST_THEME
        self._name: str = 'Naturalist'
    
    def get(self, key: str, fallback: str = '#ff00ff') -> str:
        """
        Get a theme value by key.
        
        Args:
            key: The theme token name (e.g., 'background', 'text_primary')
            fallback: Fallback color if key not found (magenta to highlight missing tokens)
        
        Returns:
            The color/value string
        """
        return self._theme.get(key, fallback)
    
    def font_size(self, size_key: str) -> str:
        """
        Get a font size formatted for stylesheets.
        
        Args:
            size_key: The size key (e.g., 'font_size_base', 'font_size_sm')
                      Can also use short forms: 'xs', 'sm', 'base', 'lg', 'xl', '2xl', '3xl', 'stat'
        
        Returns:
            Font size with 'pt' suffix (e.g., '11pt')
        """
        # Allow short form keys
        if not size_key.startswith('font_size_'):
            size_key = f'font_size_{size_key}'
        
        size = self._theme.get(size_key, 11)
        return f'{size}pt'
    
    @property
    def current_theme(self) -> str:
        """Get the current theme name."""
        return self._name
    
    @property
    def available_themes(self) -> list:
        """Get list of available theme names."""
        return ['Naturalist']
    
    # =========================================================================
    # Preset Styles - Common component styles
    # =========================================================================
    
    def card_style(self) -> str:
        """Get card/panel style."""
        return f"""
            background-color: {self.get('surface')};
            border: 1px solid {self.get('border')};
            border-radius: {self.get('radius_lg')};
        """
    
    def button_primary_style(self) -> str:
        """Get primary button style (Moss Green - Save/Add/Create)."""
        return f"""
            QPushButton {{
                background-color: {self.get('button_save')};
                color: {self.get('primary_text')};
                border: none;
                border-radius: {self.get('radius_md')};
                padding: 8px 16px;
                font-weight: bold;
                font-size: {self.font_size('base')};
            }}
            QPushButton:hover {{
                background-color: {self.get('primary_hover')};
            }}
            QPushButton:pressed {{
                background-color: {self.get('primary_pressed')};
            }}
            QPushButton:disabled {{
                background-color: {self.get('disabled_bg')};
                color: {self.get('disabled_text')};
            }}
        """
    
    def button_secondary_style(self) -> str:
        """Get secondary button style (outlined)."""
        return f"""
            QPushButton {{
                background-color: {self.get('surface')};
                color: {self.get('text_primary')};
                border: 1px solid {self.get('border')};
                border-radius: {self.get('radius_md')};
                padding: 6px 12px;
                font-size: {self.font_size('base')};
            }}
            QPushButton:hover {{
                background-color: {self.get('hover')};
            }}
            QPushButton:pressed {{
                background-color: {self.get('pressed')};
            }}
        """
    
    def button_cancel_style(self) -> str:
        """Get cancel button style (Warm Gray outlined)."""
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {self.get('button_cancel')};
                border: 1px solid {self.get('button_cancel')};
                border-radius: {self.get('radius_md')};
                padding: 6px 12px;
                font-size: {self.font_size('base')};
            }}
            QPushButton:hover {{
                background-color: {self.get('hover')};
            }}
            QPushButton:pressed {{
                background-color: {self.get('pressed')};
            }}
        """
    
    def button_delete_style(self) -> str:
        """Get delete button style (Faded Crimson outlined)."""
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {self.get('button_delete')};
                border: 1px solid {self.get('button_delete')};
                border-radius: {self.get('radius_md')};
                padding: 6px 12px;
                font-size: {self.font_size('base')};
            }}
            QPushButton:hover {{
                background-color: {self.get('error_bg')};
            }}
            QPushButton:pressed {{
                background-color: {self.get('error')};
                color: white;
            }}
        """
    
    def button_tab_style(self, tab_name: str) -> str:
        """Get button style using tab accent color."""
        accent = self.get(f'accent_{tab_name}', self.get('primary'))
        return f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                border: none;
                border-radius: {self.get('radius_md')};
                padding: 6px 12px;
                font-size: {self.font_size('base')};
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """
    
    def input_style(self) -> str:
        """Get input field style (QLineEdit, QComboBox, etc.)."""
        return f"""
            QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit {{
                background-color: {self.get('input_bg')};
                border: 1px solid {self.get('border')};
                border-radius: {self.get('radius_sm')};
                padding: 4px 8px;
                color: {self.get('text_primary')};
                font-size: {self.font_size('base')};
            }}
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QTextEdit:focus {{
                border: 2px solid {self.get('focus_border')};
                background-color: {self.get('surface')};
                padding: 3px 7px;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {self.get('text_secondary')};
                margin-right: 8px;
            }}
        """
    
    def table_style(self) -> str:
        """Get table style."""
        return f"""
            QTableWidget, QTableView {{
                background-color: {self.get('surface')};
                border: 1px solid {self.get('border')};
                border-radius: {self.get('radius_md')};
                gridline-color: {self.get('border')};
            }}
            QTableWidget::item, QTableView::item {{
                padding: 8px;
                border-bottom: 1px solid {self.get('border')};
            }}
            QTableWidget::item:selected, QTableView::item:selected {{
                background-color: {self.get('selected_bg')};
                color: {self.get('text_primary')};
            }}
            QHeaderView::section {{
                background-color: {self.get('surface_alt')};
                color: {self.get('text_secondary')};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {self.get('border')};
                font-weight: 600;
                font-size: {self.font_size('sm')};
            }}
        """
    
    def scrollbar_style(self) -> str:
        """Get scrollbar style."""
        return f"""
            QScrollBar:vertical {{
                background-color: {self.get('background')};
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background-color: {self.get('scrollbar')};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {self.get('scrollbar_hover')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background-color: {self.get('background')};
                height: 10px;
                margin: 0;
            }}
            QScrollBar::handle:horizontal {{
                background-color: {self.get('scrollbar')};
                border-radius: 5px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background-color: {self.get('scrollbar_hover')};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
        """
    
    def sidebar_button_style(self) -> str:
        """Get sidebar navigation button style."""
        return f"""
            QPushButton {{
                text-align: left;
                padding: 10px 12px;
                border: none;
                border-radius: {self.get('radius_md')};
                background: transparent;
                color: {self.get('text_secondary')};
                font-size: {self.font_size('base')};
            }}
            QPushButton:hover {{
                background-color: {self.get('hover')};
            }}
            QPushButton:checked {{
                background-color: {self.get('success_bg')};
                color: {self.get('success')};
                font-weight: 600;
            }}
        """
    
    def tab_button_style(self, accent_color: str = None) -> str:
        """Get tab/view selector button style."""
        accent = accent_color or self.get('primary')
        accent_bg = self.get('primary_bg')
        accent_text = self.get('primary_dark')
        
        return f"""
            QPushButton {{
                padding: 6px 12px;
                border: none;
                border-radius: {self.get('radius_sm')};
                background: transparent;
                color: {self.get('text_secondary')};
                font-size: {self.font_size('sm')};
            }}
            QPushButton:hover {{
                background-color: {self.get('hover')};
            }}
            QPushButton:checked {{
                background-color: {accent_bg};
                color: {accent_text};
                font-weight: 600;
            }}
        """
    
    def group_box_style(self) -> str:
        """Get QGroupBox style."""
        return f"""
            QGroupBox {{
                font-weight: 600;
                color: {self.get('text_primary')};
                border: 1px solid {self.get('border')};
                border-radius: {self.get('radius_md')};
                margin-top: 12px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: {self.get('background')};
            }}
        """
    
    def checkbox_style(self) -> str:
        """Get checkbox style."""
        return f"""
            QCheckBox {{
                color: {self.get('text_primary')};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {self.get('border_strong')};
                border-radius: 3px;
                background-color: {self.get('surface')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.get('success')};
                border-color: {self.get('success')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {self.get('success')};
            }}
        """
    
    def badge_style(self, variant: str = 'default') -> str:
        """
        Get badge/tag style.
        
        Args:
            variant: 'default', 'success', 'warning', 'error', 'info', 'personal', 'commercial'
        """
        variants = {
            'default': (self.get('surface_alt'), self.get('text_secondary')),
            'success': (self.get('success_bg'), self.get('success_text')),
            'warning': (self.get('warning_bg'), self.get('warning_text')),
            'error': (self.get('error_bg'), self.get('error_text')),
            'info': (self.get('info_bg'), self.get('info_text')),
            'personal': (self.get('success_bg'), self.get('success_text')),
            'commercial': (self.get('purple_bg'), self.get('purple_text')),
        }
        bg, text = variants.get(variant, variants['default'])
        
        return f"""
            background-color: {bg};
            color: {text};
            padding: 2px 8px;
            border-radius: {self.get('radius_sm')};
            font-size: {self.font_size('sm')};
            font-weight: 600;
        """
    
    def status_bar_style(self) -> str:
        """Get status bar style."""
        return f"""
            QStatusBar {{
                background-color: {self.get('surface')};
                border-top: 1px solid {self.get('border')};
                color: {self.get('text_secondary')};
                font-size: {self.font_size('sm')};
            }}
        """
    
    def tooltip_style(self) -> str:
        """Get tooltip style."""
        return f"""
            QToolTip {{
                background-color: {self.get('tooltip_bg')};
                color: {self.get('tooltip_text')};
                border: 1px solid {self.get('tooltip_border')};
                border-radius: {self.get('radius_sm')};
                padding: 4px 8px;
                font-size: {self.font_size('sm')};
            }}
        """


# Module-level singleton accessor
_manager: Optional[ThemeManager] = None

def theme() -> ThemeManager:
    """
    Get the theme manager singleton.
    
    Returns:
        ThemeManager instance
    """
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager
