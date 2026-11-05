import json
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
    monkeypatch.setattr("vestfold_converter.system.places.capture", lambda *a, **k: json.dumps(data))
    assert explorer_places(threading.Event()) == [
        ("Opptak æøå", "C:\\Opptak æøå"),
        ("Nettverk", "\\\\server\\media"),
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows Shell shortcuts")
def test_invalid_shell_response_is_reported(monkeypatch):
    monkeypatch.setattr("vestfold_converter.system.places.capture", lambda *a, **k: "not JSON")
    with pytest.raises(MediaError, match="Hurtigtilgang"):
        explorer_places(threading.Event())
