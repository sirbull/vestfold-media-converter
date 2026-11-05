import base64
import json
import os
import re
import threading
from pathlib import Path

import pytest

from vestfold_converter.models import MediaError
from vestfold_converter.windows_search import SEARCH_LIMIT, search_sql, windows_search


def test_filename_search_escapes_sql_and_literal_wildcards():
    sql = search_sql("O'Brien_[3]% – æøå")
    assert "System.FileName LIKE '%O''Brien[_][[]3][%] – æøå%'" in sql
    assert "System.FileExtension = '.mts'" in sql
    assert "System.ItemUrl LIKE 'file:%'" in sql


@pytest.mark.parametrize("text", ["", "  ", "x" * 201, "test\nname"])
def test_invalid_search_input_does_not_run_a_query(text):
    with pytest.raises(MediaError):
        search_sql(text)


@pytest.mark.skipif(os.name != "nt", reason="Windows Search")
def test_search_transports_terms_as_data_and_bounds_results(monkeypatch):
    term = "video'; $(Get-Process) # æøå"
    paths = [f"C:\\Medier\\opptak{i}.mp4" for i in range(SEARCH_LIMIT + 1)]

    def capture(args, cancel, timeout):
        script = args[-1]
        assert term not in script
        encoded = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", script).group(1)
        assert base64.b64decode(encoded).decode("utf-8") == search_sql(term)
        return json.dumps(paths)

    monkeypatch.setattr("vestfold_converter.windows_search.capture", capture)
    matches = windows_search(term, threading.Event())
    assert len(matches.paths) == SEARCH_LIMIT
    assert matches.limited
    assert matches.paths[0] == Path(paths[0])


@pytest.mark.skipif(os.name != "nt", reason="Windows Search")
def test_search_deduplicates_and_ignores_non_file_paths(monkeypatch):
    data = ["C:\\Medier\\ÆØÅ.mp4", "c:\\medier\\æøå.mp4", "relative", None, ""]
    monkeypatch.setattr("vestfold_converter.windows_search.capture", lambda *a, **kw: json.dumps(data))
    matches = windows_search("æøå", threading.Event())
    assert matches.paths == (Path(data[0]),)
    assert not matches.limited


@pytest.mark.skipif(os.name != "nt", reason="Windows Search")
def test_invalid_index_reply_is_reported(monkeypatch):
    monkeypatch.setattr("vestfold_converter.windows_search.capture", lambda *a, **kw: "not JSON")
    with pytest.raises(MediaError, match="søkeresultatene"):
        windows_search("video", threading.Event())
