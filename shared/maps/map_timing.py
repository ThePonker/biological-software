"""Timing hook for the Mapping tab's map: set BIOSOFT_MAP_TIMING=1 and each layer's build and
paint time (milliseconds) is printed to stdout, as are the whole background and cache hits.
Off (and free) otherwise. Display only."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager


def enabled() -> bool:
    return os.environ.get("BIOSOFT_MAP_TIMING") == "1"


@contextmanager
def timed(what: str, label: str):
    """Print "[map-timing] <what> <label> <ms> ms" after the block (nothing when off)."""
    if not enabled():
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        print(f"[map-timing] {what:6s} {label}: {(time.perf_counter() - t0) * 1000:.1f} ms",
              flush=True)


def note(what: str, label: str):
    if enabled():
        print(f"[map-timing] {what:6s} {label}", flush=True)
