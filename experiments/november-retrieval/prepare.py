"""Check the pinned publication and export all captured contribution bodies."""
import sys,json,hashlib
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'upstream/scripts'))
from hansard_access import Access
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':
    out=Path(sys.argv[2])
    a=Access(Path(sys.argv[1]))
    meta=a.describe()
    if meta['published_commit']!='41a340e06ec02b7d5d4d5802e893534697328d32':
        raise ValueError('Publication changed. Use original pinned pointer.')
    parts,rs=a.capture_rows()
    counts=Counter((r['day'],r['house']) for r in rs.values())
    assert len(rs)==a.coverage['contributions']
    for d in a.coverage['dates']:
        for h,s in d['houses'].items():
            assert counts[d['date'],h]==s['contributions']
    f=out/'corpus.jsonl'
    with f.open('x') as stream:
        for route,r in sorted(rs.items()):
            fields={k:r[k] for k in ['day','house','text','url']}
            assert fields['text'] and fields['url'].startswith('https://hansard.parliament.uk/')
            item=dict(route=route,title=parts[r['part']]['title'],speaker=r['attributed_to'],**fields)
            stream.write(json.dumps(item,ensure_ascii=False)+'\n')
    save(HERE/'capture.json',dict(commit=meta['published_commit'],snapshot=meta['snapshot'],through=a.pointer['through'],
        verified_at=a.pointer['verified_at'],capture=meta['capture'],digest=sha(f),manifest_sha256=sha(a.capture/'manifest.json'),
        counts=[dict(day=d,house=h,contributions=c) for (d,h),c in sorted(counts.items())]))
