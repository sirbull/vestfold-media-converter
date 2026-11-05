"""Eksportprofil og avanserte innstillinger for valgte filer i køen."""

from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.engine import MediaEngine
from ..core.models import ExportSettings, MediaError, QueueItem
from ..core.profiles import (
    AUDIO_CODECS,
    AUDIO_CONTAINERS,
    CONTAINERS,
    VIDEO_CODECS,
    VIDEO_CONTAINERS,
    audio_choices,
    pixel_choices,
    preset_description,
    preset_keys,
    preset_settings,
    validate,
    video_choices,
)
from .widgets import RoundedComboBox, divider


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
        for key in preset_keys(self.info):
            try:
                candidate = preset_settings(key, self.info)
                if key != "standard":
                    validate(self.info, candidate, self.engine.encoders, self.engine.muxers)
                self.profile.addItem(candidate.name, key)
            except MediaError:
                pass
        if item.settings.name not in {self.profile.itemText(i) for i in range(self.profile.count())}:
            self.profile.addItem(item.settings.name, "custom")
        index = self.profile.findText(item.settings.name)
        self.profile.setCurrentIndex(max(0, index))
        self.description.setText(preset_description(self.profile.currentData(), self.info))
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
