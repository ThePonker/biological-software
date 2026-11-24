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

# token -> Naturalist theme key. The one list the light colours are made from.
_LIGHT_KEYS = {
    "background_primary": "background",
    "background_secondary": "surface",
    "background_surface": "surface_alt",
    "background_border": "border",

    "text_primary": "text_primary",
    "text_secondary": "text_secondary",
    "text_muted": "text_muted",
    "text_accent": "primary",

    "button_primary_bg": "primary",
    "button_primary_hover": "primary_hover",
    "button_primary_text": "primary_text",
    "button_secondary_bg": "secondary",
    "button_secondary_hover": "secondary_hover",
    "button_danger_bg": "danger",
    "button_danger_hover": "danger_hover",

    "border": "border",
    "border_hover": "border_hover",
    "border_accent": "primary",

    "success": "success",
    "warning": "warning",
    "danger": "danger",
    "info": "info",
}

# Used only if Observatum's theme cannot be imported: the Naturalist theme's own values
# (the 'warning' and 'info' ones here used to differ from the theme's; review 24 Nov 2026).
_LIGHT_FALLBACKS = {
    "background": "#f5f5f4", "surface": "#ffffff", "surface_alt": "#f9fafb", "border": "#d1d5db",
    "text_primary": "#1f2937", "text_secondary": "#6b7280", "text_muted": "#9ca3af",
    "primary": "#4a7c59", "primary_hover": "#3d6649", "primary_text": "#ffffff",
    "secondary": "#8b8178", "secondary_hover": "#6b635b", "danger": "#a63d40",
    "danger_hover": "#8b3033", "border_hover": "#9ca3af", "success": "#4a7c59",
    "warning": "#d97706", "info": "#2563eb",
}


def _get_light_colors_from_main() -> Dict[str, str]:
    """The light colours: the main theme's value for each token (its own fallback if the
    theme cannot be imported)."""
    return {token: NATURALIST_THEME.get(key, _LIGHT_FALLBACKS[key])
            for token, key in _LIGHT_KEYS.items()}


LIGHT_COLORS = _get_light_colors_from_main()


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
