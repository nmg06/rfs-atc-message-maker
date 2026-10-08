"""Interface Windows de RFS ATC Message Maker."""
from __future__ import annotations
from i18n import tr, set_language, language
from copy import deepcopy
from datetime import datetime
import uuid
import json
from html import escape
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QMenu, QFileDialog, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QGridLayout, QVBoxLayout, QWidget, QToolTip
from rfs_schema import Field, FLAGS, FLIGHT_FIELDS, FLIGHT_FIELDS_BY_TYPE, FLIGHT_TYPES, MESSAGE_FIELDS, MESSAGE_TYPES, empty_flight, empty_per_type
from storage import LOGGER, Store
from templates import render
from validation import Issue, REQUIRED_FLIGHT, REQUIRED_MESSAGE, emoji_count, validate
from message_builder import compose, validate_group, DEFAULT_PRESENTATION, additional_pilots, BUILTIN_DESIGNS, EMOJI_STYLES, preview_text, clipboard_text, validate_design
from appearance import apply_palette, extra_style, get_stylesheet, DARK_STYLESHEET as DARK_STYLE, LIGHT_STYLESHEET as LIGHT_STYLE
from country_picker import CountryPicker
from dialogs import PilotsDialog, DesignDialog, WelcomeDialog, JokeDialog, GuidedDesignDialog
from app_icon import make_icon
from localized_widgets import ChoiceBox
from ux import install_wheel_guard, smooth_scroll
from visual_themes import THEMES
from appearance import colourize_stylesheet

class RFSWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        install_wheel_guard()
        self.store = Store()
        # Install the style before constructing hundreds of child controls.
        from flightdeck import deck_style
        self._styled_dark = self.store.state.get('theme', 'Sombre') == 'Sombre'
        self._styled_identity = self.store.state.get('visual_theme', 'avionique')
        apply_palette(QApplication.instance(), self._styled_dark, self._styled_identity)
        self.setStyleSheet(colourize_stylesheet(get_stylesheet(self._styled_dark) + deck_style(self._styled_dark), self._styled_dark, self._styled_identity))
        set_language(self.store.state["language"])
        self.validation_problems = []
        self.can_copy = False
        self._building = False
        self.flight_widgets: dict[str, QWidget] = {}
        self.type_widgets: dict[str, QWidget] = {}
        self.render_error = ''
        self.help_dialog = None
        from update_dialog import read_preferences
        self.update_preferences = read_preferences()
        self.update_dialog = None
        self._update_running = False
        self._update_preferences_running = False
        self.setWindowTitle('RFS Flightdeck')
        self.setWindowIcon(make_icon())
        self.resize(1290, 880)
        self.setMinimumSize(1010, 690)
        self._presentation_expanded = False
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
        QShortcut(QKeySequence('Ctrl+Shift+C'), self, activated=self.copy_message)
        QShortcut(QKeySequence('Ctrl+S'), self, activated=self.save_current_flight)
        LOGGER.info('RFS ATC Message Maker démarré')
        QTimer.singleShot(2000, self.check_updates)

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
        titles.addWidget(QLabel('RFS ATC', objectName='title'))
        titles.addWidget(QLabel('MESSAGE MAKER  /  REAL FLIGHT SIMULATOR', objectName='muted'))
        header.addLayout(titles)
        header.addStretch()
        help_button = QPushButton(tr('Aide'))
        help_menu = QMenu(help_button)
        self.help_menu = help_menu
        help_menu.addAction(tr('Formulaire en ligne — problème ou suggestion'), self.open_feedback_form)
        help_menu.addAction(tr('Rapport local et pièces jointes…'), self.open_report)
        help_button.setMenu(help_menu)
        header.addWidget(help_button)
        self.finder_button = QPushButton(tr('Flight Finder'))
        self.finder_button.clicked.connect(self.open_finder)
        self.fuel_button = QPushButton(tr('Carburant'))
        self.fuel_button.clicked.connect(self.open_fuel)
        self.language_combo = QComboBox()
        self.language_combo.addItem('Français', 'fr')
        self.language_combo.addItem('English', 'en')
        self.language_combo.setCurrentIndex(self.language_combo.findData(language()))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        header.addWidget(self.language_combo)
        self.theme_button = QPushButton(tr('☀ Mode clair'))
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        self.visual_theme_combo = QComboBox()
        self.visual_theme_combo.setAccessibleName(tr('Palette de couleurs'))
        for ident, name, *_ in THEMES:
            self.visual_theme_combo.addItem(tr(name), ident)
        self.visual_theme_combo.setCurrentIndex(max(0,self.visual_theme_combo.findData(self.store.state.get('visual_theme','avionique'))))
        self.visual_theme_combo.currentIndexChanged.connect(self.change_visual_theme)
        header.addWidget(self.visual_theme_combo)
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
        quick.addWidget(self.finder_button)
        quick.addWidget(self.fuel_button)
        outer.addLayout(quick)
        presentation_bar = QHBoxLayout()
        self.presentation_toggle = QToolButton()
        self.presentation_toggle.setObjectName('presentationToggle')
        self.presentation_toggle.setText(tr('Présentation du message'))
        self.presentation_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.presentation_toggle.setCheckable(True)
        self.presentation_toggle.setChecked(self._presentation_expanded)
        self.presentation_toggle.setArrowType(Qt.ArrowType.DownArrow if self._presentation_expanded else Qt.ArrowType.RightArrow)
        presentation_bar.addWidget(self.presentation_toggle)
        self.presentation_summary = QLabel(objectName='muted')
        self.presentation_summary.setWordWrap(True)
        presentation_bar.addWidget(self.presentation_summary, 1)
        self.presentation_panel = QFrame(objectName='settingsPanel')
        settings = QGridLayout(self.presentation_panel)
        settings.setContentsMargins(14, 12, 14, 12)
        settings.setHorizontalSpacing(16)
        settings.setVerticalSpacing(8)
        self.design_combo = ChoiceBox()
        self.design_combo.setMinimumWidth(165)
        self.length_combo = ChoiceBox()
        self.length_combo.addItems(['Court', 'Moyen', 'Détaillé'])
        self.length_combo.setToolTip(tr('Détaillé conserve les passagers et les informations facultatives. Ces détails sont rarement utiles à l’ATC ; privilégiez les informations nécessaires au vol.'))
        self.emoji_combo = ChoiceBox()
        self.emoji_combo.addItems(EMOJI_STYLES)
        self.aligned = QCheckBox(tr('Encadrés alignés'))
        self.aligned.setToolTip(tr("Discord utilisera une police monospace. Les marques techniques ne sont pas affichées dans l'aperçu ; elles disparaissent au rendu Discord."))
        designs = QPushButton(tr('Personnaliser…'))
        menu = QMenu(designs)
        menu.addAction(tr('Créer un design'), lambda: self.edit_design(new=True))
        menu.addAction(tr('Modifier le design sélectionné'), self.edit_design)
        menu.addAction(tr('Éditeur de variables (expert)'), lambda: self.edit_design(expert=True))
        menu.addAction(tr('Importer un design JSON'), self.import_design)
        menu.addAction(tr('Exporter le design sélectionné'), self.export_design)
        designs.setMenu(menu)
        self.pilots_button = QPushButton(tr('Pilotes du vol (1)'))
        self.pilots_button.clicked.connect(self.edit_pilots)
        for column, (label, widget) in enumerate(((tr('Design'), self.design_combo), (tr('Longueur'), self.length_combo), (tr('Emojis'), self.emoji_combo))):
            caption = QLabel(label, objectName='muted')
            caption.setBuddy(widget)
            settings.addWidget(caption, 0, column)
            settings.addWidget(widget, 1, column)
            settings.setColumnStretch(column, 1)
        settings.addWidget(self.aligned, 0, 3)
        settings.addWidget(designs, 1, 3)
        presentation_bar.addWidget(self.pilots_button)
        outer.addLayout(presentation_bar)
        outer.addWidget(self.presentation_panel)
        self.presentation_panel.setVisible(self._presentation_expanded)
        self.presentation_toggle.toggled.connect(self._toggle_presentation)
        for combo in (self.design_combo, self.length_combo, self.emoji_combo):
            combo.currentIndexChanged.connect(self._presentation_changed)
        self.aligned.toggled.connect(self._presentation_changed)
        split = self.main_split = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(16)
        split.setChildrenCollapsible(False)
        left_card, left = self._card()
        right_card, right = self._card()
        split.addWidget(left_card)
        split.addWidget(right_card)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        split.setSizes([600, 580])
        outer.addWidget(split, 1)
        left.addWidget(QLabel(tr('01  Préparer le vol'), objectName='section'))
        self.flight_summary = QLabel(objectName='routeSummary')
        self.flight_summary.setWordWrap(True)
        left.addWidget(self.flight_summary)
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
        left.insertLayout(2, flight_select)
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
        generate.setToolTip(tr('Recrée le message depuis le formulaire et remplace les modifications manuelles. Ctrl+Entrée'))
        generate.clicked.connect(self.generate_message)
        clear = self.clear_button = QPushButton(tr('Effacer le vol'))
        clear.setToolTip(tr('Vide le vol et les messages courants. Les pilotes mémorisés, préférences et vols sauvegardés sont conservés.'))
        clear.setProperty('variant', 'quiet')
        clear.clicked.connect(self.clear_current_message)
        form_actions.addWidget(generate)
        form_actions.addWidget(clear)
        form_actions.addStretch()
        left.addLayout(form_actions)
        library = QPushButton(tr('Favoris et historique'))
        library.setToolTip(tr('Un favori conserve un modèle de vol ; l’historique retrouve les messages copiés.'))
        library_menu = QMenu(library)
        library_menu.addAction(tr('Sauver un favori'), self.save_preset)
        library_menu.addAction(tr('Charger un favori'), self.load_preset)
        library_menu.addSeparator()
        library_menu.addAction(tr('Historique'), self.open_history)
        library.setMenu(library_menu)
        form_actions.addWidget(library)
        result_header = QHBoxLayout()
        result_header.addWidget(QLabel(tr('02  Aperçu Discord'), objectName='section'))
        result_header.addStretch()
        self.emoji_label = QLabel(tr('0 / 6 emojis'), objectName='muted')
        counters = QHBoxLayout()
        counters.addWidget(self.emoji_label)
        self.character_label = QLabel('', objectName='muted')
        counters.addStretch()
        counters.addWidget(self.character_label)
        right.addLayout(result_header)
        right.addLayout(counters)
        self.preview = QPlainTextEdit(objectName="discordPreview")
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.preview.setPlaceholderText(tr('Le message se construit pendant la saisie…'))
        font = QFont('Consolas', 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.preview.setFont(font)
        self.preview.setAccessibleName(tr('Aperçu Discord'))
        self.preview.document().setDocumentMargin(16)
        self.preview.textChanged.connect(self._preview_edited)
        right.addWidget(self.preview, 1)
        self.issues = QLabel('', objectName='danger')
        self.issues.setWordWrap(True)
        self.issues.setTextFormat(Qt.TextFormat.RichText)
        self.issues.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.issues.setOpenExternalLinks(False)
        self.issues.setToolTip(tr('Cliquez sur un avertissement pour ouvrir le champ à corriger.'))
        self.issues.linkActivated.connect(self.focus_validation_issue)
        right.addWidget(self.issues)
        self.status = QLabel(tr("Aperçu en direct. Le message n'est jamais envoyé automatiquement."), objectName='muted')
        self.status.setWordWrap(True)
        right.addWidget(self.status)
        self.strict_validation = QCheckBox(tr('Vérifier avant copie'))
        self.strict_validation.setToolTip(tr('Activé : les champs requis et les limites sont obligatoires. Désactivé : copiez votre texte tel quel, même incomplet ; les avertissements restent visibles.'))
        self.strict_validation.toggled.connect(self._copy_policy_changed)
        right.addWidget(self.strict_validation)
        copy_row = QHBoxLayout()
        self.copy_button = QPushButton(tr('Copier le message'), objectName='copy')
        self.copy_button.setToolTip(tr('Copier le message — Ctrl+Maj+C'))
        self.copy_button.clicked.connect(self.copy_message)
        copy_row.addWidget(self.copy_button)
        self.copy_button.setMinimumHeight(44)
        right.addLayout(copy_row)
        from flightdeck import install_shell
        install_shell(self, root)
        self.help_menu.addSeparator()
        from update_dialog import tx
        self._update_action = self.help_menu.addAction(tx('Mises à jour…', 'Updates…'), self.open_updates)
        self.help_menu.addAction(tx('Exporter mes données PC / Android…', 'Export my PC / Android data…'), self.export_shared_backup)
        self.help_menu.addAction(tx('Importer une sauvegarde PC / Android…', 'Import a PC / Android backup…'), self.import_shared_backup)
        self._refresh_update_action()

    def _toggle_presentation(self, expanded):
        self._presentation_expanded = expanded
        self.presentation_panel.setVisible(expanded)
        self.presentation_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def _load_top_state(self) -> None:
        self._building = True
        self.message_type.setCurrentText(self.store.state.get('message_type', 'ATC REQUEST'))
        self.pilot_name.setCurrentText(self.store.state.get('pilot_name', 'n1chita'))
        self.strict_validation.setChecked(self.store.state.get('strict_validation', True) is not False)
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
        if key == 'aircraft' and scope == 'flight':
            from aircraft_picker import AircraftPicker
            from fuel.calculator import load_json
            widget = AircraftPicker(allow_custom=True)
            widget.addItem(tr('Choisir un avion / variante…'), None)
            for record in load_json('aircraft_fuel_data.json')['aircraft']:
                widget.addItem(record['name'],record['id'])
            current = str(value or '')
            if current and widget.findText(current) < 0:
                widget.addItem(current, None) # Keep historical/manual display until an explicit choice.
            widget.setCurrentIndex(max(0,widget.findText(current)))
            widget.currentTextChanged.connect(lambda text: self._field_changed('flight','aircraft',text))
        elif field.kind == 'flag':
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
            row_widget = widget
            if key == 'fuel':
                row_widget = QWidget()
                fuel_row = QHBoxLayout(row_widget)
                fuel_row.setContentsMargins(0, 0, 0, 0)
                fuel_row.setSpacing(8)
                fuel_row.addWidget(widget, 1)
                calculate = QPushButton(tr('Calculer le fuel'))
                calculate.setObjectName('calculateCurrentFlightFuel')
                calculate.setToolTip(tr('Ouvrir le calculateur avec l’avion, la durée totale et l’arrivée de ce vol.'))
                calculate.clicked.connect(self.open_fuel)
                fuel_row.addWidget(calculate)
                # Validation and keyboard focus still belong to the input.
                widget._form_row = row_widget
                row_widget._form_input = widget
            self.flight_form.addRow(tr('{v0}{v1}', v0=tr(field.label), v1=' *' if required else ''), row_widget)
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
                    field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                    if field_item and field_item.widget():
                        field_widget = getattr(field_item.widget(), '_form_input', field_item.widget())
                        label.setBuddy(field_widget)
                        field_widget.setAccessibleName(label.text())
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
            if key == 'aircraft':
                from fuel.calculator import find_aircraft, load_json
                record = find_aircraft(value,load_json('aircraft_fuel_data.json')['aircraft'])
                self.store.state['flight'].pop('fuel_calculation',None)
                self.store.state['flight'].pop('fuel_aircraft_id',None)
                if record:
                    self.store.state['flight']['fuel_aircraft_id'] = record['id']
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
        self.store.state.pop('android_message_type', None)
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
        self.presentation_summary.setText(' / '.join(combo.itemText(combo.currentIndex()) for combo in (self.design_combo, self.length_combo, self.emoji_combo)))
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

    def _copy_policy_changed(self, checked):
        if self._building:
            return
        self.store.state['strict_validation'] = checked
        self.save_state()
        self._refresh_validation()

    def focus_validation_issue(self, link='issue-0'):
        """Use the same navigation for warning links and a blocked copy."""
        from flightdeck import show_page
        show_page(self, 1)
        try:
            issue = self.validation_problems[int(str(link).removeprefix('issue-'))]
        except (ValueError, IndexError):
            self.preview.setFocus()
            return
        widget = self.flight_widgets.get(issue.field) or self.type_widgets.get(issue.field)
        if issue.field == 'pilot_name':
            widget = self.pilot_name
        elif issue.field == 'pilots':
            widget = self.pilots_button
        elif issue.field in ('design', 'length', 'emoji'):
            if issue.field == 'design':
                self.presentation_toggle.setChecked(True)
                self._toggle_presentation(True)
                widget = self.design_combo
            else:
                widget = self.preview
        if widget:
            widget.setFocus(Qt.FocusReason.OtherFocusReason)
            if self.form_scroll.widget().isAncestorOf(widget):
                self.form_scroll.ensureWidgetVisible(widget, 20, 45)
            QToolTip.showText(widget.mapToGlobal(widget.rect().center()), tr(issue.text), widget)

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
            shown = [f'<a href="issue-{i}" style="color: inherit">{escape(tr(issue.text))}</a>' for i, issue in enumerate(problems)]
            hint = tr('Copie libre : avertissements facultatifs.') if not self.strict_validation.isChecked() else tr('À compléter : ')
            self.issues.setText(escape(hint) + '<br>' + '<br>'.join(shown))
        else:
            self.issues.setText(tr('Prêt à copier.'))
            self.issues.setObjectName('muted')
        self.issues.style().unpolish(self.issues)
        self.issues.style().polish(self.issues)
        self.validation_problems = problems
        from flightdeck import refresh
        refresh(self)
        self.can_copy = bool(self.preview.toPlainText().strip()) and (not self.strict_validation.isChecked() or not problems)
        self.copy_button.setEnabled(True)
        for form, widgets in ((self.flight_form, self.flight_widgets), (self.message_form, self.type_widgets)):
            for key, widget in widgets.items():
                errors = [p.text for p in problems if p.field == key]
                is_invalid = bool(errors)
                widget.setAccessibleDescription(' • '.join(errors))
                if bool(widget.property('invalid')) != is_invalid:
                    widget.setProperty('invalid', is_invalid)
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                label = form.labelForField(getattr(widget, '_form_row', widget))
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
            from flightdeck import show_page
            show_page(self, 1)
            self.issues.setStyleSheet('color: #ef4444; font-weight: 700;')
            QTimer.singleShot(650, self.issues, lambda: self.issues.setStyleSheet(''))
            self.focus_validation_issue()
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

    def save_state(self) -> bool:
        try:
            self.store.save_state()
            return True
        except Exception:
            LOGGER.exception('Autosauvegarde impossible')
            self.status.setText(tr('Autosauvegarde impossible. La saisie reste affichée.'))
            return False

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
        for kind in set(FLIGHT_TYPES) | set(item.get('per_type', {})):
            self.store.state['per_type'][kind] = {**defaults.get(kind, {}), **deepcopy(item.get('per_type', {}).get(kind, {}))}
        self.store.state['preview_edits'] = {}
        if 'preview_edits' in item:
            self.store.state['preview_edits'] = deepcopy(item['preview_edits'])
        if isinstance(item.get('presentation'), dict):
            self.store.state['presentation'] = deepcopy(item['presentation'])
        if item.get('pilot_name'):
            self.store.state['pilot_name'] = item['pilot_name']
        if item.get('message_type'):
            chosen_type = item['message_type']
            supported = chosen_type in MESSAGE_TYPES
            self.store.state['message_type'] = chosen_type if supported else 'ATC REQUEST'
            if not supported:
                self.store.state['android_message_type'] = chosen_type
            else:
                self.store.state.pop('android_message_type', None)
            self._load_top_state()
        elif 'presentation' in item or 'pilot_name' in item:
            self._load_top_state()
        self._rebuild_forms()
        saved = self.save_state()
        if saved:
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
        saved = self.save_state()
        if saved:
            self.status.setText(tr('Nouveau vol. Les anciens vols enregistrés restent disponibles.'))

    def open_feedback_form(self):
        from report_dialog import open_feedback_form
        if not open_feedback_form():
            QMessageBox.warning(self, tr('Formulaire en ligne'), tr('Impossible d’ouvrir le navigateur. Réessayez ou exportez un rapport local.'))

    def open_report(self):
        from report_dialog import ReportDialog
        ReportDialog(self).exec()

    def open_finder(self, countries=None):
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
                from route_map import default_database
                path = default_database() or local_db
            dialog = FinderDialog(self, path, self.store.state['language'])
            if isinstance(countries, dict):
                for key in ('origin_country', 'destination_country'):
                    dialog.fields[key].setText(countries.get(key) or '')
                dialog.advanced_toggle.setChecked(True)
                QTimer.singleShot(0, dialog.run_search)
            dialog.selected.connect(self.use_found_flight)
            dialog.exec()
            self.store.state['finder_database'] = str(dialog.path)
            self.route_map.set_database_path(dialog.path)
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
        from flightdeck import show_page
        show_page(self, 0)
        saved = self.save_state()
        if saved:
            from finder.i18n import tr as finder_tr
            from finder.provenance import duration_provenance
            origin = duration_provenance(result)
            kind = ('duration_observed' if origin == 'AGGREGATED_COMPLETE_TRACKS' else
                    'duration_estimated' if origin == 'ESTIMATED_DISTANCE_HEURISTIC' else 'duration_unverified')
            self.status.setText(tr('Vol Finder chargé. Vérifiez les pistes, portes, carburant et autres pilotes conservés. Distance = référence orthodromique. {duration}.',
                                   duration=finder_tr(kind, self.store.state['language'])))

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
        saved = self.save_state()
        if saved:
            self.status.setText(tr('Carburant RFS appliqué : ') + result['display']['total_block_fuel'] + tr(' — estimation pour simulation uniquement, jamais pour un vol réel.'))

    def save_current_flight(self) -> None:
        from update_dialog import tx
        flight = deepcopy(self.store.state['flight'])
        proposed = flight.get('callsign') or f"{flight.get('departure_icao') or tx('Départ', 'Departure')} → {flight.get('arrival_icao') or tx('Arrivée', 'Arrival')}"
        name, ok = QInputDialog.getText(self, tr('Enregistrer le vol'), tr('Nom du vol :'), text=proposed)
        if not ok or not name.strip():
            return
        flight_id = self.store.state.get('current_flight_id') or uuid.uuid4().hex
        previous_saved = deepcopy(self.store.state['saved_flights'])
        previous_id = self.store.state.get('current_flight_id', '')
        item = {'id': flight_id, 'label': name.strip(), 'flight': flight,
                'per_type': deepcopy(self.store.state['per_type']),
                'message_type': self.store.state.get('android_message_type') or self.store.state['message_type'],
                'pilot_name': self.store.state['pilot_name'],
                'presentation': deepcopy(self.store.state['presentation']),
                'preview_edits': deepcopy(self.store.state.get('preview_edits', {}))}
        saved = self.store.state['saved_flights']
        for index, previous in enumerate(saved):
            if previous.get('id') == flight_id:
                saved[index] = item
                break
        else:
            saved.append(item)
        self.store.state['current_flight_id'] = flight_id
        self._remember_frequent_values({})
        if not self.save_state():
            self.store.state['saved_flights'] = previous_saved
            self.store.state['current_flight_id'] = previous_id
            self._refresh_saved_flights()
            return
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
        if not self.save_state():
            return
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
        if self.save_state():
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
            if self.save_state():
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
        # Let the new palette paint before a possibly slow OneDrive disk write.
        self.save_timer.start(250)

    def change_visual_theme(self, *_):
        self.store.state['visual_theme'] = self.visual_theme_combo.currentData()
        self._apply_theme()
        self.save_timer.start(250)

    def _apply_theme(self) -> None:
        dark = self.store.state.get('theme', 'Sombre') == 'Sombre'
        identity = self.store.state.get('visual_theme', 'avionique')
        from flightdeck import deck_style, tx
        self.setUpdatesEnabled(False)
        try:
            apply_palette(QApplication.instance(), dark, identity)
            if getattr(self, '_styled_dark', None) != dark or getattr(self, '_styled_identity', None) != identity:
                self.setStyleSheet(colourize_stylesheet(get_stylesheet(dark) + deck_style(dark), dark, identity))
                self._styled_dark = dark
                self._styled_identity = identity
            self.route_map.set_dark(dark)
            self.theme_button.setText(tx('Clair', 'Light') if dark else tx('Sombre', 'Dark'))
        finally:
            self.setUpdatesEnabled(True)

    def closeEvent(self, event) -> None:
        self.preview_timer.stop()
        self.save_timer.stop()
        self.copy_feedback_timer.stop()
        if self.save_state():
            event.accept()
        else:
            event.ignore()

    def reset_copy_feedback(self):
        self.copy_feedback_timer.stop()
        self.copy_button.setText(tr('Copier le message'))

    def change_language(self, *_):
        update_was_open = self.update_dialog is not None
        if self.update_dialog:
            self.update_dialog.close()
        help_topic = self.help_dialog.topics.currentData() if self.help_dialog else None
        if self.help_dialog:
            self.help_dialog.close()
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
        self.route_map.set_dark(dark)
        from flightdeck import tx
        self.theme_button.setText(tx('Clair', 'Light') if dark else tx('Sombre', 'Dark'))
        self.render_preview()
        self.save_state()
        old.deleteLater()
        if help_topic:
            self.open_help(help_topic)
        if update_was_open:
            self.open_updates()

    def _refresh_update_action(self):
        from update_dialog import tx
        from updates import is_newer_release
        available = is_newer_release(self.update_preferences['last_result'])
        self._update_action.setText(tx('Nouvelle version disponible…', 'New version available…') if available else tx('Mises à jour…', 'Updates…'))

    def open_updates(self):
        from update_dialog import UpdateDialog
        if self.update_dialog:
            self.update_dialog.close()
        dialog = UpdateDialog(self)
        self.update_dialog = dialog
        dialog.finished.connect(lambda _: setattr(self, 'update_dialog', None) if self.update_dialog is dialog else None)
        dialog.show()

    @Slot()
    def check_updates(self, manual=False):
        from update_dialog import start_worker
        from updates import should_auto_check
        import time
        if self._update_running or (not manual and (not self.isVisible() or not should_auto_check(self.update_preferences))):
            return
        self.update_preferences['last_attempt'] = time.time()
        self._update_running = True
        self._update_worker = start_worker(self._updates_finished, self.update_preferences)
        if self.update_dialog:
            self.update_dialog.refresh()

    def set_update_auto(self, enabled):
        from update_dialog import start_preferences_worker
        if self._update_preferences_running:
            return
        previous = self.update_preferences['enabled']
        self.update_preferences['enabled'] = bool(enabled)
        self._update_preferences_running = True
        self._update_preferences_worker = start_preferences_worker(self._update_preferences_finished, self.update_preferences, previous)

    @Slot(object)
    def _update_preferences_finished(self, result):
        from update_dialog import tx
        self._update_preferences_running = False
        if not result['ok']:
            self.update_preferences['enabled'] = result['previous_enabled']
        if self.update_dialog:
            self.update_dialog.automatic.blockSignals(True)
            self.update_dialog.automatic.setChecked(self.update_preferences['enabled'])
            self.update_dialog.automatic.blockSignals(False)
            self.update_dialog.refresh()
            if not result['ok']:
                self.update_dialog.status.setText(tx('Le réglage n’a pas pu être sauvegardé.', 'The preference could not be saved.'))

    @Slot(object)
    def _updates_finished(self, result):
        from update_dialog import result_text, tx
        self._update_running = False
        self.update_preferences['last_result'] = result
        self._refresh_update_action()
        if result.get('status') == 'available':
            self.status.setText(result_text(result) + tx(' Ouvrez Aide → Mises à jour.', ' Open Help → Updates.'))
        if self.update_dialog:
            self.update_dialog.refresh()

    def export_shared_backup(self):
        from update_dialog import tx
        filename, _ = QFileDialog.getSaveFileName(self, tx('Exporter mes données', 'Export my data'), 'RFSFlightdeck-backup.json', 'JSON (*.json)')
        if not filename:
            return
        try:
            from storage import save_json
            payload = self.store.export_backup()
            save_json(Path(filename), json.loads(payload))
            self.status.setText(tx('Sauvegarde exportée. Vous pouvez l’importer sur PC ou Android.', 'Backup exported. You can import it on PC or Android.'))
        except (OSError, ValueError, TypeError):
            LOGGER.exception('Shared backup export failed')
            QMessageBox.warning(self, tx('Sauvegarde', 'Backup'), tx('La sauvegarde n’a pas pu être écrite. Choisissez un autre emplacement.', 'The backup could not be written. Choose another location.'))

    def import_shared_backup(self):
        from update_dialog import tx
        filenames, _ = QFileDialog.getOpenFileNames(self, tx('Importer une sauvegarde ou les quatre fichiers PC', 'Import a backup or the four PC files'), '', 'JSON (*.json)')
        if not filenames:
            return
        try:
            from backup_bundle import MAX_BYTES
            paths = [Path(filename) for filename in filenames]
            if sum(path.stat().st_size for path in paths) > MAX_BYTES:
                raise ValueError('Backup too large')
            legacy_names = {'rfs_state.json', 'rfs_history.json', 'rfs_presets.json', 'rfs_designs.json'}
            legacy = len(paths) > 1 or paths[0].name in legacy_names
            if legacy:
                if any(path.name not in legacy_names for path in paths) or len({path.name for path in paths}) != len(paths):
                    raise ValueError('Unexpected legacy file selection')
                content = {path.name: path.read_text(encoding='utf-8-sig') for path in paths}
            else:
                content = paths[0].read_text(encoding='utf-8-sig')
            preview = self.store.preview_import(content)
            summary = preview['summary']
            description = tx('Cette sauvegarde contient :', 'This backup contains:') + '\n\n' + '\n'.join((
                tx('Vols sauvegardés : ', 'Saved flights: ') + str(summary['saved_flights']),
                tx('Pilotes : ', 'Pilots: ') + str(summary['pilots']),
                tx('Historique : ', 'History: ') + str(summary['history']),
                tx('Favoris : ', 'Favourites: ') + str(summary['presets']),
                tx('Designs : ', 'Designs: ') + str(summary['designs']),
            )) + '\n\n' + tx('Fusionner conserve vos réglages et votre vol actuel, puis ajoute les données manquantes. Remplacer reprend les réglages et le vol de la sauvegarde. Une copie de sécurité locale est créée avant l’import.', 'Merge keeps your settings and current flight, then adds missing data. Replace loads the settings and flight from the backup. A local safety copy is created before importing.')
            if legacy and set(content) != legacy_names:
                description += '\n\n' + tx('Vous n’avez pas sélectionné les quatre anciens fichiers PC. Seules les données présentes seront importées ; choisissez Fusionner pour conserver les autres.', 'You have not selected all four legacy PC files. Only included data will be imported; choose Merge to keep the rest.')
            question = QMessageBox(self)
            question.setWindowTitle(tx('Importer mes données', 'Import my data'))
            question.setText(description)
            question.setTextFormat(Qt.TextFormat.PlainText)
            merge = question.addButton(tx('Fusionner', 'Merge'), QMessageBox.ButtonRole.AcceptRole)
            replace = question.addButton(tx('Remplacer', 'Replace'), QMessageBox.ButtonRole.DestructiveRole)
            question.addButton(tx('Annuler', 'Cancel'), QMessageBox.ButtonRole.RejectRole)
            question.setDefaultButton(merge)
            question.exec()
            selected = question.clickedButton()
            if selected not in (merge, replace):
                return
            self.preview_timer.stop()
            self.save_timer.stop()
            if not self.save_state():
                return
            result = self.store.import_backup(content, mode='merge' if selected is merge else 'replace')
            # Rebuild language/theme/form consistently, preserving device-local update consent.
            selected_language = self.store.state.get('language', 'fr')
            set_language(selected_language)
            self._building = True
            old = self.takeCentralWidget()
            self._build_ui()
            self._load_top_state()
            self._rebuild_forms()
            self._apply_theme()
            self.render_preview()
            old.deleteLater()
            self.status.setText(tx('Données importées. Copie de sécurité : ', 'Data imported. Safety copy: ') + result['backup_path'])
        except (OSError, ValueError, TypeError, KeyError):
            LOGGER.exception('Shared backup import failed')
            QMessageBox.warning(self, tx('Sauvegarde', 'Backup'), tx('Impossible d’importer cette sauvegarde. Vérifiez le fichier ; les données existantes sont conservées ou restaurées en cas d’erreur.', 'This backup could not be imported. Check the file; existing data is kept or restored if an error occurs.'))

    def show_welcome(self):
        if not self.store.state.get('intro_seen'):
            if not self.store.state.get('joke_seen'):
                selection, ok = QInputDialog.getItem(self, 'Français / English', tr('Langue de l’interface'), ['Français', 'English'], 0, False)
                if ok:
                    self.language_combo.setCurrentIndex(1 if selection == 'English' else 0)
                # Independent of the welcome checkbox, and saved before opening.
                self.store.state['joke_seen'] = True
                self.save_state()
                self.replay_joke()
            dialog = WelcomeDialog(self)
            dialog.exec()
            self.store.state['intro_seen'] = dialog.remember.isChecked()
            self.save_state()

        if not self.store.state.get('tutorial_seen'):
            self.open_help('flight', offer=True)

    def open_help(self, topic='flight', offer=False):
        from help_dialog import FlightdeckHelpDialog
        if self.help_dialog:
            self.help_dialog.close()
        dialog = FlightdeckHelpDialog(self, topic, offer)
        self.help_dialog = dialog
        dialog.finished.connect(lambda _: setattr(self, 'help_dialog', None) if self.help_dialog is dialog else None)
        dialog.show()

    def replay_joke(self):
        dialog = JokeDialog(self)
        dialog.exec()
        if dialog.revealed:
            QMessageBox.information(self, tr('I was kidding !'), tr("C'était une blague ! Aucun paiement ni aucune donnée bancaire : l'application est gratuite. Bienvenue à bord !"))

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
            design = validate_design(value)
            key = uuid.uuid4().hex
            self.store.save_design(key, design)
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
