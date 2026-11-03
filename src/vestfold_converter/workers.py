import os
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from .engine import MediaEngine
from .models import Cancelled, MediaError, QueueItem
from .profiles import default_settings
from .storage import long_path


def import_paths(paths: list[Path], cancel: threading.Event):
    for path in paths:
        path = long_path(path)
        if cancel.is_set():
            return
        if path.is_symlink():
            continue
        if path.is_dir():
            for folder, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not (Path(folder) / d).is_symlink())
                for name in sorted(files):
                    if cancel.is_set():
                        return
                    file = Path(folder) / name
                    if not file.is_symlink():
                        yield file.resolve()
        else:
            yield path.resolve()


class JobWorker(QObject):
    found = Signal(object)
    analyzed = Signal(str, object)
    failed = Signal(str, str)
    progress = Signal(str, float)
    converted = Signal(str, object)
    starting = Signal(str)
    done = Signal(object)

    def __init__(
        self,
        engine: MediaEngine,
        mode: str,
        cancel: threading.Event,
        *,
        paths=None,
        known=None,
        items=None,
        folder=None,
    ):
        super().__init__()
        self.engine, self.mode, self.cancel = engine, mode, cancel
        self.paths, self.known = paths or [], set(known or [])
        self.items, self.folder = items or [], folder

    @Slot()
    def run(self):
        summary = {"mode": self.mode, "ok": 0, "failed": 0, "cancelled": False, "fatal": ""}
        try:
            if self.mode == "initialize":
                self.engine.discover(self.cancel)
            elif self.mode == "analyze":
                for path in import_paths(self.paths, self.cancel):
                    key = os.path.normcase(str(path))
                    if key in self.known:
                        continue
                    self.known.add(key)
                    item = QueueItem(path=path)
                    self.found.emit(item)
                    try:
                        info = self.engine.analyze(path, self.cancel)
                        self.analyzed.emit(item.id, info)
                        summary["ok"] += 1
                    except Cancelled:
                        self.failed.emit(item.id, "Avbrutt under analyse. Fjern filen og importer på nytt.")
                        raise
                    except (MediaError, OSError) as exc:
                        self.failed.emit(item.id, str(exc))
                        summary["failed"] += 1
            elif self.mode == "convert":
                for item in self.items:
                    if self.cancel.is_set():
                        raise Cancelled("Avbrutt")
                    self.starting.emit(item.id)
                    try:
                        output = self.engine.convert(
                            item.info,
                            item.settings,
                            self.folder,
                            self.cancel,
                            lambda value, id_=item.id: self.progress.emit(id_, value),
                        )
                        self.converted.emit(item.id, output)
                        summary["ok"] += 1
                    except Cancelled:
                        self.failed.emit(item.id, "Avbrutt")
                        raise
                    except (MediaError, OSError) as exc:
                        self.failed.emit(item.id, str(exc))
                        summary["failed"] += 1
        except Cancelled:
            summary["cancelled"] = True
        except Exception as exc:  # noqa: BLE001 - trådgrense: rapporter også uventede feil til GUI.
            summary["fatal"] = str(exc)
        finally:
            summary["cancelled"] |= self.cancel.is_set()
            self.done.emit(summary)


def analyzed_item(item: QueueItem, info):
    item.info = info
    item.settings = default_settings(info)
    item.status = "Klar"
