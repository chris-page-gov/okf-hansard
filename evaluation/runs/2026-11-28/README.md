# Hansard persona walkthroughs, 28 November 2026

Start with the [phone walkthrough](phone.md). The release covers 20,900 contributions from 2 to 27 November 2026. Its GitHub Pages commit is `41a340e06ec02b7d5d4d5802e893534697328d32`. Six downloaded files, including the compressed YAML-LD bundle, matched the local verified release byte for byte. [Release identifiers and SHA-256 values](release.json)

## Android Voice

The operator spoke the first parent question. Voice recognised Nadia Whittome, accurately described the question and Georgia Gould’s response and identified the lack of an explicit appeal commitment. Its written companion cited official Hansard. The phone used the **live homepage** for discovery and reported using **official Hansard web search** to answer. The reported date and contribution count matched the release. The phone supplied no bundle record or digest for this answer. Its earlier description of the homepage as pinned was incorrect.

The answer earned **9 of 15**. It omitted an explicit House and a verifiable contribution locator. The exported transcript contained a Hansard citation label whose destination could not be checked. The assessor verified the answer from the two official passages. The initial trial took 16.45 seconds from recorded turn start to completion. The remaining eight phone answers and the assisted SEND retry await handset evidence. Their phone scores are unassigned. [Phone transcript excerpt and criterion scores](android-P1-Q1.json) · [Primary-source references](primary-source-checks.md)

## Local comparison

All nine exact questions also ran once on Qwen2.5-3B-Instruct Q4_K_M on the Mac CPU, using selected evidence from the pinned bundle and linked primary sources. Each trial began with fresh context. The model received the question and its public evidence packet. It saw neither the scoring rubric nor the reference answers. The assessor selected the evidence in advance, so these results measure answering from supplied evidence. They give no measure of mobile usability or autonomous retrieval. [Inputs by question](questions.json) · [Evidence packets](evidence.json) · [Original answers and timings](local-answers.jsonl)

| Scenario | Android Voice | Local text | Possible |
|---|---:|---:|---:|
| P1-Q1 | 9 | 3 | 15 |
| P1-Q2 | Awaiting trial | 2 | 15 |
| P1-Q3 | Awaiting trial | 0 | 15 |
| P2-Q1 | Awaiting trial | 7 | 12 |
| P2-Q2 | Awaiting trial | 4 | 19 |
| P2-Q3 | Awaiting trial | 0 | 15 |
| P3-Q1 | Awaiting trial | 12 | 15 |
| P3-Q2 | Awaiting trial | 2 | 15 |
| P3-Q3 | Awaiting trial | 0 | 15 |

The parent questions earned **5/45** locally, the researcher questions **11/46** and the citizen or journalist questions **14/45**. The local total was **30/136 (22.1%)**. The local legal answer invented an Act title and overstated the absence of legal remedies. Those are two critical flags in one answer. The model also attributed the MP’s description of appeal rights to the minister in P1-Q1 and missed the official Microsoft corrections in P3-Q2. All 136 points belong to the existing answer-quality rubric. [Atomic local scores and reasons](local-scores.json) · [Rubric](../../additive-scoring-v0.2.md)

## What was verified

- The Parliament API returned Whittome’s supplementary immediately followed by Gould’s reply. The opening question from the same MP has a different identifier. The text of 15 selected November items matched the captured SHA-256 at their stable external identifiers. For eight, Parliament’s current numeric item ID differed from the captured numeric ID. Both are retained in the evidence ledger. A numerical locator alone would have missed unchanged text.
- The SEND comparison screened every one of the 37 earlier November concept rows using three specified search terms. Two contained those terms. A separate indexed May contribution was verified as a comparator in the Lords. Historical recall across Hansard remains unmeasured.
- The reference answers use official Hansard, revised legislation and the Department for Education consultation. The two revised XML sections identify 29 October 2026 as the document validity date and list 1 September 2014 as the latest section-specific version. The date-specific section 51 XML endpoint returned HTTP 500. Legal scope is confined to the English EHCP framework.
- A correct citation such as `[Q]` resolves through the supplied evidence packet. Malformed tokens such as `[ID]R` earn no citation points. Compound criteria need all elements. The date criterion requires a full date. A single Codex assessor applied the provisional rubric. No independent second grading or cross-model calibration was performed. [Reference answers by scenario](primary-source-checks.md)

## Reproduce the comparison

Run `python3 evaluation/runs/2026-11-28/verify.py` from the repository root. It checks the questions, individual prompt hashes, rubric rows and score arithmetic offline. The verifier’s `prompt` function reconstructs the exact UTF-8 input for each local trial.

The model file SHA-256 was `626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d`. The llama.cpp b8648 completion executable SHA-256 was `355a5b8c52d18a1ed92195b8ac468475637daa17da6eed6ca7bbce91f61ac438`. The successful trials used offline mode, `--device none -ngl 0`, four threads, 6,500 context tokens, a 384-token output cap, seed 42 and temperature zero. P2-Q2 reached the output cap. An earlier launch could not initialise Metal and a subsequent diagnostic produced empty output. Neither yielded a scored answer. Each successful CLI invocation loaded the model anew. No external model API was used.

[Phone questions](phone.md) · [Verified answers](primary-source-checks.md) · [Evaluation protocol](../../master-evaluation-protocol-v0.1.md)
