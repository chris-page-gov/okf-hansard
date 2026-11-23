"""Independent compact-core reconciliation refuses missing or altered evidence."""

import base64
import json
from pathlib import Path
import tempfile
import unittest

import build_core_projection
import check_core_projection


class CoreParityTests(unittest.TestCase):
    def fixture(self, root):
        site = root / 'site'
        source = site / 'okf'
        source.mkdir(parents=True)
        fields = {'type': 'Evidence', 'title': 'Record'}
        (source / 'index.md').write_text('---\n{"okf_version":"0.3","license":"LICENSE.md"}\n---\n# Index\n')
        (source / 'record.md').write_text('---\n' + json.dumps(fields) + '\n---\n# Record\n\nEvidence with spaces.  \n')
        (source / 'LICENSE.md').write_text('Licence fixture\n')
        (source / 'extension.md').write_text('---\n{"type":"   "}\n---\n# Supporting material\n')
        build_core_projection.build(source, site)
        projection = root / 'independent.json'
        projection.write_text(json.dumps({'nodes': {'record.md': {
            'frontmatter': fields, 'body': '# Record\n\nEvidence with spaces.  \n'}}, 'edges': []}))
        return site, projection

    def test_complete_scope_includes_untyped_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            site, projection = self.fixture(Path(directory))
            result = check_core_projection.check(projection, site)
            self.assertEqual((result['typed_concepts'], result['all_source_documents_checked']), (1, 4))
            self.assertEqual(result['core_reference_pairs'], 0)

    def test_rejects_lost_concept_metadata_body_graph_and_licence(self):
        for change in ['concept', 'frontmatter', 'body', 'edge', 'licence']:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                site, projection = self.fixture(Path(directory))
                descriptor = json.loads((site / 'okf-core.json').read_bytes())
                corpus = descriptor['corpora']['hansard']
                if change == 'concept':
                    del corpus['nodes']['record.md']
                elif change == 'frontmatter':
                    corpus['nodes']['record.md']['source_frontmatter']['title'] = 'Altered'
                elif change == 'body':
                    corpus['nodes']['record.md']['body'] = 'Altered'
                elif change == 'edge':
                    corpus['relationships'].append({'source': 'record.md', 'target': 'record.md'})
                else:
                    descriptor['meta']['assets']['LICENSE.md'] = base64.b64encode(b'Altered').decode()
                (site / 'okf-core.json').write_text(json.dumps(descriptor))
                with self.assertRaises(ValueError):
                    check_core_projection.check(projection, site)

    def test_rejects_changed_physical_source(self):
        with tempfile.TemporaryDirectory() as directory:
            site, projection = self.fixture(Path(directory))
            (site / 'okf/extension.md').write_text('Changed supporting material\n')
            with self.assertRaisesRegex(ValueError, 'source-byte binding'):
                check_core_projection.check(projection, site)


if __name__ == '__main__':
    unittest.main()
