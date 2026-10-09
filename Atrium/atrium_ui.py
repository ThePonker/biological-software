"""Atrium - Suite Launcher UI

System tray icon with themed popup panel. Five main app buttons with
Flauna silhouette icons. Utility row for Codex Manager + Generate Workbook.
Always-on-top pin toggle. Draggable header.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QSystemTrayIcon, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QApplication,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon, QPixmap, QCursor, QColor, QPainter

from Atrium.process_manager import APPS, launch_app, is_running, running_count

ASSETS = Path(__file__).resolve().parent / "assets"

# Observatum naturalist palette
BG = "#faf9f7"
SURFACE = "#ffffff"
TEXT_PRIMARY = "#2c3e2d"
TEXT_SECONDARY = "#5a6b5c"
TEXT_MUTED = "#8b9a8d"
BORDER = "#d4cfc7"
SEPARATOR = "#e8e4de"
MOSS = "#4a7c59"
MOSS_LIGHT = "#e6f0ea"
HEATHER = "#7c6c9f"
HEATHER_LIGHT = "#f0edf5"
WARM_GRAY = "#8b8178"
GOLD = "#b8860b"
GOLD_LIGHT = "#fdf4e3"
CODEX_GREEN = "#2d5016"
CODEX_LIGHT = "#e8f0e2"


class AppButton(QFrame):
    """Main app launch button with silhouette icon, name, subtitle, status dot."""

    def __init__(self, app_def, parent=None):
        super().__init__(parent)
        self._app = app_def
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(f"""
            AppButton {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            AppButton:hover {{
                background: {app_def.colour_light};
                border-color: {app_def.colour};
            }}
        """)
        self.setFixedHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Icon
        icon_frame = QFrame()
        icon_frame.setFixedSize(42, 42)
        icon_frame.setStyleSheet(f"""
            border-radius: 10px;
            background: {app_def.colour_light};
            border: 1px solid {app_def.colour}40;
        """)
        icon_layout = QHBoxLayout(icon_frame)
        icon_layout.setContentsMargins(5, 5, 5, 5)
        icon_label = QLabel()
        icon_path = ASSETS / app_def.icon_file
        if icon_path.exists():
            pm = QPixmap(str(icon_path)).scaled(
                30, 30, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            # Tint icon to app colour
            tinted = QPixmap(pm.size())
            tinted.fill(Qt.GlobalColor.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, pm)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(tinted.rect(), QColor(app_def.colour))
            painter.end()
            icon_label.setPixmap(tinted)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("border: none; background: none;")
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_frame)

        # Name + subtitle
        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        name = QLabel(app_def.name)
        name.setFont(QFont("Georgia", 12, QFont.Weight.DemiBold))
        name.setStyleSheet(f"color: {TEXT_PRIMARY}; border: none;")
        text_col.addWidget(name)
        sub = QLabel(app_def.subtitle)
        sub.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; border: none;")
        text_col.addWidget(sub)
        layout.addLayout(text_col, 1)

        # Status dot
        self.status_dot = QFrame()
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setStyleSheet(
            f"border-radius: 4px; background: transparent; border: none;")
        layout.addWidget(self.status_dot)

    def update_status(self):
        running = is_running(self._app)
        colour = MOSS if running else "transparent"
        self.status_dot.setStyleSheet(
            f"border-radius: 4px; background: {colour}; border: none;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            launch_app(self._app)
            QTimer.singleShot(500, self.update_status)
        super().mousePressEvent(event)


class UtilityButton(QPushButton):
    """Small utility button for secondary actions."""

    def __init__(self, text, colour, parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFixedHeight(32)
        self.setStyleSheet(f"""
            QPushButton {{
                color: {colour};
                background: {SURFACE};
                border: 1px solid {colour}60;
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {colour}10;
                border-color: {colour};
            }}
        """)


class AtriumPanel(QWidget):
    """The popup panel that appears when clicking the tray icon."""

    def __init__(self):
        super().__init__()
        self._pinned = False
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(320)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame#panel {{
                background: {BG};
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
        """)
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ?? Header ??
        header = QFrame()
        header.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {MOSS}, stop:1 #3a6347);
            border-top-left-radius: 13px;
            border-top-right-radius: 13px;
        """)
        hl = QVBoxLayout(header)
        hl.setContentsMargins(16, 12, 16, 10)
        hl.setSpacing(2)

        # Top row: pin + close
        top_row = QHBoxLayout()
        self.pin_btn = QPushButton("\u25CB")
        self.pin_btn.setFixedSize(24, 24)
        self.pin_btn.setToolTip("Pin on top")
        self.pin_btn.setStyleSheet("""
            QPushButton {
                color: #a8c4ae;
                background: none;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover {
                color: white;
                background: rgba(255,255,255,0.15);
                border-radius: 12px;
            }
        """)
        self.pin_btn.clicked.connect(self._toggle_pin)
        top_row.addWidget(self.pin_btn)
        top_row.addStretch()

        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                color: #a8c4ae;
                background: none;
                border: none;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: white;
                background: rgba(255,255,255,0.15);
                border-radius: 12px;
            }}
        """)
        close_btn.clicked.connect(self.hide)
        top_row.addWidget(close_btn)
        hl.addLayout(top_row)

        # Title
        # Arch graphic
        arch = QLabel("\u2554\u2550\u2550\u2550\u2557")
        arch.setFont(QFont("Consolas", 11))
        arch.setStyleSheet("color: #a8c4ae; background: none; letter-spacing: 3px;")
        arch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(arch)

        title = QLabel("ATRIUM")
        title.setFont(QFont("Georgia", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #e8f0ea; background: none; letter-spacing: 4px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(title)

        subtitle = QLabel("Flauna Ecology")
        subtitle.setStyleSheet("color: #a8c4ae; font-size: 11px; background: none;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(subtitle)

        header.mousePressEvent = self._header_press
        header.mouseMoveEvent = self._header_move
        layout.addWidget(header)

        # ?? Main app buttons ??
        apps_container = QWidget()
        apps_container.setStyleSheet(f"background: {BG};")
        al = QVBoxLayout(apps_container)
        al.setContentsMargins(10, 10, 10, 6)
        al.setSpacing(5)

        # Section label
        section = QLabel("APPLICATIONS")
        section.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            border: none;
            padding-bottom: 2px;
        """)
        al.addWidget(section)

        # Only the 5 main apps (exclude Generate Tabella and Codex from main list)
        main_app_names = {"Observatum", "Curator", "Munia"}   # Tabella retired 2026-10-07
        self._buttons = []
        for app in APPS:
            if app.name in main_app_names:
                btn = AppButton(app)
                self._buttons.append(btn)
                al.addWidget(btn)

        layout.addWidget(apps_container)

        # ?? Utility row ??
        utility_container = QWidget()
        utility_container.setStyleSheet(f"""
            background: {BG};
            border-top: 1px solid {SEPARATOR};
        """)
        ul = QVBoxLayout(utility_container)
        ul.setContentsMargins(10, 8, 10, 6)
        ul.setSpacing(5)

        util_label = QLabel("TOOLS")
        util_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        util_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            border: none;
            padding-bottom: 2px;
        """)
        ul.addWidget(util_label)

        util_row = QHBoxLayout()
        util_row.setSpacing(6)
        util_row.addStretch()

        # Codex Manager button
        codex_btn = UtilityButton("Codex Manager", TEXT_PRIMARY)
        codex_btn.clicked.connect(self._on_codex)
        util_row.addWidget(codex_btn)


        util_row.addStretch()
        ul.addLayout(util_row)
        layout.addWidget(utility_container)

        # ?? Footer ??
        footer = QFrame()
        footer.setStyleSheet(f"""
            background: {BG};
            border-top: 1px solid {SEPARATOR};
            border-bottom-left-radius: 13px;
            border-bottom-right-radius: 13px;
        """)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 6, 14, 8)

        self.running_label = QLabel("")
        self.running_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        fl.addWidget(self.running_label)
        fl.addStretch()

        version = QLabel("v2.0")
        version.setStyleSheet(f"color: {BORDER}; font-size: 9px;")
        fl.addWidget(version)

        layout.addWidget(footer)
        outer.addWidget(frame)

    def _toggle_pin(self):
        self._pinned = not self._pinned
        pos = self.pos()
        if self._pinned:
            self.setWindowFlags(
                Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint)
            self.pin_btn.setText("\u25CF")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    color: white;
                    background: rgba(255,255,255,0.25);
                    border: none;
                    font-size: 14px;
                    border-radius: 12px;
                }
            """)
            self.pin_btn.setToolTip("Unpin")
        else:
            self.setWindowFlags(
                Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
            self.pin_btn.setText("\u25CB")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    color: #a8c4ae;
                    background: none;
                    border: none;
                    font-size: 14px;
                }
                QPushButton:hover {
                    color: white;
                    background: rgba(255,255,255,0.15);
                    border-radius: 12px;
                }
            """)
            self.pin_btn.setToolTip("Pin on top")
        self.move(pos)
        self.show()

    def refresh_status(self):
        for btn in self._buttons:
            btn.update_status()
        count = running_count()
        if count:
            self.running_label.setText(f"{count} running")
        else:
            self.running_label.setText("")

    def show_near_tray(self, tray_geometry):
        self.refresh_status()
        screen = QApplication.primaryScreen().availableGeometry()
        x = tray_geometry.x() + tray_geometry.width() // 2 - self.width() // 2
        y = tray_geometry.y() - self.height() - 8
        x = max(screen.left(), min(x, screen.right() - self.width()))
        y = max(screen.top(), min(y, screen.bottom() - self.height()))
        self.move(x, y)
        self.show()

    def _header_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def _header_move(self, event):
        if hasattr(self, "_drag_pos") and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _on_codex(self):
        for app in APPS:
            if app.name == "Codex":
                launch_app(app)
                QTimer.singleShot(500, self.refresh_status)
                return

    def _on_generate(self):
        from Atrium.process_manager import _run_generator
        _run_generator()


class AtriumApp:
    """System tray application."""

    def __init__(self):
        self._panel = AtriumPanel()

        icon_path = ASSETS / "tray_icon.png"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = QIcon()

        self._tray = QSystemTrayIcon(icon)
        self._tray.setToolTip("Atrium \u2014 Flauna Ecology")
        self._tray.activated.connect(self._on_tray_activated)

        menu = QMenu()
        menu.addAction("Show Atrium", self._show_panel)
        menu.addSeparator()
        menu.addAction("Quit", QApplication.quit)
        self._tray.setContextMenu(menu)
        self._tray.show()

        # Periodic status refresh
        self._timer = QTimer()
        self._timer.timeout.connect(self._panel.refresh_status)
        self._timer.start(3000)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._panel.isVisible():
                if not self._panel._pinned:
                    self._panel.hide()
            else:
                self._show_panel()

    def _show_panel(self):
        geo = self._tray.geometry()
        if geo.isValid() and geo.width() > 0:
            self._panel.show_near_tray(geo)
        else:
            cursor_pos = QCursor.pos()
            self._panel.move(cursor_pos.x() - 160, cursor_pos.y() - 450)
            self._panel.refresh_status()
            self._panel.show()
