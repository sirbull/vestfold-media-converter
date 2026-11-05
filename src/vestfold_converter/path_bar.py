"""Explorer-style clickable paths with an overflow menu and optional editing."""

from pathlib import Path

from PySide6.QtCore import QDir, QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit, QMenu, QToolButton, QWidgetAction


class PathBar(QFrame):
    folderClicked = Signal(str)

    def __init__(self, parent=None, *, framed=False):
        super().__init__(parent)
        self.framed = framed
        self.setObjectName("addressPath" if framed else "browserPath")
        self.setAccessibleName("Klikkbar mappesti" if framed else "Klikkbar filsti")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(80)
        self.setFixedHeight(36)
        self._directory = Path.home()
        self._filename = ""
        self._editing = False
        self.buttons = []
        self._separators = []
        self._labels = []
        self.prefix = QLabel("" if framed else "Sti:", self)
        self.overflow = QToolButton(self)
        self.overflow.setObjectName("pathPart")
        self.overflow.setText("…")
        self.overflow.setAccessibleName("Vis hele filstien")
        self.overflow.setToolTip("Vis hele filstien og alle overordnede mapper")
        self.overflow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overflow.clicked.connect(self.show_full_path)
        self.overflow.hide()
        self.popup_menu = QMenu(self)
        self.popup_menu.setObjectName("pathMenu")
        self.popup_menu.setToolTipsVisible(True)
        self.editor = QLineEdit(self)
        self.editor.setObjectName("pathEditor")
        self.editor.setAccessibleName("Mappe eller filsti")
        self.editor.setPlaceholderText("Skriv eller lim inn en mappesti")
        self.editor.installEventFilter(self)
        self.editor.hide()
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.timeout.connect(self._arrange)

    def sizeHint(self):
        return QSize(400, 36)

    def minimumSizeHint(self):
        return QSize(80, 36)

    def set_path(self, directory, filename=""):
        self.popup_menu.close()
        self._directory = Path(directory)
        self._filename = filename
        self._editing = False
        self.editor.hide()
        self.editor.setText(QDir.toNativeSeparators(str(self._directory)))
        self.setToolTip(str(self._directory / filename) if filename else str(self._directory))
        for widget in [*self.buttons, *self._separators, *self._labels]:
            widget.hide()
            widget.deleteLater()
        self.buttons.clear()
        self._separators.clear()
        self._labels.clear()
        for folder in [*reversed(self._directory.parents), self._directory]:
            name = folder.name or folder.anchor
            button = QToolButton(self)
            button.setObjectName("pathPart")
            button.setToolTip(str(folder))
            button.setAccessibleName(str(folder))
            button.setProperty("folderPath", str(folder))
            button.setProperty("partName", name)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, path=str(folder): self.folderClicked.emit(path))
            self.buttons.append(button)
        if filename:
            label = QLabel(self)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setProperty("partName", filename)
            label.setToolTip(filename)
            self._labels.append(label)
        for _ in range(len(self.buttons) + len(self._labels)):
            separator = QLabel("›", self)
            separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._separators.append(separator)
        self._arrange()
        self._layout_timer.start(0)

    def _arrange(self):
        if self._editing:
            self.editor.setGeometry(self.rect().adjusted(4, 3, -4, -3))
            return
        nodes = [*self.buttons, *self._labels]
        if not nodes:
            return
        for widget in [*nodes, *self._separators, self.overflow, self.prefix]:
            widget.hide()
        x = 8 if self.framed else 0
        height = self.height() - 8
        if not self.framed:
            width = self.prefix.sizeHint().width() + 8
            self.prefix.setGeometry(x, 4, width, height)
            self.prefix.show()
            x += width
        available = max(0, self.width() - x - 8)
        separator_width = 16
        widths = [node.fontMetrics().horizontalAdvance(node.property("partName")) + 12 for node in nodes]
        total = sum(widths) + separator_width * (len(nodes) - 1)
        start = 0
        overflowing = total > available
        if overflowing:
            self.overflow.setGeometry(x, 4, 28, height)
            self.overflow.show()
            x += 28
            available = max(0, available - 28 - separator_width)
            start = len(nodes) - 1
            used = min(widths[-1], available)
            while start > 0 and used + separator_width + widths[start - 1] <= available:
                start -= 1
                used += separator_width + widths[start]
        for index in range(start, len(nodes)):
            if index > start or overflowing:
                separator = self._separators[index]
                separator.setGeometry(x, 4, separator_width, height)
                separator.show()
                x += separator_width
            node = nodes[index]
            width = min(widths[index], max(0, self.width() - x - 8))
            text = node.fontMetrics().elidedText(
                node.property("partName"), Qt.TextElideMode.ElideMiddle, max(0, width - 8)
            )
            node.setText(text.replace("&", "&&") if isinstance(node, QToolButton) else text)
            node.setGeometry(x, 4, width, height)
            node.show()
            x += width

    def show_full_path(self):
        self.popup_menu.clear()
        header = QLabel(self.toolTip())
        header.setObjectName("pathMenuHeader")
        header.setTextFormat(Qt.TextFormat.PlainText)
        header.setWordWrap(True)
        header.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.setFixedWidth(min(480, max(180, self.screen().availableGeometry().width() - 60)))
        header.setMargin(8)
        header_action = QWidgetAction(self.popup_menu)
        header_action.setDefaultWidget(header)
        self.popup_menu.addAction(header_action)
        self.popup_menu.addSeparator()
        for button in self.buttons:
            path = button.property("folderPath")
            name = button.property("partName")
            text = self.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, header.width() - 40)
            action = self.popup_menu.addAction(text.replace("&", "&&"))
            action.setData(path)
            action.setToolTip(path)
            action.triggered.connect(lambda checked=False, target=path: self.folderClicked.emit(target))
        if self.framed:
            self.popup_menu.addSeparator()
            self.popup_menu.addAction("Rediger sti …", lambda: QTimer.singleShot(0, self.start_edit))
        self.popup_menu.popup(self.overflow.mapToGlobal(QPoint(0, self.overflow.height())))

    def start_edit(self):
        if not self.framed:
            return
        self._editing = True
        for widget in [*self.buttons, *self._separators, *self._labels, self.overflow, self.prefix]:
            widget.hide()
        self.editor.setText(QDir.toNativeSeparators(str(self._directory)))
        self.editor.setGeometry(self.rect().adjusted(4, 3, -4, -3))
        self.editor.show()
        self.editor.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.editor.selectAll()

    def stop_edit(self):
        self._editing = False
        self.editor.hide()
        self._arrange()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.framed:
            self.start_edit()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.framed and event.key() == Qt.Key.Key_F2:
            self.start_edit()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.editor:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.stop_edit()
                self.setFocus()
                return True
            if event.type() == QEvent.Type.FocusOut and self._editing:
                self.stop_edit()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_layout_timer"):
            self._arrange()

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "_layout_timer") and event.type() in {
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        }:
            self._layout_timer.start(0)
