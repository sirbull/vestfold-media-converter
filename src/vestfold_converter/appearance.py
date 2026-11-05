"""Tema, tegnede ikoner og køvisning for Qt Widgets."""

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolButton,
    QWidget,
)


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / name


@lru_cache(maxsize=1)
def _load_font() -> str:
    font_id = QFontDatabase.addApplicationFont(str(asset_path("fonts/Nunito-wght.ttf")))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
    if "Nunito" not in families:
        raise RuntimeError("Kunne ikke laste Nunito fra programmets fonts-mappe.")
    return "Nunito"


def configure_typography() -> None:
    """Registrer fonten bare i denne appen. Ingen installasjon eller nettverk."""
    font = QFont(_load_font(), 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    QApplication.instance().setFont(font)


class CrestBadge(QWidget):
    """Original SVG på en nøytral flate, uten toning eller endring av motivet."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(64, 64)
        self.setAccessibleName("Vestfold fylkeskommunes våpenskjold")
        self.renderer = QSvgRenderer(str(asset_path("vestfold-vapen.svg")), self)
        if not self.renderer.isValid():
            raise RuntimeError("Kunne ikke laste Vestfold-logoen fra programmets assets-mappe.")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#b9bcb2"), 1))
        painter.setBrush(QColor("#f5f5ef"))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        size = min(self.width(), self.height()) * 46 / 64
        self.renderer.render(
            painter, QRectF((self.width() - size) / 2, (self.height() - size) / 2, size, size)
        )


class ProfileMotif(QWidget):
    """Små modulformer inspirert av profilens kontrast mellom rundt og kantet."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(100, 32)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.colors = LIGHT

    def set_colors(self, colors):
        self.colors = colors
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.colors["motif_red"]))
        painter.drawEllipse(QRectF(2, 3, 26, 26))
        painter.setBrush(QColor(self.colors["nav"]))
        painter.drawRect(QRectF(36, 3, 26, 26))
        painter.setBrush(QColor(self.colors["motif_sand"]))
        shape = QPainterPath()
        shape.moveTo(70, 3)
        shape.lineTo(96, 3)
        shape.lineTo(96, 16)
        shape.cubicTo(96, 24, 90, 29, 83, 29)
        shape.cubicTo(76, 29, 70, 24, 70, 16)
        shape.closeSubpath()
        painter.drawPath(shape)


class ImportArtwork(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(124, 80)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.colors = LIGHT

    def set_colors(self, colors):
        self.colors = colors
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.width() / 124, self.height() / 80)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.save()
        painter.translate(32, 44)
        painter.rotate(-7)
        painter.setBrush(QColor(self.colors["nav"]))
        painter.drawRoundedRect(QRectF(-23, -28, 46, 56), 7, 7)
        _paint_line_icon(painter, QRectF(-12, -15, 24, 24), "video", "#ffffff")
        painter.restore()
        painter.setBrush(QColor(self.colors["motif_soft"]))
        shape = QPainterPath()
        shape.moveTo(70, 6)
        shape.lineTo(116, 6)
        shape.lineTo(116, 40)
        shape.cubicTo(116, 54, 105, 64, 93, 64)
        shape.cubicTo(80, 64, 70, 54, 70, 40)
        shape.closeSubpath()
        painter.drawPath(shape)
        _paint_line_icon(painter, QRectF(80, 17, 25, 25), "audio", self.colors["motif_red"])
        painter.setBrush(QColor(self.colors["motif_sand"]))
        painter.drawEllipse(QRectF(51, 57, 18, 18))


class RoundedComboBox(QComboBox):
    """Behold Qt sin tastaturnavigasjon, med en avrundet popup uten systemramme."""

    def __init__(self):
        super().__init__()
        view = QListView()
        view.setObjectName("comboOptions")
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setMouseTracking(True)
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setUniformItemSizes(True)
        view.setItemDelegate(QStyledItemDelegate(view))
        self.setView(view)
        self.setMaxVisibleItems(12)
        popup = view.window()
        popup.setObjectName("comboPopup")
        popup.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        popup.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint, True)
        popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

    def set_popup_colors(self, colors):
        # Qt sin private popup arver ikke alltid hovedvinduets stylesheet på Windows.
        self.view().window().setStyleSheet(popup_stylesheet(colors))

    def sizeHint(self):
        # Luft til pil og kant også når Qt runder opp tekstbredden ved større skrift.
        return super().sizeHint() + QSize(8, 0)

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(popup.rect()), 10, 10)
        popup.setMask(QRegion(shape.toFillPolygon().toPolygon()))


