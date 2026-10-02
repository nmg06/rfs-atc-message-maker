"""Interface Windows de RFS ATC Message Maker."""
from __future__ import annotations
from i18n import tr, set_language, language
from copy import deepcopy
from datetime import datetime
import uuid
import json
from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QMenu, QFileDialog, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
from rfs_schema import Field, FLAGS, FLIGHT_FIELDS, FLIGHT_FIELDS_BY_TYPE, FLIGHT_TYPES, MESSAGE_FIELDS, MESSAGE_TYPES, empty_flight, empty_per_type
from storage import LOGGER, Store
from templates import render
from validation import Issue, REQUIRED_FLIGHT, REQUIRED_MESSAGE, emoji_count, validate
from message_builder import compose, validate_group, DEFAULT_PRESENTATION, additional_pilots, BUILTIN_DESIGNS, EMOJI_STYLES, preview_text, clipboard_text
from appearance import apply_palette, extra_style, get_stylesheet, DARK_STYLESHEET as DARK_STYLE, LIGHT_STYLESHEET as LIGHT_STYLE
from country_picker import CountryPicker
from dialogs import PilotsDialog, DesignDialog, WelcomeDialog, JokeDialog, GuidedDesignDialog
from app_icon import make_icon
from localized_widgets import ChoiceBox
from ux import install_wheel_guard, smooth_scroll

class RFSWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        install_wheel_guard()
        self.store = Store()
        set_language(self.store.state["language"])
        self.validation_problems = []
        self.can_copy = False
        self._building = False
        self.flight_widgets: dict[str, QWidget] = {}
        self.type_widgets: dict[str, QWidget] = {}
        self.render_error = ''
        self.setWindowTitle(tr('RFS ATC Message Maker'))
        self.setWindowIcon(make_icon())
        self.resize(1290, 880)
        self.setMinimumSize(1010, 690)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(250)
        self.preview_timer.timeout.connect(self.render_preview)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(2000)
        self.save_timer.timeout.connect(self.save_state)
        self.copy_feedback_timer = QTimer(self)
        self.copy_feedback_timer.setSingleShot(True)
        self.copy_feedback_timer.setInterval(2500)
        self.copy_feedback_timer.timeout.connect(self.reset_copy_feedback)
        self._build_ui()
        self._load_top_state()
        self._rebuild_forms()
        self._apply_theme()
        self.render_preview()
        QShortcut(QKeySequence('Ctrl+Return'), self, activated=self.generate_message)
        LOGGER.info('RFS ATC Message Maker démarré')

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame(objectName='card')
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        return (frame, layout)

    def _build_ui(self) -> None:
        root = QWidget(objectName="appRoot")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 16, 20, 18)
        outer.setSpacing(16)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(QLabel(tr('RFS ATC MESSAGE MAKER'), objectName='title'))
        titles.addWidget(QLabel(tr('Discord • Real Flight Simulator • un vol, plusieurs messages'), objectName='muted'))
        header.addLayout(titles)
        header.addStretch()
        local = QLabel(tr('Sauvegarde sur ce PC'), objectName='muted')
        local.setToolTip(tr("Vos données restent sur ce PC. Aucun compte ou accès Internet n'est nécessaire."))
        help_button = QPushButton(tr('Aide'))
        help_menu = QMenu(help_button)
        self.help_menu = help_menu
        help_menu.addAction(tr('Formulaire en ligne — problème ou suggestion'), self.open_feedback_form)
        help_menu.addAction(tr('Rapport local et pièces jointes…'), self.open_report)
        help_button.setMenu(help_menu)
        header.addWidget(help_button)
        self.finder_button = QPushButton(tr('Flight Finder'))
        self.finder_button.clicked.connect(self.open_finder)
        header.addWidget(self.finder_button)
        self.fuel_button = QPushButton(tr('Carburant'))
        self.fuel_button.clicked.connect(self.open_fuel)
        header.addWidget(self.fuel_button)
        self.language_combo = QComboBox()
        self.language_combo.addItem('Français', 'fr')
        self.language_combo.addItem('English', 'en')
        self.language_combo.setCurrentIndex(self.language_combo.findData(language()))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_combo)
        self.theme_button = QPushButton(tr('☀ Mode clair'))
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        outer.addLayout(header)
        quick = QHBoxLayout()
        quick.addWidget(QLabel(tr('Type de message')))
        self.message_type = QComboBox()
        self.message_type.addItems(MESSAGE_TYPES)
        self.message_type.setMinimumWidth(230)
        self.message_type.currentTextChanged.connect(self._type_changed)
        quick.addWidget(self.message_type)
        quick.addSpacing(12)
        quick.addWidget(QLabel(tr('Pseudo RFS')))
        self.pilot_name = QComboBox()
        self.pilot_name.setEditable(True)
        self.pilot_name.addItems(['n1chita', 'NIKA'])
        self.pilot_name.setMinimumWidth(140)
        self.pilot_name.currentTextChanged.connect(self._pilot_changed)
        quick.addWidget(self.pilot_name)
        quick.addStretch()
        outer.addLayout(quick)
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel(tr('Design')))
        self.design_combo = ChoiceBox()
        self.design_combo.setMinimumWidth(165)
        style_row.addWidget(self.design_combo)
        style_row.addWidget(QLabel(tr('Longueur')))
        self.length_combo = ChoiceBox()
        self.length_combo.addItems(['Court', 'Moyen', 'Détaillé'])
        self.length_combo.setToolTip(tr('Détaillé conserve les passagers et les informations facultatives. Ces détails sont rarement utiles à l’ATC ; privilégiez les informations nécessaires au vol.'))
        style_row.addWidget(self.length_combo)
        style_row.addWidget(QLabel(tr('Emojis')))
        self.emoji_combo = ChoiceBox()
        self.emoji_combo.addItems(EMOJI_STYLES)
        style_row.addWidget(self.emoji_combo)
        self.aligned = QCheckBox(tr('Encadrés alignés'))
        self.aligned.setToolTip(tr("Discord utilisera une police monospace. Les marques techniques ne sont pas affichées dans l'aperçu ; elles disparaissent au rendu Discord."))
        style_row.addWidget(self.aligned)
        designs = QPushButton(tr('Personnaliser…'))
        menu = QMenu(designs)
        menu.addAction(tr('Créer un design'), lambda: self.edit_design(new=True))
        menu.addAction(tr('Modifier le design sélectionné'), self.edit_design)
        menu.addAction(tr('Éditeur de variables (expert)'), lambda: self.edit_design(expert=True))
        menu.addAction(tr('Importer un design JSON'), self.import_design)
        menu.addAction(tr('Exporter le design sélectionné'), self.export_design)
        designs.setMenu(menu)
        style_row.addWidget(designs)
        style_row.addStretch()
        self.pilots_button = QPushButton(tr('Pilotes du vol (1)'))
        self.pilots_button.clicked.connect(self.edit_pilots)
        style_row.addWidget(self.pilots_button)
        outer.addLayout(style_row)
        for combo in (self.design_combo, self.length_combo, self.emoji_combo):
            combo.currentIndexChanged.connect(self._presentation_changed)
        self.aligned.toggled.connect(self._presentation_changed)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(16)
        split.setChildrenCollapsible(False)
        left_card, left = self._card()
        right_card, right = self._card()
        split.addWidget(left_card)
        split.addWidget(right_card)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)
        form_scroll = self.form_scroll = QScrollArea()
        smooth_scroll(form_scroll)
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form_body = QWidget(objectName='formBody')
        form_body_layout = QVBoxLayout(form_body)
        form_body_layout.setContentsMargins(0, 0, 6, 8)
        form_body_layout.setSpacing(20)
        self.flight_group = QGroupBox(tr('Vol actuel — informations communes'))
        flight_box = QVBoxLayout(self.flight_group)
        flight_select = QHBoxLayout()
        self.saved_flights = QComboBox()
        self.saved_flights.currentIndexChanged.connect(self._flight_selected)
        flight_select.addWidget(self.saved_flights, 1)
        new_flight = QPushButton(tr('Nouveau'))
        new_flight.setToolTip(tr("Créer un nouveau vol sans effacer l'historique"))
        new_flight.clicked.connect(self.new_flight)
        save_flight = QPushButton(tr('Sauver le vol'))
        save_flight.clicked.connect(self.save_current_flight)
        flight_select.addWidget(new_flight)
        flight_select.addWidget(save_flight)
        flight_box.addLayout(flight_select)
        self.flight_summary = QLabel(tr('Aucun vol renseigné'), objectName='muted')
        self.flight_summary.setWordWrap(True)
        flight_box.addWidget(self.flight_summary)
        self.flight_form = QFormLayout()
        self.flight_form.setSpacing(13)
        flight_box.setContentsMargins(8, 12, 8, 12)
        flight_box.setSpacing(14)
        flight_box.addLayout(self.flight_form)
        form_body_layout.addWidget(self.flight_group)
        self.detail_group = QGroupBox(tr('Informations du message'))
        detail_box = QVBoxLayout(self.detail_group)
        self.message_form = QFormLayout()
        self.message_form.setSpacing(13)
        detail_box.setContentsMargins(8, 12, 8, 12)
        detail_box.addLayout(self.message_form)
        form_body_layout.addWidget(self.detail_group)
        form_body_layout.addStretch()
        form_scroll.setWidget(form_body)
        left.addWidget(form_scroll, 1)
        form_actions = QHBoxLayout()
        generate = QPushButton(tr('Générer'))
        generate.clicked.connect(self.generate_message)
        clear = self.clear_button = QPushButton(tr('Effacer le vol'))
        clear.setToolTip(tr('Vide le vol et les messages courants. Les pilotes mémorisés, préférences et vols sauvegardés sont conservés.'))
        clear.clicked.connect(self.clear_current_message)
        form_actions.addWidget(generate)
        form_actions.addWidget(clear)
        form_actions.addStretch()
        left.addLayout(form_actions)
        preset_actions = QHBoxLayout()
        save_preset = QPushButton(tr('Sauver un favori'))
        save_preset.clicked.connect(self.save_preset)
        load_preset = QPushButton(tr('Charger un favori'))
        load_preset.clicked.connect(self.load_preset)
        history = QPushButton(tr('Historique'))
        history.clicked.connect(self.open_history)
        preset_actions.addWidget(save_preset)
        preset_actions.addWidget(load_preset)
        preset_actions.addStretch()
        preset_actions.addWidget(history)
        left.addLayout(preset_actions)
        result_header = QHBoxLayout()
        result_header.addWidget(QLabel(tr('Aperçu Discord'), objectName='section'))
        result_header.addStretch()
        self.emoji_label = QLabel(tr('0 / 6 emojis'), objectName='muted')
        result_header.addWidget(self.emoji_label)
        self.character_label = QLabel('', objectName='muted')
        result_header.addWidget(self.character_label)
        right.addLayout(result_header)
        self.preview = QPlainTextEdit(objectName="discordPreview")
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.preview.setPlaceholderText(tr('Le message se construit pendant la saisie…'))
        font = QFont('Consolas', 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.preview.setFont(font)
        self.preview.textChanged.connect(self._preview_edited)
        right.addWidget(self.preview, 1)
        self.issues = QLabel('', objectName='danger')
        self.issues.setWordWrap(True)
        right.addWidget(self.issues)
        self.status = QLabel(tr("Aperçu en direct. Le message n'est jamais envoyé automatiquement."), objectName='muted')
        self.status.setWordWrap(True)
        right.addWidget(self.status)
        copy_row = QHBoxLayout()
        self.copy_button = QPushButton(tr('Copier le message'), objectName='copy')
        self.copy_button.clicked.connect(self.copy_message)
        copy_row.addWidget(self.copy_button)
        self.copy_button.setMinimumHeight(44)
        right.addLayout(copy_row)
        self.setCentralWidget(root)

    def _load_top_state(self) -> None:
        self._building = True
        self.message_type.setCurrentText(self.store.state.get('message_type', 'ATC REQUEST'))
        self.pilot_name.setCurrentText(self.store.state.get('pilot_name', 'n1chita'))
        self._load_presentation()
        self._refresh_pilot_names()
        self._refresh_saved_flights()
        self._building = False

    def _refresh_saved_flights(self) -> None:
        chosen = self.store.state.get('current_flight_id', '')
        self.saved_flights.blockSignals(True)
        self.saved_flights.clear()
        self.saved_flights.addItem(tr('Vol actuel (non enregistré)'), '')
        for item in self.store.state.get('saved_flights', []):
            self.saved_flights.addItem(item.get('label', 'Vol'), item.get('id', ''))
        index = self.saved_flights.findData(chosen)
        self.saved_flights.setCurrentIndex(max(index, 0))
        self.saved_flights.blockSignals(False)

    def _create_widget(self, key: str, field: Field, value: object, scope: str) -> QWidget:
        if field.kind == 'flag':
            widget = CountryPicker(str(value or ''))
            widget.flagChanged.connect(lambda text, name=key, where=scope: self._field_changed(where, name, text))
        elif field.kind == 'bool':
            widget = QCheckBox(tr(field.label))
            widget.setChecked(bool(value))
            widget.toggled.connect(lambda checked, name=key, where=scope: self._field_changed(where, name, checked))
        elif field.kind in ('combo', 'flag', 'choice'):
            widget = ChoiceBox() if field.kind == "choice" else QComboBox()
            if field.kind == 'flag':
                widget.addItems(FLAGS)
                widget.setEditable(True)
            elif field.kind == 'choice':
                widget.addItems([''] + list(field.choices))
            else:
                widget.setEditable(True)
                category = {'airline': 'airline', 'aircraft': 'aircraft', 'departure_icao': 'airports', 'arrival_icao': 'airports', 'controller': 'controllers', 'server': 'servers'}.get(key)
                if category:
                    widget.addItems(self.store.state.get('recent', {}).get(category, []))
            widget.setCurrentText(str(value or ''))
            widget.currentTextChanged.connect(lambda text, name=key, where=scope, edit=widget: self._field_changed(where, name, edit.currentText()))
        elif field.kind == 'multiline':
            widget = QTextEdit()
            widget.setFixedHeight(72)
            widget.setPlainText(str(value or ''))
            widget.textChanged.connect(lambda name=key, where=scope, edit=widget: self._field_changed(where, name, edit.toPlainText()))
        else:
            widget = QLineEdit()
            widget.setText(str(value or ''))
            widget.textChanged.connect(lambda text, name=key, where=scope: self._field_changed(where, name, text))
        if field.hint:
            widget.setToolTip(tr(field.hint))
        return widget

    def _rebuild_forms(self) -> None:
        self._building = True
        while self.flight_form.rowCount():
            self.flight_form.removeRow(0)
        while self.message_form.rowCount():
            self.message_form.removeRow(0)
        self.flight_widgets = {}
        self.type_widgets = {}
        message_type = self.message_type.currentText()
        self.flight_group.setVisible(message_type in FLIGHT_TYPES)
        flight = self.store.state['flight']
        visible_keys = list(FLIGHT_FIELDS_BY_TYPE.get(message_type, ()))
        if self.length_combo.currentText() == 'Détaillé' and message_type in ('ATC REQUEST', 'AIRBORNE', 'ARRIVAL BOARD'):
            visible_keys += [key for key in ('passengers', 'cargo', 'fuel') if key not in visible_keys]
        for key in visible_keys:
            field = FLIGHT_FIELDS[key]
            widget = self._create_widget(key, field, flight.get(key, ''), 'flight')
            required = key in REQUIRED_FLIGHT.get(message_type, ())
            self.flight_form.addRow(tr('{v0}{v1}', v0=tr(field.label), v1=' *' if required else ''), widget)
            self.flight_widgets[key] = widget
        data = self.store.state['per_type'].setdefault(message_type, {})
        for key, field in MESSAGE_FIELDS[message_type].items():
            if key == 'server' and (not data.get(key)):
                data[key] = self.store.state.get('server', '')
            widget = self._create_widget(key, field, data.get(key, False if field.kind == 'bool' else ''), 'type')
            required = key in REQUIRED_MESSAGE.get(message_type, ())
            self.message_form.addRow('' if field.kind == 'bool' else tr('{v0}{v1}', v0=tr(field.label), v1=' *' if required else ''), widget)
            self.type_widgets[key] = widget
        if not MESSAGE_FIELDS[message_type]:
            self.message_form.addRow(QLabel(tr('Tous les champs sont dans le vol actuel.'), objectName='muted'))
        for form in (self.flight_form, self.message_form):
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                if item and isinstance(item.widget(), QLabel):
                    label = item.widget()
                    label.setProperty('baseLabel', label.text())
                    label.setWordWrap(True)
                    label.setMinimumWidth(145)
                    label.setMaximumWidth(175)
        self._building = False
        self._apply_conditional_visibility()
        self._update_flight_summary()
        self.preview_timer.start()

    def _apply_conditional_visibility(self) -> None:
        message_type = self.message_type.currentText()
        data = self.store.state['per_type'].get(message_type, {})
        if message_type == 'AIRBORNE':
            self.message_form.setRowVisible(self.type_widgets['climb_waypoint'], data.get('climb_target') == 'Waypoint')
        if message_type == 'ARRIVAL BOARD':
            for key, toggle in (('arrival_ete', 'show_ete'), ('star', 'show_star'), ('altitude', 'show_altitude')):
                self.message_form.setRowVisible(self.type_widgets[key], bool(data.get(toggle)))
            self.message_form.setRowVisible(self.type_widgets['status'], not bool(data.get('go_around')))
            self.flight_form.setRowVisible(self.flight_widgets['fuel'], bool(data.get('show_fuel')))
        if message_type == 'FLIGHT COMPLETED':
            detailed = bool(data.get('detailed')) or self.length_combo.currentText() == 'Détaillé'
            self.message_form.setRowVisible(self.type_widgets['touchdown'], detailed)
            for key in ('passengers', 'cargo', 'fuel'):
                self.flight_form.setRowVisible(self.flight_widgets[key], detailed)
        if message_type in ('AIRBORNE', 'FLIGHT COMPLETED'):
            self.message_form.setRowVisible(self.type_widgets['controller'], not bool(data.get('no_atc')))

    def _field_changed(self, scope: str, key: str, value: object) -> None:
        if self._building:
            return
        self.reset_copy_feedback()
        if scope == 'flight':
            self.store.state['flight'][key] = value
            provenance = self.store.state['flight'].get('selected_flight', {}).get('fields', {})
            if key in provenance:
                provenance[key] = 'USER_INPUT'
            self.store.state['preview_edits'] = {}
            self._update_flight_summary()
        else:
            message_type = self.message_type.currentText()
            self.store.state['per_type'][message_type][key] = value
            self.store.state['preview_edits'].pop(message_type, None)
            if key == 'server':
                self.store.state['server'] = str(value)
            if key in ('climb_target', 'go_around', 'show_ete', 'show_star', 'show_fuel', 'show_altitude', 'detailed', 'no_atc'):
                self._apply_conditional_visibility()
        self.preview_timer.start()
        self.save_timer.start()

    def _pilot_changed(self, value: str) -> None:
        if self._building:
            return
        self.store.state['pilot_name'] = value
        self.store.state['preview_edits'] = {}
        self.preview_timer.start()
        self.save_timer.start()

    def _type_changed(self, value: str) -> None:
        if self._building or not value:
            return
        self.store.state['message_type'] = value
        self._rebuild_forms()
        self.save_timer.start()

    def _update_flight_summary(self) -> None:
        flight = self.store.state['flight']
        count = 1 + len(additional_pilots(flight, self.message_type.currentText()))
        self.pilots_button.setText(tr('Pilotes du vol ({v0})', v0=count))
        self.pilots_button.setEnabled(self.message_type.currentText() in FLIGHT_TYPES)
        parts = [flight.get('callsign', '') or flight.get('flight_number', ''), flight.get('departure_icao', ''), flight.get('arrival_icao', '')]
        if parts[1] or parts[2]:
            route = f"{parts[1] or '…'} → {parts[2] or '…'}"
            self.flight_summary.setText(' • '.join((part for part in (parts[0], route, flight.get('aircraft', '')) if part)))
        else:
            self.flight_summary.setText(tr('Renseignez un vol : ses données suivront chaque type de message.'))

    def render_preview(self) -> None:
        message_type = self.message_type.currentText()
        if not message_type:
            return
        flight = self.store.state['flight']
        data = self.store.state['per_type'].get(message_type, {})
        pilot = self.pilot_name.currentText().strip()
        try:
            self.render_error = ''
            text = self.store.state.get('preview_edits', {}).get(message_type)
            if text is None:
                presentation = self.store.state['presentation']
                custom = self.store.designs.get(presentation.get('custom_id', ''))
                text = compose(message_type, flight, data, pilot, presentation, custom)
            self.preview.blockSignals(True)
            self.preview.setPlainText(preview_text(text))
            self.preview.blockSignals(False)
            self._refresh_validation()
        except Exception as error:
            LOGGER.exception('Échec du rendu %s', message_type)
            self.render_error = str(error)
            self.status.setText(tr('Design à corriger : {v0}', v0=error))
            self.copy_button.setEnabled(False)

    def _preview_edited(self) -> None:
        self.store.state.setdefault('preview_edits', {})[self.message_type.currentText()] = self._clipboard_message()
        self.save_timer.start()
        self._refresh_validation()

    def _refresh_validation(self) -> None:
        message_type = self.message_type.currentText()
        flight = self.store.state['flight']
        data = self.store.state['per_type'].get(message_type, {})
        effective_data = dict(data)
        if self.length_combo.currentText() == 'Détaillé' and message_type == 'FLIGHT COMPLETED':
            effective_data['detailed'] = True
        problems = validate_group(message_type, flight, effective_data, self.pilot_name.currentText().strip())
        if self.render_error:
            problems.append(Issue('design', self.render_error))
        characters = len(self._clipboard_message())
        self.character_label.setText(tr('{v0} / 2 000 caractères', v0=characters))
        if characters > 2000:
            problems.append(Issue('length', tr('Message trop long : choisissez Court ou retirez des détails (2 000 caractères).')))
        count = emoji_count(self.preview.toPlainText())
        if message_type == 'DISPATCH FORM':
            self.emoji_label.setText(tr('{v0} emojis (illimité)', v0=count))
            self.emoji_label.setObjectName('muted')
        else:
            self.emoji_label.setText(tr('{v0} / 6 emojis', v0=count))
            self.emoji_label.setObjectName('danger' if count > 6 else 'muted')
            if count > 6:
                problems.append(Issue('emoji', tr('Plus de 6 emojis : réduisez-les avant Copy.')))
        if problems:
            self.issues.setObjectName('danger')
            shown = [tr(issue.text) for issue in problems[:5]]
            more = tr(' (+{count} autres)', count=len(problems) - 5) if len(problems) > 5 else ''
            self.issues.setText(tr('À compléter : ') + ' • '.join(shown) + more)
        else:
            self.issues.setText(tr('Prêt à copier.'))
            self.issues.setObjectName('muted')
        self.issues.style().unpolish(self.issues)
        self.issues.style().polish(self.issues)
        self.validation_problems = problems
        self.can_copy = not problems and bool(self.preview.toPlainText().strip())
        self.copy_button.setEnabled(True)
        for form, widgets in ((self.flight_form, self.flight_widgets), (self.message_form, self.type_widgets)):
            for key, widget in widgets.items():
                errors = [p.text for p in problems if p.field == key]
                is_invalid = bool(errors)
                widget.setAccessibleDescription(' • '.join(errors))
                if widget.property('invalid') != is_invalid:
                    widget.setProperty('invalid', is_invalid)
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                label = form.labelForField(widget)
                if label:
                    base = label.property('baseLabel') or label.text()
                    label.setText(base + ('\n⚠ ' + tr('À corriger') if errors else ''))
                    label.setToolTip(' • '.join(errors))
        self.pilots_button.setToolTip(' • '.join((p.text for p in problems if p.field == 'pilots')))

    def generate_message(self) -> None:
        self.store.state.setdefault('preview_edits', {}).pop(self.message_type.currentText(), None)
        self.render_preview()
        self.save_timer.start()
        if self.can_copy:
            self.status.setText(tr("Message prêt. Vous pouvez ajuster l'aperçu avant Copy."))
        else:
            self.status.setText(tr('Complétez les champs signalés pour activer Copy.'))

    def copy_message(self) -> None:
        if self.preview_timer.isActive():
            self.preview_timer.stop()
            self.render_preview()
        self._refresh_validation()
        if not self.can_copy:
            self.issues.setStyleSheet('color: #ef4444; font-weight: 700;')
            QTimer.singleShot(650, self.issues, lambda: self.issues.setStyleSheet(''))
            for issue in self.validation_problems:
                widget = self.flight_widgets.get(issue.field) or self.type_widgets.get(issue.field)
                if issue.field == 'pilot_name':
                    widget = self.pilot_name
                elif issue.field == 'pilots':
                    widget = self.pilots_button
                if widget:
                    widget.setFocus(Qt.FocusReason.OtherFocusReason)
                    self.form_scroll.ensureWidgetVisible(widget, 20, 45)
                    break
            self.status.setText(tr('Copie impossible : corrigez les champs signalés à gauche.'))
            return
        text = self._clipboard_message()
        QApplication.clipboard().setText(text)
        message_type = self.message_type.currentText()
        data = deepcopy(self.store.state['per_type'].get(message_type, {}))
        entry = {'date': datetime.now().isoformat(timespec='seconds'), 'message_type': message_type, 'pilot_name': self.pilot_name.currentText().strip(), 'flight': deepcopy(self.store.state['flight']), 'data': data, 'message': text}
        try:
            entry['presentation'] = deepcopy(self.store.state['presentation'])
            merged = self.store.add_history(entry)
            self._remember_frequent_values(data)
            self.store.save_state()
            self.status.setText(tr('Message copié — historique mis à jour.') if merged else tr("Message copié — enregistré dans l'historique local."))
        except Exception:
            LOGGER.exception('Enregistrement après copie impossible')
            self.status.setText(tr("Copié. L'historique n'a pas pu être enregistré."))
        self.copy_button.setText(tr('✓ Message copié !'))
        self.copy_feedback_timer.start()

    def _remember_frequent_values(self, data: dict) -> None:
        flight = self.store.state['flight']
        for key, category in (('airline', 'airline'), ('aircraft', 'aircraft'), ('departure_icao', 'airports'), ('arrival_icao', 'airports')):
            self.store.remember(category, str(flight.get(key, '')))
        self.store.remember('controllers', str(data.get('controller', '')))
        self.store.remember('servers', str(data.get('server', '')))

    def save_state(self) -> None:
        try:
            self.store.save_state()
        except Exception:
            LOGGER.exception('Autosauvegarde impossible')
            self.status.setText(tr('Autosauvegarde impossible. La saisie reste affichée.'))

    def _flight_selected(self, index: int) -> None:
        if self._building:
            return
        flight_id = self.saved_flights.itemData(index) or ''
        if not flight_id:
            return
        item = next((item for item in self.store.state['saved_flights'] if item.get('id') == flight_id), None)
        if not item:
            return
        self.store.state['current_flight_id'] = flight_id
        self.store.state['flight'] = {**empty_flight(), **deepcopy(item.get('flight', {}))}
        defaults = empty_per_type()
        for kind in FLIGHT_TYPES:
            self.store.state['per_type'][kind] = {**defaults[kind], **deepcopy(item.get('per_type', {}).get(kind, {}))}
        self.store.state['preview_edits'] = {}
        self._rebuild_forms()
        self.save_state()
        self.status.setText(tr('Vol chargé : {v0}.', v0=item.get('label', 'Vol')))

    def new_flight(self) -> None:
        self.store.state['current_flight_id'] = ''
        self.store.state['flight'] = empty_flight()
        defaults = empty_per_type()
        for kind in FLIGHT_TYPES:
            self.store.state['per_type'][kind] = defaults[kind]
        self.store.state['preview_edits'] = {}
        self._refresh_saved_flights()
        self._rebuild_forms()
        self.save_state()
        self.status.setText(tr('Nouveau vol. Les anciens vols enregistrés restent disponibles.'))

    def open_feedback_form(self):
        from report_dialog import open_feedback_form
        if not open_feedback_form():
            QMessageBox.warning(self, tr('Formulaire en ligne'), tr('Impossible d’ouvrir le navigateur. Réessayez ou exportez un rapport local.'))

    def open_report(self):
        from report_dialog import ReportDialog
        ReportDialog(self).exec()

    def open_finder(self):
        try:
            from finder.ui import FinderDialog
            from storage import DATA_DIR
            local_db = DATA_DIR.parent / 'finder-data' / 'aviation.sqlite'
            saved_path = self.store.state.get('finder_database')
            if local_db.exists():
                path = local_db
            elif saved_path and Path(saved_path).exists():
                path = Path(saved_path)
            else:
                path = local_db
            dialog = FinderDialog(self, path, self.store.state['language'])
            dialog.selected.connect(self.use_found_flight)
            dialog.exec()
            self.store.state['finder_database'] = str(dialog.path)
            self.save_state()
        except Exception as error:
            LOGGER.exception('Flight Finder indisponible')
            QMessageBox.warning(self, tr('Flight Finder'), str(error))

    def use_found_flight(self, result):
        from finder.mapping import use_this_flight
        self.store.state['flight'] = use_this_flight(self.store.state['flight'], result)
        self.store.state['current_flight_id'] = ''
        self.store.state['preview_edits'] = {}
        self._refresh_saved_flights()
        self._rebuild_forms()
        self.render_preview()
        self.save_state()
        self.status.setText(tr('Vol Finder chargé. Vérifiez les pistes, portes, carburant et autres pilotes conservés. Distance = référence orthodromique ; durée = typique en vol.'))

    def open_fuel(self):
        try:
            from fuel.ui import FuelDialog
            dialog = FuelDialog(self.store.state['flight'], self)
            dialog.selected.connect(self.use_fuel_result)
            dialog.exec()
        except Exception as error:
            LOGGER.exception('Calculateur carburant indisponible')
            QMessageBox.warning(self, tr('Carburant RFS'), str(error))

    def use_fuel_result(self, result):
        flight = self.store.state['flight']
        flight['fuel'] = f"{result['total_block_fuel_kg_exact']:.0f}"
        flight['aircraft'] = result['aircraft']['name']
        flight['fuel_calculation'] = deepcopy(result)
        flight['fuel_aircraft_id'] = result['aircraft']['id']
        if flight.get('selected_flight'):
            flight['selected_flight'].setdefault('fields', {})['fuel'] = 'RFS_SIMULATION_ESTIMATE'
            flight['selected_flight']['fields']['aircraft'] = 'USER_INPUT_FUEL_VARIANT'
        self.store.state['preview_edits'] = {}
        self._rebuild_forms()
        self.render_preview()
        self.save_state()
        self.status.setText(tr('Carburant RFS appliqué : ') + result['display']['total_block_fuel'] + tr(' — estimation pour simulation uniquement, jamais pour un vol réel.'))

    def save_current_flight(self) -> None:
        flight = deepcopy(self.store.state['flight'])
        proposed = flight.get('callsign') or f"{flight.get('departure_icao') or 'Départ'} → {flight.get('arrival_icao') or 'Arrivée'}"
        name, ok = QInputDialog.getText(self, tr('Enregistrer le vol'), tr('Nom du vol :'), text=proposed)
        if not ok or not name.strip():
            return
        flight_id = self.store.state.get('current_flight_id') or uuid.uuid4().hex
        item = {'id': flight_id, 'label': name.strip(), 'flight': flight, 'per_type': {kind: deepcopy(self.store.state['per_type'][kind]) for kind in FLIGHT_TYPES}}
        saved = self.store.state['saved_flights']
        for index, previous in enumerate(saved):
            if previous.get('id') == flight_id:
                saved[index] = item
                break
        else:
            saved.append(item)
        self.store.state['current_flight_id'] = flight_id
        self._remember_frequent_values({})
        self.save_state()
        self._refresh_saved_flights()
        self.status.setText(tr('Vol enregistré et disponible pour tous les messages du vol.'))

    def clear_current_message(self) -> None:
        for person in self.store.state['flight'].get('pilots', []):
            self.store.remember_pilot(person)
        self.store.state['current_flight_id'] = ''
        self.store.state['flight'] = empty_flight()
        self.store.state['per_type'] = empty_per_type()
        self.store.state['preview_edits'] = {}
        self._refresh_saved_flights()
        self._refresh_pilot_names()
        self._rebuild_forms()
        self.render_preview()
        self.reset_copy_feedback()
        self.save_state()
        self.clear_button.setText(tr('✓ Effacé'))
        QTimer.singleShot(2200, self.clear_button, lambda: self.clear_button.setText(tr('Effacer le vol')))
        self.status.setText(tr('Vol courant effacé. Pilotes mémorisés et vols enregistrés conservés.'))

    def save_preset(self) -> None:
        message_type = self.message_type.currentText()
        airline = self.store.state['flight'].get('airline', '').strip()
        proposed = f'{airline} · {message_type}' if airline else message_type
        name, ok = QInputDialog.getText(self, tr('Save preset'), tr('Nom du preset :'), text=proposed)
        if not ok or not name.strip():
            return
        preset = {'message_type': message_type, 'flight': deepcopy(self.store.state['flight']), 'data': deepcopy(self.store.state['per_type'].get(message_type, {})), 'pilot_name': self.pilot_name.currentText().strip()}
        preset['presentation'] = deepcopy(self.store.state['presentation'])
        try:
            self.store.save_preset(name.strip(), preset)
            self.status.setText(tr('Preset « {v0} » enregistré localement.', v0=name.strip()))
        except Exception:
            LOGGER.exception('Preset impossible à enregistrer')
            self.status.setText(tr("Impossible d'enregistrer le preset."))

    def load_preset(self) -> None:
        if not self.store.presets:
            self.status.setText(tr('Aucun preset enregistré pour le moment.'))
            return
        name, ok = QInputDialog.getItem(self, tr('Load preset'), tr('Choisissez un preset :'), list(self.store.presets), 0, False)
        if not ok:
            return
        preset = self.store.presets[name]
        message_type = preset.get('message_type', 'ATC REQUEST')
        if message_type not in MESSAGE_TYPES:
            self.status.setText(tr('Preset incompatible.'))
            return
        self.store.state['flight'] = {**empty_flight(), **deepcopy(preset.get('flight', {}))}
        self.store.state['presentation'] = {**DEFAULT_PRESENTATION, **preset.get('presentation', {})}
        self._load_presentation()
        self.store.state['current_flight_id'] = ''
        self.store.state['preview_edits'] = {}
        self.store.state['per_type'][message_type] = {**empty_per_type()[message_type], **deepcopy(preset.get('data', {}))}
        self.pilot_name.setCurrentText(preset.get('pilot_name', 'n1chita'))
        self.message_type.setCurrentText(message_type)
        self._refresh_saved_flights()
        self._rebuild_forms()
        self.save_state()
        self.status.setText(tr('Preset « {v0} » chargé.', v0=name))

    def open_history(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('Historique RFS local'))
        dialog.resize(920, 610)
        layout = QVBoxLayout(dialog)
        compact = QCheckBox(tr("Regrouper les petites corrections d'un même message (15 minutes)"))
        compact.setChecked(self.store.state.get('compact_history', True))
        compact.toggled.connect(lambda checked: self.store.state.update(compact_history=checked))
        layout.addWidget(compact)
        table = QTableWidget(len(self.store.history), 4)
        table.setHorizontalHeaderLabels(['Date', 'Type', 'Callsign', 'Route'])
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, item in enumerate(self.store.history):
            flight = item.get('flight', {})
            values = (item.get('date', '').replace('T', ' '), item.get('message_type', ''), flight.get('callsign', ''), f"{flight.get('departure_icao', '')} → {flight.get('arrival_icao', '')}")
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(table)
        sample = QPlainTextEdit()
        sample.setReadOnly(True)
        sample.setFont(QFont('Consolas', 10))
        layout.addWidget(sample)

        def selected() -> dict | None:
            index = table.currentRow()
            return self.store.history[index] if 0 <= index < len(self.store.history) else None

        def show_selected() -> None:
            item = selected()
            sample.setPlainText(item.get('message', '') if item else '')
        table.itemSelectionChanged.connect(show_selected)
        buttons = QHBoxLayout()
        duplicate = QPushButton(tr('Dupliquer le message'))
        copy = QPushButton(tr('Copier le message'))
        close = QPushButton(tr('Fermer'))

        def duplicate_selected() -> None:
            item = selected()
            if not item:
                return
            message_type = item.get('message_type', 'ATC REQUEST')
            if message_type not in MESSAGE_TYPES:
                return
            self.store.state['flight'] = {**empty_flight(), **deepcopy(item.get('flight', {}))}
            self.store.state['presentation'] = {**DEFAULT_PRESENTATION, **item.get('presentation', {})}
            self._load_presentation()
            self.store.state['current_flight_id'] = ''
            self.store.state['preview_edits'] = {}
            self.store.state['per_type'][message_type] = {**empty_per_type()[message_type], **deepcopy(item.get('data', {}))}
            self.pilot_name.setCurrentText(item.get('pilot_name', 'n1chita'))
            self.message_type.setCurrentText(message_type)
            self._refresh_saved_flights()
            self._rebuild_forms()
            self.preview.setPlainText(item.get('message', ''))
            self.preview_timer.stop()
            self.save_state()
            self.status.setText(tr('Message dupliqué. Ses champs sont modifiables.'))
            dialog.accept()

        def copy_selected() -> None:
            item = selected()
            if item:
                QApplication.clipboard().setText(item.get('message', ''))
        duplicate.clicked.connect(duplicate_selected)
        copy.clicked.connect(copy_selected)
        close.clicked.connect(dialog.reject)
        buttons.addWidget(duplicate)
        buttons.addWidget(copy)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        dialog.exec()

    def toggle_theme(self) -> None:
        self.store.state['theme'] = 'Clair' if self.store.state.get('theme') == 'Sombre' else 'Sombre'
        self._apply_theme()
        self.save_state()

    def _apply_theme(self) -> None:
        dark = self.store.state.get('theme', 'Sombre') == 'Sombre'
        apply_palette(QApplication.instance(), dark)
        self.setStyleSheet(get_stylesheet(dark))
        self.theme_button.setText(tr('☀ Mode clair') if dark else tr('☾ Mode sombre'))

    def closeEvent(self, event) -> None:
        self.preview_timer.stop()
        self.save_timer.stop()
        self.copy_feedback_timer.stop()
        self.save_state()
        event.accept()

    def reset_copy_feedback(self):
        self.copy_feedback_timer.stop()
        self.copy_button.setText(tr('Copier le message'))

    def change_language(self, *_):
        selected = self.language_combo.currentData()
        if selected == language():
            return
        self.preview_timer.stop()
        self.save_timer.stop()
        self.copy_feedback_timer.stop()
        self.store.state['language'] = selected
        set_language(selected)
        self._building = True
        old = self.takeCentralWidget()
        self._build_ui()
        self._load_top_state()
        self._rebuild_forms()
        dark = self.store.state.get('theme', 'Sombre') == 'Sombre'
        self.theme_button.setText(tr('☀ Mode clair') if dark else tr('☾ Mode sombre'))
        self.render_preview()
        self.save_state()
        old.deleteLater()

    def show_welcome(self):
        if not self.store.state.get('intro_seen'):
            if not self.store.state.get('joke_seen'):
                selection, ok = QInputDialog.getItem(self, 'Français / English', tr('Langue de l’interface'), ['Français', 'English'], 0, False)
                if ok:
                    self.language_combo.setCurrentIndex(1 if selection == 'English' else 0)
                # Independent of the welcome checkbox, and saved before opening.
                self.store.state['joke_seen'] = True
                self.save_state()
                JokeDialog(self).exec()
                QMessageBox.information(self, tr('I was kidding !'), tr("C'était une blague ! Aucun paiement ni aucune donnée bancaire : l'application est gratuite. Bienvenue à bord !"))
            dialog = WelcomeDialog(self)
            dialog.exec()
            self.store.state['intro_seen'] = dialog.remember.isChecked()
            self.save_state()

    def _load_presentation(self):
        previous = self._building
        self._building = True
        options = {**DEFAULT_PRESENTATION, **self.store.state.get('presentation', {})}
        self.store.state['presentation'] = options
        self.design_combo.clear()
        for name in BUILTIN_DESIGNS:
            self.design_combo.addItem(name, '')
        for key, design in self.store.designs.items():
            self.design_combo.addItem(tr("Personnel · {name}", name=design.get("name", key)), key)
        if options.get('custom_id'):
            self.design_combo.setCurrentIndex(max(0, self.design_combo.findData(options['custom_id'])))
        else:
            self.design_combo.setCurrentText(options['design'])
        self.length_combo.setCurrentText(options['length'])
        self.emoji_combo.setCurrentText(options['emoji_style'])
        self.aligned.setChecked(bool(options['discord_aligned']))
        self._building = previous

    def _presentation_changed(self, *_):
        if self._building:
            return
        custom_id = self.design_combo.currentData() or ''
        self.store.state['presentation'] = {'design': 'Classique' if custom_id else self.design_combo.currentText(), 'custom_id': custom_id, 'length': self.length_combo.currentText(), 'emoji_style': self.emoji_combo.currentText(), 'discord_aligned': self.aligned.isChecked()}
        self.store.state['preview_edits'] = {}
        self.reset_copy_feedback()
        self._rebuild_forms()
        self.render_preview()
        self.save_timer.start()

    def _clipboard_message(self):
        return clipboard_text(self.preview.toPlainText().strip(), self.aligned.isChecked())

    def edit_pilots(self):
        dialog = PilotsDialog(self.store.state['flight'], self.pilot_name.currentText(), self, library=self.store.state.get('pilot_library', []))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.store.state['flight'].update(dialog.values())
            for person in dialog.values()['pilots']:
                self.store.remember_pilot(person)
            self._refresh_pilot_names()
            self.store.state['preview_edits'] = {}
            self._update_flight_summary()
            self.render_preview()
            self.save_state()

    def _refresh_pilot_names(self):
        current = self.pilot_name.currentText()
        self.pilot_name.blockSignals(True)
        for person in self.store.state.get('pilot_library', []):
            name = person.get('name', '')
            if name and self.pilot_name.findText(name) < 0:
                self.pilot_name.addItem(name)
        self.pilot_name.setCurrentText(current)
        self.pilot_name.blockSignals(False)

    def edit_design(self, new=False, expert=False):
        key = '' if new else self.store.state['presentation'].get('custom_id', '')
        existing = self.store.designs.get(key)
        editor = DesignDialog if expert or (existing and (not existing.get('guided'))) else GuidedDesignDialog
        dialog = editor(existing, self)
        if expert:
            if existing and existing.get('guided'):
                dialog.convert_to_advanced()
            else:
                dialog.tabs.setCurrentIndex(1)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        design = dialog.values()
        if not design['name'] or not design['template'].strip():
            self.status.setText(tr('Le design doit avoir un nom et un contenu.'))
            return
        key = key or uuid.uuid4().hex
        try:
            self.store.save_design(key, design)
            self.store.state['presentation']['custom_id'] = key
            self._load_presentation()
            self._presentation_changed()
        except OSError:
            self.status.setText(tr("Impossible d'enregistrer ce design sur le disque."))

    def import_design(self):
        path, _ = QFileDialog.getOpenFileName(self, tr('Importer un design'), '', tr('Design JSON (*.json)'))
        if not path:
            return
        try:
            if Path(path).stat().st_size > 100000:
                raise ValueError(tr('Fichier trop volumineux'))
            value = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if not isinstance(value, dict) or not isinstance(value.get('name'), str) or (not isinstance(value.get('template'), str)):
                raise ValueError(tr('Le fichier doit contenir un nom et un modèle texte'))
            key = uuid.uuid4().hex
            self.store.save_design(key, {k: v for k, v in value.items() if k in ('name', 'template', 'guided', 'base_design', 'heading', 'footer')})
            self.store.state['presentation']['custom_id'] = key
            self._load_presentation()
            self._presentation_changed()
        except (OSError, ValueError) as error:
            self.status.setText(tr('Import impossible : {v0}', v0=error))

    def export_design(self):
        key = self.store.state['presentation'].get('custom_id', '')
        design = self.store.designs.get(key)
        if not design:
            self.status.setText(tr("Sélectionnez d'abord un design personnel à exporter."))
            return
        path, _ = QFileDialog.getSaveFileName(self, tr('Exporter le design'), 'design-rfs.json', tr('Design JSON (*.json)'))
        if path:
            try:
                from storage import save_json
                save_json(Path(path), design)
                self.status.setText(tr("Design exporté. Aucune donnée du vol n'est incluse."))
            except OSError:
                self.status.setText(tr("Impossible d'écrire ce fichier."))
