"""Score only after retrieval and generation. Admit declared aliases and ordinary punctuation."""
import collections,hashlib,json,re,sys,unicodedata
from pathlib import Path
from statistics import median
HERE=Path(__file__).resolve().parent
def load(path): return json.loads(path.read_bytes())
def norm(s):
    s=unicodedata.normalize('NFKC',s).casefold().strip().rstrip('.')
    s=re.sub(r'(?<=\d),(?=\d)','',s)
    s=s.replace('per cent','%').replace('percent','%').replace('‐','-').replace('‑','-')
    return re.sub(r'\s+',' ',s).replace(' %','%')
def evaluate(c,t,o):
    ps=t['passages']
    refs=c['witnesses']
    hits={w['route'] for w in refs if any(p['route']==w['route'] and w['needle'].casefold() in p['body'].casefold() for p in ps)}
    required={w['route'] for w in refs}
    parsed=o['answer']
    valid=isinstance(parsed,dict) and set(parsed)=={'citations','facts'} and isinstance(parsed['facts'],dict) and all(isinstance(x,str) for x in parsed['facts'].values()) and isinstance(parsed['citations'],list) and all(isinstance(x,str) for x in parsed['citations'])
    facts,cited=(parsed['facts'],parsed['citations']) if valid else ({},[])
    valid=valid and bool(cited) and len(set(cited))==len(cited) and set(cited)<=set(o['citable_ids'])
    bindings={'R'+str(p['rank']):p['route'] for p in ps}
    cited_routes={bindings[x] for x in cited if x in bindings}
    exact=valid and set(facts)==set(c['answers']) and all(norm(facts[k]) in [norm(s) for s in vals] for k,vals in c['answers'].items())
    citation_ok=valid and cited_routes==required and hits==required
    status_ok=o['decision']['predicted']==c['status']
    return dict(id=c['id'],kind=c['kind'],method=t['method'],status=c['status'],decision=o['decision']['predicted'],
        required=len(required),found=len(hits),all_found=hits==required,facts_ok=exact,citations_ok=citation_ok,
        strict=bool(status_ok and exact and citation_ok),evidence_bytes=o['bytes'],retrieval_ms=1000*t['seconds'],
        writer=o['writer_cost'],answer=parsed,decision_input_tokens=o['decision']['input_tokens'],
        matches=[{'id':'R'+str(p['rank']),'url':p['url'],'pid':p['pid'],'reference':p['route'] in hits} for p in ps])
if __name__=='__main__':
    q=load(HERE/'questions.json');policy=load(HERE/'protocol.json')
    assert hashlib.sha256((HERE/'questions.json').read_bytes()).hexdigest()==policy['question_sha256']
    ranked=load(Path(sys.argv[1])/'rankings.json')
    answers=[json.loads(l) for l in (Path(sys.argv[2])/'answers.jsonl').read_bytes().splitlines()]
    trials={(r['id'],r['method']):r for r in ranked}
    assert len(trials)==len(answers)==2*len(q)
    by_id={c['id']:c for c in q}
    scored=[evaluate(by_id[a['id']],trials[a['id'],a['method']],a) for a in answers]
    (HERE/'scores.json').write_text(json.dumps(scored,ensure_ascii=False,indent=2)+'\n')
    for name in ['FTS5','FTS5 + E5']:
        rows=[s for s in scored if s['method']==name]
        for kind in ['all','supported','insufficient']:
            g=[s for s in rows if kind=='all' or s['status']==kind]
            print(name,kind,len(g),{k:sum(s[k] for s in g) for k in ('required','found','all_found','facts_ok','citations_ok','strict')},'statuses',sum(s['status']==s['decision'] for s in g))
