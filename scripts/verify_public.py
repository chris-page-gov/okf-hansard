"""Verify every declared Hansard Pages asset against a frozen local catalogue."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

PUBLIC = 'https://chris-page-gov.github.io/okf-hansard/'
EMPTY_SHA256 = sha256(b'').hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate checksum catalogue key')
        result[key] = value
    return result


def catalogue(site):
    raw = (site / 'checksums.json').read_bytes()
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError('checksum catalogue exceeds its budget')
    rows = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(rows, dict) or not 1 <= len(rows) <= 100_000:
        raise ValueError('invalid checksum catalogue')
    if 'checksums.json' in rows:
        raise ValueError('checksum catalogue must not contain a self-reference')
    for name, row in rows.items():
        path = Path(name)
        if (not name or path.is_absolute() or path.as_posix() != name
                or '..' in path.parts or '\\' in name or '?' in name or '#' in name
                or not isinstance(row, dict) or set(row) != {'bytes', 'sha256'}
                or type(row['bytes']) is not int or not 0 <= row['bytes'] < 100 * 1024 * 1024
                or not re.fullmatch(r'[0-9a-f]{64}', str(row['sha256']))):
            raise ValueError('invalid checksum asset path or identity')
    rows['checksums.json'] = {'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}
    if sum(row['bytes'] for row in rows.values()) >= 1_000_000_000:
        raise ValueError('site exceeds the Pages size limit')
    files = list(site.rglob('*'))
    if any(path.is_symlink() for path in files):
        raise ValueError('site contains a symlink')
    actual = {path.relative_to(site).as_posix() for path in files if path.is_file()}
    if actual != set(rows):
        raise ValueError('site and checksum catalogue coverage differ')
    for name, row in rows.items():
        data = (site / name).read_bytes()
        if len(data) != row['bytes'] or sha256(data).hexdigest() != row['sha256']:
            raise ValueError('local asset differs from its catalogue: ' + name)
    return raw, rows


def public_base(value):
    if value not in {PUBLIC, PUBLIC + 'november/'}:
        raise ValueError('public base must be the owned week or November Pages directory')
    return value


def retrieve(base, name, expected):
    url = base + quote(name, safe='/')
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'Accept-Encoding': 'identity'}), timeout=30) as response:
                if response.status != 200:
                    raise ValueError('public asset did not return HTTP 200: ' + name)
                final = urlsplit(response.url)
                if (final.scheme != 'https' or final.hostname != 'chris-page-gov.github.io'
                        or final.username or final.password or final.query or final.fragment
                        or not response.url.startswith(base)):
                    raise ValueError('public asset redirected outside its declared boundary')
                digest, count = sha256(), 0
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > expected['bytes']:
                        raise ValueError('public asset exceeds its declared size: ' + name)
                    digest.update(chunk)
                if count != expected['bytes'] or digest.hexdigest() != expected['sha256']:
                    raise ValueError('public asset digest differs: ' + name)
                return {'path': name, 'status': response.status, 'bytes': count,
                        'sha256': digest.hexdigest(), 'served': True}
        except HTTPError as error:
            if (name == '.nojekyll' and error.code == 404 and expected['bytes'] == 0
                    and expected['sha256'] == EMPTY_SHA256):
                return {'path': name, 'status': 404, 'served': False,
                        'scope': 'Empty Pages deployment control; exact bytes verified locally and in the release archive.'}
            if error.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def verify(site, base, producer_commit):
    base = public_base(base)
    if not re.fullmatch(r'[0-9a-f]{40}', producer_commit):
        raise ValueError('producer commit must be a full Git revision')
    raw, rows = catalogue(site)
    # Check before and after the complete retrieval to detect a concurrent
    # publication or incomplete promotion, rather than mixing two snapshots.
    first = retrieve(base, 'checksums.json', rows['checksums.json'])
    with ThreadPoolExecutor(max_workers=6) as workers:
        checked = list(workers.map(lambda pair: retrieve(base, *pair), sorted(rows.items())))
    last = retrieve(base, 'checksums.json', rows['checksums.json'])
    if first != last:
        raise ValueError('public catalogue changed during retrieval')
    return {'schema': 'hansard-public-asset-verification.v1', 'status': 'passed',
            'observed_at': datetime.now(timezone.utc).isoformat(), 'base_url': base,
            'producer_commit': producer_commit, 'checksum_manifest_sha256': sha256(raw).hexdigest(),
            'catalogue_files_verified': len(rows),
            'served_files_verified': sum(row['served'] for row in checked),
            'non_served_deployment_controls': [row for row in checked if not row['served']],
            'all_local_bytes_verified': True, 'all_served_bytes_verified': True,
            'catalogue_unchanged_after_retrieval': True,
            'checker_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Complete local and public checksum-bound file coverage. Browser journeys, graph meaning, capture coverage and release publication have separate evidence.',
            'files': checked}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--base-url', type=public_base, required=True)
    parser.add_argument('--producer-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.site.resolve()):
        parser.error('write the verification receipt outside the published site')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                       cwd=Path(__file__).resolve().parents[1], text=True).strip()
    if revision != args.producer_commit:
        parser.error('producer commit must match the checked-out implementation revision')
    if subprocess.check_output(['git', 'status', '--porcelain'],
                               cwd=Path(__file__).resolve().parents[1], text=True).strip():
        parser.error('public verification requires a clean implementation checkout')
    result = verify(args.site, args.base_url, args.producer_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    args.output.chmod(0o600)
    print({key: result[key] for key in ['status', 'catalogue_files_verified', 'served_files_verified']})
