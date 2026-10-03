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

LEVELS = ((850, '≈ 1.5 km'), (700, '≈ 3 km'), (500, '≈ 5.6 km'), (400, '≈ 7.2 km'),
          (300, '≈ 9.2 km'), (250, '≈ 10.4 km'), (200, '≈ 11.8 km'), (150, '≈ 13.5 km'))
HOSTS = {'tiles.maps.eox.at', 'maps.eox.at', 'api.open-meteo.com'}


def checked_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username or parsed.password:
        raise ValueError('Unsupported map service URL')
    return url


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, checked_url(newurl))


def download(url, maximum=2_000_000):
    request = Request(checked_url(url), headers={'User-Agent': 'RFS-Flightdeck/1.0 (optional map)'})
    with build_opener(SafeRedirect()).open(request, timeout=8) as response:  # nosec B310: HTTPS host allowlist including redirects
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Map service response too large')
    return data


def tile_url(z, x, y):
    if not 0 <= z <= 15 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise ValueError('Invalid tile')
    return f'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/{z}/{y}/{x}.jpg'


def wind_url(points, level):
    if level not in dict(LEVELS) or not 1 <= len(points) <= 32:
        raise ValueError('Invalid pressure level or grid')
    if any(not all(math.isfinite(v) for v in pair) or not -85 <= pair[0] <= 85 or
           not -180 <= pair[1] <= 180 for pair in points):
        raise ValueError('Invalid weather coordinates')
    variables = [f'{key}_{level}hPa' for key in ('wind_speed', 'wind_direction', 'geopotential_height')]
    return 'https://api.open-meteo.com/v1/forecast?' + urlencode({
        'latitude': ','.join(f'{p[0]:.4f}' for p in points),
        'longitude': ','.join(f'{p[1]:.4f}' for p in points), 'hourly': ','.join(variables),
        'wind_speed_unit': 'kn', 'forecast_hours': 1, 'timezone': 'UTC'})


def parse_wind(raw, level):
    documents = json.loads(raw)
    if not isinstance(documents, list):
        documents = [documents]
    samples = []
    for doc in documents[:32]:
        hourly, units = doc.get('hourly', {}), doc.get('hourly_units', {})
        speed_key, direction_key, height_key = [f'{key}_{level}hPa' for key in
                                                ('wind_speed', 'wind_direction', 'geopotential_height')]
        if units.get(speed_key) != 'kn' or doc.get('utc_offset_seconds') != 0:
            raise ValueError('Unexpected wind units/timezone')
        try:
            speed, direction, height = (float(hourly[key][0]) for key in (speed_key, direction_key, height_key))
            lat, lon = float(doc['latitude']), float(doc['longitude'])
            stamp = datetime.fromisoformat(hourly['time'][0]).replace(tzinfo=timezone.utc)
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if (all(math.isfinite(v) for v in (speed, direction, height, lat, lon)) and
                0 <= speed <= 500 and 0 <= direction <= 360 and -90 <= lat <= 90 and -180 <= lon <= 180):
            samples.append(dict(latitude=lat, longitude=lon, speed=speed, direction=direction,
                                height_m=height, time=stamp.isoformat()))
    if not samples:
        raise ValueError('No wind data available for this pressure level')
    return dict(level=level, samples=samples, retrieved_at=datetime.now(timezone.utc).isoformat())


def wind_components(speed, direction):
    """Meteorological FROM degrees -> east/north knots in the direction of flow."""
    angle = math.radians(direction)
    return -speed * math.sin(angle), -speed * math.cos(angle)


def bearing(origin, destination):
    lat1, lon1, lat2, lon2 = map(math.radians, (*origin, *destination))
    delta = lon2 - lon1
    return math.degrees(math.atan2(math.sin(delta)*math.cos(lat2),
        math.cos(lat1)*math.sin(lat2)-math.sin(lat1)*math.cos(lat2)*math.cos(delta))) % 360


def tailwind(speed, direction, track):
    east, north = wind_components(speed, direction)
    return east*math.sin(math.radians(track)) + north*math.cos(math.radians(track))


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
