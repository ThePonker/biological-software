"""active_theme_dict() -- the colour dictionary of the theme this program draws in (R21).

ThemeManager and config.TabColors both read it, so they can never disagree. It follows
shared.theme_choice.active_name(): "1940s" only in a program that called
use_stored_theme_for_this_program() before this was first used, otherwise Naturalist.
"""
from .forties import FORTIES_THEME
from .naturalist import NATURALIST_THEME


def active_theme_name() -> str:
    from shared import theme_choice
    return "1940s" if theme_choice.active_name() == "1940s" else "Naturalist"


def active_theme_dict() -> dict:
    return FORTIES_THEME if active_theme_name() == "1940s" else NATURALIST_THEME
