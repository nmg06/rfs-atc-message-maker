"""Offline Android service using the unchanged Windows message/Finder/fuel engines."""
from copy import deepcopy
from dataclasses import asdict, fields
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid
from zoneinfo import available_timezones

from country_data import COUNTRIES
from finder.database import connect_readonly
from finder.duration import parse_minutes, parse_finder_hours
from finder.mapping import use_this_flight
from finder.search import Criteria, SearchSession
from finder.i18n import tr as finder_tr
from finder.rfs_catalogue import TYPE_BY_ID
from fuel.calculator import calculate_fuel, load_json
from fuel.selection import resolve_aircraft
from fuel.duration import duration_hours
from history_utils import duplicate_index
from i18n import set_language, tr
from message_builder import (compose, validate_group, preview_text, clipboard_text,
    DEFAULT_PRESENTATION, BUILTIN_DESIGNS, EMOJI_STYLES, PILOT_FIELDS, OPERATION_LABELS,
    _header, _layout, apply_custom, custom_context, limit_emojis, strip_emojis)
from rfs_schema import (Field, MESSAGE_TYPES, FLIGHT_TYPES, FLIGHT_FIELDS,
    MESSAGE_FIELDS, FLIGHT_FIELDS_BY_TYPE, empty_flight, empty_per_type)
from validation import Issue, REQUIRED_FLIGHT, REQUIRED_MESSAGE, emoji_count

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
STATE_LIMIT = 2 * 1024 * 1024


