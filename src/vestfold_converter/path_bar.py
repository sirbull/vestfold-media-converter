"""A compact, scrollable path whose parent folders can be clicked."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QToolButton, QWidget


class PathBar(QScrollArea):
    folderClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("browserPath")
        self.setAccessibleName("Klikkbar filsti")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(36)
        self.content = QWidget()
        self.row = QHBoxLayout(self.content)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(0)
        self.setWidget(self.content)
        self.buttons = []
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self._show_end)

    def set_path(self, directory, filename=""):
        while self.row.count():
            item = self.row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.buttons.clear()
        directory = Path(directory)
        self.setToolTip(str(directory / filename) if filename else str(directory))
        self.row.addWidget(QLabel("Sti: "))
        for folder in [*reversed(directory.parents), directory]:
            button = QToolButton()
            button.setObjectName("pathPart")
            button.setText((folder.name or folder.anchor).replace("&", "&&"))
            button.setToolTip(str(folder))
            button.setAccessibleName(str(folder))
            button.setProperty("folderPath", str(folder))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, path=str(folder): self.folderClicked.emit(path))
            if self.buttons:
                self.row.addWidget(QLabel(" › "))
            self.row.addWidget(button)
            self.buttons.append(button)
        if filename:
            self.row.addWidget(QLabel(" › " + filename))
        self.row.addStretch()
        self.scroll_timer.start(0)

    def _show_end(self):
        self.horizontalScrollBar().setValue(self.horizontalScrollBar().maximum())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "scroll_timer"):
            self.scroll_timer.start(0)
