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

The reporting compares work per trial and per fully supported answer. The publisher serves fixed public files once per acquisition. Local inference and hardware use still have a cost. This experiment measures time, bytes and token counts. A claim about total cost at scale needs data from the target workload and deployment.
