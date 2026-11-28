"""Reconcile a compact Hansard projection with an independent core import."""

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path


def check(projection, site):
    if projection.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('independent core projection exceeds its budget')
    imported = json.loads(projection.read_bytes())
    raw = (site / 'okf-core.json').read_bytes()
    published = json.loads(raw)
    corpus = published['corpora']['hansard']
    concepts = {key: row for key, row in corpus['nodes'].items() if row['core_role'] == 'concept'}
    if set(concepts) != set(imported['nodes']):
        raise ValueError('compact concept coverage differs from the independent import')
    for route, node in concepts.items():
        other = imported['nodes'][route]
        if (node['source_frontmatter'] != other['frontmatter']
                or node['body'].strip('\r\n') != other['body'].strip('\r\n')):
            raise ValueError('compact frontmatter or display body differs: ' + route)
    for node in corpus['nodes'].values():
        path = site / node['source_path']
        if not path.resolve().is_relative_to(site.resolve()) or path.is_symlink():
            raise ValueError('compact source path escapes the publication')
        data = path.read_bytes()
        if (len(data) != node['source_bytes'] or sha256(data).hexdigest() != node['source_sha256']
                or data.decode() != node['source_markdown']):
            raise ValueError('compact source-byte binding differs')
    expected = {(row['source'], row['target']) for row in imported['edges']}
    actual = {(row['source'], row['target']) for row in corpus['relationships']}
    if expected != actual:
        raise ValueError('compact core reference graph differs from the independent import')
    licence = published['meta'].get('license_asset')
    if licence:
        original = (site / published['source_root'] / licence).read_bytes()
        if base64.b64decode(published['meta']['assets'][licence], validate=True) != original:
            raise ValueError('embedded licence differs from its source')
    return {'schema': 'hansard-independent-core-parity.v1', 'status': 'passed',
            'typed_concepts': len(concepts), 'all_source_documents_checked': len(corpus['nodes']),
            'core_reference_pairs': len(actual), 'full_frontmatter_and_source_bytes': True,
            'display_body_comparison': 'Boundary line breaks only; spaces are preserved.',
            'independent_projection_sha256': sha256(projection.read_bytes()).hexdigest(),
            'descriptor_sha256': sha256(raw).hexdigest(),
            'checker_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', type=Path, required=True)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.site.resolve()):
        parser.error('write the parity receipt outside the publication')
    result = check(args.projection, args.site)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    args.output.chmod(0o600)
    print(result)
