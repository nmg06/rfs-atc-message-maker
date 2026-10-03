"""Android adapter: same translations, no Qt locale side effects."""
from ui_translations import EN, FR
_language = 'fr'


def language():
    return _language


def set_language(value):
    global _language
    _language = value if value in ('fr', 'en') else 'fr'


def tr(source, **values):
    translated = (EN if _language == 'en' else FR).get(source, source)
    return translated.format(**values) if values else translated
