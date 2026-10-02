"""Script applying surgical performance optimizations to RFS ATC Message Maker."""
from pathlib import Path

# --- 1. Optimize finder/search.py (candidate limit) ---
search_file = Path('finder/search.py')
text = search_file.read_text(encoding='utf-8')

# Dynamically size candidates: 1500 candidates is more than enough for top-30 results,
# instead of fetching 20,001 rows across 4 joins and sorting 20,000 dicts!
old_search_sql = '                      " ORDER BY n_obs DESC,last_seen DESC,pattern_id ASC LIMIT 20001", params)]'
new_search_sql = '''                      f" ORDER BY n_obs DESC,last_seen DESC,pattern_id ASC LIMIT {min(20001, max(1200, (criteria.offset + criteria.limit) * 10))}", params)]'''

if old_search_sql in text:
    text = text.replace(old_search_sql, new_search_sql)
    search_file.write_text(text, encoding='utf-8')
    print('finder/search.py optimized!')
else:
    print('finder/search.py already updated or target not found.')

# --- 2. Optimize finder/ui.py (caching) ---
ui_file = Path('finder/ui.py')
text = ui_file.read_text(encoding='utf-8')

if '_build_timezone_labels' not in text:
    top_target = 'from dataclasses import replace\n\n\nclass SearchWorker'
    top_replace = '''from dataclasses import replace
from functools import lru_cache


@lru_cache(maxsize=4)
def _build_timezone_labels(language: str) -> dict[str, str]:
    from importlib.resources import files
    countries_by_zone = {}
    for line in files('tzdata.zoneinfo').joinpath('zone.tab').read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            columns = line.split('\t')
            countries_by_zone[columns[2]] = columns[0]
    country_names = {code: (fr if language == 'fr' else en) for code, fr, en in country_rows()}
    timezones = {}
    for zone in sorted(available_timezones()):
        countries = countries_by_zone.get(zone, '').split(',')
        country_name = ', '.join(country_names.get(code, code) for code in countries if code)
        label = f"{zone.rsplit('/', 1)[-1].replace('_', ' ')} — {country_name} ({zone})"
        timezones[label] = zone
    return timezones


_SUGGESTIONS_CACHE: dict[str, tuple[dict, dict]] = {}


class SearchWorker'''
    text = text.replace(top_target, top_replace)

if 'self._runway_cache = {}' not in text:
    text = text.replace('        self.worker = None\n        self.results = []',
                        '        self.worker = None\n        self.results = []\n        self._runway_cache = {}')

old_tz = '''        self.timezones = {}
        local_zone = bytes(QTimeZone.systemTimeZoneId()).decode()
        if local_zone not in available_timezones():
            local_zone = 'UTC'
        from importlib.resources import files
        countries_by_zone = {}
        for line in files('tzdata.zoneinfo').joinpath('zone.tab').read_text(encoding='utf-8').splitlines():
            if line and not line.startswith('#'):
                columns = line.split('\t')
                countries_by_zone[columns[2]] = columns[0]
        country_names = {code:(fr if self.language == 'fr' else en) for code,fr,en in country_rows()}
        for zone in sorted(available_timezones()):
            countries = countries_by_zone.get(zone, '').split(',')
            country_name = ', '.join(country_names.get(code, code) for code in countries if code)
            label = f"{zone.rsplit('/', 1)[-1].replace('_', ' ')} — {country_name} ({zone})"
            self.timezones[label] = zone'''
new_tz = '''        local_zone = bytes(QTimeZone.systemTimeZoneId()).decode()
        if local_zone not in available_timezones():
            local_zone = 'UTC'
        self.timezones = _build_timezone_labels(self.language)'''
if old_tz in text:
    text = text.replace(old_tz, new_tz)

old_sugg = '''    def load_suggestions(self):
        self.airport_labels = {}
        self.airline_labels = {}
        try:
            with connect_readonly(self.path) as db:
                for row in db.execute('SELECT icao, iata, name FROM airports ORDER BY icao'):
                    label = f"{row['icao']} / {row['iata'] or ''} — {row['name']}"
                    self.airport_labels[label] = row['icao']
                for row in db.execute('SELECT icao, iata, name FROM airlines ORDER BY name'):
                    label = f"{row['name']} ({row['icao']} / {row['iata'] or ''})"
                    self.airline_labels[label] = row['icao']
            for key in ('origin', 'destination', 'excluded_airports'):
                self.add_completer(self.fields[key], list(self.airport_labels))
            self.add_completer(self.fields['airline'], list(self.airline_labels))
        except (ValueError, OSError, sqlite3.Error):
            pass'''
