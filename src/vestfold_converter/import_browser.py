"""File import with shared list/grid selection and cancellable FFmpeg preview."""

import os
import queue
import threading
from pathlib import Path

from PySide6.QtCore import QDir, QItemSelectionModel, QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTreeView,
    QVBoxLayout,
)

from .models import Cancelled, MediaError, QueueItem
from .preview import PreviewPanel
from .system_places import explorer_places

MEDIA_FILTERS = [
    "*.mp4",
    "*.mov",
    "*.mkv",
    "*.avi",
    "*.webm",
    "*.mts",
    "*.m2ts",
    "*.ts",
    "*.mxf",
    "*.mpg",
    "*.mpeg",
    "*.m4v",
    "*.wmv",
    "*.3gp",
    "*.vob",
    "*.flv",
    "*.wav",
    "*.mp3",
    "*.flac",
    "*.m4a",
    "*.aac",
    "*.opus",
    "*.ogg",
    "*.aif",
    "*.aiff",
    "*.wma",
    "*.alac",
]


class SelectionProbe:
    """One analysis at a time; changing selection cancels old and pending work."""

    def __init__(self, engine):
        self.engine = engine
        self.results = queue.SimpleQueue()
        self._condition = threading.Condition()
        self._pending = None
        self._cancel = threading.Event()
        self._stopped = False
        self._generation = 0
        self.thread = threading.Thread(target=self._run, name="Importforhåndsvisning", daemon=True)
        self.thread.start()

    def request(self, path=None):
        with self._condition:
            self._generation += 1
            self._cancel.set()
            self._pending = (self._generation, path) if path else None
            self._condition.notify()
            return self._generation

    def stop(self):
        with self._condition:
            self._stopped = True
            self._pending = None
            self._cancel.set()
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._stopped or self._pending is not None)
                if self._stopped:
                    return
                generation, path = self._pending
                self._pending = None
                cancel = self._cancel = threading.Event()
            try:
                info = self.engine.analyze(path, cancel)
                result = (generation, path, info, "")
            except Cancelled:
                continue
            except (MediaError, OSError) as exc:
                result = (generation, path, None, str(exc))
            if not cancel.is_set():
                self.results.put(result)


class BrowserFileModel(QFileSystemModel):
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            labels = {0: "Navn", 1: "Størrelse", 2: "Type", 3: "Endret"}
            if section in labels:
                return labels[section]
        return super().headerData(section, orientation, role)


