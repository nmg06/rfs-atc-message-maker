"""Persistance locale et récupération sûre des données RFS."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any

from rfs_schema import empty_flight, empty_per_type
from message_builder import DEFAULT_PRESENTATION
from history_utils import duplicate_index


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


class Store:
    def __init__(self) -> None:
        self.state: dict[str, Any] = load_json(STATE_FILE, DEFAULT_STATE)
        old_language = self.state.get('language', self.state.get('finder_language', 'fr'))
        self.state['language'] = old_language if old_language in ('fr', 'en') else 'fr'
        # Existing v3 users have already encountered the prop, even if they kept
        # the welcome screen enabled. Do not show it again during migration.
        self.state.setdefault('joke_seen', STATE_FILE.is_file())
        self.history: list[dict[str, Any]] = load_json(HISTORY_FILE, [])
        self.presets: dict[str, dict[str, Any]] = load_json(PRESETS_FILE, {})
        self.designs: dict[str, dict[str, Any]] = load_json(DESIGNS_FILE, {})

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
