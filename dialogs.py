from i18n import tr, set_language, language
"""Éditeurs locaux des pilotes et des designs personnels."""
from copy import deepcopy
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTabWidget, QVBoxLayout, QWidget
from message_builder import PILOT_FIELDS
from localized_widgets import ChoiceBox
from rfs_schema import FLIGHT_FIELDS, MESSAGE_FIELDS, FLIGHT_TYPES

class PilotsDialog(QDialog):

    def __init__(self, flight, primary_name, parent=None, library=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Pilotes du vol'))
        self.resize(720, 760)
        self.rows = []
        self.library = library or []
        self.primary_name = primary_name
        self.type_checks = {}
        layout = QVBoxLayout(self)
        explanation = QLabel(tr('Pilote principal : {v0}\nLa route et les données du vol sont communes. Chaque pilote garde son callsign.\nUn champ optionnel vide reprend la valeur commune. Une piste distincte est requise en parallèle.', v0=primary_name))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        modes = QFormLayout()
        self.departure_mode, self.arrival_mode = (ChoiceBox(), ChoiceBox())
        for combo, key in ((self.departure_mode, 'departure_mode'), (self.arrival_mode, 'arrival_mode')):
            combo.addItems(['Indépendant', 'En groupe', 'Parallèle', 'Décalé'])
            combo.setCurrentText(flight.get(key, 'Indépendant'))
        modes.addRow(tr('Décollage'), self.departure_mode)
        modes.addRow(tr('Arrivée / approche'), self.arrival_mode)
        layout.addLayout(modes)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget(objectName='formBody')
        self.pilot_layout = QVBoxLayout(content)
        self.pilot_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.flight = flight
        for pilot in flight.get('pilots', []):
            if isinstance(pilot, dict):
                self.add_pilot(pilot)
        saved_row = QHBoxLayout()
        self.saved_pilots = QComboBox()
        self.saved_pilots.addItem(tr('Choisir un pilote mémorisé…'), None)
        for person in self.library:
            if person.get('name', '').casefold() != primary_name.casefold():
                self.saved_pilots.addItem(person.get('name', ''), person)
        saved_row.addWidget(self.saved_pilots, 1)
        use_saved = QPushButton(tr('Ajouter au vol'))
        use_saved.clicked.connect(self.add_saved)
        saved_row.addWidget(use_saved)
        layout.addLayout(saved_row)
        add = QPushButton(tr('+ Ajouter un pilote'))
        add.clicked.connect(lambda: self.add_pilot({}))
        layout.addWidget(add)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr('Appliquer'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Annuler'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_pilot(self, values):
        box = QGroupBox(tr('Pilote supplémentaire'))
        form = QFormLayout(box)
        widgets = {}
        for key in PILOT_FIELDS:
            label = tr('Pseudo RFS *') if key == 'name' else tr(FLIGHT_FIELDS[key].label) + (' *' if key == 'callsign' else '')
            edit = QLineEdit(str(values.get(key, '')))
            if key not in ('name', 'callsign'):
                edit.setPlaceholderText(tr('Commun : {v0}', v0=self.flight.get(key) or 'non renseigné'))
            form.addRow(tr(label), edit)
            widgets[key] = edit
        selection = QWidget()
        selection_layout = QVBoxLayout(selection)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        checks = {}
        for kind in FLIGHT_TYPES:
            check = QCheckBox(kind)
            check.setChecked(kind in values.get('message_types', FLIGHT_TYPES))
            checks[kind] = check
            selection_layout.addWidget(check)
        form.addRow(tr('Afficher dans ces messages'), selection)
        self.type_checks[box] = checks
        remove = QPushButton(tr('Retirer ce pilote'))
        row = (box, widgets)

        def remove_row():
            self.rows.remove(row)
            self.type_checks.pop(box, None)
            box.setParent(None)
            box.deleteLater()
        remove.clicked.connect(remove_row)
        form.addRow(remove)
        self.rows.append(row)
        self.pilot_layout.insertWidget(self.pilot_layout.count() - 1, box)

    def values(self):
        return {'pilots': [{**{key: edit.text().strip() for key, edit in edits.items()}, 'message_types': [kind for kind, check in self.type_checks[box].items() if check.isChecked()]} for box, edits in self.rows], 'departure_mode': self.departure_mode.currentText(), 'arrival_mode': self.arrival_mode.currentText()}

    def add_saved(self):
        person = self.saved_pilots.currentData()
        if not person:
            return
        if any((edits['name'].text().strip().casefold() == person.get('name', '').casefold() for _, edits in self.rows)):
            return
        self.add_pilot(person)

class JokeDialog(QDialog):
    """Non-editable payment-form prop. Reveal BEFORE processing any input."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.revealed = False
        self.setWindowTitle(tr('Votre accès à bord'))
        self.resize(560, 520)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr('Une dernière formalité…'), objectName='title'))
        layout.addWidget(QLabel(tr('Votre carte bancaire pour continuer ?')))
        form = QFormLayout()
        self.props = []
        for label, placeholder in (('Numéro de carte', '•••• •••• •••• ••••'), ('Expiration', 'MM / AA'), ('Code de sécurité', '•••'), ('Prénom', ''), ('Nom', ''), ('Adresse de facturation', '')):
            field = QLineEdit()
            field.setReadOnly(True)
            field.setPlaceholderText(placeholder)
            field.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            field.installEventFilter(self)
            self.props.append(field)
            form.addRow(tr(label), field)
        layout.addLayout(form)
        notice = QLabel(tr('Formulaire de démonstration : aucune donnée bancaire ne peut être saisie ni enregistrée.'))
        notice.setWordWrap(True)
        layout.addWidget(notice)
        button = QPushButton(tr('Continuer'))
        button.clicked.connect(self.reveal)
        layout.addWidget(button)
        self.installEventFilter(self)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Qt can send an empty input-method event when focus is initialised.
        # That is not a user's attempt to type and must not dismiss the prop.
        entered_text = event.type() == QEvent.Type.InputMethod and bool(event.commitString() or event.preeditString())
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress) or entered_text:
            self.reveal()
            return True
        return super().eventFilter(watched, event)

    def reveal(self):
        if not self.revealed:
            self.revealed = True
            self.accept()

    def reject(self):
        self.reveal()

class WelcomeDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr('Bienvenue à bord'))
        self.resize(560, 370)
        layout = QVBoxLayout(self)
        title = QLabel(tr('Bienvenue à bord !'), objectName='title')
        layout.addWidget(title)
        joke = QLabel(tr("L'application est gratuite.\nAucune carte, aucun paiement, aucune donnée bancaire."))
        joke.setWordWrap(True)
        layout.addWidget(joke)
        help_text = QLabel(tr("1. Renseignez votre vol, puis choisissez un type de message.\n2. Ajoutez vos amis dans « Pilotes du vol » si nécessaire.\n3. Choisissez un design et cliquez sur « Copier le message ».\n\nVos vols, favoris et designs restent sur votre PC.\nL'option « Alignement Discord » garde les encadrés centrés."))
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.remember = QCheckBox(tr('Ne plus afficher cette introduction'))
        self.remember.setChecked(True)
        layout.addWidget(self.remember)
        button = QPushButton(tr('Continuer gratuitement'))
        button.clicked.connect(self.accept)
        layout.addWidget(button)

class UnifiedDesignDialog(QDialog):

    def __init__(self, design=None, parent=None):
        super().__init__(parent)
        from message_builder import BUILTIN_DESIGNS, compose, preview_text
        self.setWindowTitle(tr('Créer / Personnaliser un design'))
        self.resize(1020, 680)
        self.setMinimumSize(850, 550)
        design = design or {}

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        name_row = QHBoxLayout()
        name_label = QLabel(tr('Nom du design :'))
        name_label.setStyleSheet('font-weight: 700; font-size: 14px;')
        self.name = QLineEdit(design.get('name', tr('Mon design')))
        self.name.textChanged.connect(self.refresh)
        name_row.addWidget(name_label)
        name_row.addWidget(self.name, 1)
        main_layout.addLayout(name_row)

        split = QSplitter(Qt.Orientation.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)

        self.tabs = QTabWidget()

        # Tab 1: Mode Guidé
        guided_tab = QWidget()
        guided_layout = QVBoxLayout(guided_tab)
        guided_form = QFormLayout()

        self.base = QComboBox()
        for b_name in BUILTIN_DESIGNS:
            self.base.addItem(tr(b_name), b_name)
        self.base.setCurrentIndex(max(0, self.base.findData(design.get('base_design', 'Carte'))))
        self.base.currentIndexChanged.connect(self.refresh)

        self.heading = QLineEdit(design.get('heading', ''))
        self.heading.setPlaceholderText(tr('Ex: ✈️ BON VOL !'))
        self.heading.textChanged.connect(self.refresh)

        self.footer = QLineEdit(design.get('footer', ''))
        self.footer.setPlaceholderText(tr('Ex: Merci aux contrôleurs ATC 🙏'))
        self.footer.textChanged.connect(self.refresh)

        guided_form.addRow(tr('Présentation de base :'), self.base)
        guided_form.addRow(tr('Texte au-dessus (en-tête) :'), self.heading)
        guided_form.addRow(tr('Texte en dessous (pied) :'), self.footer)
        guided_layout.addLayout(guided_form)

        convert_btn = QPushButton(tr('➡️ Convertir en modèle avancé pour tout personnaliser'))
        convert_btn.setToolTip(tr('Conserve un message dynamique : les données suivront le prochain vol.'))
        convert_btn.clicked.connect(self.convert_to_advanced)
        guided_layout.addWidget(convert_btn)

        guided_hint = QLabel(tr('Le message complet et tous les pilotes sont conservés. Vous pouvez encadrer le résultat avec votre propre texte.'))
        guided_hint.setWordWrap(True)
        guided_hint.setObjectName('muted')
        guided_layout.addWidget(guided_hint)
        guided_layout.addStretch()

        self.tabs.addTab(guided_tab, tr('⚡ Mode Guidé'))

        # Tab 2: Mode Modèle Avancé
        advanced_tab = QWidget()
        adv_layout = QVBoxLayout(advanced_tab)
        adv_layout.setSpacing(8)

        adv_help = QLabel(tr('Composez librement votre message avec les variables. Cliquez pour insérer :'))
        adv_help.setWordWrap(True)
        adv_layout.addWidget(adv_help)

        token_bar = QHBoxLayout()
        self.tokens = QComboBox()
        keys = ['message', 'message_type', 'pilot', 'pilots'] + list(FLIGHT_FIELDS)
        keys += sorted({key for fields in MESSAGE_FIELDS.values() for key in fields} - set(keys))
        self.tokens.addItems(['{{' + key + '}}' for key in keys])
        insert_var = QPushButton(tr('Insérer variable'))
        insert_var.clicked.connect(lambda: self.template.insertPlainText(self.tokens.currentText()))
        token_bar.addWidget(self.tokens, 1)
        token_bar.addWidget(insert_var)
        adv_layout.addLayout(token_bar)

        emoji_bar = QHBoxLayout()
        self.emojis = QComboBox()
        self.emojis.addItems(['✈️', '🛩️', '🛫', '🛬', '📡', '📻', '🎧', '🎙️', '🟢', '🔴', '⏱️', '🎨', '🙏', '🤝', '👤', '🌐', '📍', '🏁', '📦', '🌙', '🌊'])
        insert_emoji = QPushButton(tr('Insérer'))
        insert_emoji.clicked.connect(lambda: self.template.insertPlainText(self.emojis.currentText()))
        emoji_bar.addWidget(self.emojis, 1)
        emoji_bar.addWidget(insert_emoji)
        adv_layout.addLayout(emoji_bar)

        initial_template = design.get('template', '{{message}}')
        self.template = QPlainTextEdit(initial_template)
        self.template.setPlaceholderText(tr('Écrivez votre modèle ici avec {{variables}} et {{message}}...'))
        self.template.textChanged.connect(self.refresh)
        adv_layout.addWidget(self.template, 1)

        load_current_btn = QPushButton(tr('Copier le texte actuel (figé) dans le modèle'))
        load_current_btn.clicked.connect(self.load_current_message)
        adv_layout.addWidget(load_current_btn)

        self.tabs.addTab(advanced_tab, tr('🛠️ Modèle Avancé (Sur-mesure)'))

        if design and (not design.get('guided', True)):
            self.tabs.setCurrentIndex(1)

        self.tabs.currentChanged.connect(self.refresh)
        left_layout.addWidget(self.tabs)
        split.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)

        preview_group = QGroupBox(tr('Aperçu Discord en direct'))
        preview_box = QVBoxLayout(preview_group)
        self.preview = QPlainTextEdit(objectName='discordPreview')
        self.preview.setReadOnly(True)
        preview_box.addWidget(self.preview)
        right_layout.addWidget(preview_group)
        split.addWidget(right_widget)

        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        main_layout.addWidget(split, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr('Enregistrer le design'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Annuler'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        self.refresh()

    def convert_to_advanced(self):
        # Keep the flight dynamic instead of freezing its current data into a design.
        self.template.setPlainText('\n\n'.join(v for v in (self.heading.text().strip(), '{{message}}', self.footer.text().strip()) if v))
        self.tabs.setCurrentIndex(1)

    def load_current_message(self):
        from message_builder import compose, preview_text
        parent = self.parent()
        if parent and hasattr(parent, 'store'):
            state = parent.store.state
            text = preview_text(compose(state['message_type'], state['flight'], state['per_type'].get(state['message_type'], {}), state['pilot_name'], state['presentation']))
            self.template.setPlainText(text)

    def refresh(self, *_):
        from message_builder import compose, preview_text
        parent = self.parent()
        if parent and hasattr(parent, 'store'):
            state = parent.store.state
            try:
                msg = compose(state['message_type'], state['flight'], state['per_type'].get(state['message_type'], {}), state['pilot_name'], state['presentation'], self.values())
                self.preview.setPlainText(preview_text(msg))
            except Exception as e:
                self.preview.setPlainText(f"Aperçu : {e}")

    def values(self):
        is_guided = (self.tabs.currentIndex() == 0)
        name = self.name.text().strip() or tr('Mon design')
        if is_guided:
            return {
                'name': name,
                'template': '{{message}}',
                'guided': True,
                'base_design': self.base.currentData(),
                'heading': self.heading.text(),
                'footer': self.footer.text()
            }
        else:
            return {
                'name': name,
                'template': self.template.toPlainText().strip() or '{{message}}',
                'guided': False,
                'base_design': self.base.currentData()
            }

GuidedDesignDialog = UnifiedDesignDialog
DesignDialog = UnifiedDesignDialog
