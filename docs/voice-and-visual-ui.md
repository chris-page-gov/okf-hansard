# Voice and visual access for a local Hansard pilot

Research note, 17 November 2026. The pilot has structured evidence tools, a browser Reader and a companion table with proportional bars. Native voice and host-specific accessibility remain acceptance work.

## Use one evidence response across speech, text and visuals

A voice-enabled client can collect the question, call the same read-only tools as a text client, speak a concise answer and give the user a companion view. The evidence response carries the contribution ID, assertion IDs, source links, matching method, observed time range, counts and gaps. A viewer needs those fields to preserve the meaning of the spoken answer.

The built Explorer already assembles bounded evidence and has exact-read tools with package identities. Its test record covers keyboard interactions, narrow layouts, cancellation on source change and package parity. Native-host compatibility needs a test in the target workspace. [Explorer Ask interface verification](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/ask-okf-ui-verification.md) · [Compact evidence delivery decision](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/adr-compact-evidence-delivery.md)

## Interface choices

| Interface | How it would work |
| --- | --- |
| Local MCP stdio | A compatible AI host calls the Hansard tools and uses the returned source links. The pilot’s transport is read-only and uses no model-service credentials. [MCP transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) |
| Browser companion | Present the source-linked record or the generated view in ordinary HTML. A voice client can open it by opaque view ID and keep the transcript and citation links alongside the answer. |
| MCP Apps | A compatible host can render an associated sandboxed view from a resource. Keep plain structured results available and test resource loading, host messaging, tool calls and navigation in the chosen host. [MCP Apps specification](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/2026-01-26/apps.mdx) · [ChatGPT UI integration guide](https://developers.openai.com/plugins/build/chatgpt-ui) |
| WebMCP | Explorer registers read-only page tools in supported browsers. Browser registration and native-host access have distinct test requirements. [Explorer Ask interface verification](https://github.com/chris-page-gov/okf-explorer/blob/main/docs/ask-okf-ui-verification.md) |
| Realtime voice client | An application can use speech-to-speech with app-executed functions or remote MCP. Browser sessions use an ephemeral credential minted by the application’s server. This route requires an approved model budget, authentication and a data handling decision. [Realtime guide](https://developers.openai.com/api/docs/guides/realtime) · [Realtime tools guide](https://developers.openai.com/api/docs/guides/realtime-mcp) |

OpenAI’s current guidance describes connected apps in Live where the account and workspace allow them. Voice in existing Codex chats is rolling out. The public Microsoft 365 example also provides ordinary web evidence that a ChatGPT conversation with web access can read. Native access to the local stdio server depends on the host and needs a live test. [Voice in Codex](https://learn.chatgpt.com/docs/features/voice) · [Connected apps in ChatGPT](https://help.openai.com/en/articles/11487775-connected-apps-in-chatgpt)

## A declarative visual contract

The prototype implements a small **okf-view.v1** descriptor for the related-entity ranked bar chart and table. It binds the data, view and evidence context by digest. Each row carries an entity ID, a count of distinct contribution records and arguments for opening the supporting evidence through the same read-only tool. The companion renderer verifies the descriptor’s identity, dataset digest and evidence binding before it writes HTML.

A broader VizQL-style approach could select a view type, typed fields, grouping, sort order and bounded transforms from explicit lists. Define the unit and date semantics for each measure, including the difference between a sitting date, text publication date and capture date. Include filters, evidence status, omissions, source versions and the underlying records or exact drill-down arguments. Compile the approved shape deterministically into ordinary HTML or a renderer such as Vega-Lite. The available view types and transforms form a closed interface with local data. [Vega-Lite grammar](https://vega.github.io/vega-lite/docs/) · [W3C WCAG 2.2 non-text contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast) · [DfE chart design pattern](https://design.education.gov.uk/design-system/patterns/charts)

For spoken interaction, confirm an ambiguous metric, select evidence, resolve the visual intent against available templates and validate the resulting package and view. Announce the view once the host confirms it opened. Provide the title, time range and a concise summary from the same numbers. Keep a plain table with labels, units and citations. Use opaque view identifiers in links and keep transcripts out of URLs.

Hansard mention counts describe selected contribution records and lexical coverage. A count can include passages with opposed views, procedural language or repeated interventions. Use the time range and corpus denominator alongside each chart.

## Improvements to OKF Explorer

1. Add a **Related evidence** panel on a contribution. Group people, offices, places, organisations, things, legislation and topics. Show earlier match counts and source links within each group. Let a reader switch between the date cohort and the extended archive.
2. Group a person and their relevant capacity in the display while preserving their separate IDs. Display the effective dates and the source of a dated appointment. Show ambiguous candidates or unresolved role labels as such.
3. Use the focus graph for a bounded neighbourhood, with a count and a stable route to more results. Keep the evidence table or list reachable by keyboard.
4. Separate the contribution date, source version and current query window in the visible provenance. Label a matched term, a contextual proceeding and a dated relation distinctly. Expose whether the archive extension applies to each entity.
5. Allow a host to hand Explorer a validated, digest-bound view reference. Include a deep link to the contribution, selected facet and evidence window. Preserve selection and focus during pagination and after reload.
6. Prototype a tiered Reader for large bundles. Load the compact week index first, then fetch historical postings and evidence by entity and page. This gives a practical path beyond the small bundle’s 64 MiB limit.

## Acceptance

- Reproduce the source-linked answer and the same view from a saved context and dataset digest. Reject a mismatched view, invalid field or altered result.
- Check the unit, date span, source coverage, omitted records and unique item count against the complete selected dataset.
- Open every sampled aggregate’s drill-down and match it to the official contribution. Test two independent facets together and verify state recovery after reload.
- Test empty, ambiguous, truncated, changed-source and stale-view states. Keep the textual lookup working if the host cannot show the view.
- Check keyboard navigation, focus, screen-reader order, colour and contrast, zoom and the narrow layout. Confirm access to the same evidence through the table.
- Run a named-host test for text, then for voice. Confirm that the voice response cites the same context ID and announces a view only after the companion screen opens.
- Verify that the chosen host policy covers voice transcripts, app messages and any model or credential use. This local pilot uses no model API calls.