class ImportBrowser(QDialog):
    def __init__(
        self, engine, parent=None, *, directory=None, view="list", sizes=None, places_loader=explorer_places
    ):
        super().__init__(parent)
        self.setWindowTitle("Importer lyd og video")
        self.setObjectName("importBrowser")
        self.setModal(True)
        self.engine = engine
        self.files = []
        self._closed = False
        self._history = []
        self._history_index = -1
        self._probe_path = None
        self._probe_generation = 0
        self.probe = SelectionProbe(engine)
        self._places_cancel = threading.Event()
        self._places_results = queue.SimpleQueue()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        toolbar = QHBoxLayout()
        self.back = self._button("Tilbake", toolbar, self.go_back)
        self.forward = self._button("Frem", toolbar, self.go_forward)
        self.up = self._button("Opp", toolbar, self.go_up)
        self.address = QLineEdit()
        self.address.setAccessibleName("Mappe eller filsti")
        self.address.setPlaceholderText("Skriv eller lim inn en mappesti")
        self.address.returnPressed.connect(self._open_address)
        toolbar.addWidget(self.address, 1)
        layout.addLayout(toolbar)
        views = QHBoxLayout()
        self.location = QLabel("Velg filer. Ctrl/Shift markerer flere.")
        self.location.setObjectName("muted")
        views.addWidget(self.location, 1)
        self.view_group = QButtonGroup(self)
        self.view_buttons = {}
        for index, (mode, label) in enumerate((("list", "Liste"), ("grid", "Rutenett"))):
            button = self._button(label, views, lambda checked=False, m=mode: self.set_view(m))
            button.setCheckable(True)
            self.view_group.addButton(button, index)
            self.view_buttons[mode] = button
        self.native = self._button(
            "Utforsker …" if os.name == "nt" else "Systemets filvelger …", views, self.open_native
        )
        self.native.setToolTip("Åpne den vanlige filvelgeren med alle systemets steder og snarveier")
        layout.addLayout(views)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("importSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(12)
        self.splitter.setAccessibleName("Dra skillelinjen for å endre størrelsen på forhåndsvisningen")
        self.places = QListWidget()
        self.places.setObjectName("browserPlaces")
        self.places.setAccessibleName("Snarveier og steder")
        self.places.setMinimumWidth(120)
        self.places.setMaximumWidth(260)
        self.places.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.places.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.places.itemClicked.connect(self._place_clicked)
        self.splitter.addWidget(self.places)
        self.model = BrowserFileModel(self)
        self.model.setReadOnly(True)
        self.model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs)
        self.model.setNameFilterDisables(False)
        self.model.setRootPath("")
        self.selection = QItemSelectionModel(self.model, self)
        self.stack = QStackedWidget()
        self.stack.setMinimumWidth(220)
        self.list_view = QTreeView()
        self.list_view.setObjectName("browserFiles")
        self.list_view.setAccessibleName("Filer som liste")
        self.list_view.setRootIsDecorated(False)
        self.list_view.setItemsExpandable(False)
        self.list_view.setUniformRowHeights(True)
        self.grid_view = QListView()
        self.grid_view.setObjectName("browserGrid")
        self.grid_view.setAccessibleName("Filer som rutenett")
        self.grid_view.setViewMode(QListView.ViewMode.IconMode)
        self.grid_view.setResizeMode(QListView.ResizeMode.Adjust)
        self.grid_view.setMovement(QListView.Movement.Static)
        self.grid_view.setWrapping(True)
        self.grid_view.setWordWrap(True)
        self.grid_view.setIconSize(QSize(48, 48))
        self.grid_view.setGridSize(QSize(116, 96))
        self.grid_view.setSpacing(6)
        for widget in (self.list_view, self.grid_view):
            widget.setModel(self.model)
            widget.setSelectionModel(self.selection)
            widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            widget.activated.connect(self._activate)
            self.stack.addWidget(widget)
        self.list_view.setSortingEnabled(True)
        self.list_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.list_view.setColumnWidth(0, 240)
        self.list_view.setColumnWidth(1, 80)
        self.list_view.hideColumn(2)
        self.splitter.addWidget(self.stack)
        self.preview = PreviewPanel(engine.ffmpeg)
        self.preview.setMinimumWidth(220)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.canvas.setMaximumHeight(16777215)
        self.preview.canvas.set_message("Marker en fil for å se forhåndsvisning")
        self.preview.filename.setText("Forhåndsvisning")
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setStretchFactor(2, 2)
        layout.addWidget(self.splitter, 1)
        self.places_status = QLabel("Henter Hurtigtilgang fra Windows …" if os.name == "nt" else "")
        self.places_status.setObjectName("muted")
        self.places_status.setWordWrap(True)
        layout.addWidget(self.places_status)
        footer = QHBoxLayout()
        self.all_files = self._button("Vis alle filtyper", footer, self._toggle_filter)
        self.all_files.setCheckable(True)
        self.count = QLabel("Ingen filer valgt")
        footer.addWidget(self.count, 1)
        self.cancel = self._button("Avbryt", footer, self.reject)
        self.import_button = self._button("Importer valgte", footer, self.accept_selection)
        self.import_button.setObjectName("primary")
        self.import_button.setEnabled(False)
        layout.addLayout(footer)
        self.selection.currentChanged.connect(self._current_changed)
        self.selection.selectionChanged.connect(self._selection_changed)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(180)
        self.debounce.timeout.connect(self._start_probe)
        self.poll = QTimer(self)
        self.poll.setInterval(60)
        self.poll.timeout.connect(self._poll)
        self.poll.start()
        for key, callback in (
            ("Alt+Left", self.go_back),
            ("Alt+Right", self.go_forward),
            ("Alt+Up", self.go_up),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
        self.set_view(view)
        self._toggle_filter()
        self._set_places([])
        initial = directory or QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        if not self.navigate(str(initial or Path.home())):
            self.navigate(str(Path.home()))
        self.setMinimumSize(760, 440)
        available = self.screen().availableGeometry()
        self.resize(min(1080, available.width() - 40), min(640, available.height() - 64))
        self.splitter.setSizes([160, 470, 360])
        if (
            isinstance(sizes, list)
            and len(sizes) == 3
            and all(isinstance(size, int) and 0 < size <= 10000 for size in sizes)
        ):
            self.splitter.setSizes(sizes)

        def load_places():
            try:
                self._places_results.put((places_loader(self._places_cancel), ""))
            except (MediaError, OSError) as exc:
                self._places_results.put(([], str(exc)))

        self.places_thread = threading.Thread(target=load_places, name="Utforsker-snarveier", daemon=True)
        self.places_thread.start()

    def _button(self, text, layout, callback):
        button = QPushButton(text)
        button.setAutoDefault(False)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _set_places(self, explorer):
        self.places.clear()
        seen = set()

        def group(title, entries):
            heading = QListWidgetItem(title)
            heading.setFlags(Qt.ItemFlag.NoItemFlags)
            font = heading.font()
            font.setBold(True)
            heading.setFont(font)
            self.places.addItem(heading)
            for name, path in entries:
                key = os.path.normcase(path)
                if not path or key in seen:
                    continue
                seen.add(key)
                item = QListWidgetItem(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon), name)
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setToolTip(path)
                self.places.addItem(item)

        if explorer:
            group("Hurtigtilgang", explorer)
        group(
            "Steder",
            [("Hjem", str(Path.home()))]
            + [
                (name, QStandardPaths.writableLocation(location))
                for name, location in (
                    ("Skrivebord", QStandardPaths.StandardLocation.DesktopLocation),
                    ("Nedlastinger", QStandardPaths.StandardLocation.DownloadLocation),
                    ("Dokumenter", QStandardPaths.StandardLocation.DocumentsLocation),
                    ("Videoer", QStandardPaths.StandardLocation.MoviesLocation),
                    ("Musikk", QStandardPaths.StandardLocation.MusicLocation),
                )
            ],
        )
        group("Stasjoner", [(drive.absoluteFilePath(), drive.absoluteFilePath()) for drive in QDir.drives()])

    def _place_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.navigate(path)

    def set_view(self, mode):
        self.view_mode = "grid" if mode == "grid" else "list"
        self.stack.setCurrentIndex(1 if self.view_mode == "grid" else 0)
        self.view_buttons[self.view_mode].setChecked(True)
        current = self.selection.currentIndex()
        if current.isValid():
            self.stack.currentWidget().scrollTo(current)

    def navigate(self, path, *, remember=True):
        directory = QDir(path)
        if not directory.exists():
            self.location.setText("Mappen er utilgjengelig. Kontroller stien eller tilkoblingen.")
            return False
        path = directory.absolutePath()
        self.selection.clear()
        self._clear_preview("Marker en fil for å se forhåndsvisning")
        self.current_directory = path
        index = self.model.index(path)
        for view in (self.list_view, self.grid_view):
            view.setRootIndex(index)
        self.address.setText(QDir.toNativeSeparators(path))
        self.location.setText("Velg filer. Ctrl/Shift markerer flere.")
        if remember:
            self._history = self._history[: self._history_index + 1] + [path]
            self._history_index = len(self._history) - 1
        self.back.setEnabled(self._history_index > 0)
        self.forward.setEnabled(self._history_index + 1 < len(self._history))
        self.up.setEnabled(not directory.isRoot())
        return True

    def go_back(self):
        if self._history_index > 0 and self.navigate(self._history[self._history_index - 1], remember=False):
            self._history_index -= 1
            self.back.setEnabled(self._history_index > 0)
            self.forward.setEnabled(True)

    def go_forward(self):
        if self._history_index + 1 < len(self._history) and self.navigate(
            self._history[self._history_index + 1], remember=False
        ):
            self._history_index += 1
            self.back.setEnabled(True)
            self.forward.setEnabled(self._history_index + 1 < len(self._history))

    def go_up(self):
        directory = QDir(self.current_directory)
        if directory.cdUp():
            self.navigate(directory.absolutePath())

    def _open_address(self):
        path = Path(self.address.text().strip().strip('"')).expanduser()
        if path.is_file():
            self.navigate(str(path.parent))
            self.selection.setCurrentIndex(
                self.model.index(str(path)),
                QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
            )
        else:
            self.navigate(str(path))

    def _toggle_filter(self):
        self.model.setNameFilters([] if self.all_files.isChecked() else MEDIA_FILTERS)

    def _activate(self, index):
        path = self.model.filePath(index)
        if self.model.isDir(index):
            self.navigate(path)
        else:
            self.accept_selection()

    def selected_paths(self):
        return [
            Path(self.model.filePath(index))
            for index in self.selection.selectedRows(0)
            if not self.model.isDir(index)
        ]

    def _selection_changed(self, *args):
        count = len(self.selected_paths())
        self.count.setText(
            f"{count} {'fil' if count == 1 else 'filer'} valgt" if count else "Ingen filer valgt"
        )
        self.import_button.setEnabled(count > 0)
        if not count:
            self._clear_preview("Marker en fil for å se forhåndsvisning")

    def _clear_preview(self, message):
        self.debounce.stop()
        self._probe_path = None
        self._probe_generation = self.probe.request()
        self.preview.show_item(None)
        self.preview.canvas.set_message(message)
        self.preview.filename.setText("Forhåndsvisning")

    def _current_changed(self, current, previous):
        if self._closed:
            return
        self._clear_preview("Marker en fil for å se forhåndsvisning")
        if current.isValid() and not self.model.isDir(current):
            self._probe_path = Path(self.model.filePath(current))
            self.preview.filename.setText(self._probe_path.name)
            self.preview.canvas.set_message("Henter filinformasjon …")
            self.debounce.start()

    def _start_probe(self):
        if self._probe_path and not self._closed:
            self._probe_generation = self.probe.request(self._probe_path)

    def _poll(self):
        while not self.probe.results.empty():
            generation, path, info, error = self.probe.results.get_nowait()
            if generation == self._probe_generation and not self._closed:
                if info:
                    self.preview.show_item(QueueItem(path, info=info))
                else:
                    self.preview.canvas.set_message("Kunne ikke forhåndsvise denne filen.")
                    self.preview.details.setText(
                        "Du kan fortsatt importere filen for å kontrollere formatet."
                    )
                    self.preview.details.setToolTip(error)
        while not self._places_results.empty():
            places, error = self._places_results.get_nowait()
            self._set_places(places)
            self.places_status.setText(
                "Hurtigtilgang kunne ikke leses. Bruk Utforsker … for alle snarveiene." if error else ""
            )
            self.places_status.setVisible(bool(error))

    def open_native(self):
        self._clear_preview("Marker en fil for å se forhåndsvisning")
        files, _ = QFileDialog.getOpenFileNames(
            self, "Importer lyd- og videofiler", self.current_directory, "Alle filer (*)"
        )
        if files:
            self.files = [Path(path) for path in files]
            self.accept()
        else:
            self._current_changed(self.selection.currentIndex(), None)

    def accept_selection(self):
        files = self.selected_paths()
        if files:
            self.files = files
            self.accept()

    def done(self, result):
        if not self._closed:
            self._closed = True
            self.debounce.stop()
            self.poll.stop()
            self._places_cancel.set()
            self.probe.stop()
            self.preview.shutdown()
        super().done(result)
