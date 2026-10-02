"""Global interface language. Persisted model values and Discord stay unchanged."""
from ui_translations import EN, FR

_language = 'fr'


def language():
    return _language


def set_language(value):
    global _language
    _language = value if value in ('fr', 'en') else 'fr'
    from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo
    from PySide6.QtWidgets import QApplication
    QLocale.setDefault(QLocale('en_GB' if _language == 'en' else 'fr_FR'))
    app = QApplication.instance()
    if app:
        previous = getattr(app, '_rfs_qt_translation', None)
        if previous:
            app.removeTranslator(previous)
        translator = QTranslator(app)
        if translator.load('qtbase_' + _language, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(translator)
        app._rfs_qt_translation = translator
        if previous:
            previous.deleteLater()


def tr(source, **values):
    translated = (EN if _language == 'en' else FR).get(source, source)
    return translated.format(**values) if values else translated
