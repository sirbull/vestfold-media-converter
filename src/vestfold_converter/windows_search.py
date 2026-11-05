"""Read filename matches from the existing Windows Search index."""

import base64
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .models import MediaError
from .process import capture

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


@dataclass(frozen=True)
class SearchMatches:
    paths: tuple[Path, ...]
    limited: bool = False


def search_sql(text: str, all_files=False) -> str:
    text = text.strip()
    if not text or len(text) > 200 or any(ord(char) < 32 for char in text):
        raise MediaError("Skriv et filnavn på mellom 1 og 200 tegn.")
    # Search SQL literals and LIKE metacharacters are escaped independently.
    escapes = {"'": "''", "%": "[%]", "_": "[_]", "[": "[[]"}
    literal = "".join(escapes.get(char, char) for char in text)
    conditions = [f"System.FileName LIKE '%{literal}%'", "System.ItemUrl LIKE 'file:%'"]
    if not all_files:
        extensions = " OR ".join(f"System.FileExtension = '{pattern[1:]}'" for pattern in MEDIA_FILTERS)
        conditions.append(f"({extensions})")
    else:
        conditions.append("System.FileAttributes <> ALL BITWISE 16")
    return f"SELECT TOP {SEARCH_LIMIT + 1} System.ItemPathDisplay FROM SystemIndex WHERE " + " AND ".join(
        conditions
    )


def windows_search(text: str, cancel: threading.Event, *, all_files=False) -> SearchMatches:
    if os.name != "nt":
        raise MediaError("Søk med Windows Search krever Windows.")
    # The script is fixed. User input is SQL-escaped, then transported as base64
    # data, so PowerShell never interprets filenames or search terms as commands.
    encoded = base64.b64encode(search_sql(text, all_files).encode("utf-8")).decode("ascii")
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
        $value = $records.Fields.Item('System.ItemPathDisplay').Value
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
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    try:
        raw = capture(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script], cancel, timeout=22
        )
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise MediaError("Kunne ikke lese søkeresultatene fra Windows.") from exc
    if not isinstance(data, list):
        raise MediaError("Kunne ikke lese søkeresultatene fra Windows.")
    paths, seen = [], set()
    for value in data:
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            continue
        key = os.path.normcase(value)
        if key not in seen:
            seen.add(key)
            paths.append(Path(value))
    return SearchMatches(tuple(paths[:SEARCH_LIMIT]), len(paths) > SEARCH_LIMIT)
