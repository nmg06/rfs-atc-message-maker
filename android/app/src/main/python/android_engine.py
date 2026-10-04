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
from map_geometry import airport_coordinates, great_circle
from visual_themes import THEMES, theme_colors
from flight_planning import airport_plan, elapsed_seconds, validate_log
from finder.database import connect_readonly
from finder.duration import parse_minutes, parse_finder_hours
from finder.mapping import use_this_flight
from finder.provenance import duration_provenance
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
    _header, _layout, apply_custom, custom_context, limit_emojis, strip_emojis,
    format_message, pilot_flight, _group_identity)
from templates import format_runway
from rfs_schema import (Field, MESSAGE_TYPES, FLIGHT_TYPES, FLIGHT_FIELDS,
    MESSAGE_FIELDS, FLIGHT_FIELDS_BY_TYPE, empty_flight, empty_per_type)
from validation import Issue, REQUIRED_FLIGHT, REQUIRED_MESSAGE, emoji_count

from backup_bundle import (EXTENSIONS, ALL_TYPES, ANDROID_FLIGHT_TYPES, STATE_LIMIT, defaults, check_json, normalise_state, pc_state, validate_design, validate_payload, parse_backup, export_backup, merge_payloads, summary, localise_error, preserve_device_preferences)

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
        return {'schema_version': 1, **parse_backup(value)['payload']}

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

    def apply_import(self, value, mode='replace'):
        parsed = parse_backup(value, self.state['language'])
        if mode not in ('merge', 'replace'):
            raise localise_error(ValueError('Invalid import mode'), self.state['language'])
        try:
            candidate = (merge_payloads(self.value, parsed['payload'], self.state['language'])
                         if mode == 'merge' else parsed['payload'])
        except (ValueError, TypeError, KeyError) as error:
            raise localise_error(error, self.state['language']) from error
        preserve_device_preferences(candidate, self.value)
        candidate = {'schema_version': 1, **candidate}
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
        backup = self.path.parent / 'backups' / ('before-import-' + stamp + '.json')
        atomic_json(backup, self.value)
        # Keep the established recovery location for older users/documentation.
        atomic_json(self.path.with_suffix('.before-import.json'), self.value)
        self.commit(candidate)
        return {'backup_path': str(backup), 'summary': summary(candidate)}

    def metadata(self):
        language = self.state['language']
        def spec(fields_dict):
            return {key: {**asdict(field), 'label': tr(field.label), 'hint': tr(field.hint),
                          'choice_labels': [tr(c) for c in field.choices]} for key, field in fields_dict.items()}
        return {'types': ALL_TYPES, 'windows_types': MESSAGE_TYPES, 'flight_types': ANDROID_FLIGHT_TYPES,
            'flight_fields': spec(FLIGHT_FIELDS), 'message_fields': {k: spec(v) for k, v in {**MESSAGE_FIELDS, **EXTENSIONS}.items()},
            'flight_by_type': FLIGHT_FIELDS_BY_TYPE, 'required_flight': REQUIRED_FLIGHT,
            'required_message': REQUIRED_MESSAGE, 'pilot_fields': PILOT_FIELDS,
            'designs': BUILTIN_DESIGNS, 'emoji_styles': EMOJI_STYLES,
            'operation_modes': list(OPERATION_LABELS), 'countries': COUNTRIES,
            'aircraft': load_json('aircraft_fuel_data.json')['aircraft'],
            'fuel_catalogue_note': tr(load_json('aircraft_fuel_data.json').get('note', '')),
            'arrivals': sorted(load_json('airport_alternates.json')['destinations']),
            'finder_fields': {f.name: {'default': deepcopy(getattr(Criteria(), f.name)),
                'label': finder_tr(f.name, language)} for f in fields(Criteria)},
            'timezones': sorted(available_timezones()), 'rfs_types': TYPE_BY_ID,
            'visual_themes': [{**theme_colors(r[0], language=language), 'light': theme_colors(r[0], False, language)} for r in THEMES],
            'warning': self.warning}

    def extension(self, kind, flight, data):
        issues = []
        required_flight = () if kind == 'ATIS' else ('aircraft', 'callsign', 'departure_icao', 'departure_gate', 'departure_runway')
        for key in required_flight:
            if not str(flight.get(key, '')).strip():
                issues.append(Issue(key, tr('{v0} est requis.', v0=tr(FLIGHT_FIELDS[key].label))))
        for key, field in EXTENSIONS[kind].items():
            if field.required and not str(data.get(key, '')).strip():
                issues.append(Issue(key, tr('{v0} est requis.', v0=tr(field.label))))
        airport = data.get('airport_icao') if kind == 'ATIS' else flight.get('departure_icao')
        if airport and not re.fullmatch('[A-Za-z]{4}', airport):
            issues.append(Issue('airport_icao' if kind == 'ATIS' else 'departure_icao', tr('Airport ICAO doit contenir exactement 4 lettres.')))
        runway = data.get('runway') if kind == 'ATIS' else flight.get('departure_runway')
        if runway and not re.fullmatch(r'(?:(?:RWY|RUNWAY)\s*)?(?:0[1-9]|[12][0-9]|3[0-6])[LRC]?', runway, re.I):
            issues.append(Issue('runway' if kind == 'ATIS' else 'departure_runway', tr('Piste invalide : 01 à 36, éventuellement L/R/C.')))
        if kind == 'ATIS':
            if data.get('information') and not re.fullmatch('[A-Za-z]', data['information']):
                issues.append(Issue('information', tr('Information ATIS : une lettre de A à Z.')))
            body = '\n'.join(f'{key.upper()} : {value}' for key, value in data.items() if value)
            if data.get('qnh') and not re.fullmatch(r'(?:[89]\d{2}|10\d{2}|1100)(?:\s*hpa)?', data['qnh'], re.I):
                issues.append(Issue('qnh', tr('QNH : 800 à 1100 hPa.')))
        else:
            if kind == 'PUSHBACK' and data.get('pushback') and not re.fullmatch(r'\d{1,3}', data['pushback']):
                issues.append(Issue('pushback', tr('Pushback doit être un nombre de minutes.')))
            if not self.state['pilot_name'].strip():
                issues.append(Issue('pilot_name', tr('Le pseudo RFS est requis.')))
            if kind == 'PUSHBACK' and data.get('direction') and data['direction'] not in EXTENSIONS[kind]['direction'].choices:
                issues.append(Issue('direction', tr('Direction invalide.')))
            body = '\n'.join(filter(None, [f"PILOT : {self.state['pilot_name']} | {flight.get('aircraft', '')}",
                f"CALLSIGN : {flight.get('callsign', '')}", f"ICAO : {airport or ''}",
                f"GATE : {flight.get('departure_gate', '')}", f"RUNWAY : {runway or ''}",
                *[f'{key.upper()} : {value}' for key, value in data.items() if value]]))
        options = deepcopy(self.state['presentation'])
        custom = self.value['designs'].get(options.get('custom_id', ''))
        if custom and custom.get('base_design'):
            options['design'] = custom['base_design']
        if options['length'] == 'Court':
            if kind == 'ATIS':
                body = body.replace('\n', ' · ')
            else:
                body = '\n'.join(line for line in body.splitlines() if not line.startswith(('SERVER :', 'NOTE :')))
        elif options['length'] == 'Détaillé' and kind != 'ATIS':
            details = [f'{key.upper()} : {flight[key]}' for key in ('airline', 'arrival_icao', 'cruise_fl', 'passengers', 'cargo', 'fuel') if flight.get(key)]
            if details:
                body += '\n\n' + '\n'.join(details)
        operation = []
        if kind != 'ATIS':
            pilots = [p for p in flight.get('pilots', []) if kind in p.get('message_types', ANDROID_FLIGHT_TYPES)]
            runways = [format_runway(flight.get('departure_runway', '')).upper()]
            parallel = flight.get('departure_mode') == 'Parallèle'
            if parallel and not pilots:
                issues.append(Issue('pilots', tr("Opération parallèle au {phase} : ajoutez au moins un autre pilote.", phase=tr('départ'))))
            for index, pilot in enumerate(pilots, 2):
                if not pilot.get('name', '').strip():
                    issues.append(Issue('pilots', tr('Pilote {index} : pseudo requis.', index=index)))
                extra = pilot_flight(flight, pilot)
                if not extra.get('callsign'):
                    issues.append(Issue('pilots', tr('Pilote {index} : callsign requis.', index=index)))
                own_runway = format_runway(pilot.get('departure_runway', '')).upper()
                if parallel and (not own_runway or own_runway in runways):
                    issues.append(Issue('pilots', tr('Pilote {index} : une opération parallèle exige une piste distincte au {phase}.', index=index, phase=tr('départ'))))
                runways.append(own_runway)
                if own_runway and not re.fullmatch(r'(?:0[1-9]|[12][0-9]|3[0-6])[LRC]?', own_runway):
                    issues.append(Issue('pilots', tr('Piste du pilote invalide.')))
            if pilots:
                body = _group_identity(body, 'ATC REQUEST', flight, data, self.state['pilot_name'], pilots)
            mode = OPERATION_LABELS.get(flight.get('departure_mode'))
            if mode:
                operation.append('OPERATION : ' + mode + ' departure')
        return format_message(kind, flight, data, self.state['pilot_name'], _layout(body, options['design']), options, custom, operation), issues

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
                'characters': len(clipboard), 'emojis': count, 'can_copy': bool(preview.strip()) and (not self.state['strict_validation'] or not problems)}

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
        origin = duration_provenance(row)
        observed = origin == 'AGGREGATED_COMPLETE_TRACKS'
        estimated = origin == 'ESTIMATED_DISTANCE_HEURISTIC'
        label = finder_tr('duration_observed' if observed else 'duration_estimated' if estimated else 'duration_unverified', self.state['language'])
        note = label
        if estimated:
            note += ' · ' + finder_tr('duration_formula', self.state['language']) + ' · ' + finder_tr('duration_formula_limits', self.state['language'])
        elif not observed:
            note += ' · ' + finder_tr('DURATION_POST_IMPORT_UNVERIFIED', self.state['language'])
        return {'origin': origin, 'label': label, 'note': note,
                'bounds_kind': 'observed_percentiles' if observed else 'arithmetic_bounds' if estimated else 'unverified_bounds',
                'bounds': [row.get('duration_p10'), row.get('duration_p90')]}

    def handle(self, method, args):
        if 'state' in args:
            self.sync(args['state'])
        if method == 'bootstrap':
            return {'value': deepcopy(self.value), 'metadata': self.metadata(), 'render': self.render()}
        if method == 'update':
            return {'render': self.render(), 'saved': True}
        if method == 'persist':
            return {'saved': True}
        if method == 'planning':
            return {k: airport_plan(self.database, self.state['flight'].get(k+'_icao', ''))
                    for k in ('departure', 'arrival')}
        if method == 'lookup':
            query = str(args.get('query', '')).strip().upper()[:80]
            kind = args.get('kind')
            with connect_readonly(self.database) as db:
                if kind == 'airline':
                    rows = db.execute('SELECT icao AS code,name FROM airlines WHERE icao LIKE ? OR iata LIKE ? OR name LIKE ? ORDER BY name LIMIT 60', (query+'%', query+'%', '%'+query+'%'))
                elif kind == 'airport':
                    rows = db.execute('SELECT icao AS code,name FROM airports WHERE icao IS NOT NULL AND (icao LIKE ? OR iata LIKE ? OR name LIKE ?) ORDER BY icao LIMIT 60', (query+'%', query+'%', '%'+query+'%'))
                else:
                    raise ValueError('Unknown lookup')
                return {'items': [dict(r) for r in rows]}
        if method == 'session':
            operation = args.get('operation')
            now = datetime.now(timezone.utc)
            candidate = deepcopy(self.value)
            state = candidate['state']
            current = state['active_session']
            if operation == 'start':
                if current:
                    raise ValueError('A flight session is already open')
                if not state['flight'].get('departure_icao') or not state['flight'].get('arrival_icao'):
                    raise ValueError('Choose departure and arrival first')
                state['active_session'] = {'id': uuid.uuid4().hex, 'flight': deepcopy(state['flight']),
                    'seconds': 0, 'started_at': now.isoformat()}
            elif operation in ('pause', 'resume', 'finish'):
                if not current:
                    raise ValueError('No flight session started')
                current['seconds'] = elapsed_seconds(current, now)
                current.pop('started_at', None)
                if operation == 'resume':
                    current['started_at'] = now.isoformat()
                elif operation == 'finish':
                    current['completed_at'] = now.isoformat()
                    state['flight_log'] = [current, *state['flight_log']][:500]
                    state['active_session'] = {}
            else:
                raise ValueError('Unknown flight session operation')
            self.commit(self.validate_backup(candidate))
            return {'value': deepcopy(self.value), 'render': self.render()}
        if method == 'map_route':
            endpoints = []
            for key in ('departure_icao', 'arrival_icao'):
                code = self.state['flight'].get(key, '').upper().strip()
                coordinates = airport_coordinates(str(self.database), code)
                endpoints.append({'code': code, 'coordinates': coordinates})
            origin, destination = [v['coordinates'] for v in endpoints]
            return {'airports': endpoints, 'route': great_circle(origin, destination) if origin and destination else []}
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
            from app_version import VERSION
            try:
                return {'text': export_backup(self.value, platform='android', version=VERSION)}
            except (ValueError, TypeError, KeyError) as error:
                raise localise_error(error, self.state['language']) from error
        elif method == 'import_preview':
            parsed = parse_backup(args.get('files', args.get('text')), self.state['language'])
            return {key: parsed[key] for key in ('summary', 'source')}
        elif method == 'import':
            self.apply_import(args['text'], args.get('mode', 'replace'))
            self.query, self.rows = None, []
            return {'value': deepcopy(self.value), 'metadata': self.metadata(), 'render': self.render()}
        elif method == 'import_pc':
            self.apply_import(args.get('files', {}), args.get('mode', 'replace'))
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
            previous = next((v for v in saved if v.get('id') == ident), None)
            if previous:
                item = {**deepcopy(previous), **item}
                for key in ('pilot_name', 'message_type', 'preview_edits', 'presentation'):
                    if key in previous:
                        item[key] = deepcopy(self.state[key])
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
            if method == 'load_flight':
                for key in ('pilot_name', 'message_type', 'preview_edits'):
                    if key in item:
                        candidate['state'][key] = deepcopy(item[key])
                if 'presentation' in item:
                    candidate['state']['presentation'] = {**DEFAULT_PRESENTATION, **deepcopy(item['presentation'])}
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
            candidate['state']['design_draft'] = {}
            candidate['state']['preview_edits'] = {}
            self.commit(candidate)
        elif method == 'library':
            category, operation, ident = args.get('category'), args.get('operation'), args.get('id')
            if category not in ('flights', 'presets', 'pilots', 'designs', 'history') or operation not in ('rename', 'delete', 'clear', 'edit', 'create'):
                raise ValueError('Invalid library operation')
            candidate = deepcopy(self.value)
            label = str(args.get('label', '')).strip()
            if operation == 'rename' and (not label or len(label) > 500):
                raise ValueError('A name of 1 to 500 characters is required')
            if category == 'flights' and operation in ('rename', 'delete'):
                saved = candidate['state']['saved_flights']
                record = next((v for v in saved if v['id'] == ident), None)
                if record is None:
                    raise ValueError('Saved flight no longer exists')
                if operation == 'rename':
                    record['label'] = label
                else:
                    saved.remove(record)
                    if candidate['state']['current_flight_id'] == ident:
                        candidate['state']['current_flight_id'] = ''
            elif category in ('presets', 'designs') and operation in ('rename', 'delete'):
                collection = candidate[category]
                if ident not in collection:
                    raise ValueError('Item no longer exists')
                if operation == 'rename' and category == 'presets':
                    if label != ident and label in collection:
                        raise ValueError('A favourite already has that name')
                    collection[label] = collection.pop(ident)
                elif operation == 'rename':
                    collection[ident]['name'] = label
                else:
                    del collection[ident]
                    if category == 'designs' and candidate['state']['presentation'].get('custom_id') == ident:
                        candidate['state']['presentation']['custom_id'] = ''
                        candidate['state']['preview_edits'] = {}
            elif category == 'pilots' and operation in ('edit', 'delete', 'create'):
                pilots = candidate['state']['pilot_library']
                index = len(pilots) if operation == 'create' else int(ident)
                if index < 0 or index >= len(pilots) and operation != 'create':
                    raise ValueError('Pilot no longer exists')
                if operation == 'delete':
                    pilots.pop(index)
                else:
                    record = deepcopy(args.get('pilot'))
                    if not isinstance(record, dict) or not isinstance(record.get('name'), str) or not record['name'].strip():
                        raise ValueError('Pilot name required')
                    record['name'] = record['name'].strip()
                    if any(i != index and v['name'].casefold() == record['name'].casefold() for i, v in enumerate(pilots)):
                        raise ValueError('A known pilot already has that name')
                    if operation == 'create':
                        pilots.append(record)
                    else:
                        pilots[index] = record
            elif category == 'history' and operation == 'clear':
                candidate['history'] = []
            else:
                raise ValueError('Unsupported library operation')
            self.commit(self.validate_backup(candidate))
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
        return json.dumps({'ok': False, 'error': tr(str(error))}, ensure_ascii=False)
