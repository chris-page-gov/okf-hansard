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

## Scoring (superseded by additive rubric)

**The following holistic 0–4 scheme is historical draft material and MUST NOT be used for baseline scoring.** The authoritative scoring specification is [additive-scoring-v0.2.md](additive-scoring-v0.2.md).

### Previous proposal (retained for review)

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


## API discovery and evidence escalation (additional evaluation requirement)

The OKF should publish a machine-readable **source-discovery contract**: authoritative service and endpoint references, accepted identifiers and parameters, operations, authentication/availability, licence, rate/error handling, source version and digest semantics, coverage bounds, and safe read-only escalation rules. Verify endpoint details against official documentation rather than assuming paths.

Evaluate separately: (a) discoverability of available source APIs from the OKF; (b) ability to choose graph, exact source read or API discovery; (c) correctness of identifier translation and returned evidence; (d) transparent abstention, failure and gap reporting; (e) source trust, freshness and corrections. The existing `hansard_find`, `hansard_trace`, `hansard_read_passage`, `hansard_member_as_of`, and `hansard_roles_as_of` are local MCP capabilities, **not** evidence of a remotely exposed general-purpose historical search endpoint.

**API test questions**
- **API-Q1:** From the OKF alone, which official service and supported operation should an agent use to retrieve the full source text of a known contribution?
- **API-Q2:** When the OKF has no evidence-backed SEND appeal-right history, can an agent discover a supported historical search route, record the query and coverage, and return source-linked results without treating them as confirmed semantic links?
- **API-Q3:** When a captured passage has been corrected, can the agent identify the current official text, report the mismatch and preserve the capture provenance?

## Graph and controlled-vocabulary/ontology fitness (additional evaluation requirement)

Evaluate the **semantic model itself**, independently of the site and AI interface. First establish intended competency questions and a reviewed gold sample of contributions/relations across Commons/Lords, time, people/roles, legislation, programmes and subjects. Test the graph against those questions, including the SEND appeal-right scenario.

**Graph checks:** source-to-node completeness; correct node identity and deduplication; direction and predicate meaning; evidence spans and assertion IDs; dated relations and change/correction handling; graph connectivity and relevant traversal paths; lexical versus semantic relationship distinction; false positives, false negatives, precision and recall on a labelled sample; ability to answer competency questions without unsupported leaps; deterministic regeneration and schema/SHACL or equivalent validation where appropriate.

**Vocabulary/ontology checks:** coverage of necessary concepts (e.g. statutory entitlement, EHCP, independent tribunal appeal, proposed Individual Support Plan, school-level accountability); clear class/predicate definitions and domain/range; stable identifiers; synonym and ambiguity handling; appropriate granularity; distinction between person, office and role-at-date; distinctions among mention, claim, proposal, enacted rule, correction and evidence; mapping to external standards only where justified; extensibility without breaking old identifiers.

**Graph test questions**
- **GRAPH-Q1:** Can the model represent and distinguish a parent’s existing statutory appeal right, a proposed support plan and a minister’s statement *about* either, without implying the proposal is law?
- **GRAPH-Q2:** For an earlier SEND contribution returned by traversal, what exact assertion, predicate, evidence span and temporal context justify its relevance? Is it merely an alias match?
- **GRAPH-Q3:** Can the graph represent that a later correction supersedes or qualifies a recorded statement while retaining the original capture and its source digest?
- **GRAPH-Q4:** What proportion of a stratified, manually adjudicated sample of relevant contributions and relationships is correctly modelled, and what important concepts or relations are missing?

**Reporting:** Maintain a separate graph/ontology scorecard and error taxonomy. Do not infer precision/recall from raw assertion counts; establish a labelled denominator. Report graph quality independently from API discoverability, retrieval quality, answer quality and usability. Document ontology gaps as potential changes to the domain profile and matching rules, not as unreviewed modifications to the frozen baseline.
