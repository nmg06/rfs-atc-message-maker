"""Explicit duration input. Bare values retain the historical minute unit."""
import math
import re


def parse_minutes(text):
    value = str(text).strip().lower().replace(',', '.')
    if not value:
        return None
    match = re.fullmatch(r'(\d+)\s*:\s*(\d{2})', value)
    if match:
        hours, minutes = map(int, match.groups())
        if minutes >= 60:
            raise ValueError('DURATION_FORMAT')
        result = hours * 60 + minutes
    else:
        match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:h|heures?|hours?)\s*(?:(\d{1,2})\s*(?:m|min|minutes?)?)?', value)
        if match:
            minutes = int(match[2] or 0)
            if minutes >= 60:
                raise ValueError('DURATION_FORMAT')
            result = float(match[1]) * 60 + minutes
        else:
            match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:m|min|minutes?)?', value)
            if not match:
                raise ValueError('DURATION_FORMAT')
            result = float(match[1])
    if not math.isfinite(result) or not 0 < result <= 1440:
        raise ValueError('DURATION_RANGE')
    return result
