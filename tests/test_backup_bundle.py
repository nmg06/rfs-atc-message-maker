"""Portable data validation, both directions and transactional profile recovery."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import storage
from backup_bundle import (FORMAT, STATE_LIMIT, defaults, export_backup, parse_backup,
                           desktop_state, merge_payloads)


def payload():
    return {'state': defaults(), 'history': [], 'presets': {}, 'designs': {}}


class PortableBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        self.patches = [patch.object(storage, 'DATA_DIR', folder)]
        for key in ('STATE', 'HISTORY', 'PRESETS', 'DESIGNS'):
            self.patches.append(patch.object(storage, key + '_FILE', folder / ('rfs_' + key.lower() + '.json')))
        for p in self.patches:
            p.start()
        self.store = storage.Store()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def files(self):
        return {p.name: p.read_bytes() for p in Path(self.temp.name).glob('rfs_*.json')}

    def test_common_envelope_and_all_android_extensions_roundtrip_through_desktop(self):
        for kind in ('ATIS', 'PUSHBACK', 'TAXI'):
            value = payload()
            value['state'].update(message_type=kind, strict_validation=False, tutorial_seen=True)
            value['state']['preview_edits'][kind] = 'Exact edited message ' + kind
            value['state']['map_settings'] = {'zoom': 42, 'winds': False}
            value['state']['flight']['callsign'] = 'KEEP-ME'
            self.store.import_backup(export_backup(value, 'android', '0.4.2'), mode='replace')
            self.assertEqual('ATC REQUEST', self.store.state['message_type'])
            self.assertEqual(kind, self.store.state['android_message_type'])
            restored = parse_backup(self.store.export_backup())['payload']
            self.assertEqual(value, restored)
        envelope = json.loads(self.store.export_backup())
        self.assertEqual(FORMAT, envelope['format'])
        self.assertEqual('windows', envelope['source']['platform'])
        self.assertTrue(envelope['created_at'].endswith('+00:00'))

    def test_malformed_and_oversized_inputs_leave_disk_byte_identical(self):
        self.store.save_state()
        before = self.files()
        original = deepcopy(self.store._backup_payload())
        valid = json.loads(self.store.export_backup())
        bad_version = {**valid, 'schema_version': 99}
        wrong_flag = deepcopy(valid)
        wrong_flag['payload']['state']['strict_validation'] = 'yes'
        wrong_nested = deepcopy(valid)
        wrong_nested['payload']['state']['saved_flights'] = [{'id': 'a', 'label': 'Invalid', 'flight': [], 'per_type': {}}]
        for value in ('{', json.dumps(bad_version), json.dumps(wrong_flag), json.dumps(wrong_nested), 'x' * (STATE_LIMIT + 1)):
            with self.assertRaises(ValueError):
                self.store.import_backup(value)
            self.assertEqual(before, self.files())
            self.assertEqual(original, self.store._backup_payload())
        self.assertFalse((Path(self.temp.name) / 'backups').exists())

    def test_four_file_save_failure_rolls_back_exact_bytes_and_memory(self):
        for key, name in [('state', 'STATE_FILE'), ('history', 'HISTORY_FILE'), ('presets', 'PRESETS_FILE'), ('designs', 'DESIGNS_FILE')]:
            storage.save_json(getattr(storage, name), getattr(self.store, key))
        before, original = self.files(), deepcopy(self.store._backup_payload())
        candidate = payload()
        candidate['state']['flight']['callsign'] = 'REPLACED'
        save = storage.save_json
        calls = []
        def fail_third(path, value):
            calls.append(path)
            if len(calls) == 3:
                raise OSError('Simulated full disk')
            save(path, value)
        with patch.object(storage, 'save_json', side_effect=fail_third):
            with self.assertRaises(OSError):
                self.store.import_backup(export_backup(candidate), mode='replace')
        self.assertEqual(before, self.files())
        self.assertEqual(original, self.store._backup_payload())
        saved = list((Path(self.temp.name) / 'backups').glob('*/portable-backup.json'))
        self.assertEqual(1, len(saved))
        self.assertEqual(original['flight'] if 'flight' in original else original['state']['flight'], parse_backup(saved[0].read_text(encoding='utf-8'))['payload']['state']['flight'])

    def test_failed_import_restores_files_that_were_initially_absent(self):
        self.store.save_state()
        before = self.files()
        original = storage.save_json
        def save(path, value):
            if path == storage.DESIGNS_FILE:
                raise OSError('write failure')
            original(path, value)
        with patch.object(storage, 'save_json', side_effect=save):
            with self.assertRaises(OSError):
                self.store.import_backup(export_backup(payload()), mode='replace')
        self.assertEqual(before, self.files())

    def test_legacy_android_and_four_pc_files_are_accepted(self):
        value = payload()
        value['state']['flight']['callsign'] = 'LEGACY'
        legacy = {'schema_version': 1, **value}
        self.store.import_backup(json.dumps(legacy), mode='replace')
        self.assertEqual('LEGACY', self.store.state['flight']['callsign'])
        files = {'rfs_' + key + '.json': '\ufeff' + json.dumps(v) for key, v in value.items()}
        self.assertEqual(value, parse_backup(files)['payload'])
        with self.assertRaises(ValueError):
            self.store.preview_import({'rfs_state.json': files['rfs_state.json']})

    def test_replace_preserves_device_local_online_consent(self):
        self.store.state['update_preferences'] = {'enabled': False}
        value = payload()
        value['state']['update_preferences'] = {'enabled': True}
        value['state']['map_settings'] = {'satellite': True, 'winds': True, 'zoom': 2}
        self.store.import_backup(export_backup(value), mode='replace')
        self.assertFalse(self.store.state['update_preferences']['enabled'])
        self.assertEqual({'satellite': False, 'winds': False, 'zoom': 2}, self.store.state['map_settings'])

    def test_interrupted_import_is_recovered_before_startup_reads_profile(self):
        self.store.save_state()
        before = self.files()
        original = storage.save_json
        def interrupt(path, value):
            if path == storage.PRESETS_FILE:
                raise KeyboardInterrupt('simulated power interruption')
            original(path, value)
        value = payload()
        value['state']['flight']['callsign'] = 'INCOMPLETE TRANSACTION'
        with patch.object(storage, 'save_json', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.store.import_backup(export_backup(value), mode='replace')
        journal = Path(self.temp.name) / 'import-transaction.json'
        self.assertTrue(journal.exists())
        self.assertNotEqual(before, self.files())
        restored = storage.Store()
        self.assertEqual(before, self.files())
        self.assertEqual('', restored.state['flight']['callsign'])
        self.assertFalse(journal.exists())

    def test_malformed_journal_cannot_restore_external_paths(self):
        self.store.save_state()
        before = self.files()
        journal = Path(self.temp.name) / 'import-transaction.json'
        journal.write_text(json.dumps({'format': 'rfs-flightdeck-import', 'schema_version': 1,
            'status': 'prepared', 'backup': '../../outside', 'files': {}, 'digests': {}}), encoding='utf-8')
        with self.assertRaises(ValueError):
            storage.Store()
        self.assertEqual(before, self.files())
        self.assertTrue(journal.exists())

    def test_failed_recovery_keeps_journal_and_retries_on_next_start(self):
        self.store.save_state()
        before = self.files()
        save = storage.save_json
        def fail(path, value):
            if path == storage.DESIGNS_FILE:
                raise OSError('Failed imported save')
            save(path, value)
        restore = storage._restore_bytes
        def fail_profile_restore(path, value):
            if path == storage.STATE_FILE:
                raise OSError('Failed rollback')
            restore(path, value)
        imported = payload()
        imported['state']['flight']['callsign'] = 'PARTIAL'
        with patch.object(storage, 'save_json', side_effect=fail), patch.object(storage, '_restore_bytes', side_effect=fail_profile_restore):
            with self.assertRaises(OSError):
                self.store.import_backup(export_backup(imported), mode='replace')
        journal = Path(self.temp.name) / 'import-transaction.json'
        self.assertTrue(journal.exists())
        storage.Store()
        self.assertEqual(before, self.files())
        self.assertFalse(journal.exists())

    def test_merge_keeps_local_draft_and_conflicts_then_is_repeatable(self):
        local, incoming = payload(), payload()
        for value, call in ((local, 'LOCAL'), (incoming, 'IMPORTED')):
            value['state']['flight']['callsign'] = call
            value['state']['preview_edits']['ATC REQUEST'] = call + ' manually edited'
            value['state']['saved_flights'] = [{'id': 'collision', 'label': 'Route', 'flight': deepcopy(value['state']['flight']), 'per_type': {}}]
            value['designs']['collision'] = {'name': call, 'guided': True, 'base_design': 'Carte'}
            value['state']['presentation']['custom_id'] = 'collision'
            value['presets']['Same name'] = {'message_type': 'ATC REQUEST', 'pilot_name': '', 'flight': deepcopy(value['state']['flight']), 'data': {}, 'presentation': deepcopy(value['state']['presentation'])}
        merged = merge_payloads(local, incoming)
        self.assertEqual('LOCAL', merged['state']['flight']['callsign'])
        self.assertEqual('LOCAL manually edited', merged['state']['preview_edits']['ATC REQUEST'])
        self.assertEqual(3, len(merged['state']['saved_flights']))
        self.assertEqual(2, len(merged['presets']))
        self.assertEqual(2, len(merged['designs']))
        imported = merged['state']['saved_flights'][-1]
        self.assertNotEqual('collision', imported['presentation']['custom_id'])
        self.assertEqual('IMPORTED', merged['designs'][imported['presentation']['custom_id']]['name'])
        self.assertEqual(merged, merge_payloads(merged, incoming))

    def test_merge_preserves_presentation_only_draft_and_never_moves_foreign_timer(self):
        local, incoming = payload(), payload()
        local['state']['flight']['callsign'] = incoming['state']['flight']['callsign'] = 'SAME'
        incoming['state'].update(pilot_name='Different pilot', message_type='AIRBORNE')
        incoming['state']['presentation']['design'] = 'Carnet'
        incoming['state']['active_session'] = {'flight': deepcopy(incoming['state']['flight']), 'seconds': 20, 'started_at': '2026-10-04T00:00:00+00:00'}
        merged = merge_payloads(local, incoming)
        self.assertEqual({}, merged['state']['active_session'])
        draft = merged['state']['saved_flights'][-1]
        self.assertEqual('AIRBORNE', draft['message_type'])
        self.assertEqual('Different pilot', draft['pilot_name'])
        self.assertEqual('Carnet', draft['presentation']['design'])
        self.assertEqual(incoming['state']['active_session'], draft['active_session'])


if __name__ == '__main__':
    unittest.main()
