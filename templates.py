"""Modèles Discord RFS. Aucun accès au réseau ni à l'interface graphique."""

from __future__ import annotations

import re


BOX_WIDTH = 27


def _value(data: dict, key: str) -> str:
    return str(data.get(key, "") or "").strip()


def _line(label: str, value: str, *, colon: str = " : ") -> str:
    return f"{label}{colon}{value}" if value else ""


def _block(*lines: str) -> str:
    return "\n".join(line for line in lines if line)


def _join(*blocks: str) -> str:
    return "\n\n".join(block for block in blocks if block.strip()).strip()


def _heading(title: str) -> str:
    # Le contenu est centré sur les 27 caractères du bord supérieur.
    return f"╭{'─' * BOX_WIDTH}╮\n{title.center(BOX_WIDTH)}\n╰{'─' * BOX_WIDTH}╯"


def _flight_identity(flight: dict, pilot_name: str) -> str:
    airline = _value(flight, "airline").upper()
    aircraft = _value(flight, "aircraft")
    callsign = _value(flight, "callsign")
    radio = _value(flight, "radio_callsign")
    identity = f"✈ {pilot_name} │ {aircraft}" if aircraft else (f"✈ {pilot_name}" if pilot_name else "")
    return _block(airline, identity, _line("CALLSIGN", callsign), _line("RADIO", radio))


def _airport(flight: dict, prefix: str) -> str:
    base = " • ".join(part for part in (
        _value(flight, f"{prefix}_icao"), _value(flight, f"{prefix}_city")
    ) if part)
    return base + (f" {_value(flight, f'{prefix}_flag')}" if base and _value(flight, f"{prefix}_flag") else "")


def _route(flight: dict) -> str:
    departure = _airport(flight, "departure")
    arrival = _airport(flight, "arrival")
    if departure and arrival:
        return f"🛫 {departure}\n🛬 {arrival}"
    if departure:
        return f"🛫 {departure}"
    if arrival:
        return f"🛬 {arrival}"
    return ""


