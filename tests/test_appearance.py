import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox

from vestfold_converter.appearance import (
    DARK,
    RoundedComboBox,
    ThemeSwitcher,
    configure_typography,
    stylesheet,
)
from vestfold_converter.storage import load_preferences, save_preferences
from vestfold_converter.ui import MainWindow


def format_picker(qtbot, points=10):
    configure_typography()
    widget = RoundedComboBox()
    qtbot.addWidget(widget)
    for text, value in (
        ("MP4 – Anbefalt", "standard"),
        ("Høy kvalitet", "quality"),
        ("Redigeringsformat (ProRes)", "prores"),
    ):
        widget.addItem(text, value)
    widget.setStyleSheet(stylesheet(DARK) + f"QComboBox {{ font-size: {points}pt; }}")
    widget.set_popup_colors(DARK)
    widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    widget.setMinimumContentsLength(14)
    widget.show()
    widget.adjustSize()
    return widget


@pytest.mark.parametrize("points", [10, 18])
def test_format_text_fits_before_arrow(qtbot, points):
    widget = format_picker(qtbot, points)
    for index in range(widget.count()):
        widget.setCurrentIndex(index)
        option = QStyleOptionComboBox()
        widget.initStyleOption(option)
        text_area = widget.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option, QStyle.SubControl.SC_ComboBoxEditField, widget
        )
        assert text_area.width() >= widget.fontMetrics().horizontalAdvance(widget.currentText())


def test_rounded_popup_keeps_keyboard_selection(qtbot):
    widget = format_picker(qtbot)
    widget.showPopup()
    popup = widget.view().window()
    qtbot.waitUntil(popup.isVisible)
    assert not popup.mask().isEmpty()
    assert not popup.mask().contains(QPoint(0, 0))
    assert popup.mask().contains(popup.rect().center())
    qtbot.keyClick(widget.view(), Qt.Key.Key_Down)
    qtbot.keyClick(widget.view(), Qt.Key.Key_Return)
    assert widget.currentData() == "quality"
    assert not popup.isVisible()


def test_theme_icons_are_exclusive_and_support_keyboard(qtbot):
    configure_typography()
    widget = ThemeSwitcher()
    qtbot.addWidget(widget)
    widget.setStyleSheet(stylesheet(DARK))
    widget.set_colors(DARK)
    widget.show()
    for mode in ("light", "dark", "system"):
        qtbot.mouseClick(widget.buttons[mode], Qt.MouseButton.LeftButton)
        assert widget.mode() == mode
        assert [name for name, button in widget.buttons.items() if button.isChecked()] == [mode]
    qtbot.mouseClick(widget.buttons["system"], Qt.MouseButton.LeftButton)
    assert widget.buttons["system"].isChecked()
    qtbot.keyClick(widget.buttons["system"], Qt.Key.Key_Right)
    assert widget.mode() == "light"
    qtbot.keyClick(widget.buttons["light"], Qt.Key.Key_Home)
    qtbot.keyClick(widget.buttons["system"], Qt.Key.Key_Left)
    assert widget.mode() == "dark"


def test_theme_icon_choice_updates_app_and_is_remembered(qtbot, engine, tmp_path):
    path = tmp_path / "settings.json"
    save_preferences({"theme": "dark"}, path)
    window = MainWindow(engine, initialize=False, preferences_path=path)
    qtbot.addWidget(window)
    window.show()
    assert window.theme.buttons["dark"].isChecked()
    assert window.table.property("dark") is True
    qtbot.mouseClick(window.theme.buttons["light"], Qt.MouseButton.LeftButton)
    assert window.table.property("dark") is False
    window.close()
    assert load_preferences(path)["theme"] == "light"
    restored = MainWindow(engine, initialize=False, preferences_path=path)
    qtbot.addWidget(restored)
    assert restored.theme.buttons["light"].isChecked()
