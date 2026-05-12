import os
import shelve
from collections import deque
from threading import Condition, RLock

from utils import get_logger, get_urlhash, normalize
from scraper import is_valid


class Frontier(object):
    def __init__(self, config, restart):
        self.logger = get_logger("FRONTIER")
        self.config = config
        self._lock = RLock()
        self._work_ready = Condition(self._lock)
        self.to_be_downloaded = deque()
        self._in_flight = 0

        if not os.path.exists(self.config.save_file) and not restart:
            self.logger.info(
                f"Did not find save file {self.config.save_file}, "
                f"starting from seed.")
        elif os.path.exists(self.config.save_file) and restart:
            self.logger.info(
                f"Found save file {self.config.save_file}, deleting it.")
            os.remove(self.config.save_file)
        self.save = shelve.open(self.config.save_file)
        if restart:
            for url in self.config.seed_urls:
                self.add_url(url)
        else:
            self._parse_save_file()
            if not len(self.save):
                for url in self.config.seed_urls:
                    self.add_url(url)

    def _parse_save_file(self):
        """This function can be overridden for alternate saving techniques."""
        total_count = len(self.save)
        tbd_count = 0
        with self._lock:
            for url, completed in self.save.values():
                if not completed and is_valid(url):
                    self.to_be_downloaded.append(url)
                    tbd_count += 1
        self.logger.info(
            f"Found {tbd_count} urls to be downloaded from {total_count} "
            f"total urls discovered.")

    def get_tbd_url(self):
        """
        Block until a URL is available, or return None when the crawl is
        finished (no queued work and no other worker holds an in-flight URL).
        """
        with self._work_ready:
            while True:
                if self.to_be_downloaded:
                    self._in_flight += 1
                    return self.to_be_downloaded.popleft()
                if self._in_flight == 0:
                    return None
                self._work_ready.wait()

    def add_url(self, url):
        url = normalize(url)
        urlhash = get_urlhash(url)
        with self._work_ready:
            if urlhash not in self.save:
                self.save[urlhash] = (url, False)
                self.save.sync()
                self.to_be_downloaded.append(url)
                self._work_ready.notify()

    def mark_url_complete(self, url):
        urlhash = get_urlhash(url)
        with self._work_ready:
            if urlhash not in self.save:
                self.logger.error(
                    f"Completed url {url}, but have not seen it before.")
            self.save[urlhash] = (url, True)
            self.save.sync()
            self._in_flight -= 1
            self._work_ready.notify_all()
