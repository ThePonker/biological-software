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

from shared.text_sizes import TEXT_PX   # R18: the named pixel text sizes (one source)

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
    
    # Personal / Commercial / Species dashboard tabs (TabColors in config.py reads these;
    # added R13 with the exact values those tabs have always drawn)
    'accent_personal': '#10b981',
    'accent_personal_light': '#d1fae5',
    'accent_personal_dark': '#065f46',
    'accent_commercial': '#8b5cf6',
    'accent_commercial_light': '#ede9fe',
    'accent_commercial_dark': '#5b21b6',
    'accent_species': '#3b82f6',
    'accent_species_light': '#dbeafe',
    'accent_species_dark': '#1e40af',
    
    # Per-app identity colours the Atrium launcher draws behind each app's icon (R13)
    'app_observatum': '#6b4c8a',
    'app_observatum_light': '#f0eaf5',
    'app_munia': '#4a6580',
    'app_munia_light': '#e4ecf2',
    
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
    # R21: font_family '' or a name that shared/theme_fonts does not bundle means "leave the
    # application font as it is"; font_heading '' means the same for card/section titles.
    'font_heading': '',
    # R21: the main window's tab bar "header" (1940s only; '' = none, the tab bar draws as before)
    'header_bg': '',
    'header_rule': '',
    'header_text': '',
    'header_mark': '',
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
    
    # --- R21 A: tokens for colours that were written into views ---
    # Text on a filled accent / secondary-coloured button or header (not a primary button)
    'on_accent_text': '#ffffff',
    'on_accent_text_soft': 'rgba(255, 255, 255, 0.8)',
    # Detail-dialog accents of the Stats dashboards (Personal / All / Commercial)
    'stats_personal_accent': '#7a9e7e',
    'stats_personal_accent_light': '#e8f0ea',
    'stats_personal_accent_dark': '#3d5e44',
    'stats_all_accent': '#6e8898',
    'stats_all_accent_light': '#e8eef2',
    'stats_all_accent_dark': '#4a6070',
    'stats_commercial_accent': '#b8860b',
    'stats_commercial_accent_light': '#fdf5e6',
    'stats_commercial_accent_dark': '#8b6914',
    # Commercial Reports: embargo alert banner and status colours
    'embargo_alert_bg': '#fff3e0',
    'embargo_alert_border': '#ffb74d',
    'embargo_expired': '#e65100',
    'embargo_released': '#2e7d32',
    # Recording Scheme dashboard / toolbar
    'scheme_selection_bg': '#e8e0f0',
    'scheme_toolbar_hover': '#5a7888',
    # Stats tables
    'new_species_text': '#008000',
    # Buttons, hovers and disabled states written into dialogs and toolbars
    'primary_hover_deep': '#3d6348',
    'danger_hover_bg': '#fdf0f0',
    'btn_disabled_bg': '#ccc',
    'btn_disabled_text': '#888',
    'btn_outline_disabled_text': '#aaa',
    'btn_outline_disabled_border': '#ccc',
    'collection_toolbar_hover': '#7a7168',
    'collection_profile_btn_hover': '#7a7068',
    # Dialogs: calendar popup, drawer bar, checked rows, species match types
    'calendar_nav_text': '#4a4a4a',
    'calendar_nav_bg': '#f5f0eb',
    'collection_bar_border': '#e8dcc0',
    'radio_checked_bg': '#e8f0ea',
    'checked_row_bg': '#e8f0ea',
    'match_synonym': '#2196F3',
    'match_alias': '#9C27B0',
    'match_cf_resolved': '#FF9800',
    'match_aggregate': '#FF9800',
    'match_manual': '#FF9800',

    # --- R21 B: tokens for colours that were written into views ---
    # Text on a coloured fill (a second theme may colour each differently)
    'text_on_accent': '#ffffff',       # text on a tab-accent fill (hover, selected row, accent button)
    'text_on_success': '#ffffff',      # text on a success (green) button
    'text_on_error': '#ffffff',        # text on an error (red) button or pressed state
    # Buttons and overlays
    'button_primary_hover_dark': '#3d6b4a',      # hover of the primary button in the column dialog
    'danger_hover_overlay': 'rgba(166, 61, 64, 0.1)',    # hover wash of an outlined danger button
    'table_selection_overlay': 'rgba(74,124,89,0.30)',   # selected row of the Data Entry grid and jobs list
    'staging_unmatched_species_bg': '#faded6',   # Data Entry: a species with no TVK
    'calendar_nav_hover': 'rgba(255, 255, 255, 0.18)',   # hover on the calendar's month/year buttons
    # Splash screen (dark, drawn with QPainter)
    'splash_bg': '#1c1c1e',
    'splash_bg_mid': '#252527',
    'splash_gradient_top': '#2a2a2c',
    'splash_gradient_mid': '#222224',
    'splash_moss': '#4a7c59',
    'splash_moss_light': '#5a9a6e',
    'splash_moss_dim': '#3a6248',
    'splash_text_warm': '#8b8178',
    'splash_cream': '#d4cdc4',
    'splash_gold_dim': '#8a7a5a',
    'splash_text_dim': '#5a5650',
    'splash_heather': '#8e6cb8',
    'splash_glow': '#0c4a7c59',          # centre glow, alpha 12 of Moss Green
    'splash_border_inner': '#504a7c59',  # inner frame line, alpha 80 of Moss Green
    # Colours that were written into the views (24 Nov 2026); the same value in every theme
    # Curator box preview (painted by hand)
    'preview_ink': '#333333',   # box title and family name
    'ink_soft': '#555555',   # soft dark text: capacity label, locked tier range, vice-county map stroke
    'preview_label_muted': '#888888',   # specimen count under a family name
    'preview_outline': '#999999',   # outline of the box
    'preview_rule': '#cccccc',   # dotted leader line and capacity bar outline
    'preview_track': '#eeeeee',   # empty part of the capacity bar
    'preview_box_fill': '#fafafa',   # inside of the box
    'family_purple': '#6b5b73',   # tenth colour of the family cycle
    # Gamification windows
    'btn_neutral_bg': '#e0e0e0',   # secondary button
    'btn_neutral_hover': '#d0d0d0',   # secondary button, hovered
    'progress_track': '#dddddd',   # progress bar track
    'tab_idle_bg': '#e8e8e8',   # tab not selected
    'neutral_light': '#f0f0f0',   # hovered tab; scroll bar track
    'scroll_handle_hover': '#aaaaaa',   # scroll bar handle, hovered
    'launcher_bg': '#f0f7f4',   # Achievements card on Home
    'launcher_ink': '#2d5a4a',   # text in the Achievements quick stats
    'launcher_stats_bg': '#e8f4ed',   # Achievements quick stats panel
    'launcher_stats_border': '#c8ddd0',   # Achievements quick stats panel border
    'ink_mid': '#666666',   # locked tier name
    'vc_unearned': '#3d3d3d',   # vice county not yet visited on the achievements map
    # Munia and Examen
    'season_tint_green': '#edf5ef',   # capacity grid, Apr-Jul
    'season_tint_purple': '#eee9f3',   # capacity grid, Aug-Oct
    'season_tint_amber': '#f7f0e0',   # capacity grid, Nov-Dec
    'table_selection_purple': '#c8bfdb',   # selected row of the Munia projects table
    'table_alt_row_warm': '#f4f3f1',   # alternate row of the Munia projects table
    'primary_hover_alt': '#3d6a4b',   # hover of the Examen import dialog's green buttons
    'outline_btn_hover_bg': '#f0eeec',   # hover wash of an outlined grey button
}

# R18: pixel text sizes by name (font_px_caption .. font_px_display_64). Apps read them through
# shared.text_sizes.font_px / font_css; the point tokens above are unchanged.
NATURALIST_THEME.update({f"font_px_{_name}": _px for _name, _px in TEXT_PX.items()})
