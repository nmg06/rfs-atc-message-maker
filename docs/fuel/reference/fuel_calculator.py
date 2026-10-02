"""Portable reference implementation of the RFS Fuel Helper calculation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent
TAXI_BURN_RATE_MULTIPLIER = 1.4
TAXI_OUT_MINUTES = 6
TAXI_IN_MINUTES = 4
CONTINGENCY_RATE = 0.05
FINAL_RESERVE_MINUTES = 30
ALTERNATE_CRUISE_SPEED_KT = 450
ALTERNATE_APPROACH_MINUTES = 15


def load_json(filename: str) -> dict[str, Any]:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def parse_endurance(value: Any) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        hours_text, minutes_text = value.split(":", maxsplit=1)
        hours, minutes = int(hours_text), int(minutes_text)
    except (ValueError, TypeError):
        return None
    if hours < 0 or not 0 <= minutes < 60:
        return None
    return hours + minutes / 60


def find_aircraft(query: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = query.strip().casefold()
    if not normalized:
        return None
    for record in records:
        if normalized in (record["id"].casefold(), record["name"].casefold()):
            return record
    # Compatibility with the Discord bot: fall back to the first name substring.
    # A new UI should prefer the stable id to avoid ambiguous selections.
    for record in records:
        if normalized in record["name"].casefold():
            return record
    return None


def closest_alternate(
    arrival_icao: str | None, destinations: dict[str, Any]
) -> dict[str, Any] | None:
    if not arrival_icao or not arrival_icao.strip():
        return None
    destination = destinations.get(arrival_icao.strip().upper())
    if destination is None:
        return None
    return min(destination["candidates"], key=lambda item: item["distance_nm"])


def format_kg(value: float) -> str:
    """Match the active Python bot: nearest kg using round-half-to-even."""
    return f"{value:,.0f} kg"


def calculate_fuel(
    aircraft_query: str,
    hours: float,
    arrival_icao: str | None = None,
    *,
    aircraft_data: dict[str, Any] | None = None,
    alternate_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(hours, (int, float)) or not math.isfinite(hours) or hours <= 0:
        raise ValueError("hours must be a finite number greater than 0")
    aircraft_data = aircraft_data or load_json("aircraft_fuel_data.json")
    alternate_data = alternate_data or load_json("airport_alternates.json")
    aircraft = find_aircraft(aircraft_query, aircraft_data["aircraft"])
    if aircraft is None:
        raise LookupError("aircraft not found")
    burn_rate = aircraft.get("cruise_burn_kg_h")
    if not isinstance(burn_rate, (int, float)) or not math.isfinite(burn_rate) or burn_rate <= 0:
        raise ValueError("aircraft has no valid cruise burn rate")
    burn_rate = float(burn_rate)

    taxi_rate = burn_rate * TAXI_BURN_RATE_MULTIPLIER
    trip = hours * burn_rate
    taxi_out = taxi_rate * TAXI_OUT_MINUTES / 60
    taxi_in = taxi_rate * TAXI_IN_MINUTES / 60
    contingency = trip * CONTINGENCY_RATE
    final_reserve = burn_rate * FINAL_RESERVE_MINUTES / 60

    alternate = closest_alternate(arrival_icao, alternate_data["destinations"])
    if alternate is None:
        alternate_time = 0.0
        alternate_fuel = 0.0
    else:
        alternate_time = (
            alternate["distance_nm"] / ALTERNATE_CRUISE_SPEED_KT
            + ALTERNATE_APPROACH_MINUTES / 60
        )
        alternate_fuel = alternate_time * burn_rate

    components = {
        "taxi_out_kg": taxi_out,
        "trip_kg": trip,
        "contingency_kg": contingency,
        "alternate_kg": alternate_fuel,
        "final_reserve_kg": final_reserve,
        "taxi_in_kg": taxi_in,
    }
    total = sum(components.values())
    max_endurance_hours = parse_endurance(aircraft.get("max_endurance"))
    return {
        "aircraft": {"id": aircraft["id"], "name": aircraft["name"]},
        "input": {"hours": float(hours), "arrival_icao": arrival_icao.strip().upper() if arrival_icao and arrival_icao.strip() else None},
        "burn_rate_kg_h": burn_rate,
        "max_endurance": aircraft.get("max_endurance"),
        "max_endurance_hours": max_endurance_hours,
        "exceeds_endurance": max_endurance_hours is not None and hours > max_endurance_hours,
        "alternate": alternate,
        "alternate_time_hours": alternate_time,
        "components_exact": components,
        "total_block_fuel_kg_exact": total,
        "display": {
            **{key: format_kg(value) for key, value in components.items()},
            "total_block_fuel": format_kg(total),
        },
        "warning": "RFS / flight simulation estimate only; not for real-world flight planning.",
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RFS Fuel Helper reference calculator")
    parser.add_argument("aircraft", help="Stable aircraft id or full/partial name")
    parser.add_argument("hours", type=float, help="Planned flight duration in hours")
    parser.add_argument("--arrival", help="Optional arrival ICAO code")
    args = parser.parse_args()
    print(json.dumps(calculate_fuel(args.aircraft, args.hours, args.arrival), ensure_ascii=False, indent=2))
