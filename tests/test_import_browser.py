import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QItemSelectionModel, QPoint, QRect, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog

from vestfold_converter.appearance import DARK, stylesheet
from vestfold_converter.import_browser import ImportBrowser, SelectionProbe
from vestfold_converter.models import Cancelled, MediaError
from vestfold_converter.ui import MainWindow
from vestfold_converter.windows_search import SearchMatches

SELECT = QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows


@pytest.fixture
def browser(qtbot, engine, media, tmp_path):
    folder = tmp_path / "medier æøå"
    folder.mkdir()
    for filename, kind in (("a.mp4", "mp4"), ("b.MTS", "mts"), ("c.wav", "wav")):
        (folder / filename).write_bytes(media[kind].read_bytes())
    (folder / "undermappe").mkdir()
    (folder / "tekst.txt").write_text("Ikke et medium")
    dialog = ImportBrowser(
        engine, directory=folder, places_loader=lambda cancel: [("Min snarvei", str(folder))]
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.model.rowCount(dialog.list_view.rootIndex()) == 4)
    yield dialog
    dialog.reject()
    qtbot.waitUntil(lambda: not dialog.probe.thread.is_alive(), timeout=8000)
    qtbot.waitUntil(lambda: not dialog.searcher.thread.is_alive(), timeout=8000)
    qtbot.waitUntil(lambda: not dialog.preview.decoder.thread.is_alive(), timeout=8000)
    qtbot.waitUntil(lambda: not dialog.places_thread.is_alive(), timeout=8000)


def select(browser, filename):
    index = browser.model.index(str(Path(browser.current_directory) / filename))
    assert index.isValid()
    browser.selection.setCurrentIndex(index, SELECT)
    return index


def test_selected_video_can_play_before_import_and_audio_clears_it(qtbot, browser):
    select(browser, "b.MTS")
    qtbot.waitUntil(lambda: not browser.preview.canvas.image.isNull(), timeout=20000)
    assert browser.files == []  # Highlighting previews without importing.
    assert browser.preview.filename.text() == "b.MTS"
    assert browser.import_button.isEnabled()
    start = browser.preview.position
    qtbot.mouseClick(browser.preview.play, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: browser.preview.position > start, timeout=10000)
    select(browser, "c.wav")
    qtbot.waitUntil(lambda: browser.preview.info is not None and not browser.preview.info.video)
    assert browser.preview.canvas.image.isNull()
    assert not browser.preview.playing
    assert not browser.preview.play.isEnabled()


def test_grid_toggle_preserves_multiple_selected_files_and_imports(qtbot, browser):
    select(browser, "a.mp4")
    second = browser.model.index(str(Path(browser.current_directory) / "c.wav"))
    browser.selection.select(
        second, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    )
    before = set(browser.selected_paths())
    qtbot.mouseClick(browser.view_buttons["grid"], Qt.MouseButton.LeftButton)
    assert browser.stack.currentWidget() is browser.grid_view
    assert set(browser.selected_paths()) == before
    qtbot.mouseClick(browser.import_button, Qt.MouseButton.LeftButton)
    assert browser.result() == QDialog.DialogCode.Accepted
    assert set(browser.files) == before
    assert len(browser.files) == 2


def test_navigation_shortcuts_filter_and_preview_splitter(qtbot, browser):
    start = browser.current_directory
    qtbot.waitUntil(
        lambda: any(browser.places.item(i).text() == "Min snarvei" for i in range(browser.places.count()))
    )
    assert browser.navigate(str(Path(start) / "undermappe"))
    browser.go_back()
    assert browser.current_directory == start
    browser.go_forward()
    assert browser.current_directory.endswith("undermappe")
    browser.go_up()
    assert browser.current_directory == start
    browser.places.itemClicked.emit(
        next(
            browser.places.item(i)
            for i in range(browser.places.count())
            if browser.places.item(i).text() == "Min snarvei"
        )
    )
    assert browser.current_directory == start
    qtbot.mouseClick(browser.all_files, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: browser.model.rowCount(browser.list_view.rootIndex()) == 5)
    before = browser.preview.width()
    browser.splitter.setSizes([120, 240, 700])
    qtbot.waitUntil(lambda: browser.preview.width() > before)
    browser.navigate(str(Path(start) / "missing"))
    assert browser.current_directory == start
    assert "utilgjengelig" in browser.location.text()


def test_reject_during_pending_analysis_leaves_no_files(browser):
    select(browser, "a.mp4")
    browser.reject()
    assert browser.files == []
    assert browser._closed
    assert not browser.preview.timer.isActive()


