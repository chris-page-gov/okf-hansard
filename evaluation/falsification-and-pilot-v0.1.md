# Falsification, adversarial testing and pilot protocol — v0.1

Date: 19 November 2026. **Design only**: no pilot or empirical result has been run. This extends the [master protocol](master-evaluation-protocol-v0.1.md) and must be agreed **before** scoring.

## Pre-registered hypotheses and failure conditions

| Hypothesis | Controlled comparison | Evidence that challenges/falsifies it | Provisional decision rule to approve before runs |
|---|---|---|---|
| H1: Explicit OKF graph adds retrieval value | Full OKF vs identical lexical index without graph | No meaningful increase in relevant evidence or provenance at matched coverage | Minimum +5 percentage points Recall@10 OR a demonstrable provenance/temporal capability absent from baseline, with no critical errors; threshold provisional |
| H2: Controlled vocabulary adds value | Full vocabulary vs label-only and aliases-only ablations | Equal/better concept-ID accuracy without vocabulary complexity | Minimum +5 pp concept-ID F1 or a material ambiguity reduction; provisional |
| H3: Historical relations add value | With/without historical edges on same records | Historical chain no more accurate than independently retrieved passages | At least one verified multi-hop relationship recovered without invented continuity and a measurable gain on a labelled historical set |
| H4: Personal context improves mapping | Same model with/without consented personal expression profile | No gain on unseen paraphrases, or privacy/false expansion harms | Predeclare minimum concept-ID F1 gain and maximum false expansion; do not optimise on test set |
| H5: Provider-side semantic inference earns its cost | Deterministic vs semantic vs hybrid at matched corpus | No material retrieval gain, or cost/latency disproportionate | Predeclare minimum Recall@k gain and maximum provider £/1,000 queries by workload |
| H6: Graph is robust to change and attack | Corrections, conflicting assertions, alias collisions, prompt injection | Fabricated evidence, false legal status, silent stale result, source-as-instruction | Zero tolerated fabricated citations/false legal status in critical sample; record all failures |
| H7: Vocabulary contract interoperates | Multiple independent personal AI models, same frozen vocabulary | Different/invalid IDs, hidden model-specific assumptions | Predeclare concept-ID accuracy and disagreement tolerance across models |

**Important:** Numbers above are *proposed thresholds*, not agreed pass/fail standards. Review and sign off a preregistration file before seeing pilot outcomes. Report effect sizes and uncertainty, not just binary pass/fail.

## Ablations

A0 plain keyword; A1 keyword + deterministic normalisation; A2 + aliases; A3 + controlled vocabulary definitions and relations; A4 + graph edges; A5 + temporal/history edges; A6 + personal-AI concept resolution; A7 + semantic/vector fallback. Hold source corpus, access permissions, question set and answer model constant; record changes to retrieval interface and coverage. Measure incremental quality, cost and complexity at each step. Include a 'no OKF' baseline with direct official Hansard source retrieval.

## Adversarial and correction cases

- Ambiguous names and roles held at different dates; misleading synonyms and false identity merges.
- Explicit negation, questions versus assertions, proposed law versus enacted law, and contradictory parliamentary statements.
- Original Hansard passage subsequently corrected; old digest must be flagged and original preserved.
- Missing contribution, missing date, unavailable API, truncated result, stale cache and unexpected licence/rights status.
- Prompt injection in retrieved text, malicious links, forged citations, tool output spoofing and oversized queries. Source text is untrusted evidence, never executable instructions.
- Distinguish failure at source, extraction, ontology, indexing, retrieval, model interpretation and presentation layers.

## Blinded disagreement resolution

Reference answers come from independently retrieved official evidence. Pool candidate passages from all arms, anonymise retrieval provenance, and use two independent reviewers for ambiguous relevance or semantic relations. Record adjudicator IDs, original labels, disagreements, consensus rationale and unresolved cases. A third reviewer resolves disputed cases where possible. Preserve original labels; never silently rewrite gold answers to match OKF output. Measure inter-annotator agreement and re-run sensitivity analyses excluding disputed items.

## Small frozen pilot

**Proposed pilot:** 12–20 contributions drawn from SEND appeal rights, Microsoft 365 outage/correction and NHS digital capability/Palantir, spanning both Houses where available, plus at least four negative/adversarial cases. The pilot is for testing the *evaluation machinery*, not estimating population-wide precision/recall. Freeze official source IDs, digests, vocabulary, graph, extractor, search indexes and evaluation prompts; record inclusion/exclusion rationale. Use this pilot to test scoring reproducibility, reference-answer completeness, error taxonomy, cost instrumentation and cross-model vocabulary mapping. Do not use pilot outcomes to tune thresholds and then claim unbiased confirmation; reserve a separate held-out evaluation set.

## Maintenance and scaling

Replay an added sitting, a corrected passage, a renamed entity and an ontology version change. Measure time and provider cost to ingest, update, invalidate caches, preserve IDs and recover correct retrieval. Test across multiple AI models and varied consented/synthetic user expression styles, including speech transcripts and cross-turn references.

## Legal/security/accessibility gates

Issue [#5](https://github.com/chris-page-gov/okf-hansard/issues/5) is a rights-audit gate for affected full-text and redistribution modes; do not infer clearance from an API response or licence banner. Include threat-model and prompt-injection tests for MCP/WebMCP, plus accessible browsing and voice evidence delivery checks. Keep sensitive user context client-side unless explicitly authorised.

## Pre-run sign-off checklist

- [ ] Pin frozen source and build hashes; verify licensing/rights for the intended evidence-return mode.
- [ ] Agree thresholds, hypotheses and critical failure definitions *before* results are viewed.
- [ ] Verify independent reference answers and gold labels.
- [ ] Agree sample inclusion, blinding, model and cost instrumentation.
- [ ] Confirm all arms have matched eligible corpus coverage.
- [ ] Register pilot versus held-out evaluation separation.
- [ ] Run pilot and publish raw receipts, disagreements, limitations and failures.

No boxes are checked until the specified action has actually happened.
