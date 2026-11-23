"""Retain checksummed compatibility URLs from the earlier public site."""

from hashlib import sha256
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'compatibility/public-assets'


def stage(site, publication, *, source=SOURCE):
    manifest = json.loads((source / 'manifest.json').read_bytes())
    if manifest['schema'] != 'hansard-retained-public-assets.v1':
        raise ValueError('Unsupported retained-asset manifest')
    rows = []
    for row in manifest['assets']:
        if row['publication'] != publication:
            continue
        name = Path(row['path'])
        if name.is_absolute() or '..' in name.parts:
            raise ValueError('Retained asset escapes its declared publication')
        original = source / publication / name
        raw = original.read_bytes()
        if (original.is_symlink() or not original.resolve().is_relative_to((source / publication).resolve())
                or len(raw) != row['bytes'] or sha256(raw).hexdigest() != row['sha256']):
            raise ValueError('Retained asset differs from its frozen input')
        rendered = raw
        if name.suffix == '.html' and b'rel="icon"' not in raw:
            if raw.count(b'</head>') != 1:
                raise ValueError('Retained HTML needs one closing head element')
            rendered = raw.replace(b'</head>', b'<link rel="icon" href="data:,"></head>')
        target = site / name
        if not target.resolve().is_relative_to(site.resolve()) or target.is_symlink():
            raise ValueError('Retained asset escapes the publication')
        if target.exists() and target.read_bytes() not in (raw, rendered):
            raise ValueError('Refusing to replace a changed retained public asset')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rendered)
        rows.append(row)
    return rows
