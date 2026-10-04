"""Stable release eligibility, trusted links, offline failure and consent."""
from copy import deepcopy
from io import BytesIO
import json
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

import updates


def release(version='0.4.3', platform='Android', suffix='debug.apk'):
    tag = 'v' + version + '-flightdeck'
    name = f'RFSFlightdeck-{platform}-{version}-{suffix}'
    return {'tag_name': tag, 'draft': False, 'prerelease': False,
            'published_at': '2026-10-01T12:00:00Z',
            'html_url': f'{updates.RELEASES_URL}/tag/{tag}',
            'assets': [{'name': name, 'state': 'uploaded', 'size': 1024,
                        'browser_download_url': f'{updates.RELEASES_URL}/download/{tag}/{name}'}]}


class UpdateTests(unittest.TestCase):
    def select(self, values, platform='android', current='0.4.2'):
        return updates.select_release(values, platform, current, now=1800000000)

    def test_stable_version_and_numeric_newest_not_github_order(self):
        self.assertEqual((0, 4, 2), updates.version_tuple('v0.4.2-flightdeck'))
        for bad in ['0.4.2-debug', 'v0.4.2-rc1', '0.04.2', '0.4', '9.0.0-beta', None]:
            self.assertIsNone(updates.version_tuple(bad))
        result = self.select([release('0.4.9'), release('0.4.10'), release('0.4.3')])
        self.assertEqual('available', result['status'])
        self.assertEqual('0.4.10', result['version'])
        self.assertTrue(result['download_url'].endswith(result['asset_name']))

    def test_no_release_is_distinct_from_up_to_date_or_downgrade(self):
        self.assertEqual('no_release', self.select([])['status'])
        self.assertEqual('up_to_date', self.select([release('0.4.1')])['status'])
        self.assertEqual('up_to_date', self.select([release('0.4.2')])['status'])
        legacy = release('9.0.0')
        legacy['assets'][0]['name'] = 'RFSATCMessageMaker.zip'
        self.assertEqual('no_release', self.select([legacy])['status'])

    def test_future_draft_prerelease_and_unpublished_assets_ignored(self):
        changes = ({'draft': True}, {'prerelease': True}, {'published_at': None},
                   {'published_at': '2999-01-01T00:00:00Z'}, {'published_at': 'bad'},
                   {'tag_name': '0.4.3-preview'}, {'published_at': '2026-10-01T12:00:00'})
        for change in changes:
            with self.subTest(change=change):
                value = release(); value.update(change)
                self.assertEqual('no_release', self.select([value])['status'])
        value = release(); value['assets'][0]['state'] = 'new'
        self.assertEqual('no_release', self.select([value])['status'])

    def test_only_compatible_versioned_asset_and_platform(self):
        windows = release(platform='Windows', suffix='x64.zip')
        self.assertEqual('available', self.select([windows], 'windows')['status'])
        self.assertEqual('no_release', self.select([windows])['status'])
        for suffix in ('arm64.zip', 'x64.exe', 'x86.zip'):
            self.assertEqual('no_release', self.select([release(platform='Windows', suffix=suffix)], 'windows')['status'])
        incorrect = release('0.4.2'); incorrect['assets'] = release('0.4.20')['assets']
        self.assertEqual('no_release', self.select([incorrect])['status'])

    def test_trusted_exact_repository_tag_and_asset_paths(self):
        unsafe = ['http://github.com/', 'https://evil.test/asset.apk',
                  'https://github.com.evil.test/nmg06/rfs-atc-message-maker/releases/download/v1/a.apk',
                  'https://github.com/other/repo/releases/download/v1/a.apk',
                  f'{updates.RELEASES_URL}/download/v1/../a.apk',
                  f'{updates.RELEASES_URL}/download/v1/%2e%2e/a.apk',
                  f'{updates.RELEASES_URL}/download/v1/a.apk?token=secret']
        for url in unsafe:
            self.assertFalse(updates.trusted_release_url(url, download=True), url)
        value = release(); value['assets'][0]['browser_download_url'] = updates.RELEASES_URL + '/download/v0.4.3-flightdeck/another.apk'
        self.assertEqual('no_release', self.select([value])['status'])
        value = release(); value['html_url'] = updates.RELEASES_URL + '/tag/v99.0.0'
        self.assertEqual('no_release', self.select([value])['status'])

    def test_network_is_bounded_fixed_and_does_not_send_local_data(self):
        stream = BytesIO(json.dumps([release()]).encode())
        stream.geturl = lambda: updates.ENDPOINT
        client = Mock(); client.open.return_value = stream
        self.assertEqual('available', updates.check_for_update('android', opener=client)['status'])
        request = client.open.call_args.args[0]
        self.assertEqual(updates.ENDPOINT, request.full_url)
        self.assertIsNone(request.data)
        self.assertNotIn('Authorization', request.headers)
        self.assertEqual(updates.TIMEOUT_SECONDS, client.open.call_args.kwargs['timeout'])
        big = BytesIO(b' ' * (updates.MAX_BYTES + 1)); big.geturl = lambda: updates.ENDPOINT
        client.open.return_value = big
        self.assertEqual('response_too_large', updates.check_for_update(opener=client)['reason'])

    def test_offline_bad_json_rate_limit_and_redirect_never_claim_current(self):
        client = Mock()
        for failure in (URLError('offline'), TimeoutError(), HTTPError(updates.ENDPOINT, 429, 'limit', {}, None)):
            client.open.side_effect = failure
            self.assertEqual('unavailable', updates.check_for_update(opener=client)['status'])
        client.open.side_effect = None
        for data, url in [(b'bad JSON', updates.ENDPOINT), (b'[]', 'https://evil.test')]:
            stream = BytesIO(data); stream.geturl = lambda: url
            client.open.return_value = stream
            self.assertEqual('unavailable', updates.check_for_update(opener=client)['status'])

    def test_automatic_checks_are_opt_in_daily_and_clock_safe(self):
        self.assertFalse(updates.should_auto_check({}, now=100000))
        self.assertFalse(updates.should_auto_check({'enabled': 'yes'}, now=100000))
        self.assertTrue(updates.should_auto_check({'enabled': True}, now=100000))
        preferences = {'enabled': True, 'last_attempt': 100000}
        self.assertFalse(updates.should_auto_check(preferences, now=99999))
        self.assertFalse(updates.should_auto_check(preferences, now=186399))
        self.assertTrue(updates.should_auto_check(preferences, now=186400))
        for bad in (float('nan'), float('inf'), 10**100, True, 'yesterday'):
            self.assertEqual(0, updates.normalise_preferences({'last_attempt': bad})['last_attempt'])

    def test_cached_offer_rechecked_after_upgrade_never_offers_same_build(self):
        for version in ('0.4.1', updates.VERSION):
            result = {'status': 'available', 'version': version,
                      'download_url': f'{updates.RELEASES_URL}/download/v{version}/old.apk'}
            preferences = updates.normalise_preferences({'last_result': result})
            self.assertEqual('up_to_date', preferences['last_result']['status'])
            self.assertFalse(updates.is_newer_release(result))
            self.assertFalse(updates.is_newer_release(preferences['last_result']))
            self.assertEqual('available', result['status'])  # input not mutated
        result = {'status': 'available', 'version': '0.4.3'}
        self.assertEqual('available', updates.normalise_preferences({'last_result': result})['last_result']['status'])
        self.assertTrue(updates.is_newer_release(result))
        for result in ({'status': 'no_release', 'reason': 'no_compatible_public_release'},
                       {'status': 'unavailable', 'reason': 'network_unavailable'}):
            self.assertEqual(result, updates.normalise_preferences({'last_result': result})['last_result'])
        self.assertEqual('unavailable', updates.normalise_preferences({'last_result': {'status': 'available'}})['last_result']['status'])


if __name__ == '__main__':
    unittest.main()
