import os
import threading
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .appearance import (
    DARK,
    LIGHT,
    CrestBadge,
    ImportArtwork,
    PathLabel,
    ProfileMotif,
    QueueDelegate,
    RoundedComboBox,
    ThemeSwitcher,
    asset_path,
    configure_typography,
    line_icon,
    stylesheet,
)
from .engine import MediaEngine
from .import_browser import ImportBrowser
from .models import ExportSettings, MediaError, QueueItem
from .preview import PreviewPanel
from .profiles import (
    AUDIO_CODECS,
    AUDIO_CONTAINERS,
    CONTAINERS,
    DESCRIPTIONS,
    VIDEO_CODECS,
    VIDEO_CONTAINERS,
    audio_choices,
    pixel_choices,
    preset_settings,
    validate,
    video_choices,
)
from .storage import load_preferences, preferred_output, save_preferences
from .workers import JobWorker, analyzed_item


def combo(items) -> QComboBox:
    widget = RoundedComboBox()
    for label, value in items:
        widget.addItem(label, value)
    return widget


def spin(minimum, maximum, value, suffix="") -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    widget.setSuffix(suffix)
    return widget


def choose(widget: QComboBox, value):
    index = widget.findData(value)
    if index >= 0:
        widget.setCurrentIndex(index)


