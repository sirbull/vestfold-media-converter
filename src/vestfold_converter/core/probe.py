import json
import math
import threading
from pathlib import Path

from .models import MediaError, MediaInfo, Stream
from .process import capture
from .storage import long_path


def _number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (ValueError, TypeError):
        return default


def _rate(value):
    numerator, _, denominator = str(value or "").partition("/")
    return _number(numerator) / _number(denominator, 1.0) if _number(denominator, 1.0) else 0.0


def _tags(raw):
    return tuple((str(key), str(value)) for key, value in (raw or {}).items() if str(value).strip())


def parse_probe(path: Path, data: dict) -> MediaInfo:
    streams = []
    for raw in data.get("streams", []):
        disposition = raw.get("disposition", {})
        tags = raw.get("tags", {})
        streams.append(
            Stream(
                index=int(raw["index"]),
                kind=raw.get("codec_type", "unknown"),
                codec=raw.get("codec_name", "unknown"),
                attached_pic=bool(disposition.get("attached_pic")),
                default=bool(disposition.get("default")),
                language=tags.get("language", "und"),
                title=tags.get("title", ""),
                sample_rate=int(_number(raw.get("sample_rate"))),
                channels=int(_number(raw.get("channels"))),
                width=int(_number(raw.get("width"))),
                height=int(_number(raw.get("height"))),
                field_order=raw.get("field_order", "unknown"),
                pixel_format=raw.get("pix_fmt", ""),
                color_space=raw.get("color_space", "unknown"),
                color_transfer=raw.get("color_transfer", "unknown"),
                color_primaries=raw.get("color_primaries", "unknown"),
                color_range=raw.get("color_range", "unknown"),
                codec_long=raw.get("codec_long_name", ""),
                profile=raw.get("profile", ""),
                bit_rate=int(_number(raw.get("bit_rate"))),
                frame_rate=_rate(raw.get("avg_frame_rate")) or _rate(raw.get("r_frame_rate")),
                bit_depth=int(_number(raw.get("bits_per_raw_sample")) or _number(raw.get("bits_per_sample"))),
                channel_layout=raw.get("channel_layout", ""),
                display_aspect=raw.get("display_aspect_ratio", ""),
                tags=_tags(tags),
            )
        )
    fmt = data.get("format", {})
    duration = _number(fmt.get("duration")) or max(
        (_number(s.get("duration")) for s in data.get("streams", [])), default=0
    )
    info = MediaInfo(
        path.resolve(),
        max(0, duration),
        path.stat().st_size,
        fmt.get("format_name", "ukjent"),
        tuple(streams),
        format_long=fmt.get("format_long_name", ""),
        bit_rate=int(_number(fmt.get("bit_rate"))),
        tags=_tags(fmt.get("tags")),
    )
    if not info.video and not info.audio:
        raise MediaError("Filen inneholder ingen støttede lyd- eller videostrømmer.")
    return info


def probe(path: Path, ffprobe: Path, cancel: threading.Event | None = None) -> MediaInfo:
    try:
        path = long_path(path)
        data = json.loads(
            capture(
                [
                    str(ffprobe),
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file,pipe",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    str(path.resolve()),
                ],
                cancel,
            )
        )
        return parse_probe(path, data)
    except (OSError, ValueError, KeyError) as exc:
        raise MediaError(f"Kunne ikke analysere filen: {exc}") from exc
