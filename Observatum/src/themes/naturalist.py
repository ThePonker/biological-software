"""
Naturalist Theme for Observatum V2.

The signature theme with a clean, modern look inspired by
Victorian naturalist field journals. Uses a slate/gray color
palette with coordinated tab accent colors.

Tab Colors (Naturalist Palette):
- Home/Settings: Warm Gray #8b8178
- Observation: Sage Green #5f8575
- Recording Scheme: Dusty Purple #7c6c9f
- Collection: Warm Gold #b8860b
- Stats: Steel Blue #5c6b7a
- Mapping: Terracotta #c2956e

Button Colors:
- Primary (Save/Add/Create): Moss Green #4a7c59
- Navigate/View: Tab accent color (filled)
- Cancel/Close: Warm Gray outlined #8b8178
- Delete: Faded Crimson outlined #a63d40

Tab Header Style:
- Background: accent_light
- Text: accent_dark
- Left border: 4px solid accent

UPDATED: Added missing tokens (success_bg_light, info_bg_light, info_border, error_bg_light)
"""

NATURALIST_THEME = {
    # =========================================================================
    # Core Surfaces
    # =========================================================================
    'background': '#f5f5f4',           # Main app background (stone-100)
    'surface': '#ffffff',              # Cards, panels, modals
    'surface_alt': '#f9fafb',          # Alternate surface (inputs, table headers)
    'hover': '#e5e7eb',                # Hover background
    'pressed': '#d1d5db',              # Pressed/active background
    
    # =========================================================================
    # Text Colors
    # =========================================================================
    'text_primary': '#1f2937',         # Primary text (gray-800)
    'text_heading': '#4b5563',         # Headings (gray-600)
    'text_secondary': '#6b7280',       # Secondary text (gray-500)
    'text_muted': '#9ca3af',           # Muted/disabled text (gray-400)
    'text_placeholder': '#9ca3af',     # Placeholder text
    
    # =========================================================================
    # Borders & Separators
    # =========================================================================
    'border': '#d1d5db',               # Standard border (gray-300)
    'border_hover': '#9ca3af',         # Hover border (gray-400)
    'border_strong': '#9ca3af',        # Emphasized border (gray-400)
    'separator': '#e5e7eb',            # Dividers/separators (gray-200)
    
    # =========================================================================
    # Interactive States
    # =========================================================================
    'selected_bg': '#e0f2fe',          # Selected item background (sky-100)
    'focus_border': '#4a7c59',         # Focus ring color (Moss Green)
    
    # =========================================================================
    # Primary Brand Color (Moss Green - for primary actions)
    # =========================================================================
    'primary': '#4a7c59',              # Primary color (Moss Green)
    'primary_hover': '#3d6649',        # Primary hover
    'primary_pressed': '#2f5a3b',      # Primary pressed
    'primary_text': '#ffffff',         # Text on primary
    'primary_bg': '#e8f0eb',           # Primary light background
    'primary_dark': '#2f5a3b',         # Dark primary text
    
    # =========================================================================
    # Secondary (Cancel/Close buttons) - Warm Gray
    # =========================================================================
    'secondary': '#8b8178',            # Secondary color (Warm Gray)
    'secondary_hover': '#6b635b',      # Secondary hover
    'secondary_text': '#8b8178',       # Text for outlined secondary buttons
    
    # =========================================================================
    # Danger (Delete buttons) - Faded Crimson
    # =========================================================================
    'danger': '#a63d40',               # Danger color (Faded Crimson)
    'danger_hover': '#8b3033',         # Danger hover
    'danger_text': '#a63d40',          # Text for outlined danger buttons
    'danger_bg': '#fce8e8',            # Danger light background
    
    # =========================================================================
    # Success - Moss Green
    # =========================================================================
    'success': '#4a7c59',              # Success primary (moss green)
    'success_hover': '#3d6b4a',        # Success hover (moss green dark)
    'success_light': '#5a8c69',        # Success lighter (moss green light)
    'success_bright': '#6a9c79',       # Success bright (moss green bright)
    'success_bg': '#f0f5f2',           # Success background (moss green bg)
    'success_bg_light': '#f5f9f6',     # Success very light bg (moss green very light)
    'success_text': '#3d6b4a',         # Success text (moss green dark)
    
    # =========================================================================
    # Warning - Amber
    # =========================================================================
    'warning': '#d97706',              # Warning primary (amber-600)
    'warning_hover': '#b45309',        # Warning hover (amber-700)
    'warning_bg': '#fef3c7',           # Warning background (amber-100)
    'warning_bg_light': '#fffbeb',     # Warning very light bg (amber-50) - ADDED
    'warning_border': '#fbbf24',       # Warning border (amber-400) - ADDED
    'warning_text': '#92400e',         # Warning text (amber-800)
    
    # =========================================================================
    # Error - Red (for validation errors, not delete buttons)
    # =========================================================================
    'error': '#dc2626',                # Error primary (red-600)
    'error_hover': '#b91c1c',          # Error hover (red-700)
    'error_bg': '#fee2e2',             # Error background (red-100)
    'error_bg_light': '#fef2f2',       # Error very light bg (red-50) - ADDED
    'error_text': '#991b1b',           # Error text (red-800)
    
    # =========================================================================
    # Info - Blue
    # =========================================================================
    'info': '#2563eb',                 # Info primary (blue-600)
    'info_hover': '#1d4ed8',           # Info hover (blue-700)
    'info_bg': '#dbeafe',              # Info background (blue-100)
    'info_bg_light': '#eff6ff',        # Info very light bg (blue-50) - ADDED
    'info_border': '#93c5fd',          # Info border (blue-300) - ADDED
    'info_text': '#1e40af',            # Info text (blue-800)
    
    # =========================================================================
    # Tab/Section Accent Colors (Naturalist Palette)
    # These should match TabColors in config.py
    # =========================================================================
    
    # Home / Settings - Warm Gray
    'accent_home': '#8b8178',
    'accent_home_light': '#f5f4f3',
    'accent_home_dark': '#6b635b',
    
    'accent_settings': '#8b8178',
    'accent_settings_light': '#f5f4f3',
    'accent_settings_dark': '#6b635b',
    
    # Observation - Sage Green
    'accent_observation': '#5f8575',
    'accent_observation_light': '#e8f0ec',
    'accent_observation_dark': '#4a6b5c',
    
    # Recording Scheme - Dusty Purple
    'accent_scheme': '#7c6c9f',
    'accent_scheme_light': '#eeeaf3',
    'accent_scheme_dark': '#5c4f7a',
    
    # Collection - Warm Gold
    'accent_collection': '#b8860b',
    'accent_collection_light': '#faf6eb',
    'accent_collection_dark': '#8a6508',
    
    # Stats - Steel Blue
    'accent_stats': '#5c6b7a',
    'accent_stats_light': '#eaecef',
    'accent_stats_dark': '#454f5c',
    
    # Mapping - Terracotta
    'accent_mapping': '#c2956e',
    'accent_mapping_light': '#f7f2ed',
    'accent_mapping_dark': '#9a7555',
    
    # =========================================================================
    # Legacy accent names (for backwards compatibility)
    # =========================================================================
    'accent_observations': '#5f8575',
    'accent_observations_light': '#e8f0ec',
    
    # Purple (Recording Scheme alias)
    'purple': '#7c6c9f',
    'purple_bg': '#eeeaf3',
    'purple_text': '#5c4f7a',
    
    # Commercial - Violet (for commercial records)
    'commercial': '#8b5cf6',
    'commercial_bg': '#f3f0ff',
    'commercial_text': '#6d28d9',
    
    # =========================================================================
    # Button Colors (explicit names for clarity)
    # =========================================================================
    'button_primary': '#4a7c59',       # Moss Green - Save/Add/Create
    'button_primary_hover': '#3d6649',
    'button_primary_text': '#ffffff',
    
    'button_secondary': '#8b8178',     # Warm Gray - Cancel/Close (outlined)
    'button_secondary_hover': '#6b635b',
    
    'button_danger': '#a63d40',        # Faded Crimson - Delete (outlined)
    'button_danger_hover': '#8b3033',
    
    # =========================================================================
    # Input Fields
    # =========================================================================
    'input_bg': '#ffffff',             # Input background
    'input_border': '#d1d5db',         # Input border (matches 'border')
    'input_border_hover': '#9ca3af',   # Input border hover
    'input_focus_border': '#4a7c59',   # Input focus border (Moss Green)
    'input_placeholder': '#9ca3af',    # Input placeholder text
    
    # =========================================================================
    # Disabled States
    # =========================================================================
    'disabled_bg': '#f3f4f6',          # Disabled background (gray-100)
    'disabled_text': '#9ca3af',        # Disabled text (gray-400)
    'disabled_border': '#e5e7eb',      # Disabled border (gray-200)
    
    # =========================================================================
    # Scrollbars
    # =========================================================================
    'scrollbar': '#cbd5e1',            # Scrollbar thumb (slate-300)
    'scrollbar_hover': '#94a3b8',      # Scrollbar thumb hover (slate-400)
    'scrollbar_track': '#f1f5f9',      # Scrollbar track (slate-100)
    
    # =========================================================================
    # Tooltips
    # =========================================================================
    'tooltip_bg': '#1f2937',           # Tooltip background (gray-800)
    'tooltip_text': '#ffffff',         # Tooltip text
    'tooltip_border': '#374151',       # Tooltip border (gray-700)
    
    # =========================================================================
    # Tables
    # =========================================================================
    'table_header_bg': '#f9fafb',      # Table header background
    'table_row_alt': '#f9fafb',        # Alternate row background
    'table_row_hover': '#f3f4f6',      # Row hover background
    'table_row_selected': '#e0f2fe',   # Selected row background
    'table_border': '#e5e7eb',         # Table borders
    
    # =========================================================================
    # Charts/Visualization (using tab accent colors)
    # =========================================================================
    'chart_1': '#5f8575',              # Sage Green (Observation)
    'chart_2': '#7c6c9f',              # Dusty Purple (Scheme)
    'chart_3': '#b8860b',              # Warm Gold (Collection)
    'chart_4': '#5c6b7a',              # Steel Blue (Stats)
    'chart_5': '#c2956e',              # Terracotta (Mapping)
    'chart_6': '#8b8178',              # Warm Gray (Home)
    'chart_grid': '#e5e7eb',           # Chart grid lines
    'chart_axis': '#6b7280',           # Chart axis text
    
    # =========================================================================
    # Typography
    # Note: Font sizes are integers (points). Use with f"{t.get('font_size_base')}pt"
    # =========================================================================
    'font_family': 'Segoe UI, system-ui, -apple-system, sans-serif',
    'font_size_xs': 9,
    'font_size_sm': 10,
    'font_size_base': 11,
    'font_size_lg': 12,
    'font_size_xl': 14,
    'font_size_2xl': 16,
    'font_size_3xl': 20,
    'font_size_stat': 24,              # Large stat numbers
    
    # =========================================================================
    # Spacing/Sizing
    # =========================================================================
    'radius_sm': '4px',
    'radius_md': '6px',
    'radius_lg': '8px',
    'radius_xl': '12px',
    
    'spacing_xs': '4px',
    'spacing_sm': '8px',
    'spacing_md': '12px',
    'spacing_lg': '16px',
    'spacing_xl': '24px',
    
    # =========================================================================
    # Shadows
    # =========================================================================
    'shadow_sm': '0 1px 2px rgba(0, 0, 0, 0.05)',
    'shadow_md': '0 4px 6px rgba(0, 0, 0, 0.07)',
    'shadow_lg': '0 10px 15px rgba(0, 0, 0, 0.1)',
    'shadow_xl': '0 20px 25px rgba(0, 0, 0, 0.15)',
}
