"""Lag lisenssamling, kildearkiv, SBOM, inventar og SHA-256 for den faktiske byggmappen."""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vestfold_converter import __version__
from vestfold_converter.core.process import CREATE_FLAGS

PYTHON_PACKAGES = ("PySide6-Essentials", "shiboken6", "pywin32", "pyinstaller", "pyinstaller-hooks-contrib")
PACKAGE_LICENSES = {
    "PySide6-Essentials": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only",
    "shiboken6": "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only",
    "pywin32": "PSF-2.0",
    "pyinstaller": "GPL-2.0-or-later WITH Bootloader-exception",
    "pyinstaller-hooks-contrib": "GPL-2.0-or-later OR Apache-2.0",
}
VENDOR = ROOT / "vendor" / "ffmpeg"


def _load_ffmpeg_verifier():
    spec = importlib.util.spec_from_file_location("ffmpeg_verify", ROOT / "scripts" / "ffmpeg" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def prepare_licenses():
    folder = ROOT / "build" / "licenses"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", folder / "APPLICATION-GPL-3.0.txt")
    shutil.copytree(ROOT / "licenses", folder / "standard-licenses", dirs_exist_ok=True)
    shutil.copy2(ROOT / "src/vestfold_converter/assets/fonts/OFL.txt", folder / "Nunito-OFL-1.1.txt")
    for dependency in PYTHON_PACKAGES:
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
    # FFmpeg og hvert bibliotek som er lenket inn i den, med egne undermapper.
    shutil.copytree(VENDOR / "licenses", folder / "ffmpeg", dirs_exist_ok=True)
    return folder


def prepare_icon(sizes=(16, 20, 24, 32, 40, 48, 64, 128, 256)):
    """Lag EXE-ikonet fra appens SVG. ICO-filen består av PNG-bilder i hver størrelse."""
    import struct

    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication(["distribution", "-platform", "offscreen"])
    renderer = QSvgRenderer(str(ROOT / "src/vestfold_converter/assets/vmc-ikon.svg"))
    if not renderer.isValid():
        raise RuntimeError("Kunne ikke lese vmc-ikon.svg.")
    images = []
    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        target = renderer.viewBoxF().size().scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio)
        renderer.render(
            painter,
            QRectF(
                (size - target.width()) / 2, (size - target.height()) / 2, target.width(), target.height()
            ),
        )
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        images.append((size, bytes(data)))
    del app
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = b"", b""
    for size, png in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
        payload += png
    target = ROOT / "build" / "vmc-ikon.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(header + entries + payload)
    return target


def _sbom(folder: Path, packages: dict, ffmpeg_build: dict) -> dict:
    """CycloneDX 1.5-oversikt over alle komponenter som følger med, for IT sin analyse."""

    def license_of(expression):
        return [{"expression": expression}] if " " in expression else [{"license": {"id": expression}}]

    def shipped(relative):
        return [{"alg": "SHA-256", "content": digest(folder / relative)}]

    def library(name, info):
        component = {
            "type": "library",
            "name": name,
            "version": info["version"],
            "licenses": license_of(info["license"]),
            "externalReferences": [
                {"type": "website", "url": info["homepage"]},
                {"type": "distribution", "url": info.get("url") or info["git"]},
            ],
        }
        if info.get("sha256"):
            component["hashes"] = [{"alg": "SHA-256", "content": info["sha256"]}]
        if info.get("commit"):
            component["properties"] = [{"name": "vmc:git-commit", "value": info["commit"]}]
        return component

    components = [
        {
            "type": "framework",
            "name": "CPython",
            "version": platform.python_version(),
            "licenses": license_of("PSF-2.0"),
            "purl": f"pkg:generic/cpython@{platform.python_version()}",
        },
        *(
            {
                "type": "library",
                "name": name,
                "version": version,
                "licenses": license_of(PACKAGE_LICENSES[name]),
                "purl": f"pkg:pypi/{name.lower()}@{version}",
            }
            for name, version in packages.items()
        ),
        {
            "type": "application",
            "name": "FFmpeg",
            "version": ffmpeg_build["ffmpeg_version"],
            "description": "Eget, minimalt bygg uten nettverksstøtte. Kildekoden ligger i source/.",
            "licenses": license_of("GPL-3.0-or-later"),
            "hashes": shipped("_internal/vendor/ffmpeg/bin/ffmpeg.exe"),
            "properties": [{"name": "vmc:configure", "value": " ".join(ffmpeg_build["configure_flags"])}],
            "components": [
                library(name, info) for name, info in ffmpeg_build["components"].items() if name != "ffmpeg"
            ],
        },
        {
            "type": "file",
            "name": "Nunito",
            "licenses": license_of("OFL-1.1"),
            "hashes": shipped("_internal/vestfold_converter/assets/fonts/Nunito-wght.ttf"),
        },
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "component": {
                "type": "application",
                "name": "Vestfold Media Converter",
                "version": __version__,
                "licenses": license_of("GPL-3.0-or-later"),
                "hashes": shipped("VestfoldMediaConverter.exe"),
            },
        },
        "components": components,
    }


