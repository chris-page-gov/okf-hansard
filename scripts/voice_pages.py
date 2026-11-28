"""Publish a portable phone entry point for the Hansard collection."""

from html import escape
from pathlib import Path
import shutil
from urllib.parse import urlencode

from capture import dump, sha
from evidence_index import REPOSITORY_INDEX
from hansard_access import BUNDLE_ID, HOME, NOVEMBER, read, snapshot_id
from mcp_skills import CONTRACT, NAME as SKILL_NAME, SKILL, stage_skill
from okf_core import CORE_SPEC, CORE_VERSION
from voice_evidence import CONCEPT, EVIDENCE, human_date as day, write_evidence


PAGE = Path(__file__).resolve().parents[1] / "docs/pages/ask.js"
PROMPT = (f"Read HANSARD-EVIDENCE.md directly from the main branch of chris-page-gov/okf-hansard. "
          f"{REPOSITORY_INDEX}\n"
          "Give the verified capture-through date and snapshot from the file. "
          "Use the excerpts and exact Hansard links in the file to answer. "
          "If you cannot open it, ask me to paste its text.")


VOICE = read(CONTRACT)
RETRIEVAL = CONTRACT.name
SKILL_PATH = f"skills/{SKILL_NAME}/SKILL.md"
DOCS = "https://github.com/chris-page-gov/okf-hansard/blob/main/docs/"
LAUNCH = (f"When I say ‘{VOICE['alias']}’, use the approved Hansard connection and the read-okf-plus "
          f"skill if available. Otherwise open {VOICE['collection']}. "
          "Check the verified snapshot and latest sitting before answering. Use my context to choose public topics "
          "and send only the terms and dates needed. Ask if my portfolio is unclear. Give a short spoken answer "
          "and put the exact Hansard links and a graph or timeline link in chat. "
          f"If you cannot read the collection, try {REPOSITORY_INDEX} or ask me for pasted evidence. "
          "Explain the scope of the evidence you could access.")
WORKED_QUESTION = ("What changed in the discussion of the Synergy programme? "
                   "Show the source passages and give me the timeline.")


def publish_retrieval(site):
    stage_skill(site)
    files = {}
    for relative in SKILL["files"]:
        path = f"skills/{SKILL_NAME}/{relative}"
        raw = (site / path).read_bytes()
        files[relative] = {"url": NOVEMBER + path, "bytes": len(raw), "sha256": sha(raw)}
    dump(site / RETRIEVAL, {**VOICE, "skill": {**SKILL, "public_files": files}})


def publish_voice(site, release, capture=None):
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

    evidence = {}
    if capture is not None and CONCEPT in history["entities"]:
        write_evidence(site, release, capture, coverage, history, snapshot)
        entry = reference(EVIDENCE)
        url = entry["url"] + "?" + urlencode({"snapshot": snapshot})
        evidence[CONCEPT] = {**entry, "url": url, "format": "text/plain", "snapshot": snapshot}

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
            "entrypoints": {**({"contribution_context": reference("context/index.json")}
                               if (site / "context/index.json").is_file() else {}),
                            "okf_index": reference("okf/index.md"), "coverage": reference("coverage.json"),
                            "history_index": reference("history/index.json"), "timeline": reference("history.html"),
                            "semantic_graph": reference("okf-bundle.yamlld.gz")},
            **({"date_templates": {"described_by": NOVEMBER + "context/index.json",
                                   "month": NOVEMBER + "context/months/{month}.json",
                                   "range": NOVEMBER + "context/ranges/{start}/{end}.json"}}
               if (site / "context/index.json").is_file() else {}),
            "concept_index": NOVEMBER + "concepts.json", "voice_quick_start": NOVEMBER + "ask.md",
            "repository_evidence": REPOSITORY_INDEX,
            "voice_retrieval": NOVEMBER + RETRIEVAL,
            **({"voice_evidence": evidence} if evidence else {}),
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
    publish_retrieval(site)
    write_finder(site, scope, evidence)
    shutil.copyfile(PAGE, site / "ask.js")


def refresh_finder(site):
    """Re-render a verified published finder without reopening its capture."""
    directory = read(site / "hansard.json")
    bundle = directory["bundles"][0]
    bundle["repository_evidence"] = REPOSITORY_INDEX
    bundle["voice_retrieval"] = NOVEMBER + RETRIEVAL
    publish_retrieval(site)
    write_finder(site, directory["scope"], bundle.get("voice_evidence", {}))
    dump(site / "hansard.json", directory)