class ThemeSwitcher(QFrame):
    modeChanged = Signal(str)
    MODES = ("system", "light", "dark")

    def __init__(self):
        super().__init__()
        self.setObjectName("themeSwitcher")
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Fargetema")
        self._mode = "system"
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        for index, (mode, name) in enumerate(
            zip(self.MODES, ("Systemtema", "Lys modus", "Mørk modus"), strict=True)
        ):
            button = QToolButton()
            button.setObjectName("themeOption")
            button.setCheckable(True)
            button.setFixedSize(38, 34)
            button.setIconSize(QSize(20, 20))
            button.setAccessibleName(name)
            button.setToolTip(name)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.installEventFilter(self)
            self.group.addButton(button, index)
            self.buttons[mode] = button
            layout.addWidget(button)
        self.buttons["system"].setChecked(True)
        self.group.idClicked.connect(lambda index: self.set_mode(self.MODES[index]))

    def mode(self):
        return self._mode

    def set_mode(self, mode):
        mode = mode if mode in self.MODES else "system"
        self.buttons[mode].setChecked(True)
        if mode != self._mode:
            self._mode = mode
            self.modeChanged.emit(mode)

    def set_colors(self, colors):
        for mode, icon in zip(self.MODES, ("monitor", "sun", "moon"), strict=True):
            color = colors["yellow_text"] if mode == self._mode else colors["muted"]
            self.buttons[mode].setIcon(line_icon(icon, color))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in {
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Home,
            Qt.Key.Key_End,
        }:
            index = self.MODES.index(self._mode)
            if event.key() == Qt.Key.Key_Home:
                index = 0
            elif event.key() == Qt.Key.Key_End:
                index = len(self.MODES) - 1
            else:
                index = (index + (1 if event.key() == Qt.Key.Key_Right else -1)) % len(self.MODES)
            self.set_mode(self.MODES[index])
            self.buttons[self._mode].setFocus()
            return True
        return super().eventFilter(watched, event)


LIGHT = {
    "background": "#f3f0ec",
    "surface": "#fffdfa",
    "raised": "#f3f0ec",
    "text": "#20231f",
    "muted": "#62655d",
    "border": "#d3cbc0",
    "accent": "#b70013",
    "primary": "#e40017",
    "primary_hover": "#bc0014",
    "primary_text": "#ffffff",
    "hover": "#eee7df",
    "selected": "#f8e8ec",
    "nav": "#005260",
    "motif_red": "#b7173d",
    "motif_sand": "#dcd3c5",
    "motif_soft": "#f1d1d8",
    "yellow": "#ffcd00",
    "yellow_text": "#302800",
    "status_text": "#005260",
    "status_bg": "#e5eeef",
    "success": "#2c6039",
    "success_bg": "#e2eadb",
    "error": "#b70013",
    "error_bg": "#f6dedf",
    "video": "#005260",
    "video_bg": "#e5eeef",
    "audio": "#b7173d",
    "audio_bg": "#f8e8ec",
}
DARK = {
    "background": "#242422",
    "surface": "#2d2e2b",
    "raised": "#33352f",
    "text": "#f5f2ed",
    "muted": "#c0bdb4",
    "border": "#515149",
    "accent": "#ffcd00",
    "primary": "#e40017",
    "primary_hover": "#bc0014",
    "primary_text": "#ffffff",
    "hover": "#383a33",
    "selected": "#48343a",
    "nav": "#196370",
    "motif_red": "#e2a2b1",
    "motif_sand": "#8a6c3e",
    "motif_soft": "#48343a",
    "yellow": "#ffcd00",
    "yellow_text": "#302800",
    "status_text": "#ccdcdf",
    "status_bg": "#283c3f",
    "success": "#b3d89d",
    "success_bg": "#34432d",
    "error": "#ffb6bb",
    "error_bg": "#4d2d32",
    "video": "#b2cbcf",
    "video_bg": "#283c3f",
    "audio": "#e2a2b1",
    "audio_bg": "#48343a",
}


def _paint_line_icon(painter: QPainter, rect: QRectF, name: str, color: str) -> None:
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
            _paint_line_icon(painter, QRectF(0, 0, size, size), name, color)
            painter.end()
            icon.addPixmap(pixmap)
    return icon


