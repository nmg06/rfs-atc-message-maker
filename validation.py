"""Validation non destructive des champs aéronautiques et limite Discord."""
from __future__ import annotations
from i18n import tr, set_language, language
from dataclasses import dataclass
import re
from emoji_tokens import emoji_count
from rfs_schema import FLIGHT_FIELDS, FLIGHT_FIELDS_BY_TYPE, MESSAGE_FIELDS

@dataclass(frozen=True)
class Issue:
    field: str
    text: str
REQUIRED_FLIGHT: dict[str, tuple[str, ...]] = {'ATC REQUEST': ('airline', 'aircraft', 'callsign', 'departure_icao', 'arrival_icao', 'departure_gate', 'departure_runway', 'cruise_fl'), 'AIRBORNE': ('airline', 'aircraft', 'callsign', 'departure_icao', 'arrival_icao', 'cruise_fl'), 'ARRIVAL BOARD': ('airline', 'aircraft', 'callsign', 'departure_icao', 'arrival_icao', 'arrival_runway'), 'FLIGHT COMPLETED': ('airline', 'aircraft', 'callsign', 'departure_icao', 'arrival_icao', 'arrival_city', 'arrival_runway', 'arrival_gate'), 'FLIGHT PLAN': ('departure_icao', 'arrival_icao', 'distance', 'departure_runway', 'arrival_runway', 'aircraft', 'airline', 'estimated_flight_time', 'passengers', 'cargo', 'fuel'), 'DISPATCH FORM': ('aircraft', 'livery', 'departure_icao', 'arrival_icao', 'estimated_flight_time')}
REQUIRED_MESSAGE: dict[str, tuple[str, ...]] = {'ATC REQUEST': ('pushback',), 'AIRBORNE': ('climb_target',), 'ARRIVAL BOARD': ('status',), 'FLIGHT COMPLETED': ('actual_flight_time',), 'ATC ACTIVE': ('airport_icao', 'city', 'positions'), 'ATC OFFLINE': ('airport_icao', 'city', 'positions'), 'DISPATCH FORM': ('server',)}

def _has(value: object) -> bool:
    return bool(str(value or '').strip())

def validate(message_type: str, flight: dict, data: dict, pilot_name: str) -> list[Issue]:
    issues: list[Issue] = []
    visible_flight = set(FLIGHT_FIELDS_BY_TYPE.get(message_type, ()))
    if message_type in ('ATC REQUEST', 'AIRBORNE', 'ARRIVAL BOARD', 'DISPATCH FORM') and (not _has(pilot_name)):
        issues.append(Issue('pilot_name', tr('Le pseudo RFS est requis.')))
    for key in REQUIRED_FLIGHT.get(message_type, ()):
        if not _has(flight.get(key)):
            issues.append(Issue(key, tr('{v0} est requis.', v0=tr(FLIGHT_FIELDS[key].label))))
    for key in REQUIRED_MESSAGE.get(message_type, ()):
        if message_type == 'ARRIVAL BOARD' and key == 'status' and data.get('go_around'):
            continue
        if not _has(data.get(key)):
            issues.append(Issue(key, tr('{v0} est requis.', v0=tr(MESSAGE_FIELDS[message_type][key].label))))
    if message_type == 'DISPATCH FORM':
        if not (_has(flight.get('callsign')) or _has(flight.get('flight_number'))):
            issues.append(Issue('callsign', tr('Callsign ou Flight number est requis.')))
    if message_type in ('AIRBORNE', 'FLIGHT COMPLETED'):
        if not data.get('no_atc') and (not _has(data.get('controller'))):
            issues.append(Issue('controller', tr('Renseignez le contrôleur ou cochez « Aucun ATC disponible ».')))
    if message_type == 'AIRBORNE':
        if not (_has(data.get('runway_used')) or _has(flight.get('departure_runway'))):
            issues.append(Issue('runway_used', tr('Runway used est requis.')))
        if data.get('climb_target') == 'Waypoint' and (not _has(data.get('climb_waypoint'))):
            issues.append(Issue('climb_waypoint', tr('Saisissez le waypoint de montée.')))
    for key in ('departure_icao', 'arrival_icao'):
        if key not in visible_flight:
            continue
        value = str(flight.get(key, '') or '').strip()
        if value and (not re.fullmatch('[A-Za-z]{4}', value)):
            issues.append(Issue(key, tr('{v0} doit contenir exactement 4 lettres.', v0=tr(FLIGHT_FIELDS[key].label))))
    airport = str(data.get('airport_icao', '') or '').strip()
    if airport and (not re.fullmatch('[A-Za-z]{4}', airport)):
        issues.append(Issue('airport_icao', tr('Airport ICAO doit contenir exactement 4 lettres.')))
    fl = str(flight.get('cruise_fl', '') or '').strip()
    if fl and 'cruise_fl' in visible_flight:
        match = re.fullmatch('(?:FL)?(\\d{2,3})', fl, flags=re.I)
        if not match or not 1 <= int(match.group(1)) <= 600:
            issues.append(Issue('cruise_fl', tr('Cruise FL doit être entre FL010 et FL600.')))
    for key in ('departure_runway', 'arrival_runway', 'runway_used'):
        if key not in visible_flight and key not in MESSAGE_FIELDS.get(message_type, {}):
            continue
        value = str((flight if key in flight else data).get(key, '') or '').strip()
        if value and (not re.fullmatch('(?:(?:RWY|RUNWAY)\\s*)?(?:0[1-9]|[12][0-9]|3[0-6])[LRC]?', value, flags=re.I)):
            issues.append(Issue(key, tr('{v0} doit ressembler à 16R ou 26L.', v0=tr(FLIGHT_FIELDS[key].label) if key in FLIGHT_FIELDS else tr(MESSAGE_FIELDS[message_type][key].label))))
    for key in ('distance', 'distance_remaining'):
        if key not in visible_flight and key not in MESSAGE_FIELDS.get(message_type, {}):
            continue
        value = str((flight if key in flight else data).get(key, '') or '').strip()
        if value and (not re.fullmatch('\\d+(?:[.,]\\d+)?(?:\\s*(?:NM|NMI))?', value, flags=re.I)):
            issues.append(Issue(key, tr('{v0} doit être numérique (NM).', v0=tr(FLIGHT_FIELDS[key].label) if key in FLIGHT_FIELDS else tr(MESSAGE_FIELDS[message_type][key].label))))
    pushback = str(data.get('pushback', '') or '').strip()
    if pushback and 'pushback' in MESSAGE_FIELDS.get(message_type, {}) and (not re.fullmatch('\\d{1,3}', pushback)):
        issues.append(Issue('pushback', tr('Pushback doit être un nombre de minutes.')))
    for key in ('departures', 'inbounds', 'passengers', 'cargo', 'fuel'):
        if key not in visible_flight and key not in MESSAGE_FIELDS.get(message_type, {}):
            continue
        if message_type == 'FLIGHT COMPLETED' and key in ('passengers', 'cargo', 'fuel') and (not data.get('detailed')):
            continue
        if message_type == 'ARRIVAL BOARD' and key == 'fuel' and (not data.get('show_fuel')):
            continue
        source = flight if key in flight else data
        value = str(source.get(key, '') or '').strip()
        if value and (not re.fullmatch('\\d+(?:\\+)?', value)):
            issues.append(Issue(key, tr('{v0} doit être un nombre saisi par vous.', v0=tr(FLIGHT_FIELDS[key].label) if key in FLIGHT_FIELDS else tr(MESSAGE_FIELDS[message_type][key].label))))
    return issues
