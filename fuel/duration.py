"""The existing Windows Fuel input parser, shared without Qt."""
import re


def duration_hours(text):
    text = str(text or '').strip().lower()
    if not text:
        return None
    match = re.fullmatch(r'(\d+)\s*(?:h|:)\s*(\d{1,2})\s*m?', text)
    if match:
        hours, minutes = map(int, match.groups())
        return hours + minutes / 60 if minutes < 60 else None
    match_min = re.fullmatch(r'(\d+(?:[\.,]\d+)?)\s*(?:m|min|minutes?)', text)
    if match_min:
        mins = float(match_min.group(1).replace(',', '.'))
        return mins / 60 if mins > 0 else None
    try:
        return float(text.rstrip('h').replace(',', '.')) if text else None
    except ValueError:
        return None
