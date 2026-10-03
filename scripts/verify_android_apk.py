"""Verify the actual APK payload, including AAPT's treatment of gzip assets."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def verify(apk, aapt):
    with zipfile.ZipFile(apk) as package:
        for name in ('assets/www/index.html', 'assets/www/app.js', 'assets/www/app.css',
                     'assets/engine-manifest.json', 'assets/aviation.database'):
            if name not in package.namelist():
                raise ValueError('Missing APK asset: ' + name)
        manifest = json.loads(package.read('assets/database-manifest.json'))
        digest = hashlib.sha256()
        size = 0
        with package.open('assets/aviation.database') as raw, gzip.GzipFile(fileobj=raw) as database:
            while block := database.read(65536):
                digest.update(block)
                size += len(block)
        if digest.hexdigest() != manifest['database_sha256'] or size != manifest['database_bytes']:
            raise ValueError('APK database checksum or size mismatch')
    permissions = subprocess.check_output([str(aapt), 'dump', 'permissions', str(apk)], text=True)
    if any(line.strip().startswith('uses-permission') for line in permissions.splitlines()):
        raise ValueError('Unexpected permission in actual APK: ' + permissions)
    print(json.dumps({'apk': str(Path(apk).resolve()), 'bytes': Path(apk).stat().st_size,
        'database_bytes': size, 'database_sha256': digest.hexdigest(), 'permissions': []}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('apk', type=Path)
    parser.add_argument('--aapt', type=Path, required=True)
    args = parser.parse_args()
    verify(args.apk, args.aapt)