def defaults():
    per_type = empty_per_type()
    per_type.update({kind: {key: False if field.kind == 'bool' else '' for key, field in spec.items()}
                     for kind, spec in EXTENSIONS.items()})
    return {'pilot_name': 'n1chita', 'pilot_library': [], 'server': '', 'theme': 'Sombre',
        'message_type': 'ATC REQUEST', 'current_flight_id': '', 'flight': empty_flight(),
        'per_type': per_type, 'saved_flights': [], 'preview_edits': {},
        'presentation': deepcopy(DEFAULT_PRESENTATION), 'compact_history': True,
        'intro_seen': False, 'joke_seen': False, 'language': 'fr', 'finder_filters': {},
        'fuel_inputs': {}, 'recent': {k: [] for k in ('airline', 'aircraft', 'airports', 'controllers', 'servers')}}


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
            temporary = Path(f.name)
            json.dump(value, f, ensure_ascii=False, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def check_json(value, depth=0):
    if depth > 24:
        raise ValueError('Backup nesting exceeds limit')
    if isinstance(value, str) and len(value) > 20000:
        raise ValueError('Text exceeds limit')
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('Invalid number')
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError('Invalid key')
            check_json(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 1000:
            raise ValueError('Collection exceeds limit')
        for item in value:
            check_json(item, depth + 1)


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
    for key in FLIGHT_FIELDS:
        if not isinstance(state['flight'][key], str):
            raise ValueError('Invalid flight field: ' + key)
    for people in (state['flight'].get('pilots'), state['pilot_library']):
        if not isinstance(people, list) or any(not isinstance(p, dict) for p in people):
            raise ValueError('Invalid pilot library')
        for person in people:
            if any(not isinstance(person.get(k, ''), str) for k in PILOT_FIELDS):
                raise ValueError('Invalid pilot field')
            if not isinstance(person.get('message_types', []), list) or any(k not in FLIGHT_TYPES for k in person.get('message_types', [])):
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
        normalise_state(nested)
    return state


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
        apply_custom(value['template'], custom_context('ATC REQUEST', empty_flight(), {}, '', ''))
    return deepcopy(value)


def fuel_hours(text):
    # Same bare-hour/decimal/HH:MM grammar as Windows, plus explicit mobile minutes.
    hours = duration_hours(text)
    if hours is None and re.search(r'(?:m|min|minutes?)$', str(text).strip().lower()):
        minutes = parse_minutes(text)
        return minutes/60 if minutes is not None else None
    return hours


class Engine:
    def __init__(self, private_dir, database):
        self.path = Path(private_dir) / 'rfs_android.json'
        self.database = Path(database)
        self.warning = ''
        self.value = {'schema_version': 1, 'state': defaults(), 'history': [], 'presets': {}, 'designs': {}}
        if self.path.exists():
            try:
                self.value = self.validate_backup(json.loads(self.path.read_text(encoding='utf-8')))
            except (ValueError, TypeError, KeyError) as error:
                recovery = self.path.with_name('rfs_android.corrupt-' + uuid.uuid4().hex + '.json')
                recovery.write_bytes(self.path.read_bytes())
                self.warning = 'Saved data was unreadable; original preserved: ' + recovery.name
        self.query = None
        self.query_time = None
        self.rows = []
        self.finder_session = SearchSession()
        self.fuel_result = None
        set_language(self.state['language'])

    @property
    def state(self):
        return self.value['state']

    def validate_backup(self, value):
        if not isinstance(value, dict):
            raise ValueError('Invalid backup')
        # An explicitly selected Windows state JSON is also accepted, never automatic.
        if 'schema_version' not in value and 'flight' in value:
            value = {'schema_version': 1, 'state': value, 'history': [], 'presets': {}, 'designs': {}}
        if value.get('schema_version') != 1:
            raise ValueError('Unsupported backup version')
        check_json(value)
        result = deepcopy(value)
        result['state'] = normalise_state(value.get('state'))
        if not isinstance(value.get('history'), list) or not isinstance(value.get('presets'), dict) or not isinstance(value.get('designs'), dict):
            raise ValueError('Invalid backup collections')
        for item in result['history']:
            if not isinstance(item, dict) or not isinstance(item.get('message'), str) or item.get('message_type') not in ALL_TYPES:
                raise ValueError('Invalid history entry')
            self.validate_record(item)
        result['designs'] = {key: validate_design(design) for key, design in value['designs'].items()}
        for item in result['presets'].values():
            if not isinstance(item, dict) or item.get('message_type') not in ALL_TYPES:
                raise ValueError('Invalid favourite')
            self.validate_record(item)
        return result

    def validate_record(self, item):
        if not isinstance(item.get('flight'), dict) or not isinstance(item.get('data'), dict):
            raise ValueError('Invalid stored message fields')
        normalise_state({'message_type': item['message_type'], 'flight': item['flight'],
            'pilot_name': item.get('pilot_name', ''), 'presentation': item.get('presentation', {}),
            'per_type': {item['message_type']: item['data']}})

    def commit(self, value):
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(payload.encode('utf-8')) > STATE_LIMIT:
            raise ValueError('Backup exceeds 2 MB')
        atomic_json(self.path, value)
        self.value = value
        set_language(self.state['language'])

    def metadata(self):
        language = self.state['language']
        def spec(fields_dict):
            return {key: {**asdict(field), 'label': tr(field.label), 'hint': tr(field.hint),
                          'choice_labels': [tr(c) for c in field.choices]} for key, field in fields_dict.items()}
        return {'types': ALL_TYPES, 'windows_types': MESSAGE_TYPES, 'flight_types': FLIGHT_TYPES,
            'flight_fields': spec(FLIGHT_FIELDS), 'message_fields': {k: spec(v) for k, v in {**MESSAGE_FIELDS, **EXTENSIONS}.items()},
            'flight_by_type': FLIGHT_FIELDS_BY_TYPE, 'required_flight': REQUIRED_FLIGHT,
            'required_message': REQUIRED_MESSAGE, 'pilot_fields': PILOT_FIELDS,
            'designs': BUILTIN_DESIGNS, 'emoji_styles': EMOJI_STYLES,
            'operation_modes': list(OPERATION_LABELS), 'countries': COUNTRIES,
            'aircraft': load_json('aircraft_fuel_data.json')['aircraft'],
            'arrivals': sorted(load_json('airport_alternates.json')['destinations']),
            'finder_fields': {f.name: {'default': deepcopy(getattr(Criteria(), f.name)),
                'label': finder_tr(f.name, language)} for f in fields(Criteria)},
            'timezones': sorted(available_timezones()), 'rfs_types': TYPE_BY_ID,
            'warning': self.warning}

    def extension(self, kind, flight, data):
        issues = []
        required_flight = () if kind == 'ATIS' else ('callsign', 'departure_icao', 'departure_gate', 'departure_runway')
        for key in required_flight:
            if not str(flight.get(key, '')).strip():
                issues.append(Issue(key, tr(FLIGHT_FIELDS[key].label) + ' required'))
        for key, field in EXTENSIONS[kind].items():
            if field.required and not str(data.get(key, '')).strip():
                issues.append(Issue(key, tr(field.label) + ' required'))
        airport = data.get('airport_icao') if kind == 'ATIS' else flight.get('departure_icao')
        if airport and not re.fullmatch('[A-Za-z]{4}', airport):
            issues.append(Issue('airport_icao' if kind == 'ATIS' else 'departure_icao', 'ICAO: 4 letters'))
        runway = data.get('runway') if kind == 'ATIS' else flight.get('departure_runway')
        if runway and not re.fullmatch(r'(?:(?:RWY|RUNWAY)\s*)?(?:0[1-9]|[12][0-9]|3[0-6])[LRC]?', runway, re.I):
            issues.append(Issue('runway' if kind == 'ATIS' else 'departure_runway', 'Invalid runway'))
        if kind == 'ATIS':
            if data.get('information') and not re.fullmatch('[A-Za-z]', data['information']):
                issues.append(Issue('information', 'Information: A-Z'))
            body = '\n'.join(f'{key.upper()} : {value}' for key, value in data.items() if value)
        else:
            if kind == 'PUSHBACK' and data.get('pushback') and not re.fullmatch(r'\d{1,3}', data['pushback']):
                issues.append(Issue('pushback', 'Pushback: minutes'))
            body = '\n'.join(filter(None, [f"{self.state['pilot_name']} | {flight.get('aircraft', '')}",
                f"CALLSIGN : {flight.get('callsign', '')}", f"ICAO : {airport or ''}",
                f"GATE : {flight.get('departure_gate', '')}", f"RUNWAY : {runway or ''}",
                *[f'{key.upper()} : {value}' for key, value in data.items() if value]]))
        options = self.state['presentation']
        body = _header(kind, options['design']) + '\n\n' + _layout(body, options['design'])
        if options['emoji_style'] == 'Sans emojis':
            body = strip_emojis(body)
        return limit_emojis(body), issues

    def render(self, regenerate=False):
        kind, flight = self.state['message_type'], self.state['flight']
        data = deepcopy(self.state['per_type'][kind])
        options = self.state['presentation']
        if options['length'] == 'Détaillé' and kind == 'FLIGHT COMPLETED':
            data['detailed'] = True
        if kind in EXTENSIONS:
            text, problems = self.extension(kind, flight, data)
        else:
            problems = validate_group(kind, flight, data, self.state['pilot_name'].strip())
            text = compose(kind, flight, data, self.state['pilot_name'].strip(), options,
                           self.value['designs'].get(options.get('custom_id', '')))
        edited = None if regenerate else self.state['preview_edits'].get(kind)
        preview = preview_text(edited if edited is not None else text)
        clipboard = clipboard_text(preview.strip(), options['discord_aligned'])
        count = emoji_count(preview)
        if len(clipboard) > 2000:
            problems.append(Issue('length', tr('Message trop long : choisissez Court ou retirez des détails (2 000 caractères).')))
        if kind != 'DISPATCH FORM' and count > 6:
            problems.append(Issue('emoji', tr('Plus de 6 emojis : réduisez-les avant Copy.')))
        return {'preview': preview, 'clipboard': clipboard, 'issues': [asdict(p) for p in problems],
                'characters': len(clipboard), 'emojis': count, 'can_copy': not problems and bool(preview.strip())}

    def sync(self, state):
        candidate = deepcopy(self.value)
        candidate['state'] = normalise_state(state)
        if candidate['state']['finder_filters'] != self.state['finder_filters']:
            self.query = None
            self.rows = []
        self.commit(candidate)

    def criteria(self, values):
        known = {f.name: getattr(Criteria(), f.name) for f in fields(Criteria)}
        converted = {}
        for key, item in values.items():
            if key not in known or key == 'offset':
                continue
            default = known[key]
            if isinstance(default, list):
                converted[key] = [x.strip().upper() for x in item.split(',') if x.strip()] if isinstance(item, str) else item
            elif key in ('min_minutes', 'max_minutes', 'target_minutes', 'tolerance_minutes', 'time_tolerance'):
                parser = parse_finder_hours if key in ('min_minutes', 'max_minutes', 'target_minutes') else parse_minutes
                value = parser(item) if isinstance(item, str) else item
                if value is not None:
                    converted[key] = value
            elif isinstance(default, bool):
                if not isinstance(item, bool):
                    raise ValueError('Invalid boolean filter')
                converted[key] = item
            elif item != '':
                converted[key] = item
        converted.update(limit=100, offset=0)
        return Criteria(**converted)

    def duration_details(self, row):
        # The shipped snapshot contains identifiable formula-derived duration rows.
        duration, distance = row.get('duration_min'), row.get('distance_nm')
        estimated = distance is not None and duration == round(distance / 390 * 60 + 15)
        return {'origin': 'estimated_or_unverified' if estimated else 'unverified',
                'note': ('Formula-compatible estimate: 390 kt + 15 min; ±5% arithmetic bounds, not observed precision.'
                         if estimated else 'Historical database value; observation provenance must be verified.'),
                'bounds': [row.get('duration_p10'), row.get('duration_p90')]}

    def handle(self, method, args):
        if 'state' in args:
            self.sync(args['state'])
        if method == 'bootstrap':
            return {'value': deepcopy(self.value), 'metadata': self.metadata(), 'render': self.render()}
        if method == 'sources':
            with connect_readonly(self.database) as db:
                return {'sources': [dict(row) for row in db.execute('SELECT * FROM sources ORDER BY source_id')]}
        if method in ('save', 'render', 'regenerate'):
            if method == 'regenerate':
                candidate = deepcopy(self.value)
                candidate['state']['preview_edits'].pop(self.state['message_type'], None)
                self.commit(candidate)
            return {'value': deepcopy(self.value), 'render': self.render()}
        if method == 'copy':
            rendered = self.render()
            if not rendered['can_copy']:
                raise ValueError('\n'.join(p['text'] for p in rendered['issues']))
            entry = {'date': datetime.now().isoformat(timespec='seconds'), 'message_type': self.state['message_type'],
                'pilot_name': self.state['pilot_name'], 'flight': deepcopy(self.state['flight']),
                'data': deepcopy(self.state['per_type'][self.state['message_type']]),
                'presentation': deepcopy(self.state['presentation']), 'message': rendered['clipboard']}
            candidate = deepcopy(self.value)
            history = candidate['history']
            index = duplicate_index(history, entry, self.state['compact_history'])
            if index is not None:
                entry['copies'] = history.pop(index).get('copies', 1) + 1
            history.insert(0, entry)
            candidate['history'] = history[:200]
            self.commit(candidate)
            return {'text': rendered['clipboard'], 'value': deepcopy(self.value)}
        if method == 'finder':
            more = bool(args.get('more'))
            if not more:
                self.query = self.criteria(self.state['finder_filters'])
                self.query_time = datetime.now(timezone.utc)
                self.rows = []
            if self.query is None:
                raise ValueError('Search filters changed: run a new search')
            query = deepcopy(self.query)
            query.offset = len(self.rows)
            result = self.finder_session.page(self.database, query, self.query_time)
            self.rows.extend(result['results'])
            result['warnings_text'] = [finder_tr(w, self.state['language']) for w in result['warnings']]
            for row in result['results']:
                row['duration_details'] = self.duration_details(row)
            return result
        if method == 'finder_details':
            row = self.rows[int(args['index'])]
            runways = {}
            with connect_readonly(self.database) as db:
                for endpoint in ('origin', 'destination'):
                    runways[endpoint] = [dict(r) for r in db.execute('SELECT le_ident,he_ident,length_ft,surface FROM runways WHERE airport_id=? AND closed=0 ORDER BY le_ident', (row[endpoint + '_id'],))]
            return {'row': row, 'runways': runways, 'duration': self.duration_details(row),
                    'warnings': [finder_tr(w, self.state['language']) for w in row['warnings']]}
        if method == 'finder_use':
            row = self.rows[int(args['index'])]
            candidate = deepcopy(self.value)
            candidate['state']['flight'] = use_this_flight(self.state['flight'], row)
            candidate['state']['current_flight_id'] = ''
            candidate['state']['preview_edits'] = {}
            self.commit(candidate)
        elif method == 'fuel_prepare':
            flight = self.state['flight']
            signature = json.dumps([flight.get(key) for key in
                ('aircraft', 'fuel_aircraft_id', 'estimated_flight_time', 'arrival_icao', 'selected_flight')], sort_keys=True)
            resolved = resolve_aircraft(flight)
            if self.state['fuel_inputs'].get('_flight_signature') != signature:
                candidate = deepcopy(self.value)
                inputs = candidate['state']['fuel_inputs']
                inputs.update(aircraft=resolved['record']['id'] if resolved['record'] else '',
                              _flight_signature=signature)
                for target, source in (('duration','estimated_flight_time'), ('arrival','arrival_icao')):
                    if flight.get(source):
                        inputs[target] = flight[source]
                self.commit(candidate)
            return {'value': deepcopy(self.value), 'selection': resolved}
        elif method == 'fuel':
            inputs = self.state['fuel_inputs']
            self.fuel_result = None
            hours = fuel_hours(inputs.get('duration', ''))
            if hours is None:
                raise ValueError('Duration required: 5h, 5h30, 330min')
            self.fuel_result = calculate_fuel(inputs.get('aircraft', ''), hours, inputs.get('arrival', ''))
            return deepcopy(self.fuel_result)
        elif method == 'fuel_use':
            inputs = self.state['fuel_inputs']
            # Recalculate on apply; a stale UI result cannot apply old inputs.
            result = calculate_fuel(inputs.get('aircraft', ''), fuel_hours(inputs.get('duration', '')) or 0, inputs.get('arrival', ''))
            candidate = deepcopy(self.value)
            flight = candidate['state']['flight']
            flight.update(fuel=f"{result['total_block_fuel_kg_exact']:.0f}", aircraft=result['aircraft']['name'],
                          fuel_aircraft_id=result['aircraft']['id'], fuel_calculation=deepcopy(result))
            if flight.get('selected_flight'):
                flight['selected_flight'].setdefault('fields', {}).update(fuel='RFS_SIMULATION_ESTIMATE', aircraft='USER_INPUT_FUEL_VARIANT')
            candidate['state']['preview_edits'] = {}
            self.commit(candidate)
        elif method == 'export':
            return {'text': json.dumps(self.value, ensure_ascii=False, indent=2)}
        elif method == 'import':
            text = args['text']
            if len(text.encode('utf-8')) > STATE_LIMIT:
                raise ValueError('Import exceeds 2 MB')
            candidate = self.validate_backup(json.loads(text))
            atomic_json(self.path.with_suffix('.before-import.json'), self.value)
            self.commit(candidate)
            self.query, self.rows = None, []
            return {'value': deepcopy(self.value), 'metadata': self.metadata(), 'render': self.render()}
        elif method == 'save_flight':
            label = str(args.get('label', '')).strip()
            if not label:
                raise ValueError('Flight name required')
            candidate = deepcopy(self.value)
            ident = self.state.get('current_flight_id') or uuid.uuid4().hex
            item = {'id': ident, 'label': label, 'flight': deepcopy(self.state['flight']),
                    'per_type': deepcopy(self.state['per_type'])}
            saved = candidate['state']['saved_flights']
            saved[:] = [v for v in saved if v.get('id') != ident]
            saved.append(item)
            candidate['state']['current_flight_id'] = ident
            self.commit(candidate)
        elif method in ('load_flight', 'load_history', 'load_preset'):
            candidate = deepcopy(self.value)
            if method == 'load_flight':
                item = next(v for v in self.state['saved_flights'] if v['id'] == args['id'])
                candidate['state']['per_type'].update(deepcopy(item.get('per_type', {})))
                candidate['state']['current_flight_id'] = item['id']
            else:
                item = self.value['history'][int(args['index'])] if method == 'load_history' else self.value['presets'][args['id']]
                kind = item['message_type']
                candidate['state'].update(message_type=kind, pilot_name=item.get('pilot_name', self.state['pilot_name']),
                    presentation={**DEFAULT_PRESENTATION, **item.get('presentation', {})}, current_flight_id='')
                candidate['state']['per_type'][kind] = {**defaults()['per_type'][kind], **deepcopy(item.get('data', {}))}
            candidate['state']['flight'] = {**empty_flight(), **deepcopy(item['flight'])}
            candidate['state']['preview_edits'] = {}
            if method == 'load_history':
                candidate['state']['preview_edits'][item['message_type']] = item['message']
            self.commit(self.validate_backup(candidate))
        elif method == 'save_preset':
            label = str(args['label']).strip()
            if not label:
                raise ValueError('Favourite name required')
            candidate = deepcopy(self.value)
            candidate['presets'][label] = {'message_type': self.state['message_type'], 'pilot_name': self.state['pilot_name'],
                'flight': deepcopy(self.state['flight']), 'data': deepcopy(self.state['per_type'][self.state['message_type']]),
                'presentation': deepcopy(self.state['presentation'])}
            self.commit(candidate)
        elif method == 'design':
            candidate = deepcopy(self.value)
            design = validate_design(args['design'])
            ident = args.get('id') or uuid.uuid4().hex
            candidate['designs'][ident] = design
            candidate['state']['presentation']['custom_id'] = ident
            candidate['state']['preview_edits'] = {}
            self.commit(candidate)
        elif method == 'clear':
            candidate = deepcopy(self.value)
            candidate['state'].update(flight=empty_flight(), current_flight_id='', preview_edits={})
            per_type = defaults()['per_type']
            for kind in (*FLIGHT_TYPES, *EXTENSIONS):
                candidate['state']['per_type'][kind] = per_type[kind]
            self.commit(candidate)
        else:
            raise ValueError('Unknown operation: ' + method)
        return {'value': deepcopy(self.value), 'render': self.render()}


_engine = None


def initialise(private_dir, database):
    global _engine
    _engine = Engine(private_dir, database)


def request(method, payload):
    try:
        if _engine is None:
            raise RuntimeError('Engine not initialised')
        result = _engine.handle(method, json.loads(payload))
        return json.dumps({'ok': True, 'result': result}, ensure_ascii=False, allow_nan=False)
    except Exception as error:
        return json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False)
