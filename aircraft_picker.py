"""Catalogue selection with a separate search field; never edits the selected value."""
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QComboBox, QFrame, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel, QPushButton, QInputDialog
from i18n import language, tr


class AircraftPicker(QComboBox):
    def __init__(self, parent=None, allow_custom=False):
        super().__init__(parent)
        self.setEditable(False)
        self.popup = QFrame(self, Qt.WindowType.Popup)
        self.popup.setObjectName('aircraftPopup')
        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(12, 12, 12, 12)
        self.search = QLineEdit(self.popup)
        self.options = QListWidget(self.popup)
        self.summary = QLabel(self.popup)
        layout.addWidget(self.search)
        layout.addWidget(self.options)
        layout.addWidget(self.summary)
        if allow_custom:
            custom = QPushButton(tr('Autre avion'), self.popup)
            custom.clicked.connect(self._custom)
            layout.addWidget(custom)
        self.search.textChanged.connect(self._filter)
        self.options.itemClicked.connect(self._choose)
        self.options.itemActivated.connect(self._choose)
        self.search.installEventFilter(self)
        self.options.installEventFilter(self)

    def setCurrentText(self, text):
        # Preserve historical/manual values without adding them to the RFS catalogue.
        index = self.findText(text)
        if index < 0 and text:
            self.addItem(text, None)
            index = self.count()-1
        if index >= 0:
            self.setCurrentIndex(index)

    def _custom(self):
        self.hidePopup()
        value, accepted = QInputDialog.getText(self, tr('Avion'), tr('Nom :'), text=self.currentText())
        if accepted and value.strip():
            self.setCurrentText(value.strip())

    def showPopup(self):
        french = language() == 'fr'
        self.search.setPlaceholderText('Rechercher Airbus, Boeing, A320…' if french else 'Search Airbus, Boeing, A320…')
        self.search.setAccessibleName('Rechercher un avion' if french else 'Search aircraft')
        self.search.clear()
        self._filter('')
        screen = self.screen().availableGeometry()
        width, height = min(max(self.width(), 350), screen.width()), min(390, screen.height())
        point = self.mapToGlobal(self.rect().bottomLeft())
        x = max(screen.left(), min(point.x(), screen.right() - width + 1))
        y = point.y() if point.y() + height <= screen.bottom() else max(screen.top(), self.mapToGlobal(self.rect().topLeft()).y() - height)
        self.popup.setGeometry(x, y, width, height)
        self.popup.show()
        self.search.setFocus(Qt.FocusReason.PopupFocusReason)

    def hidePopup(self):
        self.popup.hide()
        super().hidePopup()

    def _filter(self, text):
        self.options.clear()
        terms = text.casefold().split()
        for index in range(self.count()):
            if self.itemData(index) is None:
                continue
            label = self.itemText(index)
            if all(term in label.casefold() for term in terms):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.options.addItem(item)
        count = self.options.count()
        self.summary.setText(f'{count} variantes · choisissez la variante exacte' if language() == 'fr' else f'{count} variants · choose the exact variant')
        # Filtering must not silently choose a different aircraft.
        self.options.setCurrentRow(-1)

    def _choose(self, item):
        if item is not None:
            self.setCurrentIndex(item.data(Qt.ItemDataRole.UserRole))
            self.hidePopup()
            self.setFocus()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.hidePopup()
                self.setFocus()
                return True
            if obj is self.search and event.key() == Qt.Key.Key_Down and self.options.count():
                self.options.setFocus()
                self.options.setCurrentRow(0)
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Enter while typing doesn't accept an ambiguous first match.
                if obj is self.options:
                    self._choose(self.options.currentItem())
                return True
        return super().eventFilter(obj, event)
