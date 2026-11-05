"""Begrenset forhåndsvisning med medfølgende FFmpeg, uten systemkodeker eller Qt."""

import ctypes
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path

from .models import MediaInfo
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


def _terminate(process):
    """Avbryt uten å vente; arbeidertråden rydder opp etter prosessen."""
    if process is not None and process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass


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

    def request(self, info: MediaInfo | None, position=0.0, playing=False) -> int:
        with self._condition:
            self._generation += 1
            self._cancel.set()
            process = self._process
            self._latest = self._status = None
            self._pending = (self._generation, info, position, playing) if info else None
            self._condition.notify()
            generation = self._generation
        _terminate(process)
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
        _terminate(process)
        return result

    def stop(self):
        with self._condition:
            self._stopped = True
            self._cancel.set()
            self._pending = None
            process = self._process
            self._condition.notify()
        _terminate(process)

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
        _terminate(process)

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