@pytest.mark.parametrize("width,height", [(760, 440), (1080, 640)])
def test_browser_controls_fit_small_window(qtbot, browser, width, height):
    browser.setStyleSheet(stylesheet(DARK))
    browser.resize(width, height)
    qtbot.wait(20)
    assert browser.width() == width
    assert browser.height() == height
    for widget in (
        browser.address_bar,
        browser.native,
        browser.import_button,
        browser.cancel,
        browser.view_buttons["grid"],
        browser.search_input,
        browser.search_button,
        browser.preview.play,
    ):
        rect = QRect(widget.mapTo(browser, QPoint(0, 0)), widget.size())
        assert widget.isVisible()
        assert browser.rect().contains(rect)


def test_native_picker_passes_paths_and_cleans_up(qtbot, browser, monkeypatch):
    path = str(Path(browser.current_directory) / "a.mp4")
    monkeypatch.setattr(
        "vestfold_converter.import_browser.QFileDialog.getOpenFileNames", lambda *args: ([path], "")
    )
    qtbot.mouseClick(browser.native, Qt.MouseButton.LeftButton)
    assert browser.files == [Path(path)]
    assert browser.result() == QDialog.DialogCode.Accepted


def test_cancel_native_picker_restores_selected_preview(qtbot, browser, monkeypatch):
    select(browser, "a.mp4")
    monkeypatch.setattr(
        "vestfold_converter.import_browser.QFileDialog.getOpenFileNames", lambda *args: ([], "")
    )
    qtbot.mouseClick(browser.native, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not browser.preview.canvas.image.isNull(), timeout=20000)
    assert browser.preview.filename.text() == "a.mp4"
    assert browser.files == []
    assert browser.isVisible()


def test_path_bar_shows_file_and_clicking_parent_navigates(qtbot, browser):
    directory = Path(browser.current_directory)
    select(browser, "a.mp4")
    assert browser.path_bar.toolTip() == str(directory / "a.mp4")
    parent = next(
        button
        for button in browser.path_bar.buttons
        if Path(button.property("folderPath")) == directory.parent
    )
    if parent.isVisible():
        qtbot.mouseClick(parent, Qt.MouseButton.LeftButton)
    else:
        qtbot.mouseClick(browser.path_bar.overflow, Qt.MouseButton.LeftButton)
        menu = browser.path_bar.popup_menu
        action = next(
            action for action in menu.actions() if action.data() and Path(action.data()) == directory.parent
        )
        qtbot.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center())
    assert Path(browser.current_directory) == directory.parent
    browser.go_back()
    assert Path(browser.current_directory) == directory


