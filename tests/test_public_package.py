"""Reject personal profiles anywhere in an archive; fresh installs are blank."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from scripts.public_package import verify_archive,verify_directory
import storage
from backup_bundle import defaults
class PublicPackageTests(unittest.TestCase):
 def test_private_files_rejected_even_nested(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp); archive=root/'test.zip'
   for name in ('RFSFlightdeck/data/rfs_state.json','_internal/app.log','private/debug.keystore','nested/.env'):
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,'TEST ONLY')
    with self.assertRaises(ValueError):verify_archive(archive)
   with zipfile.ZipFile(archive,'w') as z:z.writestr('RFSFlightdeck/finder-data/aviation.sqlite','fixture')
   self.assertTrue(verify_archive(archive))
 def test_directory_guard(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'data').mkdir()
   with self.assertRaises(ValueError):verify_directory(root)
 def test_blank_fresh_profile_and_preserve_existing_user(self):
  self.assertEqual('',defaults()['pilot_name'])
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   with patch.multiple(storage,STATE_FILE=root/'state.json',HISTORY_FILE=root/'history.json',PRESETS_FILE=root/'presets.json',DESIGNS_FILE=root/'designs.json'),patch.object(storage,'recover_import'):
    store=storage.Store();self.assertEqual('',store.state['pilot_name']);self.assertFalse(store.state['intro_seen']);self.assertEqual([],store.history)
    storage.save_json(root/'state.json',{'pilot_name':'EXISTING TEST PILOT','intro_seen':True})
    restored=storage.Store();self.assertEqual('EXISTING TEST PILOT',restored.state['pilot_name']);self.assertTrue(restored.state['intro_seen'])
