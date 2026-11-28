"""Negative controls for the independent full-source conformance audit."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'audit_full_source', Path(__file__).resolve().parents[1] / 'scripts/audit_full_source.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class FullSourceAuditTests(unittest.TestCase):
    def fixture(self, root, *, invalid_type=None, omit_assertion=False):
        context = {'@vocab': 'urn:field:', 'links': 'urn:links'}
        (root / 'receipt.json').write_text(json.dumps({'okf_version': '0.3'}))
        markdown = root / 'markdown'
        markdown.mkdir()
        (markdown / 'index.md').write_text('---\n{"okf_version":"0.3"}\n---\n# Index\n')
        nodes = []
        for name in ('a', 'b'):
            metadata = {'@context': context, '@id': 'urn:' + name,
                        'type': invalid_type if name == 'a' and invalid_type is not None else 'Concept',
                        'core_role': 'concept'}
            body = '# Source ' + name
            (markdown / (name + '.md')).write_text('---\n' + json.dumps(metadata) + '\n---\n' + body)
            node = {key: value for key, value in metadata.items() if key != '@context'}
            node.update(route=name + '.md', body=body)
            if name == 'a':
                node['links'] = {'@id': 'urn:b'}
            nodes.append(node)
        rows = list(nodes)
        if not omit_assertion:
            rows.append({'@id': 'urn:assertion', 'source': {'@id': 'urn:a'},
                         'predicate': {'@id': 'urn:links'}, 'target': {'@id': 'urn:b'}})
        graph = ('"@context": ' + json.dumps(context) + '\nmeta: {}\n"@graph":\n'
                 + ''.join('- ' + json.dumps(row) + '\n' for row in rows))
        (root / 'okf-bundle.yamlld').write_text(graph)

    def test_all_source_documents_and_triples_are_covered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / 'markdown/README.md').write_text('# Ancillary Markdown\n')
            result = AUDIT.audit(root, 'a' * 40)
            self.assertEqual(result['core_concepts'], 2)
            self.assertEqual(result['assertions_checked'], 1)
            self.assertEqual(result['distinct_direct_triples'], 1)
            self.assertEqual(result['non_concept_markdown'], ['README.md'])
            self.assertEqual(len(result['markdown']), 4)

    def test_non_string_or_blank_type_cannot_be_certified_as_a_concept(self):
        for invalid in (['Concept'], {'name': 'Concept'}, True, 1, '   '):
            with self.subTest(value=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root, invalid_type=invalid)
                with self.assertRaises(ValueError):
                    AUDIT.audit(root, 'a' * 40)

    def test_unreified_direct_edge_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root, omit_assertion=True)
            with self.assertRaisesRegex(ValueError, 'coverage differ'):
                AUDIT.audit(root, 'a' * 40)

    def test_malformed_graph_framing_is_rejected(self):
        for old, new in (('"@context": ', 'wrong: '), ('meta: ', 'wrong: '), ('\n- ', '\n')):
            with self.subTest(replacement=new), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root)
                path = root / 'okf-bundle.yamlld'
                path.write_text(path.read_text().replace(old, new, 1))
                with self.assertRaisesRegex(ValueError, 'framing'):
                    AUDIT.audit(root, 'a' * 40)

    def test_log_dates_and_implementation_revision_are_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'Git revision'):
                AUDIT.audit(root, 'short')
            (root / 'markdown/log.md').write_text('# Log\n\n## 2026-02-30\n')
            with self.assertRaises(ValueError):
                AUDIT.audit(root, 'a' * 40)


if __name__ == '__main__':
    unittest.main()
