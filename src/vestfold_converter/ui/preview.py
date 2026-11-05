"""Forhåndsvisning av valgt fil ved siden av køen og i importbrowseren."""

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..core.models import QueueItem
from ..core.playback import AudioPlayer, PreviewDecoder
from .details import duration_text
from .icons import IconButton
from .widgets import PathLabel


class VideoCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.image = QImage()
        self.message = "Velg en fil i køen"
        self.setMinimumSize(200, 100)
        self.setMaximumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName("Videoforhåndsvisning")

    def sizeHint(self):
        return QSize(360, 124)

    def set_message(self, message):
        self.image = QImage()
        self.message = message
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#090f14"))
        painter.drawRoundedRect(QRectF(self.rect()), 9, 9)
        if not self.image.isNull():
            size = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(
                (self.width() - size.width()) / 2,
                (self.height() - size.height()) / 2,
                size.width(),
                size.height(),
            )
            painter.drawImage(target, self.image)
        else:
            painter.setPen(QColor("#c3d0da"))
            painter.drawText(
                self.rect().adjusted(16, 12, -16, -12),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self.message,
            )


class PreviewPanel(QWidget):
    frame_ready = Signal(float)

    def __init__(self, ffmpeg: Path):
        super().__init__()
        self.setObjectName("previewPanel")
        self.decoder = PreviewDecoder(ffmpeg)
        self.audio = AudioPlayer(ffmpeg)
        self.audio_only = False
        self.info = None
        self.generation = 0
        self.position = 0.0
        self.playing = False
        self._key = None
        self._closed = False
        self._resume = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.filename = PathLabel("Velg en fil i køen")
        self.filename.setObjectName("selectionName")
        layout.addWidget(self.filename)
        self.canvas = VideoCanvas()
        layout.addWidget(self.canvas, 1)
        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.skip_back = IconButton("backward", "Hopp 5 sekunder bakover")
        self.play = IconButton("play_filled", "Spill av forhåndsvisning")
        self.skip_forward = IconButton("forward", "Hopp 5 sekunder fremover")
        for button in (self.skip_back, self.play, self.skip_forward):
            button.setObjectName("previewControl")
            button.setFixedSize(32, 32)
            button.setEnabled(False)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 10000)
        self.seek.setAccessibleName("Tidspunkt i forhåndsvisningen")
        self.seek.setEnabled(False)
        self.seek.setMinimumWidth(48)
        self.time = QLabel("00:00:00 / 00:00:00")
        self.time.setObjectName("previewTime")
        controls.addWidget(self.skip_back)
        controls.addWidget(self.play)
        controls.addWidget(self.skip_forward)
        controls.addWidget(self.seek, 1)
        layout.addLayout(controls)
        layout.addWidget(self.time)
        self.details = QLabel()
        self.details.setObjectName("muted")
        self.details.setWordWrap(True)
        layout.addWidget(self.details)
        # Tar bare plass når videoboksen er skjult for lydfiler.
        layout.addStretch()
        self.play.clicked.connect(self.toggle_play)
        self.skip_back.clicked.connect(lambda: self.skip_seconds(-5))
        self.skip_forward.clicked.connect(lambda: self.skip_seconds(5))
        self.seek.sliderPressed.connect(self._start_seek)
        self.seek.sliderReleased.connect(self._finish_seek)
        self.seek.valueChanged.connect(self._seek_changed)
        self.seek_timer = QTimer(self)
        self.seek_timer.setSingleShot(True)
        self.seek_timer.setInterval(160)
        self.seek_timer.timeout.connect(self._request_frame)
        self.timer = QTimer(self)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def show_item(self, item: QueueItem | None):
        if self._closed:
            return
        key = (item.id, item.info) if item else None
        if key == self._key:
            return
        self._key = key
        self.generation = self.decoder.request(None)
        self.audio.stop()
        self.seek_timer.stop()
        self.info = item.info if item else None
        self.audio_only = bool(self.info and not self.info.video and self.info.audio)
        self.canvas.setVisible(not self.audio_only)
        self.playing = self._resume = False
        self._update_play_button()
        self.play.setEnabled(False)
        self.skip_back.setEnabled(False)
        self.skip_forward.setEnabled(False)
        self.seek.setEnabled(False)
        self.filename.setText(item.path.name if item else "Velg en fil i køen")
        self.filename.setToolTip(str(item.path) if item else "")
        self.details.clear()
        self.position = 0.0
        self._update_time()
        if not item:
            self.canvas.set_message("Velg en fil i køen")
        elif not self.info:
            self.canvas.set_message("Forhåndsvisning er ikke tilgjengelig før filen er analysert.")
        elif self.audio_only:
            self.canvas.set_message("")
            enabled = self.info.duration > 0
            for control in (self.play, self.seek, self.skip_back, self.skip_forward):
                control.setEnabled(enabled)
            self.details.setText(self.info.kind)
        elif not self.info.video:
            self.canvas.set_message("Ingen forhåndsvisning")
            self.details.setText(self.info.kind)
        elif self.info.video.hdr:
            self.canvas.set_message("HDR-forhåndsvisning er ikke tilgjengelig.")
            self.details.setText("Velg eksportinnstillinger for å konvertere HDR-filen.")
        else:
            self.canvas.set_message("Henter forhåndsvisning …")
            self.play.setEnabled(True)
            self.seek.setEnabled(self.info.duration > 0)
            self.skip_back.setEnabled(self.info.duration > 0)
            self.skip_forward.setEnabled(self.info.duration > 0)
            self.details.setText(
                f"{self.info.video.width} × {self.info.video.height} · {self.info.kind}\n"
                "Forhåndsvisning uten lyd"
            )
            self.position = min(1.0, self.info.duration * 0.1)
            self._request_frame()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "details") and self.parentWidget():
            compact = self.parentWidget().height() < 300
            self.details.setVisible(not compact)
            self.time.setVisible(not compact)
            margin = 12 if compact else 16
            self.layout().setContentsMargins(margin, margin, margin, margin)
            self.layout().setSpacing(8 if compact else 10)

    def _request_frame(self):
        if self._closed or not self.info:
            return
        if self.audio_only:
            if self.playing:
                self.audio.play(self.info, self.position)
            else:
                self.audio.stop()
            self._update_time()
        elif self.info.video:
            self.generation = self.decoder.request(self.info, self.position, self.playing)
            self._update_time()

    def toggle_play(self):
        if not self.info or not self.play.isEnabled():
            return
        self.seek_timer.stop()
        if self.playing and self.audio_only:
            self.position = min(self.info.duration, self.audio.position())
        self.playing = not self.playing
        if self.playing and self.position >= self.info.duration - 0.15:
            self.position = 0
        self._update_play_button()
        self._request_frame()

    def _update_play_button(self):
        self.play.set_symbol(
            "pause" if self.playing else "play_filled",
            "Sett forhåndsvisning på pause" if self.playing else "Spill av forhåndsvisning",
        )

    def skip_seconds(self, seconds):
        if self._closed or not self.info or not self.seek.isEnabled():
            return
        self.seek_timer.stop()
        self.position = max(0.0, min(self.position + seconds, max(0.0, self.info.duration - 0.1)))
        self._request_frame()

    def _start_seek(self):
        self._resume = self.playing
        self.playing = False
        self._update_play_button()
        self.generation = self.decoder.request(None)
        self.audio.stop()

    def _seek_changed(self, value):
        if not self.seek.isEnabled() or not self.info:
            return
        self.position = min(value / 10000 * self.info.duration, max(0, self.info.duration - 0.1))
        self.generation = self.decoder.request(None)
        self._update_time(update_slider=False)
        self.seek_timer.start()

    def _finish_seek(self):
        self.seek_timer.stop()
        self.playing = self._resume
        self._update_play_button()
        self._request_frame()

    def _update_time(self, *, update_slider=True):
        duration = self.info.duration if self.info else 0
        self.time.setText(f"{duration_text(self.position)} / {duration_text(duration)}")
        if update_slider and not self.seek.isSliderDown():
            self.seek.blockSignals(True)
            self.seek.setValue(round(self.position / duration * 10000) if duration else 0)
            self.seek.blockSignals(False)

    def _poll(self):
        if self.audio_only and self.playing:
            self._poll_audio()
            return
        latest, status = self.decoder.poll()
        if latest and latest[0] == self.generation:
            image = QImage.fromData(latest[1], "JPEG")
            if not image.isNull():
                self.canvas.image = image
                self.canvas.update()
                self.position = latest[2]
                self._update_time()
                self.frame_ready.emit(self.position)
        if status and status[0] == self.generation:
            self.playing = False
            self._update_play_button()
            if status[1] == "error":
                self.canvas.set_message(status[2])

    def _poll_audio(self):
        if self.audio.error or self.audio.finished:
            self.playing = False
            self._update_play_button()
            if self.audio.error:
                self.details.setText(self.audio.error)
            else:
                self.position = self.info.duration
        else:
            self.position = min(self.info.duration, self.audio.position())
        self._update_time()

    def pause(self):
        if self.playing:
            if self.audio_only:
                self.position = min(self.info.duration, self.audio.position())
            self.playing = False
            self._update_play_button()
            self._request_frame()

    def shutdown(self):
        self._closed = True
        self.seek_timer.stop()
        self.timer.stop()
        self.decoder.stop()
        self.audio.stop()
