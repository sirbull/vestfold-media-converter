"""Egne widgeter: profilmotiver, temavelger, avrundede nedtrekkslister og køvisning."""

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
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

from .icons import line_icon, paint_line_icon
from .theme import DARK, LIGHT, asset_path, is_dark, popup_stylesheet


class CrestBadge(QWidget):
    """Original SVG på en nøytral flate, uten toning eller endring av motivet."""

    def __init__(self):
        super().__init__()
        self.setAccessibleName("Vestfold Media Converter-ikon")
        self.renderer = QSvgRenderer(str(asset_path("vmc-ikon.svg")), self)
        if not self.renderer.isValid():
            raise RuntimeError("Kunne ikke laste programikonet fra programmets assets-mappe.")
        self.framed = False
        self.set_base_size(64)

    def set_base_size(self, size):
        self._base = size
        # Sirkelen i mørkt tema er litt større enn det frie ikonet i lyst tema.
        side = round(size * 1.125) if self.framed else size
        self.setFixedSize(side, side)

    def set_colors(self, colors):
        # I lyst tema står ikonet rett på bakgrunnen; i mørkt tema gir flaten kontrast.
        self.framed = is_dark(colors)
        self.set_base_size(self._base)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        if self.framed:
            painter.setPen(QPen(QColor("#b9bcb2"), 1))
            painter.setBrush(QColor("#f5f5ef"))
            ring = side - 1
            painter.drawEllipse(QRectF((self.width() - ring) / 2, (self.height() - ring) / 2, ring, ring))
            # Skjoldet er bredest øverst; tyngdepunktet ligger på 46 % av høyden. Litt lavere
            # plassering gir optisk balanse, og de øvre hjørnene holder seg innenfor sirkelen.
            size, drop = side * 0.64, side * 0.64 * 0.06
        else:
            size, drop = side * 60 / 64, 0
        self.renderer.render(
            painter, QRectF((self.width() - size) / 2, (self.height() - size) / 2 + drop, size, size)
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
        # Dråpeform: en sirkel med ett spisst hjørne øverst til høyre.
        circle, corner = QPainterPath(), QPainterPath()
        circle.addEllipse(QRectF(70, 3, 26, 26))
        corner.addRect(QRectF(83, 3, 13, 13))
        painter.drawPath(circle.united(corner))


class ImportArtwork(QWidget):
    """Video- og lydikonet fra drop-ikoner.svg, sentrert i slippfeltet."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(100, 93)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.renderer = QSvgRenderer(str(asset_path("drop-ikoner.svg")), self)
        if not self.renderer.isValid():
            raise RuntimeError("Kunne ikke laste ikonene for slippfeltet fra programmets assets-mappe.")

    def set_colors(self, colors):
        # Ikonene har faste farger og ser like ut i begge temaer.
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Behold forholdet mellom bredde og høyde, uansett widgetstørrelse.
        box = self.renderer.viewBoxF()
        scale = min(self.width() / box.width(), self.height() / box.height())
        width, height = box.width() * scale, box.height() * scale
        self.renderer.render(
            painter, QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
        )


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
        # Litt mindre radius enn feltet, så feltets fokuskant ikke stikker frem i hjørnene.
        shape.addRoundedRect(QRectF(popup.rect()), 8, 8)
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
            paint_line_icon(painter, icon_rect.adjusted(9, 9, -9, -9), "video" if video else "audio", color)
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


def divider():
    line = QFrame()
    line.setObjectName("divider")
    line.setFixedHeight(1)
    return line
