"""Lag lisenssamling, inventar og SHA-256 for den faktiske byggmappen."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vestfold_converter.process import CREATE_FLAGS


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def prepare_licenses():
    folder = ROOT / "build" / "licenses"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", folder / "APPLICATION-GPL-3.0.txt")
    shutil.copytree(ROOT / "licenses", folder / "standard-licenses", dirs_exist_ok=True)
    shutil.copy2(ROOT / "src/vestfold_converter/assets/fonts/OFL.txt", folder / "Nunito-OFL-1.1.txt")
    for dependency in ("PySide6-Essentials", "shiboken6", "pyinstaller", "pyinstaller-hooks-contrib"):
        dist = importlib.metadata.distribution(dependency)
        for file in dist.files or []:
            if any(part.lower() in {"licenses", "license_files"} for part in file.parts) or (
                file.name.lower().startswith(("license", "copying", "copyright"))
            ):
                original = Path(dist.locate_file(file))
                if original.is_file():
                    target = folder / dependency / str(file).replace("..", "parent")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, target)
    for filename in ("LICENSE.txt", "LICENSE", "LICENSE.rst"):
        license_file = Path(sys.base_prefix) / filename
        if license_file.is_file():
            shutil.copy2(license_file, folder / "PYTHON-LICENSE.txt")
            break
    else:
        raise RuntimeError("Python-lisenstekst mangler i valgt Python-distribusjon.")
    vendor = ROOT / "vendor" / "ffmpeg" / "licenses"
    for path in vendor.glob("*"):
        if path.is_file():
            shutil.copy2(path, folder / path.name)
    return folder


def audit(folder: Path):
    ffmpeg = folder / "_internal" / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"

    def run(*args):
        return subprocess.run(
            [str(ffmpeg), *args],
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_FLAGS,
        ).stdout

    version = run("-version")
    license_text = run("-L")
    if "--enable-nonfree" in version:
        raise RuntimeError("Denne FFmpeg-bygningen kan ikke redistribueres: --enable-nonfree.")
    if "--enable-gpl" not in version:
        raise RuntimeError("Forventet GPL-bygning for libx264/libx265. Kontroller lisensgrunnlaget.")
    packages = {
        name: importlib.metadata.version(name)
        for name in ("PySide6-Essentials", "shiboken6", "pyinstaller", "pyinstaller-hooks-contrib")
    }
    manifest = {
        "application": "Vestfold Media Converter",
        "version": "0.1.0",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": packages,
        "ffmpeg_version": version,
        "ffmpeg_license": license_text,
        "origin": json.loads((ROOT / "vendor/ffmpeg/origin.json").read_text()),
        "executables": [p.relative_to(folder).as_posix() for p in sorted(folder.rglob("*.exe"))],
        "distribution_status": "Teknisk testbygg. Tilsvarende kildekode for eksterne FFmpeg-biblioteker må avklares før deling.",
    }
    (folder / "BUILD-INFO.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    source = ROOT / "build" / "source" / "vestfold-media-converter"
    source.mkdir(parents=True, exist_ok=True)
    for name in ("src", "scripts", "tests", "docs", "licenses"):
        shutil.copytree(
            ROOT / name,
            source / name,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for name in (
        "pyproject.toml",
        "uv.lock",
        "VestfoldMediaConverter.spec",
        "README.md",
        "LICENSE",
        "IT-GODKJENNING.md",
        ".python-version",
    ):
        shutil.copy2(ROOT / name, source / name)
    shutil.make_archive(str(folder / "APPLICATION-SOURCE"), "zip", source.parent)
    rows = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            rows.append(f"{digest(path)}  {path.relative_to(folder).as_posix()}")
    (folder / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Inventar og kontrollsummer skrevet: {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--audit", type=Path)
    options = parser.parse_args()
    if options.prepare:
        prepare_licenses()
    if options.audit:
        audit(options.audit.resolve())
