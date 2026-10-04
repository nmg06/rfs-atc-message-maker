"""Opt-in public release discovery. Never uploads state or installs software."""
from __future__ import annotations

from datetime import datetime
import json
import math
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app_version import VERSION

REPOSITORY = 'nmg06/rfs-atc-message-maker'
RELEASES_URL = f'https://github.com/{REPOSITORY}/releases'
ENDPOINT = f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=100'
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 8
INTERVAL_SECONDS = 24 * 60 * 60
_VERSION = re.compile(r'(?:v)?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-flightdeck)?', re.I)


def version_tuple(value):
    """Accept stable project tags, excluding preview/debug/beta channels."""
    if not isinstance(value, str) or len(value) > 80:
        return None
    match = _VERSION.fullmatch(value)
    return tuple(map(int, match.groups())) if match else None


def trusted_release_url(value, *, download=False):
    """Only open HTTPS links owned by this repository's release pages."""
    if not isinstance(value, str) or len(value) > 2048:
        return False
    try:
        parsed = urlsplit(value)
        decoded = unquote(parsed.path)
        prefix = f'/{REPOSITORY}/releases/'
        needed = prefix + ('download/' if download else 'tag/')
        return (parsed.scheme == 'https' and parsed.netloc == 'github.com'
                and not parsed.query and not parsed.fragment
                and decoded.startswith(needed) and len(decoded) > len(needed)
                and not any(part in ('.', '..') for part in decoded.split('/'))
                and '\\' not in decoded and not any(ord(c) < 32 for c in decoded))
    except ValueError:
        return False


def select_release(releases, platform='windows', current_version=VERSION, *, now=None):
    """Select the newest eligible stable platform asset from public metadata."""
    current = version_tuple(current_version)
    if platform not in ('windows', 'android') or current is None:
        raise ValueError('Unsupported platform or current version')
    if not isinstance(releases, list) or len(releases) > 100:
        return {'status': 'unavailable', 'reason': 'invalid_response'}
    now = time.time() if now is None else float(now)
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get('draft') is not False or release.get('prerelease') is not False:
            continue
        version = version_tuple(release.get('tag_name'))
        if version is None or not trusted_release_url(release.get('html_url')):
            continue
        tag = release['tag_name']
        if unquote(urlsplit(release['html_url']).path) != f'/{REPOSITORY}/releases/tag/{tag}':
            continue
        published = release.get('published_at')
        if not isinstance(published, str):
            continue
        try:
            stamp = datetime.fromisoformat(published.replace('Z', '+00:00'))
            if stamp.tzinfo is None or stamp.timestamp() > now:
                continue
        except (ValueError, OverflowError, OSError):
            continue
        number = '.'.join(map(str, version))
        prefix = f'RFSFlightdeck-{platform.title()}-{number}'
        assets = release.get('assets')
        if not isinstance(assets, list):
            continue
        for asset in assets:
            if not isinstance(asset, dict) or asset.get('state') != 'uploaded':
                continue
            name = asset.get('name', '')
            size = asset.get('size')
            if not isinstance(name, str) or len(name) > 200 or '/' in name or '\\' in name or not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                continue
            # Delimit the version: 0.4.20 must never match 0.4.2.
            if not name.startswith(prefix) or name[len(prefix):len(prefix)+1] not in ('-', '.'):
                continue
            if platform == 'android':
                compatible = name.lower().endswith('.apk')
            else:
                compatible = name.lower().endswith('.zip') and re.search(r'(?:^|[-_])x64(?:[-_.]|$)', name, re.I)
            url = asset.get('browser_download_url')
            if not compatible or not trusted_release_url(url, download=True):
                continue
            if unquote(urlsplit(url).path) != f'/{REPOSITORY}/releases/download/{tag}/{name}':
                continue
            candidates.append((version, published, name, {
                'version': number, 'release_url': release['html_url'],
                'download_url': url, 'asset_name': name, 'size': size,
                'published_at': published,
            }))
    if not candidates:
        return {'status': 'no_release', 'reason': 'no_compatible_public_release'}
    version, _, _, chosen = max(candidates, key=lambda item: item[:3])
    return {'status': 'available' if version > current else 'up_to_date', **chosen}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_for_update(platform='windows', current_version=VERSION, *, opener=None):
    """Bounded HTTPS request, no authentication, cookies, state or telemetry."""
    request = Request(ENDPOINT, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'RFS-Flightdeck-update-check',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    client = opener if opener is not None else build_opener(_NoRedirect())
    try:
        with client.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.geturl() != ENDPOINT:
                return {'status': 'unavailable', 'reason': 'unexpected_redirect'}
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                return {'status': 'unavailable', 'reason': 'response_too_large'}
        return select_release(json.loads(data), platform, current_version)
    except HTTPError as error:
        return {'status': 'unavailable', 'reason': 'rate_limited' if error.code in (403, 429) else 'http_error'}
    except (URLError, OSError, TimeoutError):
        return {'status': 'unavailable', 'reason': 'network_unavailable'}
    except (ValueError, UnicodeError, TypeError):
        return {'status': 'unavailable', 'reason': 'invalid_response'}


def normalise_preferences(value, current_version=VERSION):
    value = value if isinstance(value, dict) else {}
    attempt = value.get('last_attempt', 0)
    if isinstance(attempt, bool) or not isinstance(attempt, (int, float)) or not 0 <= attempt <= 4102444800 or not math.isfinite(attempt):
        attempt = 0
    result = value.get('last_result', {})
    if not isinstance(result, dict):
        result = {'status': 'unavailable', 'reason': 'invalid_cache'}
    else:
        result = dict(result)
        if result and result.get('status') not in ('available', 'up_to_date', 'no_release', 'unavailable'):
            result = {'status': 'unavailable', 'reason': 'invalid_cache'}
    if result.get('status') in ('available', 'up_to_date'):
        cached = version_tuple(result.get('version'))
        current = version_tuple(current_version)
        if cached is None or current is None:
            result = {'status': 'unavailable', 'reason': 'invalid_cache'}
        else:
            # A cached offer belongs to the version which checked it. After an
            # upgrade, it must never keep offering the already installed build.
            result['status'] = 'available' if cached > current else 'up_to_date'
    return {'enabled': value.get('enabled') is True, 'last_attempt': attempt,
            'last_result': result}


def is_newer_release(result, current_version=VERSION):
    if not isinstance(result, dict) or result.get('status') != 'available':
        return False
    version = version_tuple(result.get('version'))
    current = version_tuple(current_version)
    return version is not None and current is not None and version > current


def should_auto_check(preferences, *, now=None):
    prefs = normalise_preferences(preferences)
    now = time.time() if now is None else float(now)
    if not prefs['enabled'] or not math.isfinite(now):
        return False
    elapsed = now - prefs['last_attempt']
    # A clock moved backwards should not cause repeated requests at startup.
    return prefs['last_attempt'] == 0 or elapsed >= INTERVAL_SECONDS