def _application_source(target: Path) -> None:
    """Appens egen kildekode, samlet i en tom mappe så slettede filer ikke blir med."""
    source = ROOT / "build" / "source" / "vestfold-media-converter"
    shutil.rmtree(source, ignore_errors=True)
    source.mkdir(parents=True)
    for name in ("src", "scripts", "tests", "docs", "licenses", "installer", ".github"):
        shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in (
        "pyproject.toml",
        "uv.lock",
        "VestfoldMediaConverter.spec",
        "README.md",
        "LICENSE",
        "IT-GODKJENNING.md",
        ".python-version",
        ".gitattributes",
    ):
        shutil.copy2(ROOT / name, source / name)
    shutil.make_archive(str(target / "APPLICATION-SOURCE"), "zip", source.parent)


def audit(folder: Path):
    ffmpeg = folder / "_internal" / "vendor" / "ffmpeg" / "bin" / "ffmpeg.exe"
    problems = _load_ffmpeg_verifier()(ffmpeg)
    if problems:
        raise RuntimeError("FFmpeg-bygget oppfyller ikke kravene:\n" + "\n".join(problems))
    origin = json.loads((VENDOR / "origin.json").read_text(encoding="utf-8"))
    ffmpeg_source = VENDOR / "source" / origin.get("source", "")
    if origin.get("provider") != "vmc" or not origin.get("source") or not ffmpeg_source.is_file():
        raise RuntimeError(
            "Kildekoden til FFmpeg mangler, og bygget kan ikke distribueres uten den. "
            "Kjør scripts/fetch_ffmpeg.ps1 med -Package og -Source."
        )
    if digest(ffmpeg_source) != origin["source_sha256"]:
        raise RuntimeError("FFmpeg-kildearkivet har endret seg etter at det ble installert.")
    ffmpeg_build = json.loads((VENDOR / "BUILD-INFO.json").read_text(encoding="utf-8"))

    def run(*args):
        return subprocess.run(
            [str(ffmpeg), *args],
            check=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_FLAGS,
        ).stdout

    packages = {name: importlib.metadata.version(name) for name in PYTHON_PACKAGES}
    target = folder / "source"
    target.mkdir(exist_ok=True)
    shutil.copy2(ffmpeg_source, target / ffmpeg_source.name)
    _application_source(target)
    manifest = {
        "application": "Vestfold Media Converter",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": packages,
        "ffmpeg_version": run("-version"),
        "ffmpeg_license": run("-L"),
        "ffmpeg_build": ffmpeg_build,
        "origin": origin,
        "executables": [p.relative_to(folder).as_posix() for p in sorted(folder.rglob("*.exe"))],
        "distribution_status": (
            "Klar for IT-vurdering. Tilsvarende kildekode for appen, FFmpeg og alle bibliotek "
            "som er lenket inn i FFmpeg, ligger i source/."
        ),
    }
    (folder / "BUILD-INFO.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (folder / "SBOM.cdx.json").write_text(
        json.dumps(_sbom(folder, packages, ffmpeg_build), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    rows = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            rows.append(f"{digest(path)}  {path.relative_to(folder).as_posix()}")
    (folder / "SHA256SUMS.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Inventar, SBOM og kontrollsummer skrevet: {folder}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--audit", type=Path)
    options = parser.parse_args()
    if options.prepare:
        prepare_licenses()
        prepare_icon()
    if options.audit:
        audit(options.audit.resolve())
