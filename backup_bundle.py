"""Validated portable backups, shared by desktop and Android without UI imports."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import uuid
from country_data import COUNTRIES
from visual_themes import THEMES
from flight_planning import validate_log
from rfs_schema import Field, MESSAGE_TYPES, FLIGHT_TYPES, FLIGHT_FIELDS, MESSAGE_FIELDS, empty_flight, empty_per_type
from message_builder import DEFAULT_PRESENTATION, BUILTIN_DESIGNS, EMOJI_STYLES, PILOT_FIELDS, custom_context, apply_custom

EXTENSIONS = {
    'PUSHBACK': {'pushback': Field('Pushback (minutes)', required=True),
                 'direction': Field('Direction', choices=('Left', 'Right', 'Straight'), kind='choice'),
                 'server': Field('Serveur'), 'note': Field('Note', kind='multiline')},
    'TAXI': {'taxi_route': Field('Taxi route', required=True),
             'hold_short': Field('Hold short'), 'server': Field('Serveur'), 'note': Field('Note', kind='multiline')},
    'ATIS': {'airport_icao': Field('ICAO aéroport', required=True),
             'information': Field('Information letter', required=True),
             'wind': Field('Wind'), 'visibility': Field('Visibility'), 'weather': Field('Weather'),
             'cloud': Field('Cloud'), 'temperature': Field('Temperature / dew point'),
             'qnh': Field('QNH'), 'runway': Field('Runway'), 'remarks': Field('Remarks', kind='multiline')},
}
ALL_TYPES = (*MESSAGE_TYPES, *EXTENSIONS)
ANDROID_FLIGHT_TYPES = (*FLIGHT_TYPES, 'PUSHBACK', 'TAXI')
STATE_LIMIT = 2 * 1024 * 1024
MAX_BYTES = STATE_LIMIT


def defaults():
    per_type = empty_per_type()
    per_type.update({kind: {key: False if field.kind == 'bool' else '' for key, field in spec.items()}
                     for kind, spec in EXTENSIONS.items()})
    return {'pilot_name': 'n1chita', 'pilot_library': [], 'server': '', 'theme': 'Sombre',
        'message_type': 'ATC REQUEST', 'current_flight_id': '', 'flight': empty_flight(),
        'per_type': per_type, 'saved_flights': [], 'preview_edits': {},
        'presentation': deepcopy(DEFAULT_PRESENTATION), 'compact_history': True,
        'intro_seen': False, 'joke_seen': False, 'tutorial_seen': False, 'strict_validation': True, 'language': 'en', 'finder_filters': {},
        'fuel_inputs': {}, 'map_settings': {}, 'visual_theme': 'avionique', 'active_session': {}, 'flight_log': [],
        'design_draft': {}, 'report_draft': {}, 'finder_shortlist': [],
        'recent': {k: [] for k in ('airline', 'aircraft', 'airports', 'controllers', 'servers')}}


def check_json(value, depth=0):
    if depth > 24:
        raise ValueError('Backup nesting exceeds limit')
    if isinstance(value, str) and len(value) > 20000:
        raise ValueError('Text exceeds limit')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Invalid number')
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 20000:
                raise ValueError('Invalid key')
            check_json(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 1000:
            raise ValueError('Collection exceeds limit')
        for item in value:
            check_json(item, depth + 1)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError('Invalid JSON value')


def normalise_state(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid state')
    check_json(value)
    state = defaults()
    for key, item in value.items():
        if key in state and type(item) is not type(state[key]):
            raise ValueError('Invalid state field: ' + key)
        state[key] = deepcopy(item)
    if state['message_type'] not in ALL_TYPES or state['language'] not in ('fr', 'en'):
        raise ValueError('Unknown message type or language')
    state['flight'] = {**empty_flight(), **state['flight']}
    if state['visual_theme'] not in {r[0] for r in THEMES}:
        raise ValueError('Unknown visual theme')
    validate_log(state['active_session'], state['flight_log'])
    # Comparisons are saved observations, never trusted flight plans or SQL.
    if len(state['finder_shortlist']) > 3:
        raise ValueError('Too many comparison flights')
    for item in state['finder_shortlist']:
        if not isinstance(item, dict):
            raise ValueError('Invalid comparison flight')
        for key in ('key', 'origin', 'destination', 'callsign', 'airline', 'airline_name',
                    'aircraft_display', 'record_kind'):
            if item.get(key) is not None and not isinstance(item[key], str):
                raise ValueError('Invalid comparison text')
        for key in ('duration_min', 'distance_nm', 'n_obs'):
            if item.get(key) is not None and (type(item[key]) not in (int, float)
                                            or not 0 <= item[key] <= 1000000000):
                raise ValueError('Invalid comparison number')
    view = state['map_settings']
    for key in ('satellite', 'winds'):
        if key in view and type(view[key]) is not bool:
            raise ValueError('Invalid online map option')
    if 'center' in view and (not isinstance(view['center'], list) or len(view['center']) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in view['center'])
            or not -180 <= view['center'][1] <= 180 or not -540 <= view['center'][0] <= 540):
        raise ValueError('Invalid map center')
    if 'zoom' in view and (type(view['zoom']) not in (int, float) or not 1 <= view['zoom'] <= 32768):
        raise ValueError('Invalid map zoom')
    for key in ('origin_country', 'destination_country'):
        if view.get(key) and view[key] not in {c for c, _ in COUNTRIES}:
            raise ValueError('Invalid map country')
    for key in FLIGHT_FIELDS:
        if not isinstance(state['flight'][key], str):
            raise ValueError('Invalid flight field: ' + key)
    for people in (state['flight'].get('pilots'), state['pilot_library']):
        if not isinstance(people, list) or any(not isinstance(p, dict) for p in people):
            raise ValueError('Invalid pilot library')
        for person in people:
            if any(not isinstance(person.get(k, ''), str) for k in PILOT_FIELDS):
                raise ValueError('Invalid pilot field')
            if not isinstance(person.get('message_types', []), list) or any(k not in ANDROID_FLIGHT_TYPES for k in person.get('message_types', [])):
                raise ValueError('Invalid pilot message selection')
    per = defaults()['per_type']
    for kind, spec in {**MESSAGE_FIELDS, **EXTENSIONS}.items():
        entry = state['per_type'].get(kind, {})
        if not isinstance(entry, dict):
            raise ValueError('Invalid per-message fields')
        for key, field in spec.items():
            if key in entry and type(entry[key]) is not (bool if field.kind == 'bool' else str):
                raise ValueError('Invalid message field: ' + key)
        per[kind].update(entry)
    state['per_type'] = per
    state['presentation'] = {**DEFAULT_PRESENTATION, **state['presentation']}
    for key, choices in [('design', BUILTIN_DESIGNS), ('length', ('Court', 'Moyen', 'Détaillé')),
                         ('emoji_style', EMOJI_STYLES)]:
        if state['presentation'][key] not in choices:
            raise ValueError('Unknown presentation: ' + key)
    if not isinstance(state['presentation']['discord_aligned'], bool):
        raise ValueError('Invalid Discord alignment')
    for key, text in state['preview_edits'].items():
        if key not in ALL_TYPES or not isinstance(text, str):
            raise ValueError('Invalid preview')
    for item in state['saved_flights']:
        if not isinstance(item, dict) or not isinstance(item.get('flight'), dict) or not isinstance(item.get('id'), str) or not isinstance(item.get('label'), str):
            raise ValueError('Invalid saved flight')
        nested = {'flight': item['flight'], 'per_type': item.get('per_type', {})}
        for key in ('preview_edits', 'presentation', 'message_type', 'pilot_name', 'active_session'):
            if key in item:
                nested[key] = item[key]
        normalise_state(nested)
    return state


def pc_state(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid PC state')
    result = deepcopy(value)
    selected = result.get('language', result.get('finder_language', 'fr'))
    result['language'] = selected if selected in ('fr', 'en') else 'fr'
    result.setdefault('joke_seen', True)
    return result


def validate_design(value):
    if not isinstance(value, dict) or not isinstance(value.get('name'), str) or not value['name'].strip():
        raise ValueError('Invalid design name')
    for key in ('template', 'heading', 'footer', 'base_design'):
        if key in value and not isinstance(value[key], str):
            raise ValueError('Invalid design field: ' + key)
    if 'guided' in value and not isinstance(value['guided'], bool):
        raise ValueError('Invalid guided design')
    if value.get('base_design', 'Classique') not in BUILTIN_DESIGNS:
        raise ValueError('Unknown base design')
    if not value.get('guided') and not value.get('template'):
        raise ValueError('Template required')
    if not value.get('guided'):
        context = custom_context('ATC REQUEST', empty_flight(), {}, '', '')
        context.update({key: '' for spec in EXTENSIONS.values() for key in spec})
        apply_custom(value['template'], context)
    return deepcopy(value)


FORMAT = 'rfs-flightdeck-backup'
SCHEMA_VERSION = 1
FILES = {'rfs_state.json': 'state', 'rfs_history.json': 'history',
         'rfs_presets.json': 'presets', 'rfs_designs.json': 'designs'}
DEVICE_LOCAL_FIELDS = ('update_preferences',)


class BackupError(ValueError):
    """A short localized user-facing error; detail never contains profile values."""

    def __init__(self, message, detail=''):
        super().__init__(message)
        self.detail = detail


def localise_error(error, language='en'):
    if isinstance(error, BackupError):
        return error
    detail = str(error)
    if 'version' in detail.lower():
        message = ('Cette version de sauvegarde n’est pas prise en charge. Aucune donnée n’a été modifiée.'
                   if language == 'fr' else 'This backup version is not supported. No data was changed.')
    elif '2 MB' in detail:
        message = ('La sauvegarde dépasse 2 Mo. Aucune donnée n’a été modifiée.'
                   if language == 'fr' else 'The backup exceeds 2 MB. No data was changed.')
    else:
        message = ('La sauvegarde est invalide ou incomplète. Aucune donnée n’a été modifiée.'
                   if language == 'fr' else 'The backup is invalid or incomplete. No data was changed.')
    return BackupError(message, detail)


def _size_check(value):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(encoded) > STATE_LIMIT:
        raise ValueError('Backup exceeds 2 MB')


def validate_record(item, history=False):
    if not isinstance(item, dict) or item.get('message_type') not in ALL_TYPES:
        raise ValueError('Invalid stored message type')
    if history and not isinstance(item.get('message'), str):
        raise ValueError('Invalid history entry')
    if not isinstance(item.get('flight'), dict) or not isinstance(item.get('data'), dict):
        raise ValueError('Invalid stored message fields')
    normalise_state({'message_type': item['message_type'], 'flight': item['flight'],
        'pilot_name': item.get('pilot_name', ''), 'presentation': item.get('presentation', {}),
        'per_type': {item['message_type']: item['data']}})


def validate_payload(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid backup')
    check_json(value)
    if (not isinstance(value.get('history'), list) or not isinstance(value.get('presets'), dict)
            or not isinstance(value.get('designs'), dict)):
        raise ValueError('Invalid backup collections')
    result = deepcopy(value)
    result.pop('schema_version', None)
    result['state'] = normalise_state(pc_state(value.get('state')))
    for item in result['history']:
        validate_record(item, history=True)
    for item in result['presets'].values():
        validate_record(item)
    result['designs'] = {key: validate_design(design) for key, design in value['designs'].items()}
    _size_check(result)
    return result


def parse_backup(value, language='en'):
    """Accept the common format, legacy Android export, PC state or four PC files."""
    try:
        if isinstance(value, str):
            if len(value.encode('utf-8')) > STATE_LIMIT:
                raise ValueError('Backup exceeds 2 MB')
            value = json.loads(value.lstrip('\ufeff'))
        if not isinstance(value, dict):
            raise ValueError('Invalid backup')
        source = {'app': 'RFS Flightdeck', 'platform': 'legacy', 'version': ''}
        if any(key in value for key in FILES):
            if set(value) != set(FILES) or any(not isinstance(v, str) for v in value.values()):
                raise ValueError('Select all four PC JSON files')
            if sum(len(v.encode('utf-8')) for v in value.values()) > STATE_LIMIT:
                raise ValueError('Backup exceeds 2 MB')
            payload = {key: json.loads(value[name].lstrip('\ufeff')) for name, key in FILES.items()}
            source['platform'] = 'windows-legacy'
        elif 'format' in value:
            if value.get('format') != FORMAT or type(value.get('schema_version')) is not int or value['schema_version'] != SCHEMA_VERSION:
                raise ValueError('Unsupported backup version or format')
            if not isinstance(value.get('source'), dict):
                raise ValueError('Invalid backup source')
            source = deepcopy(value['source'])
            for key in ('app', 'platform', 'version'):
                if not isinstance(source.get(key), str):
                    raise ValueError('Invalid backup source')
            if not isinstance(value.get('created_at'), str):
                raise ValueError('Invalid backup date')
            stamp = datetime.fromisoformat(value['created_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError('Backup requires UTC date')
            check_json(value)
            _size_check(value)
            payload = value.get('payload')
        elif 'schema_version' in value:
            if type(value['schema_version']) is not int or value['schema_version'] != 1:
                raise ValueError('Unsupported backup version')
            payload = value
            source['platform'] = 'android-legacy'
        elif 'flight' in value:
            payload = {'state': value, 'history': [], 'presets': {}, 'designs': {}}
            source['platform'] = 'windows-state-legacy'
        else:
            raise ValueError('Invalid backup')
        payload = validate_payload(payload)
        # The desktop adapter deliberately keeps Android's selection separately.
        selected = payload['state'].pop('android_message_type', '')
        if selected in EXTENSIONS:
            payload['state']['message_type'] = selected
        return {'payload': payload, 'summary': summary(payload), 'source': source}
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        raise localise_error(error, language) from error


def export_backup(payload, platform='windows', version='', created_at=None):
    value = validate_payload(payload)
    selected = value['state'].pop('android_message_type', '')
    if selected in EXTENSIONS:
        value['state']['message_type'] = selected
    result = {'format': FORMAT, 'schema_version': SCHEMA_VERSION,
        'source': {'app': 'RFS Flightdeck', 'platform': platform, 'version': version},
        'created_at': (created_at or datetime.now(timezone.utc)).isoformat(), 'payload': value}
    _size_check(result)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    if len(text.encode('utf-8')) > STATE_LIMIT:
        raise ValueError('Backup exceeds 2 MB')
    return text


def summary(payload):
    state = payload['state']
    return {'saved_flights': len(state['saved_flights']), 'pilots': len(state['pilot_library']),
            'history': len(payload['history']), 'presets': len(payload['presets']),
            'designs': len(payload['designs']),
            'android_message_type': state['message_type'] if state['message_type'] in EXTENSIONS else ''}


def desktop_state(value):
    state = deepcopy(value)
    if state['message_type'] in EXTENSIONS:
        state['android_message_type'] = state['message_type']
        state['message_type'] = 'ATC REQUEST'
    return state


def preserve_device_preferences(candidate, current):
    for key in DEVICE_LOCAL_FIELDS:
        candidate['state'].pop(key, None)
        if key in current['state']:
            candidate['state'][key] = deepcopy(current['state'][key])
    target_map = candidate['state'].get('map_settings', {})
    local_map = current['state'].get('map_settings', {})
    for key in ('satellite', 'winds'):
        if key in target_map or key in local_map:
            target_map[key] = bool(local_map.get(key, False))


def _fingerprint(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _union(first, second):
    result = deepcopy(first)
    known = {_fingerprint(v) for v in first}
    for item in second:
        marker = _fingerprint(item)
        if marker not in known:
            result.append(deepcopy(item))
            known.add(marker)
    return result


def _new_name(name, collection):
    index = 2
    while f'{name} (import {index})' in collection:
        index += 1
    return f'{name} (import {index})'


def _remap_custom_ids(value, mapping):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'custom_id' and isinstance(item, str) and item in mapping:
                value[key] = mapping[item]
            else:
                _remap_custom_ids(item, mapping)
    elif isinstance(value, list):
        for item in value:
            _remap_custom_ids(item, mapping)


def _has_draft(state):
    return (any(state['flight'].get(key) for key in FLIGHT_FIELDS) or bool(state['flight'].get('pilots'))
            or bool(state.get('preview_edits')) or state['per_type'] != defaults()['per_type'])


def merge_payloads(current, imported, language='en'):
    """Keep the live draft and both conflicting records; never guess a winning date."""
    current, imported = validate_payload(current), validate_payload(imported)
    result, incoming = deepcopy(current), deepcopy(imported)
    remapped = {}
    for key, design in incoming['designs'].items():
        if key in result['designs'] and result['designs'][key] != design:
            remapped[key] = next((ident for ident, existing in result['designs'].items() if existing == design), uuid.uuid4().hex)
    _remap_custom_ids(incoming, remapped)
    for key, design in incoming['designs'].items():
        result['designs'][remapped.get(key, key)] = design
    for key, preset in incoming['presets'].items():
        target = key
        if key in result['presets'] and result['presets'][key] != preset:
            target = next((name for name, existing in result['presets'].items() if existing == preset), None)
            if target is None:
                target = _new_name(key, result['presets'])
        result['presets'][target] = preset
    local, other = result['state'], incoming['state']
    baseline = defaults()
    for key, value in other.items():
        if key not in local or (key in ('finder_filters', 'fuel_inputs', 'map_settings', 'design_draft', 'report_draft')
                and local.get(key) == baseline.get(key)):
            local[key] = deepcopy(value)
    local['pilot_library'] = _union(local['pilot_library'], other['pilot_library'])
    local['flight_log'] = _union(local['flight_log'], other['flight_log'])[:500]
    result['history'] = _union(result['history'], incoming['history'])[:200]
    saved = local['saved_flights']
    for item in other['saved_flights']:
        match = next((s for s in saved if s['id'] == item['id']), None)
        if match == item:
            continue
        if match is not None:
            contents = {k: v for k, v in item.items() if k != 'id'}
            if any({k: v for k, v in s.items() if k != 'id'} == contents for s in saved):
                continue
            item = {**item, 'id': uuid.uuid4().hex}
        saved.append(item)
    if not _has_draft(current['state']):
        for key in ('flight', 'per_type', 'preview_edits', 'presentation', 'message_type', 'pilot_name', 'active_session'):
            local[key] = deepcopy(other[key])
        local['current_flight_id'] = ''
    elif any(local[key] != other[key] for key in ('flight', 'per_type', 'preview_edits', 'presentation', 'message_type', 'pilot_name', 'active_session')):
        label = 'Vol actuel importé' if language == 'fr' else 'Imported current flight'
        draft = {'id': uuid.uuid4().hex, 'label': label,
                 **{k: deepcopy(other[k]) for k in ('flight', 'per_type', 'preview_edits', 'presentation', 'message_type', 'pilot_name', 'active_session')}}
        # Repeated imports must not create repeated current-flight copies.
        identical = lambda s: all(s.get(k, {} if k == 'active_session' else None) == draft[k] for k in ('flight', 'per_type', 'preview_edits', 'presentation', 'message_type', 'pilot_name', 'active_session'))
        if not any(identical(s) for s in saved):
            saved.append(draft)
    preserve_device_preferences(result, current)
    return validate_payload(result)
