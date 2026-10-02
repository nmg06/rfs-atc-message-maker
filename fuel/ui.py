from i18n import tr, set_language, language
"""Fuel calculator view; explicit variant selection and explicit current-flight update."""
from copy import deepcopy
import re
from PySide6.QtCore import Qt, Signal, QEvent, QTimer, QObject
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QCompleter, QPlainTextEdit
from .calculator import calculate_fuel, find_aircraft, load_json, DISCLAIMER
COMPONENTS = (('taxi_out_kg', 'Taxi départ · 6 min × 1,4'), ('trip_kg', 'Trajet'), ('contingency_kg', 'Contingence · 5 % du trajet'), ('alternate_kg', 'Alternate · distance / 450 kt + 15 min'), ('final_reserve_kg', 'Réserve finale · 30 min'), ('taxi_in_kg', 'Taxi arrivée · 4 min × 1,4'))

def duration_hours(text):
    text = str(text or '').strip().lower()
    match = re.fullmatch('(\\d+)\\s*(?:h|:)\\s*(\\d{1,2})\\s*m?', text)
    if match:
        hours, minutes = map(int, match.groups())
        return hours + minutes / 60 if minutes < 60 else None
    try:
        return float(text.rstrip('h').replace(',', '.')) if text else None
    except ValueError:
        return None

class AircraftComboFilter(QObject):
    """Shows the full list of aircraft immediately when clicking or focusing the field."""
    def __init__(self, combo):
        super().__init__(combo)
        self.combo = combo

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.FocusIn):
            if self.combo.currentIndex() == 0:
                self.combo.lineEdit().selectAll()
            QTimer.singleShot(0, self.combo.showPopup)
        return False

