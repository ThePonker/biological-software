"""How see-through an Environment polygon layer is drawn (25 Oct 2026): the Layers window's
opacity slider, 0-100 %, remembered per layer (QSettings "mapping/layer_opacity/<key>"). Until
one is chosen the layer keeps the alpha of its style (env_registry.py), as before. Display only."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import QSettings

from shared.maps import env_registry as env
from shared.maps import layers

OPACITY_SETTING = "mapping/layer_opacity/{}"


def has_opacity(key: str) -> bool:
    """True for an Environment polygon layer (the base layers keep their own look)."""
    e = env.ENV_BY_KEY.get(key)
    return e is not None and e.kind == "polygon"


def default_opacity(key: str) -> int:
    """The style's own alpha as a percentage."""
    return round(layers.env_style(key)[0].alpha() * 100 / 255)


_SAVED: Optional[Dict[str, Optional[int]]] = None      # layer key -> remembered percentage, read once


def _cache() -> Dict[str, Optional[int]]:
    """Every layer's remembered opacity, read from QSettings once and kept current by the setters
    (a paint never reads QSettings; 25 Oct 2026)."""
    global _SAVED
    if _SAVED is None:
        out: Dict[str, Optional[int]] = {}
        try:
            s = QSettings()
            for e in env.ENV_LAYERS:
                try:
                    v = s.value(OPACITY_SETTING.format(e.key), None)
                    out[e.key] = None if v in (None, "") else max(0, min(100, int(float(v))))
                except Exception:
                    out[e.key] = None
        except Exception:
            pass
        _SAVED = out
    return _SAVED


def reload_settings() -> None:
    """Forget the in-memory opacities: the next use reads QSettings again."""
    global _SAVED
    _SAVED = None


def saved_opacity(key: str) -> Optional[int]:
    return _cache().get(key)


def opacity(key: str) -> int:
    """The percentage in force: the remembered one, else the default."""
    v = saved_opacity(key)
    return default_opacity(key) if v is None else v


def alpha(key: str) -> int:
    """The same as 0-255."""
    return round(opacity(key) * 255 / 100)


def set_opacity(key: str, pct) -> None:
    """Remember a layer's opacity; None forgets it."""
    _cache()[key] = None if pct is None else int(max(0, min(100, pct)))
    try:
        s = QSettings()
        if pct is None:
            s.remove(OPACITY_SETTING.format(key))
        else:
            s.setValue(OPACITY_SETTING.format(key), int(max(0, min(100, pct))))
    except Exception as e:
        print(f"[map layers] opacity {key} not saved: {e}")


def reset_opacities() -> None:
    for e in env.ENV_LAYERS:
        set_opacity(e.key, None)


def saved_opacities() -> Tuple[Optional[int], ...]:
    """Every layer's remembered opacity, in registry order: a cheap 'have they changed' key."""
    cache = _cache()
    return tuple(cache.get(e.key) for e in env.ENV_LAYERS)
