from dataclasses import replace
from pathlib import Path

import pytest

from vestfold_converter.engine import build_command, parse_capabilities
from vestfold_converter.models import ExportSettings, MediaError, MediaInfo, Stream
from vestfold_converter.probe import parse_probe
from vestfold_converter.profiles import (
    AUDIO_CODECS,
    CONTAINERS,
    VIDEO_CODECS,
    default_settings,
    preset_keys,
    preset_settings,
    validate,
)

ENCODERS = set(VIDEO_CODECS) | set(AUDIO_CODECS)
MUXERS = {value[2] for value in CONTAINERS.values()}


def source(video=True, audio=True):
    streams = [Stream(0, "video", "h264", width=1920, height=1080)] if video else []
    if audio:
        streams.append(Stream(1, "audio", "ac3", sample_rate=48000, channels=2))
    return MediaInfo(Path("C:/kilde.MTS"), 10, 1234, "mpegts", tuple(streams))


def test_default_profiles():
    assert default_settings(source()).video_codec == "libx264"
    assert default_settings(source(False)).container == "mp3"
    assert default_settings(source(False)).video_codec is None


@pytest.mark.parametrize(
    ("width", "height", "codec"),
    [
        (1920, 1080, "libx264"),
        (2560, 1440, "libx264"),
        (3840, 2160, "libx265"),
        (2160, 3840, "libx265"),
        (4096, 2160, "libx265"),
    ],
)
def test_4k_and_larger_default_to_h265(width, height, codec):
    video = Stream(0, "video", "h264", width=width, height=height)
    info = replace(source(), streams=(video, *source().audio))
    settings = default_settings(info)
    assert (settings.container, settings.video_codec) == ("mp4", codec)
    assert settings.name == ("MP4 · H.265 – Anbefalt" if codec == "libx265" else "MP4 · H.264 – Anbefalt")
    # Den anbefalte kodeken står bare én gang i listen.
    names = [preset_settings(key, info).name for key in preset_keys(info)]
    assert len(names) == len(set(names))
    assert sum("H.265" in name and "høy" not in name for name in names) == 1


@pytest.mark.parametrize("info", [source(), source(False)], ids=["video", "lyd"])
def test_every_listed_preset_is_valid(info):
    for key in preset_keys(info):
        validate(info, preset_settings(key, info), ENCODERS, MUXERS)
    if not info.video:
        containers = {preset_settings(key, info).container for key in preset_keys(info)}
        assert {"mp3", "m4a", "flac", "ogg", "opus", "alac", "wav", "aiff"} <= containers


def test_artwork_is_not_video(tmp_path):
    path = tmp_path / "feil.endelse"
    path.write_bytes(b"test")
    data = {
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "mjpeg", "disposition": {"attached_pic": 1}},
            {"index": 1, "codec_type": "audio", "codec_name": "mp3"},
        ],
        "format": {"duration": "NaN", "format_name": "mp3"},
    }
    info = parse_probe(path, data)
    assert info.kind == "Lyd"
    assert info.duration == 0
    assert default_settings(info).container == "mp3"


@pytest.mark.parametrize(
    "settings",
    [
        ExportSettings(container="webm"),
        ExportSettings(container="mp3"),
        ExportSettings(video_codec="prores_ks"),
        ExportSettings(fps="0"),
        ExportSettings(fps="25/0"),
        ExportSettings(width=1919, height=1080),
        ExportSettings(width=1920),
        ExportSettings(aspect=";bad"),
        ExportSettings(video_codec="copy", width=1280, height=720),
        ExportSettings(audio_stream=999),
        ExportSettings(audio_codec="copy", channels=2),
        ExportSettings(audio_codec="missing"),
        ExportSettings(quality=99),
    ],
)
def test_invalid_combinations(settings):
    with pytest.raises(MediaError):
        validate(source(), settings, ENCODERS, MUXERS)


def test_audio_cannot_export_video():
    with pytest.raises(MediaError):
        validate(source(False), ExportSettings(), ENCODERS, MUXERS)


def test_missing_encoder():
    with pytest.raises(MediaError):
        validate(source(), ExportSettings(), {"aac"}, MUXERS)


def test_prores_uses_mov():
    settings = preset_settings("prores", source())
    validate(source(), settings, ENCODERS, MUXERS)
    assert settings.container == "mov"
    assert settings.pixel_format == "yuv422p10le"


def test_default_command_preserves_timing_and_maps_one_track():
    args = build_command(Path("ffmpeg.exe"), source(), ExportSettings(), Path("part.mp4"))
    assert "libx264" in args and "aac" in args
    assert "copy" not in args and "-r" not in args and "fps=" not in " ".join(args)
    assert "0:0" in args and "0:1" in args
    assert "+faststart" in args and "-n" in args and "-progress" in args


def test_silent_command_does_not_generate_audio():
    args = build_command(Path("ffmpeg.exe"), source(audio=False), ExportSettings(), Path("part.mp4"))
    assert "-an" in args
    assert "-c:a" not in args


def test_hdr_requires_explicit_compatible_output():
    info = replace(source(), streams=(Stream(0, "video", "hevc", color_transfer="smpte2084"),))
    with pytest.raises(MediaError, match="HDR"):
        validate(info, ExportSettings(), ENCODERS, MUXERS)
    validate(info, ExportSettings(video_codec="libx265", pixel_format="yuv420p10le"), ENCODERS, MUXERS)


def test_large_file_metadata_keeps_64_bits(tmp_path, monkeypatch):
    path = tmp_path / "large.wav"
    # Simuler filsystemets 64-bit størrelse uten å allokere flere GB testdata.
    import os

    path.write_bytes(b"header")
    original_stat = Path.stat

    def large_stat(self, *args, **kwargs):
        result = original_stat(self, *args, **kwargs)
        if self == path:
            values = list(result)
            values[6] = 5 * 1024**3
            return os.stat_result(values)
        return result

    monkeypatch.setattr(Path, "stat", large_stat)
    result = parse_probe(
        path,
        {
            "streams": [{"index": 0, "codec_type": "audio", "codec_name": "pcm_s16le"}],
            "format": {"duration": "12345.67"},
        },
    )
    assert result.size == 5 * 1024**3


def test_capability_parser():
    assert parse_capabilities(" V....D libx264 description\n A..... aac AAC", "encoders") == {
        "libx264",
        "aac",
    }
    assert parse_capabilities("  E matroska Matroska\n  E mov,mp4 Test", "muxers") == {
        "matroska",
        "mov",
        "mp4",
    }
