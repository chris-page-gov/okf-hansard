"""Prepare the Microsoft 365 voice trial from the local Hansard MCP server."""

from datetime import date
from html import escape
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

from people import member_career_url

ROOT = Path.cwd()
RELEASE = ROOT / "releases/current"
SEED = json.loads((RELEASE / "example-related-evidence.json").read_bytes())
ANCHOR = SEED["anchor"]["id"]
NAME = "Microsoft 365 outage"
SERVER = ROOT / "scripts/mcp_server.py"


def rpc(method, params, number):
    return {"jsonrpc": "2.0", "id": number, "method": method, "params": params}


requests = [rpc("initialize", {
    "protocolVersion": "2025-11-25", "clientInfo": {"name": "hansard-voice-trial", "version": "1"},
    "capabilities": {},
}, 1), {"jsonrpc": "2.0", "method": "notifications/initialized"}]
for number, (name, arguments) in enumerate([
    ("hansard_read_passage", {"contribution": ANCHOR, "limit": 250}),
    ("hansard_trace", {"contribution": ANCHOR, "entity": "m365", "limit": 30, "include_view": True}),
    ("hansard_trace", {"contribution": ANCHOR, "entity": "microsoft", "limit": 3}),
    ("hansard_trace", {"contribution": ANCHOR, "entity": "cabinet-office", "limit": 3}),
], 2):
    requests.append(rpc("tools/call", {"name": name, "arguments": arguments}, number))
inputs = "".join(json.dumps(req) + "\n" for req in requests)
run = subprocess.run([sys.executable, str(SERVER)], input=inputs, text=True, capture_output=True,
                     cwd=ROOT, check=True, timeout=35)
rows = [json.loads(line) for line in run.stdout.splitlines()]
assert rows[0]["result"]["protocolVersion"] == "2025-11-25"
if any(row.get("error") or row["result"].get("isError") for row in rows):
    raise RuntimeError("The MCP server reported a query failure.")
source, focus, microsoft, cabinet = [row["result"]["structuredContent"] for row in rows[1:]]
assert source["status"] == "matches recorded version"
assert all(p["context_id"] == focus["context_id"] for p in [microsoft, cabinet])
assert focus["next_offset"] is None and len(focus["items"]) == focus["total"]
nodes = json.loads((RELEASE / "okf-bundle.json").read_bytes())["corpora"]["hansard"]
people = [{"label": nodes["nodes"][edge["target"]]["title"], "url": edge["evidence"][0]["url"]}
          for edge in nodes["relationships"] if edge["source"] == ANCHOR and edge["kind"] == "is attributed to"]
assert len(people) == 1 and people[0]["label"] == "Ian Murray"
sample = {"schema":"hansard-voice-trial.v1", "title":NAME, "context_id":focus["context_id"],
          "anchor":focus["anchor"], "speaker":people[0], "speaker_member_id":source["member_id"],
          "source_value_sha256":source["source_value_sha256"], "coverage":focus["coverage"],
          "theme":focus["selected_entity"], "earlier_mentions":focus["items"],
          "organisations":[{"entity":p["selected_entity"], "examples":p["items"]}
                           for p in [microsoft, cabinet]]}
(RELEASE / "voice-microsoft-365.json").write_text(json.dumps(sample, ensure_ascii=False, indent=2)+"\n",
                                                 encoding="utf-8")


def uk_day(raw):
    value = date.fromisoformat(raw)
    return f"{value.day} {value:%B %Y}"


def link(url, label):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "hansard.parliament.uk":
        raise ValueError(f"Expected a Hansard source URL: {url}")
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def evidence_list(items):
    return "\n".join(f"<li>{link(row['url'], uk_day(row['date']) + ' · ' + row['house'])}</li>" for row in items)


org_cards = "\n".join(
    f"<section><h3>{escape(org['entity']['label'])}</h3>"
    f"<p>{org['entity']['earlier']:,} earlier contribution records match this name or an alias.</p>"
    f"<details><summary>Three recent examples</summary><ul>{evidence_list(org['examples'])}</ul></details></section>"
    for org in sample["organisations"]
)
markup = f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{NAME} | A week in Parliament</title>
<style>
  :root {{color-scheme:light;background:#f5f6f2;color:#202722;font:1rem/1.55 system-ui,sans-serif}}
  body {{margin:0;border-top:6px solid #255a42}}
  main {{max-width:52rem;padding:clamp(1rem,4vw,3rem);margin:auto}}
  h1 {{margin:0;font-size:clamp(2rem,6vw,3.25rem);line-height:1.1;letter-spacing:-.035em}}
  h2 {{margin:1.7rem 0 .6rem;line-height:1.2}}
  h3 {{margin:0}}
  p {{max-width:68ch}}
  .lede {{color:#41554a;margin:.6rem 0 1.2rem}}
  .cards {{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr));gap:.8rem}}
  .cards section {{background:#fff;border:1px solid #c4d0c7;border-radius:.45rem;padding:1rem}}
  .cards p {{margin:.4rem 0}}
  a {{color:#174d3c;text-underline-offset:.18em}}
  summary {{cursor:pointer;color:#174d3c}}
  :focus-visible {{outline:3px solid #8a5800;outline-offset:3px}}
  li {{margin:.27rem 0}}
  .note {{border-left:3px solid #9db7a6;padding-left:.75rem;color:#3f5147}}
</style>
</head>
<body>
<main>
<h1>{NAME}</h1>
<p class="lede">House of Commons · {uk_day(focus['anchor']['date'])}</p>
<p>{link(focus['anchor']['url'], 'Read the original statement in Hansard')}</p>
<h2>People</h2>
<p><a href="{member_career_url(sample['speaker_member_id'])}">{escape(people[0]['label'])}</a> {link(people[0]['url'], 'made the statement')} as Minister for Creative Industries, Media and Online Safety.</p>
<h2>Organisations</h2>
<p>The statement mentions Microsoft and the Cabinet Office.</p>
<div class="cards">{org_cards}</div>
<h2>Earlier mentions of Microsoft 365</h2>
<p>Open any of the {focus['total']} earlier contributions that match Microsoft 365 or a recorded alias.</p>
<ol>{evidence_list(focus['items'])}</ol>
<p class="note">The historical index starts on {uk_day(focus['coverage']['extension_from'])}. Names and aliases can match other parliamentary business.</p>
</main>
</body>
</html>
"""
(RELEASE / "voice-microsoft-365.html").write_text(markup, encoding="utf-8")
print(json.dumps({"speaker": people[0]["label"], "organisations": [a["entity"]["label"] for a in sample["organisations"]],
                  "earlier_mentions": focus["total"], "source_version": source["status"],
                  "earliest_match": focus["items"][-1]["date"], "latest_match": focus["items"][0]["date"]}))
