import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from vestfold_converter.core.models import MediaError
from vestfold_converter.system.search import (
    SEARCH_LIMIT,
    SearchCriterion,
    criterion_sql,
    index_error,
    search_sql,
    windows_search,
)


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
def test_search_sends_escaped_sql_and_bounds_results(monkeypatch):
    term = "video'; $(Get-Process) # æøå"
    paths = [f"file:C:/Medier/opptak{i}.mp4" for i in range(SEARCH_LIMIT + 1)]
    criteria = (SearchCriterion("size", "gt", "1", "MB"),)

    def query(sql, limit, cancel):
        assert sql == search_sql(term, False, Path("C:/Medier"), criteria)
        assert "video''; $(Get-Process) # æøå" in sql
        assert limit == SEARCH_LIMIT + 1
        return paths

    monkeypatch.setattr("vestfold_converter.system.search._query_index", query)
    matches = windows_search(term, threading.Event(), scope=Path("C:/Medier"), criteria=criteria)
    assert len(matches.paths) == SEARCH_LIMIT
    assert matches.limited
    assert matches.paths[0] == Path("C:/Medier/opptak0.mp4")


@pytest.mark.skipif(os.name != "nt", reason="Windows Search")
def test_search_deduplicates_and_ignores_non_file_paths(monkeypatch):
    # ItemUrl gives the real path; the localised display path (C:\Brukere) does not exist on disk.
    data = ["file:C:/Users/ÆØÅ.mp4", "file:c:/users/æøå.mp4", r"C:\Brukere\x.mp4", "file:relative", None, ""]
    monkeypatch.setattr("vestfold_converter.system.search._query_index", lambda *a: data)
    matches = windows_search("æøå", threading.Event())
    assert matches.paths == (Path("C:/Users/ÆØÅ.mp4"),)
    assert not matches.limited


@pytest.mark.skipif(os.name != "nt", reason="Windows Search")
def test_invalid_index_reply_is_reported(monkeypatch):
    monkeypatch.setattr("vestfold_converter.system.search._query_index", lambda *a: None)
    with pytest.raises(MediaError, match="søkeresultatene"):
        windows_search("video", threading.Event())


def test_index_timeout_gets_a_helpful_message():
    # pywin32 reports the provider's HRESULT either directly or inside excepinfo.
    timeout = 0x80041607 - 2**32
    direct = SimpleNamespace(hresult=timeout, excepinfo=None)
    wrapped = SimpleNamespace(hresult=-2147352567, excepinfo=(0, "Provider", "Timeout", None, 0, timeout))
    for error in (direct, wrapped):
        assert "for lang tid" in str(index_error(error))
    assert "for lang tid" not in str(index_error(SimpleNamespace(hresult=-1, excepinfo=None)))


@pytest.mark.skipif(os.name != "nt", reason="Windows Search")
def test_search_runs_without_starting_a_process(monkeypatch):
    def no_process(*args, **kwargs):
        raise AssertionError("Windows-søk skal ikke starte en ny prosess")

    monkeypatch.setattr("subprocess.Popen", no_process)
    try:
        windows_search("vmc-finnes-ikke-7f3a", threading.Event())
    except MediaError:
        pass  # Indeksen kan være slått av på testmaskinen; poenget er at ingen prosess startes.


def test_folder_scope_includes_subfolders_and_escapes_quotes():
    sql = search_sql("video", scope=Path("C:/Users/Ola O'Neil/Dokumenter"))
    assert "SCOPE='file:C:/Users/Ola O''Neil/Dokumenter/'" in sql
    assert "SCOPE='file:C:/'" in search_sql("video", scope=Path("C:/"))
    assert "SCOPE" not in search_sql("video")
    with pytest.raises(MediaError):
        search_sql("video", scope=Path("relativ"))


def test_criteria_become_index_conditions():
    now = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    assert criterion_sql(SearchCriterion("size", "gt", "100", "MB")) == f"System.Size > {100 * 1024**2}"
    assert (
        criterion_sql(SearchCriterion("size", "lt", "1,5", "GB")) == f"System.Size < {round(1.5 * 1024**3)}"
    )
    assert criterion_sql(SearchCriterion("extension", "is", ".JPG")) == "System.FileExtension = '.jpg'"
    assert criterion_sql(SearchCriterion("extension", "is_not", "wav")) == "NOT System.FileExtension = '.wav'"
    assert criterion_sql(SearchCriterion("modified", "within", "2", "weeks"), now) == (
        "System.DateModified >= '2026-10-22 12:00:00'"
    )
    assert (
        criterion_sql(SearchCriterion("name", "starts", "Intervju_")) == "System.FileName LIKE 'Intervju[_]%'"
    )
    assert (
        criterion_sql(SearchCriterion("name", "not_contains", "kopi")) == "NOT System.FileName LIKE '%kopi%'"
    )
    audio = criterion_sql(SearchCriterion("kind", "is", "audio"))
    assert "'.wav'" in audio and "'.mp4'" not in audio
    assert criterion_sql(SearchCriterion("modified", "before", "2025-01-01")).startswith(
        "System.DateModified < '"
    )
    assert criterion_sql(SearchCriterion("modified", "after", "2025-01-01")).startswith(
        "System.DateModified >= '"
    )


@pytest.mark.parametrize(
    "criterion",
    [
        SearchCriterion("extension", "is", "jp g'; DROP"),
        SearchCriterion("size", "gt", "-1", "MB"),
        SearchCriterion("size", "gt", "mange", "MB"),
        SearchCriterion("size", "gt", "10", "TB"),
        SearchCriterion("modified", "before", "i går"),
        SearchCriterion("kind", "is", "bilde"),
        SearchCriterion("owner", "is", "meg"),
    ],
)
def test_invalid_criteria_are_rejected(criterion):
    with pytest.raises(MediaError):
        criterion_sql(criterion)


def test_chosen_file_type_replaces_media_filter():
    media = search_sql("poster")
    assert "'.mp4'" in media and "BITWISE 16" not in media
    jpg = search_sql("poster", criteria=(SearchCriterion("extension", "is", "jpg"),))
    assert "System.FileExtension = '.jpg'" in jpg and "'.mp4'" not in jpg
    assert "BITWISE 16" in jpg
