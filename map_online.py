"""Optional desktop-only imagery/weather. No request until explicitly enabled.

EOX WMTS: https://maps.eox.at/ (2025 layer CC BY-NC-SA 4.0).
Open-Meteo: https://open-meteo.com/en/docs (free non-commercial API).
Only map coordinates are sent; no flight/pilot/profile data.
"""
from collections import OrderedDict
from datetime import datetime, timezone
import json
import math
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from map_services import (LEVELS, HOSTS, checked_url, SafeRedirect, download, tile_url, wind_url, parse_wind, wind_components, bearing, tailwind)

class Task(QRunnable):
    def __init__(self, service, kind, key, operation):
        super().__init__()
        self.service, self.kind, self.key, self.operation = service, kind, key, operation

    def run(self):
        try:
            value, error = self.operation(), ''
        except Exception as exc:
            value, error = None, str(exc)
        try:
            self.service.completed.emit(self.kind, self.key, value, error)
        except RuntimeError:
            # The optional owning map may have been destroyed during the request.
            return


class OnlineLayers(QObject):
    completed = Signal(str, object, object, str)
    tile_ready = Signal(object, object)
    wind_ready = Signal(object, object, str)
    status = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Owned by the application, so closing a window does not wait for HTTP.
        self.pool = QThreadPool.globalInstance()
        self.pending = set()
        self.failed_until = {}
        self.wind_cache = OrderedDict()
        self.completed.connect(self.finish)

    def request_tile(self, key):
        task_key = ('tile', key)
        if task_key in self.pending or self.failed_until.get(task_key, 0) > time.monotonic() or len(self.pending) >= 24:
            return
        self.pending.add(task_key)
        self.pool.start(Task(self, 'tile', key, lambda: download(tile_url(*key))))

    def request_wind(self, points, level, refresh=False):
        key = (level, tuple(points))
        cached = self.wind_cache.get(key)
        if not refresh and cached and time.monotonic()-cached[0] < 900:
            self.wind_ready.emit(key, cached[1], '')
            return key
        if ('wind', key) not in self.pending:
            self.pending.add(('wind', key))
            self.pool.start(Task(self, 'wind', key, lambda: parse_wind(download(wind_url(points, level)), level)))
        return key

    def finish(self, kind, key, value, error):
        self.pending.discard((kind, key))
        if error:
            self.failed_until[(kind, key)] = time.monotonic()+30
        if kind == 'tile':
            if value:
                self.tile_ready.emit(key, value)
            else:
                self.status.emit('Satellite unavailable; offline map retained')
        else:
            if value:
                self.wind_cache[key] = (time.monotonic(), value)
                while len(self.wind_cache) > 8:
                    self.wind_cache.popitem(last=False)
            self.wind_ready.emit(key, value, error)