new_sugg = '''    def load_suggestions(self):
        cache_key = str(self.path)
        if cache_key in _SUGGESTIONS_CACHE:
            self.airport_labels, self.airline_labels = _SUGGESTIONS_CACHE[cache_key]
        else:
            self.airport_labels = {}
            self.airline_labels = {}
            try:
                with connect_readonly(self.path) as db:
                    for row in db.execute('SELECT icao, iata, name FROM airports ORDER BY icao'):
                        label = f"{row['icao']} / {row['iata'] or ''} — {row['name']}"
                        self.airport_labels[label] = row['icao']
                    for row in db.execute('SELECT icao, iata, name FROM airlines ORDER BY name'):
                        label = f"{row['name']} ({row['icao']} / {row['iata'] or ''})"
                        self.airline_labels[label] = row['icao']
                _SUGGESTIONS_CACHE[cache_key] = (self.airport_labels, self.airline_labels)
            except (ValueError, OSError, sqlite3.Error):
                pass
        for key in ('origin', 'destination', 'excluded_airports'):
            self.add_completer(self.fields[key], list(self.airport_labels))
        self.add_completer(self.fields['airline'], list(self.airline_labels))'''
if old_sugg in text:
    text = text.replace(old_sugg, new_sugg)

old_runways = '''        lines += ["", self.t("runways")]
        try:
            with connect_readonly(self.path) as db:
                for key in ("origin", "destination"):
                    runways = db.execute("SELECT le_ident,he_ident,length_ft,surface FROM runways WHERE airport_id=? AND closed=0 ORDER BY le_ident", (row[key + "_id"],)).fetchall()
                    lines.append(row[key] + ": " + (", ".join(f"{r[0]}/{r[1]} ({r[2] or '?'} ft, {r[3] or '?'})" for r in runways) or self.t("unknown")))
        except Exception as error:
            lines.append(str(error))'''
new_runways = '''        lines += ["", self.t("runways")]
        try:
            for key in ("origin", "destination"):
                airport_id = row[key + "_id"]
                if airport_id not in self._runway_cache:
                    with connect_readonly(self.path) as db:
                        runways = db.execute("SELECT le_ident,he_ident,length_ft,surface FROM runways WHERE airport_id=? AND closed=0 ORDER BY le_ident", (airport_id,)).fetchall()
                        self._runway_cache[airport_id] = (", ".join(f"{r[0]}/{r[1]} ({r[2] or '?'} ft, {r[3] or '?'})" for r in runways) or self.t("unknown"))
                lines.append(row[key] + ": " + self._runway_cache[airport_id])
        except Exception as error:
            lines.append(str(error))'''
if old_runways in text:
    text = text.replace(old_runways, new_runways)

ui_file.write_text(text, encoding='utf-8')
print('finder/ui.py optimized!')

# --- 3. Optimize app_icon.py (cache icon) ---
icon_file = Path('app_icon.py')
text = icon_file.read_text(encoding='utf-8')
if 'from functools import lru_cache' not in text:
    text = 'from functools import lru_cache\n' + text
    text = text.replace('def make_icon() -> QIcon:', '@lru_cache(maxsize=1)\ndef make_icon() -> QIcon:')
    icon_file.write_text(text, encoding='utf-8')
    print('app_icon.py optimized!')

# --- 4. Optimize ui.py (selective polish and lazy dialog imports) ---
main_ui_file = Path('ui.py')
text = main_ui_file.read_text(encoding='utf-8')

# Only unpolish/polish when invalid state actually changes!
old_polish = '''        for form, widgets in ((self.flight_form, self.flight_widgets), (self.message_form, self.type_widgets)):
            for key, widget in widgets.items():
                errors = [p.text for p in problems if p.field == key]
                widget.setProperty('invalid', bool(errors))
                widget.setAccessibleDescription(' • '.join(errors))
                widget.style().unpolish(widget)
                widget.style().polish(widget)'''
new_polish = '''        for form, widgets in ((self.flight_form, self.flight_widgets), (self.message_form, self.type_widgets)):
            for key, widget in widgets.items():
                errors = [p.text for p in problems if p.field == key]
                is_invalid = bool(errors)
                widget.setAccessibleDescription(' • '.join(errors))
                if widget.property('invalid') != is_invalid:
                    widget.setProperty('invalid', is_invalid)
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)'''
if old_polish in text:
    text = text.replace(old_polish, new_polish)
    print('ui.py polish loop optimized!')

main_ui_file.write_text(text, encoding='utf-8')
print('All optimizations applied successfully!')
