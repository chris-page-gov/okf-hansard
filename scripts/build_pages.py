"""Stage the allowlisted, verified Hansard pilot for GitHub Pages."""

import argparse
from datetime import date
import gzip
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import quote, urlencode, urlparse

from capture import sha
from build import PAGES_BLOB_LIMIT
from build_explorer_graph import build as build_explorer_graph, dataset_route
from demo import timeline_route, write_demo
from discovery import HEAD_LINKS, write_discovery
from history_pages import write as write_history
from okf_core import CORE_VERSION
from people import member_career_url
from query import DEFAULT_DB

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://chris-page-gov.github.io/okf-hansard/"
READER = "https://chris-page-gov.github.io/okf-explorer/explore/"
SOURCE = "https://github.com/chris-page-gov/okf-hansard"
LICENCE = "https://www.parliament.uk/site-information/copyright/open-parliament-licence/"
ATTRIBUTION = "Contains Parliamentary information licensed under the Open Parliament Licence v3.0."
BUILD_CREDIT = "Built with OpenAI Codex, using GPT-6.2 Sol with Ultra reasoning."
GUIDES = {
    "beginners.html": "Beginner’s guide",
    "methodology.html": "Methodology and prompts",
}
PUBLIC_FILES = (
    "okf-bundle.json",
    "okf-bundle.yamlld",
    "example-earlier-mentions.yamlld",
    "voice-microsoft-365.html",
    "voice-microsoft-365.json",
)
DEMO_ASSETS = ("demo.html", "demo.js", "site.css")
LOCAL_TEXT = re.compile(rb"(?:/Users/[a-z0-9._-]+/|/Volumes/[a-z0-9._-]+/|127\.0\.0\.1:8765|localhost:8765)", re.I)


def fmt_date(value):
    day = date.fromisoformat(value)
    return f"{day.day} {day:%B %Y}"