def test_address_breadcrumbs_navigate_and_ctrl_l_allows_pasted_path(qtbot, browser):
    original = Path(browser.current_directory)
    assert browser.back.text() == browser.forward.text() == browser.up.text() == ""
    assert not browser.address.isVisible()
    qtbot.keyClick(browser, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(browser.address.isVisible)
    assert browser.address.selectedText()
    browser.address.setText(str(original / "undermappe"))
    qtbot.keyClick(browser.address, Qt.Key.Key_Return)
    assert Path(browser.current_directory) == original / "undermappe"
    assert not browser.address.isVisible()
    parent = next(
        button for button in browser.address_bar.buttons if Path(button.property("folderPath")) == original
    )
    qtbot.mouseClick(parent, Qt.MouseButton.LeftButton)
    assert Path(browser.current_directory) == original
    qtbot.keyClick(browser, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(browser.address.isVisible)
    browser.address.setText("Dette skal ikke brukes")
    qtbot.keyClick(browser.address, Qt.Key.Key_Escape)
    assert browser.isVisible()
    assert not browser.address.isVisible()
    assert Path(browser.current_directory) == original


def test_search_results_preview_toggle_import_and_show_parent(qtbot, browser, monkeypatch):
    directory = Path(browser.current_directory)
    found = directory / "b.MTS"
    calls = []

    def search(request, cancel):
        calls.append(request)
        return SearchMatches((found, directory / "c.wav"))

    monkeypatch.setattr(browser.searcher, "function", search)
    browser.search_input.setText("opptak")
    qtbot.keyClick(browser.search_input, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: browser.search_model.rowCount() == 2)
    assert calls == [("opptak", False)]
    assert browser.is_search
    index = browser.search_model.index(0, 0)
    # Sorting can put either row first, so locate the requested result by path.
    for row in range(browser.search_model.rowCount()):
        index = browser.search_model.index(row, 0)
        if Path(index.data(Qt.ItemDataRole.UserRole)) == found:
            break
    browser.selection.setCurrentIndex(index, SELECT)
    qtbot.waitUntil(lambda: not browser.preview.canvas.image.isNull(), timeout=20000)
    assert browser.selected_paths() == [found]
    assert browser.path_bar.toolTip() == str(found)
    qtbot.mouseClick(browser.view_buttons["grid"], Qt.MouseButton.LeftButton)
    assert browser.selected_paths() == [found]
    assert browser.grid_view.model() is browser.search_model
    qtbot.mouseClick(browser.reveal_folder, Qt.MouseButton.LeftButton)
    assert not browser.is_search
    assert browser.search_input.text() == ""
    assert Path(browser.current_directory) == directory
    assert browser.selected_paths() == [found]
    qtbot.mouseClick(browser.import_button, Qt.MouseButton.LeftButton)
    assert browser.files == [found]


@pytest.mark.parametrize("failure", [False, True])
def test_empty_or_unavailable_index_keeps_folder_navigation(qtbot, browser, monkeypatch, failure):
    directory = browser.current_directory

    def search(request, cancel):
        if failure:
            raise MediaError("Search is unavailable")
        return SearchMatches(())

    monkeypatch.setattr(browser.searcher, "function", search)
    browser.search_input.setText("missing")
    qtbot.mouseClick(browser.search_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: (
            "utilgjengelig" in browser.location.text()
            if failure
            else "Ingen treff" in browser.location.text()
        )
    )
    assert not browser.import_button.isEnabled()
    browser.search_input.clear()
    assert not browser.is_search
    assert browser.current_directory == directory
    assert browser.list_view.model() is browser.model
    assert browser.native.isEnabled()


def test_leaving_search_cancels_it_and_discards_old_results(qtbot, browser, monkeypatch):
    started, cancelled = threading.Event(), threading.Event()

    def search(request, cancel):
        started.set()
        assert cancel.wait(5)
        cancelled.set()
        raise Cancelled("Avbrutt")

    monkeypatch.setattr(browser.searcher, "function", search)
    browser.search_input.setText("old")
    browser.start_search()
    qtbot.waitUntil(started.is_set)
    browser.navigate(browser.current_directory)
    qtbot.waitUntil(cancelled.is_set)
    assert not browser.is_search
    assert browser.search_model.rowCount() == 0
    assert browser.list_view.model() is browser.model


def test_shell_failure_does_not_disable_browser(qtbot, engine, tmp_path):
    def unavailable(cancel):
        raise MediaError("Shell is unavailable")

    dialog = ImportBrowser(engine, directory=tmp_path, places_loader=unavailable)
    qtbot.addWidget(dialog)
    dialog.show()
    try:
        qtbot.waitUntil(lambda: "kunne ikke leses" in dialog.places_status.text())
        assert dialog.native.isEnabled()
        assert dialog.current_directory == tmp_path.as_posix()
    finally:
        dialog.reject()


def test_new_selection_cancels_old_analysis(qtbot):
    started, cancelled = threading.Event(), threading.Event()

    def analyze(path, cancel):
        if path == Path("old.mp4"):
            started.set()
            assert cancel.wait(5)
            cancelled.set()
            raise Cancelled("Avbrutt")
        return "new information"

    worker = SelectionProbe(SimpleNamespace(analyze=analyze))
    try:
        worker.request(Path("old.mp4"))
        qtbot.waitUntil(started.is_set)
        generation = worker.request(Path("new.mp4"))
        qtbot.waitUntil(cancelled.is_set)
        qtbot.waitUntil(lambda: not worker.results.empty())
        assert worker.results.get_nowait() == (generation, Path("new.mp4"), "new information", "")
        assert worker.results.empty()
    finally:
        worker.stop()
        qtbot.waitUntil(lambda: not worker.thread.is_alive())


def test_main_import_button_uses_browser_and_remembers_view(qtbot, engine, media, tmp_path):
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()

    def choose_in_browser():
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, ImportBrowser):
            QTimer.singleShot(20, choose_in_browser)
            return
        dialog.set_view("grid")
        dialog.files = [media["mp4"]]
        dialog.accept()

    QTimer.singleShot(20, choose_in_browser)
    qtbot.mouseClick(window.add_files, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.busy, timeout=20000)
    assert len(window.items) == 1
    assert window.items[0].path == media["mp4"]
    assert window.preferences["import_view"] == "grid"
    assert len(window.preferences["import_splitter"]) == 3