def duration_text(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


def size_text(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class DropArea(QPushButton):
    def __init__(self):
        super().__init__()
        self.setObjectName("dropArea")
        self.setAccessibleName("Importer lyd- og videofiler")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addStretch()
        self.symbol = ImportArtwork()
        layout.addWidget(self.symbol, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = QLabel("Dra en fil hit\neller klikk for å velge fil")
        self.title.setObjectName("dropTitle")
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        self.hint = QLabel("Én fil, flere filer eller en hel mappe")
        self.hint.setObjectName("muted")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint)
        self.action_label = QLabel("Velg filer")
        self.action_label.setObjectName("dropAction")
        layout.addWidget(self.action_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        for label in self.findChildren(QLabel):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_compact(self, compact, *, tight=False):
        self.symbol.setVisible(not tight)
        self.symbol.setFixedSize(QSize(78, 50) if compact else QSize(124, 80))
        self.title.setText(
            "Dra en fil hit eller klikk for å velge fil"
            if compact
            else "Dra en fil hit\neller klikk for å velge fil"
        )
        self.layout().setContentsMargins(*(12, 10, 12, 10) if compact else (24, 24, 24, 24))
        self.layout().setSpacing(6 if compact else 12)


def divider():
    line = QFrame()
    line.setObjectName("divider")
    line.setFixedHeight(1)
    return line


class SettingsPanel(QWidget):
    apply_requested = Signal(object)
    preset_requested = Signal(str)

    def __init__(self, engine: MediaEngine):
        super().__init__()
        self.setObjectName("settingsPanel")
        self.engine = engine
        self.info = None
        self._loading = False
        self._original = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(12)
        self.heading = QLabel("Eksportinnstillinger")
        self.heading.setObjectName("sectionTitle")
        layout.addWidget(self.heading)
        self.selection = QLabel("Velg en fil for å se eksportinnstillinger.")
        self.selection.setObjectName("selectionName")
        self.selection.setWordWrap(True)
        layout.addWidget(self.selection)
        self.selection_detail = QLabel("Anbefalt profil velges automatisk.")
        self.selection_detail.setObjectName("selectionDetail")
        self.selection_detail.setWordWrap(True)
        layout.addWidget(self.selection_detail)
        layout.addWidget(divider())
        profile_label = QLabel("EKSPORTPROFIL")
        profile_label.setObjectName("eyebrow")
        layout.addWidget(profile_label)
        self.profile = RoundedComboBox()
        self.profile.setAccessibleName("Eksportprofil")
        layout.addWidget(self.profile)
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setObjectName("muted")
        layout.addWidget(self.description)
        self.notice = QLabel()
        self.notice.setObjectName("notice")
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.notice.hide()
        layout.addWidget(divider())
        self.toggle = QToolButton()
        self.toggle.setObjectName("advancedToggle")
        self.toggle.setText("Avanserte innstillinger")
        self.toggle.setCheckable(True)
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(self.toggle)
        self.advanced = QWidget()
        self.form = QFormLayout(self.advanced)
        self.form.setContentsMargins(0, 8, 0, 0)
        self.form.setVerticalSpacing(12)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.container = RoundedComboBox()
        self.vcodec = RoundedComboBox()
        self.quality_mode = combo([("Kvalitet (CRF)", "quality"), ("Bitrate", "bitrate")])
        self.quality = spin(0, 51, 21)
        self.vbitrate = spin(16, 500000, 6000, " kbit/s")
        self.preset = combo([(v, v) for v in ("ultrafast", "fast", "medium", "slow")])
        self.resolution = combo(
            [
                ("Original", ""),
                ("3840 × 2160", "3840x2160"),
                ("1920 × 1080", "1920x1080"),
                ("1280 × 720", "1280x720"),
                ("854 × 480", "854x480"),
                ("1080 × 1920", "1080x1920"),
            ]
        )
        self.fps = QLineEdit()
        self.fps.setPlaceholderText("Original · f.eks. 25 eller 30000/1001")
        self.aspect = combo([("Original", ""), *[(v, v) for v in ("16:9", "4:3", "1:1", "9:16")]])
        self.deinterlace = combo([("Automatisk", "auto"), ("På", "on"), ("Av", "off")])
        self.pixel = RoundedComboBox()
        self.track = RoundedComboBox()
        self.acodec = RoundedComboBox()
        self.abitrate = spin(32, 320, 192, " kbit/s")
        self.sample = combo(
            [
                ("Automatisk / original", 0),
                *[
                    (f"{v / 1000:g} kHz", v)
                    for v in (8000, 16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000, 192000)
                ],
            ]
        )
        self.channels = combo([("Automatisk · mono/stereo", 0), ("Mono", 1), ("Stereo", 2)])
        self.depth = combo([(f"{v}-bit", v) for v in (16, 24)])
        self.video_section = QLabel("VIDEO")
        self.audio_section = QLabel("LYD")
        for section in (self.video_section, self.audio_section):
            section.setObjectName("eyebrow")
        for label, field in (
            ("Format", self.container),
            ("Videokodek / GPU", self.vcodec),
            ("Kvalitetsstyring", self.quality_mode),
            ("Kvalitet · lavere er bedre", self.quality),
            ("Videobitrate", self.vbitrate),
            ("Encoder preset", self.preset),
            ("Oppløsning", self.resolution),
            ("Bildefrekvens", self.fps),
            ("Sideforhold", self.aspect),
            ("Deinterlacing", self.deinterlace),
            ("Pikselformat / fargedybde", self.pixel),
            ("Lydspor", self.track),
            ("Lydkodek", self.acodec),
            ("Lydbitrate", self.abitrate),
            ("Samplingsfrekvens", self.sample),
            ("Kanaler", self.channels),
            ("Bitdybde", self.depth),
        ):
            if field is self.vcodec:
                self.form.addRow(self.video_section)
            elif field is self.track:
                self.form.addRow(self.audio_section)
            field.setAccessibleName(label)
            self.form.addRow(label, field)
        self.gpu_note = QLabel("GPU-valg krever kompatibel maskinvare og driver. CPU brukes som standard.")
        self.gpu_note.setWordWrap(True)
        self.form.addRow(self.gpu_note)
        self.apply_button = QPushButton("Bruk på valgte filer")
        self.apply_button.setObjectName("softButton")
        self.form.addRow(self.apply_button)
        layout.addWidget(self.advanced)
        layout.addStretch()
        self.advanced.hide()
        self.toggle.toggled.connect(self._toggle)
        self.container.currentIndexChanged.connect(self._container_changed)
        self.vcodec.currentIndexChanged.connect(self._codec_changed)
        self.acodec.currentIndexChanged.connect(self._visibility)
        self.track.currentIndexChanged.connect(self._audio_changed)
        self.quality_mode.currentIndexChanged.connect(self._visibility)
        self.profile.currentIndexChanged.connect(self._profile_changed)
        self.apply_button.clicked.connect(self._apply)
        self.setEnabled(False)

    def _toggle(self, checked):
        self.advanced.setVisible(checked)
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    def show_items(self, items: list[QueueItem]):
        ready = [item for item in items if item.info and item.settings]
        self.setEnabled(bool(ready))
        if not ready:
            self.selection.setText("Velg en fil i køen")
            self.selection_detail.setText("Eksportvalg vises for valgte filer.")
            self.profile.clear()
            self.description.clear()
            self.notice.hide()
            return
        item = ready[0]
        self.info, self._original = item.info, item.settings
        self._loading = True
        self.selection.setText(item.path.name if len(ready) == 1 else f"{len(ready)} filer valgt")
        self.selection.setToolTip(str(item.path))
        self.selection_detail.setText(
            "Endringer gjelder alle valgte filer." if len(ready) > 1 else self.info.kind
        )
        self.profile.clear()
        self.profile.addItem("MP4 – Anbefalt" if self.info.video else "MP3 – Anbefalt", "standard")
        if self.info.video:
            for label, key in (
                ("Rask konvertering (stream copy)", "copy"),
                ("Mindre fil (H.265)", "small"),
                ("Høy kvalitet", "quality"),
                ("Redigeringsformat (ProRes)", "prores"),
                ("Kun lyd fra video", "audio"),
            ):
                try:
                    candidate = preset_settings(key, self.info)
                    validate(self.info, candidate, self.engine.encoders, self.engine.muxers)
                    self.profile.addItem(label, key)
                except MediaError:
                    pass
        if item.settings.name not in {self.profile.itemText(i) for i in range(self.profile.count())}:
            self.profile.addItem(item.settings.name, "custom")
        index = self.profile.findText(item.settings.name)
        self.profile.setCurrentIndex(max(0, index))
        self.description.setText(
            DESCRIPTIONS.get(self.profile.currentData(), "Egne innstillinger for valgte filer.")
        )
        note = ""
        if self.info.video and not self.info.audio:
            note = "Kilden inneholder ikke et lydspor. Videoen konverteres uten lyd."
        elif self.info.default_audio and self.info.default_audio.channels > 2:
            note = "Flerkanalslyd blir stereo med standardinnstillingene."
        if self.info.video and self.info.video.hdr:
            note += " HDR: velg 10-bit HEVC/AV1/VP9 eller stream copy i avansert modus."
        self.notice.setText(note)
        self.notice.setVisible(bool(note))
        self.container.clear()
        containers = list(VIDEO_CONTAINERS) if self.info.video else []
        if self.info.audio:
            containers += list(AUDIO_CONTAINERS)
        for key in containers:
            if CONTAINERS[key][2] in self.engine.muxers:
                self.container.addItem(CONTAINERS[key][0], key)
        choose(self.container, item.settings.container)
        self.track.clear()
        self.track.addItem("Standardspor (automatisk)", None)
        for stream in self.info.audio:
            self.track.addItem(
                f"Spor {stream.index} · {stream.language} · {stream.codec} · "
                f"{stream.channels} kanaler {stream.title}",
                stream.index,
            )
        choose(self.track, item.settings.audio_stream)
        self._populate_codecs()
        s = item.settings
        choose(self.vcodec, s.video_codec)
        choose(self.acodec, s.audio_codec)
        self._populate_pixels()
        for widget, value in (
            (self.pixel, s.pixel_format),
            (self.quality_mode, s.quality_mode),
            (self.preset, s.preset),
            (self.aspect, s.aspect),
            (self.deinterlace, s.deinterlace),
            (self.sample, s.sample_rate),
            (self.channels, s.channels),
            (self.depth, s.bit_depth),
            (self.resolution, f"{s.width}x{s.height}" if s.width else ""),
        ):
            choose(widget, value)
        for widget, value in (
            (self.quality, s.quality),
            (self.vbitrate, s.video_bitrate),
            (self.abitrate, s.audio_bitrate),
        ):
            widget.setValue(value)
        self.fps.setText(s.fps)
        self._loading = False
        self._visibility()

    def _populate_codecs(self):
        container = self.container.currentData()
        if not container or not self.info:
            return
        old_video, old_audio = self.vcodec.currentData(), self.acodec.currentData()
        self.vcodec.clear()
        if container in VIDEO_CONTAINERS:
            for key in video_choices(container, self.engine.encoders, self.info):
                self.vcodec.addItem(VIDEO_CODECS[key], key)
        self.acodec.clear()
        for key in audio_choices(container, self.engine.encoders, self.info, self.track.currentData()):
            self.acodec.addItem(AUDIO_CODECS[key], key)
        choose(self.vcodec, old_video)
        choose(self.acodec, old_audio)
        self._populate_pixels()

    def _populate_pixels(self):
        old = self.pixel.currentData()
        self.pixel.clear()
        for value in pixel_choices(self.vcodec.currentData()):
            self.pixel.addItem(value, value)
        choose(self.pixel, old)

    def _container_changed(self):
        if self._loading:
            return
        self._loading = True
        self._populate_codecs()
        self._loading = False
        self._visibility()

    def _codec_changed(self):
        if not self._loading:
            self._populate_pixels()
            self._visibility()

    def _audio_changed(self):
        if not self._loading:
            self._container_changed()

    def _visibility(self):
        if self._loading:
            return
        video = self.container.currentData() in VIDEO_CONTAINERS
        self.form.setRowVisible(self.video_section, video)
        codec = self.vcodec.currentData()
        transcode = video and codec != "copy"
        quality = self.quality_mode.currentData() == "quality"
        for field, visible in (
            (self.vcodec, video),
            (self.quality_mode, transcode and codec != "prores_ks"),
            (self.quality, transcode and quality and codec != "prores_ks"),
            (self.vbitrate, transcode and not quality and codec != "prores_ks"),
            (
                self.preset,
                transcode and codec in {"libx264", "libx265", "libsvtav1", "libvpx-vp9", "libaom-av1"},
            ),
            (self.resolution, transcode),
            (self.fps, transcode),
            (self.aspect, transcode),
            (self.deinterlace, transcode),
            (self.pixel, transcode),
            (self.gpu_note, video),
        ):
            self.form.setRowVisible(field, visible)
        audio = bool(self.info and self.info.audio)
        self.form.setRowVisible(self.audio_section, audio)
        acodec = self.acodec.currentData()
        for field, visible in (
            (self.track, audio),
            (self.acodec, audio),
            (self.abitrate, audio and acodec in {"libmp3lame", "aac", "libopus", "libvorbis"}),
            (self.sample, audio and acodec != "copy"),
            (self.channels, audio and acodec != "copy"),
            (self.depth, audio and acodec in {"flac", "alac"}),
        ):
            self.form.setRowVisible(field, visible)

    def _profile_changed(self):
        if not self._loading and self.profile.currentData() not in {None, "custom"}:
            self.preset_requested.emit(self.profile.currentData())

    def export_settings(self) -> ExportSettings:
        container = self.container.currentData()
        video = container in VIDEO_CONTAINERS
        codec = self.vcodec.currentData() if video else None
        resolution = self.resolution.currentData()
        width, height = map(int, resolution.split("x")) if resolution and codec != "copy" else (0, 0)
        audio = self.acodec.currentData() or "aac"
        return replace(
            self._original,
            name=f"Egendefinert · {CONTAINERS[container][0]}",
            container=container,
            video_codec=codec,
            audio_codec=audio,
            quality_mode=self.quality_mode.currentData(),
            quality=self.quality.value(),
            video_bitrate=self.vbitrate.value(),
            preset=self.preset.currentData(),
            width=width,
            height=height,
            fps=self.fps.text().strip() if codec and codec != "copy" else "",
            aspect=self.aspect.currentData() if codec and codec != "copy" else "",
            deinterlace=self.deinterlace.currentData() if codec and codec != "copy" else "auto",
            pixel_format=self.pixel.currentData() or "yuv420p",
            audio_bitrate=self.abitrate.value(),
            sample_rate=self.sample.currentData() if audio != "copy" else 0,
            channels=self.channels.currentData() if audio != "copy" else 0,
            bit_depth=self.depth.currentData(),
            audio_stream=self.track.currentData(),
        )

    def _apply(self):
        if self.info:
            self.apply_requested.emit(self.export_settings())


class MainWindow(QMainWindow):
    def __init__(self, engine: MediaEngine, *, initialize=True, preferences_path: Path | None = None):
        super().__init__()
        configure_typography()
        self.engine = engine
        self.preferences_path = preferences_path
        self.preferences = load_preferences(preferences_path)
        self.output_folder = preferred_output(self.preferences)
        self.items: list[QueueItem] = []
        self.thread = None
        self.worker = None
        self.cancel_event = threading.Event()
        self.busy = False
        self._closing = False
        self._run_items = []
        self._validation_failures = 0
        self._summary = None
        self._startup_positioned = False
        self.setWindowTitle("Vestfold media converter")
        self.setWindowIcon(QIcon(str(asset_path("vestfold-vapen.svg"))))
        self.setMinimumSize(760, 500)
        self.setAcceptDrops(True)
        central = QWidget()
        central.setObjectName("mainSurface")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.main_layout = layout
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)
        header = QHBoxLayout()
        header.setSpacing(14)
        self.brand_icon = CrestBadge()
        header.addWidget(self.brand_icon)
        title_block = QVBoxLayout()
        title_block.setSpacing(3)
        title = QLabel("Vestfold media converter")
        title.setObjectName("title")
        title_block.addWidget(title)
        header.addLayout(title_block)
        header.addStretch()
        self.profile_motif = ProfileMotif()
        header.addWidget(self.profile_motif)
        header.addSpacing(10)
        self.theme = ThemeSwitcher()
        self.theme.set_mode(self.preferences.get("theme", "system"))
        header.addWidget(self.theme)
        layout.addLayout(header)
        layout.addWidget(divider())
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        queue_heading = QLabel("Konverteringskø")
        queue_heading.setObjectName("sectionTitle")
        toolbar.addWidget(queue_heading)
        self.count = QLabel("Ingen filer")
        self.count.setObjectName("countBadge")
        toolbar.addWidget(self.count)
        toolbar.addStretch()
        self.add_files = QPushButton("Legg til filer")
        self.add_files.setObjectName("softButton")
        self.add_folder = QPushButton("Legg til mappe")
        self.remove = QPushButton("Fjern valgte")
        self.remove.setObjectName("quietButton")
        self.details = QPushButton("Detaljer")
        self.details.setObjectName("quietButton")
        self.settings_toggle = QPushButton("Eksportvalg")
        self.settings_toggle.setObjectName("quietButton")
        self.settings_toggle.setAccessibleName("Åpne eksportinnstillinger for valgte filer")
        self._compact = False
        self._tight = False
        for button in (self.add_files, self.add_folder):
            toolbar.addWidget(button)
        layout.addLayout(toolbar)
        self.queue_hint = QLabel("Video blir MP4. Lyd blir MP3. Vi velger formatet for deg.")
        self.queue_hint.setObjectName("muted")
        self.queue_hint.setWordWrap(True)
        layout.addWidget(self.queue_hint)
        self.splitter = QSplitter()
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(18)
        self.stack = QStackedWidget()
        self.drop_area = DropArea()
        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(12)
        empty_layout.addWidget(self.drop_area, 1)
        note = QLabel("Originalfilene dine beholdes alltid.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setObjectName("muted")
        empty_layout.addWidget(note)
        self.stack.addWidget(empty)
        self.table = QTableWidget(0, 4)
        self.table.setAccessibleName("Konverteringskø")
        self.table.setHorizontalHeaderLabels(["Fil", "Eksportprofil", "Størrelse", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setMouseTracking(True)
        self.table.setItemDelegate(QueueDelegate(self.table))
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(76)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(70)
        self.table.setColumnWidth(1, 166)
        self.table.setColumnWidth(2, 88)
        self.table.setColumnWidth(3, 140)
        self.table.setWordWrap(False)
        queue_card = QFrame()
        queue_card.setObjectName("queueCard")
        card_layout = QVBoxLayout(queue_card)
        card_layout.setContentsMargins(1, 8, 1, 4)
        card_layout.setSpacing(0)
        card_layout.addWidget(self.table, 1)
        card_layout.addWidget(divider())
        selection_bar = QHBoxLayout()
        selection_bar.setContentsMargins(12, 4, 10, 0)
        self.selection_count = QLabel("Ingen filer valgt")
        self.selection_count.setObjectName("muted")
        selection_bar.addWidget(self.selection_count)
        selection_bar.addStretch()
        for button in (self.details, self.remove, self.settings_toggle):
            selection_bar.addWidget(button)
        card_layout.addLayout(selection_bar)
        self.stack.addWidget(queue_card)
        self.splitter.addWidget(self.stack)
        self.panel = SettingsPanel(engine)
        self.panel_scroll = QScrollArea()
        self.panel_scroll.setObjectName("inspectorScroll")
        self.panel_scroll.setWidgetResizable(True)
        self.panel_scroll.setWidget(self.panel)
        self.preview = PreviewPanel(engine.ffmpeg)
        preview_scroll = QScrollArea()
        preview_scroll.setObjectName("inspectorScroll")
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setWidget(self.preview)
        self.inspector = QTabWidget()
        self.inspector.setObjectName("inspector")
        self.inspector.setMinimumWidth(320)
        self.inspector.addTab(preview_scroll, "Forhåndsvisning")
        self.inspector.addTab(self.panel_scroll, "Eksportvalg")
        self.inspector.setAccessibleName("Forhåndsvisning og eksportvalg for valgt fil")
        self.inspector.hide()
        self.inspector.currentChanged.connect(lambda index: self.preview.pause() if index != 0 else None)
        self.splitter.addWidget(self.inspector)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([780, 400])
        layout.addWidget(self.splitter, 1)
        destination = QFrame()
        self.destination_card = destination
        destination.setObjectName("destination")
        dest_card_layout = QVBoxLayout(destination)
        self.destination_layout = dest_card_layout
        dest_card_layout.setContentsMargins(20, 16, 20, 16)
        dest_card_layout.setSpacing(14)
        dest_layout = QHBoxLayout()
        dest_layout.setSpacing(12)
        self.folder_icon = QLabel()
        self.folder_icon.setFixedSize(28, 28)
        dest_layout.addWidget(self.folder_icon)
        destination_text = QVBoxLayout()
        destination_text.setSpacing(4)
        dest_title = QLabel("LAGRE RESULTATENE I")
        dest_title.setObjectName("eyebrow")
        self.destination = PathLabel(str(self.output_folder))
        self.destination.setToolTip(str(self.output_folder))
        self.destination.setAccessibleName("Målmappe")
        destination_text.addWidget(dest_title)
        destination_text.addWidget(self.destination)
        dest_layout.addLayout(destination_text, 1)
        self.change_folder = QPushButton("Endre mappe")
        self.change_folder.setObjectName("quietButton")
        self.open_folder = QPushButton("Åpne målmappe")
        dest_layout.addWidget(self.change_folder)
        dest_layout.addWidget(self.open_folder)
        dest_card_layout.addLayout(dest_layout)
        dest_card_layout.addWidget(divider())
        self.message = QLabel("Klar til å importere lyd og video.")
        self.message.setObjectName("muted")
        self.message.setWordWrap(True)
        self.message.setAccessibleName("Statusmelding")
        footer = QHBoxLayout()
        footer.setSpacing(12)
        self.total_progress = QProgressBar()
        self.total_progress.setAccessibleName("Samlet fremdrift")
        self.total_progress.setRange(0, 1000)
        self.total_progress.setTextVisible(False)
        self.total_progress.setValue(0)
        self.cancel = QPushButton("Avbryt")
        self.cancel.setEnabled(False)
        self.convert = QPushButton("Konverter")
        self.convert.setObjectName("primary")
        self.convert.setMinimumSize(220, 50)
        self.convert.setEnabled(False)
        footer.addWidget(self.message, 1)
        footer.addWidget(self.cancel)
        footer.addWidget(self.convert)
        dest_card_layout.addLayout(footer)
        dest_card_layout.addWidget(self.total_progress)
        self.total_progress.hide()
        self.cancel.hide()
        layout.addWidget(destination)
        self.add_files.clicked.connect(self.pick_files)
        self.drop_area.clicked.connect(self.pick_files)
        self.add_folder.clicked.connect(self.pick_folder)
        self.remove.clicked.connect(self.remove_selected)
        self.details.clicked.connect(self.show_details)
        self.settings_toggle.clicked.connect(self._open_export_settings)
        self.change_folder.clicked.connect(self.pick_destination)
        self.open_folder.clicked.connect(self.reveal_destination)
        self.convert.clicked.connect(self.start_conversion)
        self.cancel.clicked.connect(self.cancel_job)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.itemDoubleClicked.connect(lambda _: self.show_details())
        self.panel.apply_requested.connect(self.apply_settings)
        self.panel.preset_requested.connect(self.apply_preset)
        self.theme.modeChanged.connect(self.apply_theme)
        QApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        for text, shortcut, callback in (
            ("Importer filer", QKeySequence.StandardKey.Open, self.pick_files),
            ("Fjern valgte", QKeySequence.StandardKey.Delete, self.remove_selected),
        ):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            self.addAction(action)
        self.apply_theme()
        self.fit_to_available_screen()
        if initialize:
            self.start_job("initialize")
        self.drop_area.setFocus()

    def _system_theme_changed(self):
        if self.theme.mode() == "system":
            self.apply_theme()

    def _set_panel_visibility(self):
        self.inspector.setVisible(bool(self.items))

    def _open_export_settings(self):
        self._set_panel_visibility()
        self.inspector.setCurrentIndex(1)

    def fit_to_available_screen(self):
        """QScreen gir logiske mål og trekker fra oppgavelinjen, også ved høy DPI."""
        available = self.screen().availableGeometry()
        frame = self.frameGeometry()
        extra_width = max(16, frame.width() - self.width()) if self.isVisible() else 16
        extra_height = max(32, frame.height() - self.height()) if self.isVisible() else 40
        maximum_width = max(1, available.width() - extra_width - 24)
        maximum_height = max(1, available.height() - extra_height - 24)
        self.setMinimumSize(min(760, maximum_width), min(500, maximum_height))
        self.resize(min(1240, maximum_width), min(780, maximum_height))
        self._update_density()
        positioned = self.frameGeometry()
        positioned.moveCenter(available.center())
        self.move(positioned.topLeft())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._startup_positioned:
            self._startup_positioned = True
            # Native ramme og tittellinje er kjent etter første visning.
            QTimer.singleShot(0, self.fit_to_available_screen)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "convert"):
            self._update_density()

    def _update_density(self):
        compact = self.width() < 1050 or self.height() < 720
        tight = self.height() < 620
        changed = compact != self._compact
        if changed or tight != self._tight:
            self._compact, self._tight = compact, tight
            self.setProperty("compact", compact)
            self.drop_area.set_compact(compact, tight=tight)
            self.profile_motif.setVisible(not compact)
            self.brand_icon.setFixedSize(QSize(48, 48) if compact else QSize(64, 64))
            self.main_layout.setContentsMargins(*(18, 16, 18, 16) if compact else (28, 24, 28, 24))
            self.main_layout.setSpacing(10 if compact else 20)
            self.destination_layout.setContentsMargins(*(14, 10, 14, 10) if compact else (20, 16, 20, 16))
            self.destination_layout.setSpacing(8 if compact else 14)
            self.convert.setMinimumSize(QSize(200, 42) if compact else QSize(220, 50))
            self.table.verticalHeader().setDefaultSectionSize(64 if compact else 76)
            if changed:
                self.apply_theme()
        for column in (1, 2):
            self.table.setColumnHidden(column, self.width() < 1100 and self.inspector.isVisible())

    def apply_theme(self):
        mode = self.theme.mode()
        dark = mode == "dark" or (
            mode == "system" and QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        )
        colors = DARK if dark else LIGHT
        self.setStyleSheet(stylesheet(colors))
        self.theme.set_colors(colors)
        for dropdown in self.findChildren(RoundedComboBox):
            dropdown.set_popup_colors(colors)
        self.table.setProperty("dark", dark)
        self.table.viewport().update()
        self.folder_icon.setPixmap(line_icon("folder", colors["muted"]).pixmap(24, 24))
        self.drop_area.symbol.set_colors(colors)
        self.profile_motif.set_colors(colors)
        for button, icon in (
            (self.add_files, "plus"),
            (self.add_folder, "folder"),
            (self.remove, "close"),
            (self.details, "info"),
            (self.settings_toggle, "settings"),
        ):
            icon_color = colors["text"] if button is self.add_files else colors["muted"]
            button.setIcon(line_icon(icon, icon_color))
            button.setIconSize(QSize(18, 18))
        self.convert.setIcon(line_icon("play", colors["primary_text"]))
        self.convert.setIconSize(QSize(20, 20))
        self.preferences["theme"] = mode

    def pick_files(self):
        if not self.busy:
            browser = ImportBrowser(
                self.engine,
                self,
                view=self.preferences.get("import_view", "list"),
                sizes=self.preferences.get("import_splitter"),
            )
            try:
                browser.exec()
                self.preferences["import_view"] = browser.view_mode
                self.preferences["import_splitter"] = browser.splitter.sizes()
                self._save()
                if browser.files:
                    self.import_files(browser.files)
            finally:
                browser.reject()
                browser.deleteLater()

    def pick_folder(self):
        if not self.busy:
            folder = QFileDialog.getExistingDirectory(self, "Velg mappe med medier")
            if folder:
                self.import_files([Path(folder)])

    def dragEnterEvent(self, event):
        if (
            not self.busy
            and event.mimeData().hasUrls()
            and all(u.isLocalFile() for u in event.mimeData().urls())
        ):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.busy:
            self.import_files([Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()

    def import_files(self, paths: list[Path]):
        if paths and not self.busy:
            self.start_job("analyze", paths=paths, known=[os.path.normcase(str(i.path)) for i in self.items])

    def start_job(self, mode, **kwargs):
        self.busy = True
        self._summary = None
        self.cancel_event = threading.Event()
        self.thread = QThread(self)
        self.worker = JobWorker(self.engine, mode, self.cancel_event, **kwargs)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.found.connect(self.on_found)
        self.worker.analyzed.connect(self.on_analyzed)
        self.worker.failed.connect(self.on_failed)
        self.worker.starting.connect(self.on_starting)
        self.worker.progress.connect(self.on_progress)
        self.worker.converted.connect(self.on_converted)
        self.worker.done.connect(self.on_done)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.job_finished)
        self.thread.finished.connect(self.thread.deleteLater)
        self.message.setText(
            {
                "initialize": "Gjør medieverktøyene klare …",
                "analyze": "Analyserer filer …",
                "convert": "Konverterer …",
            }[mode]
        )
        if mode != "convert":
            self.total_progress.setRange(0, 0)
        self.update_controls()
        self.thread.start()

    def selected_items(self):
        return [self.items[index.row()] for index in self.table.selectionModel().selectedRows()]

    def selection_changed(self):
        if not self.busy:
            self.panel.show_items(self.selected_items())
        selected = self.selected_items()
        current_row = self.table.currentRow()
        current = self.items[current_row] if 0 <= current_row < len(self.items) else None
        item = current if current in selected else next(iter(selected), None)
        self.preview.show_item(item)
        self.update_controls()

    def update_controls(self):
        ready_count = sum(bool(i.info and i.settings and i.status != "Fullført") for i in self.items)
        ready = bool(ready_count)
        for button in (self.add_files, self.add_folder, self.drop_area, self.change_folder):
            button.setEnabled(not self.busy)
        self.remove.setEnabled(not self.busy and bool(self.selected_items()))
        self.details.setEnabled(bool(self.selected_items()))
        self.panel.setEnabled(not self.busy and any(i.info for i in self.selected_items()))
        self.convert.setEnabled(not self.busy and ready and bool(self.engine.encoders))
        self.cancel.setEnabled(self.busy and not self.cancel_event.is_set())
        self.cancel.setVisible(self.busy)
        self.settings_toggle.setEnabled(bool(self.items))
        self.total_progress.setVisible(self.busy or bool(self._run_items))
        self.count.setText(
            "1 fil" if len(self.items) == 1 else f"{len(self.items)} filer" if self.items else "Ingen filer"
        )
        selected = len(self.selected_items())
        self.selection_count.setText(f"{selected} valgt" if selected else "Velg en fil for eksportvalg")
        self.convert.setText(f"Konverter {ready_count} filer" if ready_count > 1 else "Konverter")
        for column in (1, 2):
            self.table.setColumnHidden(column, self.width() < 1100 and self.inspector.isVisible())

    def row_for(self, id_):
        return next(i for i, item in enumerate(self.items) if item.id == id_)

    def render_row(self, row):
        item = self.items[row]
        info = item.info
        formats = info.format_name.split(",") if info else []
        suffix = item.path.suffix.lower().lstrip(".")
        original_format = (
            suffix.upper()
            if suffix in formats
            else (
                "MP4 / MOV"
                if "mov" in formats and "mp4" in formats
                else formats[0].upper()
                if formats
                else "—"
            )
        )
        metadata = (
            f"{info.kind}  ·  {original_format}  ·  {duration_text(info.duration)}  ·  {size_text(info.size)}"
            if info
            else "Analyserer medieinnhold …"
        )
        values = [
            item.path.name,
            item.settings.name if item.settings else "—",
            size_text(info.size) if info else "—",
            f"Konverterer · {item.progress:.0%}" if item.status == "Konverterer" else item.status,
        ]
        for column, value in enumerate(values):
            cell = QTableWidgetItem(value)
            cell.setData(
                Qt.ItemDataRole.UserRole,
                {
                    "subtitle": metadata,
                    "video": bool(info and info.video),
                    "state": item.status,
                    "progress": item.progress,
                    "error": item.error,
                },
            )
            if column == 0:
                cell.setData(Qt.ItemDataRole.AccessibleTextRole, f"{item.path.name}. {metadata}")
            cell.setToolTip(item.error or f"{item.path}\n{metadata}\n{item.output or ''}")
            self.table.setItem(row, column, cell)

    def on_found(self, item):
        self.items.append(item)
        self.table.setRowCount(len(self.items))
        self.render_row(len(self.items) - 1)
        self.stack.setCurrentIndex(1)
        self._set_panel_visibility()
        self.count.setText(f"{len(self.items)} filer")

    def on_analyzed(self, id_, info):
        row = self.row_for(id_)
        analyzed_item(self.items[row], info)
        self.render_row(row)
        if self.table.currentRow() == row:
            self.preview.show_item(self.items[row])

    def on_failed(self, id_, error):
        row = self.row_for(id_)
        self.items[row].error = error
        self.items[row].status = "Avbrutt" if error.startswith("Avbrutt") else "Feil · se detaljer"
        self.render_row(row)

    def on_starting(self, id_):
        row = self.row_for(id_)
        self.items[row].status = "Konverterer"
        self.items[row].error = ""
        self.render_row(row)

    def on_progress(self, id_, value):
        row = self.row_for(id_)
        self.items[row].progress = value
        self.render_row(row)
        self._update_total()

    def _update_total(self):
        if self._run_items:
            # Lik vekt per fil gir stabil total også når kildevarighet er ukjent.
            total = sum(1 if i.status == "Fullført" or i.error else i.progress for i in self._run_items)
            self.total_progress.setValue(round(1000 * total / len(self._run_items)))

    def on_converted(self, id_, output):
        row = self.row_for(id_)
        item = self.items[row]
        item.output, item.progress, item.status = output, 1.0, "Fullført"
        self.render_row(row)
        self._update_total()

    def on_done(self, summary):
        self._summary = summary

    def job_finished(self):
        self.busy = False
        self.thread = self.worker = None
        self.total_progress.setRange(0, 1000)
        summary = self._summary or {"fatal": "Arbeidet ble avsluttet uventet."}
        if summary.get("fatal"):
            self.message.setText(f"Kunne ikke fullføre: {summary['fatal']}")
        elif summary.get("mode") == "convert":
            for item in self._run_items:
                if item.status == "I kø":
                    item.status = "Klar"
                    self.render_row(self.row_for(item.id))
            prefix = "Avbrutt." if summary["cancelled"] else "Ferdig!"
            failures = summary["failed"] + self._validation_failures
            error_text = f" {failures} feil – velg filen og se Detaljer." if failures else ""
            self.message.setText(
                f"{prefix} {summary['ok']} filer konvertert.{error_text} Resultatene ligger i målmappen."
            )
            self._update_total()
        elif summary.get("mode") == "analyze":
            ready_text = "1 fil er klar." if summary["ok"] == 1 else f"{summary['ok']} filer er klare."
            error_text = (
                f" {summary['failed']} kunne ikke analyseres – se Detaljer." if summary["failed"] else ""
            )
            self.message.setText(
                f"{ready_text}{error_text} Trykk Konverter for å starte."
                if not summary["cancelled"]
                else "Import avbrutt."
            )
            self.total_progress.setValue(0)
            if self.items and not self.selected_items():
                self.table.selectRow(next((n for n, i in enumerate(self.items) if i.info), 0))
            self.convert.setFocus()
        else:
            self.message.setText("Klar til å importere lyd og video.")
        self.panel.show_items(self.selected_items())
        self.selection_changed()
        if summary.get("mode") == "analyze" and summary.get("ok"):
            self.queue_hint.setText(
                "Filene er klare. Bruk anbefalt profil, eller velg en fil for å endre eksporten."
            )
        self.update_controls()
        if self._closing:
            self.close()

    def start_conversion(self):
        if self.busy:
            return
        items = [i for i in self.items if i.info and i.settings and i.status != "Fullført"]
        if not items:
            return
        valid = []
        for item in items:
            try:
                validate(item.info, item.settings, self.engine.encoders, self.engine.muxers)
                valid.append(item)
            except MediaError as exc:
                self.on_failed(item.id, str(exc))
        self._validation_failures = len(items) - len(valid)
        if not valid:
            self.message.setText("Eksportinnstillingene må endres. Velg en fil og åpne Detaljer.")
            return
        self._run_items = valid
        for item in valid:
            item.progress, item.status, item.error = 0, "I kø", ""
            self.render_row(self.row_for(item.id))
        self.total_progress.setValue(0)
        self.start_job("convert", items=valid, folder=self.output_folder)

    def apply_preset(self, key):
        self._apply_to_selected(lambda item: preset_settings(key, item.info))

    def apply_settings(self, settings):
        self._apply_to_selected(lambda _: settings)

    def _apply_to_selected(self, factory):
        if self.busy:
            return
        selected = [i for i in self.selected_items() if i.info]
        try:
            changes = [(item, factory(item)) for item in selected]
            for item, settings in changes:
                validate(item.info, settings, self.engine.encoders, self.engine.muxers)
        except MediaError as exc:
            self.message.setText(str(exc))
            self.panel.show_items(selected)
            return
        for item, settings in changes:
            item.settings, item.status, item.error, item.progress = settings, "Klar", "", 0
            self.render_row(self.row_for(item.id))
        self.panel.show_items(selected)
        self.message.setText(f"Eksportprofil oppdatert for {len(changes)} filer.")
        self.update_controls()

    def remove_selected(self):
        if self.busy:
            return
        for index in sorted(
            (index.row() for index in self.table.selectionModel().selectedRows()), reverse=True
        ):
            self.items.pop(index)
            self.table.removeRow(index)
        if not self.items:
            self.stack.setCurrentIndex(0)
            self.inspector.hide()
            self.queue_hint.setText("Video blir MP4. Lyd blir MP3. Vi velger formatet for deg.")
            self._run_items = []
        self.update_controls()

    def show_details(self):
        selected = self.selected_items()
        if selected:
            box = QMessageBox(self)
            box.setWindowTitle("Fildetaljer")
            box.setText("\n\n".join(f"{i.path.name}\n{i.error or i.status}" for i in selected))
            box.setDetailedText(
                "\n\n".join(f"Kilde: {i.path}\nResultat: {i.output or '—'}" for i in selected)
            )
            box.exec()

    def pick_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Velg målmappe", str(self.output_folder))
        if folder:
            self.output_folder = Path(folder)
            self.destination.setText(folder)
            self.preferences["output"] = folder
            self._save()

    def reveal_destination(self):
        try:
            self.output_folder.mkdir(parents=True, exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_folder))):
                self.message.setText("Kunne ikke åpne målmappen i Filutforsker.")
        except OSError as exc:
            self.message.setText(f"Kunne ikke åpne målmappen: {exc}")

    def cancel_job(self):
        self.cancel_event.set()
        self.cancel.setEnabled(False)
        self.message.setText("Avbryter og rydder opp i midlertidig fil …")

    def _save(self):
        try:
            save_preferences(self.preferences, self.preferences_path)
        except OSError:
            self.message.setText("Kunne ikke lagre innstillingene lokalt.")

    def closeEvent(self, event):
        self.preview.shutdown()
        if self.busy:
            self._closing = True
            self.cancel_job()
            event.ignore()
        else:
            self._save()
            event.accept()
