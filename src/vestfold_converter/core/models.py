import uuid
from dataclasses import dataclass, field
from pathlib import Path


class MediaError(Exception):
    """En feil som kan forklares direkte til brukeren."""


class Cancelled(MediaError):
    pass


@dataclass(frozen=True)
class Stream:
    index: int
    kind: str
    codec: str
    attached_pic: bool = False
    default: bool = False
    language: str = "und"
    title: str = ""
    sample_rate: int = 0
    channels: int = 0
    width: int = 0
    height: int = 0
    field_order: str = "unknown"
    pixel_format: str = ""
    color_space: str = "unknown"
    color_transfer: str = "unknown"
    color_primaries: str = "unknown"
    color_range: str = "unknown"
    codec_long: str = ""
    profile: str = ""
    bit_rate: int = 0
    frame_rate: float = 0.0
    bit_depth: int = 0
    channel_layout: str = ""
    display_aspect: str = ""
    tags: tuple[tuple[str, str], ...] = ()

    @property
    def hdr(self) -> bool:
        return self.color_transfer in {"smpte2084", "arib-std-b67"}


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration: float
    size: int
    format_name: str
    streams: tuple[Stream, ...]
    format_long: str = ""
    bit_rate: int = 0
    tags: tuple[tuple[str, str], ...] = ()

    @property
    def video(self) -> Stream | None:
        return next((s for s in self.streams if s.kind == "video" and not s.attached_pic), None)

    @property
    def audio(self) -> tuple[Stream, ...]:
        return tuple(s for s in self.streams if s.kind == "audio")

    @property
    def default_audio(self) -> Stream | None:
        return next((s for s in self.audio if s.default), next(iter(self.audio), None))

    @property
    def kind(self) -> str:
        if self.video:
            return "Video og lyd" if self.audio else "Video uten lyd"
        return "Lyd" if self.audio else "Ikke støttet"


@dataclass(frozen=True)
class ExportSettings:
    name: str = "MP4 · H.264 – Anbefalt"
    container: str = "mp4"
    video_codec: str | None = "libx264"
    audio_codec: str = "aac"
    quality_mode: str = "quality"
    quality: int = 21
    video_bitrate: int = 6000
    preset: str = "medium"
    audio_bitrate: int = 192
    sample_rate: int = 0
    channels: int = 0
    bit_depth: int = 16
    audio_stream: int | None = None
    width: int = 0
    height: int = 0
    fps: str = ""
    aspect: str = ""
    deinterlace: str = "auto"
    pixel_format: str = "yuv420p"


@dataclass
class QueueItem:
    path: Path
    info: MediaInfo | None = None
    settings: ExportSettings | None = None
    status: str = "Venter på analyse"
    progress: float = 0.0
    output: Path | None = None
    error: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
