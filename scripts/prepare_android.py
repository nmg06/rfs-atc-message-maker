"""Deterministically stage existing engines/data; never rewrite Windows sources."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'android'
MODULES = ['map_geometry.py', 'rfs_schema.py', 'templates.py', 'validation.py', 'message_builder.py',
           'emoji_tokens.py', 'finder/provenance.py', 'fuel/selection.py', 'fuel/duration.py',
           'history_utils.py', 'country_data.py', 'ui_translations.py',
           'finder/__init__.py', 'finder/database.py', 'finder/search.py',
           'finder/mapping.py', 'finder/time_utils.py', 'finder/duration.py',
           'finder/rfs_catalogue.py', 'finder/i18n.py', 'fuel/__init__.py', 'fuel/calculator.py']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(database=None):
    bundled = ANDROID / 'bundled'
    bundled.mkdir(parents=True, exist_ok=True)
    if database:
        database = Path(database).resolve()
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
            assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            assert db.execute('PRAGMA user_version').fetchone()[0] == 1
        with database.open('rb') as src, (bundled / 'aviation.sqlite.gz').open('wb') as raw:
            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as dst:
                shutil.copyfileobj(src, dst)
        manifest = {'schema_version': 1, 'database_sha256': digest(database),
                    'database_bytes': database.stat().st_size,
                    'gzip_sha256': digest(bundled / 'aviation.sqlite.gz')}
        (bundled / 'database-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        for name in ['README.md', 'LICENSE-ODbL.txt', 'aviation.report.json']:
            if (database.parent / name).exists():
                shutil.copy2(database.parent / name, bundled / name)
    if not (bundled / 'aviation.sqlite.gz').is_file():
        raise SystemExit('Missing bundled database: prepare_android.py --database path/to/aviation.sqlite')
    manifest = json.loads((bundled / 'database-manifest.json').read_text())
    if digest(bundled / 'aviation.sqlite.gz') != manifest['gzip_sha256']:
        raise SystemExit('Bundled database checksum mismatch')
    generated = ANDROID / 'app/build/generated'
    python = generated / 'python'
    assets = generated / 'assets'
    hashes = {}
    for name in MODULES:
        dest = python / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, dest)
        hashes[name] = digest(ROOT / name)
    # New exports shared with desktop remain pure Python: Qt/online map modules
    # are deliberately absent from this list and the APK has no INTERNET permission.
    for name in ['aircraft_fuel_data.json', 'airport_alternates.json']:
        source = ROOT / 'docs/fuel/reference' / name
        for dest in [python / 'fuel/data' / name, ROOT / 'fuel/data' / name]:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        hashes['docs/fuel/reference/' + name] = digest(source)
    assets.mkdir(parents=True, exist_ok=True)
    # One authoritative dataset for Windows and Android, transformed at build time.
    countries = ROOT / 'assets/world_countries.json'
    world = json.loads(countries.read_text(encoding='utf-8'))
    web_assets = assets / 'www'
    web_assets.mkdir(parents=True, exist_ok=True)
    (web_assets / 'world-countries.js').write_text(
        'window.FLIGHTDECK_COUNTRIES=' + json.dumps(world, ensure_ascii=False, separators=(',', ':')) + ';\n',
        encoding='utf-8')
    hashes['assets/world_countries.json'] = digest(countries)
    for source in bundled.iterdir():
        if source.is_file():
            # AAPT treats a .gz asset specially (strips suffix/decompresses it).
            # Keep gzip bytes under a neutral name to match native installation.
            name = 'aviation.database' if source.name == 'aviation.sqlite.gz' else source.name
            shutil.copy2(source, assets / name)
    (assets / 'aviation.sqlite.gz').unlink(missing_ok=True)
    notices = assets / 'notices'
    shutil.copytree(ROOT / 'docs/licenses', notices, dirs_exist_ok=True)
    shutil.copy2(ROOT / 'assets/WORLD_MAP_LICENSE.md', notices / 'WORLD_MAP_LICENSE.md')
    (assets / 'engine-manifest.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    print(f'Android engines staged from {len(hashes)} existing source/data files; database bundled.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database')
    prepare(parser.parse_args().database)
