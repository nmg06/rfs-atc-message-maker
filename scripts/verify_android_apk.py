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


def verify(apk, aapt, *, require_release=False, apksigner=None, expected_cert_sha256=None):
    with zipfile.ZipFile(apk) as package:
        for name in ('assets/www/index.html', 'assets/www/app.js', 'assets/www/app.css', 'assets/www/compat.js', 'assets/www/compat-check.html',
                     'assets/www/map.js', 'assets/www/experience.js', 'assets/www/online-map.js', 'assets/www/world-countries.js',
                     'assets/www/help-content.js', 'assets/www/help-ui.js', 'assets/www/help-ui.css', 'assets/www/help-adapter.js',
                     'assets/www/updates-ui.js', 'assets/www/backup-ui.js',
                     'assets/www/workspace.js', 'assets/www/workspace.css',
                     'assets/notices/WORLD_MAP_LICENSE.md', 'assets/engine-manifest.json', 'assets/aviation.database'):
            if name not in package.namelist():
                raise ValueError('Missing APK asset: ' + name)
        # Verify the delivered UI too: an incremental build must not silently
        # package an earlier screen while shared engines pass their tests.
        source_root = Path(__file__).resolve().parents[1] / 'android/app/src/main/assets/www'
        for source in source_root.iterdir():
            if source.is_file() and package.read('assets/www/' + source.name) != source.read_bytes():
                raise ValueError('APK UI differs from source: ' + source.name)
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
    certificate = None
    if require_release:
        if not apksigner or not expected_cert_sha256 or not re.fullmatch(r'[0-9a-fA-F]{64}', expected_cert_sha256):
            raise ValueError('Release verification requires apksigner and the expected SHA-256 certificate')
        badging = subprocess.check_output([str(aapt), 'dump', 'badging', str(apk)], text=True)
        if 'application-debuggable' in badging:
            raise ValueError('Refusing a debuggable APK as a release candidate')
        signatures = subprocess.check_output([str(apksigner), 'verify', '--verbose', '--print-certs', str(apk)], text=True)
        certificates = re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})', signatures)
        if [value.lower() for value in certificates] != [expected_cert_sha256.lower()]:
            raise ValueError('APK signing certificate differs from the expected public release key')
        certificate = certificates[0]
    print(json.dumps({'apk': str(Path(apk).resolve()), 'bytes': Path(apk).stat().st_size,
        'database_bytes': size, 'database_sha256': digest.hexdigest(), 'permissions': sorted(actual),
        'release_verified': require_release, 'certificate_sha256': certificate}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('apk', type=Path)
    parser.add_argument('--aapt', type=Path, required=True)
    parser.add_argument('--require-release', action='store_true')
    parser.add_argument('--apksigner', type=Path)
    parser.add_argument('--expected-cert-sha256')
    args = parser.parse_args()
    verify(args.apk, args.aapt, require_release=args.require_release,
           apksigner=args.apksigner, expected_cert_sha256=args.expected_cert_sha256)