def source_link(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "hansard.parliament.uk":
        raise ValueError("Expected an official Hansard evidence link.")
    return url


def explorer_record_url(asset, view, route):
    query = urlencode({"bundle": SITE + asset, "view": view})
    return f"{READER}?{query}#{quote(route)}"


def voice_explorer_links(raw, sample):
    anchor = sample["anchor"]
    graph = explorer_record_url("graph/okf-explorer.json", "graph", dataset_route(anchor["id"]))
    timeline = explorer_record_url("demo-timeline.json", "timeline", timeline_route(source_link(anchor["url"])))
    links = (f'<p><a href="{escape(graph, quote=True)}">Open the statement graph in OKF Explorer</a>'
             f' · <a href="{escape(timeline, quote=True)}">Open the demo timeline in OKF Explorer</a></p>').encode()
    if links in raw:
        return raw
    heading = b"<h2>People</h2>"
    if raw.count(heading) != 1:
        raise ValueError("The companion Explorer links could not be placed.")
    return raw.replace(heading, links + b"\n" + heading, 1)


def voice_speaker_links(raw, sample):
    speaker = sample["speaker"]
    label = escape(speaker["label"])
    statement = escape(source_link(speaker["url"]), quote=True)
    legacy = f'<a href="{statement}">{label}</a>'.encode()
    biography = f'<a href="{member_career_url(sample["speaker_member_id"])}">{label}</a>'.encode()
    phrase = b" made the statement "
    linked_phrase = f' <a href="{statement}">made the statement</a> '.encode()
    updated = biography + linked_phrase
    for previous in (legacy + phrase, biography + phrase):
        if raw.count(previous) == 1 and updated not in raw:
            return raw.replace(previous, updated, 1)
    if raw.count(updated) == 1:
        return raw
    raise ValueError("The companion speaker and statement links could not be identified.")


def voice_biography_status(raw):
    timing = (b'<p class="note">In one demo test, the UK Parliament biography took '
              b'about a minute to open.</p>')
    status = (
        b'<div class="note"><span id="biography-status" role="status"></span>'
        b'<span id="biography-elapsed" role="timer" aria-live="off"></span></div>'
    )
    feedback = timing + b"\n" + status
    if feedback in raw:
        return raw
    if status in raw:
        return raw.replace(status, feedback, 1)
    section = b"<h2>Organisations</h2>"
    if raw.count(section) != 1 or raw.count(b"</body>") != 1:
        raise ValueError("The companion biography status could not be placed.")
    script = """
<script>
const biography = document.querySelector('a[href^="https://members.parliament.uk/member/"]');
const biographyStatus = document.getElementById("biography-status");
const biographyElapsed = document.getElementById("biography-elapsed");
let stopwatch;
biography.addEventListener("click", (event) => {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey ||
      event.shiftKey || event.altKey) return;
  event.preventDefault();
  const started = performance.now();
  window.clearInterval(stopwatch);
  biographyStatus.textContent =
    "Waiting for the UK Parliament website to open " + biography.textContent.trim() + "’s biography…";
  const showElapsed = () => {
    const seconds = Math.floor((performance.now() - started) / 1000);
    biographyElapsed.textContent = " " + seconds + (seconds === 1 ? " second elapsed" : " seconds elapsed");
  };
  showElapsed();
  stopwatch = window.setInterval(showElapsed, 1000);
  // Give the current page time to show the status before handing off.
  window.setTimeout(() => window.location.assign(biography.href), 100);
});
window.addEventListener("pagehide", () => window.clearInterval(stopwatch));
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    biographyStatus.textContent = "";
    biographyElapsed.textContent = "";
  }
});
</script>
"""
    return raw.replace(section, feedback + b"\n" + section, 1).replace(
        b"</body>", script.encode() + b"</body>", 1)


def voice_match_period(sample):
    days = [item["date"] for item in sample["earlier_mentions"]]
    first, last = fmt_date(min(days)), fmt_date(max(days))
    return f"from {first} to {last}" if first != last else f"on {first}"


def voice_match_note(sample):
    return (f'<p class="note">The listed matches date {voice_match_period(sample)}. '
            'See the <a href="coverage.json">published coverage</a> for the dates searched. '
            'A name or alias match can relate to other parliamentary business.</p>')


def voice_coverage_note(raw, sample):
    note = voice_match_note(sample).encode()
    if raw.count(note) == 1:
        return raw
    legacy = (f'<p class="note">The historical index starts on {fmt_date(sample["coverage"]["extension_from"])}. '
              'Names and aliases can match other parliamentary business.</p>').encode()
    if raw.count(legacy) != 1:
        raise ValueError("The companion’s archive note could not be identified.")
    return raw.replace(legacy, note, 1)


def voice_note(sample):
    rows = [
        "# Microsoft 365 outage",
        "",
        "House of Commons, 16 November 2026",
        "",
        f"Ian Murray made the statement as Minister for Creative Industries, Media and Online Safety. "
        f"[Original statement]({source_link(sample['anchor']['url'])})",
        "",
        "## Organisations",
        "",
        "The statement mentions Microsoft and the Cabinet Office. The counts below group literal name "
        "or alias matches across earlier contributions.",
        "",
    ]
    for org in sample["organisations"]:
        label = org["entity"]["label"]
        count = org["entity"]["earlier"]
        links = ", ".join(f"[{fmt_date(row['date'])} ({row['house']})]({source_link(row['url'])})"
                          for row in org["examples"])
        rows.append(f"- {label} has {count:,} earlier matched contributions. Recent examples include {links}.")
    total = len(sample["earlier_mentions"])
    rows += ["", "## Earlier mentions of Microsoft 365", "",
             f"The index found {total} earlier contributions matching the product name or a recorded alias.", ""]
    for row in sample["earlier_mentions"]:
        rows.append(f"- [{fmt_date(row['date'])} · {row['house']}]({source_link(row['url'])})")
    rows += ["", f"The listed matches date {voice_match_period(sample)}. "
             f"[Published coverage]({SITE}coverage.json) gives the dates searched. "
             "A name or alias match can relate to other parliamentary business.",
             "", f"[Companion view]({SITE}voice-microsoft-365.html)", "",
             f"{ATTRIBUTION} [Licence]({LICENCE})", ""]
    return "\n".join(rows)


def index_page(coverage, semantic_file, graph_anchor):
    by_day = coverage["week_contributions_by_day"]
    days = sorted(by_day)
    dates = (fmt_date(days[0]) if len(days) == 1
             else f"{fmt_date(days[0])} to {fmt_date(days[-1])}")
    total = sum(by_day.values())
    assertions = coverage["pilot_graph"]["assertions"]
    facets = coverage["pilot_graph"]["visible_facet_declarations"]
    oldest = fmt_date(coverage["archive"]["ranges"]["Commons"]["from"])
    history_link = ('<li><a href="history.html">Browse earlier mentions by contribution and entity</a></li>'
                    if "history_backfill" in coverage else "")
    query = urlencode({"bundle": SITE + "okf-bundle.json"})
    focused_graph = explorer_record_url("graph/okf-explorer.json", "graph", dataset_route(graph_anchor))
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="A source-linked Hansard OKF+ pilot covering both Houses from {dates}.">
<title>A week in Parliament | Hansard OKF+</title>
<link rel="stylesheet" href="site.css">
{HEAD_LINKS}
</head>
<body>
<main>
<p class="date">House of Commons and House of Lords · {dates}</p>
<h1>A week in Parliament</h1>
<p class="intro">Follow a Hansard contribution through related people, offices, organisations, places and legislation. This experimental OKF+ bundle contains {total:,} passages and {assertions:,} source-linked relationships.</p>
<p class="actions"><a class="primary" href="demo.html?example=railways-bill">Follow the Railways Bill</a>
<a href="use-with-ai.html">Use Hansard with AI</a>
<a href="{escape(READER + '?' + query, quote=True)}">Open in OKF Explorer</a>
<a href="beginners.html">Beginner’s guide</a></p>
<div class="grid">
<section>
<h2>Commons statement on the Microsoft 365 outage</h2>
<p>Start with Ian Murray’s Commons statement and follow the named organisations and 19 earlier mentions back to Hansard.</p>
<ul>
<li><a href="{escape(focused_graph, quote=True)}">Open the focused graph in Explorer</a></li>
<li><a href="voice-microsoft-365.html">Open the companion view</a></li>
<li><a href="voice-microsoft-365.md">Read the evidence in plain text</a></li>
<li><a href="voice-microsoft-365.json">Get the evidence as JSON</a></li>
</ul>
</section>
<section>
<h2>Download the bundle</h2>
<p>Use {facets} facets in Explorer or reuse the evidence-bearing YAML-LD graph.</p>
<ul>
<li><a href="okf-bundle.json">Explorer bundle (JSON)</a></li>
<li><a href="{semantic_file}">Semantic graph ({"YAML-LD, gzip" if semantic_file.endswith(".gz") else "YAML-LD"})</a></li>
<li><a href="example-earlier-mentions.yamlld">Microsoft 365 history slice (YAML-LD)</a></li>
{history_link}
<li><a href="checksums.json">File checksums</a></li>
</ul>
</section>
<section>
<h2>Historical coverage</h2>
<p>The local index reaches {oldest}. The site includes a week snapshot, coverage results and a worked example from the wider index.</p>
<ul>
<li><a href="coverage.json">Coverage and verification</a></li>
<li><a href="methodology.html">Methodology and prompts</a></li>
<li><a href="{SOURCE}">Source repository and research notes</a></li>
</ul>
</section>
</div>
<footer>
<p>{BUILD_CREDIT}</p>
<p>{ATTRIBUTION} <a href="{LICENCE}">Licence and exclusions</a>.</p>
<p>This independent pilot links to the official record. Earlier matches use a fixed vocabulary of names and aliases.</p>
</footer>
</main>
</body>
</html>
"""


def guide_page(name, title):
    content = (ROOT / "docs" / "pages" / name).read_text(encoding="utf-8")
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | A week in Parliament</title>
<link rel="stylesheet" href="site.css">
</head>
<body>
<main class="guide">
<nav aria-label="Project"><a href="./">A week in Parliament</a></nav>
<h1>{escape(title)}</h1>
{content}
<footer>
<p>{BUILD_CREDIT}</p>
<p>{ATTRIBUTION} <a href="{LICENCE}">Licence and exclusions</a>.</p>
</footer>
</main>
</body>
</html>
"""


def stage(release, coverage_path, destination, database=DEFAULT_DB, baseline_demo=None, history_cache=None,
          *, older_database=None):
    final = json.loads(coverage_path.read_bytes())
    receipt = json.loads((release / "receipt.json").read_bytes())
    if final["local_release"] != release.resolve().name or not final["pilot_graph"]["passed"]:
        raise ValueError("The public snapshot must match the verified release.")
    if final["pilot_graph"].get("okf_core", {}).get("version") != CORE_VERSION:
        raise ValueError("The public snapshot requires verified OKF 0.3 source.")
    sample = json.loads((release / "voice-microsoft-365.json").read_bytes())
    if not sample["earlier_mentions"] or len(sample["earlier_mentions"]) != sample["theme"]["earlier"]:
        raise ValueError("The public example requires the verified Microsoft 365 evidence.")
    destination.mkdir(parents=True, exist_ok=False)
    semantic_file = "okf-bundle.yamlld"
    for name in PUBLIC_FILES:
        raw = (release / name).read_bytes()
        if LOCAL_TEXT.search(raw):
            raise ValueError(f"Local address or path in {name}")
        expected = receipt["artifacts"].get(name)
        if expected and (sha(raw) != expected["sha256"] or len(raw) != expected["bytes"]):
            raise ValueError(f"Published bytes would differ from the verified source for {name}")
        if name == "voice-microsoft-365.html":
            raw = voice_biography_status(voice_speaker_links(raw, sample))
            raw = voice_explorer_links(voice_coverage_note(raw, sample), sample)
            note = f'<p>{ATTRIBUTION} <a href="{LICENCE}">Licence and exclusions</a>.</p>'
            raw = raw.replace(b"</main>", note.encode() + b"\n</main>")
        if name == semantic_file and len(raw) >= PAGES_BLOB_LIMIT:
            semantic_file += ".gz"
            raw = gzip.compress(raw, compresslevel=6, mtime=0)
            name = semantic_file
        (destination / name).write_bytes(raw)
    public_coverage = {
        "pilot_graph": final["pilot_graph"],
        "week_contributions_by_day": final["week_contributions_by_day"],
        "archive": {k: v for k, v in final["archive"].items() if k != "path"},
        "collector": final["collector"],
        "supplemental_searches": final["supplemental_searches"],
        "coverage_statement": final["coverage_statement"],
        "observed_at": final["observed_at"],
        "source_commit": final["code_commit"],
        "licence": {"url": LICENCE, "attribution": ATTRIBUTION},
    }
    if "history_backfill" in final:
        public_coverage["history_backfill"] = final["history_backfill"]
        write_history(release, destination, database, history_cache or destination.parent / "history-cache",
                      older_database=older_database)
        if older_database:
            history_index = json.loads((destination / "history/index.json").read_bytes())
            public_coverage["older_archive"] = history_index.get("older_archive")
    (destination / "coverage.json").write_text(json.dumps(public_coverage, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    build_explorer_graph(release, destination / "graph")
    (destination / "index.html").write_text(index_page(public_coverage, semantic_file, sample["anchor"]["id"]), encoding="utf-8")
    for name, title in GUIDES.items():
        (destination / name).write_text(guide_page(name, title), encoding="utf-8")
    for name in DEMO_ASSETS:
        raw = (ROOT / "docs" / "pages" / name).read_bytes()
        if name == "demo.html" and "history_backfill" in final:
            raw = raw.replace(b"</nav>", b'  <a href="history.html">Browse earlier mentions</a>\n</nav>', 1)
        (destination / name).write_bytes(raw)
    write_demo(release, destination, public_coverage, database, baseline_demo)
    (destination / "voice-microsoft-365.md").write_text(voice_note(sample), encoding="utf-8")
    write_discovery(destination, "A week in Parliament", public_coverage["week_contributions_by_day"],
                    public_coverage["observed_at"], semantic_file)
    (destination / ".nojekyll").touch()
    manifest = {}
    for file in sorted(path for path in destination.rglob("*") if path.is_file()):
        relative = file.relative_to(destination).as_posix()
        raw = file.read_bytes()
        if LOCAL_TEXT.search(raw):
            raise ValueError(f"Local address or path in staged asset {relative}")
        if len(raw) >= PAGES_BLOB_LIMIT:
            raise ValueError(f"Asset exceeds the GitHub blob limit: {relative}")
        manifest[relative] = {"sha256": sha(raw), "bytes": len(raw)}
    (destination / "checksums.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Staged {len(manifest)} public assets and a checksum catalogue.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", type=Path, default=ROOT / "releases/current")
    p.add_argument("--coverage", type=Path, default=ROOT / "releases/final-coverage.json")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--database", type=Path, default=DEFAULT_DB)
    args = p.parse_args()
    stage(args.release, args.coverage, args.out, args.database)
