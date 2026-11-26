# Use and test Hansard with your AI

## Start on a phone

1. Open the [Hansard evidence finder](https://chris-page-gov.github.io/okf-hansard/november/ask.html). It opens without a project account or connector installation.
2. Copy the prompt into your AI app. Continue by voice if your app offers it. Ask the assistant to say which capture, dates and files it opened.
3. If the app cannot fetch the links, select a concept in the finder, copy its plain-text evidence and paste that into the same chat. The copied evidence gives dates, attributions and links. To discuss what was said, open a relevant contribution and paste the passage into that chat too.

The visitor needs a browser and an internet connection. Voice depends on the app, account and microphone permission. Clipboard access can prompt on some phones. The page lets visitors select and copy the text by hand in that case.

The [single collection directory](https://chris-page-gov.github.io/okf-hansard/november/hansard.json) links the OKF 0.3 Markdown index, full capture, verified historical matches and the week examples. The historical results are contributions matching configured names and aliases. Ask for dated Hansard links, an exact total of retained matches and the timeline. The companion lets you page through the results.

The finder’s **Copy GitHub prompt** button points the assistant to `HANSARD-EVIDENCE.md` on `main`. Ask it to report the capture-through date and snapshot from the file. The detailed Synergy text is also linked from the finder. It includes captured passages, historical links and coverage. To paste it directly, open **Copy the Synergy evidence if your AI cannot open the link**. [GitHub evidence index](https://github.com/chris-page-gov/okf-hansard/blob/main/HANSARD-EVIDENCE.md)

## Connect an MCP client

From the repository root using the project's Python environment, run the server with the verified publication receipt. It pins that capture when the process starts. Restart the connection to read a later publication. The older archive can be passed to the legacy contribution-anchored trace too.

```sh
uv run --locked python scripts/mcp_server.py --publication .work/november-2026/publication.json
uv run --locked python scripts/mcp_server.py --publication .work/november-2026/publication.json --http 8766
```

The second command listens at `http://127.0.0.1:8766/mcp`. The service implements MCP JSON-RPC over stdio and stateless Streamable HTTP. A cloud app needs an operator-provisioned supported HTTPS endpoint or tunnel, and may need sign-in or workspace approval. The static GitHub Pages finder works independently. [MCP transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

Start every session with `hansard_describe_bundle`. Use `hansard_search_passages` for full text in the captured sittings, `hansard_resolve_concept` and `hansard_mentions` for historical alias matches, and `hansard_read_passage` for an exact source passage. Preserve the `snapshot` identifier and follow `next_offset` until the last page for a complete scoped results list.

## Test the same evidence in each client

Run the deterministic replay against the verified publication receipt. It uses real capture and history data but makes no model calls. It checks both protocol transports for the same scope, aliases, passage search and every page of the Synergy programme matches. The optional client probe checks installed binaries and Gemini project discovery without running inference.

```sh
uv run --locked python scripts/check_voice_clients.py --publication .work/november-2026/publication.json --probe-clients --out .work/voice-clients.json
```

The client list starts with the MCP-Geo tracks (Codex, Claude Code, Gemini CLI and VS Code) and includes the public phone routes. Readiness, tool transport, factual answer and spoken interaction are separate results. Test the prompt in text first. Then start a fresh voice session in the same client. Save the snapshot, evidence links, elapsed time, errors and transcript excerpts only where the account permits it.

| Client | Route to test | Setup or limitation to record |
|---|---|---|
| ChatGPT on a phone | Paste the public prompt, use Live and check source links. | A custom connector is subject to the app and workspace permissions. An app with no URL retrieval can use the copied evidence. [ChatGPT Voice](https://help.openai.com/en/articles/20001274-chatgpt-voice) |
| Codex desktop and CLI | Project-local stdio or loopback HTTP. Check text, then desktop Voice where enabled. | The project must be trusted. A running tool process needs a restart after its configuration or publication changes. [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp) |
| Claude mobile and Claude Code | Public prompt on mobile, stdio or HTTP in Claude Code. | Cloud connectors need a reachable remote endpoint. Check installation and voice access in the intended app. [Claude remote connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) |
| Gemini and Gemini CLI | Public prompt or copied evidence in Gemini. Check a separate project-scoped MCP server in Gemini CLI. | A working `gemini --version` only establishes installation. Check project trust, MCP status and account sign-in separately. [Gemini CLI MCP](https://google-gemini.github.io/gemini-cli/docs/tools/mcp-server.html) |
| VS Code and GitHub Copilot CLI | Project MCP configuration and agent chat. | Check the selected host's trust and GitHub sign-in. Keep its answer test separate from the Microsoft 365 Copilot phone track. [VS Code MCP](https://code.visualstudio.com/docs/copilot/customization/mcp-servers) |
| Microsoft Copilot on a phone and Microsoft 365 Copilot | Try the public prompt, then the copied evidence. | Record which Copilot app and account were used and whether web retrieval and voice are available. |

Use these acceptance cases in each available AI. Connect the named server or paste the public entry before starting the test. A user should reach a cited answer in three minutes using either route. Record any app, authentication or copy steps that exceed that time.

1. **Discovery.** Ask what Hansard contains. The reply must report the current verified capture, the history search ending on **1 November 2026**, known gaps and the distinction between captured passages and retained alias matches.
2. **History.** Ask for every retained Synergy programme link through the last verified sitting. Ask for the total, a copyable list in the chat and the companion timeline. Independently spot-check one October and one November link against the replay output.
3. **Capture search.** Ask for the first three full-text matches for “Civil Service pension scheme”. Check exact source anchors returned by passage search. Verify that the same capture-only query before 2 November 2026 reports no evidence in scope. A phone app may need a connected MCP client for this query.
4. **Fallback.** Block link retrieval or use a client without web access. Copy evidence from the phone page, paste it and verify that the response states its supplied scope. Check an unknown concept returns no configured match with the contribution finder still accessible.

### Score a client session

Save one JSON array with an entry per observed client, mode and case. Use the client names in the replay report and `text` or `voice` for the mode. The runner reads manually recorded observations so mobile clients can use the same checks as the command-line clients. Record only what the assistant actually said or showed. Keep the transcript and any account information outside the receipt.

```json
[
  {
    "client": "ChatGPT mobile",
    "mode": "voice",
    "case": "discovery",
    "seconds": 74,
    "observed": {
      "snapshot": "<snapshot identifier reported by the assistant>",
      "capture_from": "2026-11-02",
      "capture_through": "2026-11-24",
      "contributions": 18364,
      "history_through": "2026-11-01",
      "scope_gaps": 0,
      "disclosed_alias_scope": true
    }
  }
]
```

Record `snapshot` in every answered case. For `history`, record `total`, `timeline`, `links` as an array of exact URLs and `disclosed_alias_scope`. For `capture`, record `links` and `out_of_scope_results`. For `fallback`, record `links`, `disclosed_supplied_scope` and `unknown_concept_reported`. Where sign-in, link retrieval or another product barrier stops the case, give a `blocker` instead of an observation. The report records that case as blocked and unobserved cases as pending.

```sh
uv run --locked python scripts/check_voice_clients.py --publication .work/november-2026/publication.json --receipts .work/voice-session.json --out .work/voice-acceptance.json
```

The runner exits with an error for any failed observed answer. The JSON report retains passed, blocked and pending cases separately.
