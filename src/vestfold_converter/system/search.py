"""Read filename matches from the existing Windows Search index."""

import os
import re
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from ..core.models import Cancelled, MediaError

SEARCH_LIMIT = 200
MEDIA_FILTERS = (
    "*.mp4",
    "*.mov",
    "*.mkv",
    "*.avi",
    "*.webm",
    "*.mts",
    "*.m2ts",
    "*.ts",
    "*.mxf",
    "*.mpg",
    "*.mpeg",
    "*.m4v",
    "*.wmv",
    "*.3gp",
    "*.vob",
    "*.flv",
    "*.wav",
    "*.mp3",
    "*.flac",
    "*.m4a",
    "*.aac",
    "*.opus",
    "*.ogg",
    "*.aif",
    "*.aiff",
    "*.wma",
    "*.alac",
)
AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".m4a",
    ".aac",
    ".opus",
    ".ogg",
    ".aif",
    ".aiff",
    ".wma",
    ".alac",
}
SIZE_UNITS = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}
AGE_UNITS = {"days": 1, "weeks": 7, "months": 30, "years": 365}


@dataclass(frozen=True)
class SearchMatches:
    paths: tuple[Path, ...]
    limited: bool = False


@dataclass(frozen=True)
class SearchCriterion:
    """One extra condition, for example size greater than 100 MB."""

    field: str  # kind, extension, size, modified or name
    operator: str
    value: str
    unit: str = ""


