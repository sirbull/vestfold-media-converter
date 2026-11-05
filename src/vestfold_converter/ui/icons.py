"""Linjeikoner tegnet som vektorer i skjermens faktiske oppløsning."""

from functools import lru_cache

from PySide6.QtCore import Property, QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QPushButton


def paint_line_icon(painter: QPainter, rect: QRectF, name: str, color: str) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(rect.left(), rect.top())
    painter.scale(rect.width() / 24, rect.height() / 24)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(
        QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    path = QPainterPath()
    if name == "folder":
        path.moveTo(3, 7)
        path.lineTo(3, 19)
        path.lineTo(21, 19)
        path.lineTo(21, 7)
        path.lineTo(12, 7)
        path.lineTo(10, 4)
        path.lineTo(3, 4)
        path.closeSubpath()
    elif name in {"play", "video", "brand"}:
        if name == "video":
            painter.drawRoundedRect(QRectF(3, 4, 18, 16), 3, 3)
        path.moveTo(10, 8)
        path.lineTo(16, 12)
        path.lineTo(10, 16)
        path.closeSubpath()
    elif name == "play_filled":
        path.moveTo(8, 5)
        path.lineTo(18, 12)
        path.lineTo(8, 19)
        path.closeSubpath()
        painter.setBrush(QColor(color))
    elif name == "pause":
        path.addRect(QRectF(7, 5, 3, 14))
        path.addRect(QRectF(14, 5, 3, 14))
        painter.setBrush(QColor(color))
    elif name in {"backward", "forward"}:
        x = 15 if name == "backward" else 9
        tip = 8 if name == "backward" else 16
        path.moveTo(x, 5)
        path.lineTo(tip, 12)
        path.lineTo(x, 19)
    elif name in {"arrow_left", "arrow_right"}:
        direction = -1 if name == "arrow_left" else 1
        path.moveTo(12 - direction * 8, 12)
        path.lineTo(12 + direction * 8, 12)
        path.moveTo(12 + direction, 5)
        path.lineTo(12 + direction * 8, 12)
        path.lineTo(12 + direction, 19)
    elif name == "arrow_up":
        path.moveTo(12, 20)
        path.lineTo(12, 4)
        path.moveTo(5, 11)
        path.lineTo(12, 4)
        path.lineTo(19, 11)
    elif name == "list":
        for y in (6, 12, 18):
            painter.drawPoint(QPointF(4, y))
            painter.drawLine(QPointF(9, y), QPointF(20, y))
    elif name == "grid":
        for x in (4, 14):
            for y in (4, 14):
                path.addRoundedRect(QRectF(x, y, 6, 6), 1, 1)
    elif name == "search":
        painter.drawEllipse(QRectF(4, 4, 11, 11))
        path.moveTo(14, 14)
        path.lineTo(21, 21)
    elif name == "audio":
        path.moveTo(10, 17)
        path.lineTo(10, 5)
        path.lineTo(19, 3)
        path.lineTo(19, 15)
        painter.drawEllipse(QRectF(4, 15, 6, 5))
        painter.drawEllipse(QRectF(13, 13, 6, 5))
    elif name == "upload":
        path.moveTo(12, 16)
        path.lineTo(12, 3)
        path.moveTo(7, 8)
        path.lineTo(12, 3)
        path.lineTo(17, 8)
        path.moveTo(4, 15)
        path.lineTo(4, 21)
        path.lineTo(20, 21)
        path.lineTo(20, 15)
    elif name == "plus":
        path.moveTo(12, 5)
        path.lineTo(12, 19)
        path.moveTo(5, 12)
        path.lineTo(19, 12)
    elif name == "monitor":
        painter.drawRoundedRect(QRectF(3, 4, 18, 13), 2, 2)
        path.moveTo(12, 17)
        path.lineTo(12, 21)
        path.moveTo(8, 21)
        path.lineTo(16, 21)
    elif name == "sun":
        painter.drawEllipse(QRectF(8, 8, 8, 8))
        for x1, y1, x2, y2 in (
            (12, 2, 12, 4),
            (12, 20, 12, 22),
            (2, 12, 4, 12),
            (20, 12, 22, 12),
            (5, 5, 6.5, 6.5),
            (17.5, 17.5, 19, 19),
            (5, 19, 6.5, 17.5),
            (17.5, 6.5, 19, 5),
        ):
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    elif name == "moon":
        path.moveTo(15.5, 3.5)
        path.cubicTo(8, 1, 2.5, 7, 3.5, 13)
        path.cubicTo(4.5, 21, 15.5, 24, 20.5, 15.5)
        path.cubicTo(12, 18, 9, 9, 15.5, 3.5)
        path.closeSubpath()
    elif name == "close":
        path.moveTo(6, 6)
        path.lineTo(18, 18)
        path.moveTo(18, 6)
        path.lineTo(6, 18)
    elif name == "check":
        path.moveTo(5, 12)
        path.lineTo(10, 17)
        path.lineTo(19, 7)
    elif name == "settings":
        for y, x in ((6, 8), (12, 16), (18, 10)):
            painter.drawLine(QPointF(3, y), QPointF(21, y))
            painter.setBrush(QColor(color))
            painter.drawEllipse(QPointF(x, y), 2, 2)
            painter.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "info":
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        path.moveTo(12, 11)
        path.lineTo(12, 17)
        painter.drawPoint(QPointF(12, 7))
    elif name == "shield":
        path.moveTo(12, 3)
        path.lineTo(20, 6)
        path.lineTo(19, 15)
        path.quadTo(17, 19, 12, 22)
        path.quadTo(7, 19, 5, 15)
        path.lineTo(4, 6)
        path.closeSubpath()
    painter.drawPath(path)
    painter.restore()


@lru_cache(maxsize=128)
def line_icon(name: str, color: str) -> QIcon:
    icon = QIcon()
    # Supply exact physical sizes for the controls at common Windows DPI scales.
    # Use Qt's native pixmap engine for safe copying and disabled-state rendering.
    scales = {1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0}
    scales.update(screen.devicePixelRatio() for screen in QApplication.screens())
    for size in (16, 18, 20, 22, 24, 25, 32):
        for scale in sorted(scales):
            pixmap = QPixmap(QSize(size, size) * scale)
            pixmap.setDevicePixelRatio(scale)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            paint_line_icon(painter, QRectF(0, 0, size, size), name, color)
            painter.end()
            icon.addPixmap(pixmap)
    return icon


class IconButton(QPushButton):
    """Keep line icons in sync with the button's themed text color."""

    def __init__(self, symbol, description):
        super().__init__()
        self.symbol = symbol
        self._checked_icon_color = ""
        self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(20, 20))
        self.set_symbol(symbol, description)
        self.toggled.connect(self._refresh_icon)

    @Property(str)
    def checkedIconColor(self):
        return getattr(self, "_checked_icon_color", "")

    @checkedIconColor.setter
    def checkedIconColor(self, color):
        self._checked_icon_color = color
        if hasattr(self, "symbol"):
            self._refresh_icon()

    def set_symbol(self, symbol, description):
        self.symbol = symbol
        self.setAccessibleName(description)
        self.setToolTip(description)
        self._refresh_icon()

    def _refresh_icon(self):
        color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        if self.isChecked() and self._checked_icon_color:
            color = self._checked_icon_color
        self.setIcon(line_icon(self.symbol, color))

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in {QEvent.Type.PaletteChange, QEvent.Type.StyleChange} and hasattr(self, "symbol"):
            self._refresh_icon()
