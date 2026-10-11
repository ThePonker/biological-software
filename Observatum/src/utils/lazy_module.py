"""A module imported on first use, for heavy libraries the start-up does not need.

    pd = lazy_module("pandas")      # nothing imported yet
    pd.DataFrame(...)               # pandas is imported here, once

Used by the import wizards' validation workers: their pandas import (about 1.5 s) ran
whenever Observatum started, though it is only needed when an import is validated
(startup speed, 11 Oct 2026).
"""

import importlib


class _LazyModule:
    __slots__ = ("_name", "_module")

    def __init__(self, name: str):
        self._name = name
        self._module = None

    def __getattr__(self, attr):
        mod = self._module
        if mod is None:
            mod = self._module = importlib.import_module(self._name)
        return getattr(mod, attr)

    def __repr__(self):
        state = "loaded" if self._module is not None else "not loaded yet"
        return f"<lazy module {self._name!r} ({state})>"


def lazy_module(name: str) -> _LazyModule:
    """A stand-in for `import name` that imports it the first time an attribute is read."""
    return _LazyModule(name)
