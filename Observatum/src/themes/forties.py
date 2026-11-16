"""
1940s Theme for Observatum V2 and Data Entry (R21, Wil's chosen mock-up).

A post-war natural-history-book look: cream paper, cloth-green bindings, a mustard rule, EB Garamond
text and Cormorant SC titles. Chosen in Settings > General > Appearance; it takes effect when
Observatum (or Data Entry) is next opened (shared/theme_choice.py).

Every key NATURALIST_THEME has is here (tests/test_r21_theme_choice.py checks), so a view that reads
a token gets a 1940s value. Map drawing does not use this theme: maps stay Naturalist (shared/maps).

Paper #F4EDDA  cards #FBF6E8  inputs #FFFCF2  ink #23302A  second ink #5E5848
Cloth green #2F4A3A (buttons, focus, header)  mustard #C8A23A (rules)  rust #8E3F1F (danger)
"""

from shared.text_sizes import TEXT_PX   # the named pixel text sizes (one source)

_MUSTARD = '#C8A23A'
_CLOTH = '#2F4A3A'

FORTIES_THEME = {
    # Core surfaces
    'background': '#F4EDDA',
    'surface': '#FBF6E8',
    'surface_alt': '#F1EAD3',
    'hover': '#EBE2C8',
    'pressed': '#DDD2B2',

    # Text
    'text_primary': '#23302A',
    'text_heading': '#2E3B33',
    'text_secondary': '#4B463A',
    'text_muted': '#625B4B',
    'text_placeholder': '#716A57',

    # Borders & separators
    'border': '#CFC6AE',
    'border_hover': '#A89F86',
    'border_strong': '#A89F86',
    'separator': '#E2D9C0',

    # Interactive states
    'selected_bg': '#E3E8D3',
    'focus_border': _CLOTH,

    # Primary (cloth green)
    'primary': _CLOTH,
    'primary_hover': '#3B5C48',
    'primary_pressed': '#243A2D',
    'primary_text': '#FBF6E8',
    'primary_bg': '#E4E9D8',
    'primary_dark': '#243A2D',

    # Secondary (Cancel/Close) - warm grey
    'secondary': '#7A7060',
    'secondary_hover': '#5E5848',
    'secondary_text': '#6A6150',

    # Danger - rust
    'danger': '#8E3F1F',
    'danger_hover': '#74321A',
    'danger_text': '#8E3F1F',
    'danger_bg': '#F3DFD0',

    # Success - olive
    'success': '#4F6B3A',
    'success_hover': '#3F5A2D',
    'success_light': '#62804A',
    'success_bright': '#769660',
    'success_bg': '#E6ECD6',
    'success_bg_light': '#EFF3E2',
    'success_text': '#3A5228',

    # Warning - old gold
    'warning': '#A8741A',
    'warning_hover': '#8A5C12',
    'warning_bg': '#F3E3B8',
    'warning_bg_light': '#F8EDD0',
    'warning_border': '#D9B65A',
    'warning_text': '#6B4A0E',

    # Error - brick red
    'error': '#A33326',
    'error_hover': '#862A1F',
    'error_bg': '#F2D9CF',
    'error_bg_light': '#F8E8E1',
    'error_text': '#7D2A1C',

    # Info - faded teal
    'info': '#3F6578',
    'info_hover': '#335366',
    'info_bg': '#D9E4E4',
    'info_bg_light': '#E7EEEC',
    'info_border': '#9DB6B8',
    'info_text': '#2C4A5A',

    # Tab / section accents (muted 1940s palette)
    'accent_home': '#8A7F68',
    'accent_home_light': '#F1EBDA',
    'accent_home_dark': '#655C48',

    'accent_settings': '#8A7F68',
    'accent_settings_light': '#F1EBDA',
    'accent_settings_dark': '#655C48',

    'accent_observation': '#5E7F5A',
    'accent_observation_light': '#E5EBD6',
    'accent_observation_dark': '#44603F',

    'accent_scheme': '#7A4F63',
    'accent_scheme_light': '#EFE1E3',
    'accent_scheme_dark': '#5A3647',

    'accent_collection': '#B48A1F',
    'accent_collection_light': '#F4EACB',
    'accent_collection_dark': '#85650F',

    'accent_stats': '#4E6A7E',
    'accent_stats_light': '#DFE6E6',
    'accent_stats_dark': '#384E5E',

    'accent_mapping': '#B5683F',
    'accent_mapping_light': '#F2E1D4',
    'accent_mapping_dark': '#8A4D2C',

    # Legacy accent names
    'accent_observations': '#5E7F5A',
    'accent_observations_light': '#E5EBD6',

    'purple': '#7A4F63',
    'purple_bg': '#EFE1E3',
    'purple_text': '#5A3647',

    'commercial': '#7B5A8C',
    'commercial_bg': '#EADFEA',
    'commercial_text': '#583E67',

    'accent_personal': '#4F8A62',
    'accent_personal_light': '#DDE9D6',
    'accent_personal_dark': '#2F5E40',
    'accent_commercial': '#7B5A8C',
    'accent_commercial_light': '#EADFEA',
    'accent_commercial_dark': '#583E67',
    'accent_species': '#4F6F8F',
    'accent_species_light': '#DCE5EA',
    'accent_species_dark': '#35506B',

    # Per-app identity colours (Atrium); Atrium stays Naturalist, kept in step
    'app_observatum': '#6A4A63',
    'app_observatum_light': '#F0E6E8',
    'app_munia': '#44627A',
    'app_munia_light': '#DEE7EA',

    # Buttons
    'button_primary': _CLOTH,
    'button_primary_hover': '#3B5C48',
    'button_primary_text': '#FBF6E8',

    'button_secondary': '#7A7060',
    'button_secondary_hover': '#5E5848',

    'button_danger': '#8E3F1F',
    'button_danger_hover': '#74321A',

    # Inputs
    'input_bg': '#FFFCF2',
    'input_border': '#CFC6AE',
    'input_border_hover': '#A89F86',
    'input_focus_border': _CLOTH,
    'input_placeholder': '#8A8168',

    # Disabled
    'disabled_bg': '#EAE3CF',
    'disabled_text': '#8F876F',
    'disabled_border': '#DDD4BA',

    # Scrollbars
    'scrollbar': '#CBBF9F',
    'scrollbar_hover': '#A89B78',
    'scrollbar_track': '#EDE5CF',

    # Tooltips
    'tooltip_bg': '#2B3A31',
    'tooltip_text': '#FBF6E8',
    'tooltip_border': '#3E5044',

    # Tables
    'table_header_bg': '#EFE6CC',
    'table_row_alt': '#F6F0DE',
    'table_row_hover': '#EFE7CF',
    'table_row_selected': '#E3E8D3',
    'table_border': '#E2D9C0',

    # Charts
    'chart_1': '#5E7F5A',
    'chart_2': '#7A4F63',
    'chart_3': '#B48A1F',
    'chart_4': '#4E6A7E',
    'chart_5': '#B5683F',
    'chart_6': '#8A7F68',
    'chart_grid': '#E2D9C0',
    'chart_axis': '#5E5848',

    # Typography (point sizes as Naturalist; the pixel sizes are below)
    'font_family': 'EB Garamond',
    'font_heading': 'Cormorant SC',
    # The main window's tab bar: cloth green, a 3 px mustard rule, cream text, a mustard beetle
    'header_bg': _CLOTH,
    'header_rule': _MUSTARD,
    'header_text': '#F4EDDA',
    'header_mark': _MUSTARD,
    'font_size_xs': 9,
    'font_size_sm': 10,
    'font_size_base': 11,
    'font_size_lg': 12,
    'font_size_xl': 14,
    'font_size_2xl': 16,
    'font_size_3xl': 20,
    'font_size_stat': 24,

    # Spacing / sizing (squarer corners, as a printed book)
    'radius_sm': '2px',
    'radius_md': '3px',
    'radius_lg': '4px',
    'radius_xl': '8px',

    'spacing_xs': '4px',
    'spacing_sm': '8px',
    'spacing_md': '12px',
    'spacing_lg': '16px',
    'spacing_xl': '24px',

    # Shadows (warm, faint)
    'shadow_sm': '0 1px 2px rgba(35, 48, 42, 0.06)',
    'shadow_md': '0 4px 6px rgba(35, 48, 42, 0.08)',
    'shadow_lg': '0 10px 15px rgba(35, 48, 42, 0.10)',
    'shadow_xl': '0 20px 25px rgba(35, 48, 42, 0.16)',

    # --- R21: colours that were written into views (Naturalist keeps the old values) ---
    'on_accent_text': '#FBF6E8',
    'on_accent_text_soft': 'rgba(251, 246, 232, 0.8)',
    'text_on_accent': '#FBF6E8',
    'text_on_success': '#FBF6E8',
    'text_on_error': '#FBF6E8',
    'stats_personal_accent': '#5E7F5A',
    'stats_personal_accent_light': '#E3EADB',
    'stats_personal_accent_dark': '#3F5A3D',
    'stats_all_accent': '#4E6A7E',
    'stats_all_accent_light': '#DFE6EA',
    'stats_all_accent_dark': '#36505F',
    'stats_commercial_accent': '#B48A1F',
    'stats_commercial_accent_light': '#F3E8C8',
    'stats_commercial_accent_dark': '#7E6015',
    'embargo_alert_bg': '#F6E7C4',
    'embargo_alert_border': '#C8A23A',
    'embargo_expired': '#8E3F1F',
    'embargo_released': '#4F6B3A',
    'scheme_selection_bg': '#EADDE3',
    'scheme_toolbar_hover': '#3E5566',
    'new_species_text': '#4F6B3A',
    'primary_hover_deep': '#243A2D',
    'button_primary_hover_dark': '#243A2D',
    'danger_hover_bg': '#F3E0D6',
    'danger_hover_overlay': 'rgba(142, 63, 31, 0.1)',
    'btn_disabled_bg': '#DDD5C0',
    'btn_disabled_text': '#6E6755',
    'btn_outline_disabled_text': '#9A927E',
    'btn_outline_disabled_border': '#CFC6AE',
    'collection_toolbar_hover': '#6E6553',
    'collection_profile_btn_hover': '#6E6553',
    'calendar_nav_text': '#23302A',
    'calendar_nav_bg': '#F1EAD3',
    'calendar_nav_hover': 'rgba(251, 246, 232, 0.18)',
    'collection_bar_border': '#E2D3A8',
    'radio_checked_bg': '#E3EADB',
    'checked_row_bg': '#E3EADB',
    'match_synonym': '#3F6578',
    'match_alias': '#7A4F63',
    'match_cf_resolved': '#A8741A',
    'match_aggregate': '#A8741A',
    'match_manual': '#A8741A',
    'table_selection_overlay': 'rgba(47, 74, 58, 0.25)',
    'staging_unmatched_species_bg': '#F0D9CC',
    # Splash: cloth green with mustard, like the header
    'splash_bg': '#1F3328',
    'splash_bg_mid': '#26392D',
    'splash_gradient_top': '#34503F',
    'splash_gradient_mid': '#2A4234',
    'splash_moss': '#C8A23A',
    'splash_moss_light': '#DDBB5A',
    'splash_moss_dim': '#9C7E2C',
    'splash_text_warm': '#DCD3BB',
    'splash_cream': '#F4EDDA',
    'splash_gold_dim': '#B89A5A',
    'splash_text_dim': '#9A927E',
    'splash_heather': '#B5683F',
    'splash_glow': '#0cC8A23A',
    'splash_border_inner': '#50C8A23A',
}

# Garamond runs small: caption, small and body are one pixel larger than Naturalist's (13 px is
# still the smallest text in the suite); every other named size is the same.
_BIGGER = {"caption", "small", "body"}
FORTIES_THEME.update({f"font_px_{_name}": _px + (1 if _name in _BIGGER else 0)
                      for _name, _px in TEXT_PX.items()})
