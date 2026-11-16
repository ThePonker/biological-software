"""One theme look-up for the suite's apps (R13, 24 Oct 2026).

value(key, fallback) returns Observatum's Naturalist theme value for `key`; the fallback is
used only if Observatum's theme cannot be imported, the look-up fails, or the key is
missing (theme() answers "#ff00ff" for a missing key, which is never returned).
Observatum is put on sys.path if the launcher did not.
"""
import sys
from pathlib import Path

try:
    from src.themes import theme as _theme
except Exception:                                    # launched without Observatum on the path
    try:
        import paths
        _obs_dir = paths.OBSERVATUM_DIR
    except ImportError:
        _obs_dir = Path(__file__).resolve().parent.parent / "Observatum"
    if str(_obs_dir) not in sys.path:
        sys.path.insert(0, str(_obs_dir))
    try:
        from src.themes import theme as _theme
    except Exception:                                # any failure: the fallbacks are used
        _theme = None


def value(key, fallback):
    """A theme value; the fallback is only used if Observatum's theme cannot be imported."""
    if _theme is not None:
        try:
            v = _theme().get(key)
            if v and v != "#ff00ff":
                return v
        except Exception:
            pass
    return fallback


def naturalist_value(key, fallback):
    """The NATURALIST theme's value for `key`, whatever theme the program is drawing in (R21):
    for drawing that must not change with the theme, such as the maps. The fallback is used only
    if the Naturalist theme cannot be imported or lacks the key."""
    try:
        from src.themes.naturalist import NATURALIST_THEME
        v = NATURALIST_THEME.get(key)
        if v:
            return v
    except Exception:
        pass
    return fallback
