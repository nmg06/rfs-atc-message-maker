"""Package an isolated portable Windows build with the public offline database."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def package(dist, archive):
    dist, archive = Path(dist).resolve(), Path(archive).resolve()
    if not (dist/'RFSATCMessageMaker.exe').is_file():
        raise ValueError('Build the Windows executable before packaging')
    manifest = json.loads((ROOT/'android/bundled/database-manifest.json').read_text())
    data = dist/'finder-data'
    data.mkdir(exist_ok=True)
    with gzip.open(ROOT/'android/bundled/aviation.sqlite.gz', 'rb') as src, (data/'aviation.sqlite').open('wb') as dst:
        shutil.copyfileobj(src, dst)
    if hashlib.sha256((data/'aviation.sqlite').read_bytes()).hexdigest() != manifest['database_sha256']:
        raise ValueError('Public database hash mismatch')
    for name in ('README.md', 'LICENSE-ODbL.txt', 'aviation.report.json'):
        source = ROOT/'android/bundled'/name
        if source.is_file():
            shutil.copy2(source, data/name)
    shutil.copy2(ROOT/'README.md', dist/'README.md')
    for folder in ('docs',):
        shutil.copytree(ROOT/folder, dist/folder, dirs_exist_ok=True)
    # Only this newly built public package is archived, never a user's data folder.
    if (dist/'data').exists():
        raise ValueError('Refusing to archive a package containing a user profile')
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for source in sorted(dist.rglob('*')):
            if source.is_file():
                output.write(source, Path('RFSFlightdeck')/source.relative_to(dist))
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,
                      'database_sha256':manifest['database_sha256']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', default='dist/RFSATCMessageMaker')
    parser.add_argument('--archive', default='dist/RFSFlightdeck-Windows-x64-test.zip')
    args = parser.parse_args()
    package(args.dist, args.archive)
