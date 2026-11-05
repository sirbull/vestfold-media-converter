"""File import with shared list/grid selection and cancellable FFmpeg preview."""

import os
import queue
import threading
from pathlib import Path

from PySide6.QtCore import QDir, QItemSelectionModel, QModelIndex, QSize, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QFrame,
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
    QWidget,
)

from .appearance import IconButton
from .background import LatestRequest
from .models import MediaError, QueueItem
from .path_bar import PathBar
from .preview import PreviewPanel
from .search_options import SearchOptions
from .system_places import explorer_places
from .windows_search import MEDIA_FILTERS, windows_search


class SelectionProbe(LatestRequest):
    def __init__(self, engine):
        super().__init__(engine.analyze, "Importforhåndsvisning")


class BrowserFileModel(QFileSystemModel):
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            labels = {0: "Navn", 1: "Størrelse", 2: "Type", 3: "Endret"}
            if section in labels:
                return labels[section]
        return super().headerData(section, orientation, role)


class ImportBrowser(QDialog):
    def __init__(
        self,
        engine,
        parent=None,
        *,
        directory=None,
        view="list",
        sizes=None,
        places_loader=explorer_places,
        search_loader=windows_search,
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
        self.searcher = LatestRequest(
            lambda request, cancel: search_loader(
                request[0], cancel, all_files=request[1], scope=request[2], criteria=request[3]
            ),
            "Windows-søk",
        )
        self.is_search = False
        self._search_generation = 0
        self._search_query = ""
        self._places_cancel = threading.Event()
        self._places_results = queue.SimpleQueue()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        toolbar = QHBoxLayout()
        self.back = IconButton("arrow_left", "Tilbake")
        self.forward = IconButton("arrow_right", "Frem")
        self.up = IconButton("arrow_up", "Opp én mappe")
        for button, callback in (
            (self.back, self.go_back),
            (self.forward, self.go_forward),
            (self.up, self.go_up),
        ):
            button.setObjectName("browserNavButton")
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(callback)
            toolbar.addWidget(button)
        self.address_bar = PathBar(framed=True)
        self.address_bar.folderClicked.connect(self.navigate)
        self.address = self.address_bar.editor
        self.address.returnPressed.connect(self._open_address)
        toolbar.addWidget(self.address_bar, 1)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("browserSearch")
        self.search_input.setAccessibleName("Søk etter filnavn med Windows Search")
        self.search_input.setPlaceholderText("Søk filnavn …")
        self.search_input.setToolTip("Søk i mappen du står i, med undermapper. Bare indekserte filer vises.")
        self.search_input.setMinimumWidth(80)
        self.search_input.setMaxLength(200)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.start_search)
        self.search_input.textChanged.connect(self._search_edited)
        layout.addLayout(toolbar)
        views = QHBoxLayout()
        self.location = QLabel("Velg filer. Ctrl/Shift markerer flere.")
        self.location.setObjectName("muted")
        self.location.setWordWrap(True)
        views.addWidget(self.location, 1)
        self.reveal_folder = self._button("Vis mappe", views, self.reveal_selected)
        self.reveal_folder.setVisible(False)
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
        self.normal_selection = self.selection
        self.search_model = QStandardItemModel(self)
        self.search_model.setHorizontalHeaderLabels(["Navn", "Mappe"])
        self.search_selection = QItemSelectionModel(self.search_model, self)
        self.stack = QStackedWidget()
        self.stack.setMinimumWidth(220)
        self.file_pane = QFrame()
        self.file_pane.setObjectName("browserPane")
        file_layout = QVBoxLayout(self.file_pane)
        # Listen går helt ut til rammen; litt luft nederst holder de runde hjørnene synlige.
        file_layout.setContentsMargins(0, 8, 0, 6)
        file_layout.setSpacing(8)
        self.file_toolbar = QWidget()
        file_tools = QHBoxLayout(self.file_toolbar)
        file_tools.setContentsMargins(8, 0, 8, 0)
        file_tools.setSpacing(6)
        file_tools.addWidget(self.search_input, 1)
        self.search_button = IconButton("search", "Søk etter filnavn med Windows Search")
        self.search_button.setObjectName("browserViewButton")
        self.search_button.setIconSize(QSize(16, 16))
        self.search_button.clicked.connect(self.start_search)
        file_tools.addWidget(self.search_button)
        self.view_group = QButtonGroup(self)
        self.view_buttons = {}
        for index, (mode, label) in enumerate((("list", "Listevisning"), ("grid", "Rutenettvisning"))):
            button = IconButton(mode, label)
            button.setObjectName("browserViewButton")
            button.setIconSize(QSize(16, 16))
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, m=mode: self.set_view(m))
            self.view_group.addButton(button, index)
            self.view_buttons[mode] = button
            file_tools.addWidget(button)
        file_layout.addWidget(self.file_toolbar)
        self.search_options = SearchOptions(getattr(parent, "colors", None))
        self.search_options.hide()
        self.search_options.changed.connect(lambda: self.search_timer.start())
        file_layout.addWidget(self.search_options)
        file_layout.addWidget(self.stack, 1)
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
        self.splitter.addWidget(self.file_pane)
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
        # Endringer i søkekriteriene oppdaterer treffene etter en kort pause, som i Finder.
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(400)
        self.search_timer.timeout.connect(self._run_search)
        self.poll = QTimer(self)
        self.poll.setInterval(60)
        self.poll.timeout.connect(self._poll)
        self.poll.start()
        for key, callback in (
            ("Alt+Left", self.go_back),
            ("Alt+Right", self.go_forward),
            ("Alt+Up", self.go_up),
            ("Ctrl+L", self.address_bar.start_edit),
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

    def _use_model(self, model):
        if self.list_view.model() is model:
            return
        self.selection.currentChanged.disconnect(self._current_changed)
        self.selection.selectionChanged.disconnect(self._selection_changed)
        self.selection = self.normal_selection if model is self.model else self.search_selection
        for view in (self.list_view, self.grid_view):
            view.setModel(model)
            temporary = view.selectionModel()
            view.setSelectionModel(self.selection)
            temporary.deleteLater()
        self.selection.currentChanged.connect(self._current_changed)
        self.selection.selectionChanged.connect(self._selection_changed)
        self.selection.clear()
        self._selection_changed()
        self.list_view.setColumnWidth(0, 240)
        self.list_view.setColumnWidth(1, 240 if model is self.search_model else 80)
        self.list_view.hideColumn(2)

    def _search_edited(self, text):
        if not self.is_search or text.strip() == self._search_query:
            return
        self._search_generation = self.searcher.request()
        if not text.strip():
            self.navigate(self.current_directory)
        else:
            self.search_model.removeRows(0, self.search_model.rowCount())
            self._clear_preview("Trykk Enter for å søke")
            self.location.setText("Trykk Enter for nytt søk i Windows-indeksen")

    def start_search(self):
        text = self.search_input.text().strip()
        if not text:
            if self.is_search:
                self.navigate(self.current_directory)
            return
        if not self.is_search:
            # Valg av sted og kriterier vises først når man har søkt.
            self.search_options.reset()
            self.search_options.set_folder(self.current_directory)
            self.search_options.show()
        self.is_search = True
        self._search_query = text
        self._use_model(self.search_model)
        self.reveal_folder.show()
        for view in (self.list_view, self.grid_view):
            view.setRootIndex(QModelIndex())
        self._run_search()

    def _scope_text(self):
        scope = self.search_options.scope()
        return f"i {self.search_options.this_folder.text()}" if scope else "på denne PC-en"

    def _run_search(self):
        self.search_timer.stop()
        if not self.is_search or self._closed:
            return
        self.search_model.removeRows(0, self.search_model.rowCount())
        self.selection.clear()
        self._clear_preview("Søker etter filer …")
        self.location.setText(f"Søker {self._scope_text()} …")
        self.location.setToolTip("Søket omfatter bare filene Windows har indeksert")
        options = self.search_options
        request = (self._search_query, self.all_files.isChecked(), options.scope(), options.criteria())
        self._search_generation = self.searcher.request(request)

    def _show_search(self, matches, error):
        if error:
            self.location.setText(
                error if "for lang tid" in error else "Windows-søk er utilgjengelig. Prøv Utforsker …"
            )
            self.location.setToolTip(error)
            self.preview.canvas.set_message("Kunne ikke søke. Du kan fortsatt bla i mappene.")
            return
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        for path in matches.paths:
            name = QStandardItem(icon, path.name)
            name.setData(str(path), Qt.ItemDataRole.UserRole)
            name.setToolTip(str(path))
            folder = QStandardItem(QDir.toNativeSeparators(str(path.parent)))
            folder.setToolTip(str(path.parent))
            self.search_model.appendRow([name, folder])
        count = len(matches.paths)
        self.location.setText(
            f"Viser de første {count} treffene {self._scope_text()}. Begrens søket."
            if matches.limited
            else f"{count} treff {self._scope_text()}"
            if count
            else f"Ingen treff {self._scope_text()}. Bare indekserte filer vises."
        )
        self.preview.canvas.set_message("Marker et søkeresultat for å se forhåndsvisning")

    def reveal_selected(self):
        current = self.selection.currentIndex()
        if not current.isValid():
            rows = self.selection.selectedRows(0)
            if not rows:
                return
            current = rows[0]
        path = self._index_path(current)
        if self.navigate(str(path.parent)):
            self.selection.setCurrentIndex(
                self.model.index(str(path)),
                QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
            )

    def navigate(self, path, *, remember=True):
        directory = QDir(path)
        if not directory.exists():
            self.location.setText("Mappen er utilgjengelig. Kontroller stien eller tilkoblingen.")
            return False
        path = directory.absolutePath()
        self._search_generation = self.searcher.request()
        self.is_search = False
        self.search_timer.stop()
        self.search_input.clear()
        self.search_options.hide()
        self.reveal_folder.hide()
        self._use_model(self.model)
        self.selection.clear()
        self._clear_preview("Marker en fil for å se forhåndsvisning")
        self.current_directory = path
        name = Path(path).name or path.rstrip("\\/")
        self.search_input.setPlaceholderText(f"Søk i «{name}» …")
        index = self.model.index(path)
        for view in (self.list_view, self.grid_view):
            view.setRootIndex(index)
        self.address_bar.set_path(path)
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
        if self.is_search:
            self._run_search()

    def _activate(self, index):
        path = self._index_path(index)
        if self._index_is_dir(index):
            self.navigate(str(path))
        else:
            self.accept_selection()

    def selected_paths(self):
        return [
            self._index_path(index)
            for index in self.selection.selectedRows(0)
            if not self._index_is_dir(index)
        ]

    def _index_path(self, index):
        if index.model() is self.search_model:
            return Path(index.siblingAtColumn(0).data(Qt.ItemDataRole.UserRole))
        return Path(self.model.filePath(index))

    def _index_is_dir(self, index):
        return index.model() is self.model and self.model.isDir(index)

    def _selection_changed(self, *args):
        count = len(self.selected_paths())
        self.count.setText(
            f"{count} {'fil' if count == 1 else 'filer'} valgt" if count else "Ingen filer valgt"
        )
        self.import_button.setEnabled(count > 0)
        self.reveal_folder.setEnabled(count > 0)
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
        if current.isValid() and not self._index_is_dir(current):
            self._probe_path = self._index_path(current)
            self.preview.filename.setText(self._probe_path.name)
            self.preview.canvas.set_message("Henter filinformasjon …")
            self.debounce.start()

    def _start_probe(self):
        if self._probe_path and not self._closed:
            self._probe_generation = self.probe.request(self._probe_path)

    def _poll(self):
        while not self.searcher.results.empty():
            generation, _request, matches, error = self.searcher.results.get_nowait()
            if generation == self._search_generation and self.is_search and not self._closed:
                self._show_search(matches, error)
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
            self.search_timer.stop()
            self.poll.stop()
            self._places_cancel.set()
            self.probe.stop()
            self.searcher.stop()
            self.preview.shutdown()
        super().done(result)
