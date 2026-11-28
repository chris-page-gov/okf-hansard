# Demonstrate Hansard in your own phone assistant

Bring a phone and open the AI app you already use. You can open the public finder without a Hansard account. The phone conversation uses your assistant and its available memory, tools, speech and citation display. [Open the phone finder](https://chris-page-gov.github.io/okf-hansard/november/ask.html)

## Run the demonstration

1. **Start once.** On the finder, tap **Copy full collection instructions**. Paste into a new chat. If you want a repeatable spoken shortcut, ask the app to save the instruction as a preference. Check that the saved instruction points to the correct collection. Use the same chat or paste the prompt again when the app cannot use saved preferences.
2. **Open the collection by voice.** Say, “Chat to GTM Hansard. What do you have and how up to date is it?” Expect the actual verified date range and snapshot, both Houses, and the distinction between the captured sittings and the historical alias searches. Ask for the coverage link in chat and compare it with the assistant's answer.
3. **Use the full capture.** Say, “Find three contributions about the Civil Service pension scheme in the capture. Give me a two-sentence summary and show the exact Hansard links.” Ask it to open a timeline and follow a selected contribution into its graph. If your host has the connector, try a different phrase from the last verified sitting. This establishes use of the full capture beyond the worked example.
4. **Follow a concept over time.** Say, “Trace the Synergy programme across the capture and earlier records. What changed, who spoke, and which claims were commitments? Show me the timeline and say where you could read the source text.” If the user wants every retained result, ask for the count and all source links in chat. Dated name matches alone can be used as links to investigate.
5. **Use your own context.** Say, “Which public topics from my approved portfolio were discussed in the last verified week?” The assistant can select public topic labels using what it knows and ask if the remit is ambiguous. For an authorised signed-in deployment, ask the assistant to call the secure briefing tool instead. Show which dates and topics it used. [Secure briefing connector](secure-briefing.md)

The opening phrase is a personal alias. The user can store it in memory, instructions or another supported preference. It carries no credentials, and a fresh installation has to be shown what it means. A public lookup should contain the question's approved topic, dates and optional House, rather than the person's name, private role context or conversation transcript. Use the secure connector only when the organisation and assistant are approved. Your provider controls what its own service receives and retains.

## Use the available route

| Route | Setup | How to tell it worked |
| --- | --- | --- |
| Full search using MCP | A reachable HTTPS endpoint approved for the intended host and account. Set up the connection before the demo. If offered, review and approve the published skill. | The assistant reports the current snapshot from `hansard_describe_bundle` and retrieves a fresh captured passage with the exact anchor. It can find terms absent from the small index. |
| Public collection | Paste the collection link. Use direct web retrieval in the app when offered. Follow the collection's scope, OKF index, history and timeline. | The assistant reports the verified snapshot and explains which files it opened. Try a new topic. Access to individual Markdown and data files varies. |
| GitHub evidence index | Tap **Copy GitHub prompt**. The assistant reads the small Markdown file from the public repository's main branch. | The assistant reports the snapshot and cites the supplied excerpts. Its answer covers the selected evidence in that index. |
| Pasted evidence | Open the finder in a browser, expand the Synergy evidence or find a concept and copy its selected links. Paste that text into the chat. | The assistant labels the supplied scope and uses its exact links. An excerpt can support a summary. A list of links gives pointers to evidence. |

A web service may block a provider's retrieval even when the page opens in your browser. A cached index may still refer to an older snapshot. Check the date and snapshot at the beginning of the conversation. Keep the evidence from each snapshot together. For a demonstration on an unprepared phone, the pasted route works whenever the app can read chat text. The full-capture test above requires evidence from the full collection. [Collection directory](https://chris-page-gov.github.io/okf-hansard/november/hansard.json) · [GitHub evidence index](../HANSARD-EVIDENCE.md)

## Try a fresh chat with only the collection address

The [upstream OKF 0.3 reader](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/skills/okf-consume/SKILL.md) starts at the bundle’s Markdown index. It follows relevant concepts, checks the trust, status and freshness declared for each one, and cites the supporting sources. A phone can follow these links without running the optional scan script.

The [Hansard reader](https://chris-page-gov.github.io/okf-hansard/november/skills/read-okf-plus/SKILL.md) adds a collection snapshot, sitting coverage, concept aliases, earlier mentions, and links to individual contributions. Installing a skill on a Mac does not establish that a phone loaded it. The public [retrieval contract](https://chris-page-gov.github.io/okf-hansard/november/voice-retrieval.json) advertises readable HTTPS copies of the skill and its reference. A phone with web access can read them. Record native skill activation separately if the app reports it.

The existing finder copies a fuller setup into the conversation. The following trial tests whether the assistant can discover the same resources from one address. Start a fresh chat with prior Hansard context and saved shortcuts disabled where possible. Supply only the [collection address](https://chris-page-gov.github.io/okf-hansard/november/hansard.json) and say **“Connect to OKF Hansard. What does this collection cover, and how current is it?”**

1. **Discovery.** Ask for the coverage link and snapshot in writing. Compare them with the collection you open directly. Record which provider, app mode and route actually returned the information.
2. **Retrieval.** Ask a new question about a parliamentary exchange, without supplying names, identifiers or expected answers. Ask for the contribution and the evidence used. An answer from an independent Hansard search can be checked separately. It does not demonstrate bundle retrieval.
3. **Attribution.** Ask which contribution answers the question and what the respondent committed to. A graph pass requires the relation, its direction and both evidence links in the tested snapshot. Read the reply to verify the wording. A matching debate title, a list of mentions or an Explorer link alone does not establish who answered whom. An explicit report that the relation is absent is the correct outcome for an unsupported pairing.

Repeat the trial with the shorthand **“Connect to OKF Hansard”** only after an address-only preference has been saved in that assistant. Keep the public address in memory and read the snapshot afresh on each connection. Keep the same snapshot for follow-up questions. If an app cannot retrieve a resource, record the last successful step before trying the GitHub or pasted-evidence route. Score assisted retrieval separately.

## App readiness

- **ChatGPT.** Live supports web search, memory and connected apps where available to that account. Check Live availability, the chosen workspace and the actual connector before presenting native tool use as passed. [ChatGPT Voice](https://help.openai.com/en/articles/20001274-chatgpt-voice)
- **Claude.** Custom remote connectors are set up in eligible Claude clients, with mobile installation documented as beta. Claude's voice documentation describes access to web search and connected tools. Verify the exact Hansard connector in the phone's voice mode. Claude Code validation of the local skill is a separate check. [Connectors](https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities) · [Claude Voice](https://support.claude.com/en/articles/11101966-use-voice-mode)
- **Gemini.** As checked on 27 November 2026, Google documents custom MCP apps for US adults using eligible personal accounts, with setup on the web and subsequent access in the mobile app. For a UK audience, start with the collection, GitHub or pasted evidence. Check Live in the actual mobile app. Gemini CLI's local skill discovery is a separate check. [Gemini custom apps](https://support.google.com/gemini/answer/17209137) · [Gemini CLI skills](https://geminicli.com/docs/cli/tutorials/skills-getting-started/)

## Check the result

Open one official contribution and compare speaker, date and the claim the AI attributed to them. Check the timeline displays the intended date and subject. Start a fresh chat to test that the spoken alias works where a preference was saved. Record the app and mode, region or workspace eligibility, retrieval route, whether it activated the skill, snapshot, time to a cited result and any blocker. Store only the acceptance data needed to verify the run. [Repeatable cross-client evaluation](voice-acceptance.md) · [Beginner’s guide to records and OKF 0.3](learn-hansard-okf.md)
