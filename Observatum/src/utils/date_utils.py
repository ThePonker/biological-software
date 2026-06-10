"""
Date formatting utilities for Observatum V2.

Database stores dates in ISO format (YYYY-MM-DD) for SQLite query compatibility.
These utilities format dates for display in the UI.

UPDATED: Now reads user's preferred date format from settings.
"""

from datetime import datetime
from typing import Optional

from PySide6.QtCore import QSettings

from .constants import DATE_FORMAT_OPTIONS, DEFAULT_DATE_FORMAT


def get_user_date_format() -> str:
    """
    Get the user's preferred date format pattern from settings.
    
    Returns:
        strftime pattern string (e.g., "%d/%m/%Y")
    """
    settings = QSettings()
    # Get the display name (e.g., "dd/mm/yyyy")
    format_name = settings.value("general/date_format", DEFAULT_DATE_FORMAT)
    # Convert to strftime pattern
    return DATE_FORMAT_OPTIONS.get(format_name, DATE_FORMAT_OPTIONS[DEFAULT_DATE_FORMAT])


def format_date_display(iso_date: Optional[str], format_style: str = "user") -> str:
    """
    Convert ISO date to display format.
    
    Args:
        iso_date: Date string in YYYY-MM-DD format
        format_style:
            "user" = Use format from user settings (default)
            "long" = "15 June 2024"
            "short" = "15 Jun 2024"
            "numeric" = "15/06/2024" (UK format, ignores setting)
            "iso" = "2024-06-15"
            
    Returns:
        Formatted date string, or original string if parsing fails
    """
    if not iso_date:
        return ""
    
    try:
        dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
        
        if format_style == "user":
            # Use the user's preferred format from settings
            pattern = get_user_date_format()
            return dt.strftime(pattern)
        elif format_style == "long":
            return dt.strftime("%d %B %Y")  # "15 June 2024"
        elif format_style == "short":
            return dt.strftime("%d %b %Y")  # "15 Jun 2024"
        elif format_style == "numeric":
            # Use user's format for numeric too
            pattern = get_user_date_format()
            return dt.strftime(pattern)
        elif format_style == "iso":
            return dt.strftime("%Y-%m-%d")  # "2024-06-15"
        else:
            # Default to user format
            pattern = get_user_date_format()
            return dt.strftime(pattern)
            
    except (ValueError, TypeError):
        # Return original if parsing fails
        return iso_date or ""


def format_date_for_display(iso_date: Optional[str]) -> str:
    """
    Convenience function: format date using user's preferred format.
    
    Args:
        iso_date: Date string in YYYY-MM-DD format
        
    Returns:
        Formatted date string using user's setting
    """
    return format_date_display(iso_date, "user")


def parse_display_date(display_date: str) -> Optional[str]:
    """
    Convert display format back to ISO for database storage.
    
    Handles multiple input formats:
        - "15 June 2024" or "15 Jun 2024"
        - "15/06/2024" or "15-06-2024"
        - "06/15/2024" (US format)
        - "2024-06-15" (already ISO)
        
    Args:
        display_date: Date string in various formats
        
    Returns:
        ISO format string (YYYY-MM-DD) or None if parsing fails
    """
    if not display_date:
        return None
    
    display_date = display_date.strip()
    
    # Already ISO format?
    if len(display_date) >= 10 and display_date[4] == '-':
        try:
            datetime.strptime(display_date[:10], "%Y-%m-%d")
            return display_date[:10]
        except ValueError:
            pass
    
    # Try various formats
    formats = [
        "%d %B %Y",    # 15 June 2024
        "%d %b %Y",    # 15 Jun 2024
        "%d/%m/%Y",    # 15/06/2024 (UK)
        "%m/%d/%Y",    # 06/15/2024 (US)
        "%d-%m-%Y",    # 15-06-2024
        "%Y-%m-%d",    # 2024-06-15
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(display_date, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return None


def get_date_for_db(display_date: str) -> str:
    """
    Convenience function: parse display date or return as-is if already valid.
    
    Args:
        display_date: Date in any supported format
        
    Returns:
        ISO format string for database, or empty string if invalid
    """
    result = parse_display_date(display_date)
    return result if result else ""


def get_today_iso() -> str:
    """Get today's date in ISO format for database storage."""
    return datetime.now().strftime("%Y-%m-%d")


def get_today_display() -> str:
    """Get today's date in user's preferred display format."""
    return format_date_display(get_today_iso(), "user")
