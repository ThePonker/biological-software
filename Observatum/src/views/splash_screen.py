"""
Splash Screen for Observatum V2.

Shows loading progress while application initializes.
Victorian naturalist aesthetic with ornamental details and smooth progress.
Five nature silhouettes (bird, mushroom, beetle, acorn, bat) light up
progressively from moss green to heather purple as modules load.

Round 5 (11 Oct 2026): the bar follows the named startup steps (splash_progress.py) and is
animated by a timer, so it glides at an even pace while records load in background threads
(startup_preload.py); the label says what is being loaded, in plain words.
"""

from pathlib import Path

from PySide6.QtWidgets import QSplashScreen, QProgressBar, QLabel, QApplication
from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QPixmap, QColor, QPainter, QFont, QLinearGradient,
    QPen, QPainterPath, QImage
)


class ObservatumSplashScreen(QSplashScreen):
    """Victorian naturalist-themed splash screen with ornamental progress."""

    # Palette
    BG_DARK = "#1c1c1e"
    BG_MID = "#252527"
    MOSS = "#4a7c59"
    MOSS_LIGHT = "#5a9a6e"
    MOSS_DIM = "#3a6248"
    WARM_GRAY = "#8b8178"
    CREAM = "#d4cdc4"
    GOLD_DIM = "#8a7a5a"
    TEXT_DIM = "#5a5650"
    HEATHER = "#8e6cb8"

    WIDTH = 580
    HEIGHT = 400

    # Silhouette thresholds — each lights up at this progress %
    SIL_THRESHOLDS = [0, 20, 40, 60, 80]

    def __init__(self):
        pixmap = QPixmap(self.WIDTH, self.HEIGHT)
        pixmap.fill(QColor(self.BG_DARK))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_background(painter)
        self._draw_ornaments(painter)
        self._draw_text(painter)
        painter.end()

        self._bg_pixmap = pixmap
        self._progress_value = 0

        # Load silhouettes
        self._silhouette_img = None
        self._sil_sections = []
        self._load_silhouettes()

        super().__init__(pixmap)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

        self._setup_progress_bar()
        self._setup_status_label()

        # Round 5: the bar is driven by a ProgressPlan and this timer (start_plan)
        self._plan = None
        self.cancel_requested = False     # the splash was closed while loading
        self._anim = QTimer(self)
        self._anim.setInterval(16)
        self._anim.timeout.connect(self._on_tick)

    # ── Silhouette Loading ───────────────────────────────

    def _load_silhouettes(self):
        """Load and split silhouette image into 5 sections."""
        img_path = Path(__file__).parent / "assets" / "silhouettes.png"
        if not img_path.exists():
            return

        source = QImage(str(img_path))
        if source.isNull():
            return

        self._silhouette_img = source

        # Split into 5 equal sections, scaled once to the size they are drawn at (the bar's
        # animation repaints often: scaling every paint was the slow part)
        section_w = source.width() // 5
        target_h = 80
        for i in range(5):
            x = i * section_w
            w = section_w if i < 4 else source.width() - x
            section = source.copy(x, 0, w, source.height())
            scale = target_h / max(1, section.height())
            section = section.scaled(
                max(1, int(section_w * scale)), target_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self._sil_sections.append(section)

    def _tint_section(self, section: QImage, color: QColor, opacity: float) -> QImage:
        """Create a tinted copy of a silhouette section."""
        tinted = QImage(section.size(), QImage.Format.Format_ARGB32_Premultiplied)
        tinted.fill(QColor(0, 0, 0, 0))

        p = QPainter(tinted)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the original silhouette
        p.drawImage(0, 0, section)

        # Tint: paint color over only the opaque pixels
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        tint_color = QColor(color)
        tint_color.setAlphaF(opacity)
        p.fillRect(tinted.rect(), tint_color)

        p.end()
        return tinted

    @staticmethod
    def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
        """Linearly interpolate between two colours."""
        t = max(0.0, min(1.0, t))
        return QColor(
            int(c1.red() + (c2.red() - c1.red()) * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue() + (c2.blue() - c1.blue()) * t),
        )

    # ── Paint Event ──────────────────────────────────────

    def paintEvent(self, event):
        """Override to draw animated silhouettes on top of static background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw static background
        painter.drawPixmap(0, 0, self._bg_pixmap)

        # Draw animated silhouettes
        if self._sil_sections:
            self._draw_silhouettes(painter)

        painter.end()

    def _draw_silhouettes(self, p: QPainter):
        """Draw the 5 silhouettes with progressive green→purple tinting."""
        if not self._sil_sections:
            return

        # Layout: centred between decorative rule (y=148) and progress bar (y=220)
        # (the sections are already scaled to their drawn size: _load_silhouettes)
        section_w_draw = self._sil_sections[0].width()
        total_w = section_w_draw * 5
        start_x = (self.WIDTH - total_w) // 2
        start_y = 165  # below the decorative rule

        progress = self._progress_value
        moss = QColor(self.MOSS_LIGHT)
        heather = QColor(self.HEATHER)

        for i, section in enumerate(self._sil_sections):
            threshold = self.SIL_THRESHOLDS[i]
            x = start_x + i * section_w_draw

            if progress >= threshold:
                # Lit — colour shifts from green to purple based on overall progress
                colour_t = progress / 100.0
                colour = self._lerp_color(moss, heather, colour_t)
                # Fade in smoothly over 10% after threshold
                fade = min(1.0, (progress - threshold) / 15.0)
                opacity = 0.3 + 0.7 * fade  # from 30% to 100%
            else:
                # Unlit — very dim
                colour = QColor(self.TEXT_DIM)
                opacity = 0.08

            p.drawImage(x, start_y, self._tint_section(section, colour, opacity))

    # ── Drawing ──────────────────────────────────────────

    def _draw_background(self, p: QPainter):
        """Subtle radial-ish gradient background."""
        w, h = self.WIDTH, self.HEIGHT

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#2a2a2c"))
        grad.setColorAt(0.4, QColor("#222224"))
        grad.setColorAt(1.0, QColor(self.BG_DARK))
        p.fillRect(0, 0, w, h, grad)

        centre_grad = QLinearGradient(w / 2, h * 0.3, w / 2, h)
        centre_grad.setColorAt(0.0, QColor(74, 124, 89, 12))
        centre_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, h, centre_grad)

    def _draw_ornaments(self, p: QPainter):
        """Victorian-style decorative border and rule lines."""
        w, h = self.WIDTH, self.HEIGHT
        m = 8

        pen = QPen(QColor(self.MOSS_DIM))
        pen.setWidthF(1.0)
        p.setPen(pen)
        p.drawRect(m, m, w - 2 * m, h - 2 * m)

        pen.setColor(QColor(74, 124, 89, 80))
        pen.setWidthF(0.5)
        p.setPen(pen)
        inner = m + 4
        p.drawRect(inner, inner, w - 2 * inner, h - 2 * inner)

        corner_size = 6
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.MOSS_DIM))
        for cx, cy in [
            (m, m), (w - m - corner_size, m),
            (m, h - m - corner_size), (w - m - corner_size, h - m - corner_size)
        ]:
            p.drawRect(cx, cy, corner_size, corner_size)

        rule_y = 155
        rule_margin = 60
        pen.setColor(QColor(self.MOSS_DIM))
        pen.setWidthF(0.8)
        p.setPen(pen)
        p.drawLine(rule_margin, rule_y, w // 2 - 30, rule_y)
        p.drawLine(w // 2 + 30, rule_y, w - rule_margin, rule_y)

        cx, cy = w // 2, rule_y
        diamond = QPainterPath()
        diamond.moveTo(cx, cy - 4)
        diamond.lineTo(cx + 4, cy)
        diamond.lineTo(cx, cy + 4)
        diamond.lineTo(cx - 4, cy)
        diamond.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self.MOSS))
        p.drawPath(diamond)

    def _draw_text(self, p: QPainter):
        """Draw title, subtitle, and version text."""
        w = self.WIDTH
        rect = QRectF(0, 0, w, self.HEIGHT)

        title_font = QFont("Georgia", 30, QFont.Weight.Bold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        p.setFont(title_font)
        p.setPen(QColor(self.MOSS_LIGHT))
        p.drawText(
            rect.adjusted(0, 48, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "OBSERVATUM"
        )

        sub_font = QFont("Georgia", 11)
        sub_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        p.setFont(sub_font)
        p.setPen(QColor(self.WARM_GRAY))
        p.drawText(
            rect.adjusted(0, 100, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Biological Recording System"
        )

        tag_font = QFont("Georgia", 8)
        tag_font.setItalic(True)
        tag_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(tag_font)
        p.setPen(QColor(self.TEXT_DIM))
        p.drawText(
            rect.adjusted(0, 128, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "Recording the natural world, one observation at a time"
        )

        ver_font = QFont("Segoe UI", 7)
        ver_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        p.setFont(ver_font)
        p.setPen(QColor(self.TEXT_DIM))
        p.drawText(
            rect.adjusted(0, 0, -18, -14),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom,
            "v2.0"
        )

    # ── Progress & Status ────────────────────────────────

    def _setup_progress_bar(self):
        """Custom-styled thin progress bar."""
        self._progress = QProgressBar(self)
        bar_margin = 40
        bar_y = 310
        bar_w = self.WIDTH - 2 * bar_margin
        self._progress.setGeometry(bar_margin, bar_y, bar_w, 6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 1000)          # tenths of a per cent: a smooth glide
        self._progress.setValue(0)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 3px;
                background-color: {self.BG_DARK};
            }}
            QProgressBar::chunk {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {self.MOSS_DIM},
                    stop:1 {self.MOSS_LIGHT}
                );
                border-radius: 3px;
            }}
        """)

    def _setup_status_label(self):
        """Status text below progress bar."""
        self._status = QLabel("Initializing...", self)
        self._status.setGeometry(40, 324, self.WIDTH - 80, 20)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"""
            color: {self.WARM_GRAY};
            font-family: 'Segoe UI';
            font-size: 9px;
            letter-spacing: 0.5px;
        """)

    # ── Public API ───────────────────────────────────────

    def set_progress(self, value: int, status: str = ""):
        """Update progress bar and status message. While a ProgressPlan drives the bar
        (start_plan) only the message is used: the plan's bar never goes backwards."""
        if self._plan is None:
            self._show_value(float(value))
        if status:
            self._status.setText(status)
        self.repaint()
        QApplication.processEvents()

    # ── Round 5: the bar follows the startup steps ──────

    def start_plan(self, plan):
        """Drive the bar from `plan` (splash_progress.ProgressPlan) on a timer."""
        self._plan = plan
        self._on_tick()
        self._anim.start()

    def begin_step(self, key: str):
        """Startup step `key` begins: its label goes under the bar."""
        if self._plan is None:
            return
        label = self._plan.begin(key)
        if label:
            self._status.setText(label)
        self.pump()

    def finish_progress(self, status: str = "Ready"):
        """Everything is loaded: the bar fills (only now) and the timer stops."""
        if self._plan is not None:
            self._plan.finish()
        self._anim.stop()
        self._show_value(100.0)
        self._status.setText(status)
        self.repaint()
        QApplication.processEvents()

    def progress_value(self) -> float:
        """The value the bar shows, 0-100."""
        return self._progress_value

    def pump(self):
        """Let the splash repaint (and its timer move the bar) between pieces of work."""
        QApplication.processEvents()

    def _on_tick(self):
        if self._plan is not None:
            self._show_value(self._plan.tick())

    def _show_value(self, value: float):
        value = max(0.0, min(100.0, value))
        self._progress.setValue(int(round(value * 10)))
        # the silhouettes change slowly: repaint them only when they would look different
        if abs(value - self._progress_value) >= 0.25 or value >= 100.0:
            self._progress_value = value
            self.update()

    def closeEvent(self, event):
        """Closing the splash screen while loading: startup stops cleanly (startup_preload
        checks cancel_requested between steps and while it waits for a thread)."""
        if self._plan is not None and not self._plan.done:
            self.cancel_requested = True
        self._anim.stop()
        super().closeEvent(event)

    def finish_with_delay(self, window, delay_ms: int = 500):
        """Finish splash with a small delay for smoothness."""
        self.set_progress(100, "Ready!")
        QTimer.singleShot(delay_ms, lambda: self.finish(window))