class PathLabel(QLabel):
    def __init__(self, text=""):
        super().__init__(text)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text):
        super().setText(text)
        self.setToolTip(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle, self.width())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter, text)


class QueueDelegate(QStyledItemDelegate):
    """Vis filmetadata på to linjer og status som merker med egen fremdrift."""

    def paint(self, painter, option, index):
        colors = DARK if self.parent().property("dark") else LIGHT
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ""
        styled.icon = QIcon()
        style = styled.widget.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if index.column() == 0 and styled.state & QStyle.StateFlag.State_Selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["primary"]))
            painter.drawRoundedRect(
                QRectF(option.rect.left() + 2, option.rect.top() + 14, 3, option.rect.height() - 28), 1.5, 1.5
            )
        rect = QRectF(option.rect).adjusted(14, 0, -14, 0)
        data = index.data(Qt.ItemDataRole.UserRole) or {}
        text = index.data() or ""
        font = option.font
        painter.setFont(font)
        if index.column() == 0:
            video = data.get("video", False)
            color = colors["video" if video else "audio"]
            icon_rect = QRectF(rect.left(), rect.center().y() - 20, 40, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colors["video_bg" if video else "audio_bg"]))
            painter.drawRoundedRect(icon_rect, 10, 10)
            _paint_line_icon(painter, icon_rect.adjusted(9, 9, -9, -9), "video" if video else "audio", color)
            content = rect.adjusted(54, 0, 0, 0)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(colors["text"]))
            title = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, int(content.width()))
            painter.drawText(content.adjusted(0, 12, 0, -34), Qt.AlignmentFlag.AlignVCenter, title)
            font.setBold(False)
            font.setPointSizeF(max(8, font.pointSizeF() - 1))
            painter.setFont(font)
            painter.setPen(QColor(colors["muted"]))
            subtitle = painter.fontMetrics().elidedText(
                data.get("subtitle", "Analyserer …"), Qt.TextElideMode.ElideRight, int(content.width())
            )
            painter.drawText(content.adjusted(0, 37, 0, -10), Qt.AlignmentFlag.AlignVCenter, subtitle)
        elif index.column() == 3:
            state = data.get("state", "Klar")
            active = state == "Konverterer"
            failed = bool(data.get("error")) and state != "Avbrutt"
            foreground = (
                colors["success"]
                if state == "Fullført"
                else colors["error"]
                if failed
                else colors["status_text"]
            )
            background = (
                colors["success_bg"]
                if state == "Fullført"
                else colors["error_bg"]
                if failed
                else colors["status_bg"]
            )
            label = (
                f"{data.get('progress', 0):.0%}"
                if active
                else "Feil"
                if failed
                else ("Analyserer" if state == "Venter på analyse" else state)
            )
            width = min(rect.width(), painter.fontMetrics().horizontalAdvance(label) + 32)
            badge = QRectF(rect.left(), rect.center().y() - (19 if active else 13), width, 26)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(background))
            painter.drawRoundedRect(badge, 13, 13)
            painter.setPen(QColor(foreground))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
            if active:
                track = QRectF(rect.left(), rect.center().y() + 16, rect.width(), 4)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(colors["border"]))
                painter.drawRoundedRect(track, 2, 2)
                track.setWidth(track.width() * data.get("progress", 0))
                painter.setBrush(QColor(colors["accent"]))
                painter.drawRoundedRect(track, 2, 2)
        else:
            painter.setPen(QColor(colors["text"] if index.column() == 1 else colors["muted"]))
            text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, int(rect.width()))
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(140, 76)


def popup_stylesheet(c: dict) -> str:
    return f"""
        QFrame#comboPopup {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 10px; padding: 4px; }}
        QListView#comboOptions {{ background: {c["surface"]}; color: {c["text"]}; border: 0;
            font-family: 'Nunito'; font-size: 10pt; outline: 0; padding: 4px;
            selection-background-color: {c["selected"]}; selection-color: {c["text"]}; }}
        QListView#comboOptions::item {{ padding: 9px 12px; min-height: 18px;
            margin: 2px; border: 0; border-radius: 6px; }}
        QListView#comboOptions::item:hover, QListView#comboOptions::item:selected {{
            background: {c["selected"]}; color: {c["text"]}; }}
    """


