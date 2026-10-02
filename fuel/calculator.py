"""Adaptation of the supplied RFS Fuel Helper reference, without Discord.

Formulas and constants follow docs/fuel/reference/SPECIFICATION_FR.md.
No rounding occurs before display. Exact ids/full names only: no substring fallback.
"""
from __future__ import annotations
from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / 'data'
DISCLAIMER = 'Estimation pour RFS / simulation uniquement — ne pas utiliser pour préparer un vol réel.'
TAXI_BURN_RATE_MULTIPLIER = 1.4
TAXI_OUT_MINUTES = 6
TAXI_IN_MINUTES = 4
CONTINGENCY_RATE = 0.05
FINAL_RESERVE_MINUTES = 30
ALTERNATE_CRUISE_SPEED_KT = 450
ALTERNATE_APPROACH_MINUTES = 15


@lru_cache(maxsize=4)
def _read_json_text(filename):
    return (DATA_DIR / filename).read_text(encoding='utf-8')


def load_json(filename):
    return json.loads(_read_json_text(filename))


def parse_endurance(value):
    if not isinstance(value,str):
        return None
    try:
        h,m=value.split(':',1)
        hours,minutes=int(h),int(m)
    except (ValueError,TypeError):
        return None
    return hours+minutes/60 if hours>=0 and 0<=minutes<60 else None


def find_aircraft(query, records):
    query=str(query).strip().casefold()
    matches=[r for r in records if query in (r['id'].casefold(),r['name'].casefold())]
    if len(matches)>1:
        raise ValueError('Avion ambigu : choisissez un identifiant précis dans la liste.')
    return matches[0] if matches else None


def closest_alternate(arrival_icao, destinations):
    if not arrival_icao or not arrival_icao.strip():
        return None
    destination=destinations.get(arrival_icao.strip().upper())
    if destination is None:
        return None
    candidates=destination.get('candidates',[])
    if not candidates:
        raise ValueError('La liste des dégagements de cette arrivée est vide.')
    for candidate in candidates:
        distance=candidate.get('distance_nm')
        if isinstance(distance,bool) or not isinstance(distance,(int,float)) or not math.isfinite(distance) or distance<0:
            raise ValueError('Distance de dégagement invalide dans le catalogue.')
    return deepcopy(min(candidates,key=lambda c:c['distance_nm']))


def format_kg(value):
    return f'{value:,.0f} kg'


def calculate_fuel(aircraft_query, hours, arrival_icao=None, *, aircraft_data=None, alternate_data=None):
    if isinstance(hours,bool) or not isinstance(hours,(int,float)) or not math.isfinite(hours) or hours<=0:
        raise ValueError('La durée doit être un nombre fini strictement positif.')
    aircraft_data=load_json('aircraft_fuel_data.json') if aircraft_data is None else aircraft_data
    alternate_data=load_json('airport_alternates.json') if alternate_data is None else alternate_data
    aircraft=find_aircraft(aircraft_query,aircraft_data['aircraft'])
    if aircraft is None:
        raise LookupError('Avion inconnu ou nom incomplet : choisissez une variante exacte dans la liste.')
    burn=aircraft.get('cruise_burn_kg_h')
    if isinstance(burn,bool) or not isinstance(burn,(int,float)) or not math.isfinite(burn) or burn<=0:
        raise ValueError('Cet avion ne possède pas de consommation de croisière valide.')
    burn=float(burn)
    taxi_rate=burn*TAXI_BURN_RATE_MULTIPLIER
    trip=hours*burn
    taxi_out=taxi_rate*TAXI_OUT_MINUTES/60
    taxi_in=taxi_rate*TAXI_IN_MINUTES/60
    contingency=trip*CONTINGENCY_RATE
    final_reserve=burn*FINAL_RESERVE_MINUTES/60
    arrival=arrival_icao.strip().upper() if arrival_icao and arrival_icao.strip() else None
    alternate=closest_alternate(arrival,alternate_data['destinations'])
    alternate_time=0.0 if alternate is None else alternate['distance_nm']/ALTERNATE_CRUISE_SPEED_KT+ALTERNATE_APPROACH_MINUTES/60
    components={'taxi_out_kg':taxi_out,'trip_kg':trip,'contingency_kg':contingency,
                'alternate_kg':alternate_time*burn,'final_reserve_kg':final_reserve,'taxi_in_kg':taxi_in}
    total=sum(components.values())
    if not math.isfinite(total):
        raise ValueError('La durée ou la consommation produit un total trop grand.')
    endurance=parse_endurance(aircraft.get('max_endurance'))
    return {'aircraft':{'id':aircraft['id'],'name':aircraft['name']},
        'input':{'hours':float(hours),'arrival_icao':arrival},'burn_rate_kg_h':burn,
        'max_endurance':aircraft.get('max_endurance'),'max_endurance_hours':endurance,
        'exceeds_endurance':endurance is not None and hours>endurance,
        'alternate':alternate,'alternate_time_hours':alternate_time,'components_exact':components,
        'total_block_fuel_kg_exact':total,'display':{**{k:format_kg(v) for k,v in components.items()},'total_block_fuel':format_kg(total)},
        'warning':DISCLAIMER,
        'provenance':{'aircraft_record':deepcopy(aircraft),
            'catalogue_source':aircraft_data.get('source'), 'catalogue_note':aircraft_data.get('note'),
            'catalogue_export_date':aircraft_data.get('export_date'),
            'alternate_record':deepcopy(alternate_data['destinations'].get(arrival)),
            'alternate_export_date':alternate_data.get('export_date'),
            'alternate_warning':alternate_data.get('warning')},
        'alternate_explanation': 'Dégagement statique le plus proche.' if alternate else
            'Arrivée absente ou inconnue du catalogue : alternate = 0 kg, sans ajout des 15 minutes d’approche.'}
