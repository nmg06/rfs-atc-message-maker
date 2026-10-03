"""Reuse only a known exact variant or a unique RFS match for an observed type."""
from copy import deepcopy
from .calculator import find_aircraft, load_json
from finder.rfs_catalogue import TYPE_BY_ID, observation_name


def resolve_aircraft(flight, catalogue=None):
    catalogue = catalogue if catalogue is not None else load_json('aircraft_fuel_data.json')['aircraft']
    selected = flight.get('selected_flight') or {}
    provenance = selected.get('fields', {}).get('aircraft', '')
    observed = bool(selected) and provenance not in ('USER_INPUT', 'USER_INPUT_FUEL_VARIANT')
    if not observed:
        exact = find_aircraft(flight.get('fuel_aircraft_id') or flight.get('aircraft',''), catalogue)
        if exact:
            return {'record': deepcopy(exact), 'candidates': [exact['id']], 'source': 'USER_EXACT_VARIANT'}
    code = selected.get('aircraft_icao') or ''
    text = str(flight.get('aircraft') or '').strip().casefold()
    codes = {code} if code else {value for value in TYPE_BY_ID.values() if value and
        (value.casefold() == text or observation_name(value).casefold() == text)}
    matches = [row for row in catalogue if TYPE_BY_ID.get(row['id']) in codes]
    return {'record': deepcopy(matches[0]) if observed and len(matches)==1 else None,
        'candidates': [row['id'] for row in matches],
        'source': 'OBSERVED_TYPE_UNIQUE_RFS_VARIANT' if observed and len(matches)==1 else 'AMBIGUOUS_TYPE' if matches else 'UNKNOWN_TYPE'}
