"""Rebuild the dated offline Finder snapshot from hash-verified public sources.

This is a build tool, never imported by the application. Reference CSVs are
frozen in the small repository archive; the two large Parquet files are a
maintainer cache or an explicit --download. No account or token is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SOURCE_DIR = ROOT / "finder" / "source-data"
MANIFEST = SOURCE_DIR / "source-manifest-2026-10-06.json"
REFERENCES = SOURCE_DIR / "reference-snapshot-2026-09-30.zipdata"
REFERENCES_SHA256 = "d0b44c0ff83dee89eb606c2ad227780733767b7ea75a6cc512a7e1587698f1e6"
WINDOW_DAYS = 181


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(4 * 1024 * 1024):
            checksum.update(block)
    return checksum.hexdigest()


def verify(path: Path, entry: dict) -> None:
    if not path.is_file() or path.stat().st_size != entry["bytes"] or digest(path) != entry["sha256"]:
        raise ValueError(f"Source does not match its pinned manifest: {entry['file']}")


def entries_from_manifest(path: Path = MANIFEST) -> list[dict]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Empty source manifest")
    names = set()
    for entry in entries:
        name = entry.get("file", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in names:
            raise ValueError("Invalid or duplicate source filename")
        names.add(name)
        if isinstance(entry.get("bytes"), bool) or not isinstance(entry.get("bytes"), int) or not 0 < entry["bytes"] < 2_000_000_000:
            raise ValueError("Invalid source byte count")
        if not re.fullmatch(r"[a-f0-9]{64}", entry.get("sha256", "")):
            raise ValueError("Invalid source checksum")
        if name.endswith(".parquet") and not re.fullmatch(
            r"https://github\.com/MrAirspace/aircraft-flight-schedules/releases/download/"
            r"aircraft_flight_schedules_2026_quarter[12]/2026_Q[12]_detailed_github\.parquet",
            entry.get("url", ""),
        ):
            raise ValueError("Unapproved flight source URL")
    return entries


def unpack_references(cache: Path, entries: list[dict], archive: Path = REFERENCES) -> None:
    if digest(archive) != REFERENCES_SHA256:
        raise ValueError("Frozen reference archive checksum mismatch")
    references = {entry["file"]: entry for entry in entries if not entry["file"].endswith(".parquet")}
    cache.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        if set(bundle.namelist()) != set(references):
            raise ValueError("Reference archive and manifest disagree")
        for name, entry in references.items():
            path = cache / name
            if path.exists():
                verify(path, entry)
                continue
            content = bundle.read(name)
            if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise ValueError(f"Invalid frozen reference: {name}")
            with path.open("xb") as stream:
                stream.write(content)


def download_source(cache: Path, entry: dict) -> None:
    destination = cache / entry["file"]
    temporary = destination.with_name(destination.name + ".part")
    if temporary.exists():
        raise ValueError(f"Preserve or move the previous partial source before retrying: {temporary}")
    request = urllib.request.Request(entry["url"], headers={"User-Agent": "RFSFlightdeck-build-source/1"})
    checksum = hashlib.sha256()
    count = 0
    print(f"Downloading pinned build source {entry['file']} ({entry['bytes']:,} bytes)", flush=True)
    try:
        with urllib.request.urlopen(request, timeout=30) as response, temporary.open("xb") as stream:
            for block in iter(lambda: response.read(4 * 1024 * 1024), b""):
                count += len(block)
                if count > entry["bytes"]:
                    raise ValueError("Source exceeds pinned byte count")
                checksum.update(block)
                stream.write(block)
        if count != entry["bytes"] or checksum.hexdigest() != entry["sha256"]:
            raise ValueError("Downloaded source checksum or byte count mismatch")
        temporary.replace(destination)
    except Exception:
        # Preserve partial input for diagnosis; never replace a verified cache.
        raise


def rebuild(cache: Path, output: Path, *, download: bool = False,
            memory_mb: int = 512, threads: int = 1) -> None:
    from finder.importer import build

    entries = entries_from_manifest()
    unpack_references(cache, entries)
    parquets = []
    for entry in entries:
        if not entry["file"].endswith(".parquet"):
            continue
        source = cache / entry["file"]
        if not source.exists():
            if not download:
                raise ValueError(f"Missing {entry['file']}; supply the verified cache or use --download")
            download_source(cache, entry)
        verify(source, entry)
        parquets.append(source)
    # Build stages a .building file, validates SQLite, then replaces output.
    # Use a candidate output first so an existing public snapshot is retained.
    build(cache, output, window_days=WINDOW_DAYS, parquet_files=parquets,
          source_manifest=MANIFEST, memory_mb=memory_mb, threads=threads)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "build/finder-rebuild/aviation.sqlite")
    parser.add_argument("--download", action="store_true", help="Fetch missing pinned Parquet quarters at build time")
    parser.add_argument("--memory-mb", type=int, default=512)
    parser.add_argument("--threads", type=int, default=1)
    arguments = parser.parse_args()
    rebuild(arguments.cache.resolve(), arguments.output.resolve(), download=arguments.download,
            memory_mb=arguments.memory_mb, threads=arguments.threads)
