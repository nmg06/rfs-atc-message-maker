from pathlib import Path

f = Path('finder/search.py')
text = f.read_text(encoding='utf-8')

old_code = '''    for endpoint in ("origin", "destination"):
        in_filter([endpoint, endpoint + "_iata"], getattr(criteria, endpoint))
        for suffix in ("country", "continent", "region"):
            in_filter([endpoint + "_" + suffix], getattr(criteria, endpoint + "_" + suffix))
    in_filter(["origin", "origin_iata", "destination", "destination_iata"], criteria.excluded_airports, True)'''

new_code = '''    for endpoint in ("origin", "destination"):
        codes = [v.strip().upper() for v in getattr(criteria, endpoint) if v.strip()]
        if codes:
            placeholders = ",".join("?" for _ in codes)
            where.append(f"{endpoint}_id IN (SELECT id FROM airports WHERE icao IN ({placeholders}) OR iata IN ({placeholders}))")
            params.extend(codes * 2)
        for suffix in ("country", "continent", "region"):
            in_filter([endpoint + "_" + suffix], getattr(criteria, endpoint + "_" + suffix))
    if criteria.excluded_airports:
        ex_codes = [v.strip().upper() for v in criteria.excluded_airports if v.strip()]
        if ex_codes:
            placeholders = ",".join("?" for _ in ex_codes)
            where.append(f"origin_id NOT IN (SELECT id FROM airports WHERE icao IN ({placeholders}) OR iata IN ({placeholders}))")
            where.append(f"destination_id NOT IN (SELECT id FROM airports WHERE icao IN ({placeholders}) OR iata IN ({placeholders}))")
            params.extend(ex_codes * 4)'''

assert old_code in text, 'old_code not found'
text = text.replace(old_code, new_code)
f.write_text(text, encoding='utf-8')
print('Successfully optimized search endpoint queries!')
