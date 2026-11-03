from PySide6.QtCore import Qt

from vestfold_converter.ui import MainWindow


def wait_idle(qtbot, window):
    qtbot.waitUntil(lambda: not window.busy, timeout=90000)


def test_mixed_queue_one_click(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.output_folder = tmp_path / "resultater"
    window.show()
    window.import_files([media["mts"], media["wav"], media["artwork"]])
    wait_idle(qtbot, window)
    assert [item.settings.container for item in window.items] == ["mp4", "mp3", "mp3"]
    assert not window.panel.toggle.isChecked()
    assert window.convert.isEnabled()
    qtbot.mouseClick(window.convert, Qt.MouseButton.LeftButton)
    wait_idle(qtbot, window)
    assert all(item.status == "Fullført" for item in window.items)
    assert "3 filer konvertert" in window.message.text()
    assert window.total_progress.value() == 1000


def test_audio_panel_has_no_video_options(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    window.import_files([media["wav"]])
    wait_idle(qtbot, window)
    panel = window.panel
    window.inspector.setCurrentIndex(1)
    qtbot.mouseClick(panel.toggle, Qt.MouseButton.LeftButton)
    assert not panel.vcodec.isVisible()
    assert not panel.vbitrate.isVisible()
    assert all(
        panel.container.itemData(i) not in {"mp4", "mov", "mkv", "webm", "avi"}
        for i in range(panel.container.count())
    )
    panel.container.setCurrentIndex(panel.container.findData("wav"))
    assert panel.acodec.count() >= 3
    qtbot.mouseClick(panel.apply_button, Qt.MouseButton.LeftButton)
    assert window.items[0].settings.container == "wav"


def test_video_dynamic_containers_and_multi_selection(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    window.import_files([media["mp4"], media["mov"]])
    wait_idle(qtbot, window)
    window.table.selectAll()
    window.apply_preset("prores")
    assert all(i.settings.container == "mov" and i.settings.video_codec == "prores_ks" for i in window.items)
    panel = window.panel
    window.inspector.setCurrentIndex(1)
    panel.toggle.setChecked(True)
    panel.container.setCurrentIndex(panel.container.findData("webm"))
    assert "libx264" not in [panel.vcodec.itemData(i) for i in range(panel.vcodec.count())]


def test_close_cancels_background_work(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    window.import_files([media["mp4"]] * 50)
    window.close()
    wait_idle(qtbot, window)
    assert not window.isVisible()
