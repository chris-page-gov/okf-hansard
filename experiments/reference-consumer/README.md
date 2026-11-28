# Two-phase reference consumer

This experiment compares **plain Markdown**, **OKF 0.3** and **OKF+ with a Hansard relationship excerpt**. It uses the same local model, questions, public and synthetic evidence, selection rule, context limit and answer budget in every condition. Each question is repeated at two seeds. Run the two phases as separate commands.

## What the experiment measures

- The public inputs are the complete five-document **compact Hansard week bundle**, its independently readable Core projection and two supporting files. The pinned Hansard-domain profile and real YAML-LD historical example constitute the additional OKF+ input. This is a fixed task corpus with five extracted public evidence records. The whole November graph, every historical mention and live source freshness are outside the experiment.
- The consumer verifies every acquired asset, checks local links and matches all five source Markdown documents against the Core projection. It retains exact source anchors. It does not follow external evidence URLs while reasoning.
- It selects evidence once for each question using word overlap and a stable tie-break. The three arms receive identical evidence IDs, original excerpt text, source links and record order. The OKF arm wraps the records in typed frontmatter. The OKF+ arm also presents a compact relationship excerpt, derived from the actual acquired assertion when relevant. The public text in all arms already explains the same qualified relationship. This is a **matched-passage ablation**. Any benefit from fetching or ranking better passages needs a separate experiment.
- The five cases measure staged public evidence, a public/private join with a superseded draft, the qualification of an alias match, lack of evidence for a later decision and a forbidden public disclosure in the presence of an untrusted annex.
- All answers use evidence IDs. The report binds public IDs to exact Hansard URLs and checks the requested facts, status, exact citation set and prohibited synthetic markers. This is a predeclared exact rubric, with factual capsules derived from the pinned public artefacts.

## Phase A

Use Python 3.12 from the locked project environment. Acquire into a new public directory before creating the synthetic documents. Public requests are fixed HTTPS GETs at an immutable Git commit. The acquirer accepts neither an arbitrary URL nor a redirect. The catalogue commitment is pinned separately and each file has a verified length and SHA-256. It logs destination hostname, connected peer, pinned request path, response status and bytes.

```sh
uv run --locked python experiments/reference-consumer/acquire.py .work/reference-consumer/public
```

A run can reuse this verified public directory. The worker rechecks the file bytes and its acquisition receipt before creating synthetic private material. The files were acquired from an unchanging commit. Websites linked inside them can subsequently change.

## Phase B

