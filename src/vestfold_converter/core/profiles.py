"""Eksplisitt kompatibilitetsmodell. En encoder i FFmpeg er ikke nok alene."""

import re
from dataclasses import replace

from .models import ExportSettings, MediaError, MediaInfo

VIDEO_CODECS = {
    "libx264": "H.264",
    "libx265": "H.265/HEVC",
    "libsvtav1": "AV1 (SVT)",
    "libaom-av1": "AV1 (AOM)",
    "libvpx-vp9": "VP9",
    "prores_ks": "ProRes",
    "mpeg4": "MPEG-4 Part 2",
    "h264_nvenc": "H.264 · NVIDIA",
    "hevc_nvenc": "H.265 · NVIDIA",
    "h264_qsv": "H.264 · Intel",
    "hevc_qsv": "H.265 · Intel",
    "h264_amf": "H.264 · AMD",
    "hevc_amf": "H.265 · AMD",
    "copy": "Kopier original videostrøm",
}
CODEC_FAMILY = {
    "libx264": "h264",
    "libx265": "hevc",
    "libsvtav1": "av1",
    "libaom-av1": "av1",
    "libvpx-vp9": "vp9",
    "prores_ks": "prores",
    "mpeg4": "mpeg4",
    **{
        f"{c}_{h}": "h264" if c == "h264" else "hevc"
        for c in ("h264", "hevc")
        for h in ("nvenc", "qsv", "amf")
    },
}
AUDIO_CODECS = {
    "libmp3lame": "MP3",
    "aac": "AAC-LC",
    "pcm_s16le": "PCM 16-bit",
    "pcm_s24le": "PCM 24-bit",
    "pcm_s32le": "PCM 32-bit",
    "flac": "FLAC",
    "libopus": "Opus",
    "libvorbis": "Vorbis",
    "pcm_s16be": "PCM 16-bit",
    "pcm_s24be": "PCM 24-bit",
    "pcm_s32be": "PCM 32-bit",
    "alac": "ALAC",
    "copy": "Kopier original lydstrøm",
}
AUDIO_FAMILY = {"libmp3lame": "mp3", "libopus": "opus", "libvorbis": "vorbis"}
CONTAINERS = {
    "mp4": ("MP4", "mp4", "mp4", {"h264", "hevc", "av1", "mpeg4"}, {"aac", "mp3", "alac"}),
    "mov": (
        "MOV",
        "mov",
        "mov",
        {"h264", "hevc", "prores", "mpeg4"},
        {"aac", "alac", "pcm_s16le", "pcm_s24le", "pcm_s32le"},
    ),
    "mkv": (
        "MKV",
        "mkv",
        "matroska",
        {"h264", "hevc", "av1", "vp9", "prores", "mpeg4"},
        {"aac", "mp3", "flac", "opus", "vorbis", "pcm_s16le", "pcm_s24le", "pcm_s32le"},
    ),
    "webm": ("WebM", "webm", "webm", {"av1", "vp9"}, {"opus", "vorbis"}),
    "avi": ("AVI", "avi", "avi", {"mpeg4", "h264"}, {"mp3", "pcm_s16le", "pcm_s24le"}),
    "mp3": ("MP3", "mp3", "mp3", set(), {"mp3"}),
    "wav": ("WAV", "wav", "wav", set(), {"pcm_s16le", "pcm_s24le", "pcm_s32le"}),
    "flac": ("FLAC", "flac", "flac", set(), {"flac"}),
    "m4a": ("M4A/AAC", "m4a", "ipod", set(), {"aac"}),
    "opus": ("Opus", "opus", "opus", set(), {"opus"}),
    "ogg": ("OGG/Vorbis", "ogg", "ogg", set(), {"vorbis"}),
    "aiff": ("AIFF", "aiff", "aiff", set(), {"pcm_s16be", "pcm_s24be", "pcm_s32be"}),
    "alac": ("ALAC", "m4a", "ipod", set(), {"alac"}),
}
VIDEO_CONTAINERS = ("mp4", "mov", "mkv", "webm", "avi")
AUDIO_CONTAINERS = ("mp3", "wav", "flac", "m4a", "opus", "ogg", "aiff", "alac")
VIDEO_PRESETS = ("standard", "h264", "small", "quality", "webm", "prores", "copy", "audio", "audio_wav")
AUDIO_PRESETS = ("standard", "aac", "flac", "ogg", "opus", "alac", "wav", "wav24", "aiff")
DESCRIPTIONS = {
    "standard": "Bred kompatibilitet. Original oppløsning og bildefrekvens beholdes.",
    "standard_hevc": "H.265 for 4K og større. Mindre filer enn H.264 med samme kvalitet.",
    "standard_audio": "MP3 med 192 kbit/s. Spilles av nesten overalt.",
    "h264": "H.264 spilles av på nesten alt, men gir større filer i 4K.",
    "copy": "Kopierer kompatibel video uten kvalitetstap. Lyd konverteres til AAC når det er nødvendig.",
    "small": "H.265 gir ofte mindre filer, men tar lengre tid og kan kreve mer ved redigering.",
    "quality": "Lavere komprimering for høyere kvalitet. Gir vanligvis en større fil.",
    "webm": "VP9 og Opus i WebM for nettsider. Tar lengre tid å konvertere.",
    "prores": "ProRes 422 i MOV for redigering. Krever mye diskplass.",
    "audio": "Lagrer bare det valgte lydsporet som MP3. Ingen video følger med.",
    "audio_wav": "Lagrer bare det valgte lydsporet som ukomprimert WAV for redigering.",
    "aac": "AAC i M4A. God kvalitet og liten fil, passer for Apple og mobil.",
    "flac": "Tapsfri komprimering. Mindre enn WAV, uten kvalitetstap.",
    "ogg": "Vorbis i OGG. Åpent format med god kvalitet.",
    "opus": "Opus gir svært god kvalitet ved lav bitrate. Passer for tale og nett.",
    "alac": "Apple Lossless i M4A. Tapsfri, passer for Apple-enheter.",
    "wav": "Ukomprimert PCM, 16-bit. Stor fil, passer for redigering.",
    "wav24": "Ukomprimert PCM, 24-bit. Mer dynamikk for lydredigering.",
    "aiff": "Ukomprimert PCM, 16-bit, i AIFF for Apple-programmer.",
}


