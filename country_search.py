"""Accent-independent country aliases. Codes are the only persisted values."""
import re
import unicodedata
from functools import lru_cache
from PySide6.QtCore import QLocale
from country_data import COUNTRIES


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c)).strip()


@lru_cache(maxsize=1)
def country_rows():
    return [(code, name, QLocale.territoryToString(QLocale.codeToTerritory(code))) for code, name in COUNTRIES]


def resolve_country(text):
    value = normalized(text)
    match = re.search(r'\(([A-Z]{2})\)\s*$', text)
    if match and match[1] in dict(COUNTRIES):
        return match[1]
    aliases = {'romania':'RO', 'r moldavie':'MD', 'republique de moldavie':'MD', 'moldova':'MD'}
    if value in aliases:
        return aliases[value]
    for code, french, english in country_rows():
        if value in (code.lower(), normalized(french), normalized(english)):
            return code
    raise ValueError('COUNTRY_UNKNOWN')
