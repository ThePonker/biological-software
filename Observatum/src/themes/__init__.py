"""
Observatum V2 Theme System.

Provides the Naturalist theme - a cohesive color palette inspired
by Victorian naturalist field journals with coordinated tab colors.

Usage:
    from src.themes import theme
    
    # Get a color
    bg_color = theme().get('background')
    
    # Get tab accent color
    obs_accent = theme().get('accent_observations')  # Sage Green
    
    # Use a preset style
    button_style = theme().button_primary_style()
"""

from .theme_manager import ThemeManager, theme

__all__ = ['ThemeManager', 'theme']
