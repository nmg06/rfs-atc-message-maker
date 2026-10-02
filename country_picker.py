from i18n import tr, set_language, language
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QCompleter
from country_data import COUNTRIES
from country_search import resolve_country, country_rows
from i18n import language, tr

def flag_for(code):
    return ''.join((chr(127462 + ord(char) - ord('A')) for char in code))

class CountryPicker(QComboBox):
    flagChanged = Signal(str)

    def __init__(self, value='', parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addItem('', '')
        self.lookup = {'': ''}
        for code, fr, en in sorted(country_rows(), key=lambda item: item[1]):
            name = en if language() == 'en' else fr
            flag = flag_for(code)
            label = f'{name} ({code})'
            self.addItem(label, flag)
            for key in (code, fr, en, label, flag):
                self.lookup[key.casefold()] = flag
        self.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.lineEdit().setPlaceholderText(tr('Rechercher un pays ou son code : France, FR…'))
        self.setToolTip(tr('Recherchez un pays par son nom. Son drapeau sera copié au format emoji pour Discord.'))
        index = self.findData(value)
        self.setCurrentIndex(max(index, 0))
        if index < 0:
            self.setEditText(str(value))
        self.lineEdit().editingFinished.connect(self.commit_country)
        self.currentTextChanged.connect(lambda text: self.flagChanged.emit(self.value()))

    def value(self):
        text = self.currentText().strip()
        if text.casefold() in self.lookup:
            return self.lookup[text.casefold()]
        try:
            return flag_for(resolve_country(text))
        except ValueError:
            return ''

    def commit_country(self):
        flag = self.value()
        if flag:
            self.setCurrentIndex(self.findData(flag))
