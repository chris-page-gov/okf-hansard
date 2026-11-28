from pathlib import Path
import json
from statistics import median
from report_helpers import HERE,METHODS,read,measures,report_data,casebook
def summary(root,m):
 c,b=report_data(root);return measures([b[x['id'],m] for x in c])
def src(root,key,n=0):
 c=next(x for x in read(root,'questions.json') if x['id']==key)
 return c['witnesses'][n]['url']
def link(root,key,title,n=0):return f"[{title}]({src(root,key,n)})"
def render():
 v=HERE/'voice';p0,p1=[summary(HERE,m) for m in METHODS];v0,v1=[summary(v,m) for m in METHODS]
 cases,vr=report_data(v)
 by_id={x['id']:x for x in cases}
 def row(name,a,b):
    return f"| {name} | {a['full']}/{a['n']} | {b['full']}/{b['n']} | {a['strict']}/{a['n']} | {b['strict']}/{b['n']} |"
 def detail(title,root):
    cs,by=report_data(root);out=[]
    for m in METHODS:
        rs=[by[c['id'],m] for c in cs]
        sup=measures([x for x in rs if x['status']=='supported']); neg=measures([x for x in rs if x['status']=='insufficient'])
        allr=measures(rs)
        out.append(f"| {title} · {m} | {allr['hits']}/{allr['refs']} | {sup['strict']}/{sup['n']} | {neg['status']}/{neg['n']} | {neg['strict']}/{neg['n']} | {allr['median_ms']:.1f} ms |")
    return '\n'.join(out)
 text=f"""# Finding Hansard evidence in a phone-style conversation

**Microsoft E5 helped when speakers’ names were left out.** On eight fresh conversational questions, adding E5 to SQLite search found the complete reference passage for {v1['full']} questions, compared with {v0['full']} for word search alone. With the same local models deciding and writing, {v1['strict']} hybrid answers and {v0['strict']} word-search answers passed the full fact-and-citation check.

On the original 21 questions, often rich in names and institutional clues, both systems produced **17 fully correct cited answers**. The faster word search retrieved the complete reference evidence for 20 questions, and the hybrid found it for 19. For this Hansard collection, keep word search as the baseline for precise look-ups. The evidence supports trying hybrid search for loosely worded conversation and checking that the delivered passage includes the whole answer.

## Results at a glance

| Question set | All sources found, FTS5 | All sources found, hybrid | Full answers, FTS5 | Full answers, hybrid |
|---|---:|---:|---:|---:|
{row('Original, 21 questions',p0,p1)}
{row('Conversational follow-up, 8 questions',v0,v1)}

“All sources found” requires the supporting words inside the delivered excerpt. A link to the correct speech can still leave the answer outside the evidence window. A “full answer” also requires the expected answer status, facts and exact citations. The follow-up was designed after seeing the first search results and was frozen before running its own searches. It is reported separately.

**What was searched.** The pinned release contains **20,900 contributions**, 15,125 from the Commons and 5,775 from the Lords, on **18 sitting dates from 2 to 27 November 2026**. Both engines indexed all 49,919 passages derived from those contributions. The official-source capture files were verified against their checksums. The local coverage, graph descriptor and history directory also matched the public files at the pinned Git revision. Earlier historical mentions and later sittings fall outside this test. [Published coverage](https://raw.githubusercontent.com/chris-page-gov/okf-hansard/41a340e06ec02b7d5d4d5802e893534697328d32/november/coverage.json) · [Capture counts by date and House](capture.json)

## What changed for a reader

- **A colloquial question found the right speaker.** When asked what proportion of people “behind bars” had speech, language or communication needs, FTS5 returned related passages about therapy and children. The hybrid ranked Sonia Kumar’s Commons contribution first. She gave the figure as **over 60%**. {link(v,'prison-communication','Read the exact contribution')}
- **A debate title alone was insufficient.** When asked how many people knew they had HIV and were still missing treatment, FTS5 found relevant contributions in the correct debate. E5 brought Lord Cashman’s question containing **5,000** into second place. Both questions concern what was said in Parliament. {link(v,'treatment-gap','Read Lord Cashman’s question')}
- **Both systems lost the end of a sentence.** They ranked the right driving agency statement first. The excerpt stopped at “the Libraries”, just before “of both Houses”. The scoring rule caught the missing detail. Selecting sentence boundaries or including the neighbouring passage within the same byte limit is a concrete next test. {link(v,'driving-plan','Read the complete statement')}
- **Finding the passage did not settle the claim.** Both searches found Dame Meg Hillier’s forecast of about £100,000 in board savings. Both answering pipelines treated it as supporting a question about a later *audited* saving. The forecast does not establish that outcome. {link(HERE,'future-board-saving','Read the forecast')}

## How the comparison was kept fair

The primary questions were written for this experiment from a deterministic sample of source contributions. They included 15 single-source factual questions, two requiring two contributions, and four asking for a fact the reference material did not establish. The follow-up used new contributions and eight questions without speaker names. Seven have a supported answer, and one asks for an unpublished figure. “Unseen” means held out from this evaluation: the questions and source-based answers were frozen before their retrieval runs. The two hybrid gains in the follow-up were both changes from abstention to a correctly cited answer. These were typed, speech-like questions. The phone microphone, speech recognition and a hosted personal assistant were outside the experiment.

Only the search method varied within each pair. Both used the original pinned OpenJev and Bonsai models, the same prompts, one seed (11), the same question and answer fields, identical limits and local network isolation. Each got the evidence its own search selected. Model inputs used one plain-text format throughout. The test bundled related evidence from the same publication, so the scores compare search methods across the capture and provide no independent ranking of Markdown, core OKF and OKF+.

| Set and search | Reference passages delivered | Strict answers on answerable questions | Correct status on insufficient questions | Strict answers on insufficient questions | Median search time |
|---|---:|---:|---:|---:|---:|
{detail('Original',HERE)}
{detail('Conversational',v)}

The original set included 19 required source passages across 17 answerable questions, because two questions needed two sources. For the four questions with insufficient evidence, we also recorded the parliamentary passage that establishes what was missing. Each question counts once in the headline answer score.

## Costs and interpretation

The SQLite index took **1.23 seconds** to build and occupied **40.2 MiB**. E5 added **87.6 seconds** of model loading and passage encoding, a **73.1 MiB** vector file, and **127.3 MiB** of model weights. Both methods used the same Mac and SSD. These figures exclude environment installation and the shared corpus. Latencies in the table are elapsed search times on an already built index; the hybrid timing includes the lexical search. Query caching, device load and file caches can affect subsequent runs.

The strict rubric occasionally penalises a sound answer. Both systems returned “0.5% of their budgets” with the correct Welsh community-care contribution. The accepted answer list contained “0.5%”, so both missed the fixed wording check. In the reservoir question, FTS5 supplied a different speaker who also mentioned nine reservoirs. That supported the number but did not establish what Dan Jarvis, the person named in the question, had said. The original scores are retained. {link(HERE,'Welsh-community-care','Welsh community-care contribution')} · {link(HERE,'reservoir-pair','Dan Jarvis’s contribution',1)}

The sample is small and source-led. The initial questions often reuse distinctive names, which makes them favourable to word search. The follow-up probes a different style and was motivated by that first result. A different speech can also provide valid evidence. These features limit how far the observed advantage transfers to actual callers. For a deployment decision, the next useful comparison would use independently authored user questions, check alternative valid sources and measure success within the same three-passage cap.

"""
 text+=(HERE/'methods.md').read_text()
 text+="""

## Evidence and replay

The verified primary search and the follow-up both used the original network-denial policy. The classifier and writer ran inside their own supervised worker with the same policy. The authorised control request reached its loopback sink, and none of the sealed workers did. These checks apply to the local process trees in this experiment. The tests used zero paid credits.

The trial records retain official links for all 174 supplied passage slots. Parliamentary material is attributed to UK Parliament. [Open Parliament Licence](https://www.parliament.uk/site-information/copyright/open-parliament-licence/)

[All 29 questions, actual model answers and Hansard citations](casebook.md) · [Exact passages shown for the original questions](retrieved-passages.json) · [Exact passages shown for the conversational questions](voice/retrieved-passages.json) · [Reproduction instructions](REPLAY.md) · [Primary trial scores](scores.json) · [Conversational trial scores](voice/scores.json) · [Primary verification](verification.json) · [Conversational verification](voice/verification.json)
"""
 (HERE/'report.md').write_text(text)
 casebook()
if __name__=='__main__':render()
