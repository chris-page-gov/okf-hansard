# Maintain and publish Hansard

The repository keeps the rules, vocabulary, schemas, presentation templates and tests. A publication is a generated snapshot of official material. Python, SQLite and Git handle collection through release. An AI may help write or review code and may later consume evidence, but the scheduled job has no model invocation, prompt, inference credentials or token use. It still uses network requests, CPU, disk, the GitHub API and GitHub Actions. Measure elapsed time and transferred bytes separately from AI usage. [Repository commands](../README.md)

## Read the repository

| Area | Responsibility |
| --- | --- |
| [Publication contract](../okf.publication.json) and [semantic handoff](../okf.semantic.json) | Declare the source, generated projections, version, rights and validation entry points. |
| [Domain profile](../profile/domain.yaml), [vocabulary](../profile/vocabulary.yaml) and [curated summaries](../profile/curated-summaries.json) | Author the parliamentary scope, categories, source links and editorial content. Keep code, profile and documentation in step. |
| [Source capture](../scripts/capture.py), [refresh](../scripts/refresh.py), [Member biographies](../scripts/people.py) and [source model](../scripts/model.py) | Acquire official records, parse text, derive source IDs and load reference identities. |
| [Build](../scripts/build.py), [Core projection](../scripts/okf_core.py) and [graph builder](../scripts/build_explorer_graph.py) | Generate typed Markdown, relationship assertions, a JSON projection and a sharded graph. |
| [History lookup](../scripts/query.py), [historical search](../scripts/backfill.py), [archive collector](../scripts/archive.py) and [older archive](../scripts/historic_archive.py) | Build and read scoped dated indexes. Retain unambiguous terms, pointers, hashes, bounds and unresolved failures. |
| [Verification](../scripts/verify.py), [Core parity](../scripts/check_core_projection.py), [complete source audit](../scripts/audit_full_source.py) and [public bytes](../scripts/verify_public.py) | Check output against source, the declared format, consumer needs and deployed bytes. |
| [Staging](../scripts/stage_contribution_views.py), [November publisher](../scripts/publish_november.py) and [GitHub evidence index](../scripts/evidence_index.py) | Form the public collection, preserve compatibility URLs, synchronise the small index and publish verified assets. |
| [Voice contract](../profile/voice-retrieval.json), [reader skill](../skills/read-okf-plus/SKILL.md), [MCP server](../scripts/mcp_server.py) and [acceptance runner](../scripts/check_voice_clients.py) | Give different AI hosts a single evidence workflow. Test deterministic retrieval separately from assisted answers. |

## How a sitting gets published

1. **Choose the date and check the denominator.** The calendar says whether each House sat. `publish_november.py` works back through the first unprocessed November date, uses Europe/London boundaries and retries provisional dates. `refresh.py` creates a fresh capture, verifies retained files against their digests and reuses matching files. For each House/date, `capture_day` in `capture.py` reads the advertised sections and follows the section trees and root debates. The capture retains an error for any advertised source it could not read. Calendar-listed sittings require a complete tree; a confirmed non-sitting is recorded as such.
2. **Parse and assemble a release.** The source model reads the captured sections and their ordered items. Text-bearing contributions contribute to the count. Standalone markup, timestamp markers and divisions are accounted for in the receipt according to their types. Native IDs and the source section preserve the identity of a contribution across builds. The renderer emits dates and preserves a timecode only where the contribution has one, with its source precision. Member and Bill directory entries supply identifiers. Dated appointment records supply evidence for a specific date.
3. **Validate before expensive work.** `build.py` creates the release artefacts and writes hashes to its receipt. `verify.py` checks hashes, source fields and spans, graph integrity and OKF Core. The November publisher rechecks the original receipt and declared artefacts when resuming a cached candidate. Inspect the producer verification report before retrying a source-value mismatch. A PR check exercises code; the verified capture and the served files each require their own proof.
4. **Fill the historical lookup.** `backfill.py` identifies the captured entities for the selected days and prioritises recent ones. It reads the compatible on-disk index when suitable and calls the official spoken and written search endpoints for the required windows. The search can split high-volume ranges and sufficiently long timed-out ranges and validates stable totals and unique item IDs across pages. Each returned text passes the same literal matcher. A successful cached window uses the key, term, dates, section and effective profile digest. The publisher waits for unresolved configured searches before publishing a new verified capture.
5. **Stage and bind the outputs.** `stage_contribution_views.py` produces the date and concept indexes, the full Explorer descriptor, a compact core teaching example, YAML-LD and the phone pages. Bytes for the full Core Markdown source are retained in bounded record shards. A separate source-binding manifest binds their paths and digests. The snapshot ID binds the graph identity, coverage and history index. The prepared-site identity adds the release receipt, builder inputs, profile and checksum catalogue. Scripts, public templates and skill files participate in invalidating stale staged output.
6. **Publish with proof.** The publisher attempts the small evidence index update on protected main via a checked PR. An index failure can be retried independently. Under the local publication lock, the Pages publisher fetches the current `gh-pages` head, compares the candidate's coverage and observation with the same public scope, and forecasts the size of the combined site. It checks the week catalogue and required public entry points before changing the checkout. Week and November each retain the other's files. After checking served hashes, the publisher replaces its receipt only if GitHub still reports the verified commit as the branch head. If another publisher advances the branch, the earlier verifier leaves the receipt in place. A published URL can outlive the local SSD or staging checkout.

