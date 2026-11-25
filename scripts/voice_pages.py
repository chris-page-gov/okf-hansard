"""Publish a portable phone entry point for the Hansard collection."""

from datetime import date
from html import escape
from pathlib import Path
import shutil

from capture import dump, sha
from hansard_access import BUNDLE_ID, HOME, NOVEMBER, read, snapshot_id
from okf_core import CORE_SPEC, CORE_VERSION


PAGE = Path(__file__).resolve().parents[1] / "docs/pages/ask.js"
PROMPT = (f"Use the Hansard OKF bundle at {NOVEMBER}hansard.json. "
          "Tell me the dates covered, the historical search window and the known gaps. "
          "Then trace mentions of the Synergy programme and give me exact Hansard links and the timeline. "
          "Say which evidence files you opened.")


def day(value):
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {parsed:%B %Y}"


def publish_voice(site, release):
    history = read(site / "history/index.json")
    coverage = read(site / "coverage.json")
    profile = read(release / "analysis-profile.json")["entities"]
    descriptor = read(site / "graph/okf-explorer.json")
    snapshot = snapshot_id(site, descriptor)
    dates = history["days"]
    backfill = coverage["backfill"]
    older = history.get("older_archive")
    scope = (f"{coverage['contributions']:,} contributions from Commons and Lords sittings, "
             f"{day(min(dates))} to {day(max(dates))}. Historical searches for configured entities "
             f"cover {day(backfill['from'])} to {day(backfill['through'])} inclusive.")
    if older:
        earliest = min(row[0] for row in older["ranges"].values())
        latest = max(row[1] for row in older["ranges"].values())
        scope += f" The older indexed archive spans {day(earliest)} to {day(latest)} and lists {older['source_gaps']} source gaps."
    scope += " Counts of historical matches depend on the configured names and aliases."
    def reference(name):
        raw = (site / name).read_bytes()
        return {"url": NOVEMBER + name, "bytes": len(raw), "sha256": sha(raw)}

    dump(site / "hansard.json", {
        "schema": "okf-public-access-directory.v1", "title": "Hansard", "locale": "en-GB",
        "time_zone": "Europe/London", "scope": scope, "bundles": [{
            "id": BUNDLE_ID, "title": "Hansard", "snapshot": snapshot,
            "declared_okf_version": CORE_VERSION, "core_specification": CORE_SPEC,
            "home": NOVEMBER + "ask.html", "descriptor": NOVEMBER + "graph/okf-explorer.json",
            "descriptor_sha256": reference("graph/okf-explorer.json")["sha256"],
            "descriptor_schema": descriptor["schema"], "visibility": "public",
            "repository": "https://github.com/chris-page-gov/okf-hansard",
            "access_directory": NOVEMBER + "okf-public-access.json",
            "capture": {"from": min(dates), "through": max(dates), "contributions": coverage["contributions"],
                        "sitting_dates": dates},
            "historical_search": {key: backfill[key] for key in ("from", "through", "method", "entities", "complete", "exceptions")},
            "older_archive": older,
            "entrypoints": {"okf_index": reference("okf/index.md"), "coverage": reference("coverage.json"),
                            "history_index": reference("history/index.json"), "timeline": reference("history.html"),
                            "semantic_graph": reference("okf-bundle.yamlld.gz")},
            "concept_index": NOVEMBER + "concepts.json", "voice_quick_start": NOVEMBER + "ask.md",
            "historical_exports": NOVEMBER + "historical-downloads.html",
            "mention_resources": {"recent_and_search": NOVEMBER + "history/{concept}.json",
                                  "archive": NOVEMBER + "history/{concept}.archive.json.gz",
                                  "older_archive": NOVEMBER + "history/{concept}.older.json.gz"},
            "views": {"week_examples": HOME + "demo.html", "worked_evidence": HOME + "okf/index.md"},
        }],
    })
    dump(site / "concepts.json", {"snapshot": snapshot, "concepts": {
        key: {**record, "aliases": profile.get(key, {}).get("aliases", [])}
        for key, record in history["entities"].items()
    }})
    (site / "ask.md").write_text(f"""# Ask your AI about Hansard

{scope}

1. Open your AI assistant. Paste the prompt below into its chat and start voice if available.
2. If the assistant cannot open the links, use the evidence finder and paste its plain-text evidence into the same chat.
3. Check that the answer cites specific Hansard contributions and gives the date range used.

> {PROMPT}

- [Find and copy evidence]({NOVEMBER}ask.html)
- [Hansard collection directory]({NOVEMBER}hansard.json)
- [Capture and historical coverage]({NOVEMBER}coverage.json)
- [OKF 0.3 source index]({NOVEMBER}okf/index.md)
""", encoding="utf-8")
    (site / "ask.html").write_text(f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ask your AI about Hansard</title><link rel="icon" href="data:,">
<link rel="stylesheet" href="site.css"><link rel="describedby" href="hansard.json" type="application/json">
<script src="ask.js" defer></script>
</head>
<body><main class="guide">
<nav aria-label="Hansard"><a href="./">November in Parliament</a></nav>
<h1>Ask your AI about Hansard</h1>
<p id="coverage-summary">{escape(scope)}</p>
<h2>Try it on your phone</h2>
<p>Copy the prompt into your AI chat, then use voice if your app offers it. If the app cannot open links, find a concept here and copy its evidence instead. The finder opens without signing in.</p>
<label for="prompt">Prompt to copy</label>
<textarea id="prompt" readonly rows="5" style="display:block;width:100%;font:inherit">{escape(PROMPT)}</textarea>
<button type="button" data-copy="prompt">Copy prompt</button>
<h2>Find and copy evidence</h2>
<form id="lookup">
<label for="concept">Concept name or alias</label>
<input id="concept" value="Synergy programme" required>
<button>Find mentions</button>
</form>
<p id="status" role="status"></p><p id="choices"></p>
<section id="results" hidden>
<p id="count"></p><p id="timeline"></p><ol id="links"></ol>
<button type="button" id="previous">Previous matches</button><button type="button" id="next">Next matches</button>
<p><label for="evidence">Evidence to paste into your AI chat</label></p>
<textarea id="evidence" readonly rows="10" style="display:block;width:100%;font:inherit"></textarea>
<button type="button" data-copy="evidence">Copy evidence</button>
</section>
<p><a href="ask.md">Plain-text guide</a> · <a href="hansard.json">Collection directory</a> · <a href="history.html">Contribution timeline</a> · <a href="coverage.json">Coverage</a></p>
</main></body></html>
""", encoding="utf-8")
    shutil.copyfile(PAGE, site / "ask.js")
