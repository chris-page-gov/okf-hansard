# Secure Hansard briefings on a phone

Once the assistant is connected and the user has signed in, the person can ask, “What did Parliament discuss about my portfolio last week? Give me a short summary and the Hansard links.” The assistant can make one `hansard_my_briefing` call. It receives the topics that were configured for the signed-in person's effective portfolio dates, verified excerpts, speakers, and links to the exact contributions and timeline. It can speak the summary and show the links in chat.

The default covers seven calendar days ending at the latest verified sitting. If the question says “last week”, the assistant should pass the local calendar dates explicitly. The response lists the observed sitting dates inside the request. It counts retained matches per topic, supplies up to three examples for each speaker group, and identifies that member's own contributions by the official Parliament Member ID. A portfolio match is evidence of parliamentary discussion. The exact source gives the context for whether a speaker asked a question, made a proposal or announced a decision.

## Bind the account to its portfolio

An authorised administrator maps the identity provider's stable subject identifier to an official Parliament Member ID. Select concept IDs from the collection's configured vocabulary and verify the dates of the person's responsibilities. A topic can have several assignments with different dates. Omit `through` while an assignment is in force. Write both dates as ISO calendar dates. [UK Parliament member search](https://members.parliament.uk/) · [Hansard concept catalogue](https://chris-page-gov.github.io/okf-hansard/november/concepts.json)

The tool accepts the date range only. It uses the identity established by OAuth for the portfolio. An assistant can phrase the question using its own context about the person. Names and job titles from a conversation cannot select a different user's binding.

## Run the protected connector

Use a verified publication receipt and its staged public bundle, release and captured Parliament records on the approved host. The private service reads data from those host paths. Each call uses one verified snapshot, and the next call reopens it when the publisher atomically replaces its receipt.

Keep the settings file and the introspection client secret in the hosting environment's private configuration. The following values illustrate the shape. Use actual concept IDs and authorisation server values in the host configuration.

```json
{
  "resource": "https://briefings.example.gov.uk/mcp",
  "issuer": "https://login.example.gov.uk/realm",
  "introspection_endpoint": "https://login.example.gov.uk/realm/introspect",
  "introspection_client_id": "hansard-briefing-resource",
  "bindings": {
    "example-opaque-subject": {
      "member_id": 1234,
      "portfolio": [
        {"key": "synergy-dwp", "from": "2026-11-01"}
      ]
    }
  }
}
```

Set `HANSARD_INTROSPECTION_CLIENT_SECRET` through the host's secret store. Set up the authorisation server to issue user-delegated access tokens with the exact resource URL as audience and the scope `hansard:briefing`. It must support HTTPS OAuth token introspection with confidential-client authentication and return the verified subject, audience, expiry and scope for active tokens. Register the approved assistant as an OAuth client using its supported registration and redirect flow. Keep the bindings on the protected host. [MCP authorisation](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization) · [OAuth token introspection](https://datatracker.ietf.org/doc/html/rfc7662)

```sh
uv run --locked python scripts/mcp_server.py \
  --publication .work/november-2026/publication.json \
  --http 8766 --authorisation /path/to/private/briefing-settings.json
```

Terminate TLS at the approved reverse proxy. Route `/mcp` and `/.well-known/oauth-protected-resource/mcp` to `127.0.0.1:8766`, rewrite the upstream Host to `127.0.0.1:8766`, and pass the OAuth Authorization header. The connector's loopback listener keeps plaintext HTTP on that host. The proxy should use the organisation's access logging and traffic controls and exclude credentials. Token errors return an OAuth challenge or a forbidden response. An unavailable identity provider yields a temporary failure.

## Accept the phone journey

1. From the intended workspace, connect the approved HTTPS MCP resource and sign in. Open the phone app, ask the briefing question and check that the assistant called `hansard_my_briefing`.
2. Verify that the response identifies the publication and dates and that two exact links open the cited Hansard contributions. Ask which contributions were the user's own, then test a changed date range.
3. Sign in with a second test identity bound to a different member and portfolio. Check the identity and results change with the token. Confirm that an unauthenticated request and a token for another resource are denied.

Claude documents cloud-hosted access to remote MCP connectors from its mobile clients. The HTTPS endpoint must be reachable by the approved provider. ChatGPT custom MCP setup is documented on web. Test the workspace-approved connection in the intended phone Voice mode as a separate acceptance step. If a provider's native phone app cannot use the connector, an organisation-controlled voice client can call the same MCP tool once its sign-in and speech stack are available. [Claude remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) · [ChatGPT custom MCP setup](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt) · [ChatGPT Voice](https://help.openai.com/en/articles/20001274-chatgpt-voice)
