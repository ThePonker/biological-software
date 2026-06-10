"""
Filter Bar Styling Constants and Helpers.

Shared styling for filter bars across Observation, Collection, and Recording Scheme tabs.
Provides consistent column widths, input heights, and styled helper functions.
"""

from PySide6.QtWidgets import QLabel

from ...themes import theme


# =============================================================================
# STANDARD INPUT DIMENSIONS
# =============================================================================
STANDARD_INPUT_HEIGHT = 26


# =============================================================================
# UNIFIED COLUMN WIDTHS - Shared across all filter bars
# =============================================================================
COL_SPECIES = 180      # Column 1: Species search
COL_LOCATION = 180     # Column 2: Location search  
COL_DATE_FROM = 150    # Column 3: Date From
COL_DATE_TO = 150      # Column 4: Date To
COL_ORDER = 130        # Column 5: Order
COL_FAMILY = 130       # Column 6: Family / Subfamily
COL_VICE_COUNTY = 130  # Column 7: Vice County
COL_RECORDER = 115     # Column 8: Recorder / Collector
COL_METHOD = 115       # Column 9: Method
COL_SOURCE = 130       # Column 10: Source / Obs Type
COL_VERIFICATION = 130 # Column 11: Verification Status


def get_input_style() -> str:
    """
    Get standard input style using theme tokens.
    
    Returns:
        str: CSS stylesheet for QLineEdit inputs
    """
    t = theme()
    return f"""
        padding: 4px 6px;
        border: 1px solid {t.get('border')};
        border-radius: {t.get('radius_sm')};
        background-color: {t.get('surface')};
        color: {t.get('text_primary')};
        font-size: 13px;
    """


def get_combo_style() -> str:
    """
    Get standard combo box style using theme tokens.
    
    Returns:
        str: CSS stylesheet for QComboBox widgets
    """
    t = theme()
    return f"""
        QComboBox {{
            padding: 4px 6px;
            border: 1px solid {t.get('border')};
            border-radius: {t.get('radius_sm')};
            background-color: {t.get('surface')};
            color: {t.get('text_primary')};
            font-size: 13px;
            min-height: 18px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {t.get('text_secondary')};
            margin-right: 6px;
        }}
        QComboBox:hover {{
            border-color: {t.get('border_hover')};
        }}
    """


def get_placeholder_style() -> str:
    """
    Get style for disabled/placeholder inputs (e.g., unused columns).
    
    Returns:
        str: CSS stylesheet for placeholder QLineEdit
    """
    t = theme()
    return f"""
        QLineEdit {{
            padding: 4px 6px;
            border: 1px solid {t.get('separator')};
            border-radius: {t.get('radius_sm')};
            background-color: {t.get('surface_alt')};
            color: {t.get('text_muted')};
            font-size: 13px;
        }}
    """


def get_clear_button_style() -> str:
    """
    Get style for Clear All button.
    
    Returns:
        str: CSS stylesheet for clear button
    """
    t = theme()
    return f"""
        QPushButton {{
            background-color: {t.get('surface_alt')};
            color: {t.get('text_secondary')};
            padding: 4px 12px;
            border: 1px solid {t.get('border')};
            border-radius: {t.get('radius_sm')};
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {t.get('error_bg')};
            border-color: {t.get('error')};
            color: {t.get('error')};
        }}
        QPushButton:pressed {{
            background-color: {t.get('error')};
            color: white;
        }}
    """


def create_filter_label(text: str, muted: bool = False) -> QLabel:
    """
    Create a styled filter label.
    
    Args:
        text: Label text
        muted: If True, use muted color (for placeholder columns)
    
    Returns:
        QLabel: Styled label widget
    """
    t = theme()
    label = QLabel(text)
    color = t.get('text_muted') if muted else t.get('text_secondary')
    label.setStyleSheet(f"font-size: 12px; color: {color}; font-weight: 500;")
    label.setFixedHeight(16)
    return label
