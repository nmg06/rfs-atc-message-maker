"""Optional local Finder dialog. Search runs off the GUI thread."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from PySide6.QtCore import QDate, QThread, Signal, Qt, QTimeZone, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFormLayout, QLineEdit, QCheckBox, QDateEdit, QSplitter, QScrollArea, QWidget, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QPlainTextEdit, QFileDialog, QGroupBox, QCompleter)

from .database import connect_readonly
from .i18n import tr, error_text
from .search import Criteria, search, SearchSession, parse_airport_codes
from .duration import parse_minutes, parse_finder_hours
from .rfs_catalogue import records, TYPE_BY_ID
from .provenance import duration_provenance
from country_search import country_rows, resolve_country
from ux import install_wheel_guard, smooth_scroll
from zoneinfo import available_timezones
from i18n import language as app_language
from dataclasses import replace
from functools import lru_cache


@lru_cache(maxsize=4)
def _build_timezone_labels(language: str) -> dict[str, str]:
    from importlib.resources import files
    countries_by_zone = {}
    for line in files('tzdata.zoneinfo').joinpath('zone.tab').read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            columns = line.split('	')
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


class SearchWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, path, criteria, parent, now=None, session=None):
        super().__init__(parent)
        install_wheel_guard()
        self.revision = 0
        self.search_revision = 0
        self.query = None
        self.response = None
        self.path, self.criteria = path, criteria
        self.now = now or datetime.now(timezone.utc)
        self.session = session

    def run(self):
        try:
            self.done.emit(self.session.page(self.path, self.criteria, self.now) if self.session else search(self.path, self.criteria, self.now))
        except Exception as error:
            self.failed.emit(str(error))


class FinderDialog(QDialog):
    selected = Signal(dict)

    def __init__(self, parent, database: Path, language=None):
        super().__init__(parent)
        install_wheel_guard()
        self.revision = 0
        self.search_revision = 0
        self.query = None
        self.response = None
        language = language if language in ('fr', 'en') else app_language()
        self.path, self.language = Path(database), language
        self.worker = None
        self._profile_store = getattr(parent, 'store', None)
        self._restoring = False
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.setInterval(250)
        self._persist_timer.timeout.connect(self.persist_filters)
        self.finished.connect(self.persist_filters)
        self.results = []
        self.session = SearchSession()
        self.visible_count = 0
        self._runway_cache = {}
        self.sources = []
        self.setWindowTitle("Flight Finder")
        self.resize(1200, 820)
        self.setMinimumSize(920, 620)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(20, 18, 20, 18)
        self.outer.setSpacing(12)
        top = QHBoxLayout()
        self.lang = QComboBox()
        for name, code in (("Français", "fr"), ("English", "en")):
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(language)))
        self.lang.currentIndexChanged.connect(self.change_language)
        self.lang.hide() # Global application preference; retained for API compatibility.
        self.database_button = QPushButton()
        self.database_button.clicked.connect(self.choose_database)

        top.addWidget(QLabel('Flight Finder', objectName='title'))
        top.addStretch()
        from help_dialog import FlightdeckHelpDialog
        from i18n import tr as app_tr
        self.help_button = QPushButton(app_tr('Comprendre cet écran'))
        self.help_button.clicked.connect(lambda: FlightdeckHelpDialog(self, 'finder').exec())
        top.addWidget(self.help_button)
        self.outer.addLayout(top)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.outer.addWidget(self.hint)
        split = QSplitter()
        split.setChildrenCollapsible(False)
        split.setHandleWidth(16)
        self.outer.addWidget(split, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget(objectName="formBody")
        body_layout = QVBoxLayout(body)
        body_layout.setSpacing(20)
        common = QGroupBox(self.t('common'))
        self.form = QFormLayout(common)
        self.form.setContentsMargins(8, 10, 8, 12)
        self.form.setSpacing(10)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        body_layout.addWidget(common)
        self.advanced_toggle = QCheckBox(self.t('advanced'))
        body_layout.addWidget(self.advanced_toggle)
        self.advanced_body = QWidget()
        advanced = QFormLayout(self.advanced_body)
        advanced.setSpacing(12)
        advanced.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        body_layout.addWidget(self.advanced_body)
        self.advanced_body.hide()
        self.advanced_toggle.toggled.connect(self.advanced_body.setVisible)
        self.time_toggle = QCheckBox(self.t('time_options'))
        body_layout.addWidget(self.time_toggle)
        self.time_body = QWidget()
        times = QFormLayout(self.time_body)
        times.setSpacing(12)
        times.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        time_hint = QLabel(self.t('time_hint'))
        time_hint.setWordWrap(True)
        times.addRow(time_hint)
        body_layout.addWidget(self.time_body)
        self.time_body.hide()
        self.time_toggle.toggled.connect(self.time_body.setVisible)
        advanced.addRow(self.database_button)
        base_hint = QLabel(self.t('base_hint'))
        base_hint.setWordWrap(True)
        advanced.addRow(base_hint)
        duration_hint = QLabel(self.t('duration_hint'))
        duration_hint.setWordWrap(True)
        self.form.addRow(duration_hint)
        self.rfs_only = QCheckBox(self.t('rfs_only'))
        self.rfs_only.setChecked(True)
        self.form.addRow(self.rfs_only)
        self.rfs_labels = {r['name']:r['id'] for r in records()}
        self.timezones = {}
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
            self.timezones[label] = zone
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.fields, self.labels = {}, {}
        self.list_keys = ("origin", "destination", "excluded_airports", "origin_country", "destination_country",
                          "origin_continent", "destination_continent", "origin_region", "destination_region")
        keys = ("airline", "aircraft", "manufacturer", "family", "origin", "destination", "excluded_airports", "min_minutes",
                "max_minutes", "target_minutes", "origin_country", "destination_country",
                "origin_continent", "destination_continent", "origin_region", "destination_region",
                "departure_time", "departure_date", "departure_tz", "arrival_time", "arrival_date", "arrival_tz", "time_tolerance")
        for key in keys:
            label = QLabel()
            label.setWordWrap(True)
            label.setMinimumWidth(280)
            if key.endswith("_date"):
                field = QDateEdit(QDate.currentDate())
                field.setCalendarPopup(True)
                field.setDisplayFormat("yyyy-MM-dd")
            else:
                field = QLineEdit()
                if key.endswith('_tz'):
                    field = QComboBox()
                    field.setEditable(True)
                    field.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                    for zone_label, zone in self.timezones.items():
                        field.addItem(zone_label, zone)
                    field.setCurrentIndex(field.findData(local_zone))
                    field.completer().setFilterMode(Qt.MatchFlag.MatchContains)
                    field.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                elif key == "time_tolerance":
                    field.setText("60")
            self.labels[key], self.fields[key] = label, field
            target_form = times if key.startswith(('departure_', 'arrival_')) or key == 'time_tolerance' else (
                self.form if key in ('airline', 'aircraft', 'origin', 'destination', 'excluded_airports', 'min_minutes', 'max_minutes', 'target_minutes') else advanced)
            target_form.addRow(label, field)
            if key.endswith('_minutes'):
                field.setPlaceholderText('10 = 10h · 9h30 · 03:00 · 60 min')
            if key.endswith('_time'):
                field.setPlaceholderText('07:00')
            if key == 'aircraft':
                self.add_completer(field, list(self.rfs_labels))
            if key.endswith('_country'):
                self.add_completer(field, [f'{fr} / {en} ({code})' for code, fr, en in country_rows()])
            if key == 'airline':
                field.setToolTip(self.t('airline_hint'))
            if key == 'excluded_airports':
                field.setPlaceholderText('VABB, EGLL LFPG')
                self.excluded_hint = QLabel(self.t('excluded_hint'))
                self.excluded_hint.setWordWrap(True)
                self.form.addRow(self.excluded_hint)
        self.international, self.real = QCheckBox(), QCheckBox()
        self.real.setChecked(True)
        self.real.setEnabled(False)
        advanced.addRow(self.international)
        advanced.addRow(self.real)
        self.diversify = QCheckBox(self.t('diversify'))
        self.diversify.setChecked(True)
        advanced.addRow(self.diversify)
        body_layout.addStretch()
        smooth_scroll(scroll)
        scroll.setWidget(body)
        split.addWidget(scroll)
        right = QWidget()
        layout = QVBoxLayout(right)
        self.empty_state = QLabel(self.t('start_hint'), objectName='emptyState')
        self.empty_state.setWordWrap(True)
        layout.addWidget(self.empty_state)
        self.table = QTableWidget(0, 5)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.show_result)
        smooth_scroll(self.table)
        layout.addWidget(self.table, 1)
        self.details = QPlainTextEdit(objectName="discordPreview")
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 0)
        self.details.setMinimumHeight(170)
        self.details.setMaximumHeight(235)
        split.addWidget(right)
        split.setSizes([420, 740])
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.outer.addWidget(self.status)
        actions = QHBoxLayout()
        self.search_button = QPushButton(objectName="primary")
        self.search_button.clicked.connect(self.run_search)
        self.use_button = QPushButton(objectName="copy")
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self.use_flight)
        self.more_button = QPushButton(self.t('more'))
        self.more_button.setEnabled(False)
        self.more_button.clicked.connect(lambda: self.run_search(more=True))
        self.less_button = QPushButton('Voir moins' if language == 'fr' else 'Show less')
        self.less_button.setEnabled(False)
        self.less_button.clicked.connect(self.show_less)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.reject)
        for button in (self.search_button, self.less_button, self.more_button, self.use_button, self.close_button):
            actions.addWidget(button)
        self.outer.addLayout(actions)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.search_button.setDefault(True)
        for field in self.fields.values():
            if isinstance(field, QDateEdit):
                field.dateChanged.connect(self.invalidate)
            elif isinstance(field, QComboBox):
                field.currentTextChanged.connect(self.invalidate)
            else:
                field.textChanged.connect(self.invalidate)
        for check in (self.international, self.rfs_only, self.diversify):
            check.toggled.connect(self.invalidate)
        self.load_suggestions()
        self.restore_filters()
        self.translate()
        self.status.setText(self.t("optional") if self.path.is_file() else self.t("missing"))

    def t(self, key):
        return tr(key, self.language)

    def translate(self):
        self.less_button.setText('Voir moins' if self.language == 'fr' else 'Show less')
        self.database_button.setText(self.t("database"))
        self.search_button.setText(self.t("search"))
        self.use_button.setText(self.t("use"))
        self.close_button.setText(self.t("close"))
        self.hint.setText(self.t("optional"))
        self.international.setText(self.t("international"))
        self.real.setText(self.t("real"))
        for key, label in self.labels.items():
            label.setText(self.t(key))
        self.table.setHorizontalHeaderLabels(self.t("columns"))
        self.details.setPlaceholderText(self.t("details"))
        self.excluded_hint.setText(self.t('excluded_hint'))

    def restore_filters(self):
        if self._profile_store is None:
            return
        saved = self._profile_store.state.get('finder_filters', {})
        if not isinstance(saved, dict):
            return
        self._restoring = True
        try:
            for key, widget in self.fields.items():
                if key not in saved:
                    continue
                value = saved[key]
                if isinstance(widget, QDateEdit):
                    date = QDate.currentDate().addDays(1 if value == 'tomorrow' else 0) if value in ('today', 'tomorrow') else QDate.fromString(str(value), 'yyyy-MM-dd')
                    if date.isValid():
                        widget.setDate(date)
                elif isinstance(widget, QComboBox):
                    index = widget.findData(value)
                    widget.setCurrentIndex(index) if index >= 0 else widget.setCurrentText(str(value))
                else:
                    widget.setText(', '.join(value) if isinstance(value, list) else str(value))
            for key, widget in (('international_only', self.international), ('rfs_only', self.rfs_only), ('diversify', self.diversify)):
                if type(saved.get(key)) is bool:
                    widget.setChecked(saved[key])
        finally:
            self._restoring = False

    def persist_filters(self, *_):
        if self._profile_store is None or self._restoring:
            return
        self._persist_timer.stop()
        values = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QDateEdit):
                value = widget.date().toString('yyyy-MM-dd')
            elif isinstance(widget, QComboBox):
                value = self.timezones.get(widget.currentText(), widget.currentText())
            else:
                value = widget.text()
            values[key] = value
        values.update(international_only=self.international.isChecked(), rfs_only=self.rfs_only.isChecked(), diversify=self.diversify.isChecked())
        self._profile_store.state['finder_filters'] = values
        try:
            self._profile_store.save_state()
        except OSError:
            self.status.setText('Impossible de sauvegarder les filtres.' if self.language == 'fr' else 'Could not save the filters.')

    def change_language(self):
        self.language = self.lang.currentData()
        self.translate()
        self.show_result()

    def choose_database(self):
        name, _ = QFileDialog.getOpenFileName(self, self.t("database"), str(self.path.parent), "SQLite (*.sqlite *.db)")
        if not name:
            return
        try:
            with connect_readonly(Path(name)) as db:
                db.execute("SELECT * FROM v_pattern_search LIMIT 0")
                db.execute("SELECT * FROM sources LIMIT 0")
            self.path = Path(name)
            self.invalidate()
            self.load_suggestions()
            self.status.setText(name)
        except Exception as error:
            self.fail(str(error))

    def add_completer(self, field, items):
        completer = QCompleter(items, field)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        field.setCompleter(completer)

    def load_suggestions(self):
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
        self.add_completer(self.fields['airline'], list(self.airline_labels))

    def invalidate(self, *_):
        if not self._restoring:
            self._persist_timer.start()
        self.revision += 1
        self.results = []
        self.visible_count = 0
        self.session.clear()
        self.less_button.setEnabled(False)
        self.response = None
        self.empty_state.setText(self.t("changed"))
        self.empty_state.show()
        self.table.setRowCount(0)
        self.details.clear()
        self.use_button.setEnabled(False)
        self.more_button.setEnabled(False)
        self.status.setText(self.t('changed'))
        self.more_button.setText(self.t('more'))

    def criteria(self):
        values = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QDateEdit):
                values[key] = widget.date().toString('yyyy-MM-dd')
                continue
            text = (widget.currentText() if isinstance(widget, QComboBox) else widget.text()).strip()
            if key.endswith('_tz'):
                zone = self.timezones.get(text, text)
                if zone not in available_timezones():
                    raise ValueError('ZONE_UNKNOWN')
                values[key] = zone
            elif key in ('origin_country', 'destination_country'):
                values[key] = [resolve_country(v.strip()) for v in text.split(',') if v.strip()]
            elif key in ('origin', 'destination', 'excluded_airports'):
                resolved = self.airport_labels.get(text, text)
                try:
                    values[key] = parse_airport_codes(resolved, exclusion=key == 'excluded_airports')
                except ValueError:
                    widget.setFocus()
                    raise
            elif key in self.list_keys:
                values[key] = [self.airport_labels.get(text, text).upper()] if text in self.airport_labels else [v.strip().upper() for v in text.split(',') if v.strip()]
            elif key.endswith('_minutes') or key == 'time_tolerance':
                minutes = parse_finder_hours(text) if key in ('min_minutes', 'max_minutes', 'target_minutes') else parse_minutes(text)
                if minutes is not None:
                    values[key] = minutes
            elif key == 'airline':
                values[key] = self.airline_labels.get(text, text)
            elif key == 'aircraft' and text in self.rfs_labels:
                values['rfs_aircraft_id'] = self.rfs_labels[text]
            else:
                values[key] = text
        values['international_only'] = self.international.isChecked()
        values['rfs_only'] = self.rfs_only.isChecked()
        values['diversify'] = self.diversify.isChecked()
        return Criteria(**values)

    def run_search(self, checked=False, more=False):
        self.persist_filters()
        if self.worker and self.worker.isRunning():
            return
        if more and self.query is None:
            return
        if more and self.visible_count < len(self.results):
            self.show_cached_rows(min(len(self.results), self.visible_count + self.query.limit))
            return
        if not more:
            self.invalidate()
        try:
            criteria = replace(self.query, offset=len(self.results)) if more else self.criteria()
            criteria.validate()
        except ValueError as error:
            self.fail(str(error))
            return
        if not more:
            self.query = criteria
            self.query_time = datetime.now(timezone.utc)
        elif self.session.metadata is not None:
            self.search_revision = self.revision
            try:
                self.present(self.session.page(self.path, criteria, self.query_time))
            except (ValueError, OSError) as error:
                self.fail(str(error))
            return
        self.search_revision = self.revision
        self.use_button.setEnabled(False)
        self.more_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.database_button.setEnabled(False)
        self.empty_state.setText(self.t("busy"))
        self.empty_state.show()
        self.status.setText(self.t('busy'))
        if self.worker:
            self.worker.deleteLater()
        self.worker = SearchWorker(self.path, criteria, self, self.query_time, self.session)
        self.worker.done.connect(self.present)
        self.worker.failed.connect(self.fail)
        self.worker.finished.connect(self.search_finished)
        self.worker.start()

    def search_finished(self):
        self.search_button.setEnabled(True)
        self.database_button.setEnabled(True)
        if self.revision == self.search_revision and self.response:
            self.more_button.setEnabled(self.visible_count < len(self.results) or self.response.get('has_more', False))

    def fail(self, message):
        text = error_text(message, self.language)
        self.empty_state.setText(self.t("error") + ": " + text)
        self.empty_state.show()
        self.status.setText(self.t("error") + ": " + text)
        if str(message).split(':', 1)[0] in ('EXCLUDED_AIRPORT_FORMAT', 'EXCLUDED_AIRPORT_UNKNOWN'):
            self.fields['excluded_airports'].setFocus()

    def present(self, response):
        if self.revision != self.search_revision:
            return
        self.response = response
        appended = bool(response.get('offset'))
        first_new = len(self.results) if appended else 0
        self.results = self.results + response['results'] if appended else response['results']
        self.sources = response['sources']
        # Keep clicks disabled until the thread has fully finished; otherwise
        # run_search can silently discard a click between done and finished.
        self.more_button.setEnabled(response.get('has_more', False) and not (self.worker and self.worker.isRunning()))
        self.empty_state.setVisible(not self.results)
        self.empty_state.setText(self.t("no_match_hint"))
        self.table.setRowCount(len(self.results))
        for index in range(first_new, len(self.results)):
            row = self.results[index]
            minutes = round(row["duration_min"])
            origin = duration_provenance(row)
            label = self.t('duration_observed_short' if origin == 'AGGREGATED_COMPLETE_TRACKS'
                           else 'duration_estimated_short' if origin == 'ESTIMATED_DISTANCE_HEURISTIC'
                           else 'duration_unknown_short')
            values = (f"{row['airline_name']} / {row['callsign']}", f"{row['origin']} → {row['destination']}",
                      row.get("aircraft_display", row["aircraft"]), f"{minutes//60}h{minutes%60:02} · {label}", f"{row['score']:.1f}")
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(value))
        self.visible_count = len(self.results)
        for index in range(len(self.results)):
            self.table.setRowHidden(index, False)
        self.less_button.setEnabled(self.visible_count > self.query.limit)
        status = self.t("count").format(n=len(self.results), candidates=response["candidates"], matches=response["matches"], available=response["available"], dropped=response["diversity_dropped"],
                 last=response["build"].get("last_observation", self.t("unknown"))) if self.results else self.t("none")
        if not self.results:
            active = {k:v for k,v in vars(self.query).items() if v and k not in ('limit','offset','tolerance_minutes','time_tolerance','departure_date','arrival_date','departure_tz','arrival_tz','real_only','rfs_aircraft_id')}
            if self.query.rfs_aircraft_id:
                active['aircraft'] = next((r['name'] for r in records() if r['id'] == self.query.rfs_aircraft_id), self.fields['aircraft'].text())
            labels = []
            for key, value in active.items():
                if isinstance(value, bool):
                    labels.append(self.t(key))
                else:
                    value = ', '.join(value) if isinstance(value, list) else str(value)
                    labels.append(f'{self.t(key)} : {value}')
            status += '\n' + self.t('active_filters') + ': ' + ' ; '.join(labels)
        self.status.setText(status + "\n" + " ".join(self.t(w) for w in response["warnings"]))
        self.more_button.setText(self.t('more_count').format(shown=len(self.results), total=response['available']))
        if self.results:
            selected_row = min(first_new, len(self.results) - 1)
            self.table.selectRow(selected_row)
            self.table.scrollToItem(self.table.item(selected_row, 0), QAbstractItemView.ScrollHint.PositionAtTop)
        if appended and response['results']:
            self.status.setText(self.t('page_added').format(count=len(response['results']), start=first_new + 1, end=len(self.results)) + '\n' + self.status.text())

    def show_less(self):
        if self.query and self.visible_count > self.query.limit:
            self.show_cached_rows(max(self.query.limit, self.visible_count-self.query.limit))

    def show_cached_rows(self, count):
        self.visible_count = count
        for index in range(len(self.results)):
            self.table.setRowHidden(index, index >= count)
        self.less_button.setEnabled(count > self.query.limit)
        self.more_button.setEnabled(count < len(self.results) or bool(self.response and self.response.get('has_more')))
        if count:
            selected = max(0, count-self.query.limit)
            self.table.selectRow(selected)
            self.table.scrollToItem(self.table.item(selected,0),QAbstractItemView.ScrollHint.PositionAtTop)
        self.status.setText((f'{count} affichés / {len(self.results)} chargés' if self.language == 'fr' else f'{count} visible / {len(self.results)} loaded'))

    def show_result(self):
        index = self.table.currentRow()
        self.use_button.setEnabled(0 <= index < len(self.results))
        if not 0 <= index < len(self.results):
            self.details.clear()
            return
        row = self.results[index]
        origin = duration_provenance(row)
        observed = origin == 'AGGREGATED_COMPLETE_TRACKS'
        duration_label = ('duration_observed' if observed else 'duration_estimated'
                          if origin == 'ESTIMATED_DISTANCE_HEURISTIC' else 'duration_unverified')
        duration_line = f"{self.t(duration_label)}: {row['duration_min']:.0f} min"
        if observed and row.get('duration_p10') is not None and row.get('duration_p90') is not None:
            duration_line += f" (P10–P90: {row['duration_p10']:.0f}–{row['duration_p90']:.0f})"
        lines = [self.t("observed"), f"ICAO: {row['aircraft']}", f"{row['airline_name']} • {row['callsign']} • {row.get('aircraft_display') or row['aircraft_model'] or row['aircraft']}",
            f"{row['origin']} — {row['origin_name']} → {row['destination']} — {row['destination_name']}",
            duration_line,
            f"{self.t('distance')}: {row['distance_nm']:.0f} NM" if row['distance_nm'] is not None else self.t('unknown'),
            f"{row['n_obs']} {self.t('observations')} • {row['n_complete']} {self.t('coverage')}",
            f"{self.t('times')}: {row['latest_departure']} → {row['latest_arrival']}"]
        if origin == 'ESTIMATED_DISTANCE_HEURISTIC':
            lines += [self.t('duration_formula'), self.t('duration_formula_limits')]
        elif not observed:
            lines.append(self.t('DURATION_POST_IMPORT_UNVERIFIED'))
        if row.get("sim_departure_utc"):
            dep = datetime.fromisoformat(row["sim_departure_utc"])
            arr = datetime.fromisoformat(row["sim_arrival_utc"])
            lines += ["", self.t("simulation"), f"UTC: {dep.isoformat()} → {arr.isoformat()}"]
            if self.query:
                lines.append(self.t('your_arrival') + ': ' + arr.astimezone(ZoneInfo(self.query.arrival_tz)).isoformat() + ' (' + self.query.arrival_tz + ')')
            for instant, key in ((dep, "origin_tz"), (arr, "destination_tz")):
                if row.get(key):
                    lines.append(f"{row[key]}: {instant.astimezone(ZoneInfo(row[key])).isoformat()}")
        lines += ["", self.t("runways")]
        try:
            for key in ("origin", "destination"):
                airport_id = row[key + "_id"]
                if airport_id not in self._runway_cache:
                    with connect_readonly(self.path) as db:
                        runways = db.execute("SELECT le_ident,he_ident,length_ft,surface FROM runways WHERE airport_id=? AND closed=0 ORDER BY le_ident", (airport_id,)).fetchall()
                        self._runway_cache[airport_id] = (", ".join(f"{r[0]}/{r[1]} ({r[2] or '?'} ft, {r[3] or '?'})" for r in runways) or self.t("unknown"))
                lines.append(row[key] + ": " + self._runway_cache[airport_id])
        except Exception as error:
            lines.append(str(error))
        lines += ["", self.t("notice"), *[self.t(w) for w in row["warnings"]], "", self.t("provenance")]
        lines += [s["attribution_text"] + "\n" + s["url"] for s in self.sources]
        lines += ["", self.t("score_help"), self.t("rfs_notice"), "Score: " + ", ".join(f"{self.t(k)}={v*100:.0f}%" for k,v in row["subscores"].items())]
        self.details.setPlainText("\n".join(lines))

    def use_flight(self):
        index = self.table.currentRow()
        if 0 <= index < len(self.results):
            self.selected.emit(self.results[index])
            self.accept()

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.status.setText(self.t("busy"))
            return
        super().reject()
