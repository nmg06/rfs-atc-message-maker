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
        # Qt sends LanguageChange to every widget on install/remove. Recreating
        # parented translators even for an unchanged language churned native
        # objects and deferred deletions during window teardown on Windows.
        # Keep at most two catalogues alive for the QApplication lifetime.
        if getattr(app, '_rfs_qt_language', None) == _language:
            return
        catalogues = getattr(app, '_rfs_qt_catalogues', None)
        if catalogues is None:
            app._rfs_qt_catalogues = catalogues = {}
        if _language not in catalogues:
            translator = QTranslator(app)
            loaded = translator.load('qtbase_' + _language, QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
            catalogues[_language] = translator if loaded else None
        previous = getattr(app, '_rfs_qt_translation', None)
        if previous:
            app.removeTranslator(previous)
        translator = catalogues[_language]
        if translator:
            app.installTranslator(translator)
        app._rfs_qt_translation = translator
        app._rfs_qt_language = _language


def tr(source, **values):
    translated = (EN if _language == 'en' else FR).get(source, source)
    return translated.format(**values) if values else translated
