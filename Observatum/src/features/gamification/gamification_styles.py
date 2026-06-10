"""
Gamification Styles for Observatum V2.

Theme-aware styling functions for the gamification window.
Uses the Observatum theme system for consistent appearance.
"""

try:
    from src.themes import theme
except ImportError:
    try:
        from themes import theme
    except ImportError:
        # Fallback if theme not available
        def theme():
            return {
                'surface': '#ffffff',
                'surface_alt': '#f9fafb',
                'border': '#d1d5db',
                'text_primary': '#1f2937',
                'text_secondary': '#6b7280',
                'success': '#059669',
                'success_bg': '#e8f0ec',
                'warning': '#d97706',
                'error': '#dc2626',
            }


def get_gamification_stylesheet() -> str:
    """
    Generate theme-aware stylesheet for gamification window.
    
    Returns:
        Complete stylesheet string using current theme colors.
    """
    t = theme()
    
    # Use theme colors with gamification-specific accents
    primary = t.get('success', '#5f8575')  # Sage green for achievements
    primary_light = t.get('success_bg', '#e8f0ec')
    primary_dark = '#4a6b5c'
    accent = t.get('warning', '#b8860b')  # Gold for special achievements
    
    return f"""
QDialog {{
    background-color: {t.get('surface')};
}}

QWidget {{
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: {t.get('text_primary')};
}}

QFrame#card {{
    background-color: {t.get('surface')};
    border: 1px solid {t.get('border')};
    border-radius: 8px;
    padding: 16px;
}}

QFrame#tierCard {{
    background-color: {primary_light};
    border: 2px solid {primary};
    border-radius: 12px;
    padding: 20px;
}}

QLabel#title {{
    font-size: 24px;
    font-weight: bold;
    color: {primary_dark};
}}

QLabel#subtitle {{
    font-size: 14px;
    color: {t.get('text_secondary')};
}}

QLabel#tierName {{
    font-size: 20px;
    font-weight: bold;
    color: {primary_dark};
}}

QLabel#tierNumber {{
    font-size: 48px;
    font-weight: bold;
    color: {primary};
}}

QLabel#statValue {{
    font-size: 28px;
    font-weight: bold;
    color: {primary};
}}

QLabel#statLabel {{
    font-size: 12px;
    color: {t.get('text_secondary')};
}}

QLabel#sectionTitle {{
    font-size: 16px;
    font-weight: bold;
    color: {t.get('text_primary')};
    padding: 8px 0;
}}

QPushButton {{
    background-color: {primary};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {primary_dark};
}}

QPushButton#secondary {{
    background-color: {t.get('surface_alt')};
    color: {t.get('text_primary')};
    border: 1px solid {t.get('border')};
}}

QPushButton#secondary:hover {{
    background-color: {t.get('border')};
}}

QPushButton#accent {{
    background-color: {accent};
}}

QPushButton#accent:hover {{
    background-color: #996f0a;
}}

QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: {t.get('border')};
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {primary};
    border-radius: 4px;
}}

QTabWidget::pane {{
    border: 1px solid {t.get('border')};
    border-radius: 8px;
    background-color: {t.get('surface')};
}}

QTabBar::tab {{
    background-color: {t.get('surface_alt')};
    border: 1px solid {t.get('border')};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {t.get('surface')};
    border-bottom: 2px solid {primary};
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}
"""


def get_colors() -> dict:
    """
    Get theme-aware color dictionary for widget styling.
    
    Returns:
        Dictionary of color values using current theme.
    """
    t = theme()
    
    return {
        "primary": t.get('success', '#5f8575'),
        "primary_light": t.get('success_bg', '#e8f0ec'),
        "primary_dark": '#4a6b5c',
        "accent": t.get('warning', '#b8860b'),
        "background": t.get('surface', '#ffffff'),
        "surface": t.get('surface_alt', '#f9fafb'),
        "border": t.get('border', '#d1d5db'),
        "text": t.get('text_primary', '#1f2937'),
        "text_secondary": t.get('text_secondary', '#6b7280'),
        "success": t.get('success', '#059669'),
        "warning": t.get('warning', '#d97706'),
        "error": t.get('error', '#dc2626'),
    }
