"""Champs et groupes visibles de RFS ATC Message Maker."""

from __future__ import annotations

from dataclasses import dataclass


MESSAGE_TYPES = (
    "ATC REQUEST", "AIRBORNE", "ARRIVAL BOARD", "FLIGHT COMPLETED",
    "ATC ACTIVE", "ATC OFFLINE", "FLIGHT PLAN", "DISPATCH FORM",
)

FLIGHT_TYPES = MESSAGE_TYPES[:4] + MESSAGE_TYPES[6:]

FLAGS = ("", "🇫🇷", "🇬🇧", "🇺🇸", "🇨🇦", "🇯🇵", "🇩🇪", "🇮🇹", "🇪🇸", "🇷🇴", "🇦🇪", "🇮🇳", "🇳🇱", "🇧🇷", "🇦🇺")


@dataclass(frozen=True)
class Field:
    label: str
    kind: str = "text"  # text, combo, flag, choice, bool, multiline
    required: bool = False
    choices: tuple[str, ...] = ()
    hint: str = ""


FLIGHT_FIELDS: dict[str, Field] = {
    "airline": Field("Compagnie", "combo", True),
    "aircraft": Field("Avion", "combo", True),
    "livery": Field("Livrée", "combo"),
    "callsign": Field("Callsign", "text", True),
    "radio_callsign": Field("Indicatif radio"),
    "flight_number": Field("Numéro de vol"),
    "departure_icao": Field("ICAO départ", "combo", True, hint="4 lettres, valeur conservée telle que saisie"),
    "departure_city": Field("Ville / aéroport départ", hint="Facultatif : nom affiché, par exemple Paris Charles de Gaulle. L'ICAO reste dans le champ séparé."),
    "departure_flag": Field("Drapeau départ", "flag"),
    "arrival_icao": Field("ICAO arrivée", "combo", True, hint="4 lettres, valeur conservée telle que saisie"),
    "arrival_city": Field("Ville / aéroport arrivée", hint="Nom affiché, par exemple Tokyo Narita. Aucun nom n'est déduit automatiquement."),
    "arrival_flag": Field("Drapeau arrivée", "flag"),
    "departure_runway": Field("Piste départ"),
    "arrival_runway": Field("Piste arrivée"),
    "departure_gate": Field("Porte départ"),
    "arrival_gate": Field("Porte arrivée"),
    "cruise_fl": Field("Croisière FL"),
    "distance": Field("Distance / référence (NM)", hint="Le Finder fournit une distance orthodromique entre aéroports, pas la longueur d'une route aérienne."),
    "estimated_flight_time": Field("Durée estimée"),
    "passengers": Field("Passagers"),
    "cargo": Field("Fret (kg)"),
    "fuel": Field("Carburant (kg)"),
}


FLIGHT_FIELDS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "ATC REQUEST": ("airline", "aircraft", "callsign", "radio_callsign", "departure_icao",
                    "departure_city", "departure_flag", "arrival_icao", "arrival_city", "arrival_flag",
                    "departure_gate", "departure_runway", "cruise_fl", "distance", "estimated_flight_time"),
    "AIRBORNE": ("airline", "aircraft", "callsign", "departure_icao", "departure_city",
                 "departure_flag", "arrival_icao", "arrival_city", "arrival_flag", "departure_runway",
                 "cruise_fl", "distance", "estimated_flight_time"),
    "ARRIVAL BOARD": ("airline", "aircraft", "callsign", "departure_icao", "departure_city",
                      "departure_flag", "arrival_icao", "arrival_city", "arrival_flag", "arrival_runway",
                      "fuel"),
    "FLIGHT COMPLETED": ("airline", "aircraft", "callsign", "departure_icao", "arrival_icao",
                         "arrival_city", "arrival_flag", "arrival_runway", "arrival_gate", "passengers",
                         "cargo", "fuel"),
    "FLIGHT PLAN": ("callsign", "departure_icao", "arrival_icao", "distance", "departure_runway",
                    "arrival_runway", "aircraft", "airline", "estimated_flight_time", "passengers",
                    "cargo", "fuel"),
    "DISPATCH FORM": ("callsign", "flight_number", "aircraft", "livery", "departure_icao",
                      "arrival_icao", "estimated_flight_time", "passengers", "cargo"),
}


