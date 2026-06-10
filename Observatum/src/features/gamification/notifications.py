"""
Gamification Notifications for Observatum V2.

Popup notification cards for newly earned achievements.
Dark Victorian theme.
"""

from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, Signal, QByteArray
from PySide6.QtGui import QColor
from PySide6.QtSvgWidgets import QSvgWidget

from .models import Achievement, AchievementType
from .renderer import AchievementRenderer
from .theme import BACKGROUND, TEXT, UI_SETTINGS


class NotificationCard(QFrame):
    """
    A single notification card for an achievement.
    """
    
    dismissed = Signal()
    view_clicked = Signal(object)
    
    def __init__(
        self,
        achievement: Achievement,
        renderer: AchievementRenderer,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.achievement = achievement
        self.renderer = renderer
        self._setup_ui()
        self._setup_timer()
    
    def _setup_ui(self):
        """Set up the notification card UI."""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {BACKGROUND['surface']};
                border: 1px solid {TEXT['accent']};
                border-radius: 8px;
            }}
        """)
        
        # Shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # Achievement icon
        icon_widget = QSvgWidget()
        icon_widget.setFixedSize(48, 60)
        svg_content = self._get_achievement_svg()
        if svg_content:
            icon_widget.renderer().load(QByteArray(svg_content.encode()))
        layout.addWidget(icon_widget)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title = QLabel(self.achievement.name)
        title.setStyleSheet(f"""
            font-family: Georgia, serif;
            font-size: 14px;
            font-weight: bold;
            color: {TEXT['accent']};
        """)
        text_layout.addWidget(title)
        
        description = QLabel(self.achievement.description)
        description.setStyleSheet(f"""
            font-family: Georgia, serif;
            font-size: 11px;
            color: {TEXT['secondary']};
        """)
        description.setWordWrap(True)
        text_layout.addWidget(description)
        
        layout.addLayout(text_layout, 1)
        
        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(4)
        
        view_btn = QPushButton("View")
        view_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #4a7c59;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-family: Georgia, serif;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #5a8c69;
            }}
        """)
        view_btn.clicked.connect(lambda: self.view_clicked.emit(self.achievement))
        button_layout.addWidget(view_btn)
        
        dismiss_btn = QPushButton("×")
        dismiss_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {TEXT['muted']};
                border: none;
                font-size: 18px;
                padding: 0;
            }}
            QPushButton:hover {{
                color: {TEXT['primary']};
            }}
        """)
        dismiss_btn.setFixedSize(24, 24)
        dismiss_btn.clicked.connect(self._dismiss)
        button_layout.addWidget(dismiss_btn, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(button_layout)
        
        self.setFixedWidth(350)
    
    def _get_achievement_svg(self) -> str:
        """Get SVG content for the achievement."""
        a_type = self.achievement.achievement_type
        
        if a_type == AchievementType.TIER:
            return self.renderer.render_shield(
                tier=getattr(self.achievement, 'tier_number', 1),
                stage=getattr(self.achievement, 'stage', 'beginner'),
                size="small"
            )
        elif a_type == AchievementType.VC_BADGE:
            return self.renderer.render_badge(
                vc_number=getattr(self.achievement, 'vc_number', 1),
                region=getattr(self.achievement, 'region', 'england'),
                size="small"
            )
        elif a_type == AchievementType.VC_COMPLETION:
            return self.renderer.render_crown(
                region=getattr(self.achievement, 'region', None),
                size="small"
            )
        elif a_type == AchievementType.FAMILY_FIRST:
            return self.renderer.render_ribbon(
                family=getattr(self.achievement, 'family_name', ''),
                taxonomic_group=getattr(self.achievement, 'taxonomic_group', 'other'),
                size="small"
            )
        elif a_type == AchievementType.FAMILY_DEPTH:
            return self.renderer.render_medal(
                trophy_tier=getattr(self.achievement, 'trophy_tier', 'bronze'),
                size="small"
            )
        elif a_type == AchievementType.RARE_SPECIES:
            return self.renderer.render_pin(
                rarity_tier=getattr(self.achievement, 'rarity_tier', 'uncommon'),
                size="small"
            )
        elif a_type == AchievementType.RARE_MILESTONE:
            return self.renderer.render_rosette(
                trophy_tier=getattr(self.achievement, 'trophy_tier', 'bronze'),
                size="small"
            )
        return ""
    
    def _setup_timer(self):
        """Set up auto-dismiss timer."""
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self._dismiss)
        self.dismiss_timer.start(UI_SETTINGS["notification_timeout_ms"])
    
    def _dismiss(self):
        """Dismiss the notification."""
        self.dismiss_timer.stop()
        self.dismissed.emit()
    
    def enterEvent(self, event):
        """Pause timer when mouse enters."""
        self.dismiss_timer.stop()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Restart timer when mouse leaves."""
        self.dismiss_timer.start(UI_SETTINGS["notification_timeout_ms"])
        super().leaveEvent(event)


class NotificationStack(QWidget):
    """
    A stack of notification cards.
    Shows multiple achievements, dismissing one by one.
    """
    
    view_achievement = Signal(object)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.renderer = AchievementRenderer()
        self.notifications: List[NotificationCard] = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the notification stack UI."""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
    
    def add_notification(self, achievement: Achievement):
        """Add a new notification to the stack."""
        card = NotificationCard(achievement, self.renderer, self)
        card.dismissed.connect(lambda: self._remove_notification(card))
        card.view_clicked.connect(self._on_view_clicked)
        
        self.notifications.append(card)
        self.layout.addWidget(card)
        
        self.adjustSize()
        self.show()
    
    def add_notifications(self, achievements: List[Achievement]):
        """Add multiple notifications."""
        for achievement in achievements:
            self.add_notification(achievement)
    
    def _remove_notification(self, card: NotificationCard):
        """Remove a notification from the stack."""
        if card in self.notifications:
            self.notifications.remove(card)
            self.layout.removeWidget(card)
            card.deleteLater()
        
        if not self.notifications:
            self.hide()
        else:
            self.adjustSize()
    
    def _on_view_clicked(self, achievement: Achievement):
        """Handle view button click."""
        self.view_achievement.emit(achievement)
    
    def clear_all(self):
        """Clear all notifications."""
        for card in self.notifications[:]:
            self._remove_notification(card)
