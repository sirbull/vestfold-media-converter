"""Kontroller vindu og hovedkontroller mot faktisk arbeidsflate og Windows-DPI."""

import json
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QTimer
from PySide6.QtWidgets import QApplication

from vestfold_converter.engine import MediaEngine
from vestfold_converter.storage import bundled_tools
from vestfold_converter.ui import MainWindow

output = Path(__file__).resolve().parents[1] / "artifacts" / "layout"
output.mkdir(parents=True, exist_ok=True)
app = QApplication([])
app.setStyle("Fusion")
window = MainWindow(MediaEngine(*bundled_tools()), initialize=False,
                    preferences_path=output / "settings.json")
window.show()


def check():
    available = window.screen().availableGeometry()
    controls = {}
    for name in ("add_files", "add_folder", "drop_area", "destination_card", "open_folder", "convert", "theme"):
        widget = getattr(window, name)
        rect = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())
        controls[name] = widget.isVisible() and available.contains(rect)
    result = {
        "available": available.getRect(), "frame": window.frameGeometry().getRect(),
        "client": window.size().toTuple(), "device_pixel_ratio": window.screen().devicePixelRatio(),
        "frame_fits": available.contains(window.frameGeometry()), "maximized": window.isMaximized(),
        "controls_fit": controls,
    }
    window.grab().save(str(output / "startup.png"))
    (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    window.close()
    app.exit(0 if result["frame_fits"] and all(controls.values()) and not result["maximized"] else 1)


QTimer.singleShot(350, check)
raise SystemExit(app.exec())
