"""Static UI choices retain canonical persisted values across language switches."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox
from i18n import tr


class ChoiceBox(QComboBox):
    CanonicalRole = Qt.ItemDataRole.UserRole + 47

    def addItem(self, text, userData=None):
        super().addItem(tr(text), userData)
        self.setItemData(self.count() - 1, text, self.CanonicalRole)

    def addItems(self, texts):
        for text in texts:
            self.addItem(text)

    def currentText(self):
        canonical = self.currentData(self.CanonicalRole)
        return canonical if canonical is not None else super().currentText()

    def setCurrentText(self, text):
        index = self.findData(text, self.CanonicalRole)
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            super().setCurrentText(text)

    def wheelEvent(self, event):
        if self.view() and self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()
