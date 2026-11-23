# Discover and demonstrate the Hansard bundle

## Run the demonstration

Open the AI guide beside the companion. Give your assistant the Railways Bill prompt or attach the Markdown evidence. Follow the recorded stages from the Commons to the Lords and check the timeline against the official Bill record and Hansard. [AI guide](https://chris-page-gov.github.io/okf-hansard/use-with-ai.html) · [Railways Bill evidence](https://chris-page-gov.github.io/okf-hansard/okf/railways-bill.md)

For other examples, follow Martin Wrigley’s references to earlier debates or read Ian Murray’s Commons statement about the Microsoft 365 outage and trace earlier mentions. For other questions, choose a sitting or entity in the November contribution finder. Shared name and alias matches can concern other business. Use a contribution’s official source to check its meaning. [Palantir and the NHS](https://chris-page-gov.github.io/okf-hansard/okf/palantir-nhs.md) · [Commons statement on the Microsoft 365 outage](https://chris-page-gov.github.io/okf-hansard/okf/microsoft-365.md) · [November finder](https://chris-page-gov.github.io/okf-hansard/november/history.html)

## Find the right data

Each landing page advertises its Markdown index and machine directory. The directory provides the OKF version and specification, coverage, licence, exact file URLs, SHA-256 checksums and Explorer descriptor. The `.well-known/okf.json` alias lives under the project path on GitHub Pages. `llms.txt` provides a plain-text route. [Week directory](https://chris-page-gov.github.io/okf-hansard/okf-public-access.json) · [November directory](https://chris-page-gov.github.io/okf-hansard/november/okf-public-access.json) · [Plain-text route](https://chris-page-gov.github.io/okf-hansard/llms.txt)

Open the Markdown example or coverage first. For a broader graph query, follow the descriptor’s record or relationship locator and retrieve the relevant shards. For November dates, use the coverage report to select a day and follow the contribution and entity links. The public YAML-LD and historical downloads support bulk use. Fetch them only if the question or workflow needs them. [Explorer discovery conventions](https://chris-page-gov.github.io/okf-explorer/docs/public-bundle-access.html)

In the full-corpus Explorer graph, focus the Railways Bill node and press Enter to open its record. The keyboard journey checks the exact Bill 4030 route. Weekly pointer acceptance remains open: the Bill node’s mouse hit area was intercepted by an overlapping SVG label hit area. The accepted journey uses keyboard activation, and does not claim pointer selection passed.

The public files require an assistant that can open the URLs or accept uploaded text. Voice hosts vary in what their assistant can retrieve and what the user can open on screen. Ask the assistant to state its coverage and open the companion in a browser when needed. Local MCP access is a separate route. [Voice and storage](voice-and-visual-ui.md#voice-and-storage)

The weekly finder reuses verified search records through 1 November 2026. Searches for 2–15 November are not present in that bundle. The November bundle contains captured proceedings for its declared dates, but it does not fill this weekly search gap. Keep the gap visible when answering questions about earlier mentions.

## Standards and checks

Upstream OKF 0.3 was announced on 18 November 2026. The Hansard implementation
was committed on 23 November 2026 in
[the source-linked discovery and 0.3 migration change](https://github.com/chris-page-gov/okf-hansard/commit/bfebbed03e1a76e12f1f4680739c51860997d147).
The active domain profile declares the same core version as the writer.
Source conformance, consumer journeys and publication retain their own evidence.

The core version is **OKF 0.3**, pinned to the upstream specification by commit. The Hansard domain semantic profile is separately versioned and published at [hansard-domain-v2.json](https://chris-page-gov.github.io/okf-hansard/profile/hansard-domain-v2.json). It inherits the current Bundle Wiki v2 profile while retaining the frozen v1 assertion and relationship-row schemas as structural dependencies. Generated Markdown has a navigable root and subdirectory indexes. The reserved `index.md` and `log.md` files sit outside the concept graph. Reader navigation rows are marked `core_role: navigation`; typed Markdown concepts are marked `core_role: concept`. Concepts carry source locators where available. Capture and source-relationship verification stay in their receipts. Source conformance, Explorer use, AI retrieval and publication each have separate acceptance evidence. [Pinned OKF 0.3 specification](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/SPEC.md)

The OKF+ YAML-LD projection uses the frozen Explorer Bundle Wiki v1 relationship assertion schema as a structural dependency. It retains source fields, spans, identity qualifiers and rights. The compact public `okf-core.json` projection carries the exact bytes, frontmatter and body of every typed Markdown concept in the week or November entry-point directory. Its zero-relationship scope is explicit. The full generated Markdown source is bound to the same large-corpus descriptor: every typed concept is included in a bounded record-detail shard with its exact Markdown, frontmatter, path, byte count and digest; the descriptor carries the reserved index documents and complete source-path digest roster. Existing assertion IDs and graph shards remain the graph traversal surface. The local verifier checks the Markdown structure, graph integrity, a sample of RDF triples and the source values behind relationship assertions.

Explorer’s standards register records the same OKF 0.3 specification pin and links the earlier core versions and public bundle catalogues. [Standards register](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/okf-standards.md) · [Machine-readable register](https://raw.githubusercontent.com/chris-page-gov/okf-explorer/main/registry/okf-standards.json) · [Public access directory](https://chris-page-gov.github.io/okf-explorer/okf-public-access.json)

The domain vocabulary, build code and curated summaries remain in the repository. The Markdown, YAML-LD, sharded Reader and discovery outputs are generated from verified snapshots. The week and month stagers regenerate discovery files as part of publication, with the discovery files included in each checksum catalogue. Each public site contains a focused entry-point projection and a full-source graph descriptor whose record-detail chunks preserve source text, frontmatter and paths for AI retrieval.

The `okf-hansard-ci` GitHub Actions check runs the locked Python tests and checks the browser scripts on pull requests to `main`. The release stagers and public verification check the larger captures and deployed views separately.

GitHub requires an up-to-date pull request, a passing `okf-hansard-ci` check and resolved conversations before merging into `main`. The protection applies to administrators and blocks force-pushes and branch deletion. Use squash or rebase to retain linear history.
