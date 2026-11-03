import threading

from vestfold_converter.storage import (
    default_output,
    load_preferences,
    preferred_output,
    publish_file,
    safe_stem,
    save_preferences,
)
from vestfold_converter.workers import import_paths


def test_preferences_and_fallback(tmp_path):
    path = tmp_path / "settings.json"
    save_preferences({"output": str(tmp_path), "theme": "dark"}, path)
    assert preferred_output(load_preferences(path)) == tmp_path
    assert preferred_output({"output": str(tmp_path / "missing")}) == default_output()
    path.write_text("broken")
    assert load_preferences(path) == {}


def test_output_never_overwrites_source_or_existing(tmp_path):
    source = tmp_path / "lyd.mp3"
    source.write_bytes(b"original")
    existing = tmp_path / "lyd (1).mp3"
    existing.write_bytes(b"existing")
    temporary = tmp_path / ".part.mp3"
    temporary.write_bytes(b"converted")
    result = publish_file(temporary, tmp_path, "lyd", "mp3", source)
    assert result.name == "lyd (2).mp3"
    assert source.read_bytes() == b"original"
    assert existing.read_bytes() == b"existing"
    assert result.read_bytes() == b"converted"


def test_folder_import_and_cancellation(tmp_path):
    child = tmp_path / "undermappe"
    child.mkdir()
    (child / "lyd.wav").write_bytes(b"a")
    (tmp_path / "video.MTS").write_bytes(b"b")
    cancel = threading.Event()
    assert len(list(import_paths([tmp_path], cancel))) == 2
    cancel.set()
    assert list(import_paths([tmp_path], cancel)) == []


def test_long_names(tmp_path):
    assert len(safe_stem(tmp_path / ("æ" * 200 + ".mp4"))) == 120
    assert safe_stem(tmp_path / "CON.wav") == "_CON"