MESSAGE_FIELDS: dict[str, dict[str, Field]] = {
    "ATC REQUEST": {
        "pushback": Field("Pushback (minutes)", required=True),
        "server": Field("Serveur", "combo"),
        "procedure": Field("Procédure départ", "choice", choices=("Standard", "Intersection departure", "Holding position", "Line up and wait")),
        "procedure_note": Field("Précision procédure (anglais)"),
    },
    "AIRBORNE": {
        "runway_used": Field("Piste utilisée"),
        "climb_target": Field("Montée vers", "choice", choices=("to TOC", "Waypoint")),
        "climb_waypoint": Field("Waypoint"),
        "controller": Field("Contrôleur ATC", "combo"),
        "no_atc": Field("Aucun ATC disponible", "bool"),
        "procedure": Field("Procédure en vol", "choice", choices=("Standard", "Holding", "Returning to departure airport", "Diversion")),
        "procedure_note": Field("Précision procédure (anglais)"),
    },
    "ARRIVAL BOARD": {
        "status": Field("Statut", "choice", choices=("Descent", "Approach", "Final", "Holding", "Other")),
        "arrival_ete": Field("ETE restante"),
        "distance_remaining": Field("Distance restante (NM)"),
        "approach": Field("Détails approche"),
        "atc_positions": Field("Positions ATC"),
        "server": Field("Serveur", "combo"),
        "go_around": Field("GO-AROUND / SECOND ATTEMPT", "bool"),
        "procedure": Field("Procédure arrivée", "choice", choices=("Standard", "Go-around", "Missed approach", "Holding", "Diversion")),
        "procedure_note": Field("Précision procédure (anglais)"),
        "show_ete": Field("Afficher ETE", "bool"),
        "show_star": Field("Afficher STAR", "bool"),
        "star": Field("STAR"),
        "show_fuel": Field("Afficher Fuel", "bool"),
        "show_altitude": Field("Afficher altitude", "bool"),
        "altitude": Field("Altitude"),
    },
    "FLIGHT COMPLETED": {
        "actual_flight_time": Field("Durée du vol", required=True),
        "controller": Field("Contrôleur ATC", "combo"),
        "no_atc": Field("Aucun ATC disponible", "bool"),
        "detailed": Field("Version détaillée", "bool"),
        "touchdown": Field("Touchdown"),
    },
    "ATC ACTIVE": {
        "airport_icao": Field("ICAO aéroport", required=True),
        "city": Field("Ville / aéroport", required=True),
        "flag": Field("Drapeau", "flag"),
        "positions": Field("Positions", required=True),
        "server": Field("Serveur", "combo"),
        "duration": Field("Durée"),
        "departures": Field("Départs"),
        "inbounds": Field("Arrivées"),
        "free_sentence": Field("Phrase libre", "multiline"),
    },
    "ATC OFFLINE": {
        "airport_icao": Field("ICAO aéroport", required=True),
        "city": Field("Ville / aéroport", required=True),
        "flag": Field("Drapeau", "flag"),
        "positions": Field("Positions", required=True),
        "server": Field("Serveur", "combo"),
        "duration": Field("Durée"),
        "departures": Field("Départs"),
        "inbounds": Field("Arrivées"),
        "free_sentence": Field("Phrase de clôture", "multiline"),
    },
    "FLIGHT PLAN": {},
    "DISPATCH FORM": {"server": Field("Serveur RFS", "combo", required=True), "meals": Field("Repas")},
}


def empty_flight() -> dict:
    return {**{key: "" for key in FLIGHT_FIELDS}, "pilots": [],
            "departure_mode": "Indépendant", "arrival_mode": "Indépendant"}


def empty_per_type() -> dict[str, dict[str, str | bool]]:
    values: dict[str, dict[str, str | bool]] = {}
    for message_type, fields in MESSAGE_FIELDS.items():
        values[message_type] = {key: False if field.kind == "bool" else "" for key, field in fields.items()}
    values["ARRIVAL BOARD"]["show_ete"] = True
    return values
