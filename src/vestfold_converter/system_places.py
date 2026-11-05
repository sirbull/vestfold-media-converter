"""Read Explorer's filesystem shortcuts without changing Shell settings."""

import json
import os
import threading
from pathlib import Path

from .models import MediaError
from .process import capture


def explorer_places(cancel: threading.Event) -> list[tuple[str, str]]:
    if os.name != "nt":
        return []
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    # Fixed script: paths and names returned by the Shell are data, never commands.
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$shell = New-Object -ComObject Shell.Application
$folder = $shell.NameSpace('shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}')
if ($null -eq $folder) { throw 'Quick access is unavailable' }
$places = @($folder.Items() | Where-Object { $_.IsFolder -and $_.Path -notlike '::*' } |
    ForEach-Object { [PSCustomObject]@{name=$_.Name; path=$_.Path} })
ConvertTo-Json -InputObject $places -Compress
"""
    try:
        data = json.loads(
            capture([str(powershell), "-NoProfile", "-NonInteractive", "-Command", script], cancel, timeout=8)
        )
    except (ValueError, TypeError) as exc:
        raise MediaError("Kunne ikke lese Hurtigtilgang fra Windows.") from exc
    if not isinstance(data, list):
        raise MediaError("Kunne ikke lese Hurtigtilgang fra Windows.")
    result, seen = [], set()
    for place in data:
        if not isinstance(place, dict):
            continue
        name, path = place.get("name"), place.get("path")
        if not isinstance(name, str) or not isinstance(path, str) or not path:
            continue
        key = os.path.normcase(path)
        if key not in seen and Path(path).is_absolute():
            seen.add(key)
            result.append((name, path))
    return result
