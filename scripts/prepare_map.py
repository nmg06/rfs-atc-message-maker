"""Convert a Natural Earth GeoJSON download into deterministic offline geometry.

Usage: python scripts/prepare_map.py /path/ne_50m_admin_0_countries.geojson
Source: https://github.com/nvkelso/natural-earth-vector/tree/master/geojson
No network requests at application startup.
"""
import hashlib
import json
from pathlib import Path
import sys


def convert(source, output):
    raw = Path(source).read_bytes()
    countries = []
    for feature in json.loads(raw)['features']:
        props, geometry = feature['properties'], feature['geometry']
        code = props.get('ISO_A2_EH') or props.get('ISO_A2')
        if code == '-99':
            code = props.get('ISO_A2')
        polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        countries.append({'code': code if code != '-99' else '',
                          'name': props.get('NAME_EN') or props['NAME'],
                          'polygons': [[[[round(lon, 4), round(lat, 4)] for lon, lat in ring]
                                        for ring in polygon] for polygon in polygons]})
    data = {'source': 'Natural Earth 1:50m admin-0 countries', 'license': 'Public domain',
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'countries': sorted(countries, key=lambda row: (row['code'], row['name']))}
    Path(output).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"{len(countries)} country features; {Path(output).stat().st_size} bytes; source SHA256 {data['source_sha256']}")


if __name__ == '__main__':
    convert(sys.argv[1], Path(__file__).resolve().parents[1] / 'assets/world_countries.json')