def is_4k(info: MediaInfo) -> bool:
    return bool(info.video) and max(info.video.width, info.video.height) >= 3840


def default_settings(info: MediaInfo) -> ExportSettings:
    if is_4k(info):
        return ExportSettings(name="MP4 · H.265 – Anbefalt", video_codec="libx265", quality=24)
    if info.video:
        return ExportSettings(name="MP4 · H.264 – Anbefalt")
    return ExportSettings(name="MP3 – Anbefalt", container="mp3", video_codec=None, audio_codec="libmp3lame")


def preset_keys(info: MediaInfo) -> tuple[str, ...]:
    if not info.video:
        return AUDIO_PRESETS
    # Den anbefalte kodeken vises bare én gang.
    return tuple(k for k in VIDEO_PRESETS if k != ("small" if is_4k(info) else "h264"))


def preset_description(key: str, info: MediaInfo) -> str:
    if key == "standard":
        key = "standard_hevc" if is_4k(info) else "standard" if info.video else "standard_audio"
    return DESCRIPTIONS.get(key, "Egne innstillinger for valgte filer.")


def _audio_only(name, container, codec, **changes) -> ExportSettings:
    return ExportSettings(name=name, container=container, video_codec=None, audio_codec=codec, **changes)


AUDIO_ONLY = {
    "aac": lambda: _audio_only("M4A · AAC", "m4a", "aac"),
    "flac": lambda: _audio_only("FLAC · tapsfri", "flac", "flac", bit_depth=24),
    "ogg": lambda: _audio_only("OGG · Vorbis", "ogg", "libvorbis"),
    "opus": lambda: _audio_only("Opus", "opus", "libopus", audio_bitrate=128),
    "alac": lambda: _audio_only("M4A · ALAC tapsfri", "alac", "alac", bit_depth=24),
    "wav": lambda: _audio_only("WAV · 16-bit", "wav", "pcm_s16le"),
    "wav24": lambda: _audio_only("WAV · 24-bit", "wav", "pcm_s24le", bit_depth=24),
    "aiff": lambda: _audio_only("AIFF · 16-bit", "aiff", "pcm_s16be"),
}


