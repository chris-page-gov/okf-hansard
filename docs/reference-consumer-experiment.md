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

## Research attachments

The original and the Word version both contain the recommendation for this experiment. The Word file is a compressed document container. A visible-text comparison found roughly 10,300 words in the Word content and 9,700 in the Markdown body, with the original section structure represented and 58 numbered references in Word. This comparison did not find a missing substantive section. It does not validate each reference’s destination or interpretation. The attached reports were used as research context. The implementation follows the experiment explicitly requested in chat.