Determinism means the same fixed source and vocabulary inputs give the same selected IDs, matches, source hashes and assertion structure. Intake times, monitoring timestamps and the identity of a later release can still change. Stable sort keys, hash-bound artefacts and explicit source windows make the process reproducible and let an operator resume only the unfinished work. Saving a successful search window avoids calling Parliament again. Graph shards and timeline date indexes let a reader load just the selected record and its links. Plain JSON mention lists and day files omit indentation to reduce transfer while remaining directly readable by JSON clients. Downloads for bulk reuse can be larger. [Scope and published formats](okf-discovery.md)

## Maintain the vocabulary and matching algorithm

Each curated vocabulary row has a stable ID, type, preferred label, source URL where supplied, and aliases. An alias is an alternative term with the same intended meaning in the capture. Members, constituencies and Bills also come from captured Parliament directories using source IDs. Dated official posts and representations are separate from printed speaker text. Use the [Parliament Member lookup](https://members.parliament.uk/) to check identities and the [Parliament Bills service](https://bills.parliament.uk/) for legislation.

The matcher tokenises text and case-folds it for lookup, storing the exact text span for verification. Candidate sequences are indexed by first token. At each position the longest admissible match wins, with a control to avoid matching across configured breaks. A single-token constituency needs parliamentary context such as “Member for”. Some short uppercase aliases require exact uppercase spelling. Competing keys and configured exclusions remove ambiguous candidates. Historical search can send a shorter equivalent contained alias to Parliament, then verifies the complete local match against the captured text. A role resolver uses dated assignments and returns evidence rather than guessing from the label.

When changing the vocabulary:

1. Keep the ID stable for the same concept. Supply an authoritative source and explicit aliases. Give homonyms distinct IDs and review competing phrases.
2. Check strong and weak examples. Include a sentence that should match, a shared word that should stay ambiguous and any capitalisation or constituency edge case.
3. Regenerate the analysis profile. Use a compatible archive database or rebuild against the appropriate profile. Keep older profile and index identities in historical artefacts.
4. Verify both the new relationship and its exact span and source. Inspect exclusions, the effect on alias coverage, changed counts and the graph and timeline before publishing.

An **inverted index** maps an entity or term to a list of matching records. This list is often called a postings list. The browser and MCP use these lists for chronological mention retrieval. A captured full-text query uses SQLite FTS5, a searchable local text index. It matches normalised search tokens with an AND query and returns a bounded result page with text snippets, source anchors and dates. A search result is a textual match. Read the contribution and surrounding debate to determine its meaning.

## Run, recover and check

Run the locked project toolchain with Python 3.12 and uv 0.13.4. Run from the repo root so paths resolve as shown. The **test** command uses fixtures and does not publish anything.

```sh
PYTHONPATH=scripts uv run --locked python -m unittest discover -s tests
```

The **publish** command writes the scoped publication state and, for verified outputs, can push the Pages branch and open or update the protected index PR. The production invocation needs the configured local state, read/write access to the SSD staging directory, working Parliament network access, a Pages checkout and the authorised GitHub CLI account.

```sh
uv run --locked python scripts/publish_november.py \
  --attempts-root /Volumes/ExtSSD-Data/okf-hansard-cache/november-publication-attempts
```

The default publisher tracks dates through 30 November 2026. Scheduling is external to the repository. GitHub CI validates code. It does not run the local daily source acquisition. Check the deployed host's own scheduler and logs for an actual run. An unchanged observed date may retry its evidence index without restaging. A prepared attempt can be reused if its source evidence passes the preflight. A missing or changed stage identity causes restaging; a failed release preflight needs operator diagnosis.

- Inspect `.work/november-2026/publication-errors.log` and `publication.log`. Find the relevant prepared attempt and its capture, source receipt and `release/verification.json` before retrying.
- Read `.work/november-2026/publication.json` for the active date and Pages commit. For previous attempts, retain input hashes, error details and any resumable windows. Check the live `coverage.json` and `hansard.json` agree and open a source anchor and graph for the claimed day.
- Keep the SSD connected during collection, indexing or publishing when the inputs or scratch directories are there. Static Pages, GitHub Markdown and pasted evidence need no SSD. A local MCP process may still read the SSD-backed capture or archive when serving exact passages or building its full-text search index.
- For deeper history or known historical source gaps, use the older archive runbook. A first incomplete source read records a retryable gap. Repeat failures keep any previously retained matches. A complete repeat replaces the sitting's matches in one transaction. A sitting listed by Parliament's calendar stays open for retry when the section index is empty. The retry also reopens older terminal empty records when a cached calendar confirms the sitting. A processed range, zero open gaps within that range and a completed alias search describe different evidence. [Pre-2007 archive operations](historic-archive-operations.md)

## Trust boundaries

The public pages and skill contain evidence and instructions for using it. The skill exports only its declared Markdown files through an allowlist and binds each file by digest. It ships no code or credentials. The server listens on loopback. An operator needs an approved HTTPS deployment and the relevant host permissions for mobile MCP. Text from a source may contain apparent instructions and must remain evidence.

A phone assistant can select public topics from context it already has. Restrict outbound public tool arguments to the needed terms, dates and source scope. Never submit a private portfolio description as a public search query. The separate signed-in briefing validates OAuth tokens and maps the verified subject to authorised dated topics. Its output belongs to that account. [Protected briefing](secure-briefing.md) · [Mobile routes and user checks](mobile-demonstration.md)
