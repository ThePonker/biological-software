"""Date pop-up calendars styled once for the whole application (F76, 13 Oct 2026).

Every QDateEdit with calendarPopup (Quick Entry's date, the When filter, Mark commercial,
the import wizard, Data Entry) opens a plain QCalendarWidget whose header came out white
on a pale band -- "October 2026" unreadable -- with plain arrows and red weekends.

install(app, colours) watches the application: whenever a QCalendarWidget is polished or
shown it is given, once, the suite's look (apply()):

  * the navigation band in the accent (Moss Green) with white month, year and arrows
    (chevrons drawn in the accent-text colour, cached as PNGs beside the tick marks);
  * day names on the pale band; days of other months faded;
  * Saturday and Sunday in the warning colour (amber), not red;
  * today in the accent, bold, on the pale accent band (a QCalendarWidget has no "outline"
    format: a text format carries colours and font only).

    from shared.calendar_style import install
    install(app, lambda: dict(accent=theme().get('primary'), ...))        # keys: COLOURS

colours: a function returning the colours (so a theme change is followed). A calendar that
sets its own look first calls apply() itself; install() then leaves it alone.
"""
from typing import Callable, Dict, Optional

from PySide6.QtCore import QDate, QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QTextCharFormat
from PySide6.QtWidgets import QApplication, QCalendarWidget

from shared.tick_mark import CACHE

COLOURS = ("surface", "surface_alt", "text_primary", "text_secondary", "text_muted", "border",
           "hover", "accent", "accent_text", "weekend", "today_bg")
_MARK = "_biosoft_calendar_styled"


def _chevron_image(colour, left: bool, size=16):
    """Path of a PNG arrow head (and an @2x copy) pointing left or right, in colour."""
    name = f"chevron_{'l' if left else 'r'}_{QColor(colour).name()[1:]}_{size}"
    path = CACHE / f"{name}.png"
    if not path.exists() or not (CACHE / f"{name}@2x.png").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        for p, s in ((path, size), (CACHE / f"{name}@2x.png", size * 2)):
            img = QImage(s, s, QImage.Format.Format_ARGB32)
            img.fill(Qt.GlobalColor.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(colour), 2.0 * s / 16)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            x0, x1 = (0.62 * s, 0.38 * s) if left else (0.38 * s, 0.62 * s)
            painter.drawPolyline([QPointF(x0, 0.25 * s), QPointF(x1, 0.5 * s), QPointF(x0, 0.75 * s)])
            painter.end()
            img.save(str(p), "PNG")
    return path.as_posix()


def calendar_qss(c: Dict[str, str]) -> str:
    """Style sheet for one QCalendarWidget from the colour dict (keys: COLOURS)."""
    return f"""
        QCalendarWidget {{ background-color: {c['surface']}; border: 1px solid {c['border']}; }}
        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: {c['accent']}; padding: 2px 4px; }}
        QCalendarWidget QToolButton {{
            color: {c['accent_text']}; background-color: transparent; border: none;
            border-radius: 3px; padding: 4px 8px; font-weight: 600; font-size: 13px; }}
        QCalendarWidget QToolButton:hover {{ background-color: rgba(255, 255, 255, 0.18); }}
        QCalendarWidget QToolButton::menu-indicator {{ image: none; }}
        QCalendarWidget QToolButton#qt_calendar_prevmonth {{
            qproperty-icon: url("{_chevron_image(c['accent_text'], True)}"); }}
        QCalendarWidget QToolButton#qt_calendar_nextmonth {{
            qproperty-icon: url("{_chevron_image(c['accent_text'], False)}"); }}
        QCalendarWidget QMenu {{ background-color: {c['surface']}; color: {c['text_primary']}; }}
        QCalendarWidget QMenu::item:selected {{
            background-color: {c['accent']}; color: {c['accent_text']}; }}
        QCalendarWidget QSpinBox {{
            color: {c['text_primary']}; background-color: {c['surface']}; font-weight: 600;
            border: 1px solid {c['border']}; border-radius: 3px; padding: 1px 4px;
            selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
        QCalendarWidget QAbstractItemView {{
            background-color: {c['surface']}; color: {c['text_primary']}; border: none;
            border-radius: 0; outline: none; font-size: 12px;
            selection-background-color: {c['accent']}; selection-color: {c['accent_text']}; }}
        QCalendarWidget QAbstractItemView:disabled {{ color: {c['text_muted']}; }}
        QCalendarWidget QAbstractItemView::item:hover {{ background-color: {c['hover']}; }}
    """


def apply(cal: QCalendarWidget, c: Dict[str, str]) -> None:
    """Give one calendar the suite's look: the style sheet plus the day formats."""
    cal.setStyleSheet(calendar_qss(c))
    cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    head = QTextCharFormat()
    head.setBackground(QBrush(QColor(c["surface_alt"])))
    head.setForeground(QBrush(QColor(c["text_secondary"])))
    head.setFontWeight(QFont.Weight.DemiBold)
    cal.setHeaderTextFormat(head)
    weekday = QTextCharFormat()
    weekday.setForeground(QBrush(QColor(c["text_primary"])))
    weekend = QTextCharFormat()
    weekend.setForeground(QBrush(QColor(c["weekend"])))
    for day in (Qt.DayOfWeek.Monday, Qt.DayOfWeek.Tuesday, Qt.DayOfWeek.Wednesday,
                Qt.DayOfWeek.Thursday, Qt.DayOfWeek.Friday):
        cal.setWeekdayTextFormat(day, weekday)
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        cal.setWeekdayTextFormat(day, weekend)
    today = QTextCharFormat()
    today.setForeground(QBrush(QColor(c["accent"])))
    today.setBackground(QBrush(QColor(c["today_bg"])))
    today.setFontWeight(QFont.Weight.Bold)
    cal.setDateTextFormat(QDate.currentDate(), today)
    cal.setProperty(_MARK, True)


def is_styled(cal: QCalendarWidget) -> bool:
    return bool(cal.property(_MARK))


_installed = None


class _CalendarFilter(QObject):
    def __init__(self, colours: Callable[[], Dict[str, str]], parent=None):
        super().__init__(parent)
        self._colours = colours

    def eventFilter(self, obj, event):
        if (event.type() in (QEvent.Type.Polish, QEvent.Type.Show)
                and isinstance(obj, QCalendarWidget) and not is_styled(obj)):
            try:
                apply(obj, self._colours())
            except Exception as e:                      # never stop a calendar opening
                print(f"[calendar_style] {e}")
        return False


def install(app: Optional[QApplication] = None,
            colours: Optional[Callable[[], Dict[str, str]]] = None) -> QObject:
    """Style every calendar the application shows (once per application; a second call
    replaces the colours). Returns the event filter."""
    global _installed
    app = app or QApplication.instance()
    if _installed is not None and _installed.parent() is app:
        _installed._colours = colours or _installed._colours
        return _installed
    _installed = _CalendarFilter(colours, app)
    app.installEventFilter(_installed)
    return _installed


__all__ = ["COLOURS", "apply", "calendar_qss", "install", "is_styled"]
