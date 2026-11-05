import pytest
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox

from vestfold_converter.appearance import (
    DARK,
    RoundedComboBox,
    ThemeSwitcher,
    configure_typography,
    line_icon,
    stylesheet,
)
from vestfold_converter.storage import load_preferences, save_preferences
from vestfold_converter.ui import DropArea, MainWindow


def test_drop_action_and_outer_area_each_request_import_once(qtbot):
    widget = DropArea()
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    requests = []
    widget.clicked.connect(lambda checked=False: requests.append("import"))
    qtbot.mouseClick(widget.action_button, Qt.MouseButton.LeftButton)
    assert len(requests) == 1
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
    assert len(requests) == 2
    widget.setEnabled(False)
    qtbot.mouseClick(widget.action_button, Qt.MouseButton.LeftButton)
    assert len(requests) == 2


@pytest.mark.parametrize("size", [18, 20, 22, 24, 25])
@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 1.75, 2.0, 3.0])
def test_line_icons_render_at_requested_screen_resolution(qapp, size, scale):
    pixmap = line_icon("folder", "#005260").pixmap(QSize(size, size), scale)
    assert pixmap.size() == QSize(size, size) * scale
    assert pixmap.devicePixelRatio() == scale
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    alpha = memoryview(image.constBits())[3::4]
    assert max(alpha) > 200
    assert any(0 < value < 200 for value in alpha)
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() == 0


def test_copied_line_icon_keeps_disabled_state_and_transparency(qapp):
    icon = QIcon(line_icon("play", "#ffffff"))
    icon.setIsMask(True)  # Detach the copy, as Qt does when changing icon properties.
    normal = icon.pixmap(QSize(24, 24), 1.5).toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    disabled = icon.pixmap(QSize(24, 24), 1.5, QIcon.Mode.Disabled).toImage().convertToFormat(
        QImage.Format.Format_RGBA8888
    )
    assert max(memoryview(normal.constBits())[3::4]) > 200
    assert not disabled.isNull()
    assert max(memoryview(disabled.constBits())[3::4]) > 0
    assert disabled.pixelColor(0, 0).alpha() == 0


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
