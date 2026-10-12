"""MainWindow's part in startup Round 6 ("window early, rest behind", 11 Oct 2026).

- How Stats/Reports, Mapping and Settings are built: as generators of short slices
  (LazyTabPage.build_steps), so the background loader can build them without freezing the
  window; all at once (LazyTabPage.ensure_built) when needed this moment.
- start_background(): after the window has opened, the Recording Scheme records, Stats/
  Reports, Mapping, Settings and the species search finish loading in the background
  (background_loader.py, background_steps.py), with a "Still loading: …" line in the status
  bar that goes when everything is ready.
- A tab clicked before it is ready shows "Finishing loading…" with a busy cursor, is moved
  to the front of the queue and shows its contents the moment it is ready.
- Links into a tab that is not ready yet (Stats > View N scheme records, county first
  records, ...) open the tab at once and act when it is ready (waits_for).
- stop_background() (closing the window) stops everything cleanly.
"""

import functools
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ..models.database import get_database


def waits_for(key: str):
    """Decorator for a MainWindow method that needs background step `key`'s tab ready: if it
    is not, its tab is shown at once ("Finishing loading…") and the method runs when ready."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(self, *a, **k):
            bg = getattr(self, "_bg", None)
            if bg is not None and bg.is_pending(key):
                page = self._background_page(key)
                if page is not None:
                    self.tabs.setCurrentWidget(page)
                bg.when_done(key, lambda: fn(self, *a, **k))
                return None
            return fn(self, *a, **k)
        return wrapper
    return deco


class BackgroundTabsMixin:
    """Mixed into MainWindow (main_window.py); see the module's notes."""

    _bg = None
    _busy_cursor = False
    settings_generation = 0          # +1 on every Settings / species-counting change

    # ── the tabs built a piece at a time ────────────────────────────

    def _stats_tab_parts(self):
        from .stats import StatsReportsTab
        yield
        tab = StatsReportsTab(build=False)
        for _ in (getattr(tab, "build_parts", None) or (lambda: iter(())))():
            yield
        self.stats_reports_tab = tab
        self._connect_stats_signals()
        yield
        for part in (tab.theme_parts() if hasattr(tab, "theme_parts") else [tab]):
            self._theme_tab(part)
            yield
        return tab

    def _mapping_tab_parts(self):
        from .mapping import MappingTab
        yield
        lists = getattr(self, "_map_lists", None)
        if lists:                    # read in a thread by the background step
            from .background_steps import prefetched_map_lists
            with prefetched_map_lists(lists):
                tab = MappingTab()
        else:
            tab = MappingTab()
        yield
        self.mapping_tab = tab
        self._theme_tab(tab)
        yield
        return tab

    def _settings_tab_parts(self):
        from .settings import SettingsTab
        yield
        import inspect
        if "build" in inspect.signature(SettingsTab).parameters:
            tab = SettingsTab(db_manager=get_database(), build=False)
            for _ in tab.build_parts():      # a panel at a time (R8)
                yield
        else:
            tab = SettingsTab(db_manager=get_database())
        yield
        tab.settings_changed.connect(self._on_settings_changed)
        self._theme_tab(tab)
        yield
        try:
            tab.initialize()            # database paths and figures
        except Exception as e:
            print(f"Warning: Could not initialize Settings tab: {e}")
        self.settings_tab = tab
        return tab

    def ensure_tab(self, name: str):
        """The tab called `name` ('stats_reports_tab', 'mapping_tab', 'settings_tab' or any
        tab built at startup), building it now if it is not built yet."""
        page = {'stats_reports_tab': getattr(self, '_stats_page', None),
                'mapping_tab': getattr(self, '_mapping_page', None),
                'settings_tab': getattr(self, '_settings_page', None)}.get(name)
        if page is not None:
            page.ensure_built()
        return getattr(self, name, None)

    def _theme_tab(self, tab):
        if hasattr(tab, 'apply_theme'):
            try:
                tab.apply_theme()
            except Exception as e:
                print(f"Warning: Could not apply theme to {tab.__class__.__name__}: {e}")

    # ── the background phase ────────────────────────────────────────

    def start_background(self, timing=None, steps=None):
        """Start finishing the remaining tabs in the background (call once the window is
        shown). `steps`: for tests; normally background_steps.background_steps(self)."""
        from .background_loader import BackgroundLoader
        from .background_steps import STEP_PAGES, background_steps, start_scheme_read
        if self._bg is not None:
            return self._bg
        steps = background_steps(self) if steps is None else steps
        keys = {s.key for s in steps}
        for key, attr in STEP_PAGES.items():
            page = getattr(self, attr, None)
            if key in keys and hasattr(page, "deferred"):
                page.deferred = True             # shows "Finishing loading…" until built
        if "scheme" in keys:
            self._cover_scheme_tab()
            try:
                start_scheme_read(self)          # its own worker thread, from now
            except Exception as e:
                print(f"[startup] Recording Scheme records not started: {e}")
        self._bg = BackgroundLoader(steps, timing, self.statusBar(), self)
        self._bg.step_finished.connect(self._on_background_step_done)
        self._bg.finished.connect(self._end_busy_cursor)
        current = self._background_key_for(self.tabs.currentWidget())
        if current:
            self._bg.prioritise(current)
        self._bg.start()
        return self._bg

    def stop_background(self):
        """The window is closing: stop the background loading cleanly."""
        if self._bg is not None:
            self._bg.stop()
        self._end_busy_cursor()

    def _background_page(self, key: str):
        from .background_steps import STEP_PAGES
        attr = STEP_PAGES.get(key)
        return getattr(self, attr, None) if attr else None

    def _background_key_for(self, widget) -> Optional[str]:
        from .background_steps import STEP_PAGES
        if widget is None:
            return None
        for key, attr in STEP_PAGES.items():
            if getattr(self, attr, None) is widget:
                return key
        return None

    def _tab_pending_in_background(self, index: int) -> bool:
        """Tab `index` is still being loaded in the background: say so (its placeholder and a
        busy cursor), load it next and return True. False: carry on as usual."""
        key = self._background_key_for(self.tabs.widget(index))
        if key is None or self._bg is None or not self._bg.is_pending(key):
            self._end_busy_cursor()
            return False
        self._bg.prioritise(key)
        if not self._busy_cursor:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
            self._busy_cursor = True
        return True

    def _end_busy_cursor(self):
        if self._busy_cursor:
            self._busy_cursor = False
            QApplication.restoreOverrideCursor()

    def _on_background_step_done(self, key: str):
        page = self._background_page(key)
        if key == "scheme":
            self._uncover_scheme_tab()
        if page is None:
            return
        if hasattr(page, "deferred"):
            page.deferred = False                # a failed build: built on opening (R4)
        if page is self.tabs.currentWidget():
            self._end_busy_cursor()
            i = self.tabs.indexOf(page)
            if i not in self._initialized_tabs:  # failed: the first-opening path, now
                self._on_tab_changed(i)
        err = self._bg.error(key) if self._bg is not None else None
        if err is not None:
            self.statusBar().showMessage(
                f"{self._bg_label(key)} could not be loaded in the background ({err}); "
                "it will be loaded when its tab is opened.", 10000)

    @staticmethod
    def _bg_label(key: str) -> str:
        from .background_steps import LABELS
        return LABELS.get(key, key)

    # ── the Recording Scheme tab's "Finishing loading…" cover ──────

    def _cover_scheme_tab(self):
        from .lazy_tab import PENDING_TEXT
        from .pending_cover import PendingCover
        rs = self.recording_scheme_tab
        if getattr(rs, "_initialized", False):
            return
        self._scheme_cover = PendingCover(rs, PENDING_TEXT)

    def _uncover_scheme_tab(self):
        cover = getattr(self, "_scheme_cover", None)
        if cover is not None:
            cover.hide()
            cover.deleteLater()
            self._scheme_cover = None
