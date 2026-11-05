import hashlib
import subprocess
import threading
from dataclasses import replace
from types import SimpleNamespace

import pytest

from vestfold_converter.core.models import Cancelled, MediaError
from vestfold_converter.core.process import CREATE_FLAGS
from vestfold_converter.core.profiles import AUDIO_PRESETS, default_settings, preset_settings
from vestfold_converter.core.storage import long_path

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("kind", ["mts", "mp4", "mov", "mkv", "wav", "mp3", "flac", "silent", "artwork"])
def test_one_click_defaults(engine, media, tmp_path, kind):
    source = media[kind]
    digest = hashlib.sha256(source.read_bytes()).digest()
    info = engine.analyze(source)
    settings = default_settings(info)
    values = []
    result = engine.convert(info, settings, tmp_path / "Målmappe æøå", threading.Event(), values.append)
    output = engine.analyze(result)
    assert result.exists() and values[-1] == 1
    assert hashlib.sha256(source.read_bytes()).digest() == digest
    if info.video:
        assert output.video.codec == "h264"
        assert output.video.pixel_format == "yuv420p"
        assert bool(output.audio) == bool(info.audio)
        if output.audio:
            assert output.audio[0].codec == "aac"
        data = result.read_bytes()
        assert data.index(b"moov") < data.index(b"mdat")
    else:
        assert not output.video
        assert output.audio[0].codec == "mp3"


@pytest.mark.parametrize(
    "container,codec",
    [
        ("wav", "pcm_s24le"),
        ("flac", "flac"),
        ("m4a", "aac"),
        ("opus", "libopus"),
        ("ogg", "libvorbis"),
        ("aiff", "pcm_s16be"),
        ("alac", "alac"),
    ],
)
def test_advanced_audio(engine, media, tmp_path, container, codec):
    info = engine.analyze(media["wav"])
    settings = replace(default_settings(info), container=container, audio_codec=codec)
    output = engine.convert(info, settings, tmp_path, threading.Event())
    assert engine.analyze(output).audio


@pytest.mark.parametrize("profile", ["small", "quality", "webm", "prores"])
def test_advanced_profiles(engine, media, tmp_path, profile):
    info = engine.analyze(media["mts"])
    settings = preset_settings(profile, info)
    output = engine.convert(info, settings, tmp_path, threading.Event())
    assert engine.analyze(output).video


def test_copy_and_extract_audio(engine, media, tmp_path):
    info = engine.analyze(media["mp4"])
    for key in ("copy", "audio", "audio_wav"):
        output = engine.convert(info, preset_settings(key, info), tmp_path, threading.Event())
        assert engine.analyze(output).audio


@pytest.mark.parametrize("profile", AUDIO_PRESETS)
def test_audio_profiles(engine, media, tmp_path, profile):
    info = engine.analyze(media["wav"])
    output = engine.convert(info, preset_settings(profile, info), tmp_path, threading.Event())
    result = engine.analyze(output)
    assert result.audio and not result.video


def test_interlaced_and_tracks(engine, media, tmp_path):
    info = engine.analyze(media["interlace"])
    output = engine.convert(info, default_settings(info), tmp_path, threading.Event())
    assert engine.analyze(output).video.field_order in {"progressive", "unknown"}
    info = engine.analyze(media["multi"])
    assert len(info.audio) == 2
    assert info.default_audio.index == info.audio[1].index
    settings = replace(default_settings(info), audio_stream=info.audio[0].index)
    output = engine.convert(info, settings, tmp_path, threading.Event())
    assert len(engine.analyze(output).audio) == 1


def test_existing_names_and_source_untouched(engine, media, tmp_path):
    info = engine.analyze(media["wav"])
    settings = default_settings(info)
    results = [engine.convert(info, settings, tmp_path, threading.Event()) for _ in range(2)]
    assert results[0] != results[1]
    assert results[1].stem.endswith("(1)")


def test_low_disk_space(engine, media, tmp_path, monkeypatch):
    info = engine.analyze(media["wav"])
    monkeypatch.setattr("vestfold_converter.core.engine.shutil.disk_usage", lambda _: SimpleNamespace(free=1))
    with pytest.raises(MediaError, match="diskplass"):
        engine.convert(info, default_settings(info), tmp_path, threading.Event())
    assert not list(tmp_path.iterdir())


def test_cancel_before_start(engine, media, tmp_path):
    info = engine.analyze(media["wav"])
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        engine.convert(info, default_settings(info), tmp_path, cancel)
    assert not list(tmp_path.iterdir())


