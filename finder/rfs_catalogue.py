"""Supplied RFS catalogue -> observed ICAO type, never an inferred fuel variant.

Codes checked against the bundled VRS aircraft_types table. Shared type codes
cannot distinguish cargo, winglets, operator or exact subvariant. None means no
supported mapping in this database, not that the aircraft cannot exist.
"""
from fuel.calculator import load_json
from functools import lru_cache

TYPE_BY_ID = {
    'airbus_a220_300':'BCS3', 'airbus_a310_300':'A310', 'airbus_a318':'A318',
    'airbus_a319ceo':'A319', 'airbus_a320_200':'A320', 'airbus_a320neo':'A20N',
    'airbus_a321_200':'A321', 'airbus_a321neo':'A21N', 'airbus_a330_200':'A332',
    'airbus_a330_200f':'A332', 'airbus_a330_300':'A333', 'airbus_belugaxl_a330_700l':'A337',
    'airbus_a330_900neo':'A339', 'airbus_a340_300':'A343', 'airbus_a340_600':'A346',
    'airbus_a350_1000':'A35K', 'airbus_a350_900':'A359', 'airbus_a380_800':'A388',
    'antonov_an_225_mriya':'A225', 'atr_72_600':'AT76', 'bae_systems_146_300':'B463',
    'boeing_707_320c':'B703', 'boeing_727_200':'B722', 'boeing_737_max_8':'B38M',
    'boeing_737_100':None, 'boeing_737_200':'B732', 'boeing_737_800':'B738',
    'boeing_737_800bcf':'B738', 'boeing_747_200b':'B742', 'boeing_747_400':'B744',
    'boeing_747_400f':'B744', 'boeing_747_8f':'B748', 'boeing_747_8i':'B748',
    'boeing_757_200f':'B752', 'boeing_757_200wl':'B752', 'boeing_767_300':'B763',
    'boeing_767_300f':'B763', 'boeing_767_400er':'B764', 'boeing_777_200':'B772',
    'boeing_777_200lr':'B77L', 'boeing_777_300er':'B77W', 'boeing_777f':'B77L',
    'boeing_787_10_dreamliner':'B78X', 'boeing_787_8_dreamliner':'B788', 'boeing_787_9_dreamliner':'B789',
    'bombardier_crj900':'CRJ9', 'cessna_172':'C172', 'cessna_208_caravan':'C208',
    'cirrus_sr22':'SR22', 'concorde':None, 'dhc_dash_8_q400':'DH8D',
    'dhc_6_twin_otter_300':'DHC6', 'douglas_dc_8_61':'DC86', 'embraer_190':'E190',
    'embraer_190_e2':'E290', 'embraer_erj145':'E145', 'learjet_35a':'LJ35',
    'lockheed_c_5b_galaxy':None, 'mcdonnell_douglas_md_11':'MD11',
    'mcdonnell_douglas_md_11f':'MD11', 'mcdonnell_douglas_md_81':'MD81',
    'saab_340b':'SF34', 'tupolev_tu_154m':'T154',
}
SUPPORTED_TYPES = tuple(sorted({v for v in TYPE_BY_ID.values() if v}))


@lru_cache(maxsize=1)
def records():
    return load_json('aircraft_fuel_data.json')['aircraft']


@lru_cache(maxsize=512)
def observation_name(code, fallback=''):
    # Deliberately neutral where the ICAO type covers multiple supplied variants.
    broad = {'A310':'Airbus A310', 'A319':'Airbus A319', 'A320':'Airbus A320',
             'A321':'Airbus A321', 'A332':'Airbus A330-200', 'B703':'Boeing 707-300',
             'B738':'Boeing 737-800', 'B742':'Boeing 747-200', 'B744':'Boeing 747-400',
             'B748':'Boeing 747-8', 'B752':'Boeing 757-200', 'B763':'Boeing 767-300',
             'B77L':'Boeing 777-200LR / 777F', 'DHC6':'DHC-6 Twin Otter',
             'DC86':'Douglas DC-8-60', 'LJ35':'Learjet 35', 'MD11':'McDonnell Douglas MD-11',
             'SF34':'Saab 340', 'T154':'Tupolev Tu-154'}
    if code in broad:
        return broad[code]
    names = [r['name'] for r in records() if TYPE_BY_ID.get(r['id']) == code]
    return names[0] if len(names) == 1 else (fallback or code)
