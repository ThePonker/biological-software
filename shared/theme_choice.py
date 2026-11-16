"""theme_choice -- which look (theme) the suite's programs use (R21, 16 Nov 2026).

Naturalist (the original) or 1940s (a post-war natural-history-book look). The choice is stored
once, in the suite's settings store (shared/settings_store.app_settings(), key KEY), and is read
when a program starts, so a change takes effect the next time the program is opened.

Only Observatum and Data Entry follow the choice. Each calls, FIRST, before anything imports
Observatum's src.themes or src.core.config:

    from shared import theme_choice
    theme_choice.use_stored_theme_for_this_program()

Every other program (Examen, Curator, Munia, Codex, Lector, Atrium) never makes that call, so
active_name() stays "Naturalist" for them.
"""
from __future__ import annotations

KEY = "display/theme"
NAMES = ("Naturalist", "1940s")
DEFAULT = "Naturalist"

_active = DEFAULT


def load_name() -> str:
    """The stored theme name (Naturalist if unset, unreadable or not one of NAMES)."""
    try:
        from shared.settings_store import app_settings
        value = str(app_settings().value(KEY, DEFAULT))
    except Exception:
        return DEFAULT
    return value if value in NAMES else DEFAULT


def save_name(name: str) -> None:
    """Store the choice for Observatum and Data Entry (the next time each starts)."""
    from shared.settings_store import app_settings
    s = app_settings()
    s.setValue(KEY, name if name in NAMES else DEFAULT)
    s.sync()


def use_stored_theme_for_this_program() -> str:
    """Make this program follow the stored choice; returns the name now active."""
    global _active
    _active = load_name()
    return _active


def active_name() -> str:
    """The theme this program draws in: the stored one after use_stored_theme_for_this_program(),
    otherwise always Naturalist."""
    return _active
