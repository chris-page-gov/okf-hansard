# A week in Parliament

An experimental OKF+ bundle of Westminster Hansard for 16 and 17 November 2026, with a rolling index of earlier contributions that share an identified person, office, place, organisation, thing, legislative instrument or subject.

## Public snapshot

Start at [A week in Parliament](https://chris-page-gov.github.io/okf-hansard/) for the Explorer import and YAML-LD graph. The [demonstration companion](https://chris-page-gov.github.io/okf-hansard/demo.html) covers Microsoft 365, Palantir and the NHS, and the Railways Bill. The [plain-text evidence](https://chris-page-gov.github.io/okf-hansard/demo-evidence.md) gives chat and voice assistants the exact links.

Use the [beginner’s guide](https://chris-page-gov.github.io/okf-hansard/beginners.html) to follow a contribution and check its source. The [methodology and prompts](https://chris-page-gov.github.io/okf-hansard/methodology.html) explain the collection, matching rules and Foundry templates.

The public snapshot contains derived records, source links and a worked history example. The rolling archive database and raw captures are local inputs.

## Open a local build

- Load [the Explorer bundle](releases/current/okf-bundle.json) using **File** in OKF Explorer. The compact JSON retains the week and its linked earlier examples. The YAML-LD graph retains the full initial assertion evidence.
- Read [the YAML-LD graph](releases/current/okf-bundle.yamlld) or start with the [portable Markdown index](releases/current/markdown/index.md).
- Check the [capture and build receipt](releases/current/receipt.json) and [rolling history coverage](releases/history-progress.json).
- Read the [international comparison](docs/international-models.md), [domain profile](profile/domain.yaml) and [voice and visual UI study](docs/voice-and-visual-ui.md).

The pilot comprises all text-bearing API contribution items observed in the published section trees at the cut-off. That includes some procedural passages, written statements and petitions. The receipt counts omitted layout-only items, timestamps and separately represented divisions. It records source availability at capture time.

## Trace earlier mentions

Run from the repository root with Python 3.12 and the locked environment.

    export UV_CACHE_DIR="$PWD/.work/uv-cache"
    uv sync --locked
    uv run --locked python scripts/query.py find "Palantir" --date 2026-11-17 --limit 5
    uv run --locked python scripts/query.py trace CONTRIBUTION_ROUTE --view
    uv run --locked python scripts/query.py trace CONTRIBUTION_ROUTE --entity ENTITY_ID --limit 25
    uv run --locked python scripts/roles.py "The Prime Minister" --as-of 2026-11-17 --kind office

Use the exact route and entity IDs returned by search and trace. For a selected entity, follow **next_offset** with the returned **context_id**. The query includes the on-disk archive extension when available and exposes the dates and gaps it can see. Historical counts describe literal matches within the fixed alias profile. Same-day matches in separate sections have unknown order. The response identifies targeted spoken-search supplements and their date coverage where a later capture adds a name to the pilot.

An exact retained locator identifies the API field. The source read tool compares the live value with the recorded digest and labels changes. The archive index retains references, evidence spans and hashes. Full historical responses are processed in memory. The initial capture is local scratch for replay.

## Use an AI client

Start the read-only MCP stdio server with this repository as its working directory, or pass absolute paths for the release, database and people snapshot.

    uv run --locked python scripts/mcp_server.py

The tools are **hansard_find**, **hansard_trace**, **hansard_roles_as_of**, **hansard_member_as_of** and **hansard_read_passage**. A source-linked passage returns its Member ID where available. The member tool returns effective representations, posts, memberships and party records as of the requested day from cached biographies or the Members API. The passage tool reads the official Hansard API. No AI API key or model calls are needed. A voice-enabled host can speak a short answer and pass the digest-bound view to a companion screen. See the [UI study](docs/voice-and-visual-ui.md) for host-specific support and limits.

## Extend the collection

Capture to a fresh directory. The archive uses Parliament’s calendars to avoid polling non-sitting dates. It hashes the matching profile, indexes one House and sitting at a time and reuses processed sittings on restart. The default index path is on ExtSSD-Data. Use another database path when changing the matching profile. The active release can bind an older index by retaining its exact profile. Each entity’s response states whether the extension applies.

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

## Build the Pages snapshot

Run the staging command from the repository root against a verified local release. To regenerate the worked example, run the voice trial builder against the same release and archive first.

    uv run --locked python scripts/build_voice_trial.py
    uv run --locked python scripts/build_pages.py --out .work/pages-next

The Pages site publishes the root of the generated gh-pages branch. The build stages a fixed set of assets, validates the bundle digests and writes a public checksum catalogue. Compare the served files with the catalogue after deployment.

Use `scripts/prepare_demo_week.py --through YYYY-MM-DD --out .work/NEW-BUILD` to prepare an extended release against the local historical index. It reuses the cached sittings and Member biographies, checks both Houses and stages Pages only after verifying the full graph. Explorer uses recorded sitting dates as day-precision timestamps. When its JSON projection needs to be smaller, the week stays complete and earlier contributions are sampled. The full semantic graph is available as YAML-LD or as a gzip download.

## Source attribution

Built with OpenAI Codex, using GPT-6.2 Sol with Ultra reasoning. The build log records the model and reasoning effort. The project owner set the scope and authorised publication.

Contains Parliamentary information licensed under the Open Parliament Licence v3.0 where applicable. Follow the official record for the words and context. The graph’s matches are experimental and carry their own provenance. [Licence and exclusions](https://www.parliament.uk/site-information/copyright/open-parliament-licence/)
