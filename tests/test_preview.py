import subprocess
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt

from vestfold_converter.core.models import QueueItem
from vestfold_converter.core.playback import (
    AUDIO_FRAME_BYTES,
    AUDIO_RATE,
    AudioPlayer,
    audio_preview_command,
)
from vestfold_converter.core.process import CREATE_FLAGS
from vestfold_converter.ui.main_window import MainWindow
from vestfold_converter.ui.preview import PreviewPanel


def wait_image(qtbot, panel):
    qtbot.waitUntil(lambda: not panel.canvas.image.isNull(), timeout=20000)


@pytest.mark.parametrize("kind", ["mts", "mp4", "silent", "interlace"])
def test_frame_uses_bundled_ffmpeg(qtbot, engine, media, kind):
    panel = PreviewPanel(engine.ffmpeg)
    qtbot.addWidget(panel)
    panel.show()
    panel.show_item(QueueItem(media[kind], info=engine.analyze(media[kind])))
    try:
        wait_image(qtbot, panel)
        assert panel.canvas.image.width() <= 640
        assert panel.canvas.image.height() <= 360
        assert panel.play.isEnabled()
        assert "uten lyd" in panel.details.text()
        if kind == "mts":
            with qtbot.waitSignal(panel.frame_ready, timeout=15000):
                panel.seek.setValue(5000)
            assert panel.position > 0.3
    finally:
        panel.shutdown()
    qtbot.waitUntil(lambda: not panel.decoder.thread.is_alive(), timeout=8000)


def test_play_pause_and_seek_to_another_scene(qtbot, engine, tmp_path):
    source = tmp_path / "to scener.mp4"
    subprocess.run(
        [
            str(engine.ffmpeg),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=128x72:r=12:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=128x72:r=12:d=2",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            str(source),
        ],
        check=True,
        capture_output=True,
        creationflags=CREATE_FLAGS,
        timeout=30,
    )
    panel = PreviewPanel(engine.ffmpeg)
    qtbot.addWidget(panel)
    panel.show()
    panel.show_item(QueueItem(source, info=engine.analyze(source)))
    try:
        wait_image(qtbot, panel)
        assert panel.canvas.image.pixelColor(20, 20).red() > 200
        start = panel.position
        qtbot.mouseClick(panel.play, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: panel.position > start + 0.15, timeout=10000)
        qtbot.mouseClick(panel.play, Qt.MouseButton.LeftButton)
        assert not panel.playing
        panel.seek.setValue(8000)
        qtbot.waitUntil(
            lambda: not panel.canvas.image.isNull() and panel.canvas.image.pixelColor(20, 20).blue() > 200,
            timeout=15000,
        )
        assert panel.position > 3
    finally:
        panel.shutdown()


def test_switching_to_audio_clears_video_and_cancels_decoder(qtbot, engine, media):
    panel = PreviewPanel(engine.ffmpeg)
    qtbot.addWidget(panel)
    panel.show()
    try:
        panel.show_item(QueueItem(media["mp4"], info=engine.analyze(media["mp4"])))
        wait_image(qtbot, panel)
        panel.toggle_play()
        panel.show_item(QueueItem(media["wav"], info=engine.analyze(media["wav"])))
        assert panel.canvas.image.isNull()
        assert not panel.canvas.isVisible()
        assert not panel.playing
        qtbot.wait(300)
        assert panel.canvas.image.isNull()
        # Lydfiler har bare tidslinje og avspillingsknapper.
        for control in (panel.play, panel.seek, panel.skip_back, panel.skip_forward):
            assert control.isVisible() and control.isEnabled()
        panel.show_item(QueueItem(media["mp4"], info=engine.analyze(media["mp4"])))
        assert panel.canvas.isVisible()
    finally:
        panel.shutdown()


class SilentOutput:
    """Erstatter lydkortet: tar imot PCM og later som hver buffer spilles med en gang."""

    def __init__(self, received):
        self.received = received
        self.played = 0

    def write(self, data):
        self.received.append(len(data))
        self.played += len(data)

    def pending(self):
        return 0

    def played_seconds(self):
        return self.played / (AUDIO_RATE * AUDIO_FRAME_BYTES)

    def close(self):
        pass


def test_audio_preview_plays_pauses_seeks_and_finishes(qtbot, engine, media):
    received = []
    panel = PreviewPanel(engine.ffmpeg)
    panel.audio = AudioPlayer(engine.ffmpeg, output=lambda: SilentOutput(received))
    qtbot.addWidget(panel)
    panel.show()
    info = engine.analyze(media["wav"])
    panel.show_item(QueueItem(media["wav"], info=info))
    try:
        assert audio_preview_command(engine.ffmpeg, info, 0.25)[-6:] == [
            "48000", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
        ]  # fmt: skip
        qtbot.mouseClick(panel.play, Qt.MouseButton.LeftButton)
        assert panel.playing
        qtbot.waitUntil(lambda: not panel.playing, timeout=10000)
        assert panel.position == pytest.approx(info.duration, abs=0.05)
        assert sum(received) / (AUDIO_RATE * AUDIO_FRAME_BYTES) == pytest.approx(info.duration, abs=0.05)
        assert panel.time.text().startswith("00:00:00 / ")
        # Ny avspilling fra slutten starter på nytt; søk midt i fortsetter derfra.
        received.clear()
        panel.seek.setValue(5000)
        qtbot.waitUntil(lambda: panel.position == pytest.approx(info.duration / 2, abs=0.05), timeout=2000)
        panel.toggle_play()
        qtbot.waitUntil(lambda: not panel.playing, timeout=10000)
        assert sum(received) / (AUDIO_RATE * AUDIO_FRAME_BYTES) == pytest.approx(info.duration / 2, abs=0.05)
    finally:
        panel.shutdown()


