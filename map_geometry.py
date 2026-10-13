"""Shared offline map geometry and read-only airport coordinates, without Qt."""
from functools import lru_cache
from pathlib import Path
import math
import sqlite3


def mercator_y(latitude):
    latitude = max(-85.05112878, min(85.05112878, latitude))
    return -math.degrees(math.log(math.tan(math.pi/4 + math.radians(latitude)/2)))


def inverse_mercator(y):
    return math.degrees(2*math.atan(math.exp(math.radians(-max(-180, min(180, y)))))-math.pi/2)


@lru_cache(maxsize=512)
def airport_coordinates(database, code):
    """Return trusted coordinates from the selected local database, read-only."""
    if not database or not code:
        return None
    try:
        path = Path(database).resolve()
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.2)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            row = connection.execute(
                "SELECT latitude,longitude FROM airports WHERE icao=?", (code.upper().strip(),)
            ).fetchone()
        finally:
            connection.close()
        if row and all(value is not None and math.isfinite(float(value)) for value in row):
            lat, lon = map(float, row)
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    except (OSError, sqlite3.Error, TypeError, ValueError):
        pass
    return None


def great_circle(origin, destination, steps=96):
    """Lat/lon samples on the shortest sphere arc; continuous longitude at dateline."""
    def vector(point):
        lat, lon = map(math.radians, point)
        return math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)
    a, b = vector(origin), vector(destination)
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b))))
    angle = math.acos(dot)
    if angle < 1e-9:
        return [origin, destination]
    # An antipodal pair has infinitely many equal arcs: choose a stable orthogonal plane.
    normal = tuple(b[i] - dot * a[i] for i in range(3))
    length = math.sqrt(sum(x * x for x in normal))
    if length < 1e-9:
        axis = (0, 0, 1) if abs(a[2]) < 0.9 else (0, 1, 0)
        projection = sum(x * y for x, y in zip(axis, a))
        normal = tuple(axis[i] - projection * a[i] for i in range(3))
        length = math.sqrt(sum(x * x for x in normal))
    normal = tuple(x / length for x in normal)
    result = []
    previous = origin[1]
    for index in range(steps + 1):
        part = angle * index / steps
        point = tuple(a[i] * math.cos(part) + normal[i] * math.sin(part) for i in range(3))
        lat = math.degrees(math.atan2(point[2], math.hypot(point[0], point[1])))
        lon = math.degrees(math.atan2(point[1], point[0]))
        while lon - previous > 180:
            lon -= 360
        while lon - previous < -180:
            lon += 360
        result.append((lat, lon))
        previous = lon
    return result
