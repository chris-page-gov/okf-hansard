"""Each public bundle keeps its own source scope and Reader destination."""

import html
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import build_core_projection
import build_walkthrough


class BundleWalkthroughTests(unittest.TestCase):
    def test_compact_month_question_binds_only_its_own_source(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            source = site / 'okf'
            source.mkdir()
            (source / 'index.md').write_text('---\n{"okf_version":"0.3","title":"November fixture"}\n---\n# Index\n')
            fields = {'type': 'Evidence index', 'title': 'Sittings',
                      'description': 'Captured sittings from 2026-11-02 to 2026-11-20.'}
            (source / 'sittings.md').write_text('---\n' + json.dumps(fields) + '\n---\n# Sittings\n')
            build_core_projection.build(source, site)
            core = json.loads((site / 'okf-core.json').read_bytes())
            build_walkthrough.build_core_walkthrough(site, month=True)
            case = json.loads((site / 'core-walkthrough.json').read_bytes())
            self.assertEqual(case['expected_identity']['id'], core['id'])
            self.assertEqual((case['typed_concepts'], case['graph_relationships']), (1, 0))
            self.assertIn('2026-11-02 to 2026-11-20', case['answer'])
            self.assertIn('cannot establish which House', case['answer'])
            self.assertNotIn('has business concerning', case['answer'])
            core['corpora']['hansard']['nodes']['sittings.md']['source_frontmatter']['description'] = 'Changed outside source'
            (site / 'okf-core.json').write_text(json.dumps(core))
            with self.assertRaisesRegex(ValueError, 'source differs'):
                build_walkthrough.build_core_walkthrough(site, month=True)

    def test_full_walkthrough_link_keeps_the_month_and_exact_proceedings_route(self):
        for month in [False, True]:
            with self.subTest(month=month), tempfile.TemporaryDirectory() as directory:
                site = Path(directory)
                (site / 'okf-core.json').write_text('{}')
                (site / 'graph').mkdir()
                (site / 'graph/okf-explorer.json').write_text(json.dumps({
                    'schema': 'okf-explorer-large-corpus.v1', 'id': 'fixture',
                    'version': '0.3.0', 'snapshot': 'fixture-source-sha256'}))
                case = {'id': 'fixture', 'question': 'Question', 'answer': 'Source-bound answer',
                        'scope': 'Declared fixture scope', 'negative_control': 'No unsupported inference',
                        'sources': [], 'coverage': {'through': '2026-11-20'},
                        'graph': {'descriptor': 'graph/okf-explorer.json',
                                  'route': 'timeline-route', 'entry_route': 'dataset/proceedings.md'}}
                with mock.patch.object(build_walkthrough, 'build_core_walkthrough', return_value={}), \
                        mock.patch.object(build_walkthrough, 'month_case', return_value=case), \
                        mock.patch.object(build_walkthrough, 'week_case', return_value=case), \
                        mock.patch.object(build_walkthrough, 'svg', return_value='<svg></svg>'):
                    build_walkthrough.build(site, month=month)
                bound = json.loads((site / 'walkthrough.json').read_bytes())
                self.assertEqual(bound['expected_identity']['snapshot'], 'fixture-source-sha256')
                self.assertEqual(len(bound['descriptor_sha256']), 64)
                links = [urlsplit(html.unescape(value)) for value in re.findall(r'href="([^"]+)"', (site / 'walkthrough.html').read_text())]
                graph, = [value for value in links if parse_qs(value.query).get('view') == ['graph']]
                expected = build_walkthrough.SITE + ('november/' if month else '') + 'graph/okf-explorer.json'
                self.assertEqual(parse_qs(graph.query)['bundle'], [expected])
                self.assertEqual(graph.fragment, 'dataset/proceedings.md')

    def test_compact_source_must_be_published_inside_the_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'
            source.mkdir()
            with self.assertRaisesRegex(ValueError, 'inside the output'):
                build_core_projection.build(source, Path(directory) / 'different-publication')

    def test_walkthrough_links_reject_active_schemes_and_credentials(self):
        for value in ['javascript:alert(1)', '//unrelated.example.test/',
                      'https://secret@hansard.parliament.uk/record']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_walkthrough.link(value, 'Source')


if __name__ == '__main__':
    unittest.main()
