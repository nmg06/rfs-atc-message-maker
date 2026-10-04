"""Verify the actual APK payload, including AAPT's treatment of gzip assets."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def verify(apk, aapt):
    with zipfile.ZipFile(apk) as package:
        for name in ('assets/www/index.html', 'assets/www/app.js', 'assets/www/app.css',
                     'assets/www/map.js', 'assets/www/experience.js', 'assets/www/online-map.js', 'assets/www/world-countries.js',
                     'assets/www/help-content.js', 'assets/www/help-ui.js', 'assets/www/help-ui.css', 'assets/www/help-adapter.js',
                     'assets/www/updates-ui.js', 'assets/www/backup-ui.js',
                     'assets/notices/WORLD_MAP_LICENSE.md', 'assets/engine-manifest.json', 'assets/aviation.database'):
            if name not in package.namelist():
                raise ValueError('Missing APK asset: ' + name)
        manifest = json.loads(package.read('assets/database-manifest.json'))
        from help_content import CONTENT
        guide = package.read('assets/www/help-content.js').decode('utf-8')
        if json.loads(guide.removeprefix('window.FLIGHTDECK_HELP=')[:-2]) != CONTENT:
            raise ValueError('APK guide differs from shared bilingual catalogue')
        engine = json.loads(package.read('assets/engine-manifest.json'))
        prefix = 'window.FLIGHTDECK_COUNTRIES='
        source = package.read('assets/www/world-countries.js').decode('utf-8')
        if not source.startswith(prefix) or not source.endswith(';\n'):
            raise ValueError('Invalid bundled country data script')
        countries = json.loads(source[len(prefix):-2])
        expected = json.loads((Path(__file__).resolve().parents[1] / 'assets/world_countries.json').read_text(encoding='utf-8'))
        if countries != expected or len(countries['countries']) != 242 or 'map_geometry.py' not in engine:
            raise ValueError('Bundled map differs from the shared Windows source')
        digest = hashlib.sha256()
        size = 0
        with package.open('assets/aviation.database') as raw, gzip.GzipFile(fileobj=raw) as database:
            while block := database.read(65536):
                digest.update(block)
                size += len(block)
        if digest.hexdigest() != manifest['database_sha256'] or size != manifest['database_bytes']:
            raise ValueError('APK database checksum or size mismatch')
    permissions = subprocess.check_output([str(aapt), 'dump', 'permissions', str(apk)], text=True)
    import re
    actual = set(re.findall(r"uses-permission: name='([^']+)'", permissions))
    allowed = {'android.permission.INTERNET','android.permission.POST_NOTIFICATIONS','android.permission.RECEIVE_BOOT_COMPLETED',
               'com.nmg06.rfsatc.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'}
    if actual != allowed:
        raise ValueError('Unexpected permission in actual APK: ' + permissions)
    print(json.dumps({'apk': str(Path(apk).resolve()), 'bytes': Path(apk).stat().st_size,
        'database_bytes': size, 'database_sha256': digest.hexdigest(), 'permissions': sorted(actual)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('apk', type=Path)
    parser.add_argument('--aapt', type=Path, required=True)
    args = parser.parse_args()
    verify(args.apk, args.aapt)
