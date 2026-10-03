"""The existing Windows Fuel input parser, shared without Qt."""
import re


def duration_hours(text):
    text = str(text or '').strip().lower()
    match = re.fullmatch(r'(\d+)\s*(?:h|:)\s*(\d{1,2})\s*m?', text)
    if match:
        hours, minutes = map(int, match.groups())
        return hours + minutes / 60 if minutes < 60 else None
    try:
        return float(text.rstrip('h').replace(',', '.')) if text else None
    except ValueError:
        return None
