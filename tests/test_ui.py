from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from vestfold_converter.ui.details import FileDetailsDialog
from vestfold_converter.ui.main_window import MainWindow


def wait_idle(qtbot, window):
    qtbot.waitUntil(lambda: not window.busy, timeout=90000)


def test_many_short_jobs_release_their_worker_once(qtbot, engine, tmp_path):
    # Korte jobber rett etter hverandre gjør at opprydding i arbeidertråden og i
    # hovedtråden ville overlappe hvis arbeideren ble slettet begge steder.
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    for _ in range(300):
        window.start_job("analyze", paths=[], known=[])
        wait_idle(qtbot, window)
        assert window.thread is None and window.worker is None


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
    # Full linje vises grønn en kort stund og tømmes så.
    assert window.total_progress.property("done") is True
    qtbot.waitUntil(lambda: window.total_progress.value() == 0, timeout=5000)
    assert window.total_progress.property("done") is False
    assert window.total_progress.isVisible()


def test_audio_panel_has_no_video_options(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    window.import_files([media["wav"]])
    wait_idle(qtbot, window)
    panel = window.panel
    window.inspector.setCurrentWidget(window.panel_scroll)
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
    window.inspector.setCurrentWidget(window.panel_scroll)
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


def test_header_click_sorts_queue_and_keeps_selection(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    window.import_files([media["wav"], media["mp4"], media["mov"]])
    wait_idle(qtbot, window)
    window.table.selectRow(window.row_for(window.items[0].id))
    selected = window.selected_items()[0]
    header = window.table.horizontalHeader()
    header.sectionClicked.emit(2)
    sizes = [item.info.size for item in window.items]
    assert sizes == sorted(sizes)
    assert window.table.horizontalHeaderItem(2).text() == "Størrelse ↑"
    header.sectionClicked.emit(2)
    assert [item.info.size for item in window.items] == sorted(sizes, reverse=True)
    header.sectionClicked.emit(0)
    names = [item.path.name.casefold() for item in window.items]
    assert names == sorted(names)
    assert [window.table.item(row, 0).text() for row in range(3)] == [i.path.name for i in window.items]
    assert window.selected_items() == [selected]
    assert window.table.horizontalHeaderItem(2).text() == "Størrelse"


def test_file_details_dialog_lists_metadata_without_extra_click(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    window.import_files([media["mp4"]])
    wait_idle(qtbot, window)
    dialog = FileDetailsDialog(window.items, window)
    qtbot.addWidget(dialog)
    dialog.show()
    texts = [label.text() for label in dialog.findChildren(QLabel) if label.isVisible()]
    for heading in ("FIL", "FORMAT", "EKSPORT"):
        assert heading in texts
    assert any(text.startswith("VIDEO – STRØM") for text in texts)
    assert "Oppløsning" in texts and "Samplingsfrekvens" in texts
    dialog.copy_all()
    assert media["mp4"].name in QApplication.clipboard().text()
    assert not hasattr(window, "settings_toggle")
