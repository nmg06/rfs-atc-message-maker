"""The sole bridge into the existing current-flight state."""
from copy import deepcopy
import re
from .provenance import duration_provenance


def safe_text(value) -> str:
    return re.sub(r"[\x00-\x1f`*_~|<>@]", "", str(value or "")).strip()


def use_this_flight(current: dict, result: dict) -> dict:
    flight = deepcopy(current)
    # Retain the manually visible fuel quantity, but invalidate its old calculation.
    flight.pop('fuel_calculation', None)
    flight.pop('fuel_aircraft_id', None)
    mapping = {"airline_name": "airline", "aircraft_model": "aircraft", "callsign": "callsign",
               "origin": "departure_icao", "destination": "arrival_icao",
               "origin_name": "departure_city", "destination_name": "arrival_city"}
    known = {}
    for source, target in mapping.items():
        value = safe_text(result.get(source))
        if value:
            flight[target] = value
            known[target] = "STATIC_DB" if source != "callsign" else "OBSERVED"
            if result.get('record_kind') == 'OBSERVED_ROUTE':
                if source == 'airline_name':
                    known[target] = 'DERIVED_FROM_CALLSIGN_PREFIX'
                elif source == 'callsign':
                    known[target] = 'OBSERVED_ROUTE_EVIDENCE'
    if result.get('aircraft_display'):
        flight['aircraft'] = safe_text(result['aircraft_display'])
        known['aircraft'] = 'OBSERVED_TYPE_ONLY'
    if not result.get("aircraft_model") and result.get("aircraft"):
        flight["aircraft"] = safe_text(result["aircraft"])
        known["aircraft"] = "OBSERVED"
    for endpoint, target in (("origin", "departure"), ("destination", "arrival")):
        code = result.get(endpoint + "_country") or ""
        if re.fullmatch(r"[A-Z]{2}", code):
            flight[target + "_flag"] = "".join(chr(127397 + ord(c)) for c in code)
            known[target + "_flag"] = "STATIC_DB"
    if result.get("distance_nm") is not None:
        # This is a great-circle reference, not a routed airway distance.
        flight["distance"] = str(round(result["distance_nm"]))
        known["distance"] = "DERIVED_GREAT_CIRCLE"
    if result.get("duration_min") is not None:
        minutes = round(result["duration_min"])
        flight["estimated_flight_time"] = f"{minutes//60}h{minutes%60:02}"
        known["estimated_flight_time"] = ("TYPICAL_AIRBORNE" if duration_provenance(result) == 'AGGREGATED_COMPLETE_TRACKS'
                                           else duration_provenance(result))
    callsign = result.get("callsign") or ""
    suffix = re.fullmatch(r"[A-Z]{3}(\d{1,4}[A-Z]?)", callsign)
    if suffix and result.get("airline_iata"):
        flight["flight_number"] = safe_text(result["airline_iata"] + suffix[1])
        known["flight_number"] = "DERIVED_FROM_CALLSIGN"
    flight["selected_flight"] = {"schema_version": 1, "pattern_id": result.get("pattern_id"),
        "aircraft_icao": result.get('aircraft'),
        "source_id": result.get("source_id"), "last_seen": result.get("last_seen"), "fields": known,
        "status": "OBSERVED_ROUTE" if result.get('record_kind') == 'OBSERVED_ROUTE' else "HISTORICAL_OBSERVED",
        "route_id": result.get('route_id'), "n_obs": result.get("n_obs"),
        "duration_provenance": duration_provenance(result), "n_complete": result.get('n_complete'),
        "sim_departure_utc": result.get("sim_departure_utc"), "sim_arrival_utc": result.get("sim_arrival_utc")}
    return flight
