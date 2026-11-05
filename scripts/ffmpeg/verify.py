"""Kontroller at et FFmpeg-bygg dekker alt appen bruker, og at det ikke har nettverksstøtte.

Bruk:
  python scripts/ffmpeg/verify.py vendor/ffmpeg/bin/ffmpeg.exe
  python scripts/ffmpeg/verify.py vendor/ffmpeg/bin/ffmpeg.exe --capture baseline.json

Kravene hentes fra appens profiler og fra baseline.json, som er det tidligere Gyan-bygget.
Alt som mangler i forhold til baseline, må stå i requirements.json med en begrunnelse.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vestfold_converter.core.process import CREATE_FLAGS
from vestfold_converter.core.profiles import AUDIO_CODECS, CONTAINERS, VIDEO_CODECS


def run(ffmpeg: Path, *args: str) -> str:
    return subprocess.run(
        [str(ffmpeg.resolve()), "-hide_banner", *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_FLAGS,
    ).stdout


def _after_header(text: str) -> list[str]:
    """Linjene etter skillelinjen av bindestreker som avslutter forklaringen øverst."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() and set(line.strip()) == {"-"})
    return lines[start + 1 :]


def _codecs(text: str) -> list[str]:
    return sorted({line.split()[1] for line in _after_header(text) if len(line.split()) > 1})


def _formats(text: str) -> list[str]:
    names = set()
    for line in _after_header(text):
        parts = line.split()
        if len(parts) > 1:
            names.update(parts[1].split(","))
    return sorted(names)


def capabilities(ffmpeg: Path) -> dict:
    protocols, section = {"input": [], "output": []}, None
    for line in run(ffmpeg, "-protocols").splitlines():
        if line.strip() in {"Input:", "Output:"}:
            section = line.strip()[:-1].lower()
        elif section and line.startswith("  "):
            protocols[section].append(line.strip())
    filters = sorted(
        m.group(1)
        for line in run(ffmpeg, "-filters").splitlines()
        if (m := re.match(r"^ \S+ (\S+)\s+\S+->", line))
    )
    return {
        "encoders": _codecs(run(ffmpeg, "-encoders")),
        "decoders": _codecs(run(ffmpeg, "-decoders")),
        "muxers": _formats(run(ffmpeg, "-muxers")),
        "demuxers": _formats(run(ffmpeg, "-demuxers")),
        "filters": filters,
        "protocols": protocols,
    }


def pixel_formats(ffmpeg: Path, encoder: str) -> set[str]:
    text = run(ffmpeg, "-h", f"encoder={encoder}")
    match = re.search(r"Supported pixel formats: (.*)", text)
    return set(match.group(1).split()) if match else set()


def verify(ffmpeg: Path) -> list[str]:
    requirements = json.loads((HERE / "requirements.json").read_text(encoding="utf-8"))
    baseline = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    found = capabilities(ffmpeg)
    problems = []

    def require(kind, names, why):
        missing = sorted(set(names) - set(found[kind]))
        if missing:
            problems.append(f"Mangler {kind} ({why}): {', '.join(missing)}")

    app_encoders = (set(VIDEO_CODECS) | set(AUDIO_CODECS)) - {"copy"}
    require("encoders", (app_encoders & set(baseline["encoders"])) | set(requirements["encoders"]), "appen")
    require("muxers", {c[2] for c in CONTAINERS.values()} | set(requirements["muxers"]), "appen")
    require("filters", requirements["filters"], "appen")
    for kind in ("decoders", "demuxers"):
        excluded = requirements["excluded"][kind]
        require(kind, set(baseline[kind]) - set(excluded), "innlesing som før")
        unexpected = sorted(set(excluded) & set(found[kind]))
        if unexpected:
            problems.append(f"Står som utelatt, men finnes: {kind} {', '.join(unexpected)}")
    for encoder, formats in requirements["pixel_formats"].items():
        missing = set(formats) - pixel_formats(ffmpeg, encoder)
        if missing:
            problems.append(f"{encoder} mangler pikselformat: {', '.join(sorted(missing))}")
    allowed = set(requirements["protocols_allowed"])
    for direction, names in found["protocols"].items():
        extra = sorted(set(names) - allowed)
        if extra:
            problems.append(f"Ikke tillatte {direction}-protokoller (nettverk?): {', '.join(extra)}")
    configuration = run(ffmpeg, "-version")
    for flag in requirements["configure_required"]:
        if flag not in configuration:
            problems.append(f"Bygget mangler {flag}")
    for flag in requirements["configure_forbidden"]:
        if flag in configuration:
            problems.append(f"Bygget har {flag}")
    return problems


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("ffmpeg", type=Path)
    parser.add_argument("--capture", type=Path, help="Skriv bare bygget sine egenskaper til denne filen")
    options = parser.parse_args()
    if options.capture:
        options.capture.write_text(
            json.dumps(capabilities(options.ffmpeg), indent=1) + "\n", encoding="utf-8"
        )
        raise SystemExit(0)
    issues = verify(options.ffmpeg)
    for issue in issues:
        print(f"FEIL: {issue}")
    print("FFmpeg-bygget dekker appens behov." if not issues else f"{len(issues)} avvik.")
    raise SystemExit(1 if issues else 0)
