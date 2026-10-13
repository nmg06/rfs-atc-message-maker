"""Android adapter: same translations, no Qt locale side effects."""
from ui_translations import EN, FR
_language = 'fr'
ANDROID_FR = {'Taxi route': 'Itinéraire de roulage', 'Hold short': 'Arrêt avant',
    'Information letter': 'Lettre d’information', 'Wind': 'Vent', 'Visibility': 'Visibilité',
    'Weather': 'Météo', 'Cloud': 'Nuages', 'Temperature / dew point': 'Température / point de rosée',
    'Runway': 'Piste', 'Remarks': 'Remarques', 'Left': 'Gauche', 'Right': 'Droite', 'Straight': 'Tout droit'}
ANDROID_EN = {'QNH : 800 à 1100 hPa.': 'QNH: 800 to 1100 hPa.',
    'Direction invalide.': 'Invalid direction.', 'Piste du pilote invalide.': 'Invalid pilot runway.',
    'Piste invalide : 01 à 36, éventuellement L/R/C.': 'Invalid runway: 01 to 36, optionally L/R/C.',
    'Information ATIS : une lettre de A à Z.': 'ATIS information: one letter A to Z.',
    'Pilote {index} : callsign requis.': 'Pilot {index}: callsign required.'}


def language():
    return _language


def set_language(value):
    global _language
    _language = value if value in ('fr', 'en') else 'fr'


def tr(source, **values):
    translated = (ANDROID_EN if _language == 'en' else ANDROID_FR).get(source,
        (EN if _language == 'en' else FR).get(source, source))
    return translated.format(**values) if values else translated
