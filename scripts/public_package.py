"""Public packages must never contain a maintainer profile or private signing key."""
from pathlib import Path, PurePosixPath
import zipfile

PRIVATE_NAMES={'rfs_state.json','rfs_history.json','rfs_presets.json','rfs_designs.json','rfs_android.json','rfs_updates.json','app.log','.env','rfs-flightdeck-backup.json','portable-backup.json'}
PRIVATE_SUFFIXES={'.jks','.keystore','.p12'}


def private_path(name):
    path=PurePosixPath(str(name).replace('\\','/'))
    return path.name.lower() in PRIVATE_NAMES or path.suffix.lower() in PRIVATE_SUFFIXES or any(part in ('.private-signing','backups') for part in path.parts) or (path.name.lower().startswith('rfs_') and ('.corrupt-' in path.name or '.before-import.' in path.name))


def verify_directory(root):
    root=Path(root)
    for path in root.rglob('*'):
        if path.is_file() and private_path(path.relative_to(root).as_posix()):
            raise ValueError('Private user/configuration data in public package: '+str(path.relative_to(root)))
    if (root/'data').exists():raise ValueError('Public package contains a user data directory')


def verify_archive(archive):
    with zipfile.ZipFile(archive) as package:
        unsafe=[name for name in package.namelist() if private_path(name)]
        if unsafe:raise ValueError('Private user/configuration data in public archive: '+', '.join(unsafe))
    return True
