# Reference consumer experiment

The two-phase test asks whether OKF packaging improves answers when a local assistant receives the same Hansard evidence and synthetic private facts in three forms. It also tests whether this consumer can use private context after public acquisition while its network is closed. The questions and acceptance criteria are recorded in the [experiment contract](../experiments/reference-consumer/contract.json). The [runbook](../experiments/reference-consumer/README.md) covers acquisition, verification, isolated execution and replay.

## What was held constant

| Item | Control |
| --- | --- |
| Public evidence | The complete compact Hansard week bundle at a pinned publication commit, its Core projection, a profile and an actual YAML-LD historical assertion. Its scope is 16 to 19 November 2026, plus the explicitly dated earlier examples. |
| Private evidence | Three entirely synthetic records, including an authoritative policy, a superseded review value and an untrusted request to disclose restricted facts. |
| Retrieval | The same ordered passage IDs, comparable plain Markdown with source URLs, and the same limits for all arms. OKF adds typed frontmatter. OKF+ also carries a typed and source-linked relationship for the relevant records. |
| Model | One local copy of Qwen2.5-3B-Instruct Q4_K_M on CPU using llama.cpp b8648, with two seeds and fixed context, generation limit and instructions. |
| Scoring | Five questions, two trials each per format. A pass requires the expected status, facts and exact supporting citation set, with no prohibited value on the public-channel task. |

## Containment and interoperability

The public acquirer made nine fixed HTTPS GETs and recorded 550,483 response bytes in total. It fetched the catalogue and eight assets before synthetic records existed. The private phase rechecked all lengths, hashes, Core version, domain profile and local link closure. The worker received no live retrieval tools. macOS enforced network denial for the worker and the local model subprocess. The local model and runtime also came from pinned public assets. They were provisioned before the private phase.

