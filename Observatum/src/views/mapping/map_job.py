"""Making the map without freezing the window (R16, 10 Nov 2026).

Generate used to read the records and build the squares on the GUI thread: 0.4-1 s warm and 2-4 s
cold for the 76k scheme records, with the window stuck meanwhile. Now `_generate_map` checks the
inputs on the GUI thread (dates, sources: the same messages as before), then ONE worker thread runs
map_selection.fetch and squares_for and the GUI thread picks the result up when it is done
(a 15 ms poll, the pattern of shared/maps/map_warmup.py and views/background_loader.py).

- Python's cyclic garbage collector is switched off while the worker runs (shared/gc_pause.py, as
  views/background_loader.py does while it loads): a collection run on the worker thread can
  finalise a Qt wrapper made on the GUI thread, which crashed the interpreter in a test.
- Nothing Qt is touched in the worker, and every SQLite connection fetch uses is opened inside
  it (fetch opens and closes its own, as do the taxon context and the counting switches).
- While it runs: the map's corner says "Making map...", Generate is greyed out, and another
  request with the same inputs (a second press) is ignored.
- A request with DIFFERENT inputs while it runs (a taxon added, a data source or the grid
  changed ...) marks the running one stale: its result is thrown away and the map is made again
  from the new inputs. Clear all / removing the last taxon also discards it, and makes nothing.
Display only (reads the databases, writes nothing).
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtCore import QTimer

from shared import gc_pause
from ...services import map_selection
from ...services import map_square_service as squares_svc
from .map_notes import hold_tetrads

POLL_MS = 15
MAKING = "Making map…"


@dataclass
class MapRequest:
    """Everything the worker needs, copied on the GUI thread (equal requests are one request)."""
    selection: list
    sources: list
    filters: Any
    size: int
    tetrads: bool
    bands: Any


@dataclass
class MapData:
    """What the worker made: the fetch result and the squares built from it."""
    result: Any
    tetrads_held: int
    squares: dict
    coarse: Any
    unparsed: Any
    timing: tuple                       # (fetch seconds, squares seconds)


def make_map_data(req: MapRequest) -> MapData:
    """The compute half of the old _generate_map. Runs in the worker thread: no Qt, no widgets."""
    t0 = time.perf_counter()
    result = map_selection.fetch(req.selection, req.sources, req.filters)
    t1 = time.perf_counter()
    mappable, held = hold_tetrads(result.records, req.tetrads)          # decision 10
    squares, coarse, unparsed = squares_svc.squares_for(
        mappable, req.size, lambda y: squares_svc.year_to_band(y, req.bands))
    return MapData(result, held, squares, coarse, unparsed, (t1 - t0, time.perf_counter() - t1))


class _Job:
    def __init__(self, req: MapRequest):
        self.req = req
        self.stale = False              # a different request came in, or the map was cleared
        self.rerun = False              # ... and the map is to be made again when this one ends
        self.data: Optional[MapData] = None
        self.error: Optional[BaseException] = None
        self.thread = threading.Thread(target=self._run, name="mapping-generate", daemon=True)

    def _run(self):
        try:
            self.data = make_map_data(self.req)
        except BaseException as e:      # reported on the GUI thread
            traceback.print_exc()
            self.error = e

    def alive(self) -> bool:
        return self.thread.is_alive()


class MapJobMixin:
    """For MappingTab: uses its map_widget, filter_panel and _apply_map(req, data)."""

    def _init_job(self):
        self._job: Optional[_Job] = None
        self._job_timer = QTimer(self)
        self._job_timer.setInterval(POLL_MS)
        self._job_timer.timeout.connect(self._job_poll)

    def map_running(self) -> bool:
        return self._job is not None

    def _job_request(self, req: MapRequest):
        """Start making the map, or, when one is being made, ignore a repeat of the same request
        and make the running one stale if the request differs."""
        job = self._job
        if job is not None:
            if req != job.req:
                job.stale = job.rerun = True
            return
        self._job = job = _Job(req)
        gc_pause.acquire()
        self.filter_panel.generate_btn.setEnabled(False)
        self.map_widget.set_message(MAKING)
        job.thread.start()
        self._job_timer.start()

    def _job_discard(self):
        """The map was cleared: whatever is being made is no longer wanted (and nothing is remade)."""
        if self._job is not None:
            self._job.stale, self._job.rerun = True, False

    def _job_poll(self):
        job = self._job
        if job is None or job.alive():
            return
        self._job_timer.stop()
        self._job = None
        gc_pause.release()
        self.filter_panel.generate_btn.setEnabled(not self.filter_panel.dates_reversed())
        if job.stale:
            if job.rerun:
                self._generate_map()                    # the inputs as they are now
            return
        if job.error is not None:
            self.map_widget.set_message(f"Map not made. {job.error}")
            return
        self._apply_map(job.req, job.data)

    def wait_for_map(self, timeout_s: float = 60.0) -> bool:
        """Block until no map is being made (tests and scripts); True when it finished."""
        end = time.monotonic() + timeout_s
        while self._job is not None and time.monotonic() < end:
            self._job_poll()
            time.sleep(0.002)
        return self._job is None