def test_cancel_running_process(engine, tmp_path):
    source = tmp_path / "lang.mp4"
    subprocess.run(
        [
            str(engine.ffmpeg),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=25",
            "-t",
            "15",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            str(source),
        ],
        check=True,
        capture_output=True,
        creationflags=CREATE_FLAGS,
        timeout=60,
    )
    info = engine.analyze(source)
    cancel = threading.Event()
    timer = threading.Timer(0.3, cancel.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            engine.convert(info, replace(default_settings(info), preset="slow"), tmp_path / "output", cancel)
    finally:
        timer.cancel()
    assert not list((tmp_path / "output").iterdir())


def test_invalid_file_and_removed_source(engine, media, tmp_path):
    broken = tmp_path / "korrupt.mp4"
    broken.write_bytes(b"not a real video")
    with pytest.raises(MediaError):
        engine.analyze(broken)
    missing = replace(engine.analyze(media["wav"]), path=tmp_path / "missing.wav")
    with pytest.raises(MediaError):
        engine.convert(missing, default_settings(missing), tmp_path / "output", threading.Event())
    assert not list((tmp_path / "output").iterdir())


def test_rotation_and_color_tags(engine, media, tmp_path):
    source = tmp_path / "rotert.mp4"
    subprocess.run(
        [
            str(engine.ffmpeg),
            "-v",
            "error",
            "-display_rotation:v:0",
            "90",
            "-i",
            str(media["mp4"]),
            "-c",
            "copy",
            str(source),
        ],
        check=True,
        capture_output=True,
        creationflags=CREATE_FLAGS,
        timeout=30,
    )
    info = engine.analyze(source)
    output = engine.convert(info, default_settings(info), tmp_path / "output", threading.Event())
    result = engine.analyze(output)
    assert (result.video.width, result.video.height) == (info.video.height, info.video.width)


def test_sdr_color_information(engine, tmp_path):
    source = tmp_path / "farger.mp4"
    subprocess.run(
        [
            str(engine.ffmpeg),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=128x72:r=25",
            "-t",
            "0.4",
            "-c:v",
            "libx264",
            "-vf",
            "setparams=colorspace=bt709:color_trc=bt709:color_primaries=bt709:range=tv",
            "-colorspace",
            "bt709",
            "-color_trc",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_range",
            "tv",
            str(source),
        ],
        check=True,
        capture_output=True,
        creationflags=CREATE_FLAGS,
        timeout=30,
    )
    info = engine.analyze(source)
    output = engine.convert(info, default_settings(info), tmp_path / "output", threading.Event())
    result = engine.analyze(output)
    assert (
        result.video.color_space,
        result.video.color_transfer,
        result.video.color_primaries,
        result.video.color_range,
    ) == ("bt709", "bt709", "bt709", "tv")


@pytest.mark.parametrize(
    "container,codec", [("webm", "libvpx-vp9"), ("webm", "libaom-av1"), ("avi", "mpeg4"), ("mkv", "libx264")]
)
def test_advanced_video_formats(engine, media, tmp_path, container, codec):
    info = engine.analyze(media["mp4"])
    audio = "libopus" if container == "webm" else "libmp3lame" if container == "avi" else "aac"
    settings = replace(
        default_settings(info), container=container, video_codec=codec, audio_codec=audio, preset="ultrafast"
    )
    assert engine.convert(info, settings, tmp_path, threading.Event()).exists()


def test_corrupt_result_is_not_published(engine, media, tmp_path, monkeypatch):
    info = engine.analyze(media["wav"])

    def broken_encode(args, *_):
        from pathlib import Path

        Path(args[-1]).write_bytes(b"corrupt")

    monkeypatch.setattr(engine, "_encode", broken_encode)
    with pytest.raises(MediaError):
        engine.convert(info, default_settings(info), tmp_path, threading.Event())
    assert not list(tmp_path.iterdir())


def test_disk_error_during_encoding_cleans_partial(engine, media, tmp_path, monkeypatch):
    info = engine.analyze(media["wav"])

    def disk_error(args, *_):
        import errno
        from pathlib import Path

        Path(args[-1]).write_bytes(b"partial")
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(engine, "_encode", disk_error)
    with pytest.raises(MediaError, match="full"):
        engine.convert(info, default_settings(info), tmp_path, threading.Event())
    assert not list(tmp_path.iterdir())


def test_windows_long_path(engine, media, tmp_path):
    folder = tmp_path
    while len(str(folder)) < 280:
        folder /= "mediemappe-med-norsk-tekst-æøå"
    long_path(folder).mkdir(parents=True)
    source = long_path(folder / "opptak.wav")
    source.write_bytes(media["wav"].read_bytes())
    info = engine.analyze(source)
    assert engine.convert(info, default_settings(info), folder / "resultater", threading.Event()).is_file()
