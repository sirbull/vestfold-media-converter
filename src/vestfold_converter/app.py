import os
import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .appearance import configure_typography
from .engine import MediaEngine
from .models import MediaError
from .storage import bundled_tools
from .ui import MainWindow


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
    app.setApplicationName("Vestfold media converter")
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
    return app.exec()
