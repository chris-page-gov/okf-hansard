# Changelog

## Unreleased — replay the reference consumer with Bonsai 27B

- Diagnose the original failures by reading the saved local answers against
  the frozen rubric. Add a pinned local Bonsai profile and exact evidence replay,
  including byte-identical synthetic fixtures under the same network denial.

## Unreleased — two-phase reference consumer

- Pin a complete compact Hansard bundle, an OKF+ relationship example and a
  local model for a matched-evidence comparison.
- Verify source bytes before generating synthetic private documents in a
  network-denied worker. Record controlled network traces, supported answers,
  citation accuracy, model tokens and latency.

## Unreleased — bring your own AI to Hansard

- Add beginner guides to Hansard and OKF 0.3, a full mobile demonstration and
  a maintainer guide covering vocabulary, algorithms and zero-token publishing.
- Publish a small, source-linked Read OKF+ skill and a retrieval contract.
  Add MCP 2026-07-28 and beta skill discovery and delivery to the read-only
  connector. Preserve legacy protocol support and the separate OAuth briefing.
- Test modern and legacy MCP retrieval across both transports, validate the
  skill files by digest and probe local Claude Code and Gemini CLI separately
  from spoken answers.
- Add a copyable full-collection voice setup and optional spoken shortcut.
  Keep the GitHub and pasted evidence routes available on the same finder.
- Bind recorded capacity assertions to the original Hansard attribution field.
  Retain the cleaned speaker label for display.
- Compact the full collection's plain JSON mention and day files to reduce
  transfer and make room for the new verified sittings on Pages.

## Unreleased — check cached November builds before backfill

- Check the native build receipt, OKF version and artefact digests before a
  cached November candidate can resume historical collection.

## Unreleased — GitHub evidence index, 26 November 2026

- Add a small Markdown evidence index on the repository's main branch for
  assistants that can read GitHub. Include verified dates, recent excerpts
  and the Synergy worked example.
- Refresh the index through protected pull requests before attempting Pages
  deployment and retry a pending index on the next scheduled run.
- Point the phone finder's copyable prompt and collection directory to the
  GitHub evidence index. Keep the worked example available to read or copy.

## Unreleased — signed-in Hansard portfolio briefings, 26 November 2026

- Add an OAuth-protected MCP briefing for a signed-in member's dated portfolio.
  Return verified excerpts and exact contribution links from the latest
  published capture and distinguish the member's contributions from others.
- Reopen the verified publication when its receipt is replaced so a long-running
  briefing connector can answer against a new snapshot.

## Unreleased — Synergy evidence for phone assistants, 26 November 2026

- Publish one small plain-text Synergy example with a snapshot identifier,
  exact source links, captured extracts and downloaded historical alias matches.
  Embed the same evidence in the phone finder for direct copying.
- Explain why the configured historical search dates differ from the main
  archive and what a House-day with no calendar sitting means.

## Unreleased — resume the November publisher, 26 November 2026

- Resume a verified prepared attempt after an interrupted refresh. Retain the
  attempt's receipt path so publishing can save the checked site and restart
  from the same point.
- Compress the November YAML-LD export at gzip level 9 to keep the
  25 November release within the GitHub Pages size limit.

## Unreleased — bound full-source descriptor size, 25 November 2026

- Keep the deployed Reader's 16 MiB descriptor limit. Move the complete Core
  source roster and non-record Markdown to a separate plain JSON asset, bound
  from the small descriptor by SHA-256 and byte count and included in the
  public checksum catalogue. Retain all concept Markdown in the existing
  record shards and all graph assertions unchanged.
- Reject oversized full-graph descriptors before either Pages publisher takes
  its lock or replaces assets. Validate the external Core binding schema and
  expose its plain JSON URL through the public access directory. Mark source
  documents served by that manifest as `source_manifest`, retaining
  `record_chunks` for records.

## Unreleased — fail-closed November publication assets, 25 November 2026

- Include every authored profile and static page input in the November cache
  fingerprint, including vocabulary and additional stylesheets. A change to
  these inputs invalidates an otherwise intact prepared site.
- Validate the cached November site and every required entry point against its
  checksum catalogue before replacing the published directory. An incomplete
  cache is restaged under a fresh path; the compact descriptor and both
  source-linked walkthroughs are mandatory publication assets. Recheck the
  full and compact bundle identities and their walkthrough bindings before
  publication. Bind each prepared site to its through-date, release receipt,
  builder and profile inputs, and exact checksum catalogue so stale caches are
  restaged even when their files are internally consistent. Keep the prior
  frozen archive links in the expanded current download index.

## Unified Hansard and voice access

- Link the home page and worked examples directly to the Hansard collection.
- Add a shared scoring runner for recorded text and voice answers from ChatGPT,
  Codex, Claude, Gemini, VS Code and Copilot. Keep pending cases separate from
  recorded blockers and failed answers.
- Added a single collection entry for the verified capture, earlier matches and demonstration views.
- Added an account-free phone evidence finder, plain-text prompt and followable source links.
- Added capture search, concept resolution, complete paged mention lookup and read-only MCP access over stdio or Streamable HTTP. A project server can pin the latest verified publication at start-up.
- Added cross-client evidence and transport tests, with separate readiness, assistant answer and voice checks.
- Recovered the four Commons written-answer timeouts in the pre-2007 archive. Retry attempts keep previously captured records until a complete replacement is verified.

