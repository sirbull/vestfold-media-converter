"""Begrenset forhåndsvisning med medfølgende FFmpeg, uten systemkodeker."""

import ctypes
import subprocess
import threading
import time
from ctypes import wintypes
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

from .appearance import IconButton, PathLabel
from .models import MediaInfo, QueueItem
from .process import CREATE_FLAGS, stop_process

PREVIEW_FPS = 12


def preview_command(ffmpeg: Path, info: MediaInfo, position: float, playing: bool) -> list[str]:
    args = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", "file,pipe"]
    # Litt preroll gir også en keyframe ved søking i korte transportstrømmer.
    seek_start = max(0.0, position - 3)
    args += ["-ss", f"{seek_start:.3f}", "-i", str(info.path)]
    if position > seek_start:
        args += ["-ss", f"{position - seek_start:.3f}"]
    args += ["-map", f"0:{info.video.index}", "-an", "-sn", "-dn"]
    filters = []
    if info.video.field_order in {"tt", "bb", "tb", "bt"}:
        filters.append("bwdif=mode=send_frame:deint=interlaced")
    if playing:
        filters.append(f"fps={PREVIEW_FPS}")
    filters.append("scale=640:360:force_original_aspect_ratio=decrease:reset_sar=1")
    args += ["-vf", ",".join(filters), "-c:v", "mjpeg", "-pix_fmt", "yuvj420p", "-q:v", "4", "-threads", "1"]
    if not playing:
        args += ["-frames:v", "1"]
    return args + ["-f", "image2pipe", "pipe:1"]


class PreviewDecoder:
    """Én arbeider, siste forespørsel vinner, og bare siste JPEG beholdes i minnet."""

    def __init__(self, ffmpeg: Path):
        self.ffmpeg = ffmpeg
        self._condition = threading.Condition()
        self._generation = 0
        self._pending = None
        self._latest = None
        self._status = None
        self._process = None
        self._cancel = threading.Event()
        self._stopped = False
        self._activity = time.monotonic()
        self.thread = threading.Thread(target=self._run, name="Videoforhåndsvisning", daemon=True)
        self.thread.start()

    @staticmethod
    def _terminate(process):
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass

    def request(self, info: MediaInfo | None, position=0.0, playing=False) -> int:
        with self._condition:
            self._generation += 1
            self._cancel.set()
            process = self._process
            self._latest = self._status = None
            self._pending = (self._generation, info, position, playing) if info else None
            self._condition.notify()
            generation = self._generation
        self._terminate(process)
        return generation

    def poll(self):
        process = None
        with self._condition:
            if self._process and not self._cancel.is_set() and time.monotonic() - self._activity > 15:
                self._cancel.set()
                process = self._process
                self._status = (self._generation, "error", "Forhåndsvisningen tok for lang tid.")
            result = self._latest, self._status
            self._latest = self._status = None
        self._terminate(process)
        return result

    def stop(self):
        with self._condition:
            self._stopped = True
            self._cancel.set()
            self._pending = None
            process = self._process
            self._condition.notify()
        self._terminate(process)

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._stopped or self._pending is not None)
                if self._stopped:
                    return
                generation, info, position, playing = self._pending
                self._pending = None
                cancel = self._cancel = threading.Event()
                self._activity = time.monotonic()
            try:
                self._decode(generation, info, position, playing, cancel)
            except (OSError, ValueError, subprocess.SubprocessError):
                with self._condition:
                    if generation == self._generation and not cancel.is_set():
                        self._status = (
                            generation,
                            "error",
                            "Kunne ikke vise videoen. Filen kan være skadet.",
                        )

    def _decode(self, generation, info, position, playing, cancel):
        with subprocess.Popen(
            preview_command(self.ffmpeg, info, position, playing),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_FLAGS,
        ) as process:
            with self._condition:
                self._process = process
                if generation != self._generation or self._stopped:
                    cancel.set()
            buffer = bytearray()
            frames = 0
            playback_started = None
            try:
                if cancel.is_set():
                    return
                while not cancel.is_set():
                    chunk = process.stdout.read1(64 * 1024)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    if len(buffer) > 8 * 1024 * 1024:
                        raise ValueError("For stor JPEG i forhåndsvisning")
                    while (end := buffer.find(b"\xff\xd9")) >= 0:
                        start = buffer.find(b"\xff\xd8")
                        if start < 0 or start > end:
                            del buffer[: end + 2]
                            continue
                        frame = bytes(buffer[start : end + 2])
                        del buffer[: end + 2]
                        if playing:
                            if playback_started is None:
                                playback_started = time.monotonic()
                            delay = playback_started + frames / PREVIEW_FPS - time.monotonic()
                            if cancel.wait(max(0, delay)):
                                return
                        timestamp = min(info.duration, position + frames / PREVIEW_FPS)
                        frames += 1
                        with self._condition:
                            if generation == self._generation and not cancel.is_set():
                                self._latest = (generation, frame, timestamp)
                                self._activity = time.monotonic()
                if not cancel.is_set():
                    process.wait(timeout=3)
                    with self._condition:
                        if generation == self._generation:
                            self._status = (
                                generation,
                                "finished" if frames and process.returncode == 0 else "error",
                                "Kunne ikke hente et bilde fra videoen.",
                            )
            finally:
                stop_process(process)
                process.stdout.close()
                with self._condition:
                    if self._process is process:
                        self._process = None


AUDIO_RATE = 48000
AUDIO_FRAME_BYTES = 4  # 16-bit stereo
AUDIO_CHUNK = AUDIO_RATE * AUDIO_FRAME_BYTES // 5  # 0,2 sekunder per buffer
AUDIO_BUFFERS = 4


