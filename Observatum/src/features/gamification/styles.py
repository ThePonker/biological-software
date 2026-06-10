"""
Gamification Window Stylesheets.

Centralized stylesheet generation using theme tokens.
Supports both dark (Victorian) and light modes.
"""

from .theme import BACKGROUND, TEXT
from .theme_bridge import get_color


# =============================================================================
# DARK MODE STYLESHEET (Victorian Naturalist)
# =============================================================================

def get_dark_stylesheet() -> str:
    """Generate dark Victorian theme stylesheet."""
    # Colors from theme
    bg_primary = BACKGROUND['primary']
    bg_secondary = BACKGROUND['secondary']
    bg_surface = BACKGROUND['surface']
    bg_border = BACKGROUND['border']
    
    text_primary = TEXT['primary']
    text_secondary = TEXT['secondary']
    text_muted = TEXT['muted']
    text_accent = TEXT['accent']
    
    # Button colors from bridge
    btn_primary = get_color('button_primary_bg', dark_mode=True)
    btn_primary_hover = get_color('button_primary_hover', dark_mode=True)
    
    return f"""
QDialog {{
    background-color: {bg_primary};
}}

QWidget {{
    font-family: Georgia, serif;
    font-size: 13px;
    color: {text_primary};
}}

QFrame#card {{
    background-color: {bg_secondary};
    border: 1px solid {text_accent};
    border-radius: 8px;
    padding: 16px;
}}

QFrame#tierCard {{
    background-color: {bg_surface};
    border: 2px solid {text_accent};
    border-radius: 12px;
    padding: 20px;
}}

QLabel#title {{
    font-size: 24px;
    font-weight: bold;
    color: {text_accent};
}}

QLabel#subtitle {{
    font-size: 14px;
    color: {text_secondary};
}}

QLabel#tierName {{
    font-size: 20px;
    font-weight: bold;
    color: {text_accent};
}}

QLabel#tierNumber {{
    font-size: 48px;
    font-weight: bold;
    color: {text_accent};
}}

QLabel#statValue {{
    font-size: 28px;
    font-weight: bold;
    color: {text_accent};
}}

QLabel#statLabel {{
    font-size: 12px;
    color: {text_secondary};
}}

QLabel#sectionTitle {{
    font-size: 16px;
    font-weight: bold;
    color: {text_accent};
    padding: 8px 0;
}}

QPushButton {{
    background-color: {btn_primary};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {btn_primary_hover};
}}

QPushButton#secondary {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 1px solid {bg_border};
}}

QPushButton#secondary:hover {{
    background-color: {bg_surface};
}}

QProgressBar {{
    border: none;
    border-radius: 6px;
    background-color: {bg_border};
    height: 14px;
    text-align: center;
}}

QProgressBar::chunk {{
    border-radius: 6px;
}}

QTabWidget::pane {{
    border: 1px solid {bg_border};
    border-radius: 8px;
    background-color: {bg_secondary};
}}

QTabBar::tab {{
    background-color: {bg_primary};
    color: {text_muted};
    border: 1px solid {bg_border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 10px 20px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {bg_secondary};
    color: {text_accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: {bg_surface};
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: {bg_primary};
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {bg_border};
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {text_muted};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QLineEdit {{
    background-color: {bg_primary};
    border: 1px solid {bg_border};
    border-radius: 4px;
    padding: 8px;
    color: {text_primary};
}}

QCheckBox {{
    color: {text_primary};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 1px solid {bg_border};
    background-color: {bg_secondary};
}}

QCheckBox::indicator:checked {{
    background-color: {btn_primary};
    border-color: {btn_primary};
}}
"""


# =============================================================================
# LIGHT MODE STYLESHEET
# =============================================================================

def get_light_stylesheet() -> str:
    """Generate light theme stylesheet using theme bridge."""
    # Colors from bridge (light mode)
    bg_primary = get_color('background_primary', dark_mode=False)
    bg_secondary = get_color('background_secondary', dark_mode=False)
    bg_surface = get_color('background_surface', dark_mode=False)
    bg_border = get_color('border', dark_mode=False)
    
    text_primary = get_color('text_primary', dark_mode=False)
    text_secondary = get_color('text_secondary', dark_mode=False)
    text_muted = get_color('text_muted', dark_mode=False)
    text_accent = get_color('text_accent', dark_mode=False)
    
    btn_primary = get_color('button_primary_bg', dark_mode=False)
    btn_primary_hover = get_color('button_primary_hover', dark_mode=False)
    
    return f"""
QDialog {{
    background-color: {bg_primary};
}}

QWidget {{
    font-family: Georgia, serif;
    font-size: 13px;
    color: {text_primary};
}}

QFrame#card {{
    background-color: {bg_secondary};
    border: 1px solid {bg_border};
    border-radius: 8px;
    padding: 16px;
}}

QFrame#tierCard {{
    background-color: {bg_secondary};
    border: 2px solid {text_muted};
    border-radius: 12px;
    padding: 20px;
}}

QLabel#title {{
    font-size: 24px;
    font-weight: bold;
    color: {text_primary};
}}

QLabel#subtitle {{
    font-size: 14px;
    color: {text_secondary};
}}

QLabel#tierName {{
    font-size: 20px;
    font-weight: bold;
    color: {text_primary};
}}

QLabel#tierNumber {{
    font-size: 48px;
    font-weight: bold;
    color: {text_primary};
}}

QLabel#statValue {{
    font-size: 28px;
    font-weight: bold;
    color: {text_primary};
}}

QLabel#statLabel {{
    font-size: 12px;
    color: {text_secondary};
}}

QLabel#sectionTitle {{
    font-size: 16px;
    font-weight: bold;
    color: {text_primary};
    padding: 8px 0;
}}

QPushButton {{
    background-color: {btn_primary};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {btn_primary_hover};
}}

QPushButton#secondary {{
    background-color: #e0e0e0;
    color: {text_primary};
    border: 1px solid {bg_border};
}}

QPushButton#secondary:hover {{
    background-color: #d0d0d0;
}}

QProgressBar {{
    border: none;
    border-radius: 6px;
    background-color: #dddddd;
    height: 14px;
    text-align: center;
}}

QProgressBar::chunk {{
    border-radius: 6px;
}}

QTabWidget::pane {{
    border: 1px solid {bg_border};
    border-radius: 8px;
    background-color: {bg_secondary};
}}

QTabBar::tab {{
    background-color: #e8e8e8;
    color: {text_secondary};
    border: 1px solid {bg_border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 10px 20px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {bg_secondary};
    color: {text_primary};
}}

QTabBar::tab:hover:!selected {{
    background-color: #f0f0f0;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background-color: #f0f0f0;
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background-color: {bg_border};
    border-radius: 6px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #aaaaaa;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QLineEdit {{
    background-color: {bg_secondary};
    border: 1px solid {bg_border};
    border-radius: 4px;
    padding: 8px;
    color: {text_primary};
}}

QCheckBox {{
    color: {text_primary};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 1px solid {bg_border};
    background-color: {bg_secondary};
}}

QCheckBox::indicator:checked {{
    background-color: {btn_primary};
    border-color: {btn_primary};
}}
"""
