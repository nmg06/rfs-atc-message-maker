"""Local, replayable desktop guide. Help content is shared with both web UIs."""
from PySide6.QtCore import Qt, QPropertyAnimation
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QScrollArea, QWidget, QGraphicsOpacityEffect)
from help_content import CONTENT
from i18n import language


class FlightdeckHelpDialog(QDialog):
    def __init__(self, parent=None, topic='flight', offer=False):
        super().__init__(parent)
        self.locale = language()
        self.offer = offer
        self.index = 0
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(self.tx('Bienvenue dans votre cockpit', 'Welcome to your cockpit'))
        self.resize(680, 620)
        layout = QVBoxLayout(self)
        title = QLabel(self.tx('✈ Découvrez Flightdeck à votre rythme', '✈ Discover Flightdeck at your pace'))
        title.setWordWrap(True)
        layout.addWidget(title)
        self.topics = QComboBox()
        for row in CONTENT['topics']:
            self.topics.addItem(row['title'][self.locale], row['id'])
        self.topics.setCurrentIndex(max(0, self.topics.findData(topic)))
        layout.addWidget(self.topics)
        self.progress = QLabel()
        self.heading = QLabel()
        self.heading.setWordWrap(True)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        for widget in (self.progress, self.heading, self.text):
            layout.addWidget(widget)
        nav = QHBoxLayout()
        self.previous = QPushButton(self.tx('Précédent', 'Previous'))
        self.next = QPushButton(self.tx('Suivant', 'Next'))
        self.try_button = QPushButton(self.tx('Ouvrir cette rubrique', 'Open this section'))
        for button in (self.previous, self.next, self.try_button):
            nav.addWidget(button)
        layout.addLayout(nav)
        self.search = QLineEdit()
        self.search.setPlaceholderText(self.tx('Rechercher parmi les 30 questions…', 'Search the 30 questions…'))
        self.search.setAccessibleName(self.tx('Questions fréquentes', 'Frequently asked questions'))
        layout.addWidget(self.search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        questions = QVBoxLayout(body)
        self.faq_rows = []
        for row in CONTENT['faq']:
            panel = QWidget()
            box = QVBoxLayout(panel)
            box.setContentsMargins(4, 5, 4, 5)
            toggle = QPushButton('▸ ' + row['question'][self.locale])
            toggle.setCheckable(True)
            answer = QLabel(row['answer'][self.locale])
            answer.setWordWrap(True)
            answer.setVisible(False)
            toggle.toggled.connect(answer.setVisible)
            box.addWidget(toggle)
            box.addWidget(answer)
            questions.addWidget(panel)
            self.faq_rows.append((panel, row, toggle, answer))
        questions.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        close = QPushButton(self.tx('Passer pour le moment', 'Skip for now') if offer else self.tx('Fermer l’aide', 'Close help'))
        layout.addWidget(close)
        close.clicked.connect(self.close)
        self.topics.currentIndexChanged.connect(self.reset_step)
        self.previous.clicked.connect(lambda: self.move(-1))
        self.next.clicked.connect(lambda: self.move(1))
        self.try_button.clicked.connect(self.open_section)
        self.search.textChanged.connect(self.filter_questions)
        self.effect = QGraphicsOpacityEffect(self.text)
        self.text.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b'opacity', self)
        self.animation.setDuration(160)
        self.animation.setStartValue(.65)
        self.animation.setEndValue(1)
        self.refresh()

    def tx(self, fr, en):
        return en if self.locale == 'en' else fr

    def reset_step(self):
        self.index = 0
        self.refresh()

    def move(self, direction):
        self.index += direction
        self.refresh()

    def refresh(self):
        topic = CONTENT['topics'][self.topics.currentIndex()]
        self.index = min(max(self.index, 0), len(topic['steps']) - 1)
        item = topic['steps'][self.index]
        self.progress.setText(f'{self.index+1} / {len(topic["steps"])} · {topic["title"][self.locale]}')
        self.heading.setText(item['title'][self.locale])
        self.text.setText(item['text'][self.locale])
        self.previous.setEnabled(self.index > 0)
        self.next.setEnabled(self.index < len(topic['steps']) - 1)
        self.animation.start()

    def filter_questions(self, query):
        query = query.casefold().strip()
        for panel, row, _, _ in self.faq_rows:
            panel.setVisible(query in (row['question'][self.locale] + ' ' + row['answer'][self.locale]).casefold())

    def open_section(self):
        parent = self.parent()
        topic = CONTENT['topics'][self.topics.currentIndex()]
        target = topic['steps'][self.index]['target']
        self.close()
        if not hasattr(parent, 'store'):
            return  # Finder/Fuel contextual help returns to its own dialog.
        from flightdeck import show_page
        if topic['id'] == 'finder':
            parent.open_finder()
        elif topic['id'] == 'fuel':
            parent.open_fuel()
        elif topic['id'] == 'library':
            parent.open_history()
        else:
            show_page(parent, 1 if topic['id'] in ('messages', 'preview', 'settings') or target else 0)
            if topic['id'] == 'settings':
                parent.presentation_toggle.setChecked(True)
                parent._toggle_presentation(True)
                parent.language_combo.setFocus()
            widget = parent.flight_widgets.get(target) or parent.type_widgets.get(target)
            if widget:
                parent.form_scroll.ensureWidgetVisible(widget, 20, 45)
                widget.setFocus()
            elif topic['id'] == 'preview':
                parent.preview.setFocus()

    def closeEvent(self, event):
        parent = self.parent()
        if self.offer and hasattr(parent, 'store'):
            parent.store.state['tutorial_seen'] = True
            parent.save_state()
        super().closeEvent(event)
