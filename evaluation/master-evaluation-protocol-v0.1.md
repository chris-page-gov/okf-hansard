# Master evaluation protocol and completeness register — v0.1

Date: 19 November 2026. **Status: design implemented in documentation; evidence verification, benchmarking and site implementation NOT completed.** This file is the entry point for the proposed Hansard OKF+ evaluation. It does not assert that a measured baseline exists.

## 1. Scope and linked specifications

- [Personas and questions](personas-and-questions-v0.1.md): 3 personas × 3 questions; API-Q1–3 and GRAPH-Q1–4.
- [Reference-answer ledger](reference-answers-v0.1.md): 9 provisional answers and outstanding evidence checks.
- [Additive scoring](additive-scoring-v0.2.md): 16 tests, **246 available points** before N/A; no points yet awarded.
- [Retrieval architectures](retrieval-architecture-comparison-v0.1.md): keyword, graph, deterministic MCP, semantic and hybrid; 17-point **separate per-query** rubric.
- [Personal AI and vocabulary](personal-ai-vocabulary-retrieval-v0.1.md): lexical, generic, personalised, resolved and expanded concept selection; 21-point **separate per-run** rubric.
- [Extraction benchmark protocol](extraction-benchmark-v0.1.md): independently annotated source-to-graph comparison.
- [Cost and decision protocol](cost-and-decision-protocol-v0.1.md): lifecycle accounting and evidence-based architecture decisions.
- [Coverage issue #3](https://github.com/chris-page-gov/okf-hansard/issues/3): Monday history index and SEND appeal-right tracing.
- [i.AI comparator](https://github.com/i-dot-ai/parliament-mcp): documented semantic search implementation; runtime equivalence and query costs unverified.

## 2. Master evaluation matrix

Each question ID is a primary key; its individual atomic criteria live in the additive scoring file. The 'reference' column identifies **evidence work**, not an assertion that the answer is verified.

| IDs | Persona / purpose | Reference evidence | Primary capability | Scoring ledger | Current state |
|---|---|---|---|---|---|
| P1-Q1–3 | Parent/carer: appeal rights | 16 Nov SEND exchange; 2014 Act; earlier contributions | Legal-status distinction and history | Answer quality | Draft, partial |
| P2-Q1–3 | Parliamentary researcher: exact trace | Contribution IDs, passages, predicates, dates | Source-to-graph trace and false-positive rejection | Answer quality | Draft, partial |
| P3-Q1–3 | Citizen/journalist: proceedings and linked topics | Both Houses, Microsoft statement/correction, NHS/Palantir | Coverage, factual summary, source linkage | Answer quality | Draft, partial |
| API-Q1–3 | API discovery and source escalation | Official API docs, source identifiers, versions | Discovery, correction and gap handling | API/retrieval | Specified, untested |
| GRAPH-Q1–4 | Ontology and relationship fitness | Independently annotated source passages | Graph semantics, identity, temporal/legal status | Graph/ontology | Specified, untested |
| RET-K/G/M/S/H | Five retrieval arms | Same frozen corpus and relevance pool | Precision/recall, ranking, cost and reliability | Separate 17-point per-query | Designed, untested |
| VOC-L/G/P/R/E/V | Six interpretation conditions | Consented expression profiles, gold concept IDs | Vocabulary discovery, personalisation, resolution | Separate 21-point per-run | Designed, untested |
| EXT | Source-to-graph extraction | Blinded adjudicated annotation set | Entity/relationship precision and recall | Extraction metrics, not arbitrary additive total | Designed, untested |
| SITE | GitHub Pages vs Sites | Identical graph, source and test questions | UI/access-mode differences | Report by layer | Sites not built |

**Record format per run:** `run_id, question_id, persona_id, corpus_id, graph_sha256, ontology_version, retrieval_arm, client_model, client_context_condition, source_access_mode, answer, source_ids, graph_assertion_ids, criterion_awards[], critical_flags[], latency_ms, token_counts, provider_cost, client_cost, adjudicator, status`. Keep missing/not-run separate from zero.

## 3. Freeze and reproduce the baseline

1. Record the exact Git commit for main and gh-pages; retrieve and SHA-256 the published OKF JSON, YAML-LD, coverage, vocabulary/profile, history index, graph manifest and checksums. Compare published bytes with declared checksums.
2. Record captured dates, Commons/Lords denominators, missing source dates, history window, aliases/profile hash, corrections, source capture timestamps and source licences. Keep the source corpus snapshot immutable.
3. Pin parser/extractor revision, schema, ontology, vocabulary aliases, graph builder configuration, deterministic index, vector model/index parameters, MCP version and host environment.
4. Store query strings, prompts, model versions, temperatures where exposed, tool-call traces, API response IDs/digests, time, retries and error/coverage statuses. Avoid storing personal memory in provider-side logs.
5. Run a smoke test for source integrity, graph assertions, contribution locator, missing-day behaviour, correction handling and one negative control.
6. Publish a reproducibility receipt with command lines, environment and hashes; do not label a baseline 'frozen' until the receipt exists and is validated.

## 4. Independent reference evidence and blinded adjudication

Use official Hansard APIs and original pages, the Parliament Members/Bills services and legislation.gov.uk as applicable. Reference evidence must be collected **without consulting OKF output for the truth of a claim**. Candidate-pooling may include results from all systems, but adjudicators should receive anonymised candidate passages in random order, with official source text and identifiers. Include unpooled samples to detect missed relevant documents. Two reviewers independently adjudicate ambiguous semantic/temporal/legal relations; record disagreements, rationale and resolution. Do not use the same model's unsupported judgement as both prediction and gold standard.

## 5. Scoring reconciliation and failure attribution

- The existing **246-point** framework is the v0.2 primary 16-test design only; it is **not** a measured score.
- The **17-point retrieval rubric** is per query/arm, and the **21-point vocabulary rubric** is per applicable run. They are NOT additive to 246 without a formally versioned denominator change.
- Extraction quality is evaluated with precision/recall and error taxonomy against labelled evidence, plus provenance coverage; do not substitute raw edge counts for accuracy.
- Preserve separate scorecards for answer quality, graph/ontology, retrieval/API, vocabulary interpretation, extraction, UI usability, reliability and cost. Report numerator, eligible denominator, N/A rationale, critical failures and confidence intervals.
- Failure attribution: **source gap**, **corpus coverage**, **extraction miss**, **ontology inadequacy**, **incorrect assertion**, **index/publishing defect**, **retrieval failure**, **client concept resolution**, **reasoning error**, **source correction/freshness**, **tool/host failure**. A missing Monday UI anchor is provisionally a publishing/index defect, not proof of a deficient ontology.
- Critical failures (fabricated citations, false legal status, identity confusion, unsupported historical link, ignored digest mismatch) are reported independently and prevent an unqualified success verdict.

## 6. Architecture comparison and decision gates

Hold corpus and personal-AI reasoning conditions constant for retrieval-only tests; compare lexical baseline, graph, deterministic MCP, i.AI-style semantic and hybrid. Evaluate query vocabulary mapping separately with/without personal context. Account for provider inference, client inference, ingestion, indexing, hosting, updates and operations. Select no architecture by composite score alone: examine retrieval quality, semantic correctness, provenance, privacy, reliability and cost at declared query volumes. See [cost and decision protocol](cost-and-decision-protocol-v0.1.md).

## 7. Completeness checklist — design captured vs work executed

| Requirement | Design captured | Implemented/tested |
|---|---|---|
| Personas and 9 questions | [x] | [ ] Reference answers not fully verified |
| Independent evidence and correction ledger | [x] | [ ] Partial reference answers |
| Atomic additive scoring and critical failures | [x] | [ ] No awarded scores |
| API discovery contract and safe escalation | [x] | [ ] Contract not deployed |
| Graph and controlled-vocabulary fitness | [x] | [ ] Gold graph/sample not yet labelled |
| Source-to-graph extraction benchmark | [x] | [ ] No extraction run |
| Historical SEND appeal trace | [x] | [ ] Issue #3 open |
| Retrieval methods incl. i.AI comparator | [x] | [ ] No matched corpus experiment |
| Personal AI vocabulary and privacy | [x] | [ ] No personalisation experiment |
| Cost separation and break-even analysis | [x] | [ ] No measured call/cost data |
| Frozen corpus and reproducibility receipt | [x] | [ ] Not yet frozen |
| Blind adjudication and controls | [x] | [ ] Not yet conducted |
| Decision criteria and architecture trade-offs | [x] | [ ] No decision evidence |
| GitHub Pages versus Sites | [x] | [ ] Sites not built |
| Integrated scorecards, IDs and failure taxonomy | [x] | [ ] No run ledger populated |

**Review outcome:** All major ideas discussed in the 19 November voice design session are represented in linked, version-controlled documents. This is a **documentation completeness assessment**, not a claim that experiments, code, reference verification or implementation are complete.

## 8. Next executable milestones

1. Review this protocol and merge the draft PR once agreed; preserve the baseline before any ontology change.
2. Verify nine reference answers and source locators, prioritising SEND exact anchor, Lords coverage and Microsoft correction.
3. Build a small independent extraction gold set and graph/ontology evaluation harness.
4. Freeze and verify the published corpus and run the current OKF baseline.
5. Implement controlled-vocabulary discovery and optional personal-AI resolution experiments.
6. Compare deterministic, semantic and hybrid retrieval on the same eligible corpus; measure costs.
7. Build Sites using the frozen knowledge and run paired comparisons.