## Unreleased — patched uv certificate trust, 24 November 2026

- Require uv 0.13.4 for local project commands and CI. This removes the
  compromised emSign root from the build tool’s bundled certificate store
  ([GHSA-hq85-5cpj-mr62](https://github.com/astral-sh/uv/security/advisories/GHSA-hq85-5cpj-mr62)).
  Preserve the dependency lock, source captures, generated bundle bytes and
  published 0.3.0 release. This correction governs future builds; it does not
  change the frozen publication.

## Unreleased — readable mobile walkthroughs, 23 November 2026

- Give each compact and full-graph walkthrough a separate readable mobile
  diagram. Stack the evidence steps vertically and retain legible date/count
  labels in the November chart. Publish both diagram hashes, choose the layout
  by viewport width and offer a full-size diagram link. Preserve source and
  graph bytes.

## Unreleased — preserve existing public assets, 23 November 2026

- Retain three small compatibility assets from the previous Pages revision,
  including the catalogue of frozen historical downloads. Keep their acquired
  input bytes, prior publication revision and digests in the source repository.
  Restore the November archive link and suppress an unrelated favicon request.
- Refuse altered inputs or collisions with later public material. These assets
  retain historical context; they do not become part of the active 0.3 graph.

## Unreleased — complete bundle publication checks, 23 November 2026

- Give each compact week and November entry-point bundle its own source-bound
  question, qualified answer, diagram and negative controls, alongside the two
  full-graph walkthroughs. Keep compact answers within their zero-edge scope.
- Preserve root metadata and exact licence bytes in compact projections, and
  declare each document's actual published `okf/` path for Reader and AI access.
- Reconcile each compact projection with an independent core import. Check all
  concepts, reference pairs, frontmatter, bodies, source bytes and licence;
  require a non-empty string `type` before treating a document as a concept.
- Correct the November walkthrough's Reader link to the November bundle and
  focus the source-linked proceedings route. Record the replayable mouse
  journey for Reader 0.9.0, retaining keyboard access for earlier Readers.
- Describe the static stage diagram accurately and keep official source links
  separately accessible. Derive the weekly answer from its stage records,
  require its reviewed three-stage scope and bind each full-graph walkthrough
  to its own descriptor identity and digest. Label the monthly total accurately.
  Avoid an unrelated host favicon request.
- Implement the missing complete public-asset verifier with strict local
  checksum coverage, bounded retrieval, exact empty Pages-marker handling,
  source revision binding and a clean-checkout requirement. Keep public browser
  and semantic acceptance separate from file retrieval.

## Unreleased — estate acceptance, 23 November 2026

- Strengthen the independent full-source audit: require complete agreement
  between direct graph edges and reified assertions, check graph framing and
  log dates, and accept only a non-empty string as a concept type. Hash ancillary
  Markdown without treating it as a concept. Add negative controls for these
  boundaries and bind each audit to the full implementation revision.
- Correct the active domain profile's core declaration to match the implemented
  OKF 0.3 writer. Document the upstream announcement and implementation dates.
  Retain the pinned historical schema references and existing source identities.
- Add a versioned Hansard domain profile and a repository semantic contract for
  the full corpus graph and the smaller public entry-point bundles. Add an exact
  Markdown-backed core Reader projection for each entry-point bundle, bind the
  full generated Markdown source into the existing bounded graph record shards,
  and add a separate graph-linked visual walkthrough for the week and November
  coverage.
- Set the producer version to 0.3.0 in package metadata and active descriptors;
  retain the existing November historical-release tag and frozen assets.
- Retain 506 compatible weekly history-search packages through 1 November and
  mark the 2–15 November weekly search interval as uncovered. Two changed
  profile records are excluded; no new Hansard API searches were run.
- Add four portable, exact-identity Explorer journeys for the week and November
  compact cores and full graphs. The graph journeys activate the focusable Bill
  node with Enter and assert its exact route. Weekly pointer selection remains
  unaccepted because an overlapping SVG label hit area intercepted the mouse
  target; the visual walkthrough records this limitation.

## Unreleased

- Link the central current and historical OKF standards register and public bundle catalogue.
- Migrate the generated Hansard Markdown to the pinned OKF 0.3 specification. Keep directory indexes outside the semantic concept graph and retain the Reader’s navigation route.
- Publish Markdown entry points, a machine-readable directory and `llms.txt` for the week and November views. Add a demo prompt and direct links to source evidence, the companion, graph and timeline.
- Lead with the Railways Bill in the AI guide and companion. Label the Microsoft 365 example as a Commons statement about the outage.
- Add the November publication workflow and contribution-level history views to the source repository. The build reuses previously verified archive partitions when their scope is unchanged.
- Allow new November publication attempts to stage on ExtSSD-Data while retaining existing checkpoints and published assets.
- Require the read-only `okf-hansard-ci` check for `main`. It runs locked Python tests and browser-script syntax checks without source acquisition or publication.
