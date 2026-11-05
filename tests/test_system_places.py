import os
import threading

import pytest

from vestfold_converter.core.models import MediaError
from vestfold_converter.system.places import explorer_places


@pytest.mark.skipif(os.name != "nt", reason="Windows Shell shortcuts")
def test_shell_places_keep_names_unicode_and_deduplicate(monkeypatch):
    data = [
        {"name": "Opptak æøå", "path": "C:\\Opptak æøå"},
        {"name": "Duplikat", "path": "c:\\opptak æøå"},
        {"name": "Nettverk", "path": "\\\\server\\media"},
        {"name": "Ugyldig", "path": "relative"},
        None,
        {"path": 42},
    ]
    monkeypatch.setattr("vestfold_converter.system.places._read_quick_access", lambda cancel: data)
    assert explorer_places(threading.Event()) == [
        ("Opptak æøå", "C:\\Opptak æøå"),
        ("Nettverk", "\\\\server\\media"),
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows Shell shortcuts")
def test_invalid_shell_response_is_reported(monkeypatch):
    monkeypatch.setattr("vestfold_converter.system.places._read_quick_access", lambda cancel: None)
    with pytest.raises(MediaError, match="Hurtigtilgang"):
        explorer_places(threading.Event())


@pytest.mark.skipif(os.name != "nt", reason="Windows Shell shortcuts")
def test_quick_access_is_read_without_starting_a_process(monkeypatch):
    def no_process(*args, **kwargs):
        raise AssertionError("Hurtigtilgang skal ikke starte en ny prosess")

    monkeypatch.setattr("subprocess.Popen", no_process)
    places = explorer_places(threading.Event())
    assert all(isinstance(name, str) and isinstance(path, str) for name, path in places)
