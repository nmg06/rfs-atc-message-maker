"""Persistance locale et récupération sûre des données RFS."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
import logging
import os
import re
from pathlib import Path
import shutil
import sys
import tempfile
import time
import uuid
from typing import Any

from rfs_schema import empty_flight, empty_per_type
from message_builder import DEFAULT_PRESENTATION
from history_utils import duplicate_index
from backup_bundle import (FILES, export_backup, parse_backup, merge_payloads,
                           desktop_state, preserve_device_preferences, summary, localise_error)


def data_directory() -> Path:
    override = os.environ.get("RFS_MESSAGE_MAKER_DATA_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).resolve().parent / "data"


DATA_DIR = data_directory()
STATE_FILE = DATA_DIR / "rfs_state.json"
HISTORY_FILE = DATA_DIR / "rfs_history.json"
PRESETS_FILE = DATA_DIR / "rfs_presets.json"
DESIGNS_FILE = DATA_DIR / "rfs_designs.json"
LOG_FILE = DATA_DIR / "app.log"

DEFAULT_STATE: dict[str, Any] = {
    "pilot_name": "n1chita",
    "pilot_library": [],
    "server": "",
    "theme": "Sombre",
    "visual_theme": "avionique",
    "message_type": "ATC REQUEST",
    "current_flight_id": "",
    "flight": empty_flight(),
    "per_type": empty_per_type(),
    "saved_flights": [],
    "preview_edits": {},
    "presentation": deepcopy(DEFAULT_PRESENTATION),
    "compact_history": True,
    "intro_seen": False,
    "tutorial_seen": False,
    "strict_validation": True,
    "recent": {"airline": [], "aircraft": [], "airports": [], "controllers": [], "servers": []},
}


def setup_logging() -> logging.Logger:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("rfs_atc_message_maker")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
    return logger


LOGGER = setup_logging()


def _merge(default: Any, loaded: Any) -> Any:
    if not isinstance(loaded, type(default)):
        return deepcopy(default)
    if isinstance(default, dict) and isinstance(loaded, dict):
        result = deepcopy(default)
        for key, value in loaded.items():
            result[key] = _merge(default[key], value) if key in default else value
        return result
    return loaded


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deepcopy(default)
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, type(default)):
            raise ValueError("Structure JSON inattendue")
        return _merge(default, value)
    except (OSError, ValueError, TypeError, UnicodeError) as error:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(path.name + f".corrupt-{stamp}")
        try:
            shutil.copy2(path, backup)
        except OSError:
            pass
        LOGGER.exception("Fichier %s illisible, valeurs par défaut restaurées : %s", path, error)
        return deepcopy(default)


def save_json(path: Path, value: Any) -> None:
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows can briefly lock the destination during another replacement.
        # Retry only access/sharing failures, then report a persistent disk error.
        for attempt in range(6):
            try:
                temporary.replace(path)
                break
            except PermissionError as error:
                if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 5:
                    raise
                time.sleep(.02 * (attempt + 1))
    except OSError as error:
        LOGGER.error("Impossible de sauvegarder %s : %s", path, error)
        raise
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                LOGGER.warning('Nettoyage du fichier temporaire impossible : %s', error)


def _restore_bytes(path: Path, original: bytes | None) -> None:
    if original is None:
        path.unlink(missing_ok=True)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def _profile_paths() -> dict:
    return {'state': STATE_FILE, 'history': HISTORY_FILE, 'presets': PRESETS_FILE, 'designs': DESIGNS_FILE}


def recover_import() -> None:
    """Finish an interrupted rollback before reading any of the profile files."""
    journal_path = DATA_DIR / 'import-transaction.json'
    if not journal_path.exists():
        return
    try:
        if journal_path.stat().st_size > 4096:
            raise ValueError('Invalid import journal')
        journal = json.loads(journal_path.read_text(encoding='utf-8'))
        if (not isinstance(journal, dict) or journal.get('format') != 'rfs-flightdeck-import'
                or type(journal.get('schema_version')) is not int or journal['schema_version'] != 1
                or journal.get('status') not in ('prepared', 'committed')
                or not isinstance(journal.get('backup'), str)
                or not re.fullmatch(r'before-import-\d{8}-\d{6}-[a-f0-9]{8}', journal['backup'])
                or not isinstance(journal.get('files'), dict) or set(journal['files']) != set(FILES)
                or not isinstance(journal.get('digests'), dict) or set(journal['digests']) != set(FILES)):
            raise ValueError('Invalid import journal')
        base = DATA_DIR.resolve()
        folder = (DATA_DIR / 'backups' / journal['backup']).resolve()
        if not folder.is_relative_to(base / 'backups'):
            raise ValueError('Invalid import backup path')
        originals = {}
        for name, key in FILES.items():
            exists, digest = journal['files'][name], journal['digests'][name]
            if type(exists) is not bool or (exists and (not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest))) or (not exists and digest is not None):
                raise ValueError('Invalid import snapshot')
            if journal['status'] == 'prepared':
                file = folder / name
                if not file.resolve().is_relative_to(folder):
                    raise ValueError('Invalid import snapshot path')
                original = file.read_bytes() if exists else None
                if exists and hashlib.sha256(original).hexdigest() != digest:
                    raise ValueError('Invalid import snapshot checksum')
                originals[key] = original
        if journal['status'] == 'prepared':
            for key, path in _profile_paths().items():
                _restore_bytes(path, originals[key])
        try:
            journal_path.unlink()
        except OSError:
            if journal['status'] != 'committed':
                raise
    except (ValueError, TypeError, KeyError, UnicodeError) as error:
        # A malformed journal cannot authorize arbitrary paths or partial restore.
        language = 'fr'
        try:
            if STATE_FILE.exists() and STATE_FILE.stat().st_size <= 2 * 1024 * 1024:
                saved_language = json.loads(STATE_FILE.read_text(encoding='utf-8-sig')).get('language')
                if saved_language in ('fr', 'en'):
                    language = saved_language
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        raise localise_error(error, language) from error


class Store:
    def __init__(self) -> None:
        recover_import()
        self.state: dict[str, Any] = load_json(STATE_FILE, DEFAULT_STATE)
        old_language = self.state.get('language', self.state.get('finder_language', 'fr'))
        self.state['language'] = old_language if old_language in ('fr', 'en') else 'fr'
        # Existing v3 users have already encountered the prop, even if they kept
        # the welcome screen enabled. Do not show it again during migration.
        self.state.setdefault('joke_seen', STATE_FILE.is_file())
        self.history: list[dict[str, Any]] = load_json(HISTORY_FILE, [])
        self.presets: dict[str, dict[str, Any]] = load_json(PRESETS_FILE, {})
        self.designs: dict[str, dict[str, Any]] = load_json(DESIGNS_FILE, {})

    def _backup_payload(self) -> dict:
        return {key: deepcopy(getattr(self, key)) for key in ('state', 'history', 'presets', 'designs')}

    def export_backup(self) -> str:
        from app_version import VERSION
        try:
            return export_backup(self._backup_payload(), platform='windows', version=VERSION)
        except (ValueError, TypeError, KeyError) as error:
            raise localise_error(error, self.state.get('language', 'fr')) from error

    def preview_import(self, value: str | dict) -> dict:
        return parse_backup(value, self.state.get('language', 'fr'))

    def import_backup(self, value: str | dict, mode: str = 'merge') -> dict:
        """Validate completely, save a dated safety copy, then commit all four files."""
        parsed = self.preview_import(value)
        if mode not in ('merge', 'replace'):
            raise localise_error(ValueError('Invalid import mode'), self.state.get('language', 'fr'))
        current = self._backup_payload()
        try:
            candidate = (merge_payloads(current, parsed['payload'], self.state.get('language', 'fr'))
                         if mode == 'merge' else deepcopy(parsed['payload']))
        except (ValueError, TypeError, KeyError) as error:
            raise localise_error(error, self.state.get('language', 'fr')) from error
        preserve_device_preferences(candidate, current)
        candidate['state'] = desktop_state(candidate['state'])
        paths = _profile_paths()
        originals = {key: path.read_bytes() if path.exists() else None for key, path in paths.items()}
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
        backup = DATA_DIR / 'backups' / ('before-import-' + stamp)
        backup.mkdir(parents=True, exist_ok=False)
        for name, key in FILES.items():
            if originals[key] is not None:
                _restore_bytes(backup / name, originals[key])
        # Also retain in-memory unsaved changes in a portable recovery file.
        _restore_bytes(backup / 'portable-backup.json', self.export_backup().encode('utf-8'))
        journal_path = DATA_DIR / 'import-transaction.json'
        journal = {'format': 'rfs-flightdeck-import', 'schema_version': 1, 'status': 'prepared',
            'backup': backup.name,
            'files': {name: originals[key] is not None for name, key in FILES.items()},
            'digests': {name: hashlib.sha256(originals[key]).hexdigest() if originals[key] is not None else None for name, key in FILES.items()}}
        save_json(journal_path, journal)
        try:
            for key, path in paths.items():
                save_json(path, candidate[key])
            save_json(journal_path, {**journal, 'status': 'committed'})
        except Exception:
            for key, path in paths.items():
                _restore_bytes(path, originals[key])
            journal_path.unlink(missing_ok=True)
            raise
        for key in paths:
            setattr(self, key, candidate[key])
        try:
            journal_path.unlink(missing_ok=True)
        except OSError:
            # The committed marker guarantees startup won't restore old data.
            pass
        return {'backup_path': str(backup), 'summary': summary(candidate), 'source': parsed['source']}

    def save_state(self) -> None:
        save_json(STATE_FILE, self.state)

    def remember_pilot(self, pilot: dict) -> None:
        name = str(pilot.get('name','')).strip()
        if not name:
            return
        record = {k: deepcopy(v) for k,v in pilot.items() if k != 'message_types'}
        record['name'] = name
        library = self.state.setdefault('pilot_library', [])
        for index, previous in enumerate(library):
            if previous.get('name','').casefold() == name.casefold():
                library[index] = {**previous, **record}
                break
        else:
            library.append(record)

    def save_history(self) -> None:
        save_json(HISTORY_FILE, self.history[:200])

    def add_history(self, entry: dict[str, Any]) -> bool:
        history = deepcopy(self.history)
        entry = deepcopy(entry)
        index = duplicate_index(history, entry, self.state.get("compact_history", True))
        if index is not None:
            previous = history.pop(index)
            entry["copies"] = previous.get("copies", 1) + 1
        history.insert(0, entry)
        history = history[:200]
        save_json(HISTORY_FILE, history)
        self.history = history
        return index is not None

    def save_design(self, key: str, design: dict) -> None:
        designs = {**self.designs, key: deepcopy(design)}
        save_json(DESIGNS_FILE, designs)
        self.designs = designs

    def save_preset(self, name: str, preset: dict[str, Any]) -> None:
        presets = {**self.presets, name: deepcopy(preset)}
        save_json(PRESETS_FILE, presets)
        self.presets = presets

    def remember(self, category: str, value: str) -> None:
        value = value.strip()
        if not value:
            return
        recent = self.state.setdefault("recent", {}).setdefault(category, [])
        recent[:] = [item for item in recent if item.casefold() != value.casefold()]
        recent.insert(0, value)
        del recent[12:]