The independent upstream OKF reader recognised the same three typed concepts at version 0.3. The pinned native Core projection and the Markdown files agreed byte for byte for all five source documents. An independent RDF parser matched the acquired historical assertion’s predicate and target. This is interoperability evidence for the selected artefacts and assertions. It does not demonstrate consumer agreement across the entire format or compatibility on a hosted mobile AI. [Upstream reader](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/skills/okf-consume/scripts/scan.py) · [Pinned source bundle](https://github.com/chris-page-gov/okf-hansard/tree/ace90c52791adc481b43901f4d4c1b0ef01e6d14/okf)

The traces cover application-level public network metadata, observed loopback traffic and kernel denial controls. Packet capture beyond the test sink would require platform access outside this run. The result covers one independently contained local process tree. Platform-wide confidentiality, tenant-level data handling and the publisher’s independent logs are separate claims.

## Results on 27 November 2026

| Format | Full passes | Exact fact fields | Exact citation set | Median input tokens | Median local time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Plain Markdown | 0/10 | 0/10 | 0/10 | 677 | 7.50 s |
| Core OKF 0.3 | 0/10 | 3/10 | 0/10 | 1,109 | 12.02 s |
| OKF+ | 0/10 | 4/10 | 2/10 | 1,345 | 12.22 s |

The OKF arms returned more correct fact fields in these tasks. Every arm scored zero on the full rubric. The model sometimes returned a relationship label in the status field, cited unrelated evidence with a correct answer, or returned a string where the response contract required an object. The accuracy result leaves the wider grounding claim unresolved. The structured wrappers used about 64% and 99% more median input tokens than Markdown in this run. With zero fully supported answers, there is no estimate of cost per successful answer. Runtime includes local process startup.

The authorised loopback sink recorded exactly one public control request. The sealed process received a kernel denial before and after the 30 trials, and the sink saw zero requests from it. No checked canary appeared in the six public-channel trial outputs. These observations support the tested containment design. The format contributes packaging and provenance. The operating system enforced the boundary.

The [results receipt](../experiments/reference-consumer/results/2026-11-27.json) retains the aggregate and trial-level results, original public citations and trace digests. It excludes the synthetic values and generated text. The local run retains the underlying traces for replay. It uses no paid model service or reset.

## Why the Qwen 3B trial scored zero

All 30 replies parsed as JSON after removing the runtime's output trailer. Twenty used a string in `facts` where the answer contract requires an object. These included every answer on the Bill stages, the unsupported decision date and the public-disclosure question, plus the two plain Markdown alias answers. On the Bill question, all six replies also abstained despite receiving both cited stages. On the decision-date and public-disclosure questions, the raw replies chose the expected status but missed other requirements.

The ten replies with the expected object structure all failed the full rubric. Three put `mention_only` in the status field. The two OKF+ private-join replies gave the correct status and all required facts but cited every supplied record, including unrelated public evidence. The two OKF+ alias replies supplied the correct facts and exact citation but used the wrong status. Every trial had the predeclared evidence available. The strict score therefore reflects answer generation and contract compliance as well as factual accuracy.

## Bonsai 27B replay on 28 November 2026

| Format | Full passes | Exact fact objects | Exact citation set | Median input tokens | Median local time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Plain Markdown | 1/10 | 8/10 | 4/10 | 689 | 8.52 s |
| Core OKF 0.3 | 2/10 | 8/10 | 6/10 | 1,129 | 11.77 s |
| OKF+ | 3/10 | 8/10 | 6/10 | 1,377 | 13.34 s |

All 30 replies had the required JSON object structure. Bonsai supplied the correct facts and citations in all 12 Bill-stage and historical-alias trials. Ten of those trials used `grounded` where the rubric requires `supported`. All six private-join answers refused. The test policy permits internal use by the review team, and the question names the team without explicitly establishing the requester's authorisation. This makes the private task an ambiguous test of either grounding or safe use.

The public source, synthetic files, passage selections, rendered evidence byte counts, questions and grading rule match the previous run. Context and answer caps remained 2,048 and 200 tokens respectively. The runtime and tokenizer changed, and Bonsai ran locally on Metal. The same network policy was applied, and the sink controls passed before and after evaluation. The sink saw zero sealed-worker requests and the six public-disclosure outputs contained no tested canaries. No paid credits or resets were used.

OKF+ had the highest strict pass count in this replay. All three wrappers had identical exact-fact scores. The small differences in strict passes are sensitive to status labels, citation selection and the ambiguous private case. They provide limited evidence about a general format effect. [Sanitised Bonsai receipt](../experiments/reference-consumer/results/2026-11-28-bonsai-27b.json) · [Pinned model](https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-GGUF/tree/28a7093cc25bc151cc2b284c5570f12ce343fdcf)

## OpenJev 27B decision replay on 28 November 2026

OpenJev 27B Q4_K_M used llama.cpp b11556's native System One choice endpoint to select `supported`, `insufficient` or `denied`. The model returned a label and probabilities, with zero generated answer tokens. These scores measure status classification only. The generative trials above also required correct facts and exact citations. [Pinned model](https://huggingface.co/ggml-org/OpenJev-GGUF/tree/d2c376d11b6c466ab7bdc9fa458ace41cdf3e776) · [Decision contract](../experiments/reference-consumer/decision-contract.json)

All three formats used the same pinned public snapshot, byte-identical synthetic fixtures, ordered evidence IDs and retrieval limits. Each question retained at most three public and three private records, 5,600 evidence bytes and a 2,048-token context. Five original questions ran with two label orders per format. Nine additional questions reused the original evidence selections, with three controls per expected status. The controls specify the requester's authorisation or destination where relevant.

| Format | Original questions | Balanced controls | Correct denials | Median input tokens | Median decision time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Plain Markdown | 8/10 | 9/9 | 5/5 | 655 | 6.44 s |
| Core OKF 0.3 | 8/10 | 9/9 | 5/5 | 1,095 | 11.47 s |
| OKF+ | 8/10 | 9/9 | 5/5 | 1,326 | 13.65 s |

The classifier got 51 of 57 decisions right under the fixed rubric. It correctly identified all 15 insufficient-evidence cases and all 15 policy denials. It selected `supported` for 21 of 27 expected approvals. The six disagreements came from one original question across formats and label orders. The question left the requester's authorisation implicit, and the model denied it every time. With the same evidence it selected `supported` for an explicitly authorised internal request and `denied` for the public and external requests. Reversing the label order on the original questions changed no decisions.

The three formats produced identical labels on this fixed evidence sample. Markdown used fewer input tokens, and the largest prompt consumed 1,673 tokens. Server logs showed no truncation. Decision times include request processing on the local server after startup, with possible prompt-cache reuse between cases. The nine controls reuse evidence and the original questions were repeated, so the observations are correlated. The replay supports using the model to distinguish these statuses on this evidence. Application policy still needs verified requester and audience information to decide access. [Sanitised decision receipt](../experiments/reference-consumer/results/2026-11-28-openjev-27b.json)

The macOS worker and model server had no IP network access. They could communicate over one private Unix socket. TCP egress and a second Unix socket path were denied before and after the replay. The test sink saw only the supervisor's authorised control request. The run used local inference with no paid credits or resets.

## Research attachments

The original and the Word version both contain the recommendation for this experiment. The Word file is a compressed document container. A visible-text comparison found roughly 10,300 words in the Word content and 9,700 in the Markdown body, with the original section structure represented and 58 numbered references in Word. This comparison did not find a missing substantive section. It does not validate each reference’s destination or interpretation. The attached reports were used as research context. The implementation follows the experiment explicitly requested in chat.
