"""Sealed full-corpus search; the query input contains no answers or gold sources."""
import argparse,hashlib,json,re,sqlite3,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'upstream/experiments/reference-consumer'))
from decide import run_isolated,probe_boundary
from provision_e5 import verify
STOP=set('a an and are as at be been by did do does for from had has have how in into is it its many much of on or that the their there they this to was were what when where which who whom why will with would'.split())
def load(p): return json.loads(p.read_bytes())
def save(p,value): p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def hashed(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def clock(): return time.monotonic()
def chunks(text):
    words=text.split()
    for start in range(0,len(words),80):
        yield ' '.join(words[start:start+96])
        if start+96>=len(words): break
def passage_text(r):
    return f"{r['title']} | {r['speaker']} | {r['day']} {r['house']} | {r['body']}"
def encode(model,tok,texts,device):
    import torch
    data=tok(texts,padding=True,return_tensors='pt',truncation=False)
    if data['input_ids'].shape[1]>512: raise ValueError('E5 input overflow')
    data={k:v.to(device) for k,v in data.items()}
    with torch.inference_mode():
        hidden=model(**data).last_hidden_state
        mask=data['attention_mask'].unsqueeze(-1)
        pooled=(hidden.float()*mask).sum(1)/mask.sum(1)
        return torch.nn.functional.normalize(pooled,p=2,dim=1).cpu().numpy()
def ordered(values,n):
    import numpy as np
    return (np.argsort(-values,kind='stable')[:n]+1).tolist()
def worker(a):
    import os
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
    import numpy as np
    import torch
    from transformers import AutoModel,AutoTokenizer
    probes=[probe_boundary(a.port,a.socket)]
    p=load(HERE/'protocol.json'); q=load(HERE/'queries.json')
    if hashed(a.store/'corpus.jsonl')!=p['corpus_sha256']: raise ValueError('Corpus digest mismatch')
    verify(a.store/'model')
    db=sqlite3.connect(a.output/'passages.sqlite')
    db.execute('CREATE VIRTUAL TABLE passages USING fts5(content, tokenize="porter unicode61")')
    rows=[None]
    t=clock()
    with (a.store/'corpus.jsonl').open() as stream:
        for line in stream:
            source=json.loads(line)
            text=source.pop('text')
            for i,body in enumerate(chunks(text)):
                r={**source,'chunk':i,'body':body}
                db.execute('INSERT INTO passages(rowid, content) VALUES (?,?)',(len(rows),passage_text(r)))
                rows.append(r)
    db.commit()
    fts_seconds=clock()-t
    device='mps' if torch.backends.mps.is_available() else 'cpu'
    t=clock()
    tok=AutoTokenizer.from_pretrained(a.store/'model',local_files_only=True)
    model=AutoModel.from_pretrained(a.store/'model',local_files_only=True,use_safetensors=True).eval().to(device)
    vectors=np.lib.format.open_memmap(a.output/'vectors.npy',mode='w+',dtype='float32',shape=(len(rows)-1,384))
    # Group similar lengths to reduce padding. Store vectors in their original passage order.
    indices=sorted(range(1,len(rows)),key=lambda i:len(passage_text(rows[i])))
    for j in range(0,len(indices),64):
        ids=indices[j:j+64]
        vectors[np.asarray(ids)-1]=encode(model,tok,['passage: '+passage_text(rows[i]) for i in ids],device)
        if j%2048==0: print('E5 passages',j,len(indices),flush=True)
    vectors.flush()
    if not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-4): raise ValueError('Unnormalised vectors')
    dense_seconds=clock()-t
    results=[]
    for query in q:
        question=query['question']
        t=clock()
        terms=[x for x in re.findall(r'[^\W_]+',question.casefold()) if x not in STOP]
        expr=' OR '.join('"'+w+'"' for w in dict.fromkeys(terms))
        lex=[i for (i,) in db.execute('SELECT rowid FROM passages WHERE passages MATCH ? ORDER BY rank,rowid LIMIT 100',(expr,))]
        lt=clock()-t
        t=clock()
        v=encode(model,tok,['query: '+question],device)[0]
        # Explicit accumulation avoids Accelerate BLAS floating-point status warnings on macOS.
        sims=np.einsum('ij,j->i',vectors,v,optimize=False)
        if not np.isclose(np.linalg.norm(v),1,atol=1e-4) or not np.isfinite(sims).all() or np.max(np.abs(sims))>1.0001:
            raise ValueError('Invalid cosine similarity')
        dense=ordered(sims,100)
        scores={}
        for ranks in (lex,dense):
            for rank,i in enumerate(ranks,1): scores[i]=scores.get(i,0)+1/(60+rank)
        hybrid=sorted(scores,key=lambda i:(-scores[i],i))
        dt=clock()-t
        for name,ranked,elapsed in [('FTS5',lex,lt),('FTS5 + E5',hybrid,lt+dt)]:
            selected=[]; seen=set()
            for pid in ranked:
                r=rows[pid]
                if r['route'] in seen: continue
                selected.append({**r,'pid':pid,'rank':len(selected)+1})
                seen.add(r['route'])
                if len(selected)==p['public_documents']: break
            results.append({'id':query['id'],'method':name,'seconds':elapsed,'passages':selected})
    probes.append(probe_boundary(a.port,a.socket))
    save(a.output/'rankings.json',results)
    save(a.output/'index-receipt.json',{'device':device,'torch':torch.__version__,'sqlite':sqlite3.sqlite_version,
        'chunks':len(rows)-1,'contributions':len({r['route'] for r in rows[1:]}),'lex_build_s':fts_seconds,
        'dense_build_s':dense_seconds,'vectors_bytes':(a.output/'vectors.npy').stat().st_size,
        'sqlite_bytes':(a.output/'passages.sqlite').stat().st_size,'query_sha256':hashed(HERE/'queries.json'),
        'corpus_sha256':p['corpus_sha256'],'protocol_sha256':hashed(HERE/'protocol.json'),'probes':probes})
def options():
    pa=argparse.ArgumentParser()
    for field in ('store','output'): pa.add_argument('--'+field,type=Path,required=True)
    pa.add_argument('--_sealed-port',dest='port',type=int);pa.add_argument('--_socket',dest='socket',type=Path)
    return pa.parse_args()
if __name__=='__main__':
    a=options()
    if a.port:worker(a)
    else:
        a.output.mkdir(mode=0o700)
        network=run_isolated(a,Path(__file__),('store','output'),7200)
        save(a.output/'network.json',network)
