import time
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock


class PerHostPoliteness(object):
    """
    Cross-thread politeness: at most one in-flight / scheduled download per host
    at a time, and the next fetch to that host may begin only after `delay_sec`
    from when the previous fetch *finished* (matches prior single-thread Worker).

    Each hostname has its own lock so different hosts can be fetched in parallel.
    """

    def __init__(self, delay_sec: float):
        # Extra credit: at least 500 ms between requests to the same domain.
        self.delay_sec = max(float(delay_sec), 0.5)
        self._meta_lock = Lock()
        self._host_locks = {}
        self._last_done = defaultdict(float)

    def _lock_for_host(self, hostname: str) -> Lock:
        with self._meta_lock:
            if hostname not in self._host_locks:
                self._host_locks[hostname] = Lock()
            return self._host_locks[hostname]

    @contextmanager
    def polite_scope(self, hostname: str):
        h = (hostname or "").lower()
        if not h:
            yield
            return
        lock = self._lock_for_host(h)
        with lock:
            wait = self._last_done[h] + self.delay_sec - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                yield
            finally:
                self._last_done[h] = time.time()
