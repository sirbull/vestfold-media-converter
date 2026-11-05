"""Prosesser uten shell, PATH-oppslag eller synlig Windows-konsoll."""

import os
import subprocess
import threading
import time
from pathlib import Path

from .models import Cancelled, MediaError

CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def powershell(script: str) -> list[str]:
    """Windows PowerShell med absolutt sti, uten brukerprofil. Skriptet er alltid fast tekst."""
    executable = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    return [str(executable), "-NoProfile", "-NonInteractive", "-Command", script]


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def capture(args: list[str], cancel: threading.Event | None = None, timeout: float = 45) -> str:
    started = time.monotonic()
    try:
        with subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=CREATE_FLAGS
        ) as process:
            try:
                while True:
                    if cancel and cancel.is_set():
                        raise Cancelled("Avbrutt")
                    if time.monotonic() - started > timeout:
                        raise MediaError("Medieanalysen brukte for lang tid. Kontroller at filen kan leses.")
                    try:
                        out, err = process.communicate(timeout=0.15)
                        break
                    except subprocess.TimeoutExpired:
                        continue
                if process.returncode:
                    detail = err.decode("utf-8", errors="replace")[-2500:]
                    raise MediaError(f"Kunne ikke lese mediet. {detail}")
                return out.decode("utf-8", errors="replace")
            finally:
                stop_process(process)
    except OSError as exc:
        raise MediaError(f"Kunne ikke starte medieverktøyet: {exc}") from exc
