# Additive evaluation scoring specification — v0.2

**Status:** proposed, unscored, 19 November 2026. Replaces the six holistic 0–4 marks in the earlier draft. All awards require evidence. This is a scoring design, not a report of measured performance.

## Rules

- Score each **atomic criterion** as either **earned in full** or **not earned**; no discretionary partial points. Award only when the named achievement and its source evidence are present. A missing criterion scores zero; a genuinely inapplicable criterion is N/A only with a documented reason and excluded from the denominator.
- Weights: 1 = simple identification; 2 = direct retrieval or basic relationship; 3 = substantive evidence-backed interpretation, temporal semantics or multi-step reasoning. Weights are provisional and should be calibrated on a pilot.
- Record criterion ID (question + row number), expected source, actual output, evidence URL/ID, reviewer, award, failure type, and reproducibility notes.
- Maintain **three separate scorecards**: (A) answer quality: P1/P2/P3; (B) graph/ontology: GRAPH; (C) retrieval/API: API. Report question, persona and layer totals with earned/eligible points and percentages; do not average percentages without denominators. Usability, latency and reliability remain **additional measured outcomes**, not inferred from answer correctness.
- Critical failures are separate flags: fabricated citation, treating proposal as enacted law, unsupported legal advice, false identity, fabricated historical connection, source digest mismatch ignored. Report critical-failure counts even if additive points are high; do not call a flagged run 'fully successful'.
- Keep baseline corpus and question text fixed. Distinguish OKF-only, OKF+official source retrieval, and external research. Never silently use external information to make an OKF-only run appear successful.
- Score the **current implementation** and Sites independently with the same reference answers, access-mode declaration and evidence standards. A graph quality score is corpus-level and should not change merely because a new interface improves access.
- Evaluate graph precision and recall only on a labelled sample with an explicit denominator. Zero observed matches is not zero graph coverage unless the intended scope and source completeness are established.
- Review adjudication disagreements and calibrate weights before final baseline publication.

## Atomic criteria for all 16 tests

### P1-Q1 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Who asked | 1 | Exact source, assertion, or recorded test output supporting this criterion |
| date/House | 1 | Exact source, assertion, or recorded test output supporting this criterion |
| precise contribution link | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| appeal concern | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| minister response | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| distinguish non-answer from commitment | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| evidence links | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| gaps | 1 | Exact source, assertion, or recorded test output supporting this criterion |

### P1-Q2 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Identify existing EHCP law | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| enumerate appealable decisions | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| source statute/version | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| identify proposed ISP | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| separate law/proposal | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| qualification | 2 | Exact source, assertion, or recorded test output supporting this criterion |

### P1-Q3 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Earlier dated source | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| second independent relevant source | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| exact locators | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| substantive comparison | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| lexical false-positive exclusion | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| gaps | 2 | Exact source, assertion, or recorded test output supporting this criterion |

### P2-Q1 — 12 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Speaker | 1 | Exact source, assertion, or recorded test output supporting this criterion |
| date | 1 | Exact source, assertion, or recorded test output supporting this criterion |
| House | 1 | Exact source, assertion, or recorded test output supporting this criterion |
| stable contribution ID | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| exact link | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| source identity check | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| confidence/gaps | 1 | Exact source, assertion, or recorded test output supporting this criterion |

### P2-Q2 — 19 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Start anchor | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| earlier contribution | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| second earlier contribution | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| predicate and assertion ID | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| evidence spans | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| temporal ordering | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| lexical/semantic distinction | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| coverage | 2 | Exact source, assertion, or recorded test output supporting this criterion |

### P2-Q3 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Identify lexical candidate | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| demonstrate false positive with source | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| identify true relevant case | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| distinguish predicate types | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| quantify inspected denominator | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| gaps | 2 | Exact source, assertion, or recorded test output supporting this criterion |

### P3-Q1 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Commons main business | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| Lords main business | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| source links | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| accurate date/sitting | 1 | Exact source, assertion, or recorded test output supporting this criterion |
| distinguish proceedings from contributions | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| completeness bounds | 3 | Exact source, assertion, or recorded test output supporting this criterion |

### P3-Q2 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Minister/date | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| outage account | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| Hansard anchor | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| distinguish attributed claims | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| subsequent correction checked | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| accurate limits | 2 | Exact source, assertion, or recorded test output supporting this criterion |

### P3-Q3 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Monday source | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| Tuesday source | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| named actors | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| FDP/Palantir relationship | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| explicit vs alias distinction | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| source spans | 3 | Exact source, assertion, or recorded test output supporting this criterion |

### API-Q1 — 13 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Official API service identified | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| supported endpoint/operation documented | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| stable identifier mapping | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| source/version evidence | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| error/limits documented | 2 | Exact source, assertion, or recorded test output supporting this criterion |

### API-Q2 — 14 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Gap detected | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| official search route discovered | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| reproducible query/coverage | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| source-linked candidates | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| no semantic overclaim | 3 | Exact source, assertion, or recorded test output supporting this criterion |

### API-Q3 — 14 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Original captured digest | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| current text retrieval | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| mismatch/correction detection | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| provenance retained | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| clear user warning | 3 | Exact source, assertion, or recorded test output supporting this criterion |

### GRAPH-Q1 — 18 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Distinct legal-right node/concept | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| proposal node/concept | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| statement/claim node | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| typed relationships | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| temporal/legal-status validity | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| evidence | 3 | Exact source, assertion, or recorded test output supporting this criterion |

### GRAPH-Q2 — 18 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Earlier record identified | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| typed predicate | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| assertion ID | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| evidence span | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| time context | 2 | Exact source, assertion, or recorded test output supporting this criterion |
| lexical/semantic label | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| justified relevance | 3 | Exact source, assertion, or recorded test output supporting this criterion |

### GRAPH-Q3 — 15 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Original source preserved | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| correction represented | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| relationship semantics | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| digests and dates | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| corrected retrieval behaviour | 3 | Exact source, assertion, or recorded test output supporting this criterion |

### GRAPH-Q4 — 18 possible points

| Atomic observable criterion | Points | Required evidence |
|---|---:|---|
| Stratified sample defined | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| gold adjudication recorded | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| true/false positives | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| false negatives | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| precision and recall with denominators | 3 | Exact source, assertion, or recorded test output supporting this criterion |
| ontology gap taxonomy | 3 | Exact source, assertion, or recorded test output supporting this criterion |


## Score summary template

| Layer | Tests | Maximum (before N/A) | Earned | Critical failures |
|---|---:|---:|---:|---:|
| Answer quality | 9 | 136 | Not evaluated | Not evaluated |
| API discovery and retrieval | 3 | 41 | Not evaluated | Not evaluated |
| Graph and ontology | 4 | 69 | Not evaluated | Not evaluated |
| **Total** | **16** | **246** | **Not evaluated** | **Not evaluated** |

**Interpretation caution:** these are maximum possible points for the rubric, not empirical measurements. A combined total is descriptive only; use the three layer results for decisions. Revisit weights if one persona or layer dominates for accidental reasons.

## Verification gate

Do not assign definitive baseline scores until reference-answer evidence is verified and the deployed release is pinned. Pending evidence is recorded as **not yet evaluated**, not as a failure. If a live evaluation cannot access an expected source, record an access failure separately from correctness.
