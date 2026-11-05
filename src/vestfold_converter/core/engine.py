import errno
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from .models import Cancelled, ExportSettings, MediaError, MediaInfo
from .probe import probe
from .process import CREATE_FLAGS, capture, stop_process
from .profiles import CODEC_FAMILY, CONTAINERS, validate
from .storage import long_path, publish_file, safe_stem


def parse_capabilities(text: str, kind: str) -> set[str]:
    pattern = r"^\s*[VAS][A-Z.]{5}\s+(\S+)" if kind == "encoders" else r"^\s*E\s+(\S+)"
    return {
        name
        for line in text.splitlines()
        if (m := re.match(pattern, line))
        for name in m.group(1).split(",")
        if name != "="
    }


def build_command(ffmpeg: Path, info: MediaInfo, s: ExportSettings, temporary: Path) -> list[str]:
    args = [
        str(ffmpeg),
        "-hide_banner",
        "-nostdin",
        "-n",
        "-loglevel",
        "warning",
        "-xerror",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(info.path),
        "-map_metadata",
        "0",
        "-map_chapters",
        "-1",
    ]
    if s.video_codec:
        args += ["-map", f"0:{info.video.index}", "-c:v", s.video_codec]
        if s.video_codec != "copy":
            codec = s.video_codec
            filters = []
            interlaced = info.video.field_order in {"tt", "bb", "tb", "bt"}
            if s.deinterlace == "on" or (s.deinterlace == "auto" and interlaced):
                filters.append(
                    "bwdif=mode=send_frame:parity=auto:deint=interlaced"
                    if s.deinterlace == "auto"
                    else "bwdif=mode=send_frame:parity=auto:deint=all"
                )
            if s.width and s.height:
                filters += [
                    f"scale={s.width}:{s.height}:force_original_aspect_ratio=decrease",
                    f"pad={s.width}:{s.height}:(ow-iw)/2:(oh-ih)/2",
                ]
            else:
                # Minimal padding gjør odde dimensjoner gyldige uten å strekke bildet.
                filters.append("pad=ceil(iw/2)*2:ceil(ih/2)*2")
            if s.fps:
                filters.append(f"fps={s.fps}")
            color_params = []
            for option, value in (
                ("colorspace", info.video.color_space),
                ("color_trc", info.video.color_transfer),
                ("color_primaries", info.video.color_primaries),
                ("range", info.video.color_range),
            ):
                if value not in {"unknown", "unspecified", "reserved", ""}:
                    color_params.append(f"{option}={value}")
            if color_params:
                filters.append("setparams=" + ":".join(color_params))
            args += ["-vf", ",".join(filters), "-pix_fmt", s.pixel_format, "-fps_mode", "passthrough"]
            if s.aspect:
                args += ["-aspect", s.aspect]
            if codec == "prores_ks":
                args += ["-profile:v", "2"]
            elif s.quality_mode == "bitrate":
                args += ["-b:v", f"{s.video_bitrate}k"]
            elif codec in {"libx264", "libx265", "libsvtav1", "libaom-av1", "libvpx-vp9"}:
                args += ["-crf", str(s.quality)]
                if codec in {"libvpx-vp9", "libaom-av1"}:
                    args += ["-b:v", "0"]
            elif codec.endswith("_nvenc"):
                args += ["-rc", "vbr", "-cq", str(s.quality), "-b:v", "0"]
            elif codec.endswith("_qsv"):
                args += ["-global_quality", str(s.quality)]
            elif codec.endswith("_amf"):
                args += ["-rc", "cqp", "-qp_i", str(s.quality), "-qp_p", str(s.quality)]
            else:
                args += ["-q:v", str(max(1, min(31, round(s.quality / 2))))]
            if codec in {"libx264", "libx265"}:
                args += ["-preset", s.preset]
            elif codec == "libsvtav1":
                args += ["-preset", {"ultrafast": "12", "fast": "10", "medium": "8", "slow": "5"}[s.preset]]
            elif codec in {"libvpx-vp9", "libaom-av1"}:
                args += ["-cpu-used", {"ultrafast": "8", "fast": "6", "medium": "4", "slow": "2"}[s.preset]]
            if CODEC_FAMILY.get(codec) == "h264":
                args += ["-profile:v", "high"]
            if CODEC_FAMILY.get(codec) == "hevc" and s.container in {"mp4", "mov"}:
                args += ["-tag:v", "hvc1"]
            for option, value in (
                ("colorspace", info.video.color_space),
                ("color_trc", info.video.color_transfer),
                ("color_primaries", info.video.color_primaries),
                ("color_range", info.video.color_range),
            ):
                if value not in {"unknown", "unspecified", "reserved", ""}:
                    args += [f"-{option}", value]
    else:
        args += ["-vn"]
    if info.audio:
        audio = next((a for a in info.audio if a.index == s.audio_stream), info.default_audio)
        args += ["-map", f"0:{audio.index}", "-c:a", s.audio_codec]
        if s.audio_codec != "copy":
            if s.audio_codec in {"libmp3lame", "aac", "libopus", "libvorbis"}:
                args += ["-b:a", f"{s.audio_bitrate}k"]
            if s.audio_codec == "aac":
                args += ["-profile:a", "aac_low"]
            rate = s.sample_rate
            if not rate:
                if s.audio_codec == "libmp3lame":
                    rate = audio.sample_rate if audio.sample_rate in {32000, 44100, 48000} else 48000
                elif s.audio_codec in {"aac", "libopus"}:
                    rate = 48000
            if rate:
                args += ["-ar", str(rate)]
            channels = s.channels or (1 if audio.channels == 1 else 2)
            args += ["-ac", str(channels)]
            if s.audio_codec in {"flac", "alac"}:
                args += ["-sample_fmt", "s16" if s.bit_depth == 16 else "s32"]
                if s.bit_depth > 16:
                    args += ["-bits_per_raw_sample", str(min(s.bit_depth, 24))]
    else:
        args += ["-an"]
    args += ["-sn", "-dn"]
    if s.container in {"mp4", "mov", "m4a", "alac"}:
        args += ["-movflags", "+faststart"]
    args += ["-progress", "pipe:1", "-nostats", "-f", CONTAINERS[s.container][2], str(temporary)]
    return args


