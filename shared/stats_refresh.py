"""When a statistics service cannot refresh (R4B, 24 Nov 2026).

Both stats services (observation, recording scheme) used to answer a failed refresh with an
empty cache that was marked valid, so every card showed zeros for the next five minutes and
nothing said why. Now: the last good figures are kept, the cache is marked invalid so the next
read tries again, the error is logged and kept in `service.last_error`, and the Stats tab
(StatsReportsTab.refresh) reports it through the status bar the main window already uses for
"Stats could not be refreshed".
"""
from __future__ import annotations

import logging


def refresh_failed(service, name: str, exc: Exception, last_good: dict) -> None:
    """Keep `last_good` as the service's figures, retry on the next read, remember why."""
    logging.getLogger(name).exception("Stats refresh failed")
    service._cache = last_good
    service._valid = False
    service.last_error = f"{name}: {exc}"


def refresh_ok(service) -> None:
    service.last_error = None


def pending_errors(*services) -> list:
    """The `last_error` of each service that could not refresh."""
    return [s.last_error for s in services if getattr(s, "last_error", None)]
