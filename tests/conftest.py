"""pytest set-up for the suite's tests (backlog I6).

Puts the project root on sys.path (paths, shared, DataEntry, Examen, Observatum.src...)
and Observatum on it as well, for the modules that import `src.` themselves.
Tests here touch no database: they exercise pure functions only.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "Observatum")):
    if p not in sys.path:
        sys.path.insert(0, p)
