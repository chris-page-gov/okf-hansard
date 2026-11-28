"""One-time source-led question authoring record. No retrieval engine is used here."""
import json, hashlib
from datetime import datetime,UTC
from pathlib import Path
from collections import Counter
HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'source-sample.json').read_bytes())
cases=[]
def add(key,question,answers,refs,kind):
    facts={k:v.split('|') for k,v in answers.items()}
    witnesses=[]
    for n,needle in refs:
        row=r[n-1]
        assert needle.casefold() in row['text'].casefold(), needle
        witnesses.append({**{k:row[k] for k in ('route','url','day','house','speaker','title')},'needle':needle})
    cases.append(dict(id=key,question=question,answers=facts,witnesses=witnesses,kind=kind,
                      status='supported' if facts else 'insufficient'))
add('holiday-clubs','Across how many local authorities in England had the holiday food and activities programme delivered the days mentioned in the Lords?',{'answer':'153'},[(2,'153 local authorities')],'paraphrase')
add('shared-housing','On what August date did Matthew Pennycook say the new planning framework on concentrations of small HMOs was published?',{'answer':'17 August|17 August 2026|17th August|August 17|2026-08-17'},[(1,'published on 17 August')],'literal')
add('housing-chargers','In the Social Housing Bill committee, how many months after passage would new clause 63 give the Secretary of State to make electric vehicle charging regulations?',{'answer':'6|six|6 months|six months'},[(3,'Within six months')],'literal')
add('defence-wales','How many defence jobs did the Wales minister say the country already had when discussing higher military spending?',{'answer':'20000|20 thousand|twenty thousand|20000 jobs'},[(5,'20,000 defence jobs')],'paraphrase')
add('water-shortfall','By what percentage did Lord Roborough say water in storage was below the usual level for that time of year?',{'answer':'17%|17 per cent|17 percent|17'},[(7,'17% beneath seasonal norms')],'paraphrase')
add('battery-factory','What sum did Baroness Dacres say Tata was investing in its UK gigafactory?',{'answer':'£4 billion|4 billion|£4bn|4bn|£4000000000|4000000000'},[(9,'Tata is investing £4 billion')],'literal')
add('summer-heat','How many heat-associated deaths did Olivia Blake say there were in the eight days in June?',{'answer':'2124|2124 deaths'},[(10,'2,124 heat-associated deaths')],'literal')
add('steel-operating-cost','What daily cost to taxpayers for keeping British Steel running did Lord Fox attribute to the National Audit Office?',{'answer':'£1.3 million|£1.3 million a day|£1.3 million per day|1.3 million|£1.3m|£1300000|1300000'},[(13,'£1.3 million a day')],'paraphrase')
add('island-heating','How many households in Torcuil Crichton’s own constituency had been able to claim the £300 heating-oil support?',{'answer':'324|324 households'},[(17,'only 324')],'literal')
add('Welsh-community-care','What share of their budgets were Welsh health boards to shift towards community services, according to Liz Saville Roberts?',{'answer':'0.5%|0.5 per cent|0.5 percent|half a per cent|0.5'},[(19,'0.5% of their budgets')],'paraphrase')
add('charity-research','How many people did Baroness Pidgeon say Cancer Research UK expected to take part in its trials over the following five years?',{'answer':'80000|80000 people|80 thousand|eighty thousand'},[(22,'80,000 people')],'literal')
add('paris-building','What fraction of the Palace of Westminster’s floorspace did Marie Goldman say Notre-Dame occupied?',{'answer':'one twentieth|one-twentieth|1/20|5%|5 per cent|a twentieth|one twentieth of the size'},[(28,'one twentieth')],'paraphrase')
add('technical-college','Which further education college did Lord Wallace name when he discussed teenagers who might otherwise leave education?',{'answer':'Shipley College|Shipley'},[(29,'Shipley College')],'paraphrase')
add('business-share','What proportion of UK businesses did the Business Secretary say were small or medium-sized?',{'answer':'99%|99 per cent|99 percent|99'},[(30,'99% of businesses')],'paraphrase')
add('health-record-notice','In the Lords discussion about AI systems accessing NHS data, within how many hours did the minister say the Information Commission should be informed?',{'answer':'72|72 hours|seventy-two hours'},[(31,'within 72 hours')],'literal')
add('arts-and-sport','Give the name of the choir Lord Wallace said was rehearsing, and the name of the Tredegar park where Nick Smith thanked junior running volunteers.',{'choir':'Parliament Choir|the Parliament Choir','park':'Parc Bryn Bach'},[(6,'Parliament Choir'),(12,'Parc Bryn Bach')],'two-source')
add('reservoir-pair','In two different debates, how far below seasonal norms did Lord Roborough put stored water, and how many new reservoirs did Dan Jarvis say the UK was investing in?',{'shortfall':'17%|17 per cent|17 percent|17','reservoirs':'9|nine|nine new reservoirs|9 reservoirs'},[(7,'17% beneath seasonal norms'),(21,'nine new reservoirs')],'two-source')
add('statistics-date','What exact calendar date did Baroness Merron announce for publishing the 2026 annual abortion statistics in her Annual Report Bill reply?',{},[(23,'announced in due course')],'unannounced')
add('mandate-date','What exact day did Baroness Dacres announce for publishing the result of the ZEV mandate consultation in her November answer?',{},[(9,'as soon as possible')],'unannounced')
add('future-trial-total','What final number of participants actually enrolled across the five years that Baroness Pidgeon said lay ahead for Cancer Research UK?',{},[(22,'expects 80,000')],'future outcome')
add('future-board-saving','What exact audited annual saving was achieved after the board disappeared, according to Dame Meg Hillier’s remarks about the Financial Services and Markets Bill?',{},[(8,'a saving of about £100,000')],'forecast versus outcome')
p=HERE/'questions.json'
with p.open('x') as f: json.dump(cases,f,ensure_ascii=False,indent=2)
policy={'commit':'41a340e06ec02b7d5d4d5802e893534697328d32','chunk_words':96,'overlap_words':16,'candidates_per_channel':100,'rrf_k':60,'public_documents':3,'private_documents':3,'wrapper_byte_limit':5600,'context_tokens':2048,'output_tokens':200,'seed':11,'temperature':0.2,
 'fusion':'equal reciprocal ranks of FTS5 BM25 and exact E5 cosine, union of top 100 distinct passages in each list; retain the best passage per contribution during final packing',
 'ranking':'FTS5 unicode61 porter OR terms after fixed English question stop list; title, speaker, date, house and passage body in both arms; stable passage ID tie-break',
 'metric':'reference-route hit with matching span in delivered text; complete set and mean fraction; also report strict cited factual answers, insufficient handling and latency. Negative questions scored separately. No selection by outcomes.',
 'question_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frozen_at':datetime.now(UTC).isoformat(),'corpus_sha256':json.loads((HERE/'capture.json').read_text())['digest']}
with (HERE/'protocol.json').open('x') as f:json.dump(policy,f,indent=2)
print(len(cases),Counter(c['kind'] for c in cases),policy['question_sha256'])
