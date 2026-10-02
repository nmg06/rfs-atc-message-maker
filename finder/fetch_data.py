"""Explicit build-time download; never imported by the desktop UI.

Usage: python -m finder.fetch_data --directory PATH
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
from urllib.parse import urlparse
from datetime import datetime, timezone

RELEASES = "https://api.github.com/repos/MrAirspace/aircraft-flight-schedules/releases?per_page=5"
REFERENCES = {
    **{name: f"https://davidmegginson.github.io/ourairports-data/{name}"
       for name in ("airports.csv", "runways.csv", "countries.csv", "regions.csv")},
    "airlines.csv": "https://raw.githubusercontent.com/vradarserver/standing-data/master/airlines/schema-01/airlines.csv",
    **{f"models-{letter}.csv": f"https://raw.githubusercontent.com/vradarserver/standing-data/main/model-type/schema-01/{letter}.csv"
       for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"},
    "LICENSE-ODbL.txt": "https://raw.githubusercontent.com/MrAirspace/aircraft-flight-schedules/main/LICENSE-ODbL.txt",
}


def download(url: str, target: Path, expected_size: int | None = None) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'github.com', 'raw.githubusercontent.com', 'davidmegginson.github.io'}:
        raise ValueError('Only the configured HTTPS public data sources are allowed')
    if not target.exists() or (expected_size and target.stat().st_size != expected_size):
        temporary = target.with_suffix(target.suffix + ".part")
        print(f"Downloading {target.name}", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "RFS-Local-Finder/1"})
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as out:  # nosec B310 - HTTPS/source allowlist above
            total = 0
            while chunk := response.read(4 * 1024 * 1024):
                out.write(chunk)
                total += len(chunk)
                if total % (64 * 1024 * 1024) == 0:
                    print(f"  {total // 1024 // 1024} MiB", flush=True)
        if expected_size and temporary.stat().st_size != expected_size:
            raise ValueError(f"Truncated download: {target}")
        temporary.replace(target)
    with target.open('rb') as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"url": url, "file": target.name, "bytes": target.stat().st_size,
            "sha256": digest, "retrieved_at": datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(RELEASES, timeout=30) as response:  # nosec B310 - constant GitHub HTTPS URL
        releases = json.load(response)
    asset = next(a for r in releases for a in r["assets"] if a["name"].endswith(".parquet"))
    if Path(asset['name']).name != asset['name'] or ':' in asset['name']:
        raise ValueError('Unexpected release asset filename')
    manifest = [download(asset["browser_download_url"], args.directory / asset["name"], asset["size"])]
    for name, url in REFERENCES.items():
        manifest.append(download(url, args.directory / name))
    (args.directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Source files ready.", flush=True)


if __name__ == "__main__":
    main()