def format_flight_level(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return value if value.upper().startswith("FL") else f"FL{value}"


def format_runway(value: str, *, with_prefix: bool = False) -> str:
    value = re.sub(r"^(?:RWY|RUNWAY)\s*", "", value.strip(), flags=re.IGNORECASE)
    return f"RWY {value}" if with_prefix and value else value


def format_distance(value: str, *, upper: bool = True) -> str:
    value = re.sub(r"\s*(?:NM|NMI)\s*$", "", value.strip(), flags=re.IGNORECASE)
    return f"{value} {'NM' if upper else 'nm'}" if value else ""


def format_duration(value: str, style: str = "compact") -> str:
    """Convertit 10 h 20, 10:20 ou 10h20m sans créer de durée absente."""
    value = value.strip()
    if not value:
        return ""
    match = re.fullmatch(r"(\d+)\s*(?:h|:|hours?)\s*(\d{1,2})\s*m?", value, flags=re.I)
    if match:
        hours, minutes = int(match.group(1)), int(match.group(2))
        if minutes >= 60:
            return value
        if style == "colon":
            return f"{hours}:{minutes:02d}"
        if style == "spaced":
            return f"{hours}h {minutes:02d}m"
        return f"{hours}h{minutes:02d}m"
    match = re.fullmatch(r"(\d+)\s*h(?:ours?)?", value, flags=re.I)
    if match:
        hours = int(match.group(1))
        return f"{hours}:00" if style == "colon" else f"{hours}h"
    return value


def _callsign(flight: dict) -> str:
    return _value(flight, "callsign") or _value(flight, "flight_number")


def atc_request(flight: dict, data: dict, pilot_name: str) -> str:
    departure = _value(flight, "departure_icao")
    gate = _value(flight, "departure_gate")
    pushback = _value(data, "pushback")
    info = _block(
        _line("ICAO　　", departure),
        _line("STATUS　", f"Gate {gate} • Parking" if gate else ""),
        _line("PUSHBACK", f"in {pushback} minute{'s' if pushback != '1' else ''}" if pushback else ""),
        _line("RUNWAY　", format_runway(_value(flight, "departure_runway"))),
        _line("CRUISE　", format_flight_level(_value(flight, "cruise_fl"))),
        _line("ROUTE　　", format_distance(_value(flight, "distance"))),
        _line("ETE　　　", format_duration(_value(flight, "estimated_flight_time"))),
        _line("SERVER　", _value(data, "server")),
    )
    request = f"Requesting Ground and Tower for departure at {departure}." if departure else ""
    return _join(_heading("ATC REQUEST"), _flight_identity(flight, pilot_name),
                 _route(flight), info, request, "「REQUESTING ATC」", "@RFS ATC")


def airborne(flight: dict, data: dict, pilot_name: str) -> str:
    climb = _value(data, "climb_target")
    if climb == "Waypoint":
        climb = f"to {_value(data, 'climb_waypoint')}" if _value(data, "climb_waypoint") else ""
    runway = _value(data, "runway_used") or _value(flight, "departure_runway")
    info = _block(
        "STATUS　 : Airborne",
        _line("RUNWAY　", format_runway(runway)),
        _line("CLIMBING", climb),
        _line("CRUISE　", format_flight_level(_value(flight, "cruise_fl"))),
        _line("ROUTE　　", format_distance(_value(flight, "distance"))),
        _line("ETE　　　", format_duration(_value(flight, "estimated_flight_time"))),
    )
    controller = _value(data, "controller").lstrip("@")
    thanks = ("No ATC available for departure." if data.get("no_atc") else
              f"Big thanks to @{controller} for the ATC on the ground and the departure 🙏" if controller else "")
    return _join(_heading("AIRBORNE"), _flight_identity(flight, pilot_name),
                 _route(flight), info, thanks)


def arrival_board(flight: dict, data: dict, pilot_name: str) -> str:
    go_around = bool(data.get("go_around"))
    status = ("Go-around procedure • first landing attempt unsuccessful" if go_around
              else _value(data, "status"))
    runway = format_runway(_value(flight, "arrival_runway"), with_prefix=True)
    approach = _value(data, "approach")
    approach_parts = [part for part in (runway, approach) if part]
    if go_around and approach_parts:
        approach_parts.append("second attempt")
    info = _block(
        _line("STATUS　", status),
        _line("ETE　　 ", _value(data, "arrival_ete") if data.get("show_ete", True) else ""),
        _line("DIST　　", format_distance(_value(data, "distance_remaining"))),
        _line("APPROACH", " • ".join(approach_parts)),
        _line("ATC　　 ", _value(data, "atc_positions")),
        _line("SERVER　", _value(data, "server")),
        _line("STAR　　", _value(data, "star") if data.get("show_star") else ""),
        _line("FUEL　　", f"{_value(flight, 'fuel')} kg" if data.get("show_fuel") and _value(flight, "fuel") else ""),
        _line("ALTITUDE", _value(data, "altitude") if data.get("show_altitude") else ""),
    )
    return _join(_heading("ARRIVAL BOARD"), _flight_identity(flight, pilot_name),
                 _route(flight), info, "「REQUESTING ATC REPORT」", "@RFS ATC")


def flight_completed(flight: dict, data: dict, pilot_name: str) -> str:
    airport = _airport({**flight, "arrival_city": _value(flight, "arrival_city").upper()}, "arrival")
    airline = _value(flight, "airline").upper()
    aircraft = _value(flight, "aircraft")
    plane = " • ".join(part for part in (airline, aircraft) if part)
    departure = _value(flight, "departure_icao")
    arrival = _value(flight, "arrival_icao")
    route = f"{departure} → {arrival}" if departure and arrival else (departure or arrival)
    gate = _value(flight, "arrival_gate")
    status = f"AT GATE {gate}" if gate else ""
    info = _join(
        f"📡 {airport}" if airport else "",
        _block(
        f"✈️ {plane}" if plane else "",
        _line("CALLSIGN", _callsign(flight)),
        _line("ROUTE   ", route),
        ),
        _block(
        _line("RUNWAY  ", format_runway(_value(flight, "arrival_runway"))),
        _line("STATUS  ", status),
        _line("FLIGHT  ", format_duration(_value(data, "actual_flight_time"))),
        ),
    )
    detail = ""
    if data.get("detailed"):
        detail = _block(
            _line("PASSENGERS", _value(flight, "passengers")),
            _line("CARGO     ", f"{_value(flight, 'cargo')} kg" if _value(flight, "cargo") else ""),
            _line("FUEL      ", f"{_value(flight, 'fuel')} kg" if _value(flight, "fuel") else ""),
            _line("TOUCHDOWN ", format_touchdown(_value(data, "touchdown"))),
        )
    controller = _value(data, "controller").lstrip("@")
    thanks = ("No ATC available." if data.get("no_atc") else
              f"Thanks for ATC 🙏 @{controller}" if controller else "")
    middle = _join(info, detail, thanks)
    return f"╭─────── ATC • ARRIVED ───────╮\n\n{middle}\n\n╰────────────────────────────╯"


def atc_session(data: dict, *, active: bool) -> str:
    title = "🟢 ATC ACTIVE" if active else "🔴 ATC CLOSED"
    airport = " • ".join(part for part in (_value(data, "airport_icao"), _value(data, "city").upper()) if part)
    flag = _value(data, "flag")
    lines = _block(
        title,
        f"{flag + ' ' if flag else ''}{airport}" if airport else "",
        f"🎧 {_value(data, 'positions')}" if _value(data, "positions") else "",
        f"⏱️ DURATION: {format_duration(_value(data, 'duration'))}" if _value(data, "duration") else "",
        f"🛫 DEPARTURES: {_value(data, 'departures')}" if _value(data, "departures") else "",
        f"🛬 INBOUNDS: {_value(data, 'inbounds')}" if _value(data, "inbounds") else "",
        _line("SERVER", _value(data, "server"), colon=": "),
    )
    sentence = _value(data, "free_sentence") or ("" if active else "Thanks to everyone who joined the session!")
    return _join(lines, sentence)


def flight_plan(flight: dict) -> str:
    departure = _value(flight, "departure_icao")
    arrival = _value(flight, "arrival_icao")
    route = f"{departure} - {arrival}" if departure and arrival else ""
    return _join("✈️ Flight Plan ✈️", _block(
        _line("Route", route),
        _line("Distance", format_distance(_value(flight, "distance"), upper=False)),
        _line("Departure Runway", format_runway(_value(flight, "departure_runway"))),
        _line("Arrival Runway", format_runway(_value(flight, "arrival_runway"))),
        _line("Aircraft", _value(flight, "aircraft")),
        _line("Airline", _value(flight, "airline")),
        _line("Estimated Flight Time", format_duration(_value(flight, "estimated_flight_time"), "spaced")),
        _line("Pax", _value(flight, "passengers")),
        _line("Cargo", f"{_value(flight, 'cargo')} kg" if _value(flight, "cargo") else ""),
        _line("Fuel", f"{_value(flight, 'fuel')} kg" if _value(flight, "fuel") else ""),
    ))


def dispatch_form(flight: dict, data: dict, pilot_name: str) -> str:
    server = _value(data, "server")
    return _block(
        f"👤 Pilot Name- {pilot_name}" if pilot_name else "",
        f"🌐 RFS Server- {server}" if server else "",
        f"📡 Call Sign / Flight Number- {_callsign(flight)}" if _callsign(flight) else "",
        f"✈️ Aircraft- {_value(flight, 'aircraft')}" if _value(flight, "aircraft") else "",
        f"🎨 Livery- {_value(flight, 'livery')}" if _value(flight, "livery") else "",
        f"🛫 Departure Airport- {_value(flight, 'departure_icao')}" if _value(flight, "departure_icao") else "",
        f"🛬 Arrival Airport- {_value(flight, 'arrival_icao')}" if _value(flight, "arrival_icao") else "",
        f"⏱️ Estimated Flight Time- {format_duration(_value(flight, 'estimated_flight_time'), 'colon')}" if _value(flight, "estimated_flight_time") else "",
        _line("Passengers", _value(flight, "passengers"), colon="- "),
        _line("Cargo", f"{_value(flight, 'cargo')} kg" if _value(flight, "cargo") else "", colon="- "),
        _line("Meals", _value(data, "meals"), colon="- "),
    )


def render(message_type: str, flight: dict, data: dict, pilot_name: str) -> str:
    match message_type:
        case "ATC REQUEST":
            return atc_request(flight, data, pilot_name)
        case "AIRBORNE":
            return airborne(flight, data, pilot_name)
        case "ARRIVAL BOARD":
            return arrival_board(flight, data, pilot_name)
        case "FLIGHT COMPLETED":
            return flight_completed(flight, data, pilot_name)
        case "ATC ACTIVE":
            return atc_session(data, active=True)
        case "ATC OFFLINE":
            return atc_session(data, active=False)
        case "FLIGHT PLAN":
            return flight_plan(flight)
        case "DISPATCH FORM":
            return dispatch_form(flight, data, pilot_name)
        case _:
            raise ValueError(f"Type de message inconnu : {message_type}")


def format_touchdown(value):
    value = str(value or '').strip()
    return value + ' ft/min' if re.fullmatch(r'[+-]?\d+(?:[.,]\d+)?', value) else value