def preset_settings(key: str, info: MediaInfo) -> ExportSettings:
    base = default_settings(info)
    if key == "standard":
        return base
    if key in {"audio", "audio_wav", *AUDIO_ONLY}:
        if not info.audio:
            raise MediaError("Kilden har ikke lydspor.")
        if key == "audio":
            return _audio_only("Kun lyd · MP3", "mp3", "libmp3lame")
        if key == "audio_wav":
            return _audio_only("Kun lyd · WAV", "wav", "pcm_s16le")
        return AUDIO_ONLY[key]()
    if not info.video:
        raise MediaError("Denne profilen krever video.")
    if key == "h264":
        return replace(base, name="MP4 · H.264", video_codec="libx264", quality=21)
    if key == "small":
        return replace(base, name="MP4 · H.265 – mindre fil", video_codec="libx265", quality=26)
    if key == "quality":
        codec = "H.265" if base.video_codec == "libx265" else "H.264"
        return replace(
            base,
            name=f"MP4 · {codec} – høy kvalitet",
            quality=20 if codec == "H.265" else 17,
            preset="slow",
        )
    if key == "webm":
        return replace(
            base,
            name="WebM · VP9",
            container="webm",
            video_codec="libvpx-vp9",
            audio_codec="libopus",
            quality=32,
            audio_bitrate=128,
        )
    if key == "prores":
        return replace(
            base,
            name="MOV · ProRes 422 – redigering",
            container="mov",
            video_codec="prores_ks",
            audio_codec="pcm_s24le",
            pixel_format="yuv422p10le",
            bit_depth=24,
        )
    if key == "copy":
        audio = "copy" if info.default_audio and info.default_audio.codec in CONTAINERS["mp4"][4] else "aac"
        return replace(base, name="Rask konvertering (stream copy)", video_codec="copy", audio_codec=audio)
    raise MediaError("Ukjent profil.")


def video_choices(container: str, encoders: set[str], info: MediaInfo) -> list[str]:
    families = CONTAINERS[container][3]
    return [
        c
        for c in VIDEO_CODECS
        if (c in encoders and CODEC_FAMILY.get(c) in families)
        or (c == "copy" and info.video and info.video.codec in families)
    ]


def audio_choices(container: str, encoders: set[str], info: MediaInfo, index=None) -> list[str]:
    families = CONTAINERS[container][4]
    stream = next((s for s in info.audio if s.index == index), info.default_audio)
    return [
        c
        for c in AUDIO_CODECS
        if (c in encoders and AUDIO_FAMILY.get(c, c) in families)
        or (c == "copy" and stream and stream.codec in families)
    ]


def pixel_choices(codec: str | None) -> list[str]:
    if codec == "prores_ks":
        return ["yuv422p10le"]
    if CODEC_FAMILY.get(codec) in {"hevc", "av1", "vp9"} and codec in {
        "libx265",
        "libsvtav1",
        "libaom-av1",
        "libvpx-vp9",
    }:
        return ["yuv420p", "yuv420p10le"]
    return ["yuv420p"]


