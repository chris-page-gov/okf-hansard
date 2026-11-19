# Source-to-graph extraction benchmark — v0.1

Status: protocol only; no gold sample collected and no extraction scores measured.

## Goal

Evaluate whether the OKF correctly turns original Hansard text into entities, typed relationships and evidence-bearing assertions **before** evaluating retrieval or answer synthesis. A valid schema and many assertions do not prove semantic accuracy.

## Sampling and gold labels

Sample from Commons and Lords across 16–18 November 2026 and historical links, stratified by sitting, speaker, contribution type, entity frequency, policy topic, explicit/implicit relation, temporal complexity and correction status. Include SEND appeal rights, Microsoft outage/correction, NHS/Palantir and Railways Bill. Record inclusion probabilities and a reproducible random seed. Use a pilot of at least 30 passages to refine the annotation guide; set the final sample size using observed prevalence and desired confidence precision, not an arbitrary claim of representativeness.

For each passage independently annotate: contribution ID; exact text span and digest; entity surface form and canonical ID; entity type; candidate relationship subject/predicate/object; assertion modality (mentioned, asserted, questioned, proposed, enacted, denied, corrected); direction; time interval; confidence/ambiguity; supporting text span; whether the link is literal/alias or substantively semantic. Label 'not inferable' explicitly. Record source and adjudicator IDs.

## Adjudication

Two independent annotators work from official source text, blind to the originating extraction arm. Resolve disagreement with documented rationale; measure inter-annotator agreement for key labels. Do not force consensus when the evidence is genuinely ambiguous. Compare deterministic OKF extraction with optional model-assisted extraction only after the reference set is frozen. Model-assisted candidates must not be used uncritically as gold.

## Metrics

- Entity identification: span-level and canonical-ID precision, recall and F1; identity conflation.
- Relation extraction: typed subject/predicate/object precision, recall and F1; direction and temporal accuracy.
- Provenance: fraction of correct assertions with exact supporting span and resolvable official source locator.
- Ontology: unrepresentable gold concepts/relations, alias ambiguity, vocabulary coverage and class/predicate misuse.
- Critical errors: invented entities, false legal status, mistaken office-holder at date, unsupported continuity, correction ignored.
- Report per stratum and macro/micro averages, labelled denominators and uncertainty. Measure build-time compute/cost separately from query-time inference.

## Error taxonomy and root cause

Separate missed source passage, extraction failure, canonicalisation failure, vocabulary gap, relation typing error, unsupported inference, incorrect time/status, evidence-span error and graph export/index defect. Inspect at least one error from each populated category and propose repairs **after** the frozen baseline has been scored.

## Outputs

`gold-passages.jsonl`, `gold-entities.jsonl`, `gold-relations.jsonl`, `adjudication.csv`, `extraction-results.jsonl`, `metrics.json`, and a signed/hashed provenance receipt. These are proposed output names, not existing files. Protect sensitive annotation notes; source text remains subject to Parliamentary licence and provenance requirements.

## Acceptance

No extraction-quality score is final without a pinned corpus, adjudicated labels, evidence spans, denominator, reproducible extraction run and error analysis. This benchmark feeds GRAPH-Q1–4 and the architecture decision protocol.
