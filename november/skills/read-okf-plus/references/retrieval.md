# Hansard retrieval routes

| Route | How to start | Evidence available |
| --- | --- | --- |
| Connected MCP | Call `hansard_describe_bundle`. For passage queries use `hansard_search_passages`. For historical queries call `hansard_resolve_concept` then `hansard_mentions` with the resolved key, snapshot and optional dates. | Full captured passage search, retained alias matches, official links and per-concept timeline. |
| Public web | Open the [collection directory](https://chris-page-gov.github.io/okf-hansard/november/hansard.json). Follow its OKF index, coverage, history and source links as needed. | Published evidence, browser finder, graph and timeline. A host may have access to only some formats. |
| GitHub or pasted evidence | Read the [small index on main](https://github.com/chris-page-gov/okf-hansard/blob/main/HANSARD-EVIDENCE.md). If links are blocked, ask for copied evidence from the [finder](https://chris-page-gov.github.io/okf-hansard/november/ask.html). | Snapshot, counts and selected evidence. Use another verified route for questions outside that scope. |

For scoped exhaustive results, follow `next_offset` until it is null. A changed snapshot invalidates a previous offset. Historical data includes separate ranges, matching profiles and recorded gaps. A completed search means that configured names and aliases were checked. It does not measure all historical discussions of the subject.

For a spoken date range, read the context index's calendar. Use its RFC 6570 month or range template, substituting ISO dates. Bounds include both days in Europe/London. Split a cross-month request at month boundaries, check coverage and report missing dates. “Last month” means the previous calendar month relative to the conversation date. “Last 30 days” includes today and the preceding 29 days. Open only the selected dates and sections.

For surrounding turns, follow the current collection's `entrypoints.contribution_context`. The index links each sitting date to a section list. Resolve its day links relative to the index URL. When a captured contribution route is known, open `history/days/YYYY-MM-DD.json` relative to the collection and follow that row's `context` relative to the collection. Read the numbered turn identified by the fragment. With the connector, use `hansard_contribution_context` with the same contribution route and snapshot. Distinguish speaking order from a reviewed reply link. Cite each contributing passage separately and disclose when the excerpt ends before the wording you need.

For exact wording, use the source anchor or `hansard_read_passage` on a supported contribution ID. If neither yields the source text, report a link-level match. The public site includes a graph for exploring relationships and a timeline for inspecting dated material. Share the relevant view URL so the user can inspect it while speaking.

The workflow follows the upstream [OKF 0.3 reader skill](https://github.com/open-knowledge-format/open-knowledge-format/tree/527e81aff55992be21507e97004286789126f88c/skills/okf-consume) for scoped reading and provenance. This repository specialises it for parliamentary evidence and provides an instructions-only path for mobile.
