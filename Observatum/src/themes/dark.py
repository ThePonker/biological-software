"""
Dark Theme for Observatum V2.

A dark theme with deep slate backgrounds and adjusted colors
for comfortable viewing in low-light conditions.

UPDATED: Added missing tokens (info_bg_light, info_border, error_bg_light, warning_bg_light)
"""

DARK_THEME = {
    # =========================================================================
    # Core Surfaces
    # =========================================================================
    'background': '#0f172a',           # Main app background (slate-900)
    'surface': '#1e293b',              # Cards, panels, modals (slate-800)
    'surface_alt': '#334155',          # Alternate surface (slate-700)
    
    # =========================================================================
    # Text Colors
    # =========================================================================
    'text_primary': '#f1f5f9',         # Primary text (slate-100)
    'text_heading': '#e2e8f0',         # Headings (slate-200)
    'text_secondary': '#94a3b8',       # Secondary text (slate-400)
    'text_muted': '#64748b',           # Muted/disabled text (slate-500)
    'text_placeholder': '#64748b',     # Placeholder text
    
    # =========================================================================
    # Borders
    # =========================================================================
    'border': '#334155',               # Standard border (slate-700)
    'border_strong': '#475569',        # Emphasized border (slate-600)
    'separator': '#475569',            # Dividers/separators
    
    # =========================================================================
    # Interactive States
    # =========================================================================
    'hover': '#334155',                # Hover background
    'pressed': '#475569',              # Pressed/active background
    'selected_bg': '#1e3a5f',          # Selected item background (blue-tinted)
    'focus_border': '#34d399',         # Focus ring color (emerald-400)
    
    # =========================================================================
    # Primary Brand Color (Amber - adjusted for dark mode)
    # =========================================================================
    'primary': '#f59e0b',              # Primary color (amber-500)
    'primary_hover': '#d97706',        # Primary hover (amber-600)
    'primary_pressed': '#b45309',      # Primary pressed (amber-700)
    'primary_text': '#1e293b',         # Text on primary (dark)
    'primary_bg': '#451a03',           # Primary dark background (amber-950)
    'primary_dark': '#fcd34d',         # Light primary text (amber-300)
    
    # =========================================================================
    # Success/Green (Personal Data)
    # =========================================================================
    'success': '#34d399',              # Success primary (emerald-400)
    'success_light': '#6ee7b7',        # Success lighter (emerald-300)
    'success_bright': '#a7f3d0',       # Success bright (emerald-200)
    'success_bg': '#064e3b',           # Success background (emerald-900)
    'success_bg_light': '#022c22',     # Success very light bg (emerald-950)
    'success_text': '#a7f3d0',         # Success text (emerald-200)
    
    # =========================================================================
    # Error/Red
    # =========================================================================
    'error': '#f87171',                # Error primary (red-400)
    'error_bg': '#450a0a',             # Error background (red-950)
    'error_bg_light': '#7f1d1d',       # Error lighter bg (red-900) - ADDED
    'error_text': '#fecaca',           # Error text (red-200)
    
    # =========================================================================
    # Warning/Amber
    # =========================================================================
    'warning': '#fbbf24',              # Warning primary (amber-400)
    'warning_bg': '#451a03',           # Warning background (amber-950)
    'warning_bg_light': '#78350f',     # Warning lighter bg (amber-900) - ADDED
    'warning_border': '#f59e0b',       # Warning border (amber-500) - ADDED
    'warning_text': '#fde68a',         # Warning text (amber-200)
    
    # =========================================================================
    # Info/Blue
    # =========================================================================
    'info': '#60a5fa',                 # Info primary (blue-400)
    'info_bg': '#172554',              # Info background (blue-950)
    'info_bg_light': '#1e3a8a',        # Info lighter bg (blue-900) - ADDED
    'info_border': '#3b82f6',          # Info border (blue-500) - ADDED
    'info_text': '#bfdbfe',            # Info text (blue-200)
    
    # =========================================================================
    # Purple (Commercial Data)
    # =========================================================================
    'purple': '#a78bfa',               # Purple primary (violet-400)
    'purple_bg': '#2e1065',            # Purple background (violet-950)
    'purple_text': '#c4b5fd',          # Purple text (violet-300)
    
    # =========================================================================
    # Tab/Section Accent Colors (brighter for dark mode)
    # =========================================================================
    'accent_home': '#34d399',          # Home tab (emerald-400)
    'accent_observations': '#60a5fa',  # Observations tab (blue-400)
    'accent_scheme': '#fbbf24',        # Recording Scheme tab (amber-400)
    'accent_collection': '#a78bfa',    # Collection tab (violet-400)
    'accent_stats': '#f472b6',         # Stats tab (pink-400)
    'accent_mapping': '#22d3ee',       # Mapping tab (cyan-400)
    'accent_settings': '#9ca3af',      # Settings tab (gray-400)
    
    # =========================================================================
    # Input Fields
    # =========================================================================
    'input_bg': '#1e293b',             # Input background
    'input_border': '#475569',         # Input border
    'input_focus_border': '#34d399',   # Input focus border
    
    # =========================================================================
    # Disabled States
    # =========================================================================
    'disabled_bg': '#1e293b',          # Disabled background
    'disabled_text': '#475569',        # Disabled text
    'disabled_border': '#334155',      # Disabled border
    
    # =========================================================================
    # Scrollbars
    # =========================================================================
    'scrollbar': '#475569',            # Scrollbar thumb
    'scrollbar_hover': '#64748b',      # Scrollbar thumb hover
    'scrollbar_track': '#1e293b',      # Scrollbar track
    
    # =========================================================================
    # Tooltips
    # =========================================================================
    'tooltip_bg': '#f1f5f9',           # Tooltip background (inverted)
    'tooltip_text': '#1e293b',         # Tooltip text
    'tooltip_border': '#e2e8f0',       # Tooltip border
    
    # =========================================================================
    # Charts/Visualization (brighter for dark mode)
    # =========================================================================
    'chart_bar_1': '#34d399',          # Chart color 1
    'chart_bar_2': '#60a5fa',          # Chart color 2
    'chart_bar_3': '#a78bfa',          # Chart color 3
    'chart_bar_4': '#f472b6',          # Chart color 4
    'chart_bar_5': '#fbbf24',          # Chart color 5
    'chart_grid': '#334155',           # Chart grid lines
    
    # =========================================================================
    # Typography (same as light)
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
    'font_size_stat': 24,
    
    # =========================================================================
    # Spacing/Sizing (same as light)
    # =========================================================================
    'radius_sm': '4px',
    'radius_md': '6px',
    'radius_lg': '8px',
    'radius_xl': '12px',
    
    # =========================================================================
    # Shadows (stronger for dark theme visibility)
    # =========================================================================
    'shadow_sm': '0 1px 2px rgba(0, 0, 0, 0.3)',
    'shadow_md': '0 4px 6px rgba(0, 0, 0, 0.4)',
    'shadow_lg': '0 10px 15px rgba(0, 0, 0, 0.5)',
}