def audio_preview_command(ffmpeg: Path, info: MediaInfo, position: float) -> list[str]:
    args = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-protocol_whitelist", "file,pipe"]
    args += ["-ss", f"{max(0.0, position):.3f}", "-i", str(info.path)]
    args += ["-map", f"0:{info.default_audio.index}", "-vn", "-sn", "-dn", "-ac", "2", "-ar", str(AUDIO_RATE)]
    return args + ["-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"]


class _WaveFormat(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class _WaveHeader(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", wintypes.DWORD),
        ("dwLoops", wintypes.DWORD),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_size_t),
    ]


class _MMTime(ctypes.Structure):
    _fields_ = [("wType", wintypes.UINT), ("sample", wintypes.DWORD), ("_pad", wintypes.DWORD)]


class WaveOut:
    """Windows' innebygde lydutgang (winmm). Ingen ekstra biblioteker eller systemkodeker."""

    def __init__(self):
        try:
            self._winmm = ctypes.WinDLL("winmm")
        except (AttributeError, OSError) as exc:
            raise OSError("Lydavspilling støttes bare på Windows.") from exc
        fmt = _WaveFormat(1, 2, AUDIO_RATE, AUDIO_RATE * AUDIO_FRAME_BYTES, AUDIO_FRAME_BYTES, 16, 0)
        self._handle = ctypes.c_void_p()
        # WAVE_MAPPER velger standard lydutgang, CALLBACK_NULL betyr at vi spør etter status selv.
        wave_mapper = wintypes.UINT(0xFFFFFFFF)
        if self._winmm.waveOutOpen(ctypes.byref(self._handle), wave_mapper, ctypes.byref(fmt), None, None, 0):
            raise OSError("Fant ingen lydutgang.")
        self._queued = []

    def write(self, data: bytes) -> None:
        buffer = ctypes.create_string_buffer(data, len(data))
        header = _WaveHeader(ctypes.cast(buffer, ctypes.c_void_p), len(data))
        size = ctypes.sizeof(header)
        self._winmm.waveOutPrepareHeader(self._handle, ctypes.byref(header), size)
        if self._winmm.waveOutWrite(self._handle, ctypes.byref(header), size):
            self._winmm.waveOutUnprepareHeader(self._handle, ctypes.byref(header), size)
            raise OSError("Lydutgangen avviste lyden.")
        self._queued.append((header, buffer))

    def pending(self) -> int:
        """Antall buffere som ikke er spilt ferdig. Ferdige buffere frigis."""
        still = []
        for header, buffer in self._queued:
            if header.dwFlags & 1:  # WHDR_DONE
                self._winmm.waveOutUnprepareHeader(self._handle, ctypes.byref(header), ctypes.sizeof(header))
            else:
                still.append((header, buffer))
        self._queued = still
        return len(still)

    def played_seconds(self) -> float:
        position = _MMTime(2)  # TIME_SAMPLES
        self._winmm.waveOutGetPosition(self._handle, ctypes.byref(position), ctypes.sizeof(position))
        # Noen drivere svarer i byte selv om vi ber om samples.
        frames = position.sample / AUDIO_FRAME_BYTES if position.wType == 4 else position.sample
        return frames / AUDIO_RATE

    def close(self) -> None:
        self._winmm.waveOutReset(self._handle)
        self.pending()
        self._winmm.waveOutClose(self._handle)


class AudioPlayer:
    """Spiller lydsporet fra en posisjon. Pause og søk starter en ny, kort FFmpeg-prosess."""

    def __init__(self, ffmpeg: Path, output=WaveOut):
        self.ffmpeg = ffmpeg
        self._output = output
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._process = None
        self._start = 0.0
        self._played = 0.0
        self.finished = False
        self.error = ""
        self.thread = None

    def play(self, info: MediaInfo, position: float) -> None:
        self.stop()
        self._cancel = cancel = threading.Event()
        self._start, self._played = position, 0.0
        self.finished, self.error = False, ""
        self.thread = threading.Thread(
            target=self._run, args=(info, position, cancel), name="Lydforhåndsvisning", daemon=True
        )
        self.thread.start()

    def position(self) -> float:
        with self._lock:
            return self._start + self._played

    def stop(self) -> None:
        self._cancel.set()
        with self._lock:
            process = self._process
        PreviewDecoder._terminate(process)

    def _run(self, info, position, cancel):
        output = None
        try:
            # FFmpeg starter mens lydenheten åpnes; første åpning kan ta et halvt sekund.
            with subprocess.Popen(
                audio_preview_command(self.ffmpeg, info, position),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_FLAGS,
            ) as process:
                with self._lock:
                    self._process = process
                try:
                    try:
                        output = self._output()
                    except OSError as exc:
                        if not cancel.is_set():
                            self.error = str(exc)
                        return
                    self._feed(output, process, cancel)
                finally:
                    stop_process(process)
                    process.stdout.close()
                    with self._lock:
                        self._process = None
        except (OSError, ValueError, subprocess.SubprocessError):
            if not cancel.is_set():
                self.error = "Kunne ikke spille av lyden. Filen kan være skadet."
        finally:
            if output:
                output.close()

    def _feed(self, output, process, cancel):
        ended = False
        while not cancel.is_set():
            while not ended and output.pending() < AUDIO_BUFFERS:
                data = process.stdout.read(AUDIO_CHUNK)
                data = data[: len(data) - len(data) % AUDIO_FRAME_BYTES]
                if not data:
                    ended = True
                    break
                output.write(data)
            with self._lock:
                if not cancel.is_set():
                    self._played = output.played_seconds()
            if ended and not output.pending():
                self.finished = not cancel.is_set()
                return
            cancel.wait(0.02)


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


def time_text(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


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
        self.time.setText(f"{time_text(self.position)} / {time_text(duration)}")
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
