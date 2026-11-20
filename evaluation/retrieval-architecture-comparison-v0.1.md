# Retrieval architecture comparison — v0.1

Status: experimental design, not measured results. 19 November 2026.

## Core hypothesis

A user's personal AI can retrieve and reason over parliamentary evidence through deterministic, source-linked OKF/MCP infrastructure **without the knowledge provider invoking an AI model for each question**. Test whether centrally provided semantic retrieval delivers enough additional relevant evidence to justify its recurring inference, infrastructure and operational costs. Do not presume the result.

## Experimental arms

| Arm | Retrieval path | Provider-side inference at query time |
|---|---|---|
| K — keyword baseline | Lexical search over the same indexed corpus | None |
| G — OKF graph | Controlled vocabulary, typed edges, provenance and deterministic traversal | None |
| M — deterministic MCP | Explicit read-only indexed search and official API retrieval | None |
| S — i.AI-style semantic retrieval | Query embedding + Qdrant nearest-neighbour search | Usually query embedding; confirm actual implementation |
| H — hybrid | Deterministic OKF first, semantic fallback triggered by declared insufficiency | Only when fallback occurs |

Keep graph and deterministic MCP distinct in instrumentation, but compare both against a common lexical baseline. A personal AI is the same model/version and prompt policy across arms when generating final answers. For *retrieval-only* evaluation, bypass answer generation entirely and submit fixed queries to each retrieval mechanism. Report model-mediated query rewriting separately.

## Controls and dataset

- Pin identical Hansard source records, dates, licences, updates and evaluation questions. Ensure every arm has access to the same eligible corpus, or report coverage-adjusted results and exclude unmatched coverage from paired comparisons.
- Freeze graph build, matching profile, semantic model and embeddings, vector-index parameters, MCP version, search parameters, model version, prompts and runtime environment.
- Use the nine persona questions plus paraphrases, implicit-semantic-link cases, exact-ID cases, ambiguous-name cases, historical/temporal cases and negative controls. Include the SEND appeal-right chain and Microsoft correction.
- Construct a blinded, adjudicated pool of relevant and non-relevant contribution IDs from independent official source retrieval, plus candidates from **all** arms to reduce pooling bias. Record relevance grade and evidence spans; sample additional unpooled documents to estimate missed recall.
- Record separate retrieval, relationship extraction/representation and final-answer phases. Semantic similarity is not by itself a verified historical relationship.

## Retrieval metrics

- Recall@5, @10 and @20; precision@5 and @10; MRR or nDCG@10 for graded relevance; citation/source-locator accuracy; temporal validity; coverage and abstention rates.
- For graph assertions: precision/recall of typed relations on an independently labelled sample; entity identity, predicate, direction, evidence span, time and legal status correctness. Report graph *construction* cost separately from query-time cost.
- Latency p50/p95, cold/warm performance, error rate, determinism/repeatability, storage footprint, network bytes and freshness/correction propagation.
- Provider-side AI calls, embedding tokens, model tokens, cache hit rate, query rewriting, energy/compute where measurable, cost per 1,000 queries and total cost of ownership. Include ingestion, indexing, updates, hosting, storage and operations. Record personal-AI inference separately; do not claim it is free, even when already covered by a subscription.
- i.AI's public README documents Azure OpenAI embeddings and Qdrant; this **does not establish** an LLM completion per query. Inspect actual query path and log calls before cost claims.

## Additive scoring (additional retrieval scorecard)

For each arm and each test query, award only evidenced atomic points:
1. Retrieves at least one adjudicated relevant passage in top 5 — **2**.
2. Retrieves all designated essential passages in top 10 — **3**.
3. Returns stable official contribution identifiers and resolvable source links — **2**.
4. Preserves correct date/House and source version — **2**.
5. Does not present lexical or vector similarity as verified semantic relationship — **3**.
6. Reports gaps/unsupported results and abstains appropriately — **2**.
7. Returns evidence without fabricated or unsupported citations — **3**.

Maximum **17 points per query**, conditional on applicable criteria; record earned/eligible and failures. Do not combine with the existing 246-point maximum without revising its denominator and version. Cost, latency, precision/recall and critical failures are **separate quantitative measures**, not converted into arbitrary points.

## Cost accounting

Use measured calls and prices effective on the test date, rather than assumed rates. Compute:
- Provider query cost = query embeddings + any server-side LLM calls + amortised query-serving infrastructure.
- Lifecycle cost = corpus embedding/build + graph extraction/build + storage + updates + query costs + operations.
- Break-even by query volume and update frequency; report scenarios with and without shared fixed infrastructure.
- Personal AI cost = separately measured/estimated client-side inference, never hidden or counted twice.

## Decision rules

No single winner based solely on composite points. Compare retrieval relevance and coverage first, then reliability/provenance and total cost at explicit workload volumes. Report Pareto trade-offs and confidence intervals for repeated model-dependent trials. A hybrid must demonstrate incremental recall or quality against its additional expense.

## References

- https://github.com/i-dot-ai/parliament-mcp
- https://github.com/chris-page-gov/okf-hansard
- https://github.com/chris-page-gov/okf-hansard/pull/4
