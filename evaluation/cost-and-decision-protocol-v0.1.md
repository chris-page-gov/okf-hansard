# Cost accounting and architecture decision protocol — v0.1

Status: methodology only; no measured cost or winning architecture claimed.

## Accounting boundaries

Separate **personal-AI inference** (question interpretation, concept selection, answer synthesis), **provider-side inference** (query embeddings, server LLMs, reranking), **one-time corpus preparation** (source capture, extraction, graph construction, document embeddings), **ongoing updates** (corrections, new sittings, vocabulary revisions), and **non-inference serving** (API requests, storage, Qdrant/graph/keyword indexes, bandwidth, monitoring and operations). Record direct prices at observation date and estimated staff/hosting assumptions distinctly. Existing subscriptions are not zero economic cost; disclose both marginal billed cost and resource consumption.

## Per-run instrumentation

Capture run ID, architecture, corpus revision, query, query length, client model and calls/tokens, provider model and calls/tokens, embedding calls and dimensions, cache status, request count, CPU/memory if observable, storage/transfer bytes, p50/p95 latency, retries, errors, source freshness, index update age and cost source. Measure cold and warm retrieval and cache effects. Confirm i.AI's actual deployed query path before claiming per-query inference cost: the public repository documents embeddings and Qdrant but not universal generative completion on every query.

## Cost formulas

For N queries and U update cycles over period T:

`TCO(T,N,U) = initial_capture + extraction_build + embedding_build + index_build + U*(update_processing + reindex + reembedding) + N*(provider_query_inference + non_inference_serving + allocated_client_inference) + hosting_fixed(T) + operations(T)`.

Also report provider-only TCO and marginal per-query cost; do not double-count shared client inference. Use measured cache-hit proportions and variable query lengths. Show break-even query volume under low, medium and high update rates with sensitivity to inference prices, graph construction cost and hosting utilisation. No assumed universal cost advantage.

## Comparison decisions

1. **Evidence sufficiency gate:** candidate must meet minimum independently adjudicated retrieval recall, precision, source-link integrity, temporal/legal status and correction handling for the task. Set thresholds before running tests.
2. **Safety/provenance gate:** no fabricated sources or unsupported legal relationships accepted as fully successful; report critical failures independently.
3. **Privacy gate:** personal context remains client-side absent explicit permission; record remote transfer.
4. **Operational gate:** compare latency, availability, maintainability, freshness and correction propagation at equal corpus coverage.
5. **Cost/benefit gate:** compare marginal relevance improvement per additional provider inference call/token and lifecycle cost at declared workload volumes. A hybrid must demonstrate incremental benefit.
6. **Ontology repair gate:** where relevant passages exist but are not representable or linked, assess vocabulary/graph repairs before attributing the miss to the retrieval interface.
7. **Decision output:** publish Pareto trade-offs rather than declaring a winner from a combined score. Record evidence, assumptions, dissent, confidence and next experiment.

## Controls

Compare keyword, deterministic graph, deterministic MCP, personal-AI vocabulary mapping, semantic retrieval and hybrid with identical source corpus, stable queries and a fixed personal-AI model where possible. If architecture intrinsically requires different coverage or model resources, document the mismatch and avoid unsupported head-to-head claims. Blind semantic relevance adjudicators to retrieval arm.

## Deliverables

A per-run cost ledger, reproducible benchmark manifest, measured retrieval metrics, confidence intervals for stochastic trials, break-even sensitivity table and an architecture decision record. None are yet populated; this document specifies their required content.
