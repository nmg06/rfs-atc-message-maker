"""Deterministic filtering/ranking. No network, LLM, random values or hidden clock."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
import json
from pathlib import Path

from .database import connect_readonly
from .time_utils import resolve_local
from .rfs_catalogue import SUPPORTED_TYPES, TYPE_BY_ID, observation_name


@dataclass
class Criteria:
    airline: str = ""
    aircraft: str = ""
    manufacturer: str = ""
    family: str = ""
    origin: list[str] = field(default_factory=list)
    destination: list[str] = field(default_factory=list)
    origin_country: list[str] = field(default_factory=list)
    destination_country: list[str] = field(default_factory=list)
    origin_continent: list[str] = field(default_factory=list)
    destination_continent: list[str] = field(default_factory=list)
    origin_region: list[str] = field(default_factory=list)
    destination_region: list[str] = field(default_factory=list)
    excluded_airports: list[str] = field(default_factory=list)
    min_minutes: float | None = None
    max_minutes: float | None = None
    target_minutes: float | None = None
    tolerance_minutes: float = 30
    departure_date: str = "today"
    departure_time: str = ""
    departure_tz: str = "Europe/Paris"
    arrival_date: str = "today"
    arrival_time: str = ""
    arrival_tz: str = "Europe/Paris"
    time_tolerance: float = 60
    international_only: bool = False
    real_only: bool = True
    limit: int = 30
    offset: int = 0
    diversify: bool = True
    rfs_only: bool = False
    rfs_aircraft_id: str = ""

    def validate(self):
        for key, value in vars(self).items():
            if isinstance(value, list) and (len(value) > 50 or any(not isinstance(v, str) or len(v)>100 for v in value)):
                raise ValueError(f"Invalid filter: {key}")
        for value in (self.min_minutes, self.max_minutes, self.target_minutes):
            if value is not None and (not math.isfinite(value) or not 0 < value <= 1440):
                raise ValueError("Duration must be between 1 and 1440 minutes")
        if self.min_minutes is not None and self.max_minutes is not None and self.min_minutes > self.max_minutes:
            raise ValueError("Minimum duration exceeds maximum duration")
        if not 0 <= self.offset <= 20000 or not 1 <= self.limit <= 100 or not 1 <= self.tolerance_minutes <= 1440 or not 1 <= self.time_tolerance <= 1440:
            raise ValueError("Invalid limit or tolerance")
        if not self.real_only:
            raise ValueError("Only observed routes are supported in Phase 1")


ALIASES = {"a320neo": "A20N", "a321neo": "A21N", "a319neo": "A19N", "b737max8": "B38M"}


def search(path: Path, criteria: Criteria, now_utc: datetime) -> dict:
    criteria.validate()
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now_utc = now_utc.astimezone(timezone.utc)
    warnings = ["DURATION_IS_AIRBORNE", "HISTORICAL_NOT_SCHEDULED"]
    departure = arrival = None
    for endpoint in ("departure", "arrival"):
        if getattr(criteria, endpoint + "_time"):
            instant, notices = resolve_local(getattr(criteria, endpoint + "_date"),
                getattr(criteria, endpoint + "_time"), getattr(criteria, endpoint + "_tz"), now_utc)
            warnings.extend(notices)
            if endpoint == "departure":
                departure = instant
            else:
                arrival = instant
    implied = (arrival - departure).total_seconds() / 60 if departure and arrival else None
    target = criteria.target_minutes
    if implied is not None:
        if implied <= 0:
            raise ValueError("ARRIVAL_BEFORE_DEPARTURE")
        if ((criteria.min_minutes is not None and implied < criteria.min_minutes) or
            (criteria.max_minutes is not None and implied > criteria.max_minutes) or
            (target is not None and abs(target-implied) > criteria.time_tolerance)):
            raise ValueError("TIME_INCONSISTENT")
        if target is None:
            target = implied
    where = ["n_obs >= 3", "duration_min IS NOT NULL"]
    params = []

    def in_filter(columns, values, negate=False):
        if not values:
            return
        pieces = []
        for column in columns:
            pieces.append(f"COALESCE(UPPER({column}), '') IN ({','.join('?' for _ in values)})")
            params.extend(v.strip().upper() for v in values)
        where.append(("NOT " if negate else "") + "(" + " OR ".join(pieces) + ")")

    for endpoint in ("origin", "destination"):
        codes = [v.strip().upper() for v in getattr(criteria, endpoint) if v.strip()]
        if codes:
            placeholders = ",".join("?" for _ in codes)
            where.append(f"{endpoint}_id IN (SELECT id FROM airports WHERE icao IN ({placeholders}) OR iata IN ({placeholders}))")  # nosec B608: fixed endpoint; only bound parameter markers are generated
            params.extend(codes * 2)
        for suffix in ("country", "continent", "region"):
            in_filter([endpoint + "_" + suffix], getattr(criteria, endpoint + "_" + suffix))
    if criteria.excluded_airports:
        ex_codes = [v.strip().upper() for v in criteria.excluded_airports if v.strip()]
        if ex_codes:
            placeholders = ",".join("?" for _ in ex_codes)
            where.append(f"origin_id NOT IN (SELECT id FROM airports WHERE icao IN ({placeholders}) OR iata IN ({placeholders}))")  # nosec B608: codes bound separately; placeholders contain only question marks
            where.append(f"destination_id NOT IN (SELECT id FROM airports WHERE icao IN ({placeholders}) OR iata IN ({placeholders}))")  # nosec B608: codes bound separately; placeholders contain only question marks
            params.extend(ex_codes * 4)
    if criteria.airline.strip():
        term = criteria.airline.strip()
        if len(term) <= 3 and term.isalnum():
            where.append("(airline = ? COLLATE NOCASE OR airline_iata = ? COLLATE NOCASE)")
            params.extend([term] * 2)
        else:
            where.append("instr(lower(airline_name), lower(?)) > 0")
            params.append(term)
    if criteria.rfs_only:
        in_filter(['aircraft'], SUPPORTED_TYPES)
    if criteria.rfs_aircraft_id:
        code = TYPE_BY_ID.get(criteria.rfs_aircraft_id)
        if not code:
            raise ValueError('RFS_TYPE_UNMAPPED')
        in_filter(['aircraft'], [code])
    if criteria.aircraft.strip():
        term = ALIASES.get(criteria.aircraft.lower().replace(" ", ""), criteria.aircraft.strip())
        where.append("(aircraft = ? COLLATE NOCASE OR instr(lower(aircraft_model), lower(?)) > 0)")
        params.extend([term, term])
    for key in ("manufacturer", "family"):
        if getattr(criteria, key).strip():
            where.append(f"{key} = ? COLLATE NOCASE")
            params.append(getattr(criteria, key).strip())
    if criteria.min_minutes is not None:
        where.append("duration_min >= ?")
        params.append(criteria.min_minutes)
    if criteria.max_minutes is not None:
        where.append("duration_min <= ?")
        params.append(criteria.max_minutes)
    if criteria.international_only:
        where.append("origin_country IS NOT NULL AND destination_country IS NOT NULL AND origin_country != destination_country")
    with connect_readonly(path) as db:
        candidates = [dict(row) for row in db.execute("SELECT * FROM v_pattern_search WHERE " + " AND ".join(where) +  # nosec B608 - SQL fragments/columns are fixed; all filter values bound
                      f" ORDER BY n_obs DESC,last_seen DESC,pattern_id ASC LIMIT {min(20001, max(1200, (criteria.offset + criteria.limit) * 10))}", params)]
        sources = [dict(r) for r in db.execute("SELECT * FROM sources ORDER BY source_id")]
        build = dict(db.execute("SELECT key,value FROM build_info"))
    if len(candidates) > 20000:
        warnings.append("CANDIDATE_LIMIT_REFINE_SEARCH")
        candidates = candidates[:20000]
    results = []
    for row in candidates:
        duration = row["duration_min"]
        last_seen = datetime.fromisoformat(row["last_seen"]).astimezone(timezone.utc)
        age_days = max(0, (now_utc-last_seen).total_seconds()/86400)
        parts = {"frequency": (10, min(1, math.log1p(row["n_obs"])/math.log1p(60))),
                 "recency": (5, .5 ** (age_days/30)),
                 "confidence": (5, row["n_complete"]/row["n_obs"])}
        if target is not None:
            tolerance = max(criteria.tolerance_minutes, .15 * target)
            fit = max(0, 1-abs(duration-target)/tolerance)
            if fit <= 0:
                continue
            parts["duration"] = (30, fit)
        elif criteria.max_minutes is not None:
            parts["duration"] = (30, min(1, duration/criteria.max_minutes))
        elif criteria.min_minutes is not None:
            parts["duration"] = (30, 1)
        proposed_departure = departure
        proposed_arrival = departure + timedelta(minutes=duration) if departure else None
        if arrival and not departure:
            proposed_arrival = arrival
            proposed_departure = arrival - timedelta(minutes=duration)
        if arrival and departure:
            delta = abs((proposed_arrival-arrival).total_seconds()/60)
            if delta > criteria.time_tolerance:
                continue
            # The implied duration already scores the same difference.
            if criteria.target_minutes is not None:
                parts["arrival"] = (25, max(0, 1-delta/criteria.time_tolerance))
        row["aircraft_display"] = observation_name(row["aircraft"], row["aircraft_model"])
        row["score"] = round(100 * sum(w*s for w,s in parts.values())/sum(w for w,s in parts.values()), 3)
        row["subscores"] = {k: round(v[1], 4) for k,v in parts.items()}
        row["warnings"] = []
        if row["n_obs"] < 5:
            row["warnings"].append("LOW_OBSERVATIONS")
        if age_days > 45:
            row["warnings"].append("STALE_DATA")
        if row["n_complete"] < row["n_obs"]:
            row["warnings"].append("PARTIAL_TRACKS_EXCLUDED_FROM_DURATION")
        if len(json.loads(row["type_mix"] or "[]")) > 1:
            row["warnings"].append("MIXED_AIRCRAFT_TYPES")
        if not row["origin_tz"] or not row["destination_tz"]:
            row["warnings"].append("TZ_UNKNOWN")
        row["sim_departure_utc"] = proposed_departure.isoformat() if proposed_departure else None
        row["sim_arrival_utc"] = proposed_arrival.isoformat() if proposed_arrival else None
        results.append(row)
    results.sort(key=lambda r: (-r["score"], -r["n_obs"], -datetime.fromisoformat(r["last_seen"]).timestamp(),
                               r["callsign"], r["origin"], r["destination"], r["pattern_id"]))
    diversified, counts = [], {}
    max_per_route = 10 if criteria.airline else 3
    for row in results:
        key = (row["airline"], row["origin"], row["destination"])
        if not criteria.diversify or counts.get(key, 0) < max_per_route:
            diversified.append(row)
            counts[key] = counts.get(key, 0) + 1
    return {"results": diversified[criteria.offset:criteria.offset + criteria.limit], "warnings": sorted(set(warnings)),
            "available": len(diversified), "diversity_dropped": len(results) - len(diversified),
            "offset": criteria.offset, "has_more": criteria.offset + criteria.limit < len(diversified),
            "candidates": len(candidates), "matches": len(results), "sources": sources, "build": build,
            "now_utc": now_utc.isoformat(), "implied_minutes": implied}
