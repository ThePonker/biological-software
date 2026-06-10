"""
Light Theme for Observatum V2.

The default light theme with a clean, modern look.
Uses a slate/gray color palette with amber accents.

UPDATED: Added missing tokens (info_bg_light, info_border, error_bg_light, warning_bg_light)
"""

LIGHT_THEME = {
    # =========================================================================
    # Core Surfaces
    # =========================================================================
    'background': '#f1f5f9',          # Main app background (slate-100)
    'surface': '#ffffff',              # Cards, panels, modals
    'surface_alt': '#f8fafc',          # Alternate surface (inputs, table headers)
    
    # =========================================================================
    # Text Colors
    # =========================================================================
    'text_primary': '#1e293b',         # Primary text (slate-800)
    'text_heading': '#334155',         # Headings (slate-700)
    'text_secondary': '#64748b',       # Secondary text (slate-500)
    'text_muted': '#94a3b8',           # Muted/disabled text (slate-400)
    'text_placeholder': '#94a3b8',     # Placeholder text
    
    # =========================================================================
    # Borders
    # =========================================================================
    'border': '#e2e8f0',               # Standard border (slate-200)
    'border_strong': '#cbd5e1',        # Emphasized border (slate-300)
    'separator': '#d1d5db',            # Dividers/separators (gray-300)
    
    # =========================================================================
    # Interactive States
    # =========================================================================
    'hover': '#f1f5f9',                # Hover background
    'pressed': '#e2e8f0',              # Pressed/active background
    'selected_bg': '#e0f2fe',          # Selected item background (sky-100)
    'focus_border': '#059669',         # Focus ring color (emerald-600)
    
    # =========================================================================
    # Primary Brand Color (Amber - for Recording Scheme accent)
    # =========================================================================
    'primary': '#d97706',              # Primary color (amber-600)
    'primary_hover': '#b45309',        # Primary hover (amber-700)
    'primary_pressed': '#92400e',      # Primary pressed (amber-800)
    'primary_text': '#ffffff',         # Text on primary
    'primary_bg': '#fef3c7',           # Primary light background (amber-100)
    'primary_dark': '#92400e',         # Dark primary text (amber-800)
    
    # =========================================================================
    # Success/Green (Personal Data)
    # =========================================================================
    'success': '#059669',              # Success primary (emerald-600)
    'success_light': '#10b981',        # Success lighter (emerald-500)
    'success_bright': '#34d399',       # Success bright (emerald-400)
    'success_bg': '#dcfce7',           # Success background (green-100)
    'success_bg_light': '#ecfdf5',     # Success very light bg (emerald-50)
    'success_text': '#166534',         # Success text (green-800)
    
    # =========================================================================
    # Error/Red
    # =========================================================================
    'error': '#dc2626',                # Error primary (red-600)
    'error_bg': '#fee2e2',             # Error background (red-100)
    'error_bg_light': '#fef2f2',       # Error very light bg (red-50) - ADDED
    'error_text': '#991b1b',           # Error text (red-800)
    
    # =========================================================================
    # Warning/Amber
    # =========================================================================
    'warning': '#d97706',              # Warning primary (amber-600)
    'warning_bg': '#fef3c7',           # Warning background (amber-100)
    'warning_bg_light': '#fffbeb',     # Warning very light bg (amber-50) - ADDED
    'warning_border': '#fbbf24',       # Warning border (amber-400) - ADDED
    'warning_text': '#92400e',         # Warning text (amber-800)
    
    # =========================================================================
    # Info/Blue
    # =========================================================================
    'info': '#3b82f6',                 # Info primary (blue-500)
    'info_bg': '#dbeafe',              # Info background (blue-100)
    'info_bg_light': '#eff6ff',        # Info very light bg (blue-50) - ADDED
    'info_border': '#93c5fd',          # Info border (blue-300) - ADDED
    'info_text': '#1e40af',            # Info text (blue-800)
    
    # =========================================================================
    # Purple (Commercial Data)
    # =========================================================================
    'purple': '#7c3aed',               # Purple primary (violet-600)
    'purple_bg': '#ede9fe',            # Purple background (violet-100)
    'purple_text': '#5b21b6',          # Purple text (violet-800)
    
    # =========================================================================
    # Tab/Section Accent Colors
    # =========================================================================
    'accent_home': '#10b981',          # Home tab (emerald-500)
    'accent_observations': '#3b82f6',  # Observations tab (blue-500)
    'accent_scheme': '#d97706',        # Recording Scheme tab (amber-600)
    'accent_collection': '#8b5cf6',    # Collection tab (violet-500)
    'accent_stats': '#ec4899',         # Stats tab (pink-500)
    'accent_mapping': '#06b6d4',       # Mapping tab (cyan-500)
    'accent_settings': '#6b7280',      # Settings tab (gray-500)
    
    # =========================================================================
    # Input Fields
    # =========================================================================
    'input_bg': '#f8fafc',             # Input background
    'input_border': '#e2e8f0',         # Input border
    'input_focus_border': '#059669',   # Input focus border
    
    # =========================================================================
    # Disabled States
    # =========================================================================
    'disabled_bg': '#f1f5f9',          # Disabled background
    'disabled_text': '#94a3b8',        # Disabled text
    'disabled_border': '#e2e8f0',      # Disabled border
    
    # =========================================================================
    # Scrollbars
    # =========================================================================
    'scrollbar': '#cbd5e1',            # Scrollbar thumb
    'scrollbar_hover': '#94a3b8',      # Scrollbar thumb hover
    'scrollbar_track': '#f1f5f9',      # Scrollbar track
    
    # =========================================================================
    # Tooltips
    # =========================================================================
    'tooltip_bg': '#1e293b',           # Tooltip background
    'tooltip_text': '#ffffff',         # Tooltip text
    'tooltip_border': '#334155',       # Tooltip border
    
    # =========================================================================
    # Charts/Visualization
    # =========================================================================
    'chart_bar_1': '#10b981',          # Chart color 1
    'chart_bar_2': '#3b82f6',          # Chart color 2
    'chart_bar_3': '#8b5cf6',          # Chart color 3
    'chart_bar_4': '#ec4899',          # Chart color 4
    'chart_bar_5': '#f59e0b',          # Chart color 5
    'chart_grid': '#e2e8f0',           # Chart grid lines
    
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
    
    # =========================================================================
    # Shadows (for light theme, subtle shadows work well)
    # =========================================================================
    'shadow_sm': '0 1px 2px rgba(0, 0, 0, 0.05)',
    'shadow_md': '0 4px 6px rgba(0, 0, 0, 0.07)',
    'shadow_lg': '0 10px 15px rgba(0, 0, 0, 0.1)',
}