def _text(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 200 or any(ord(char) < 32 for char in value):
        raise MediaError("Skriv et filnavn på mellom 1 og 200 tegn.")
    return value


def _like(value: str) -> str:
    # Search SQL literals and LIKE metacharacters are escaped independently.
    escapes = {"'": "''", "%": "[%]", "_": "[_]", "[": "[[]"}
    return "".join(escapes.get(char, char) for char in value)


def _extensions(extensions) -> str:
    return "(" + " OR ".join(f"System.FileExtension = '{extension}'" for extension in extensions) + ")"


def _number(value: str, maximum: float) -> float:
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        raise MediaError("Skriv et tall i søkekriteriet.") from None
    if not 0 < number <= maximum:
        raise MediaError("Tallet i søkekriteriet er utenfor gyldig område.")
    return number


def _utc(moment: datetime) -> str:
    # Windows Search compares dates in UTC.
    return moment.astimezone(UTC).strftime("'%Y-%m-%d %H:%M:%S'")


def criterion_sql(criterion: SearchCriterion, now: datetime | None = None) -> str:
    c = criterion
    if c.field == "kind" and c.operator in {"is", "is_not"} and c.value in {"video", "audio"}:
        media = [pattern[1:] for pattern in MEDIA_FILTERS]
        condition = _extensions(e for e in media if (e in AUDIO_EXTENSIONS) == (c.value == "audio"))
    elif c.field == "extension" and c.operator in {"is", "is_not"}:
        extension = c.value.strip().lower().lstrip(".")
        if not re.fullmatch(r"[a-z0-9]{1,15}", extension):
            raise MediaError("Skriv en filtype med bokstaver og tall, for eksempel jpg.")
        condition = f"System.FileExtension = '.{extension}'"
    elif c.field == "size" and c.operator in {"gt", "lt"} and c.unit in SIZE_UNITS:
        size = round(_number(c.value, 1_000_000) * SIZE_UNITS[c.unit])
        return f"System.Size {'>' if c.operator == 'gt' else '<'} {size}"
    elif c.field == "modified" and c.operator == "within" and c.unit in AGE_UNITS:
        days = _number(c.value, 10_000) * AGE_UNITS[c.unit]
        return f"System.DateModified >= {_utc((now or datetime.now(UTC)) - timedelta(days=days))}"
    elif c.field == "modified" and c.operator in {"before", "after"}:
        try:
            day = date.fromisoformat(c.value)
        except ValueError:
            raise MediaError("Velg en gyldig dato i søkekriteriet.") from None
        # Local midnight: "before" means before the day starts, "after" means after the day ends.
        start = datetime.combine(day + timedelta(days=c.operator == "after"), time()).astimezone()
        return f"System.DateModified {'<' if c.operator == 'before' else '>='} {_utc(start)}"
    elif c.field == "name" and c.operator in {"contains", "not_contains", "starts"}:
        literal = _like(_text(c.value))
        condition = (
            f"System.FileName LIKE '{literal}%'"
            if c.operator == "starts"
            else (f"System.FileName LIKE '%{literal}%'")
        )
    else:
        raise MediaError("Ukjent søkekriterium.")
    return f"NOT {condition}" if c.operator in {"is_not", "not_contains"} else condition


def scope_sql(folder: Path) -> str:
    if not folder.is_absolute():
        raise MediaError("Søkemappen må være en fullstendig sti.")
    # SCOPE covers the folder and every subfolder.
    url = "file:" + folder.as_posix().rstrip("/").replace("'", "''") + "/"
    return f"SCOPE='{url}'"


def search_sql(text: str, all_files=False, scope: Path | None = None, criteria=()) -> str:
    conditions = [f"System.FileName LIKE '%{_like(_text(text))}%'", "System.ItemUrl LIKE 'file:%'"]
    if scope is not None:
        conditions.append(scope_sql(scope))
    conditions += [criterion_sql(criterion) for criterion in criteria]
    # A chosen file type overrides the media filter, otherwise "file type is jpg" never matches.
    explicit_type = any(c.field == "extension" and c.operator == "is" for c in criteria)
    if not all_files and not explicit_type:
        conditions.append(_extensions(pattern[1:] for pattern in MEDIA_FILTERS))
    else:
        conditions.append("System.FileAttributes <> ALL BITWISE 16")
    # ItemUrl holds the real path; ItemPathDisplay is localised (C:\Brukere instead of C:\Users).
    return f"SELECT TOP {SEARCH_LIMIT + 1} System.ItemUrl FROM SystemIndex WHERE " + " AND ".join(conditions)


INDEX_TIMEOUT = 0x80041607


def index_error(exc) -> MediaError:
    """Explain a COM error from the search index, with a hint when the query timed out."""
    codes = [getattr(exc, "hresult", None)]
    info = getattr(exc, "excepinfo", None)
    if info and len(info) > 5:
        codes.append(info[5])
    if INDEX_TIMEOUT in {code & 0xFFFFFFFF for code in codes if isinstance(code, int)}:
        return MediaError("Søket tok for lang tid. Skriv mer av filnavnet eller legg til et kriterium.")
    return MediaError(f"Kunne ikke søke i Windows-indeksen: {exc}")


def _query_index(sql: str, limit: int, cancel: threading.Event) -> list[str]:
    """Run the query through the Windows Search OLE DB provider, in this process.

    No script or child process is used. The SQL is built by search_sql, where every user
    value is escaped as a literal.
    """
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    connection = records = None
    try:
        connection = win32com.client.Dispatch("ADODB.Connection")
        connection.ConnectionTimeout = 5
        connection.CommandTimeout = 15
        connection.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
        records = connection.Execute(sql)[0]
        urls = []
        while not records.EOF and len(urls) < limit:
            if cancel.is_set():
                raise Cancelled("Avbrutt")
            value = records.Fields.Item("System.ItemUrl").Value
            if isinstance(value, str):
                urls.append(value)
            records.MoveNext()
        return urls
    except (pythoncom.com_error, AttributeError, TypeError) as exc:
        raise index_error(exc) from exc
    finally:
        for handle in (records, connection):
            try:
                if handle is not None and handle.State == 1:
                    handle.Close()
            except pythoncom.com_error:
                pass
        records = connection = None
        pythoncom.CoUninitialize()


def windows_search(
    text: str, cancel: threading.Event, *, all_files=False, scope: Path | None = None, criteria=()
) -> SearchMatches:
    if os.name != "nt":
        raise MediaError("Søk med Windows Search krever Windows.")
    data = _query_index(search_sql(text, all_files, scope, criteria), SEARCH_LIMIT + 1, cancel)
    if not isinstance(data, list):
        raise MediaError("Kunne ikke lese søkeresultatene fra Windows.")
    paths, seen = [], set()
    for value in data:
        if not isinstance(value, str) or not value.startswith("file:"):
            continue
        value = str(Path(value.removeprefix("file:")))
        if not Path(value).is_absolute():
            continue
        key = os.path.normcase(value)
        if key not in seen:
            seen.add(key)
            paths.append(Path(value))
    return SearchMatches(tuple(paths[:SEARCH_LIMIT]), len(paths) > SEARCH_LIMIT)
