"""Offline simulation planning. No invented gate, runway assignment or log hours."""
from datetime import datetime, timezone
import math
from finder.database import connect_readonly


def airport_plan(database, code):
    with connect_readonly(database) as db:
        airport = db.execute('SELECT * FROM airports WHERE icao=?', (str(code).strip().upper(),)).fetchone()
        if airport is None:
            return {'airport': None, 'runways': [], 'gates': [], 'gate_available': False}
        runways = [dict(r) for r in db.execute(
            'SELECT le_ident,he_ident,length_ft,surface FROM runways WHERE airport_id=? AND closed=0 ORDER BY length_ft DESC', (airport['id'],))]
        return {'airport': dict(airport), 'runways': runways, 'gates': [], 'gate_available': False}


def elapsed_seconds(session, now=None):
    result = float(session.get('seconds', 0))
    started = session.get('started_at')
    if started:
        instant = datetime.fromisoformat(started)
        result += max(0, ((now or datetime.now(timezone.utc)) - instant).total_seconds())
    return round(result)


def validate_log(active, log):
    if not isinstance(active, dict) or not isinstance(log, list) or len(log) > 500:
        raise ValueError('Invalid flight log')
    for item in ([active] if active else []) + log:
        if not isinstance(item, dict) or not isinstance(item.get('flight'), dict):
            raise ValueError('Invalid logged flight')
        seconds = item.get('seconds', 0)
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 365 * 86400:
            raise ValueError('Invalid logged duration')
        for key in ('started_at', 'completed_at'):
            if item.get(key):
                stamp = datetime.fromisoformat(item[key])
                if stamp.tzinfo is None:
                    raise ValueError('Flight log requires timezone')
