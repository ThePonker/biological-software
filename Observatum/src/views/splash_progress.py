"""How far the splash screen's bar has got: startup as a fixed list of named steps.

Round 5 (11 Oct 2026). Wil: "even out the bar that shows loading and the animation".
Round 6: the bar covers only the steps before the window opens (startup_preload.py); the
rest finish in the background after it (background_loader.py).

Each step has a plain-words label and a typical duration. The bar gives each step a share
of its length in proportion to that duration, so it moves at an even pace in time rather
than jumping. Within a step it moves towards the step's end over the step's expected
duration; a step that runs long keeps creeping but never reaches the end; the shown value
eases towards that target (no jumps after a busy moment), never goes backwards, and is
100 only after finish().

The durations start from the measurements below and are then those of this computer: the
last startups' measured seconds are kept (QSettings "startup/step_seconds") and blended in.
No Qt here apart from QSettings in load/save, so it is easy to test.
"""

import json
import math
import time
from typing import Dict, List, Optional, Sequence, Tuple

# key, label shown under the bar, typical seconds (measured on the Linux test machine with
# the 10 Oct data copy, 11 Oct 2026; replaced by this computer's own figures after the first
# startup). Round 6: only the steps before the window opens; the rest load after it, in the
# background (background_loader.py), with their own line in the status bar.
STEPS: List[Tuple[str, str, float]] = [
    ("imports", "Loading the program…", 0.15),
    ("window", "Building the window…", 0.5),
    ("services", "Opening the databases…", 0.28),
    ("home", "Filling in the Home page…", 0.3),
    ("observations", "Loading your observation records…", 1.8),
    ("contributed", "Loading contributed records…", 0.25),
    ("collection", "Loading insect collection specimens…", 0.8),
]

SETTINGS_KEY = "startup/step_seconds"
EASE_S = 0.25          # how quickly the shown value catches up with the target (seconds)
IN_STEP = 0.92         # share of a step reached at its expected duration; the rest creeps


class ProgressPlan:
    """The bar's position (0-100) over a fixed list of steps."""

    def __init__(self, steps: Sequence[Tuple[str, str, float]] = STEPS,
                 seconds: Optional[Dict[str, float]] = None, clock=time.perf_counter):
        self._clock = clock
        self.keys = [k for k, _l, _s in steps]
        self.labels = {k: label for k, label, _s in steps}
        typical = {k: float(s) for k, _l, s in steps}
        for k, s in (seconds or {}).items():
            if k in typical and isinstance(s, (int, float)) and 0 < s < 600:
                typical[k] = float(s)
        self.expected = {k: max(0.05, typical[k]) for k in self.keys}
        total = sum(self.expected.values())
        # each step's span of the bar, 0..99 (the last 1% is finish())
        self.span: Dict[str, Tuple[float, float]] = {}
        at = 0.0
        for k in self.keys:
            width = 99.0 * self.expected[k] / total
            self.span[k] = (at, at + width)
            at += width
        self.current: Optional[str] = None
        self._started = 0.0
        self._shown = 0.0
        self._last_tick: Optional[float] = None
        self._floor = 0.0                         # the end of the last step finished
        self.done = False
        self.measured: Dict[str, float] = {}

    # ---- steps
    def begin(self, key: str) -> str:
        """Step `key` starts now (the one before it has ended). Returns its label."""
        now = self._clock()
        self._close_current(now)
        if key not in self.span:                  # an unknown step: keep the bar where it is
            self.current = None
            return ""
        self.current, self._started = key, now
        return self.labels[key]

    def finish(self):
        """Everything is loaded: the bar may now show 100."""
        self._close_current(self._clock())
        self.current = None
        self.done = True
        self._shown = 100.0

    def _close_current(self, now: float):
        if self.current is not None:
            self.measured[self.current] = round(now - self._started, 3)
            # a step that ended early still counts as reached
            self._floor = self.span[self.current][1]

    # ---- the value
    def target(self, now: Optional[float] = None) -> float:
        """Where the bar should be now (before easing)."""
        if self.done:
            return 100.0
        now = self._clock() if now is None else now
        floor = self._floor
        if self.current is None:
            return floor
        a, b = self.span[self.current]
        x = (now - self._started) / self.expected[self.current]
        if x <= 1.0:
            share = IN_STEP * x
        else:                                     # running long: creep, never reach b
            share = IN_STEP + (1.0 - IN_STEP) * (1.0 - math.exp(-(x - 1.0)))
        return max(floor, a + (b - a) * min(share, 0.995))

    def tick(self, now: Optional[float] = None) -> float:
        """The value to show now: eased towards target(), never backwards, < 100 until done."""
        now = self._clock() if now is None else now
        if self.done:
            self._shown = 100.0
            return 100.0
        goal = self.target(now)
        # a pause between ticks (a busy moment on the GUI thread) counts as one short tick,
        # so the bar then glides up to the target instead of jumping
        dt = 0.0 if self._last_tick is None else min(0.05, max(0.0, now - self._last_tick))
        self._last_tick = now
        step = (goal - self._shown) * min(1.0, dt / EASE_S) if dt else 0.0
        self._shown = min(99.5, max(self._shown, self._shown + step))
        return self._shown


# ---- this computer's step durations ---------------------------------------------

def load_seconds() -> Dict[str, float]:
    """The step durations kept from the last startups (empty when none)."""
    try:
        from PySide6.QtCore import QSettings
        raw = QSettings().value(SETTINGS_KEY, "")
        data = json.loads(raw) if raw else {}
        return {k: float(v) for k, v in data.items() if isinstance(v, (int, float))}
    except Exception:
        return {}


def save_seconds(measured: Dict[str, float], previous: Optional[Dict[str, float]] = None):
    """Keep this startup's durations, blended half and half with the ones kept before."""
    if not measured:
        return
    try:
        from PySide6.QtCore import QSettings
        prev = previous if previous is not None else load_seconds()
        blended = {k: round((prev[k] + v) / 2, 3) if k in prev else v for k, v in measured.items()}
        QSettings().setValue(SETTINGS_KEY, json.dumps(blended))
    except Exception as e:
        print(f"[startup] step durations not kept: {e}")
