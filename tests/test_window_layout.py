from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QScrollBar

from vestfold_converter.ui import MainWindow


@pytest.mark.parametrize("width,height", [(1280, 752), (1024, 640), (800, 560)])
def test_startup_fits_work_area_and_shows_all_main_controls(
    qtbot, engine, tmp_path, monkeypatch, width, height
):
    # Logiske skjermmål tilsvarer også en stor fysisk skjerm med Windows-skalering.
    available = QRect(0, 0, width, height)
    screen = SimpleNamespace(availableGeometry=lambda: available)
    monkeypatch.setattr(MainWindow, "screen", lambda _: screen)
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(20)
    qtbot.waitUntil(lambda: available.contains(window.frameGeometry()), timeout=3000)
    assert not window.isMaximized()
    for control in (
        window.add_files,
        window.add_folder,
        window.drop_area,
        window.destination_card,
        window.open_folder,
        window.convert,
        window.theme,
    ):
        assert control.isVisible()
        assert available.contains(QRect(control.mapToGlobal(QPoint(0, 0)), control.size()))
    assert not any(
        bar.isVisible() and bar.orientation() == Qt.Orientation.Vertical
        for bar in window.findChildren(QScrollBar)
    )
