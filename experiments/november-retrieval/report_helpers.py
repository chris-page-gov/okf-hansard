"""Render the per-question audit and compute grouped measures from the frozen scores."""
import json
from collections import Counter
from pathlib import Path
from statistics import median
from html import escape
HERE=Path(__file__).resolve().parent
METHODS=('FTS5','FTS5 + E5')
def read(root,name):return json.loads((root/name).read_bytes())
def rate(v,den):return f'{v}/{den}'
def report_data(root):
    cases=read(root,'questions.json');rows=read(root,'scores.json')
    by={(r['id'],r['method']):r for r in rows}
    assert len(by)==2*len(cases)==len(rows)
    return cases,by
def measures(rows):
    g=list(rows);n=len(g)
    return dict(n=n,full=sum(r['all_found'] for r in g),hits=sum(r['found'] for r in g),refs=sum(r['required'] for r in g),
        status=sum(r['decision']==r['status'] for r in g),facts=sum(r['facts_ok'] for r in g),
        cites=sum(r['citations_ok'] for r in g),strict=sum(r['strict'] for r in g),
        median_ms=round(median(r['retrieval_ms'] for r in g),1),max_bytes=max(r['evidence_bytes'] for r in g))
def casebook():
    groups=[('Original question set',HERE),('Conversational follow-up',HERE/'voice')]
    lines=['# Question-by-question results','',
        'Each question has a reference source chosen before its search. “Retrieved” gives the number of those sources delivered with the supporting words. “Full pass” also requires the expected decision, the accepted fact value and the exact reference citations. The model IDs R1 to R3 refer to the three passages listed beside each answer.','']
    for label,root in groups:
        cases,rows=report_data(root)
        lines+=['## '+label,'']
        for i,c in enumerate(cases,1):
            lines += [f"### {i}. {c['question']}",'']
            expected='; '.join(k+' = '+v[0] for k,v in c['answers'].items()) if c['answers'] else 'The requested fact was unestablished.'
            lines += [f"Expected **{c['status']}**. {expected}",'']
            for w in c['witnesses']:
                lines += [f"- {w['speaker']}, {w['day']}. [Hansard contribution]({w['url']})"]
            lines+=['']
            for m in METHODS:
                s=rows[c['id'],m];a=s['answer']; st='pass' if s['strict'] else 'miss'
                facts=', '.join(f'{k} = {v}' for k,v in (a or {}).get('facts',{}).items()) or 'empty facts'
                ids=', '.join((a or {}).get('citations',[])) or 'none'
                choices=' · '.join(f"[{r['id']}]({r['url']})" for r in s['matches'])
                lines += [f"**{m}.** Retrieved {s['found']}/{s['required']}. OpenJev chose *{s['decision']}*. Bonsai returned {escape(facts)} and cited {ids}. Full {st}. Supplied passages {choices}.",'']
    (HERE/'casebook.md').write_text('\n'.join(lines).rstrip()+'\n')
def compare():
    for lbl,root in [('Primary',HERE),('Conversational',HERE/'voice')]:
        cases,by=report_data(root)
        print(lbl)
        for m in METHODS:
            r=[by[c['id'],m] for c in cases]
            for subset in ('supported','insufficient','all'):
                g=[x for x in r if subset=='all' or x['status']==subset]
                print(m,subset,measures(g))
        for k in ('all_found','strict'):
            print(k,[(c['id'],by[c['id'],METHODS[0]][k],by[c['id'],METHODS[1]][k]) for c in cases if by[c['id'],METHODS[0]][k]!=by[c['id'],METHODS[1]][k]])
if __name__=='__main__':casebook();compare()
