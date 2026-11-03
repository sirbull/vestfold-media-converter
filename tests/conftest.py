import os
import subprocess

import pytest

from vestfold_converter.engine import MediaEngine
from vestfold_converter.models import MediaError
from vestfold_converter.process import CREATE_FLAGS
from vestfold_converter.storage import bundled_tools

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def engine():
    try:
        tools = bundled_tools()
    except MediaError as exc:
        if os.environ.get("VMC_REQUIRE_FFMPEG") == "1":
            pytest.fail(str(exc))
        pytest.skip("Medfølgende FFmpeg mangler; kjør scripts/fetch_ffmpeg.ps1")
    result = MediaEngine(*tools)
    result.discover()
    return result


@pytest.fixture(scope="session")
def media(tmp_path_factory, engine):
    folder = tmp_path_factory.mktemp("medier æøå")

    def generate(name, options, *, video=True, audio=True, seconds="0.8"):
        target = folder / name
        args = [str(engine.ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-n"]
        if video:
            args += ["-f", "lavfi", "-i", "testsrc2=size=128x72:rate=25"]
        if audio:
            args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
        args += ["-t", seconds, *options, str(target)]
        subprocess.run(args, check=True, capture_output=True, creationflags=CREATE_FLAGS, timeout=60)
        return target

    files = {
        "mts": generate("Skoleklipp æøå.MTS", ["-c:v", "libx264", "-c:a", "ac3", "-f", "mpegts"]),
        "mp4": generate("video.mp4", ["-c:v", "libx264", "-c:a", "aac"]),
        "mov": generate("video.mov", ["-c:v", "libx264", "-c:a", "aac"]),
        "mkv": generate("video.mkv", ["-c:v", "libx264", "-c:a", "aac"]),
        "silent": generate("uten lyd.mp4", ["-c:v", "libx264"], audio=False),
        "wav": generate("lydopptak.wav", ["-c:a", "pcm_s16le"], video=False),
        "mp3": generate("lydopptak.mp3", ["-c:a", "libmp3lame"], video=False),
        "flac": generate("lydopptak.flac", ["-c:a", "flac"], video=False),
        "interlace": generate(
            "interlaced.mts",
            [
                "-vf",
                "setfield=tff",
                "-flags",
                "+ilme+ildct",
                "-c:v",
                "libx264",
                "-c:a",
                "ac3",
                "-f",
                "mpegts",
            ],
        ),
        "multi": generate(
            "flere spor.mkv",
            [
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-map",
                "1:a",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-disposition:a:0",
                "0",
                "-disposition:a:1",
                "default",
            ],
        ),
    }
    artwork = folder / "cover.jpg"
    subprocess.run(
        [
            str(engine.ffmpeg),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=64x64",
            "-frames:v",
            "1",
            str(artwork),
        ],
        check=True,
        capture_output=True,
        creationflags=CREATE_FLAGS,
        timeout=30,
    )
    covered = folder / "med albumgrafikk.mp3"
    subprocess.run(
        [
            str(engine.ffmpeg),
            "-v",
            "error",
            "-i",
            str(files["mp3"]),
            "-i",
            str(artwork),
            "-map",
            "0:a",
            "-map",
            "1:v",
            "-c",
            "copy",
            "-id3v2_version",
            "3",
            "-disposition:v",
            "attached_pic",
            str(covered),
        ],
        check=True,
        capture_output=True,
        creationflags=CREATE_FLAGS,
        timeout=30,
    )
    files["artwork"] = covered
    return files
