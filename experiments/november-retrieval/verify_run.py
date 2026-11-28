"""Independently check data joins, finite budgets and the original kernel/container controls."""
from collections import Counter
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_bytes())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check_net(p,probes,n,original):
    net=load(p/'network.json')
    assert net['policy']==original and net['sealed_sink_requests']==0
    assert load(p/'sink-trace.json')==[{'method':'GET','path':'/public-control','peer':'127.0.0.1'}]
    assert net['sink_trace_sha256']==digest(p/'sink-trace.json')
    assert len(probes)==n and all(x['result']==x['other_unix_socket']=='kernel-denied' for x in probes)
if __name__=='__main__':
    store=Path(sys.argv[1]); idx=store/'index-02'; out=store/'answers-01'
    old=load(HERE/'upstream/experiments/reference-consumer/results/2026-11-28-openjev-bonsai-phi-citations.json')
    plan=load(HERE/'protocol.json'); capture=load(HERE/'capture.json')
    idxr=load(idx/'index-receipt.json');ctrl=load(out/'controls.json')
    assert idxr['protocol_sha256']==digest(HERE/'protocol.json')
    assert digest(HERE/'questions.json')==plan['question_sha256']
    assert idxr['query_sha256']==digest(HERE/'queries.json')
    assert digest(store/'corpus.jsonl')==idxr['corpus_sha256']==capture['digest']
    assert sum(x['contributions'] for x in capture['counts'])==idxr['contributions']==20900
    assert old['models']=={'decision':ctrl['decision_model'],'writer':ctrl['writer_model']}
    assert all(old['retrieval'][k]==plan[k] for k in ('public_documents','private_documents','wrapper_byte_limit'))
    for path,probes,n in [(idx,idxr['probes'],2),(out,ctrl['probes'],3)]:
        check_net(path,probes,n,old['network']['policy'])
    trials=load(idx/'rankings.json')
    keys={(x['id'],x['method']) for x in trials}
    q=load(HERE/'queries.json')
    assert keys=={(x['id'],arm) for x in q for arm in ('FTS5','FTS5 + E5')}
    one=load(store/'index-01/rankings.json')
    idx_equal=all((a['id'],a['method'],a['passages'])==(b['id'],b['method'],b['passages']) for a,b in zip(one,trials,strict=True))
    evidence={}
    for t in trials:
        ps=t['passages']
        assert 0<len(ps)==len({p['route'] for p in ps})<=3
        text='\n\n'.join(f"# R{p['rank']} {p['title']} | {p['speaker']} | {p['day']} {p['house']}\n\n{p['body']}\nSource: {p['url']}" for p in ps)
        evidence[t['id'],t['method']]=text.encode()
    rows=[json.loads(l) for l in (out/'answers.jsonl').read_bytes().splitlines()]
    assert len(rows)==len(keys)==42 and {(r['id'],r['method']) for r in rows}==keys
    for r in rows:
        data=evidence[r['id'],r['method']]
        assert hashlib.sha256(data).hexdigest()==r['evidence_sha256'] and len(data)==r['bytes']<=5600
        assert 0<r['decision']['input_tokens']<=2048 and r['decision']['output_tokens']==0
        if r['answer'] is not None:
            assert 0<r['writer_cost']['prompt_tokens']<=1848 and 0<r['writer_cost']['generated_tokens_reported']<=200
    receipt={'verified_pairs':len(q),'trial_count':len(rows),'first_and_second_index_same_top_three':idx_equal,
             'sources':capture,'index':idxr,'answer_controls':ctrl,'inputs':{f:digest(HERE/f) for f in
                 ('questions.json','queries.json','protocol.json','prepare.py','retrieval.py','answer.py','score.py')},
             'index_network':load(idx/'network.json'),'answer_network':load(out/'network.json'),
             'scores_sha256':digest(HERE/'scores.json'),'rankings_sha256':digest(idx/'rankings.json'),
             'answers_sha256':digest(out/'answers.jsonl'),'sink_events_per_run':1,'sealed_sink_requests':0}
    (HERE/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Validated',len(rows),'trials. Top-three equivalence between index builds:',idx_equal)
