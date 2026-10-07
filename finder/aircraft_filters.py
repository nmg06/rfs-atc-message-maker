"""Shared local aircraft catalogue and explicit OR-filter normalization."""
import re
from .database import connect_readonly


def normalize_types(value):
    if isinstance(value, str):
        value = [v for v in re.split(r'[,;\s]+', value) if v]
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError('AIRCRAFT_TYPES_FORMAT')
    result = []
    for item in value:
        if not isinstance(item, str) or not re.fullmatch(r'[A-Za-z0-9]{2,6}', item.strip()):
            raise ValueError('AIRCRAFT_TYPES_FORMAT')
        code = item.strip().upper()
        if code not in result:
            result.append(code)
    return result


def catalogue(path):
    with connect_readonly(path) as db:
        return [dict(row) for row in db.execute(
            'SELECT icao AS code, COALESCE(NULLIF(model, ?), icao) AS name, manufacturer FROM aircraft_types ORDER BY manufacturer, model, icao', ('',))]
