"""Read Explorer's filesystem shortcuts without changing Shell settings."""

import os
import threading
from pathlib import Path

from ..core.models import MediaError

QUICK_ACCESS = "shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}"


def _read_quick_access(cancel: threading.Event) -> list[dict]:
    """Ask Windows Shell directly over COM. No script, process or Shell setting is involved."""
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        folder = win32com.client.Dispatch("Shell.Application").NameSpace(QUICK_ACCESS)
        if folder is None:
            raise MediaError("Kunne ikke lese Hurtigtilgang fra Windows.")
        places = []
        for item in folder.Items():
            if cancel.is_set():
                break
            if item.IsFolder and not str(item.Path).startswith("::"):
                places.append({"name": item.Name, "path": item.Path})
        return places
    except (pythoncom.com_error, AttributeError, TypeError) as exc:
        # Uventede svar fra Shell gir samme melding som en utilgjengelig Hurtigtilgang.
        raise MediaError("Kunne ikke lese Hurtigtilgang fra Windows.") from exc
    finally:
        pythoncom.CoUninitialize()


def explorer_places(cancel: threading.Event) -> list[tuple[str, str]]:
    if os.name != "nt":
        return []
    # Names and paths returned by the Shell are data, never commands.
    data = _read_quick_access(cancel)
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