def validate(info: MediaInfo, settings: ExportSettings, encoders: set[str], muxers: set[str]) -> None:
    s = settings
    if s.container not in CONTAINERS or CONTAINERS[s.container][2] not in muxers:
        raise MediaError("Denne containeren finnes ikke i medfølgende FFmpeg.")
    is_video = s.video_codec is not None
    if is_video:
        if not info.video or s.container not in VIDEO_CONTAINERS:
            raise MediaError("Videoeksport krever en videokilde og en video-container.")
        if s.video_codec not in video_choices(s.container, encoders, info):
            raise MediaError("Videokodeken passer ikke i containeren eller er ikke tilgjengelig.")
        if s.video_codec == "copy":
            if s.width or s.height or s.fps or s.aspect or s.deinterlace == "on":
                raise MediaError("Stream copy kan ikke kombineres med videoendringer.")
        elif s.pixel_format not in pixel_choices(s.video_codec):
            raise MediaError("Pikselformatet støttes ikke av valgt encoder.")
        elif info.video.hdr and s.pixel_format != "yuv420p10le":
            raise MediaError(
                "HDR-kilden krever 10-bit HEVC/AV1/VP9 eller stream copy for å bevare fargene. "
                "Velg dette i avanserte innstillinger. Automatisk HDR til SDR støttes ikke."
            )
    elif not info.audio:
        raise MediaError("Kilden inneholder ikke et lydspor som kan eksporteres.")
    elif s.container not in AUDIO_CONTAINERS:
        raise MediaError("Velg et lydformat for eksport uten video.")
    if info.audio:
        if s.audio_stream is not None and not any(a.index == s.audio_stream for a in info.audio):
            raise MediaError("Det valgte lydsporet finnes ikke i kilden.")
        if s.audio_codec not in audio_choices(s.container, encoders, info, s.audio_stream):
            raise MediaError("Lydkodeken passer ikke i containeren eller er ikke tilgjengelig.")
        if s.audio_codec == "copy" and (s.sample_rate or s.channels):
            raise MediaError("Stream copy kan ikke endre samplingsfrekvens eller kanaloppsett.")
        if s.audio_codec in {"flac", "alac"} and s.bit_depth not in {16, 24}:
            raise MediaError("Velg 16 eller 24-bit for tapsfri lyd i denne versjonen.")
        if s.sample_rate not in {0, 8000, 16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000, 192000}:
            raise MediaError("Ugyldig samplingsfrekvens.")
        if s.audio_codec == "libmp3lame" and s.sample_rate not in {0, 32000, 44100, 48000}:
            raise MediaError("MP3 ved 192 kbit/s eller mer krever 32, 44,1 eller 48 kHz.")
        if s.audio_codec == "libopus" and s.sample_rate not in {0, 8000, 16000, 24000, 48000}:
            raise MediaError("Opus støtter 8, 16, 24 eller 48 kHz.")
    if s.quality_mode not in {"quality", "bitrate"} or not 0 <= s.quality <= 51:
        raise MediaError("Ugyldig kvalitetsinnstilling.")
    if not 16 <= s.video_bitrate <= 500000 or not 32 <= s.audio_bitrate <= 320:
        raise MediaError("Ugyldig bitrate.")
    if s.preset not in {"ultrafast", "fast", "medium", "slow"}:
        raise MediaError("Ugyldig encoder preset.")
    if s.channels not in {0, 1, 2} or s.bit_depth not in {16, 24, 32}:
        raise MediaError("Ugyldig lydinnstilling.")
    if s.width < 0 or s.height < 0 or s.width > 16384 or s.height > 16384 or bool(s.width) != bool(s.height):
        raise MediaError("Angi både bredde og høyde, eller behold original oppløsning.")
    if (s.width and s.width % 2) or (s.height and s.height % 2):
        raise MediaError("Bredde og høyde må være partall.")
    if s.fps:
        if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}|/\d{1,5})?", s.fps):
            raise MediaError("Bildefrekvens må være et tall, for eksempel 25 eller 30000/1001.")
        parts = s.fps.split("/")
        rate = (
            float(parts[0]) / float(parts[1])
            if len(parts) == 2 and float(parts[1])
            else (float(parts[0]) if len(parts) == 1 else 0)
        )
        if not 1 <= rate <= 240:
            raise MediaError("Bildefrekvens må være mellom 1 og 240.")
    if s.aspect and s.aspect not in {"16:9", "4:3", "1:1", "9:16"}:
        raise MediaError("Ugyldig sideforhold.")
    if s.deinterlace not in {"auto", "on", "off"}:
        raise MediaError("Ugyldig deinterlacing.")
