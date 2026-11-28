# Finding Hansard evidence in a phone-style conversation

**Microsoft E5 helped when speakers’ names were left out.** On eight fresh conversational questions, adding E5 to SQLite search found the complete reference passage for 5 questions, compared with 3 for word search alone. With the same local models deciding and writing, 5 hybrid answers and 3 word-search answers passed the full fact-and-citation check.

On the original 21 questions, often rich in names and institutional clues, both systems produced **17 fully correct cited answers**. The faster word search retrieved the complete reference evidence for 20 questions, and the hybrid found it for 19. For this Hansard collection, keep word search as the baseline for precise look-ups. The evidence supports trying hybrid search for loosely worded conversation and checking that the delivered passage includes the whole answer.

## Results at a glance

| Question set | All sources found, FTS5 | All sources found, hybrid | Full answers, FTS5 | Full answers, hybrid |
|---|---:|---:|---:|---:|
| Original, 21 questions | 20/21 | 19/21 | 17/21 | 17/21 |
| Conversational follow-up, 8 questions | 3/8 | 5/8 | 3/8 | 5/8 |

“All sources found” requires the supporting words inside the delivered excerpt. A link to the correct speech can still leave the answer outside the evidence window. A “full answer” also requires the expected answer status, facts and exact citations. The follow-up was designed after seeing the first search results and was frozen before running its own searches. It is reported separately.