Provision the model and executable as public inputs before running the private phase. Use [llama.cpp b8648 for Apple Silicon](https://github.com/ggml-org/llama.cpp/releases/tag/b8648) and [Qwen2.5-3B-Instruct Q4_K_M at the pinned revision](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/tree/af75b7aaf5bb163ce4c5dab4e6b84d844e96265d). Check the release archive digest in `contract.json` before extraction. The runner also checks the exact executable and weight file digests. The Apple Silicon run uses the CPU, a 2,048-token context, a 200-token generation cap, six threads and the same sampling settings for every trial.

```sh
uv run --locked python experiments/reference-consumer/evaluate.py \
  --public .work/reference-consumer/public \
  --output .work/reference-consumer/new-run \
  --binary .work/reference-consumer/runtime/llama-b8648/llama-completion \
  --weights .work/reference-consumer/model/qwen2.5-3b-instruct-q4_k_m.gguf
```

Run from a macOS session that permits `sandbox-exec`. The sandbox supervises the whole reasoning child process, including the local model, with `(deny network*)`. The outer supervisor makes one authorised public-positive request to a loopback test sink. The child tries the same destination without carrying any private text. Only a kernel denial permits the child to proceed. A second denial is checked after all trials. The sink trace must contain only the public-positive request. The local model has no web, tool or MCP interface in this run. No online model endpoint or paid service is used.

Three synthetic documents are created only after the denial, with one newly generated marker, an invented date and an invented threshold. The parent can read the aggregate result. It does not read the synthetic documents, prompts or raw responses. The model receives each prompt over local stdin. The macOS process needs its existing home directory for startup. No provider credentials or proxy environment variables are passed.

The network evidence combines the acquisition HTTPS journal, kernel-denied socket controls and the application trace at the only authorised test sink. Host-wide packet capture, external provider audit and live mobile behaviour are outside the run. The experiment covers its own process tree on this host. A future deployment needs its own independent containment test.

## Outputs and checks

- `report.json` records the run contract, executable and input hashes, source scope, per-case pass criteria, latency and input/output token counts. It omits model-generated text and private values.
- `network-audit.json` in the public directory and `sink-trace.json` in the run directory show the authorised connections and network controls. Keep them with the report when reproducing the experiment.
- `local-answers.jsonl` and `synthetic/` retain the details for local inspection. Store them under ignored `.work` directories with restricted permissions. The supplied documents remain read-only research inputs.

```sh
uv run --locked python -m unittest discover -s experiments/reference-consumer -v
```

## Replay with Bonsai 27B

The [Bonsai profile](model-bonsai-27b.json) pins PrismML's Ternary Bonsai 2.5 27B Q2_0 weights and the compatible Apple Silicon llama.cpp b11556 build. The model file is 7.67 GB. Keep it on a volume with sufficient free space, and verify its SHA-256 and the runtime archive hash before running. The runner checks the model and executable again. [Pinned model files](https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-GGUF/tree/28a7093cc25bc151cc2b284c5570f12ce343fdcf) · [Pinned runtime release](https://github.com/ggml-org/llama.cpp/releases/tag/b11556)

Use the same evaluation command with these additional options and the Bonsai executable and weights:

```sh
--model-profile experiments/reference-consumer/model-bonsai-27b.json \
--replay .work/reference-consumer/run-04
```

Supply a fresh output directory. The replay checks the previous receipt, checksums, policy and selected evidence for all 30 trials. It reads the earlier synthetic fixtures within the network-denied worker and verifies their exact bytes before reuse. The model profile changes the runtime, tokenizer and acceleration. It keeps the questions, system text, rubric, retrieved passages, byte budget, 2,048-token context, 200-token output cap, temperature and seeds. Bonsai uses Metal and its ChatML prefix with thinking disabled in all three arms. Compare latency and token counts across models with those runtime and tokenisation differences in mind.

## Test OpenJev as a decision model

The [decision contract](decision-contract.json) pins OpenJev 27B Q4_K_M and the Apple Silicon llama.cpp server. Provision its 19.4 GB text weights on a volume with sufficient free space. The runner validates the weights and executable digests and uses the official `/v1/systemone` endpoint. The model returns a distribution over the supplied status labels, with no generated text. [Pinned OpenJev weights](https://huggingface.co/ggml-org/OpenJev-GGUF/tree/d2c376d11b6c466ab7bdc9fa458ace41cdf3e776) · [Pinned endpoint documentation](https://github.com/ggml-org/llama.cpp/blob/b11556/tools/server/README.md#post-v1systemone-typesafe-compatible-system-one-api)

```sh
uv run --locked python experiments/reference-consumer/decide.py \
  --public .work/reference-consumer/public \
  --replay .work/reference-consumer/run-04 \
  --output .work/reference-consumer/new-decision-run \
  --binary .work/reference-consumer/runtime/llama-b11556/llama-server \
  --weights /Volumes/ExtSSD-Data/okf-hansard-cache/reference-consumer/OpenJev-Q4_K_M.gguf
```

Run from a macOS session that permits `sandbox-exec`. The supervisor and worker follow the original two-phase pattern. The server and client share one path in a private temporary directory over a Unix socket. TCP is denied. The worker checks TCP and another Unix socket path before opening private fixtures and after the model shuts down. The control sink must see only the supervisor's one positive request. The model process receives no provider credentials or network tools.

The decision replay uses the same public snapshot, byte-identical synthetic fixtures, ordered evidence IDs, rendered evidence sizes, 5,600-byte wrapper limit, and 2,048-token context as the generative benchmark. The five original questions are unchanged and run with two label orders in each format. The nine control questions reuse those same evidence selections and include three examples of each expected status. A private question names an authorised internal audience for one control and a public or external audience for paired controls. The original question with implicit authorisation is retained for comparison.

The receipt reports accuracy, a confusion matrix, policy-denial misses, cases incorrectly allowed, and label flips when the option order changes. These scores measure classification, while the generative benchmark scores complete answers and citations. The controls reuse evidence, so this small suite does not establish probability calibration or a production acceptance threshold.

## Run OpenJev and Bonsai together

Use the same verified public acquisition, earlier replay, OpenJev server and Bonsai completion executable. Keep both model files available for the duration of the test. OpenJev runs first. The runner shuts down its server before starting Bonsai to limit simultaneous memory use. The [hybrid contract](hybrid-contract.json) defines the synthetic request contexts and the answer rubric for the decision controls. It adds explicit request context to the private questions while preserving the original wording and exact scoring rubric.

```sh
uv run --locked python experiments/reference-consumer/hybrid.py \
  --public .work/reference-consumer/public \
  --replay .work/reference-consumer/run-04 \
  --output .work/reference-consumer/new-hybrid-run \
  --binary .work/reference-consumer/runtime/llama-b11556/llama-server \
  --weights /Volumes/ExtSSD-Data/okf-hansard-cache/reference-consumer/OpenJev-Q4_K_M.gguf \
  --writer-binary .work/reference-consumer/runtime/llama-b11556/llama-completion \
  --writer-weights /Volumes/ExtSSD-Data/okf-hansard-cache/reference-consumer/Ternary-Bonsai-2.5-27B-Q2_0.gguf
```

The replay covers the five original questions, two seeds and three formats, then adds nine controls in each format. OpenJev receives the original selection, with the same three public and three private record limits and 5,600-byte evidence cap. The runner changes only the request context and the answer-field instructions for the new controls. The worker limits Bonsai to the same 2,048-token context and 200 output tokens. Bonsai returns facts and citation IDs. The runner inserts the status selected by OpenJev and checks the final object against the expected label, facts and citation set. A writer response containing a status field fails validation.

The harness supplies synthetic authorisation outside the evidence. Its evidence gate grants factual private records to Bonsai only when the context explicitly establishes an internal reviewer and OpenJev has selected `supported`. Public, external and non-supported runs allow the public records and the handling policy. This applies even if OpenJev incorrectly approves a public request. This fixture models trusted authorisation metadata. A live application would have to establish it independently.

Both models run inside the same IP-denied macOS worker. The worker probes TCP denial and a second Unix socket path before inference, between models and after inference. Only OpenJev needs the permitted private Unix socket. Raw answers stay inside the restricted local run directory. The report contains scores, evidence IDs, exact public Hansard URLs and trace digests. It omits raw responses and synthetic facts.

The reporting compares work per trial and per fully supported answer. The publisher serves fixed public files once per acquisition. Local inference and hardware use still have a cost. This experiment measures time, bytes and token counts. A claim about total cost at scale needs data from the target workload and deployment.
