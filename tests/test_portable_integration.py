"""Real desktop/Android storage adapters exchange backups without losing drafts."""
from contextlib import ExitStack
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from backup_bundle import defaults, export_backup, parse_backup


class PortableIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.pc_folder = self.folder / 'pc'
        self.pc_folder.mkdir()
        self.android_folder = self.folder / 'android'
        self.android_folder.mkdir()
        self.storage = importlib.import_module('storage')
        self.stack.enter_context(patch.object(self.storage, 'DATA_DIR', self.pc_folder))
        for key in ('STATE', 'HISTORY', 'PRESETS', 'DESIGNS'):
            self.stack.enter_context(patch.object(
                self.storage, key + '_FILE', self.pc_folder / ('rfs_' + key.lower() + '.json')))
        root = Path(__file__).resolve().parents[1]
        android_python = str(root / 'android' / 'app' / 'src' / 'main' / 'python')
        if android_python not in sys.path:
            sys.path.insert(0, android_python)
            self.stack.callback(sys.path.remove, android_python)
        self.android_module = importlib.import_module('android_engine')
        i18n = importlib.import_module('i18n')
        self.stack.callback(i18n.set_language, i18n.language())
        self.database = root / 'finder-data' / 'aviation.sqlite'
        self.pc = self.storage.Store()
        self.android = self.android_module.Engine(self.android_folder, self.database)

    @staticmethod
    def payload(callsign):
        state = defaults()
        state['language'] = 'en'
        state['flight']['callsign'] = callsign
        state['strict_validation'] = False
        state['preview_edits']['ATC REQUEST'] = 'Edited draft: ' + callsign
        state['pilot_library'] = [{'name': 'Portable pilot', 'message_types': ['ATC REQUEST']}]
        state['saved_flights'] = [{
            'id': 'saved-flight', 'label': 'Saved ' + callsign,
            'flight': deepcopy(state['flight']), 'per_type': deepcopy(state['per_type']),
        }]
        design = {'name': 'Portable design', 'guided': True, 'base_design': 'Carte'}
        state['presentation']['custom_id'] = 'portable-design'
        history = [{
            'message_type': 'ATC REQUEST', 'pilot_name': 'Portable pilot',
            'flight': deepcopy(state['flight']), 'data': {},
            'presentation': deepcopy(state['presentation']), 'message': 'Copied ' + callsign,
        }]
        return {'state': state, 'history': history, 'presets': {},
                'designs': {'portable-design': design}}

    def test_pc_android_pc_android_roundtrip_survives_real_restarts(self):
        original = self.payload('PC-ORIGINAL')
        self.pc.import_backup(export_backup(original, platform='windows'), mode='replace')
        pc_text = self.pc.export_backup()
        self.android.handle('import', {'text': pc_text, 'mode': 'replace'})
        self.assertEqual(original, parse_backup(self.android.handle('export', {})['text'])['payload'])

        edited = deepcopy(self.android.value)
        edited['state']['flight']['callsign'] = 'ANDROID-EDITED'
        edited['state']['message_type'] = 'TAXI'
        edited['state']['per_type']['TAXI']['taxi_route'] = 'A1 A2'
        edited['state']['preview_edits']['TAXI'] = 'Exact mobile preview — keep this text.'
        self.android.commit(self.android.validate_backup(edited))
        restarted_android = self.android_module.Engine(self.android_folder, self.database)
        android_text = restarted_android.handle('export', {})['text']
        expected = parse_backup(android_text)['payload']
        self.pc.import_backup(android_text, mode='replace')
        restarted_pc = self.storage.Store()
        self.assertEqual('ATC REQUEST', restarted_pc.state['message_type'])
        self.assertEqual('TAXI', restarted_pc.state['android_message_type'])
        restored_text = restarted_pc.export_backup()
        self.assertEqual(expected, parse_backup(restored_text)['payload'])

        final_android = self.android_module.Engine(self.folder / 'second-android', self.database)
        final_android.handle('import', {'text': restored_text, 'mode': 'replace'})
        final_restart = self.android_module.Engine(self.folder / 'second-android', self.database)
        self.assertEqual(expected, parse_backup(final_restart.handle('export', {})['text'])['payload'])
        self.assertTrue(list((self.pc_folder / 'backups').glob('*/portable-backup.json')))

    def test_android_merge_is_repeatable_and_keeps_local_live_flight(self):
        local = self.payload('LOCAL-ANDROID')
        incoming = self.payload('PC-INCOMING')
        incoming['state']['message_type'] = 'TAXI'
        incoming['state']['per_type']['TAXI']['taxi_route'] = 'B3 B4'
        incoming['state']['preview_edits']['TAXI'] = 'Do not discard this edited taxi request.'
        incoming['designs']['portable-design']['name'] = 'Conflicting PC design'
        incoming['state']['active_session'] = {
            'flight': deepcopy(incoming['state']['flight']), 'seconds': 15,
            'started_at': '2026-10-04T00:00:00+00:00',
        }
        self.android.handle('import', {'text': export_backup(local), 'mode': 'replace'})
        incoming_text = export_backup(incoming, platform='windows')
        self.android.handle('import', {'text': incoming_text, 'mode': 'merge'})
        first = deepcopy(self.android.value)
        self.android.handle('import', {'text': incoming_text, 'mode': 'merge'})
        self.assertEqual(first, self.android.value)
        self.assertEqual('LOCAL-ANDROID', self.android.state['flight']['callsign'])
        self.assertEqual({}, self.android.state['active_session'])
        imported = [flight for flight in self.android.state['saved_flights']
                    if flight.get('active_session')]
        self.assertEqual(1, len(imported))
        self.assertEqual(incoming['state']['active_session'], imported[0]['active_session'])
        self.assertEqual(2, len(self.android.value['designs']))
        self.assertEqual(2, len(self.android.value['history']))
        restarted = self.android_module.Engine(self.android_folder, self.database)
        self.assertEqual(first, restarted.value)
        restarted.handle('load_flight', {'id': imported[0]['id']})
        self.assertEqual('TAXI', restarted.state['message_type'])
        self.assertEqual(incoming['state']['preview_edits'], restarted.state['preview_edits'])
        self.assertEqual(incoming['state']['pilot_name'], restarted.state['pilot_name'])
        selected_design = restarted.state['presentation']['custom_id']
        self.assertEqual('Conflicting PC design', restarted.value['designs'][selected_design]['name'])
        self.assertEqual({}, restarted.state['active_session'])
        # Export/import through the actual desktop adapter preserves both devices' records.
        self.pc.import_backup(restarted.handle('export', {})['text'], mode='replace')
        self.assertEqual(parse_backup(restarted.handle('export', {})['text'])['payload'],
                         parse_backup(self.storage.Store().export_backup())['payload'])

    def test_boolean_schema_version_is_rejected_before_both_adapters_write(self):
        value = self.payload('EXISTING')
        text = export_backup(value)
        self.pc.import_backup(text, mode='replace')
        self.android.handle('import', {'text': text, 'mode': 'replace'})
        pc_before = {path.name: path.read_bytes() for path in self.pc_folder.glob('rfs_*.json')}
        android_before = self.android.path.read_bytes()
        pc_memory, android_memory = deepcopy(self.pc._backup_payload()), deepcopy(self.android.value)
        backups_before = sorted(str(path.relative_to(self.folder)) for path in self.folder.rglob('before-import-*'))
        envelope = json.loads(text)
        malformed = [{**envelope, 'schema_version': True}, {'schema_version': True, **value}]
        for invalid in malformed:
            with self.assertRaises(ValueError):
                self.pc.import_backup(json.dumps(invalid), mode='replace')
            with self.assertRaises(ValueError):
                self.android.handle('import', {'text': json.dumps(invalid), 'mode': 'replace'})
            self.assertEqual(pc_before, {path.name: path.read_bytes() for path in self.pc_folder.glob('rfs_*.json')})
            self.assertEqual(android_before, self.android.path.read_bytes())
            self.assertEqual(pc_memory, self.pc._backup_payload())
            self.assertEqual(android_memory, self.android.value)
        self.assertEqual(backups_before, sorted(str(path.relative_to(self.folder)) for path in self.folder.rglob('before-import-*')))


if __name__ == '__main__':
    unittest.main()
