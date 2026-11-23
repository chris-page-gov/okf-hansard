"""Independently audit every Markdown document and direct graph assertion."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON/frontmatter key')
        result[key] = value
    return result


def audit(release, producer_commit):
    release_receipt = (release / 'receipt.json').read_bytes()
    build_receipt = json.loads(release_receipt, object_pairs_hook=unique)
    if build_receipt.get('okf_version') != '0.3':
        raise ValueError('release receipt does not declare OKF core 0.3')
    graph_file = release / 'okf-bundle.yamlld'
    if graph_file.stat().st_size > 1024 * 1024 * 1024:
        raise ValueError('graph exceeds the audit budget')
    nodes, assertions = {}, []
    with graph_file.open() as stream:
        context = json.loads(stream.readline().split(': ', 1)[1], object_pairs_hook=unique)
        stream.readline()
        if stream.readline().strip() != '"@graph":':
            raise ValueError('unsupported graph framing')
        for line in stream:
            if len(line.encode()) > 2 * 1024 * 1024:
                raise ValueError('graph row exceeds the audit budget')
            row = json.loads(line.removeprefix('- '), object_pairs_hook=unique)
            if '@context' in row:
                raise ValueError('unexpected row-local graph context')
            if 'predicate' in row:
                assertions.append(row)
            else:
                if row['@id'] in nodes:
                    raise ValueError('duplicate semantic node identity')
                nodes[row['@id']] = row
    def expand(key):
        if key in context:
            value = context[key]
            value = value.get('@id', key) if isinstance(value, dict) else value
            if value != key:
                return expand(value)
        if ':' in key:
            prefix, suffix = key.split(':', 1)
            base = context.get(prefix)
            if isinstance(base, str):
                return base + suffix
            return key
        return context.get('@vocab', '') + key
    direct = set()
    for identifier, node in nodes.items():
        for key, value in node.items():
            if key.startswith('@'):
                continue
            for target in value if isinstance(value, list) else [value]:
                if isinstance(target, dict) and '@id' in target:
                    direct.add((identifier, expand(key), target['@id']))
    assertion_ids = set()
    for row in assertions:
        if row['@id'] in assertion_ids:
            raise ValueError('duplicate assertion identity')
        assertion_ids.add(row['@id'])
        triple = row['source']['@id'], row['predicate']['@id'], row['target']['@id']
        if triple not in direct or triple[0] not in nodes or triple[2] not in nodes:
            raise ValueError('missing direct triple or semantic endpoint')
    markdown = release / 'markdown'
    source, concept_ids, navigation = {}, set(), []
    derived_fields = 0
    count = 0
    for directory, subdirectories, names in markdown.walk():
        for name in [*subdirectories, *names]:
            path = directory / name
            count += 1
            if count > 100_000 or path.is_symlink():
                raise ValueError('source inventory boundary refused')
        for name in names:
            if not name.endswith('.md'):
                continue
            path = directory / name
            # The complete contribution listing is 3.2 MB. It is navigation,
            # not a concept; inspect it fully with an explicit larger budget.
            maximum = 8 * 1024 * 1024 if name in {'index.md', 'log.md'} else 2 * 1024 * 1024
            if path.stat().st_size > maximum:
                raise ValueError('Markdown exceeds the audit budget')
            raw = path.read_bytes()
            if len(raw) > maximum:
                raise ValueError('Markdown exceeds the audit budget')
            route = path.relative_to(markdown).as_posix()
            source[route] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}
            text = raw.decode('utf-8')
            metadata, body = None, text
            if text.startswith('---\n'):
                header, delimiter, body = text[4:].partition('\n---\n')
                if not delimiter:
                    raise ValueError('unclosed frontmatter')
                metadata = json.loads(header, object_pairs_hook=unique)
                if not isinstance(metadata, dict):
                    raise ValueError('frontmatter must be a mapping')
            if name in {'index.md', 'log.md'}:
                navigation.append(route)
                if route == 'index.md':
                    if metadata.get('okf_version') != '0.3':
                        raise ValueError('wrong source core declaration')
                elif metadata is not None:
                    raise ValueError('frontmatter in reserved navigation')
                continue
            if not metadata or not metadata.get('type'):
                continue
            identifier = metadata['@id']
            node = nodes[identifier]
            if node['route'] != route or identifier in concept_ids:
                raise ValueError('core path or identity differs from graph')
            for key, value in metadata.items():
                if key != '@context' and node.get(key) != value:
                    # The reviewed writer adds these exact convenience aliases
                    # from the semantic node's official URL; no other mismatch
                    # is accepted. Keep the conversion visible in the receipt.
                    expected_alias = node.get('url') if key == 'resource' else (
                        [{'id':'record','resource':node['url']}]
                        if key == 'sources' and node.get('url') else None)
                    if key in {'resource','sources'} and value == expected_alias and key not in node:
                        derived_fields += 1
                    else:
                        raise ValueError(f'frontmatter differs from semantic node: {route} field {key}')
            if metadata.get('@context') != context:
                raise ValueError('source context differs from graph context')
            if body.strip() != node.get('body', '').strip():
                raise ValueError('display body differs from source')
            concept_ids.add(identifier)
    extension_ids = set(nodes) - concept_ids
    if (any(nodes[identifier].get('core_role') != 'extension' for identifier in extension_ids)
            or any(nodes[identifier].get('route') in source for identifier in extension_ids)):
        raise ValueError('non-Markdown semantic records are not explicitly source-backed extensions')
    return {'schema':'hansard-core-full-graph-audit.v1', 'status':'passed',
            'observed_at':datetime.now(timezone.utc).isoformat(),
            'producer_commit':producer_commit,
            'source_capture':{'capture_id':build_receipt.get('capture'),
                              'capture_finished_at':build_receipt.get('capture_finished_at'),
                              'manifest_sha256':build_receipt.get('manifest_sha256')},
            'release_receipt_sha256':sha256(release_receipt).hexdigest(),
            'scope':'Retained generated release, strict JSON subset of YAML 1.2; all concept metadata, display bodies, semantic identities and direct/assertion agreement. No public retrieval or browser claim.',
            'core_concepts':len(concept_ids), 'extension_records_without_markdown':len(extension_ids),
            'assertions_checked':len(assertions),
            'distinct_direct_triples':len(direct), 'reserved_navigation':navigation,
            'exact_url_derived_resource_and_source_aliases_checked':derived_fields,
            'body_comparison':'Display body after boundary whitespace trimming; exact source bytes are separately hashed.',
            'graph_sha256':sha256(graph_file.read_bytes()).hexdigest(),
            'checker_sha256':sha256(Path(__file__).read_bytes()).hexdigest(), 'markdown':source}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release', type=Path)
    parser.add_argument('--producer-commit', required=True,
                        help='Full implementation commit, separate from the source capture identity')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.release, args.producer_commit)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    args.output.chmod(0o600)
    print({k:result[k] for k in ['status','core_concepts','assertions_checked','distinct_direct_triples']})