class FuelDialog(QDialog):
    selected = Signal(dict)

    def __init__(self, flight, parent=None):
        super().__init__(parent)
        from ux import install_wheel_guard
        install_wheel_guard()
        self.setWindowTitle(tr('RFS Fuel Helper'))
        self.resize(790, 820)
        self.result = None
        self.aircraft_data = load_json('aircraft_fuel_data.json')
        self.alternate_data = load_json('airport_alternates.json')
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(tr('RFS FUEL HELPER'), objectName='title'))
        disclaimer = QLabel(tr(DISCLAIMER), objectName='danger')
        disclaimer.setWordWrap(True)
        outer.addWidget(disclaimer)
        advice = QLabel(tr('Consigne du bot : prévoyez 20 à 30 minutes de plus que le planificateur RFS.\nCe supplément n’est PAS ajouté automatiquement. Choisissez la variante exacte de l’avion.'))
        advice.setWordWrap(True)
        outer.addWidget(advice)
        form = QFormLayout()
        self.aircraft = QComboBox()
        self.aircraft.setEditable(True)
        self.aircraft.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.aircraft.addItem(tr('Choisir un avion / variante…'), None)
        self.labels = {}
        for record in self.aircraft_data['aircraft']:
            label = record['name']
            self.labels[label] = record['id']
            self.aircraft.addItem(label, record['id'])
        completer = QCompleter(list(self.labels), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.aircraft.setCompleter(completer)
        self.aircraft.lineEdit().setPlaceholderText(tr('Tapez ou cliquez pour chercher un avion…'))
        self._aircraft_filter = AircraftComboFilter(self.aircraft)
        self.aircraft.lineEdit().installEventFilter(self._aircraft_filter)
        self.aircraft.lineEdit().returnPressed.connect(lambda: self.aircraft.showPopup())
        provenance = flight.get('selected_flight', {}).get('fields', {}).get('aircraft', '')
        observed = bool(flight.get('selected_flight')) and provenance not in ('USER_INPUT', 'USER_INPUT_FUEL_VARIANT')
        current = None if observed else find_aircraft(flight.get('fuel_aircraft_id') or flight.get('aircraft', ''), self.aircraft_data['aircraft'])
        if current:
            self.aircraft.setCurrentIndex(self.aircraft.findData(current['id']))
        self.hours = QLineEdit()
        initial = duration_hours(flight.get('estimated_flight_time', ''))
        if initial is not None:
            self.hours.setText(str(initial))
        self.hours.setPlaceholderText(tr('5  ou  5:30  ou  5h30'))
        self.arrival = QLineEdit(str(flight.get('arrival_icao', '')))
        self.arrival.setPlaceholderText(tr('Facultatif, ex. EGLL'))
        form.addRow(tr('Avion / variante'), self.aircraft)
        form.addRow(tr('Durée prévue (heures ou HH:MM)'), self.hours)
        form.addRow(tr('ICAO arrivée'), self.arrival)
        outer.addLayout(form)
        self.calculate_button = QPushButton(tr('Calculer le carburant'), objectName='primary')
        self.calculate_button.clicked.connect(self.calculate)
        outer.addWidget(self.calculate_button)
        self.table = QTableWidget(7, 2)
        self.table.setHorizontalHeaderLabels([tr('Composant'), tr('Carburant')])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, (_, label) in enumerate(COMPONENTS):
            self.table.setItem(row, 0, QTableWidgetItem(tr(label)))
        self.table.setItem(6, 0, QTableWidgetItem(tr('TOTAL BLOC')))
        self.table.setMinimumHeight(285)
        outer.addWidget(self.table)
        self.status = QLabel(tr('Sélectionnez un avion puis calculez. Aucun carburant ne sera appliqué automatiquement.'))
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.provenance = QPlainTextEdit()
        self.provenance.setReadOnly(True)
        self.provenance.setPlaceholderText(tr('Consommation, confiance, provenance et dégagement retenu…'))
        outer.addWidget(self.provenance, 1)
        actions = QHBoxLayout()
        self.apply_button = QPushButton(tr('Appliquer avion + carburant au vol'), objectName='copy')
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.use_result)
        close = QPushButton(tr('Fermer'))
        close.clicked.connect(self.reject)
        actions.addWidget(self.apply_button)
        actions.addWidget(close)
        outer.addLayout(actions)
        self.aircraft.currentTextChanged.connect(self.invalidate)
        self.hours.textChanged.connect(self.invalidate)
        self.arrival.textChanged.connect(self.invalidate)

    def invalidate(self, *_):
        self.result = None
        self.apply_button.setEnabled(False)
        for row in range(7):
            self.table.setItem(row, 1, QTableWidgetItem('—'))
        self.provenance.clear()
        self.status.setText(tr('Valeurs modifiées : recalculez pour appliquer le résultat.'))

    def calculate(self):
        self.result = None
        self.apply_button.setEnabled(False)
        try:
            label = self.aircraft.currentText().strip()
            identifier = self.labels.get(label)
            if identifier is None:
                raise ValueError('Choisissez explicitement une variante dans les propositions de la liste.')
            hours = duration_hours(self.hours.text())
            if hours is None:
                raise ValueError('Durée invalide : utilisez 5, 5:30 ou 5h30, par exemple.')
            result = calculate_fuel(identifier, hours, self.arrival.text(), aircraft_data=self.aircraft_data, alternate_data=self.alternate_data)
        except (ValueError, LookupError) as error:
            self.status.setText(tr(str(error)))
            return
        self.result = result
        for row, (key, _) in enumerate(COMPONENTS):
            item = QTableWidgetItem(result['display'][key])
            item.setToolTip(repr(result['components_exact'][key]) + tr(' kg — valeur non arrondie'))
            self.table.setItem(row, 1, item)
        total = QTableWidgetItem(result['display']['total_block_fuel'])
        font = total.font()
        font.setBold(True)
        total.setFont(font)
        total.setToolTip(repr(result['total_block_fuel_kg_exact']) + tr(' kg — valeur non arrondie'))
        self.table.setItem(6, 1, total)
        status = tr(result['alternate_explanation'])
        if result['exceeds_endurance']:
            status += '\n' + tr('Endurance maximale dépassée ({value}). Escale ravitaillement nécessaire. Le total reste inchangé.', value=result['max_endurance'])
        self.status.setText(status)
        record = result['provenance']['aircraft_record']
        lines = [result['aircraft']['name'],
                 tr('Consommation : {value} kg/h', value=f"{result['burn_rate_kg_h']:g}"),
                 tr('Confiance : {value}', value=tr(record.get('burn_confidence', 'Inconnue'))),
                 tr('Note : {value}', value=tr(record.get('burn_note') or 'Aucune note spécifique.')),
                 tr('Endurance : {value}', value=result['max_endurance'] or tr('Inconnue'))]
        if result['alternate']:
            alternate = result['alternate']
            lines += [tr('Dégagement retenu : {code} — {distance} NM', code=alternate['icao'], distance=f"{alternate['distance_nm']:g}"),
                      tr('Provenance dégagement : {value}', value=tr(str((result['provenance']['alternate_record'] or {}).get('provenance', 'Inconnue'))))]
        else:
            lines.append(tr(result['alternate_explanation']))
        lines += ['', tr(str(result['provenance']['catalogue_source'] or '')),
                  tr(str(result['provenance']['alternate_warning'] or '')),
                  tr('Les suggestions statiques ne vérifient pas la météo, les NOTAM, les pistes, la masse ni les performances.')]
        self.provenance.setPlainText('\n'.join(lines))
        self.apply_button.setEnabled(True)

    def use_result(self):
        if self.result:
            self.selected.emit(deepcopy(self.result))
            self.accept()
