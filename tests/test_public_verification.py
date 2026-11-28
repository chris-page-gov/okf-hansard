"""Boundary tests for complete frozen-catalogue public asset verification."""

from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.error import HTTPError

import verify_public


class PublicAssetVerificationTests(unittest.TestCase):
    def fixture(self, root):
        files = {'index.html': b'<h1>Frozen source</h1>', '.nojekyll': b'',
                 'graph/okf-explorer.json': b'{}'}
        rows = {}
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            rows[name] = {'bytes': len(data), 'sha256': sha256(data).hexdigest()}
        (root / 'checksums.json').write_text(json.dumps(rows))
        return rows

    def test_complete_local_roster_and_every_byte_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            raw, rows = verify_public.catalogue(root)
            self.assertEqual(set(rows), {'index.html', '.nojekyll', 'graph/okf-explorer.json', 'checksums.json'})
            self.assertEqual(rows['checksums.json']['sha256'], sha256(raw).hexdigest())
            (root / 'index.html').write_text('Changed')
            with self.assertRaisesRegex(ValueError, 'local asset differs'):
                verify_public.catalogue(root)

    def test_unlisted_local_file_and_path_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.fixture(root)
            (root / 'extra.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'coverage differ'):
                verify_public.catalogue(root)
            rows['../escape'] = rows['.nojekyll']
            (root / 'checksums.json').write_text(json.dumps(rows))
            with self.assertRaisesRegex(ValueError, 'invalid checksum asset'):
                verify_public.catalogue(root)

    def test_duplicate_catalogue_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / 'checksums.json').write_text('{"same":{},"same":{}}')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                verify_public.catalogue(root)

    def test_only_the_exact_empty_pages_marker_may_be_non_served(self):
        expected = {'bytes': 0, 'sha256': verify_public.EMPTY_SHA256}
        error = HTTPError(verify_public.PUBLIC + '.nojekyll', 404, 'Not served', {}, None)
        with mock.patch.object(verify_public, 'urlopen', side_effect=error):
            result = verify_public.retrieve(verify_public.PUBLIC, '.nojekyll', expected)
            self.assertFalse(result['served'])
            for name, row in [('index.html', expected), ('.nojekyll', {**expected, 'bytes': 1})]:
                with self.subTest(name=name, row=row), self.assertRaises(HTTPError):
                    verify_public.retrieve(verify_public.PUBLIC, name, row)

    def test_redirect_boundary_is_checked_before_reading(self):
        response = mock.MagicMock(status=200, url='http://chris-page-gov.github.io/okf-hansard/index.html')
        with mock.patch.object(verify_public, 'urlopen') as opened:
            opened.return_value.__enter__.return_value = response
            with self.assertRaisesRegex(ValueError, 'redirected outside'):
                verify_public.retrieve(verify_public.PUBLIC, 'index.html', {'bytes': 0, 'sha256': verify_public.EMPTY_SHA256})
        response.read.assert_not_called()

    def test_only_owned_week_and_november_public_bases_are_admitted(self):
        for value in ['http://chris-page-gov.github.io/okf-hansard/',
                      'https://unrelated.example.test/', verify_public.PUBLIC + '../other/']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                verify_public.public_base(value)
        self.assertEqual(verify_public.PUBLIC + 'november/', verify_public.public_base(verify_public.PUBLIC + 'november/'))


if __name__ == '__main__':
    unittest.main()
