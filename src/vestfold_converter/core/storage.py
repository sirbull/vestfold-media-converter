import ctypes
import json
import os
import sys
import uuid
from pathlib import Path

from .models import MediaError


def long_path(path: Path) -> Path:
    """Bruk Windows sitt extended-length-format uten å endre maskinens registerpolicy."""
    absolute = str(path.absolute())
    if os.name == "nt" and len(absolute) >= 240 and not absolute.startswith("\\\\?\\"):
        absolute = "\\\\?\\UNC\\" + absolute[2:] if absolute.startswith("\\\\") else "\\\\?\\" + absolute
    return Path(absolute)


def project_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def bundled_tools() -> tuple[Path, Path]:
    folder = project_root() / "vendor" / "ffmpeg" / "bin"
    suffix = ".exe" if os.name == "nt" else ""
    paths = tuple(folder / (tool + suffix) for tool in ("ffmpeg", "ffprobe"))
    if not all(p.is_file() for p in paths):
        raise MediaError(
            "FFmpeg og FFprobe mangler i programmappen. "
            "Bruk en komplett programmappe, eller kjør scripts/fetch_ffmpeg.ps1 ved utvikling."
        )
    return paths


def documents_folder() -> Path:
    if os.name == "nt":
        # Windows Known Folder API støtter også omdirigerte Dokumenter-mapper. Ingen registerskriving.
        folder_id = uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7")
        guid = (ctypes.c_byte * 16).from_buffer_copy(folder_id.bytes_le)
        result = ctypes.c_wchar_p()
        try:
            status = ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(guid), 0, None, ctypes.byref(result)
            )
            if status == 0 and result.value:
                return Path(result.value)
        finally:
            if result:
                ctypes.windll.ole32.CoTaskMemFree(result)
    return Path.home() / "Documents"


def default_output() -> Path:
    return documents_folder() / "Mediekonverter"


def settings_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / (
        "VestfoldMediaConverter/settings.json"
    )


def load_preferences(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or settings_path()).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_preferences(data: dict, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def preferred_output(preferences: dict) -> Path:
    value = preferences.get("output", "")
    if isinstance(value, str) and value:
        folder = Path(value)
        if folder.is_dir() and os.access(folder, os.W_OK):
            return folder
    return default_output()


def safe_stem(path: Path) -> str:
    # Hold god margin for suffiks og midlertidige navn, også på FAT/exFAT-minnekort.
    stem = path.stem[:120].rstrip(" .") or "konvertert"
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    return f"_{stem}" if stem.upper() in reserved else stem


def publish_file(temporary: Path, folder: Path, stem: str, extension: str, source: Path) -> Path:
    """Publiser uten å overskrive, også ved konkurrerende instanser av programmet."""
    for number in range(10000):
        suffix = "" if number == 0 else f" ({number})"
        target = folder / f"{stem}{suffix}.{extension}"
        if target.resolve() == source.resolve():
            continue
        try:
            if os.name == "nt":
                # Windows rename er atomisk og feiler dersom målet finnes.
                temporary.rename(target)
            else:
                os.link(temporary, target)
                temporary.unlink()
            return target
        except FileExistsError:
            continue
    raise MediaError("Fant ikke et ledig filnavn i målmappen.")
