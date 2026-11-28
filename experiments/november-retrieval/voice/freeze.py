"""All eight eligible questions from the second, previously unused sample."""
import hashlib,json
from datetime import datetime,UTC
from pathlib import Path
h=Path(__file__).resolve().parent
r=json.loads((h.parent/'followup-sample.json').read_text())
qs=[
 ("worker-wait","Someone earning forty grand who had already started the process of staying here permanently was used as an example. How many years would they now have to wait in total?","10|ten|ten years|10 years","five to 10 years"),
 ("release-date","On what September date was the press release mentioned about taking action against unlawful settlements in the West Bank?","8 September|8 September 2026|8th September|September 8|2026-09-08","press release that came out on 8 September"),
 ("prison-communication","What proportion of people behind bars did an MP say had difficulty with speech, language or communication?","over 60%|more than 60%|over 60 per cent|more than sixty per cent|greater than 60%|>60%","Over 60%"),
 ("treatment-gap","How many people were said to know they had HIV but still be missing out on treatment?","5000|5000 people|five thousand","5,000 people"),
 ("driving-plan","Besides the government website, where could parliamentarians find the annual plan for the agency that oversees driving tests and vehicle standards?","the Libraries of both Houses|Libraries of both Houses|in the Libraries of both Houses|the libraries of both Houses of Parliament|both Houses’ libraries","Libraries of both Houses"),
 ("deportation-total","What exact headcount did the quoted minister give for overseas offenders still here because of human-rights claims when the figures were discussed in the upper chamber?",None,"not yet in a form to be published"),
 ("portable-qualifications","Which profession seemed closest to getting its credentials accepted on both sides of the Channel after talks with the EU?","architects|architects only|architecture","only architects"),
 ("committee-speaking-time","How many minutes was the committee spokesperson allowed for the statement on getting legal help, before other MPs could put questions?","10|10 minutes|ten minutes|up to 10 minutes|up to ten minutes","up to 10 minutes")]
out=[]
for row,(key,q,forms,needle) in zip(r,qs,strict=True):
 assert needle.lower() in row['text'].lower()
 ref={k:row[k] for k in ('route','day','house','speaker','title','url')}
 out.append(dict(id=key,question=q,kind='voice-style',status='supported' if forms else 'insufficient',
                 answers={'answer':forms.split('|')} if forms else {},witnesses=[{**ref,'needle':needle}]))
for name,items in [('questions.json',out),('queries.json',[dict(id=c['id'],question=c['question'],keys=['answer']) for c in out])]:
 with (h/name).open('x') as f: json.dump(items,f,indent=2,ensure_ascii=False)
p=json.loads((h.parent/'protocol.json').read_text())
p.update(question_sha256=hashlib.sha256((h/'questions.json').read_bytes()).hexdigest(),frozen_at=datetime.now(UTC).isoformat(),
 purpose='Exploratory second set after observing the original retrieval ceiling, before looking up these questions. Reuse both index files, ranking parameters and the complete generation harness. Do not pool with the primary set.')
with (h/'protocol.json').open('x') as f:json.dump(p,f,indent=2)
