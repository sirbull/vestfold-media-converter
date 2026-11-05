import os
import subprocess
import sys

from vestfold_converter.core.process import CREATE_FLAGS


def test_real_application_startup(engine, tmp_path):
    """Test app.main med eget QApplication, faktisk FFmpeg-oppstart og norsk locale."""
    script = """
import os
from pathlib import Path
from PySide6.QtCore import QLocale, QPoint, QRect, QTimer
from PySide6.QtWidgets import QApplication
from vestfold_converter import app

original_window = app.MainWindow

def create_window(engine):
    window = original_window(engine, preferences_path=Path(os.environ['VMC_TEST_PREFERENCES']))

    def finish():
        if window.busy:
            QTimer.singleShot(25, finish)
            return
        valid = (bool(engine.encoders and engine.muxers) and QLocale().name() == 'nb_NO'
                 and QApplication.instance().font().family() == 'Nunito'
                 and window.screen().availableGeometry().contains(window.frameGeometry())
                 and window.screen().availableGeometry().contains(
                     QRect(window.convert.mapToGlobal(QPoint(0, 0)), window.convert.size())))
        window.close()
        QApplication.instance().exit(0 if valid else 2)

    QTimer.singleShot(25, finish)
    return window

app.MainWindow = create_window
raise SystemExit(app.main())
"""
    environment = dict(
        os.environ, QT_QPA_PLATFORM="offscreen", VMC_TEST_PREFERENCES=str(tmp_path / "settings.json")
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_FLAGS,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
