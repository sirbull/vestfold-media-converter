import os
import signal
import sys

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .core.engine import MediaEngine
from .core.models import MediaError
from .core.storage import bundled_tools
from .ui.main_window import MainWindow
from .ui.theme import configure_typography


def main() -> int:
    arguments = list(sys.argv)
    # FreeType gives the bundled variable font smooth outlines at fractional DPI.
    # Keep explicit Qt platform choices (including headless tests) intact.
    if (
        sys.platform == "win32"
        and not os.environ.get("QT_QPA_PLATFORM")
        and not any(arg == "-platform" or arg.startswith("-platform=") for arg in arguments)
    ):
        arguments += ["-platform", "windows:fontengine=freetype"]
    app = QApplication(arguments)
    app.setApplicationName("Vestfold Media Converter")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("VestfoldMediaConverter")
    app.setStyle("Fusion")
    configure_typography()
    QLocale.setDefault(QLocale("nb_NO"))
    try:
        window = MainWindow(MediaEngine(*bundled_tools()))
    except MediaError as exc:
        QMessageBox.critical(None, "Programfilene er ufullstendige", str(exc))
        return 1
    window.show()
    # Ctrl+C in a terminal closes the window normally instead of raising
    # KeyboardInterrupt inside a Qt callback, which Qt only prints.
    signal.signal(signal.SIGINT, lambda *_: window.close())
    # Python only sees the signal while running Python code; wake it regularly.
    wake = QTimer()
    wake.timeout.connect(lambda: None)
    wake.start(200)
    return app.exec()
