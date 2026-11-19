# Hansard OKF+ evaluation: personas and questions (v0.1)

Status: proposed baseline; no scores assigned. Evaluation date: 19 November 2026.

## Purpose and controls

Compare the existing GitHub Pages experience with a future Sites experience (including WebMCP/MCP where implemented). Hold the Hansard/OKF release, question wording, reference evidence and model configuration constant where feasible. Record interface and retrieval mode separately. A question's absence from the published index is a retrieval/coverage failure, not proof that the source graph lacks it.

Before scoring, pin the release commit, bundle SHA-256, coverage receipt, evaluation date, model/version, tool permissions and retrieval logs. Prepare an independently verified reference answer and exact official Hansard URLs for every question. Do not assume the questions' premises are correct. Distinguish primary-source evidence from graph-derived interpretation.

## Personas and user stories

### P1 — Parent or carer seeking SEND support
*As a parent, I need to understand the difference between current enforceable rights and proposed reforms so I can assess what parliamentary debate actually establishes.*

- **P1-Q1:** What did Nadia Whittome ask about parents' independent appeal rights on 16 November 2026, and what did the Minister actually answer?
- **P1-Q2:** Which appeal rights under the existing EHCP framework are in force, and which aspects of Individual Support Plans remain proposals? Cite primary legal and parliamentary sources; mark any external sources.
- **P1-Q3:** Which earlier parliamentary contributions specifically address SEND appeal rights, and how do their positions compare with the 16 November exchange?

### P2 — Parliamentary researcher tracing policy
*As a researcher, I need to reconstruct the provenance of a claim across parliamentary proceedings without conflating similar terminology with substantive agreement.*

- **P2-Q1:** Locate the exact 16 November contribution on SEND appeal rights and return its speaker, date, House, stable contribution identifier and source link.
- **P2-Q2:** Trace backwards from that contribution to earlier discussions of independent SEND appeal rights. For each link, identify the matching entity/predicate and quote or locate the supporting evidence span.
- **P2-Q3:** Which apparent historical links are only lexical mentions of SEND, EHCPs or appeals rather than evidence of the same legal question? Explain exclusions and coverage gaps.

### P3 — Citizen or journalist checking parliamentary events
*As a reader, I need an accurate, accessible account of proceedings with enough evidence to verify what was said and what was decided.*

- **P3-Q1:** What were the main subjects covered in both Houses on Monday 16 November 2026, and what is the completeness boundary of this summary?
- **P3-Q2:** What was said in the Commons about the Microsoft 365 outage on 16 November, by whom, and what was established versus merely asserted?
- **P3-Q3:** How does Monday's discussion of NHS digital capability connect to Tuesday's Palantir/Federated Data Platform debate? Distinguish explicit references from shared entity mentions.

## Test execution and evidence record

For every question, store: question ID; persona; reference answer; authoritative URLs and contribution IDs; OKF assertion IDs and evidence spans; expected minimum elements; run date; implementation; access mode (browser, direct bundle, WebMCP, MCP); model and prompt; retrieved evidence; final answer; errors; elapsed time; coverage warnings; assessor notes. Record whether the answer was produced from **OKF only**, **OKF plus official source lookup**, or **external research**.

Run each question against both implementations under matched conditions. Repeat variable model-driven trials, retaining raw outputs. Include at least one negative/control query (a non-existent contribution or unsupported inference) to test abstention. Do not award credit for plausible but unsupported answers.

## Scoring (each dimension 0–4, separately reported)

- **Correctness:** accuracy against independently verified source record.
- **Provenance:** exact, accessible citations and evidence spans supporting claims.
- **Completeness:** required answer elements and explicit limits.
- **Historical reasoning:** justified continuity and distinction between lexical and semantic links.
- **Usability:** task completion for the persona, with effort and accessibility observations.
- **Reliability/access:** repeatability, tool errors, latency and failure handling.

Anchors: **0** absent/incorrect; **1** largely unsupported; **2** partly correct with important gaps; **3** substantially correct with minor omissions; **4** complete and independently verifiable for that dimension. Mark **N/A** where a dimension is genuinely inapplicable and report denominators. Report all six dimension scores, not only a composite; any composite must state its weighting. Track retrieval failure, missing corpus coverage, unsupported inference and answer-generation error as distinct causes.

## Initial regression: historical SEND appeal rights

The published history UI at https://chris-page-gov.github.io/okf-hansard/history.html was observed on 19 November to use an index whose `days` contained only `2026-11-18`, although the pilot covers 16–18 November. Recheck against a pinned deployment before treating this as a persistent defect. The Monday anchor must be selectable, and its earlier links must be evaluated against source evidence rather than assumed from alias matching. See issue #3.

## Acceptance criteria

1. Nine questions have reference answers and verifiable official source locators before scores are finalised.
2. Baseline and Sites results share the same corpus version and evaluation definitions.
3. Evidence retrieval and answer synthesis are scored distinctly; missing access is not silently replaced with web research.
4. All historical assertions are supported by explicit passages or labelled as candidate lexical matches.
5. Results report coverage gaps, abstentions and failure categories alongside scores.
