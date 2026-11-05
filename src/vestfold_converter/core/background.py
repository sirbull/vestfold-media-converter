"""A cancellable, latest-request-wins worker with no Qt object access."""

import queue
import threading

from .models import Cancelled, MediaError


class LatestRequest:
    def __init__(self, function, name):
        self.function = function
        self.results = queue.SimpleQueue()
        self._condition = threading.Condition()
        self._pending = None
        self._cancel = threading.Event()
        self._stopped = False
        self._generation = 0
        self.thread = threading.Thread(target=self._run, name=name, daemon=True)
        self.thread.start()

    def request(self, key=None):
        with self._condition:
            self._generation += 1
            self._cancel.set()
            self._pending = (self._generation, key) if key is not None else None
            self._condition.notify()
            return self._generation

    def stop(self):
        with self._condition:
            self._stopped = True
            self._pending = None
            self._cancel.set()
            self._condition.notify()

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._stopped or self._pending is not None)
                if self._stopped:
                    return
                generation, key = self._pending
                self._pending = None
                cancel = self._cancel = threading.Event()
            try:
                data = self.function(key, cancel)
                result = (generation, key, data, "")
            except Cancelled:
                continue
            except (MediaError, OSError) as exc:
                result = (generation, key, None, str(exc))
            if not cancel.is_set():
                self.results.put(result)
