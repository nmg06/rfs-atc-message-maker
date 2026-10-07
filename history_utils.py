"""Regroupement prudent : une correction typographique n'est pas un nouveau vol."""
from datetime import datetime
from difflib import SequenceMatcher
import json
import re


def normalized(text):
    return re.sub(r"\s+", " ", str(text)).strip().casefold()


def same_operational_context(first, second):
    keys = ("callsign", "flight_number", "aircraft", "departure_icao", "arrival_icao",
            "departure_runway", "arrival_runway", "departure_gate", "arrival_gate",
            "cruise_fl", "distance", "estimated_flight_time", "passengers", "cargo", "fuel",
            "pilots", "departure_mode", "arrival_mode")
    f1 = first.get("flight") or {}
    f2 = second.get("flight") or {}
    for key in keys:
        a, b = f1.get(key, ""), f2.get(key, "")
        if normalized(json.dumps(a, sort_keys=True)) != normalized(json.dumps(b, sort_keys=True)):
            return False
    if normalized(first.get("pilot_name")) != normalized(second.get("pilot_name")):
        return False
    return (first.get("data") or {}) == (second.get("data") or {})


def duplicate_index(history, entry, compact=True):
    message = normalized(entry.get("message", ""))
    for index, previous in enumerate(history):
        if previous.get("message_type") != entry.get("message_type"):
            continue
        old = normalized(previous.get("message", ""))
        if old == message:
            return index
        if not compact or not same_operational_context(previous, entry):
            continue
        try:
            elapsed = abs((datetime.fromisoformat(entry["date"]) - datetime.fromisoformat(previous["date"])).total_seconds())
        except (KeyError, ValueError, TypeError):
            continue
        if elapsed <= 900 and abs(len(old) - len(message)) <= 8 and SequenceMatcher(None, old, message).ratio() >= .98:
            return index
    return None
