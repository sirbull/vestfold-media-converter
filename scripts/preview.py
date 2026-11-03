"""Lag reproduserbare Qt-skjermbilder med lokale syntetiske medier."""

import os
import subprocess
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from vestfold_converter.appearance import configure_typography
from vestfold_converter.engine import MediaEngine
from vestfold_converter.process import CREATE_FLAGS
from vestfold_converter.storage import bundled_tools
from vestfold_converter.ui import MainWindow

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "preview"
OUT.mkdir(parents=True, exist_ok=True)
engine = MediaEngine(*bundled_tools())
engine.discover()
for filename, inputs in (
    (
        "Skoleopptak.MTS",
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=128x72:r=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-c:v",
            "libx264",
            "-c:a",
            "ac3",
            "-f",
            "mpegts",
        ],
    ),
    ("Lydopptak.wav", ["-f", "lavfi", "-i", "sine=frequency=440", "-c:a", "pcm_s16le"]),
):
    target = OUT / filename
    if not target.exists():
        subprocess.run(
            [str(engine.ffmpeg), "-v", "error", *inputs, "-t", "1", str(target)],
            check=True,
            capture_output=True,
            creationflags=CREATE_FLAGS,
        )

app = QApplication([])
configure_typography()
app.setStyle("Fusion")
window = MainWindow(engine, initialize=False, preferences_path=OUT / "settings.json")
window.theme.set_mode("light")
window.show()
app.processEvents()
window.grab().save(str(OUT / "empty-light.png"))
window.resize(900, 600)
app.processEvents()
window.grab().save(str(OUT / "empty-small-light.png"))
window.resize(1240, 780)
app.processEvents()
window.import_files([OUT / "Skoleopptak.MTS", OUT / "Lydopptak.wav"])
preview_deadline = time.monotonic() + 15


def finished():
    if window.busy:
        QTimer.singleShot(50, finished)
        return
    if window.preview.canvas.image.isNull() and time.monotonic() < preview_deadline:
        QTimer.singleShot(50, finished)
        return
    app.processEvents()
    window.grab().save(str(OUT / "queue-light.png"))
    window.theme.grab().save(str(OUT / "theme-control-light.png"))
    window.theme.set_mode("dark")
    app.processEvents()
    window.grab().save(str(OUT / "queue-dark.png"))
    window.theme.grab().save(str(OUT / "theme-control-dark.png"))
    window.inspector.setCurrentIndex(1)
    window.panel.toggle.setChecked(True)
    app.processEvents()
    window.grab().save(str(OUT / "advanced-dark.png"))
    window.panel.toggle.setChecked(False)
    window.inspector.setCurrentIndex(0)
    window.resize(900, 600)
    window.theme.set_mode("light")
    app.processEvents()
    window.grab().save(str(OUT / "small-light.png"))
    window.close()
    app.quit()


QTimer.singleShot(50, finished)
app.exec()
print(f"Skjermbilder lagret i {OUT}")