def stylesheet(c: dict) -> str:
    arrow = asset_path("chevron-dark.svg" if c["background"] == DARK["background"] else "chevron-light.svg")
    return f"""
        QWidget {{ font-family: 'Nunito'; font-size: 10pt; color: {c["text"]}; }}
        QMainWindow, QWidget#mainSurface {{ background: {c["background"]}; }}
        QDialog#importBrowser {{ background: {c["background"]}; }}
        QDialog#importBrowser QTreeView, QDialog#importBrowser QListView {{
            background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]};
            border-radius: 8px; selection-background-color: {c["selected"]};
            selection-color: {c["text"]}; outline: 0; }}
        QListWidget#browserPlaces::item {{ padding: 5px 6px; }}
        QTreeView#browserFiles::item {{ min-height: 26px; padding: 2px 4px; }}
        QDialog#importBrowser QPushButton:checked {{
            background: {c["yellow"]}; color: {c["yellow_text"]}; border-color: {c["yellow"]}; }}
        QSplitter#importSplitter::handle {{ background: {c["border"]};
            border-radius: 3px; margin: 10px 3px; }}
        QSplitter#importSplitter::handle:hover {{ background: {c["accent"]}; }}
        QLabel {{ background: transparent; }}
        QLabel#title {{ font-size: 21pt; font-weight: 850; }}
        QLabel#sectionTitle {{ font-size: 14pt; font-weight: 800; }}
        QLabel#muted, QLabel#selectionDetail, QLabel#eyebrow {{ color: {c["muted"]}; }}
        QLabel#eyebrow {{ font-size: 9pt; font-weight: 600; }}
        QLabel#selectionName {{ font-weight: 600; font-size: 11pt; }}
        QLabel#countBadge {{ background: {c["yellow"]}; color: {c["yellow_text"]};
            border-radius: 6px; padding: 4px 10px; font-weight: 800; }}
        QLabel#notice {{ background: {c["raised"]}; padding: 10px; border-radius: 8px; }}
        QFrame#themeSwitcher {{ background: {c["raised"]}; border: 1px solid {c["border"]}; border-radius: 11px; }}
        QToolButton#themeOption {{ background: transparent; border: 1px solid transparent;
            border-radius: 7px; padding: 0; min-height: 30px; min-width: 34px; }}
        QToolButton#themeOption:hover {{ background: {c["hover"]}; }}
        QToolButton#themeOption:checked {{ background: {c["yellow"]}; border-color: {c["yellow"]}; }}
        QToolButton#themeOption:focus {{ border: 2px solid {c["accent"]}; }}
        QPushButton, QToolButton {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 8px; padding: 9px 13px; min-height: 18px; }}
        QPushButton:hover, QToolButton:hover {{ background: {c["hover"]}; border-color: {c["accent"]}; }}
        QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{
            border: 2px solid {c["accent"]}; }}
        QPushButton:disabled, QToolButton:disabled {{ color: {c["muted"]}; background: {c["raised"]}; }}
        QPushButton#primary {{ background: {c["primary"]}; color: {c["primary_text"]};
            border: 2px solid {c["primary"]}; border-radius: 6px; font-weight: 850;
            font-size: 12pt; padding: 11px 24px; }}
        QPushButton#primary:hover {{ background: {c["primary_hover"]}; border-color: {c["primary_hover"]}; }}
        QPushButton#primary:focus {{ border: 2px solid {c["yellow"]}; }}
        QPushButton#primary:disabled {{ background: {c["border"]}; border-color: {c["border"]}; color: {c["muted"]}; }}
        QPushButton#softButton {{ background: {c["surface"]}; border-color: {c["border"]};
            color: {c["text"]}; font-weight: 800; }}
        QPushButton#softButton:hover {{ background: {c["hover"]}; border-color: {c["accent"]}; }}
        QPushButton#quietButton, QToolButton#advancedToggle {{ background: transparent; border: 1px solid transparent; }}
        QPushButton#quietButton:hover, QToolButton#advancedToggle:hover,
        QPushButton#quietButton:checked {{ background: {c["hover"]}; color: {c["accent"]}; }}
        QToolButton#advancedToggle {{ text-align: left; padding-left: 0; }}
        QPushButton#dropArea {{ background: {c["surface"]}; border: 2px dashed {c["border"]};
            border-radius: 10px; min-height: 160px; }}
        QPushButton#dropArea:hover, QPushButton#dropArea:focus {{ background: {c["hover"]}; border-color: {c["accent"]}; }}
        QLabel#dropTitle {{ font-size: 21pt; font-weight: 850; }}
        QLabel#dropAction {{ background: {c["primary"]}; color: {c["primary_text"]};
            border-radius: 6px; padding: 10px 26px; font-weight: 800; }}
        QFrame#queueCard, QFrame#destination, QScrollArea#settingsCard {{ background: {c["surface"]};
            border: 1px solid {c["border"]}; border-radius: 8px; }}
        QTableWidget {{ background: {c["surface"]}; border: 0; selection-background-color: {c["selected"]};
            selection-color: {c["text"]}; outline: 0; }}
        QTableWidget::item {{ border: 0; border-bottom: 1px solid {c["border"]}; }}
        QTableWidget::item:focus {{ border: 1px solid {c["accent"]}; }}
        QHeaderView::section {{ background: {c["raised"]}; color: {c["muted"]}; padding: 11px 14px;
            border: 0; border-bottom: 1px solid {c["border"]}; text-align: left; font-size: 9pt; font-weight: 600; }}
        QScrollArea#settingsCard > QWidget > QWidget, QWidget#settingsPanel {{ background: {c["surface"]}; }}
        QScrollArea#inspectorScroll {{ background: {c["surface"]}; border: 0; }}
        QScrollArea#inspectorScroll > QWidget > QWidget, QWidget#previewPanel {{ background: {c["surface"]}; }}
        QTabWidget#inspector::pane {{ background: {c["surface"]}; border: 1px solid {c["border"]}; border-radius: 10px; }}
        QTabBar::tab {{ background: transparent; color: {c["muted"]}; padding: 10px 12px;
            border: 0; border-bottom: 2px solid transparent; }}
        QTabBar::tab:selected {{ color: {c["accent"]}; border-bottom-color: {c["accent"]}; font-weight: 600; }}
        QTabBar::tab:focus {{ border: 1px solid {c["accent"]}; }}
        QLabel#previewTime {{ color: {c["muted"]}; font-size: 9pt; }}
        QSlider::groove:horizontal {{ height: 4px; background: {c["border"]}; border-radius: 2px; }}
        QSlider::sub-page:horizontal {{ background: {c["accent"]}; border-radius: 2px; }}
        QSlider::handle:horizontal {{ width: 12px; margin: -5px 0; background: {c["accent"]};
            border-radius: 6px; border: 1px solid {c["surface"]}; }}
        QComboBox, QLineEdit, QSpinBox {{ background: {c["surface"]}; border: 1px solid {c["border"]};
            border-radius: 7px; padding: 8px; min-height: 20px; selection-background-color: {c["selected"]}; }}
        QComboBox {{ border: 2px solid {c["border"]}; border-radius: 9px;
            padding: 8px 38px 8px 12px; min-height: 20px; }}
        QComboBox:hover {{ border-color: {c["muted"]}; }}
        QComboBox:focus, QComboBox:on {{ border-color: {c["accent"]}; }}
        QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right;
            width: 28px; border: 0; background: transparent; margin-right: 6px; }}
        QComboBox::down-arrow {{ image: url("{arrow.as_posix()}"); width: 16px; height: 16px; }}
        QProgressBar {{ border: 0; border-radius: 3px; background: {c["border"]}; max-height: 6px; min-height: 6px; }}
        QProgressBar::chunk {{ background: {c["primary"]}; border-radius: 3px; }}
        QFrame#divider {{ background: {c["border"]}; border: 0; max-height: 1px; }}
        QSplitter::handle {{ background: transparent; width: 18px; }}
        QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {c["border"]}; border-radius: 4px; min-height: 32px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QToolTip {{ background: {c["surface"]}; color: {c["text"]}; border: 1px solid {c["border"]}; padding: 5px; }}
        QMainWindow[compact="true"] QLabel#title {{ font-size: 18pt; }}
        QMainWindow[compact="true"] QLabel#sectionTitle {{ font-size: 12pt; }}
        QMainWindow[compact="true"] QLabel#dropTitle {{ font-size: 16pt; }}
        QMainWindow[compact="true"] QPushButton, QMainWindow[compact="true"] QToolButton {{
            padding: 7px 10px; min-height: 16px; }}
        QMainWindow[compact="true"] QPushButton#primary {{ font-size: 11pt; padding: 7px 18px; min-height: 18px; }}
        QMainWindow[compact="true"] QPushButton#dropArea {{ min-height: 120px; }}
    """
