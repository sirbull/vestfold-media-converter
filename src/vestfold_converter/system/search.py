"""Read filename matches from the existing Windows Search index."""

import base64
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from ..core.models import MediaError
from ..core.process import capture, powershell

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


def windows_search(
    text: str, cancel: threading.Event, *, all_files=False, scope: Path | None = None, criteria=()
) -> SearchMatches:
    if os.name != "nt":
        raise MediaError("Søk med Windows Search krever Windows.")
    # The script is fixed. User input is SQL-escaped, then transported as base64
    # data, so PowerShell never interprets filenames or search terms as commands.
    sql = search_sql(text, all_files, scope, criteria)
    encoded = base64.b64encode(sql.encode("utf-8")).decode("ascii")
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$query = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__QUERY__'))
$connection = New-Object -ComObject ADODB.Connection
$records = $null
$paths = New-Object System.Collections.Generic.List[string]
try {
    $connection.ConnectionTimeout = 5
    $connection.CommandTimeout = 15
    $connection.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
    $records = $connection.Execute($query)
    while (-not $records.EOF -and $paths.Count -lt __LIMIT__) {
        $value = $records.Fields.Item('System.ItemUrl').Value
        if ($value -is [string]) { $paths.Add($value) }
        if ($paths.Count -ge __LIMIT__) { break }
        $records.MoveNext()
    }
} finally {
    if ($null -ne $records -and $records.State -eq 1) { $records.Close() }
    if ($connection.State -eq 1) { $connection.Close() }
}
ConvertTo-Json -InputObject @($paths.ToArray()) -Compress
""".replace("__QUERY__", encoded).replace("__LIMIT__", str(SEARCH_LIMIT + 1))
    try:
        data = json.loads(capture(powershell(script), cancel, timeout=22))
    except MediaError as exc:
        if "0x80041607" in str(exc):
            raise MediaError(
                "Søket tok for lang tid. Skriv mer av filnavnet eller legg til et kriterium."
            ) from exc
        raise
    except (ValueError, TypeError) as exc:
        raise MediaError("Kunne ikke lese søkeresultatene fra Windows.") from exc
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
