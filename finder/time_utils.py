"""Timezone-aware wall-clock resolution, independent of the computer timezone."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def local_to_utc(local: datetime, tz_name: str) -> tuple[datetime, list[str]]:
    if local.tzinfo is not None:
        raise ValueError("Expected a naive local datetime")
    try:
        zone = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"Unknown IANA timezone: {tz_name}") from error
    warnings = []
    for minute in range(181):
        probe = local + timedelta(minutes=minute)
        candidates = set()
        for fold in (0, 1):
            instant = probe.replace(tzinfo=zone, fold=fold).astimezone(UTC)
            if instant.astimezone(zone).replace(tzinfo=None) == probe:
                candidates.add(instant)
        if candidates:
            if minute:
                warnings.append("DST_GAP_SHIFTED")
            if len(candidates) > 1:
                warnings.append("DST_AMBIGUOUS_EARLIER")
            return min(candidates), warnings
    raise ValueError("Unable to resolve local time within three hours")


def resolve_local(day: str, clock: str, tz_name: str, now: datetime):
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    zone = ZoneInfo(tz_name)
    if day in ("today", "tomorrow"):
        local_day = now.astimezone(zone).date() + timedelta(days=day == "tomorrow")
    else:
        local_day = date.fromisoformat(day)
    time = datetime.strptime(clock, "%H:%M").time()
    return local_to_utc(datetime.combine(local_day, time), tz_name)


def circular_median(minutes: list[int]) -> int | None:
    if not minutes:
        return None
    # Minimize circular L1 distance; deterministic earliest-minute tie break.
    candidates = sorted(set(minutes))
    return min(candidates, key=lambda x: (sum(min(abs(x-y), 1440-abs(x-y)) for y in minutes), x))
