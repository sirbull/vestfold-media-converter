from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidgetAction

from vestfold_converter.ui.path_bar import PathBar
from vestfold_converter.ui.theme import DARK, LIGHT, stylesheet


@pytest.mark.parametrize("colors", [LIGHT, DARK])
def test_overflow_exposes_full_path_and_every_ancestor(qtbot, tmp_path, colors):
    directory = tmp_path / "OneDrive – Skole & medier" / "Undervisning 2026-2027" / "Opptak æøå"
    bar = PathBar(framed=True)
    qtbot.addWidget(bar)
    bar.setStyleSheet(stylesheet(colors))
    bar.resize(280, 36)
    bar.set_path(directory)
    bar.show()
    qtbot.waitUntil(bar.overflow.isVisible)
    assert any(not button.isVisible() for button in bar.buttons)
    assert bar.buttons[-1].isVisible()
    qtbot.mouseClick(bar.overflow, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(bar.popup_menu.isVisible)
    actions = bar.popup_menu.actions()
    header = next(action.defaultWidget() for action in actions if isinstance(action, QWidgetAction))
    assert isinstance(header, QLabel)
    assert header.text() == str(directory)
    folders = [Path(action.data()) for action in actions if action.data()]
    assert folders == [*reversed(directory.parents), directory]
    target = directory.parent.parent
    action = next(action for action in actions if action.data() and Path(action.data()) == target)
    with qtbot.waitSignal(bar.folderClicked) as signal:
        qtbot.mouseClick(
            bar.popup_menu, Qt.MouseButton.LeftButton, pos=bar.popup_menu.actionGeometry(action).center()
        )
    assert Path(signal.args[0]) == target
    bar.resize(2500, 36)
    qtbot.waitUntil(lambda: not bar.overflow.isVisible())
    assert all(button.isVisible() for button in bar.buttons)


def test_long_single_component_and_filename_stay_within_bar(qtbot, tmp_path):
    bar = PathBar()
    qtbot.addWidget(bar)
    bar.setStyleSheet(stylesheet(LIGHT))
    bar.resize(220, 36)
    directory = tmp_path / ("Et langt mappenavn " * 8)
    filename = "Et langt filnavn " * 8 + ".mp4"
    bar.set_path(directory, filename)
    bar.show()
    qtbot.waitUntil(bar.overflow.isVisible)
    assert bar.width() == 220
    assert bar.toolTip() == str(directory / filename)
    for widget in [*bar.buttons, *bar._labels, bar.overflow]:
        if widget.isVisible():
            assert bar.rect().contains(widget.geometry())