def test_five_second_buttons_seek_scenes_clamp_and_keep_playing(qtbot, engine, tmp_path):
    source = tmp_path / "tolv sekunder.mp4"
    subprocess.run(
        [
            str(engine.ffmpeg),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=128x72:r=12:d=6",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=128x72:r=12:d=6",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            str(source),
        ],
        check=True,
        capture_output=True,
        creationflags=CREATE_FLAGS,
        timeout=30,
    )
    panel = PreviewPanel(engine.ffmpeg)
    qtbot.addWidget(panel)
    panel.show()
    panel.show_item(QueueItem(source, info=engine.analyze(source)))
    try:
        wait_image(qtbot, panel)
        assert panel.play.text() == ""
        assert not panel.play.icon().isNull()
        assert panel.play.accessibleName() == "Spill av forhåndsvisning"
        assert panel.position == pytest.approx(1)
        assert panel.canvas.image.pixelColor(20, 20).red() > 200
        with qtbot.waitSignal(panel.frame_ready, timeout=15000):
            qtbot.mouseClick(panel.skip_forward, Qt.MouseButton.LeftButton)
        assert panel.position == pytest.approx(6)
        assert panel.canvas.image.pixelColor(20, 20).blue() > 200
        with qtbot.waitSignal(panel.frame_ready, timeout=15000):
            qtbot.mouseClick(panel.skip_back, Qt.MouseButton.LeftButton)
        assert panel.position == pytest.approx(1)
        assert panel.canvas.image.pixelColor(20, 20).red() > 200
        with qtbot.waitSignal(panel.frame_ready, timeout=15000):
            qtbot.mouseClick(panel.skip_back, Qt.MouseButton.LeftButton)
        assert panel.position == 0
        # Repeated clicks must never request a frame beyond the source's end.
        for _ in range(3):
            qtbot.mouseClick(panel.skip_forward, Qt.MouseButton.LeftButton)
        assert panel.position == pytest.approx(11.9)
        assert not panel.playing
        qtbot.mouseClick(panel.skip_back, Qt.MouseButton.LeftButton)
        qtbot.mouseClick(panel.play, Qt.MouseButton.LeftButton)
        assert panel.playing
        assert panel.play.accessibleName() == "Sett forhåndsvisning på pause"
        previous = panel.position
        qtbot.mouseClick(panel.skip_back, Qt.MouseButton.LeftButton)
        assert panel.position == pytest.approx(previous - 5)
        assert panel.playing
        with qtbot.waitSignal(panel.frame_ready, timeout=15000):
            pass
        qtbot.mouseClick(panel.play, Qt.MouseButton.LeftButton)
        assert not panel.playing
        assert panel.play.accessibleName() == "Spill av forhåndsvisning"
    finally:
        panel.shutdown()
    qtbot.waitUntil(lambda: not panel.decoder.thread.is_alive(), timeout=8000)


def test_unreadable_source_reports_preview_error(qtbot, engine, media, tmp_path):
    info = replace(engine.analyze(media["mp4"]), path=tmp_path / "borte.mp4")
    panel = PreviewPanel(engine.ffmpeg)
    qtbot.addWidget(panel)
    panel.show_item(QueueItem(info.path, info=info))
    try:
        qtbot.waitUntil(lambda: "Kunne ikke" in panel.canvas.message, timeout=10000)
    finally:
        panel.shutdown()


def test_folder_queue_selection_drives_side_preview(qtbot, engine, media, tmp_path):
    folder = tmp_path / "import"
    folder.mkdir()
    for name, kind in (("a.mp4", "mp4"), ("b.mp4", "silent"), ("c.wav", "wav")):
        (folder / name).write_bytes(media[kind].read_bytes())
    window = MainWindow(engine, initialize=False, preferences_path=tmp_path / "settings.json")
    qtbot.addWidget(window)
    window.show()
    window.import_files([folder])
    qtbot.waitUntil(lambda: not window.busy, timeout=30000)
    assert len(window.items) == 3
    assert window.inspector.isVisible()
    # Eksportvalg er første fane og vises når filer blir valgt.
    assert window.inspector.tabText(0) == "Eksportvalg"
    assert window.inspector.currentWidget() is window.panel_scroll
    window.inspector.setCurrentWidget(window.preview_scroll)
    wait_image(qtbot, window.preview)
    window.table.selectRow(1)
    assert window.preview.filename.text() == "b.mp4"
    wait_image(qtbot, window.preview)
    window.resize(900, 600)
    qtbot.waitUntil(lambda: window.table.isColumnHidden(1), timeout=1000)
    assert window.inspector.isVisible()
    window.table.selectRow(2)
    assert window.preview.play.isEnabled()
    assert window.preview.canvas.isHidden()
    # Brukerens fanevalg beholdes mens man bytter mellom valgte filer.
    assert window.inspector.currentWidget() is window.preview_scroll
