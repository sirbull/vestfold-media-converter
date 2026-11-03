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
    app = QApplication(sys.argv)
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