**What was searched.** The pinned release contains **20,900 contributions**, 15,125 from the Commons and 5,775 from the Lords, on **18 sitting dates from 2 to 27 November 2026**. Both engines indexed all 49,919 passages derived from those contributions. The official-source capture files were verified against their checksums. The local coverage, graph descriptor and history directory also matched the public files at the pinned Git revision. Earlier historical mentions and later sittings fall outside this test. [Published coverage](https://raw.githubusercontent.com/chris-page-gov/okf-hansard/41a340e06ec02b7d5d4d5802e893534697328d32/november/coverage.json) · [Capture counts by date and House](capture.json)

## What changed for a reader

- **A colloquial question found the right speaker.** When asked what proportion of people “behind bars” had speech, language or communication needs, FTS5 returned related passages about therapy and children. The hybrid ranked Sonia Kumar’s Commons contribution first. She gave the figure as **over 60%**. [Read the exact contribution](https://hansard.parliament.uk/Commons/2026-11-10/debates/C620E704-423E-4AC6-BDD2-26DADF431CD5/TopicalQuestions#contribution-6127D140-8C81-4CD4-AA0F-B1BAD0B80118)
- **A debate title alone was insufficient.** When asked how many people knew they had HIV and were still missing treatment, FTS5 found relevant contributions in the correct debate. E5 brought Lord Cashman’s question containing **5,000** into second place. Both questions concern what was said in Parliament. [Read Lord Cashman’s question](https://hansard.parliament.uk/Lords/2026-11-12/debates/8615C30B-65EB-4F2F-B8AE-614CF6454880/HealthHIV#contribution-4058E90B-99CE-48DD-9D35-AFE53B1BABEE)
- **Both systems lost the end of a sentence.** They ranked the right driving agency statement first. The excerpt stopped at “the Libraries”, just before “of both Houses”. The scoring rule caught the missing detail. Selecting sentence boundaries or including the neighbouring passage within the same byte limit is a concrete next test. [Read the complete statement](https://hansard.parliament.uk/Commons/2026-11-16/debates/26111750000012/DriverandVehicleStandardsAgencyBusinessPlan2026-27#contribution-FD732141-EFCF-4EF2-9EEA-93B829B8BAFF)
- **Finding the passage did not settle the claim.** Both searches found Dame Meg Hillier’s forecast of about £100,000 in board savings. Both answering pipelines treated it as supporting a question about a later *audited* saving. The forecast does not establish that outcome. [Read the forecast](https://hansard.parliament.uk/Commons/2026-11-10/debates/4CE6842A-BA2A-4D7C-9FC3-68B972190018/FinancialServicesandMarketsBillLords#contribution-9057B4E3-3872-44BB-8A04-BD4038334E8C)

## How the comparison was kept fair

The primary questions were written for this experiment from a deterministic sample of source contributions. They included 15 single-source factual questions, two requiring two contributions, and four asking for a fact the reference material did not establish. The follow-up used new contributions and eight questions without speaker names. Seven have a supported answer, and one asks for an unpublished figure. “Unseen” means held out from this evaluation: the questions and source-based answers were frozen before their retrieval runs. The two hybrid gains in the follow-up were both changes from abstention to a correctly cited answer. These were typed, speech-like questions. The phone microphone, speech recognition and a hosted personal assistant were outside the experiment.

Only the search method varied within each pair. Both used the original pinned OpenJev and Bonsai models, the same prompts, one seed (11), the same question and answer fields, identical limits and local network isolation. Each got the evidence its own search selected. Model inputs used one plain-text format throughout. The test bundled related evidence from the same publication, so the scores compare search methods across the capture and provide no independent ranking of Markdown, core OKF and OKF+.

| Set and search | Reference passages delivered | Strict answers on answerable questions | Correct status on insufficient questions | Strict answers on insufficient questions | Median search time |
|---|---:|---:|---:|---:|---:|
| Original · FTS5 | 22/23 | 15/17 | 3/4 | 2/4 | 38.5 ms |
| Original · FTS5 + E5 | 21/23 | 15/17 | 3/4 | 2/4 | 69.2 ms |
| Conversational · FTS5 | 3/8 | 2/7 | 1/1 | 1/1 | 32.3 ms |
| Conversational · FTS5 + E5 | 5/8 | 4/7 | 1/1 | 1/1 | 49.0 ms |

The original set included 19 required source passages across 17 answerable questions, because two questions needed two sources. For the four questions with insufficient evidence, we also recorded the parliamentary passage that establishes what was missing. Each question counts once in the headline answer score.

## Costs and interpretation

The SQLite index took **1.23 seconds** to build and occupied **40.2 MiB**. E5 added **87.6 seconds** of model loading and passage encoding, a **73.1 MiB** vector file, and **127.3 MiB** of model weights. Both methods used the same Mac and SSD. These figures exclude environment installation and the shared corpus. Latencies in the table are elapsed search times on an already built index; the hybrid timing includes the lexical search. Query caching, device load and file caches can affect subsequent runs.

The strict rubric occasionally penalises a sound answer. Both systems returned “0.5% of their budgets” with the correct Welsh community-care contribution. The accepted answer list contained “0.5%”, so both missed the fixed wording check. In the reservoir question, FTS5 supplied a different speaker who also mentioned nine reservoirs. That supported the number but did not establish what Dan Jarvis, the person named in the question, had said. The original scores are retained. [Welsh community-care contribution](https://hansard.parliament.uk/Commons/2026-11-18/debates/B0C441D5-2A02-4E0E-AE5C-EBA274D2C35B/CommunityHospitalsandStep-downCare#contribution-E8AC7768-C58B-4B6B-B25F-2DA21D2EE425) · [Dan Jarvis’s contribution](https://hansard.parliament.uk/Commons/2026-11-19/debates/A4E27291-DF2D-4ECB-83BE-D976AED0FD4A/ElNi%C3%B1oNationalResilience#contribution-75EC630A-1400-4BFE-9BB6-83ABFD786F0F)

The sample is small and source-led. The initial questions often reuse distinctive names, which makes them favourable to word search. The follow-up probes a different style and was motivated by that first result. A different speech can also provide valid evidence. These features limit how far the observed advantage transfers to actual callers. For a deployment decision, the next useful comparison would use independently authored user questions, check alternative valid sources and measure success within the same three-passage cap.

## How a question becomes a cited answer

Imagine asking which profession was closest to having its qualifications recognised on both sides of the Channel. A search engine has to connect your wording to a particular speech. “Credentials accepted” and “mutual recognition of qualifications” can describe the same idea. Once the speeches arrive, the reader still has to identify the profession, check who made the remark and cite the correct contribution.

1. **Build the searchable collection.** Hansard is Parliament’s official written record. A *contribution* is one text-bearing item, such as an MP’s question or a ministerial reply. This experiment checked a frozen copy of the November collection against its publication receipt and counted each date and House. Longer contributions were split into passages of up to 96 words, with 16 words repeated at the boundary. This lets either method surface words from the middle of a speech. Both searched the same passage text, debate titles, speaker labels, dates and Houses.
2. **Find three pieces of evidence.** Each system chose up to three passages from different contributions. Every passage kept its Hansard source link. The models saw the actual retrieved words. The reference answers and source identifiers chosen by the evaluator stayed separate.
3. **Decide whether the question can be answered.** OpenJev read the evidence and chose one of three labels. *Supported* means the supplied material establishes the answer. *Insufficient* means it leaves a necessary fact open. *Denied* is for a handling policy that forbids an answer. This public-record test has no expected denials.
4. **Write and check the answer.** Bonsai received the decision and the same passages. It returned short facts and IDs for the passages it cited. A separate scoring program checked the status, accepted answer wording and exact citations against the frozen key. A correct number attributed to the wrong speaker can therefore fail.

## The names in the experiment

| Term | What it does here |
|---|---|
| **SQLite FTS5** | SQLite is a database that runs on the computer. FTS5 means *Full-Text Search 5*. It builds a word index so a question can be matched against thousands of passages. [SQLite documentation](https://www.sqlite.org/fts5.html) |
| **BM25** | The FTS5 rule used to order matches. It weighs the words in the question by how distinctive they are and takes passage length into account. We searched for any of the remaining terms after removing common question words and applied English word stemming. This is an experimental FTS5 baseline. The existing Hansard service has its own query policy. [SQLite ranking documentation](https://www.sqlite.org/fts5.html#the_bm25_function) |
| **Microsoft E5-small-v2** | A small English-language model from the Microsoft Research E5 work. It represents a question or passage as a list of 384 numbers, called an *embedding*. Similar numerical directions suggest related meaning. E5 ranked every passage using *cosine similarity*, a measure of that directional agreement. It did not write the answers. [Model and usage instructions](https://huggingface.co/intfloat/e5-small-v2) |
| **Reciprocal rank fusion** | The hybrid system combined the top 100 FTS5 passages and top 100 E5 passages. Each list awarded a score of 1/(60 + position), so the first-ranked passage received 1/61. Scores for the same passage were added. A passage ranked highly by both methods tends to rise. [Original research paper](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) |
| **OpenJev** | The local 27-billion-parameter model that chose the answer status. It read only the question and retrieved evidence. “27B” describes its approximate number of learned parameters. [Decision model](https://huggingface.co/ggml-org/OpenJev-GGUF/tree/d2c376d11b6c466ab7bdc9fa458ace41cdf3e776) |
| **Bonsai** | Ternary Bonsai 2.5 27B wrote each cited answer. The experiment reused the same compressed model weights and local llama.cpp software as the earlier comparison. *Quantisation* stores model weights more compactly so they take less memory. [Writer model](https://huggingface.co/prism-ml/Ternary-Bonsai-2.5-27B-GGUF/tree/28a7093cc25bc151cc2b284c5570f12ce343fdcf) |
| **Evidence budget and tokens** | A budget limits what reaches the answering models. The previous experiment allowed three public and three private records, 5,600 evidence bytes, 2,048 tokens of context per model and up to 200 tokens of generated answer. A *token* is a piece of text handled by a model. This experiment used public records only. |
| **OKF 0.3 and OKF+** | The Hansard bundle organises documents, source identities and relationships for reuse by different readers. Both methods drew from the same publication and used the same plain-text evidence rendering. This isolates the choice of search method. [Pinned publication directory](https://raw.githubusercontent.com/chris-page-gov/okf-hansard/41a340e06ec02b7d5d4d5802e893534697328d32/november/hansard.json) |
| **Network isolation** | macOS denied network access to the worker and its model processes. OpenJev used one permitted local Unix socket, a private communications path on the computer. Control requests checked that other connections were blocked. The public evidence, software and weights were acquired before sealed inference. |

**How to read the scores.** A source counts as *found* when one of the three supplied passages has the reference contribution ID and contains the words that establish the relevant point. *Complete retrieval* means all the question’s reference sources arrived. *Strict answer* adds the expected status, accepted fact values and exactly the supporting citations. For questions about a missing fact, the reference is the passage that establishes the limit, such as a minister saying that a date will be announced later. An equivalent answer from a different contribution can miss this strict score. Actual links and model answers are retained so readers can inspect such cases.

**What “local” means.** SQLite ran on the Mac. E5 used Apple’s Metal GPU support through PyTorch. The two answering models were loaded from GGUF files, a model format the local llama.cpp runtime can read. Search latency measures the look-up with indexes already built. Model time to decide and write an answer is a separate cost. The experiment used a local computer, SSD storage and electricity, with zero paid model credits.


## Evidence and replay

The verified primary search and the follow-up both used the original network-denial policy. The classifier and writer ran inside their own supervised worker with the same policy. The authorised control request reached its loopback sink, and none of the sealed workers did. These checks apply to the local process trees in this experiment. The tests used zero paid credits.

The trial records retain official links for all 174 supplied passage slots. Parliamentary material is attributed to UK Parliament. [Open Parliament Licence](https://www.parliament.uk/site-information/copyright/open-parliament-licence/)

[All 29 questions, actual model answers and Hansard citations](casebook.md) · [Exact passages shown for the original questions](retrieved-passages.json) · [Exact passages shown for the conversational questions](voice/retrieved-passages.json) · [Reproduction instructions](REPLAY.md) · [Primary trial scores](scores.json) · [Conversational trial scores](voice/scores.json) · [Primary verification](verification.json) · [Conversational verification](voice/verification.json)
