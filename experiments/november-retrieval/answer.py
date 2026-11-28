"""Pass retrieved evidence to the pinned classifier and writer in the original sandbox."""
import argparse, hashlib,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'upstream/experiments/reference-consumer'))
from acquire import CONTRACT,read,write_json
from corpus import Record
from decide import DECISION_CONTRACT,server,classify,probe_boundary,run_isolated
from evaluate import complete,parse_answer,settings_for,verify_model
from hybrid import WRITER,WRITER_PROFILE,citation_scope,writer_schema
FIELDS=('index','output','binary','weights','writer_binary','writer_weights')
def inputs(a,policy):
    queries={q['id']:q for q in read(HERE/'queries.json')}
    source=read(a.index/'rankings.json')
    if len(source)!=2*len(queries) or len({(r['id'],r['method']) for r in source})!=len(source):
        raise ValueError('Incomplete pairs')
    plan=[]
    for j,(_,q) in enumerate(queries.items()):
        pair=[r for r in source if r['id']==q['id']]
        assert {r['method'] for r in pair}=={'FTS5','FTS5 + E5'}
        if j%2: pair.reverse()
        for trial in pair:
            question=q['question']+' If supported, give the shortest exact value for each facts key: '+', '.join(q['keys'])+'.'
            records=[]
            for p in trial['passages']:
                title=f"{p['title']} | {p['speaker']} | {p['day']} {p['house']}"
                records.append(Record('R'+str(p['rank']),title,p['body'],p['url']))
            state='\n\n'.join(r.prose() for r in records)
            size=len(state.encode())
            assert len(records)<=policy['public_documents'] and size<=policy['wrapper_byte_limit']
            plan.append((trial,question,records,state))
    return plan
def worker(a):
    p=read(HERE/'protocol.json')
    base=settings_for(read(CONTRACT),WRITER_PROFILE)
    model=base['model'];decision=read(DECISION_CONTRACT)
    assert all(p[k]==model[k] for k in ('context_tokens','output_tokens','temperature')) and p['seed'] in model['seeds']
    assert all(p[k]==base['retrieval'][k] for k in ('public_documents','private_documents','wrapper_byte_limit'))
    probes=[probe_boundary(a.port,a.socket)]
    plan=inputs(a,p)
    rows=[]
    with server(a,base), (a.output/'decisions.jsonl').open('x') as f:
        for trial,question,records,state in plan:
            out=classify(a.socket,state,question,decision['orders'][0],decision,p['context_tokens'],{})
            row=dict(id=trial['id'],method=trial['method'],decision=out,evidence_sha256=hashlib.sha256(state.encode()).hexdigest(),bytes=len(state.encode()))
            rows.append(row); f.write(json.dumps(row)+'\n');f.flush()
    assert re.findall(r'truncated = (\d+)',(a.output/'server.log').read_text())==['0']*len(rows)
    probes.append(probe_boundary(a.port,a.socket))
    with (a.output/'answers.jsonl').open('x') as f:
        for row,(trial,question,records,state) in zip(rows,plan,strict=True):
            label=row['decision']['predicted']
            q=question.split(' If supported, give')[0]
            eligible=citation_scope(q,records,label)
            if eligible:
                raw,cost=complete(a.writer_binary,a.writer_weights,model,p['seed'],f'Fixed decision: {label}.\n\n{question}',
                                  state,a.output,instructions=WRITER,schema=writer_schema(eligible))
                parsed=parse_answer(raw)
                assert 0<cost['prompt_tokens']<=p['context_tokens']-p['output_tokens'] and 0<cost['generated_tokens_reported']<=p['output_tokens']
            else:
                parsed,cost=None,{'withheld':'No permitted citation for this decision.'}
            f.write(json.dumps({**row,'citable_ids':sorted(eligible),'answer':parsed,'writer_cost':cost},ensure_ascii=False)+'\n');f.flush()
    probes.append(probe_boundary(a.port,a.socket))
    write_json(a.output/'controls.json',{'probes':probes,'decision_model':decision['model'],'writer_model':model,'trials':len(rows)})
if __name__=='__main__':
    pa=argparse.ArgumentParser()
    for key in FIELDS:pa.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    pa.add_argument('--_sealed-port',dest='port',type=int);pa.add_argument('--_socket',dest='socket',type=Path)
    a=pa.parse_args()
    if a.port:worker(a)
    else:
        verify_model(a.weights,a.binary,read(DECISION_CONTRACT)['model'])
        verify_model(a.writer_weights,a.writer_binary,read(WRITER_PROFILE))
        assert read(a.index/'network.json')['sealed_sink_requests']==0
        assert read(a.index/'index-receipt.json')['query_sha256']==hashlib.sha256((HERE/'queries.json').read_bytes()).hexdigest()
        a.output.mkdir(mode=0o700)
        net=run_isolated(a,Path(__file__),FIELDS,3600)
        write_json(a.output/'network.json',net)
