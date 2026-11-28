# GTM Hansard

Explore what the UK Parliament said, follow related material over time and bring your own AI to the evidence. The full November collection is the main entry point. The original week remains a set of guided examples.

| Start here | Guide |
| --- | --- |
| Ask questions on your phone | [Run the full voice demonstration](docs/mobile-demonstration.md) · [Open the finder](https://chris-page-gov.github.io/okf-hansard/november/ask.html) |
| Learn Hansard and OKF 0.3 | [Beginner’s guide to Parliament, the data and how to read it](docs/learn-hansard-okf.md) |
| Inspect the full collection | [Coverage, sittings and timeline](https://chris-page-gov.github.io/okf-hansard/november/) · [Full graph descriptor](https://chris-page-gov.github.io/okf-hansard/november/graph/okf-explorer.json) |
| Connect an AI client | [Read OKF+ skill](skills/read-okf-plus/SKILL.md) · [Retrieval contract](profile/voice-retrieval.json) · [Repeatable client tests](docs/voice-acceptance.md) |
| Maintain or reuse the project | [Architecture, algorithms, vocabulary and zero-token publishing](docs/maintainer-guide.md) · [Discovery and specifications](docs/okf-discovery.md) |
| Explore how the project works | [Optional contributor tour](https://chris-page-gov.github.io/okf-hansard/contributor-tour.html) · [Software and data licences](NOTICE.md) |


For the full capture, history and voice entry point, open the [Hansard collection](https://chris-page-gov.github.io/okf-hansard/november/hansard.json) or [ask your AI about Hansard](https://chris-page-gov.github.io/okf-hansard/november/ask.html). The week examples are guided views into the project. See [voice and cross-client tests](docs/voice-acceptance.md) for connection setup, limits and repeatable checks.

For a phone assistant that can read GitHub, open [the Markdown evidence index on main](HANSARD-EVIDENCE.md). It gives the verified date range, selected passages and exact Hansard links in one file. The scheduled publisher refreshes it through a checked pull request after validating the capture.

The guided week covers Westminster Hansard from 16 to 19 November 2026, with a rolling index of earlier contributions that share a person, office, place, organisation, programme, legislative instrument or subject. The November companion adds sittings as they are verified.

The current producer candidate is version 0.3.0 and declares OKF core 0.3. The
Hansard domain profile is versioned separately from core and from the inherited
Bundle Wiki structures. Historical release assets keep their original identity.

The [two-phase reference consumer experiment](docs/reference-consumer-experiment.md) compares plain Markdown, OKF 0.3 and OKF+ with matched evidence and a network-denied local model.

## Public snapshot

Start with the Railways Bill and follow its stages from the Commons to the Lords. The companion also covers Palantir and the NHS and the Commons statement on the Microsoft 365 outage. [Use Hansard with AI](https://chris-page-gov.github.io/okf-hansard/use-with-ai.html) · [Railways Bill companion](https://chris-page-gov.github.io/okf-hansard/demo.html?example=railways-bill) · [November in Parliament](https://chris-page-gov.github.io/okf-hansard/november/)

Use the [beginner’s guide](https://chris-page-gov.github.io/okf-hansard/beginners.html) to follow a contribution and check its source. The [methodology and prompts](https://chris-page-gov.github.io/okf-hansard/methodology.html) explain the collection, matching rules and Foundry templates.

The public snapshot contains derived records, source links and a worked history example. The rolling archive database and raw captures are local inputs.

The public companion and published history work without the SSD. See the [Voice and storage matrix](docs/voice-and-visual-ui.md#voice-and-storage) for the web and local MCP options.

Use the [secure briefing connector](docs/secure-briefing.md) to query a signed-in person's configured portfolio from a phone assistant that supports remote MCP.

## Open a local build

- Open the full graph through the companion's Explorer link. Its sharded descriptor, `graph/okf-explorer.json`, loads bounded record and relationship files. The complete Core source-path inventory and non-record Markdown remain in the plain JSON sibling `graph/core-source-binding.json`; the descriptor binds its exact bytes and digest, and the publication checksum catalogue covers it. The deployed Reader's 16 MiB descriptor limit remains in force. The [intermediate JSON](releases/current/okf-bundle.json) remains available for compatible local workflows; larger captures can exceed the Reader's single-file transfer limit.
- Read [the YAML-LD graph](releases/current/okf-bundle.yamlld) or start with the [portable Markdown index](releases/current/markdown/index.md).
- Check the [capture and build receipt](releases/current/receipt.json) and [rolling history coverage](releases/history-progress.json).
- Read the [international comparison](docs/international-models.md), [domain profile](profile/domain.yaml) and [voice and visual UI study](docs/voice-and-visual-ui.md).
- The week and November stagers each generate separate compact-core and full-graph visual walkthroughs. Each has its own source-bound question, qualified answer and negative controls. Compact answers remain within their own evidence scope.

The pilot comprises all text-bearing API contribution items observed in the published section trees at the cut-off. That includes some procedural passages, written statements and petitions. The receipt counts omitted layout-only items, timestamps and separately represented divisions. It records source availability at capture time.

## Trace earlier mentions

Run from the repository root with Python 3.12, uv 0.13.4 and the locked environment.
The project rejects other uv versions before running a command. This patched
version removes the compromised emSign root described in
[GHSA-hq85-5cpj-mr62](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62).

    export UV_CACHE_DIR="$PWD/.work/uv-cache"
    uv sync --locked
    uv run --locked python scripts/query.py find "Palantir" --date 2026-11-17 --limit 5
    uv run --locked python scripts/query.py trace CONTRIBUTION_ROUTE --view
    uv run --locked python scripts/query.py trace CONTRIBUTION_ROUTE --entity ENTITY_ID --limit 25
    uv run --locked python scripts/roles.py "The Prime Minister" --as-of 2026-11-17 --kind office

Use the exact route and entity IDs returned by search and trace. For a selected entity, follow **next_offset** with the returned **context_id**. The query includes the on-disk archive extension when available and exposes the dates and gaps it can see. Historical counts describe literal matches within the fixed alias profile. Same-day matches in separate sections have unknown order. The response identifies targeted spoken-search supplements and their date coverage where a later capture adds a name to the pilot.

An exact retained locator identifies the API field. The source read tool compares the live value with the recorded digest and labels changes. The archive index retains references, evidence spans and hashes. Full historical responses are processed in memory. The initial capture is local scratch for replay.

## Use an AI client

Give a URL-capable assistant the small OKF 0.3 Markdown index and ask it to open one example. Attach the relevant Markdown file if the assistant works from files. Ask for the exact Hansard links, the graph and timeline, and which sources it could open. The static routes work without an account or the SSD. [Markdown index](https://chris-page-gov.github.io/okf-hansard/okf/index.md) · [Machine directory](https://chris-page-gov.github.io/okf-hansard/okf-public-access.json) · [Discovery and standards](docs/okf-discovery.md)

Start the read-only MCP stdio server with a verified November publication receipt. It implements the July 2026 revision and the beta MCP Skills extension, with a compatibility route for earlier clients. See [transport and setup](docs/voice-acceptance.md).

    uv run --locked python scripts/mcp_server.py --publication .work/november-2026/publication.json

The tools are **hansard_find**, **hansard_trace**, **hansard_roles_as_of**, **hansard_member_as_of** and **hansard_read_passage**. A source-linked passage returns its Member ID where available. The member tool returns effective representations, posts, memberships and party records as of the requested day from cached biographies or the Members API. The passage tool reads the official Hansard API. No AI API key or model calls are needed. A voice-enabled host can speak a short answer and pass the digest-bound view to a companion screen. See the [UI study](docs/voice-and-visual-ui.md) for host-specific support and limits.

## Extend the collection

Capture to a fresh directory. The archive uses Parliament’s calendars to avoid polling non-sitting dates. It hashes the matching profile, indexes one House and sitting at a time and reuses processed sittings on restart. The default index path is on ExtSSD-Data. Use another database path when changing the matching profile. The active release can bind an older index by retaining its exact profile. Each entity’s response states whether the extension applies.

The [pre-2007 archive runbook](docs/historic-archive-operations.md) gives the source checks, checkpoint location and commands to query, pause, resume or finish the separate collector.

    uv run --locked python scripts/capture.py .snapshots/CAPTURE_ID --from-date 2026-11-02 --to-date 2026-11-17
    uv run --locked python scripts/people.py --snapshot .snapshots/CAPTURE_ID --output .snapshots/PEOPLE_ID --first 2026-11-16 --last 2026-11-17
    uv run --locked python scripts/build.py --snapshot .snapshots/CAPTURE_ID --people .snapshots/PEOPLE_ID --out releases/RELEASE_ID --first 2026-11-16 --last 2026-11-17
    uv run --locked python scripts/passages.py --build .snapshots/CAPTURE_ID --release releases/RELEASE_ID

To add a published day, extend the capture and build end dates. Existing contributions retain source-based identifiers. Compare denominator totals, assertion evidence and profile hashes before treating a new snapshot as active.

For a deadline-bound historic run, set an explicit time-zone offset. Create **.work/pause-history** to request a safe stop between work units. Processed sittings remain queryable while the index grows.

    uv run --locked python scripts/archive.py \
      --profile releases/current/archive-analysis-profile.json \
      --database /Volumes/ExtSSD-Data/okf-hansard-cache/history-v1.sqlite \
      --report releases/history-progress.json \
      --before 2026-11-02 --deadline 2026-11-18T07:00:00+00:00

## Reuse a companion view or export older links

The read-only evidence response can carry a view descriptor. Save the JSON, then render its digest-checked table and bars locally. Use the archive exporter for a portable YAML-LD slice of older relations.

    uv run --locked python scripts/render_view.py EVIDENCE.json VIEW.html
    uv run --locked python scripts/export_history.py --from-date 2026-10-01 --to-date 2026-10-31 --entity palantir --out OCTOBER.yamlld

The extended archive uses the 569-entity matching profile from the first capture. The Tuesday refresh added entities to the pilot. Official spoken-search supplements use recorded membership, constituency representation and Bill stage dates to bound matches for new names and titles. Their coverage is shown beside each result.

From the Wednesday snapshot, the [earlier mentions view](https://chris-page-gov.github.io/okf-hansard/history.html) lists earlier Hansard links by contribution and entity. The backfill reuses compatible SSD archive matches and checks the remaining dates and entities with official spoken and written search, starting on 1 January 2007. Its coverage receipt records incomplete searches. The published entity files carry links and the local index retains response digests and matching spans.

The current weekly candidate reuses verified search records only through 1 November 2026. It has no matching frozen search results for 2–15 November, so the weekly finder does not cover that interval. The separate November bundle contains captured proceedings for those dates; this does not fill the weekly finder’s search gap.

Pass `--history-cache .work/history-cache` when preparing a refresh to reuse completed search windows and archive projections. The scheduled refresh carries forward completed results and checks newly encountered entities before staging the site.

Use `scripts/export_history.py --include-backfill --release PATH` with the usual date and entity options to export the archive and verified search evidence together as YAML-LD.

## Build the Pages snapshot

Run the staging command from the repository root against a verified local release. To regenerate the worked example, run the voice trial builder against the same release and archive first.

    uv run --locked python scripts/build_voice_trial.py
    uv run --locked python scripts/build_pages.py --out .work/pages-next

The Pages site publishes the root of the generated gh-pages branch. The build stages a fixed set of assets, validates the bundle digests and writes a public checksum catalogue. Compare the served files with the catalogue after deployment.

The [retained public-asset manifest](compatibility/public-assets/manifest.json)
preserves three small earlier URLs and their source digests. Historical archive
references keep their original version and verification status; they are not
added to the active 0.3 graph.

Use `scripts/prepare_demo_week.py --through YYYY-MM-DD --out .work/NEW-BUILD` to prepare an extended release against the local historical index. It reuses the cached sittings and Member biographies, checks both Houses and stages Pages only after verifying the full graph. When its JSON projection needs to be smaller, the week stays complete and earlier contributions are sampled. The full semantic graph is available as YAML-LD or as a gzip download.

The week's Explorer projection records the sitting date at day precision, with a separate `hansard_proceedings` field for the section title and one-based source item within that section. An individual contribution's `Timecode` is retained as supplied, with its source pointer and API URL. A time-zone-free value keeps its unrecorded zone. Published section markers come from `Timestamp` items and are attached to the section. A marker never supplies a time for an untimed contribution.

The small [curated summary file](profile/curated-summaries.json) contains editorial summaries of a speaker's position, keyed by the exact official contribution link. The build supplies a summary only when the link matches the captured record. The official link remains the source for the speech and its context.

The demonstration companion links to an Explorer Timeline containing the three worked examples and links for each verified sitting. An exact contribution link carries its verified timecode, nearby section markers and editorial summary where supplied. The Explorer also keeps day-only dates for records without an individual time. Open the full Explorer bundle from the homepage to browse all the week’s records.

The focused Graph link loads the selected record and its incident assertions from `graph/okf-explorer.json`. The route locator binds each incident set by assertion count and SHA-256. Each edge keeps its direction, endpoint labels, assertion identifier and evidence. The builder groups links for high-degree nodes into small shards and checks every route against Explorer's transfer, row and retained-text limits. The descriptor's versioned Core source binding points to a separate, hash-bound plain JSON file, keeping the descriptor within the pinned Reader transfer limit while retaining the complete source roster. The full JSON bundle remains available for the learning paths.

On 18 November 2026, a fresh Chrome 158 context opened Ian Murray's statement in 134 ms after transferring 380,338 bytes of corpus files over 12 requests. It rendered all 12 incident edges, showed the exact contribution link for a selected assertion, and loaded a new shard on refocus. The NHS graph exposed its 572 incident relationships in pages of 72. The previously published export transferred 60,453,211 bytes and took 23.6 seconds to reach its focused graph on the same local host. Both observations used a warmed application server and fresh browser contexts.

The published graph schemas are byte-for-byte copies of the [Explorer assertion contract](https://github.com/chris-page-gov/okf-explorer/blob/e57e2c2e056bce326033fa576c4aa278dc437eb2/profiles/bundle-wiki/v1/semantic-assertion.schema.json) and the [UK Legislation runtime row contract](https://github.com/chris-page-gov/okf-uk-legislation/blob/9830fde2d32052f10713298f16b8ab1e321b1928/whole-law/schemas/relationship-runtime-row.schema.json).

### November contribution views

For a larger date range, build with `--sharded-reader` and verify the release before staging it with `scripts/stage_contribution_views.py`. This stage needs the calendar-checked day receipts, the verified release, and the backfill manifest. Use a fresh output directory when restaging. The site serves the full YAML-LD graph as gzip and gives Explorer a digest-bound record and relationship locator. The intermediate JSON is an input to the sharded build.

The contribution timeline loads one day of contribution choices and the selected entity's dated matches. It opens within the captured month and loads SSD archive projections when the user chooses an earlier period. Speaker, recorded capacity and proceedings filters follow source record links in the captured month. Earlier name and topic matches use the declared alias profile. The coverage report records provisional days and unfinished searches.

`scripts/backfill.py` gives priority to entities from the latest selected sitting and saves each entity's results. Repeat the same command to reuse compatible results and completed search windows. Pass `--older-database` to the staging and YAML-LD export commands to include matches available in the pre-2007 index. The exporter streams the selected date and entity ranges from SQLite with source locators and assertion evidence.

The November publisher checks the official Commons and Lords calendars, caches each verified day, and retries incomplete searches before publishing. It puts the graph, contribution timeline and core YAML-LD under [November in Parliament](https://chris-page-gov.github.io/okf-hansard/november/). Historical YAML-LD downloads use GitHub Releases, with additions uploaded separately. The month and week publishers share a publication lock and the week refresh preserves the November directory.

The local publisher runs through the 30 November snapshot without model calls. It saves the latest verified deployment in `.work/november-2026/publication.json` and logs failures in `.work/november-2026/publication-errors.log`. The SSD is required for rebuilding archive projections. The published views use static files.

Before resuming historical collection for a saved November candidate, the publisher checks its original build receipt, OKF version and every declared artefact. A failed check leaves the saved attempt in place and stops before backfill or publication. See the [shared publication preflight guidance](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/okf-build-and-publication-methodology.md#check-release-evidence-compatibility-early).

Before replacing the November Pages directory, the publisher verifies the prepared site's identity against the through-date, selected release receipt, builder/profile inputs and exact checksum catalogue. It requires the compact Reader descriptor plus both full-graph and compact-core walkthroughs and their diagrams, and checks that each walkthrough binds to the matching current descriptor. A missing or stale identity, required file or digest causes a fresh staging attempt before publication.

Pass `--attempts-root` an existing directory on ExtSSD-Data to place new captures, verification outputs and staged Pages files on the SSD. The publication checkpoint and shared lock stay in the repository’s ignored working directory. A refresh that needs to stage a new release waits for the configured directory to be available.

## Source attribution

Built with OpenAI Codex. The retained build logs record the model and reasoning effort for each phase. The project owner set the scope and authorised publication.

Contains Parliamentary information licensed under the Open Parliament Licence v3.0 where applicable. Follow the official record for the words and context. The graph’s matches are experimental and carry their own provenance. [Licence and exclusions](https://www.parliament.uk/site-information/copyright/open-parliament-licence/)

Original project software is available under the [MIT Licence](LICENSE). See the [attribution notice](NOTICE.md) for the scope of the software and Parliamentary data licences.

## OKF standards and bundle discovery

Use the [central current and historical standards register](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/okf-standards.md) and [machine-readable register](https://raw.githubusercontent.com/chris-page-gov/okf-explorer/main/registry/okf-standards.json) for version-specific specifications and the public bundle catalogue.

Pull requests to `main` run the locked Python test suite and browser-script syntax checks. The required `okf-hansard-ci` check validates these results; it does not acquire source material or publish a release.

For each compact publication, use a clean, pinned Explorer checkout to run
`scripts/check_okf_03_source.py SITE/okf --require-0.3 --output SOURCE_REPORT --projection PROJECTION`
through Explorer's locked Python environment. Then run
`uv run --locked python scripts/check_core_projection.py --projection PROJECTION --site SITE --output PARITY_REPORT`
here. This independent comparison checks every typed concept, frontmatter,
body, source byte and core reference pair. Keep both reports outside `SITE`.

Replay each of the six manifests in `acceptance/` separately with
`pnpm --dir EXPLORER/apps/okf-explorer acceptance:bundle -- --bundle-root SITE --journeys MANIFEST --output REPORT --port PORT`.
Use the week or November site that matches the manifest. The canonical wrapper
builds the pinned Reader before running the journey and records its exact
revision and build identity. Keep that checkout idle during each invocation.
The two `large-pointer` manifests require Reader 0.9.0 or a later verified
revision containing its SVG hit-area correction.
Run the source, browser and public-file checks separately; passing one does
not establish the others.
