"""A fresh publication preserves frozen compatibility inputs without collisions."""

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

import retained_public_assets
from stage_contribution_views import write_landing


class RetainedPublicAssetTests(unittest.TestCase):
    def test_month_landing_keeps_archive_and_no_sitting_distinctions(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            coverage = {'contributions': 2, 'dates': [
                {'date': '2026-11-20', 'publication_status': 'observed',
                 'houses': {'Commons': {'contributions': 2}}},
                {'date': '2026-11-21', 'publication_status': 'observed', 'houses': {}}]}
            write_landing(site, coverage, 'historical-downloads.html')
            result = (site / 'index.html').read_text()
            self.assertIn('href="historical-downloads.html"', result)
            self.assertIn('2 captured contributions', result)
            self.assertIn('21 November 2026 · No sitting', result)

    def test_all_declared_inputs_are_hash_bound_and_idempotent(self):
        manifest = json.loads((retained_public_assets.SOURCE / 'manifest.json').read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            for publication in ['week', 'november']:
                site = Path(directory) / publication
                for _ in range(2):
                    retained_public_assets.stage(site, publication)
                for row in manifest['assets']:
                    if row['publication'] != publication:
                        continue
                    raw = (retained_public_assets.SOURCE / publication / row['path']).read_bytes()
                    self.assertEqual(sha256(raw).hexdigest(), row['sha256'])
                    actual = (site / row['path']).read_bytes()
                    if row['path'].endswith('.html'):
                        self.assertEqual(actual.replace(b'<link rel="icon" href="data:,">', b''), raw)
                    else:
                        self.assertEqual(actual, raw)

    def test_refuses_to_replace_changed_public_material(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            (site / 'historical-downloads.json').write_text('Later reviewed catalogue\n')
            with self.assertRaisesRegex(ValueError, 'Refusing to replace'):
                retained_public_assets.stage(site, 'november')
            self.assertEqual((site / 'historical-downloads.json').read_text(), 'Later reviewed catalogue\n')

    def test_refuses_altered_frozen_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'week').mkdir(parents=True)
            (source / 'week/file.json').write_text('{}')
            (source / 'manifest.json').write_text(json.dumps({
                'schema': 'hansard-retained-public-assets.v1',
                'assets': [{'publication': 'week', 'path': 'file.json', 'bytes': 2, 'sha256': '0' * 64}]}))
            with self.assertRaisesRegex(ValueError, 'frozen input'):
                retained_public_assets.stage(root / 'site', 'week', source=source)
            self.assertFalse((root / 'site').exists())
