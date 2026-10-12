"""Only intentional public assets can reach Pages; builds cannot touch user data."""
from pathlib import Path
import tempfile
import unittest
from scripts.prepare_site import ROOT, PUBLIC_FILES, prepare


class SiteExportTests(unittest.TestCase):
    def setUp(self):
        folder = ROOT / 'build'
        folder.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder, prefix='site-test-')
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'public'

    def test_only_declared_public_files_are_exported(self):
        prepare(self.output)
        actual = {str(p.relative_to(self.output)).replace('\\', '/')
                  for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(set(PUBLIC_FILES) | {'.nojekyll'}, actual)
        for name in PUBLIC_FILES:
            self.assertEqual((ROOT/name).read_bytes(), (self.output/name).read_bytes())
        self.assertFalse((self.output/'data').exists())
        self.assertFalse((self.output/'android').exists())

    def test_existing_output_is_never_replaced_or_published(self):
        self.output.mkdir()
        marker = self.output / 'private.txt'
        marker.write_text('must remain private', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            prepare(self.output)
        self.assertEqual('must remain private', marker.read_text(encoding='utf-8'))

    def test_output_cannot_escape_build_directory(self):
        with self.assertRaises(ValueError):
            prepare(ROOT/'data/site')

    def test_home_preserves_access_to_legacy_drafts(self):
        self.assertIn('mobile/index.html', (ROOT/'index.html').read_text(encoding='utf-8'))
        self.assertIn('rfs_mobile_state_v1', (ROOT/'assets/site.js').read_text(encoding='utf-8'))
        self.assertIn('rfs_mobile_state_v1', (ROOT/'mobile/index.html').read_text(encoding='utf-8'))
