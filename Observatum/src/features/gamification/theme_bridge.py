"""
Theme Bridge for Gamification Module.

Maps gamification theme tokens to the main Observatum theme system.
This allows the gamification module to use centralized theme values
while maintaining its own specialized tokens (trophies, tiers, etc.).

Usage:
    from .theme_bridge import get_theme_colors
    
    colors = get_theme_colors()
    background = colors['background']
"""

from typing import Dict

# Try to import main theme, fall back to local defaults
try:
    from src.themes.naturalist import NATURALIST_THEME
    MAIN_THEME_AVAILABLE = True
except ImportError:
    NATURALIST_THEME = {}
    MAIN_THEME_AVAILABLE = False


# =============================================================================
# DARK MODE MAPPINGS (Gamification window uses dark theme)
# =============================================================================

DARK_COLORS = {
    # Backgrounds
    "background_primary": "#1a1a2e",
    "background_secondary": "#252542",
    "background_surface": "#2a2a3e",
    "background_border": "#333355",
    
    # Text
    "text_primary": "#eeeeee",
    "text_secondary": "#aaaaaa",
    "text_muted": "#888888",
    "text_accent": "#c9a227",  # Gold
    
    # Buttons
    "button_primary_bg": "#4a7c59",  # Moss Green
    "button_primary_hover": "#5a8c69",
    "button_primary_text": "#ffffff",
    "button_secondary_bg": "#8b8178",  # Warm Gray
    "button_secondary_hover": "#6b635b",
    "button_danger_bg": "#a63d40",  # Faded Crimson
    "button_danger_hover": "#8b3033",
    
    # Borders
    "border": "#333355",
    "border_hover": "#444466",
    "border_accent": "#c9a227",
    
    # Status colors
    "success": "#4a7c59",
    "warning": "#c9a227",
    "danger": "#a63d40",
    "info": "#5c6b7a",
}


# =============================================================================
# LIGHT MODE MAPPINGS (For potential light theme support)
# =============================================================================

def _get_light_colors_from_main() -> Dict[str, str]:
    """Extract light colors from main theme if available."""
    if not MAIN_THEME_AVAILABLE:
        return {}
    
    return {
        "background_primary": NATURALIST_THEME.get("background", "#f5f5f4"),
        "background_secondary": NATURALIST_THEME.get("surface", "#ffffff"),
        "background_surface": NATURALIST_THEME.get("surface_alt", "#f9fafb"),
        "background_border": NATURALIST_THEME.get("border", "#d1d5db"),
        
        "text_primary": NATURALIST_THEME.get("text_primary", "#1f2937"),
        "text_secondary": NATURALIST_THEME.get("text_secondary", "#6b7280"),
        "text_muted": NATURALIST_THEME.get("text_muted", "#9ca3af"),
        "text_accent": NATURALIST_THEME.get("primary", "#4a7c59"),
        
        "button_primary_bg": NATURALIST_THEME.get("primary", "#4a7c59"),
        "button_primary_hover": NATURALIST_THEME.get("primary_hover", "#3d6649"),
        "button_primary_text": NATURALIST_THEME.get("primary_text", "#ffffff"),
        "button_secondary_bg": NATURALIST_THEME.get("secondary", "#8b8178"),
        "button_secondary_hover": NATURALIST_THEME.get("secondary_hover", "#6b635b"),
        "button_danger_bg": NATURALIST_THEME.get("danger", "#a63d40"),
        "button_danger_hover": NATURALIST_THEME.get("danger_hover", "#8b3033"),
        
        "border": NATURALIST_THEME.get("border", "#d1d5db"),
        "border_hover": NATURALIST_THEME.get("border_hover", "#9ca3af"),
        "border_accent": NATURALIST_THEME.get("primary", "#4a7c59"),
        
        "success": NATURALIST_THEME.get("success", "#4a7c59"),
        "warning": NATURALIST_THEME.get("warning", "#c9a227"),
        "danger": NATURALIST_THEME.get("danger", "#a63d40"),
        "info": NATURALIST_THEME.get("info", "#5c6b7a"),
    }


LIGHT_COLORS = _get_light_colors_from_main() if MAIN_THEME_AVAILABLE else {
    "background_primary": "#f5f5f4",
    "background_secondary": "#ffffff",
    "background_surface": "#f9fafb",
    "background_border": "#d1d5db",
    
    "text_primary": "#1f2937",
    "text_secondary": "#6b7280",
    "text_muted": "#9ca3af",
    "text_accent": "#4a7c59",
    
    "button_primary_bg": "#4a7c59",
    "button_primary_hover": "#3d6649",
    "button_primary_text": "#ffffff",
    "button_secondary_bg": "#8b8178",
    "button_secondary_hover": "#6b635b",
    "button_danger_bg": "#a63d40",
    "button_danger_hover": "#8b3033",
    
    "border": "#d1d5db",
    "border_hover": "#9ca3af",
    "border_accent": "#4a7c59",
    
    "success": "#4a7c59",
    "warning": "#c9a227",
    "danger": "#a63d40",
    "info": "#5c6b7a",
}


# =============================================================================
# PUBLIC API
# =============================================================================

def get_theme_colors(dark_mode: bool = True) -> Dict[str, str]:
    """
    Get theme colors for the gamification module.
    
    Args:
        dark_mode: If True, returns dark theme colors. Otherwise light theme.
    
    Returns:
        Dictionary of color tokens to hex values.
    """
    return DARK_COLORS if dark_mode else LIGHT_COLORS


def get_color(key: str, dark_mode: bool = True, default: str = "#888888") -> str:
    """
    Get a specific color value.
    
    Args:
        key: Color token name
        dark_mode: Theme mode
        default: Fallback value if key not found
    
    Returns:
        Hex color string
    """
    colors = get_theme_colors(dark_mode)
    return colors.get(key, default)


def is_main_theme_available() -> bool:
    """Check if the main Observatum theme is available."""
    return MAIN_THEME_AVAILABLE
