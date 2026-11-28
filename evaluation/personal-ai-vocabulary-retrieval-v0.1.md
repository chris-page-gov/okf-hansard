# Personal AI, controlled vocabulary and deterministic retrieval — research note v0.1

Date: 19 November 2026. Status: proposed architecture and test plan; not measured findings.

## Motivation

A user's personal AI may know their vocabulary, conversational shorthand, habitual expressions and intended referents. The knowledge provider should not have to operate a generative AI for each query. Instead, the personal AI interprets the user's natural language into **candidate concepts**, an authoritative OKF vocabulary resolves these deterministically, and a read-only graph or MCP service retrieves evidence. Personalisation must never override the ontology's actual meaning.

This hypothesis extends the comparison in [retrieval-architecture-comparison-v0.1.md](retrieval-architecture-comparison-v0.1.md), the [personas](personas-and-questions-v0.1.md), the [reference-answer ledger](reference-answers-v0.1.md), and the [additive scoring rubric](additive-scoring-v0.2.md). The parent SEND appeal-rights question is the initial test case; the same approach should extend to other Hansard domains.

## Proposed vocabulary discovery contract

The OKF should publish a compact, versioned, machine-readable vocabulary manifest, independently accessible without downloading the full graph. Each entry should include:
- Stable URI/ID, preferred label, definition, language, concept type, provenance and vocabulary version.
- Exact aliases and known alternative expressions, broader/narrower/related concepts, disambiguation hints and deprecated/replacement IDs.
- Allowed predicates and their domain/range, direction, temporal applicability, and whether a relation is lexical mention, asserted claim, proposed reform, enacted legal status, correction, or independently verified relationship.
- Lookup capabilities: exact ID, label/alias, prefix, bounded related-concept discovery, pagination, cache validators/digests, clear unsupported/ambiguous results.
- API discovery metadata: supported source services, authoritative documentation, identifier mapping, permitted read-only operations, source freshness and coverage, and correction/version handling.

The manifest is an authoritative **vocabulary**, not a license for the personal AI to invent concepts. It should be usable via static JSON/YAML-LD and optional deterministic WebMCP/MCP lookup tools. Host/client caching is desirable; measure transfer bytes and cold/warm latency.

## Interpretation pipeline

1. Retain the user's original question and conversational context **within the personal AI's permitted environment**.
2. Extract candidate intents, concepts, dates, entities, negations and constraints, optionally with a lightweight model.
3. Resolve candidates against the OKF's actual controlled vocabulary. Return exact IDs and disambiguation options, not free-form invented identifiers.
4. Distinguish *extraction* of expressed concepts from *expansion* to inferred related concepts. Log the reason for each expansion.
5. Execute deterministic, source-linked graph/MCP retrieval; disclose unmatched concepts, gaps and lexical-only matches.
6. Let the personal AI synthesise an answer using evidence and its own conversation context. Never send private memory to the OKF service unless separately and explicitly authorised.

Example: 'the council's support plan' might mean an EHCP for one user, but this must be checked against the ontology; it cannot automatically be equated to a proposed Individual Support Plan. 'Can I challenge it?' may suggest appeal rights, but this expansion is a hypothesis to test, not a legal conclusion.

## Evaluation design

**Conditions** (same questions, evidence snapshot, model budget and retrieval backend where feasible):
- L: deterministic stemming/lemmatisation/aliases only.
- G: generic personal-AI model with the published OKF vocabulary, without user history.
- P: personal AI with user-permitted conversational context, using the same vocabulary.
- R: personal AI with context **plus** deterministic vocabulary resolution and explicit concept-ID validation.
- E: model-assisted related-concept expansion with deterministic validation, recorded separately.
- V: embedding/vector retrieval comparator (i.AI-style), with identical corpus coverage.

Use consented synthetic or volunteered expression profiles; do not expose personal histories to the central service or evaluators. Counterbalance question wording and test across multiple users to avoid overfitting to one individual's shorthand. Include ambiguous, incomplete, spoken, colloquial, correction and cross-turn references, as well as unseen paraphrases and negative controls.

**Measures:** exact concept-ID precision/recall, ambiguous-concept calibration, false expansions, clarification rate, downstream Recall@k/Precision@k/nDCG, source/citation correctness, time to first evidence, cold/warm bytes and latency, repeatability, incremental personal-model tokens/calls, provider-side inference calls and lifecycle costs. Report confidence intervals for stochastic runs. Distinguish the user's already-paid model cost from genuinely marginal compute, and do not assume i.AI runs a generative completion per query.

## Additive acceptance tests (new scorecard, not yet included in 246-point baseline)

- Manifest is reachable independently of the graph and version/digest checked (2 points).
- Each tested concept has stable ID, definition, alias provenance and disambiguation information (3).
- Candidate concept resolves to an existing ID or explicit unresolved state, with no fabricated ID (3).
- Extracted and expanded concepts are labelled distinctly (2).
- Ambiguous personal shorthand triggers evidence-backed resolution or clarification (3).
- Personal context remains client-side unless explicitly authorised (3).
- Retrieval uses resolved IDs and returns source-linked passages and coverage status (3).
- All inference calls/tokens and incremental latency are measurable (2).

**Maximum: 21 points per applicable evaluation run**, pending review and calibration. Do not silently add to the existing 246-point maximum or the separate 17-point retrieval rubric; revise scorecard version and denominators first.

## Open research questions

1. How compact can a vocabulary manifest be without harming concept recall?
2. Is it better to present all concepts, a bounded shortlist or deterministic lookup on demand?
3. Can a single personal-AI inference both converse and select vocabulary concepts without a separate model call?
4. Does user-specific context improve unseen paraphrase performance enough to justify privacy and complexity costs?
5. Where do deterministic lexical methods suffice, and when is model-assisted expansion or vector search genuinely better?
6. Can the OKF represent a legally meaningful relationship, rather than merely a shared lexical mention, with precise provenance and temporal status?

## Next steps

- Review and freeze a vocabulary manifest contract; inspect current `profile/domain.yaml` and published facets before modifying the graph.
- Prepare a consent-safe test corpus and independently adjudicated concept IDs.
- Implement a deterministic resolver and baseline tests without server-side AI.
- Compare model-assisted extraction, personal context, semantic search and hybrid fallback under matched conditions.
- Publish separate scores for ontology fitness, extraction quality, retrieval, answer quality, cost and usability; preserve raw receipts.

## Related tracking

- Draft PR: https://github.com/chris-page-gov/okf-hansard/pull/4
- History index/SEND trace issue: https://github.com/chris-page-gov/okf-hansard/issues/3
- Comparator: https://github.com/i-dot-ai/parliament-mcp
