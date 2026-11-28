"""Check paired follow-up cases, isolation, consistency and unchanged model pins."""
from pathlib import Path
import hashlib,json,sys
from verify_run import HERE,load,digest,check_net
from score import evaluate
if __name__=='__main__':
    store=Path(sys.argv[1]);idx=store/'voice-index';out=store/'voice-answers'
    primary=load(HERE/'verification.json')
    suite=HERE/'voice'
    assert digest(suite/'answer.py')==digest(HERE/'answer.py')
    assert digest(suite/'score.py')==digest(HERE/'score.py')
    policy=load(suite/'protocol.json')
    assert all(policy[k]==load(HERE/'protocol.json')[k] for k in ('commit','chunk_words','overlap_words','rrf_k','candidates_per_channel','public_documents','private_documents','wrapper_byte_limit','context_tokens','output_tokens','seed','temperature'))
    ctrl=load(out/'controls.json');index=load(idx/'index-receipt.json')
    assert index['query_sha256']==digest(suite/'queries.json') and index['protocol_sha256']==digest(suite/'protocol.json')
    assert index['corpus_sha256']==primary['sources']['digest'] and index['original_rankings_reproduced']==42
    assert ctrl['decision_model']==primary['answer_controls']['decision_model'] and ctrl['writer_model']==primary['answer_controls']['writer_model']
    for path,probes,n in [(idx,index['probes'],2),(out,ctrl['probes'],3)]:
        check_net(path,probes,n,primary['answer_network']['policy'])
    q={c['id']:c for c in load(suite/'questions.json')}
    ranks={(r['id'],r['method']):r for r in load(idx/'rankings.json')}
    actual=[json.loads(l) for l in (out/'answers.jsonl').read_bytes().splitlines()]
    assert len(actual)==len(ranks)==16 and set(ranks)=={(k,m) for k in q for m in ['FTS5','FTS5 + E5']}
    scored=[]
    for row in actual:
        t=ranks.pop((row['id'],row['method']))
        ps=t['passages'];assert len(ps)==len({x['route'] for x in ps})==3
        text='\n\n'.join(f"# R{p['rank']} {p['title']} | {p['speaker']} | {p['day']} {p['house']}\n\n{p['body']}\nSource: {p['url']}" for p in ps).encode()
        assert len(text)==row['bytes']<=5600 and hashlib.sha256(text).hexdigest()==row['evidence_sha256']
        assert 0<row['decision']['input_tokens']<=2048 and row['decision']['output_tokens']==0
        if row['answer'] is not None:assert 0<row['writer_cost']['prompt_tokens']<=1848 and 0<row['writer_cost']['generated_tokens_reported']<=200
        scored.append(evaluate(q[row['id']],t,row))
    assert not ranks and scored==load(suite/'scores.json')
    summary={'pairs':8,'trials':16,'replayed_primary_rankings':42,'corpus_sha256':index['corpus_sha256'],
             'questions_sha256':digest(suite/'questions.json'),'scores_sha256':digest(suite/'scores.json'),
             'rankings_sha256':digest(idx/'rankings.json'),'answers_sha256':digest(out/'answers.jsonl'),
             'index_network':load(idx/'network.json'),'answer_network':load(out/'network.json'),
             'index_probes':index['probes'],'answer_probes':ctrl['probes'],'sealed_sink_requests':0}
    (suite/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Verified all 8 follow-up pairs.')