class MediaEngine:
    def __init__(self, ffmpeg: Path, ffprobe: Path):
        self.ffmpeg, self.ffprobe = ffmpeg.resolve(), ffprobe.resolve()
        self.encoders: set[str] = set()
        self.muxers: set[str] = set()

    def discover(self, cancel: threading.Event | None = None) -> None:
        self.encoders = parse_capabilities(
            capture([str(self.ffmpeg), "-hide_banner", "-encoders"], cancel), "encoders"
        )
        self.muxers = parse_capabilities(
            capture([str(self.ffmpeg), "-hide_banner", "-muxers"], cancel), "muxers"
        )
        missing = {"libx264", "aac", "libmp3lame"} - self.encoders
        if missing or not {"mp4", "mp3"} <= self.muxers:
            raise MediaError(
                "FFmpeg-bygningen mangler nødvendige standard-encodere eller muxere: "
                + ", ".join(sorted(missing))
            )

    def analyze(self, path: Path, cancel: threading.Event | None = None) -> MediaInfo:
        return probe(path, self.ffprobe, cancel)

    def convert(
        self,
        info: MediaInfo,
        settings: ExportSettings,
        folder: Path,
        cancel: threading.Event,
        progress: Callable[[float], None] = lambda _: None,
    ) -> Path:
        validate(info, settings, self.encoders, self.muxers)
        temporary = None
        try:
            if cancel.is_set():
                raise Cancelled("Avbrutt")
            folder = long_path(folder)
            folder.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(folder).free < 16 * 1024 * 1024:
                raise MediaError("For lite ledig diskplass i målmappen. Frigjør plass og prøv igjen.")
            extension = CONTAINERS[settings.container][1]
            temporary = folder / f".vmc-{uuid.uuid4().hex}.part.{extension}"
            args = build_command(self.ffmpeg, info, settings, temporary)
            self._encode(args, cancel, info.duration, progress, folder)
            if cancel.is_set():
                raise Cancelled("Avbrutt")
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise MediaError("FFmpeg opprettet ingen ferdig mediefil.")
            result = self.analyze(temporary, cancel)
            self._verify(info, settings, result)
            if cancel.is_set():
                raise Cancelled("Avbrutt")
            final = publish_file(temporary, folder, safe_stem(info.path), extension, info.path)
            progress(1.0)
            return final
        except OSError as exc:
            if exc.errno == errno.ENOSPC or getattr(exc, "winerror", None) == 112:
                raise MediaError("Disken er full. Frigjør plass i målmappen.") from exc
            raise MediaError(
                f"Kunne ikke lese eller lagre filen. Kontroller tilgang og tilkobling: {exc}"
            ) from exc
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass  # En frakoblet/defekt disk kan hindre opprydding. Kun .part-filen blir igjen.

    def _encode(self, args, cancel, duration, progress, folder):
        with tempfile.TemporaryFile(mode="w+b") as errors:  # noqa: SIM117 - filen opprettes før Popen.
            with subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=errors,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_FLAGS,
            ) as process:
                updates: queue.SimpleQueue = queue.SimpleQueue()

                def read_progress():
                    for line in process.stdout:
                        updates.put(line.decode("utf-8", errors="replace").strip())

                reader = threading.Thread(target=read_progress, daemon=True)
                reader.start()
                last_disk_check = time.monotonic()
                try:
                    while process.poll() is None or not updates.empty():
                        if cancel.is_set():
                            raise Cancelled("Avbrutt")
                        if time.monotonic() - last_disk_check > 2:
                            if shutil.disk_usage(folder).free < 4 * 1024 * 1024:
                                raise MediaError("Konverteringen stoppet fordi disken nesten er full.")
                            last_disk_check = time.monotonic()
                        try:
                            line = updates.get(timeout=0.1)
                            if line.startswith("out_time_us=") and duration > 0:
                                try:
                                    progress(
                                        min(0.98, max(0, int(line.split("=", 1)[1]) / 1_000_000 / duration))
                                    )
                                except ValueError:
                                    pass
                        except queue.Empty:
                            continue
                    process.wait()
                    if process.returncode:
                        errors.seek(0, 2)
                        size = errors.tell()
                        errors.seek(max(0, size - 4000))
                        detail = errors.read().decode("utf-8", errors="replace")
                        hint = (
                            "Disken er full."
                            if "No space left" in detail
                            else "Kontroller at kildefilen er lesbar og at den valgte encoderen støttes av maskinen."
                        )
                        raise MediaError(f"Konverteringen mislyktes. {hint}\n\n{detail}")
                finally:
                    stop_process(process)
                    reader.join(timeout=3)
                    process.stdout.close()

    @staticmethod
    def _verify(source: MediaInfo, s: ExportSettings, result: MediaInfo) -> None:
        if bool(result.video) != bool(s.video_codec):
            raise MediaError("Resultatet har ikke forventet videostrøm.")
        if bool(result.audio) != bool(source.audio):
            raise MediaError("Resultatet har ikke forventet lydstrøm.")
        if result.video and s.video_codec != "copy" and result.video.codec != CODEC_FAMILY[s.video_codec]:
            raise MediaError("Resultatet har feil videokodek.")
        if result.video and s.video_codec == "copy" and result.video.codec != source.video.codec:
            raise MediaError("Videostrømmen ble ikke kopiert som forventet.")
        if result.audio:
            from .profiles import AUDIO_FAMILY

            expected = (
                next((a.codec for a in source.audio if a.index == s.audio_stream), source.default_audio.codec)
                if s.audio_codec == "copy"
                else AUDIO_FAMILY.get(s.audio_codec, s.audio_codec)
            )
            if result.audio[0].codec != expected or len(result.audio) != 1:
                raise MediaError("Resultatet har feil lydkodek eller antall lydspor.")
        if source.duration > 2 and result.duration < source.duration - max(2, source.duration * 0.03):
            raise MediaError("Resultatet er kortere enn forventet. Kildefilen kan være skadet.")
