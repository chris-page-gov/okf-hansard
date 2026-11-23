# Discover and demonstrate the Hansard bundle

## Run the demonstration

Open the AI guide beside the companion. Give your assistant the example prompt or attach the relevant Markdown file. For a live demonstration, use the Microsoft 365 example. The evidence gives you Ian Murray’s statement, the direct links to the people and organisations named, and a dated list of earlier matches. Follow a passage back to Hansard, then open the same trail in the graph and timeline. [AI guide](https://chris-page-gov.github.io/okf-hansard/use-with-ai.html) · [Microsoft 365 evidence](https://chris-page-gov.github.io/okf-hansard/okf/microsoft-365.md)

For a different demonstration, follow Martin Wrigley’s references to earlier debates or compare the stages of the Railways Bill. For other questions, choose a sitting or entity in the November contribution finder. Shared name and alias matches can concern other business. Use a contribution’s official source to check its meaning. [Palantir and the NHS](https://chris-page-gov.github.io/okf-hansard/okf/palantir-nhs.md) · [Railways Bill](https://chris-page-gov.github.io/okf-hansard/okf/railways-bill.md) · [November finder](https://chris-page-gov.github.io/okf-hansard/november/history.html)

## Find the right data

Each landing page advertises its Markdown index and machine directory. The directory provides the OKF version and specification, coverage, licence, exact file URLs, SHA-256 checksums and Explorer descriptor. The `.well-known/okf.json` alias lives under the project path on GitHub Pages. `llms.txt` provides a plain-text route. [Week directory](https://chris-page-gov.github.io/okf-hansard/okf-public-access.json) · [November directory](https://chris-page-gov.github.io/okf-hansard/november/okf-public-access.json) · [Plain-text route](https://chris-page-gov.github.io/okf-hansard/llms.txt)

Open the Markdown example or coverage first. For a broader graph query, follow the descriptor’s record or relationship locator and retrieve the relevant shards. For November dates, use the coverage report to select a day and follow the contribution and entity links. The public YAML-LD and historical downloads support bulk use. Fetch them only if the question or workflow needs them. [Explorer discovery conventions](https://chris-page-gov.github.io/okf-explorer/docs/public-bundle-access.html)

The public files require an assistant that can open the URLs or accept uploaded text. Voice hosts vary in what their assistant can retrieve and what the user can open on screen. Ask the assistant to state its coverage and open the companion in a browser when needed. Local MCP access is a separate route. [Voice and storage](voice-and-visual-ui.md#voice-and-storage)

## Standards and checks

The core version is **OKF 0.3**, pinned to the upstream specification by commit. Generated Markdown has a navigable root and subdirectory indexes. The reserved `index.md` and `log.md` files sit outside the concept graph. The Explorer runtime keeps a virtual navigation record for existing Reader routes. Concepts carry source locators where available. Capture and source-relationship verification stay in their receipts. The producer has only recorded verification that it can substantiate. [Pinned OKF 0.3 specification](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/SPEC.md)

The OKF+ YAML-LD projection uses the Explorer Bundle Wiki v1 relationship assertion schema and retains source fields, spans, identity qualifiers and rights. The local verifier checks the Markdown structure, graph integrity, a sample of RDF triples and the source values behind relationship assertions. The shared Explorer reconciler currently targets its OKF 0.2 profile and has no Hansard preset. [Semantic authoring profile](https://chris-page-gov.github.io/okf-explorer/docs/okf-0.2-yaml-ld-semantic-authoring.html)

The estate-wide standards locations are Explorer’s [standards register](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/okf-standards.md) and [machine register](https://github.com/chris-page-gov/okf-explorer/blob/main/registry/okf-standards.json). Until those paths are available, use the exact specification pin above and the [published standards crosswalk](https://chris-page-gov.github.io/okf-explorer/docs/okf-standards-crosswalk.html).

The domain vocabulary, build code and curated summaries remain in the repository. The Markdown, YAML-LD, sharded Reader and discovery outputs are generated from verified snapshots. The week and month stagers regenerate discovery files as part of publication, with the discovery files included in each checksum catalogue. The complete generated Markdown tree is available locally. The website publishes the smaller Markdown entry points.

The `okf-hansard-ci` GitHub Actions check runs the locked Python tests and checks the browser scripts on pull requests to `main`. The release stagers and public verification check the larger captures and deployed views separately.