def write_finder(site, scope, evidence):
    question = "Summarise the selected evidence from the latest sitting."
    evidence_link, evidence_details = "", ""
    if entry := evidence.get(CONCEPT):
        raw = (site / EVIDENCE).read_bytes()
        if len(raw) != entry["bytes"] or sha(raw) != entry["sha256"]:
            raise ValueError("The finder requires its verified Synergy evidence.")
        content, url = raw.decode("utf-8"), entry["url"]
        question = ("Explain what Synergy is, how the discussion changed, and which statements were commitments. "
                    "Distinguish historical alias matches from captured contributions.")
        evidence_link = f"- [Read the Synergy evidence and passages]({url})\n"
        evidence_details = f"""<p><a href="{escape(url, quote=True)}">Read the Synergy evidence and passages</a></p>
<details><summary>Copy the Synergy evidence if your AI cannot open the link</summary>
<label for="synergy-evidence">Synergy evidence</label>
<textarea id="synergy-evidence" readonly rows="8">{escape(content)}</textarea>
<button type="button" data-copy="synergy-evidence">Copy Synergy evidence</button>
</details>"""
    prompt = PROMPT + "\n" + question
    markdown_prompt = "\n".join("> " + line for line in prompt.splitlines())

    (site / "ask.md").write_text(f"""# Ask your AI about Hansard

{scope}

## Use the full collection

Paste the following instruction into your assistant once. If your assistant supports saved preferences, you can ask it to remember the shortcut. Otherwise paste it in each new chat. Switch to voice and say “{VOICE['alias']}”.

> {LAUNCH}

Try asking “{WORKED_QUESTION}”

## Use the small evidence index

When the assistant cannot open the full collection, paste this prompt. If it cannot open GitHub either, paste the selected evidence from the finder.

{markdown_prompt}

In the contribution timeline, select a turn and choose “Show this contribution in context”.
For voice, ask “Who spoke around this contribution? Cite the turns you used.”


- [Open the GitHub evidence index]({REPOSITORY_INDEX})
{evidence_link}- [Find and copy evidence]({NOVEMBER}ask.html)
- [Hansard collection directory]({NOVEMBER}hansard.json)
- [Capture and historical coverage]({NOVEMBER}coverage.json)
- [OKF 0.3 source index]({NOVEMBER}okf/index.md)
- [Read the OKF+ skill]({NOVEMBER}{SKILL_PATH})
- [Retrieval contract]({NOVEMBER}{RETRIEVAL})
- [Full phone demonstration]({DOCS}mobile-demonstration.md)
- [Learn OKF 0.3 with Hansard]({DOCS}learn-hansard-okf.md)
""", encoding="utf-8")
    (site / "ask.html").write_text(f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ask your AI about Hansard</title><link rel="icon" href="data:,">
<link rel="stylesheet" href="site.css"><link rel="describedby" href="hansard.json" type="application/json">
<script src="ask.js" defer></script>
</head>
<body><main class="guide finder">
<nav aria-label="Hansard"><a href="./">November in Parliament</a></nav>
<h1>Ask your AI about Hansard</h1>
<p id="coverage-summary">{escape(scope)}</p>
<h2>Try it on your phone</h2>
<ol>
<li>Copy the full collection instructions into your own AI chat. Save them as a preference if your app supports it.</li>
<li>Start voice and say “{escape(VOICE['alias'])}”. Ask it to confirm the snapshot and latest sitting.</li>
<li>Ask a question, then open a cited contribution and its graph or timeline from the chat.</li>
</ol>
<label for="launch-prompt">Full collection instructions</label>
<textarea id="launch-prompt" readonly rows="7">{escape(LAUNCH)}</textarea>
<button type="button" data-copy="launch-prompt">Copy full collection instructions</button>
<p>Try “{escape(WORKED_QUESTION)}”</p>
<p><a href="{DOCS}mobile-demonstration.md">Follow the full phone demonstration</a> · <a href="{DOCS}learn-hansard-okf.md">Learn OKF 0.3 with Hansard</a></p>
<h2>If the full collection is unavailable</h2>
<p>Copy the GitHub prompt to use the small evidence index. You can also paste evidence directly from this page.</p>
<p><a href="{REPOSITORY_INDEX}">Open the GitHub evidence index</a></p>
<label for="prompt">GitHub prompt</label>
<textarea id="prompt" readonly rows="6">{escape(prompt)}</textarea>
<button type="button" data-copy="prompt">Copy GitHub prompt</button>
{evidence_details}
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
<textarea id="evidence" readonly rows="10"></textarea>
<button type="button" data-copy="evidence">Copy evidence</button>
</section>
<p><a href="ask.md">Plain-text guide</a> · <a href="hansard.json">Collection directory</a> · <a href="history.html">Contribution timeline</a> · <a href="coverage.json">Coverage</a> · <a href="{SKILL_PATH}">Read the OKF+ skill</a> · <a href="{RETRIEVAL}">Retrieval contract</a></p>
</main></body></html>
""", encoding="utf-8")
