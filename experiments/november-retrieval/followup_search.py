"""Reuse both indexes and verify every primary ranking as a parity control."""
import argparse,json,os,sqlite3
from pathlib import Path
from time import monotonic
import re
from retrieval import encode,ordered,chunks,STOP,HERE,hashed,load,save,run_isolated,probe_boundary,verify
def worker(a):
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
    import numpy as np,torch
    from transformers import AutoModel, AutoTokenizer
    probes=[probe_boundary(a.port,a.socket)]
    base=a.store/'index-02'
    prior=load(base/'index-receipt.json')
    assert hashed(a.store/'corpus.jsonl')==prior['corpus_sha256']
    rows=[None]
    for line in (a.store/'corpus.jsonl').read_bytes().splitlines():
        r=json.loads(line)
        text=r.pop('text')
        for i,s in enumerate(chunks(text)):rows.append({**r,'body':s,'chunk':i})
    db=sqlite3.connect((base/'passages.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True)
    v=np.load(base/'vectors.npy',mmap_mode='r',allow_pickle=False)
    assert len(v)==len(rows)-1==db.execute('select count(*) from passages').fetchone()[0]
    verify(a.store/'model');device=prior['device']
    tok=AutoTokenizer.from_pretrained(a.store/'model',local_files_only=True)
    model=AutoModel.from_pretrained(a.store/'model',local_files_only=True,use_safetensors=True).eval().to(device)
    expected={(r['id'],r['method']):r['passages'] for r in load(base/'rankings.json')}
    results=[]
    for suite in (HERE,HERE/'voice'):
        for q in load(suite/'queries.json'):
            t=monotonic()
            words=[w for w in re.findall(r'[^\W_]+',q['question'].casefold()) if w not in STOP]
            expr=' OR '.join('"'+w+'"' for w in dict.fromkeys(words))
            lex=[i for (i,) in db.execute('select rowid from passages where passages match ? order by rank,rowid limit 100',(expr,))]
            lapsed=monotonic()-t;t=monotonic()
            vec=encode(model,tok,['query: '+q['question']],device)[0]
            sims=np.einsum('ij,j->i',v,vec,optimize=False)
            assert np.isfinite(sims).all() and np.abs(sims).max()<=1.0001 and np.isclose(np.linalg.norm(vec),1,atol=1e-4)
            dense=ordered(sims,100)
            weights={}
            for ids in [lex,dense]:
                for j,i in enumerate(ids,1): weights[i]=weights.get(i,0)+1/(60+j)
            fused=sorted(weights,key=lambda i:(-weights[i],i))
            dt=monotonic()-t
            for method,ids,secs in [('FTS5',lex,lapsed),('FTS5 + E5',fused,lapsed+dt)]:
                chosen=[];seen=set()
                for i in ids:
                    r=rows[i]
                    if r['route'] in seen:continue
                    seen.add(r['route']);chosen.append({**r,'pid':i,'rank':len(chosen)+1})
                    if len(chosen)==3:break
                if suite==HERE:
                    assert chosen==expected.pop((q['id'],method))
                else: results.append({'id':q['id'],'method':method,'seconds':secs,'passages':chosen})
    assert not expected
    probes.append(probe_boundary(a.port,a.socket))
    save(a.output/'rankings.json',results)
    save(a.output/'index-receipt.json',{**prior,'query_sha256':hashed(HERE/'voice/queries.json'),
        'protocol_sha256':hashed(HERE/'voice/protocol.json'),'reused_index':True,'original_rankings_reproduced':42,'probes':probes})
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('store','output'): p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--_sealed-port',dest='port',type=int);p.add_argument('--_socket',dest='socket',type=Path)
    a=p.parse_args()
    if a.port: worker(a)
    else:
        a.output.mkdir(mode=0o700)
        save(a.output/'network.json',run_isolated(a,Path(__file__),('store','output'),600))
