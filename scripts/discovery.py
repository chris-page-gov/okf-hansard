"""Publish a small, source-linked entry point for web and file-based AI clients."""

from hashlib import file_digest
from html import escape
import json
from urllib.parse import quote, urlencode, urljoin

from capture import dump
from build_explorer_graph import dataset_route
from demo import timeline_route
from model import PROFILE
from okf_core import CORE_SPEC, CORE_VERSION, LICENCE, check_markdown, index_link, write_document, write_index


SITE = "https://chris-page-gov.github.io/okf-hansard/"
REPOSITORY = "https://github.com/chris-page-gov/okf-hansard"
EXPLORER = "https://chris-page-gov.github.io/okf-explorer/"
PROMPT = (
    f"Read {SITE}okf/index.md and open the Microsoft 365 outage example. "
    "Tell me who made the statement, which organisations are linked and what two earlier matches show. "
    "Cite the exact Hansard passages and give me the companion, graph and timeline links. "
    "Keep name or alias matches distinct from explicit references. Say which sources you could open."
)
HEAD_LINKS = (
    '<link rel="describedby" type="application/json" href="okf-public-access.json">\n'
    '<link rel="alternate" type="text/markdown" href="okf/index.md">'
)


def file_reference(site, base, name):
    path = site / name
    with path.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    return {"url": urljoin(base, name), "sha256": digest, "bytes": path.stat().st_size}


def explorer_link(asset, view, route=""):
    query = urlencode({"bundle": urljoin(SITE, asset), "view": view})
    return EXPLORER + "explore/?" + query + ("#" + quote(route) if route else "")


def write_examples(site, root):
    demo = json.loads((site / "demo.json").read_bytes())
    voice = json.loads((site / "voice-microsoft-365.json").read_bytes())
    entries = []
    for example in demo["examples"]:
        key = example["id"]
        title = example["title"]
        entries.append(index_link(title, key + ".md"))
        rows = example["rows"]
        anchor = next((row for row in rows if row["relation"] == "Starting contribution"), rows[-1])
        sources = {row["url"]: row["title"] for row in [*rows, *example["links"]]}
        sources.update({link: name for name, link in example["biographies"].items()})
        fields = {"type": "Parliamentary evidence trail", "title": title,
                  "description": example["summary"], "resource": anchor["url"],
                  "sources": [{"resource": url, "title": label} for url, label in sources.items()]}
        lines = [f"# {title}", "", example["summary"], "",
                 "Shared mentions are matches on a name or alias. Check the linked passage for context.",
                 "", "## People and related subjects", ""]
        for label, values in example["facets"].items():
            if label == "People":
                values = [f"[{name}]({example['biographies'][name]})" for name in values]
            if values:
                lines.append(f"- **{label}** — {', '.join(values)}")
        lines.extend(["", "## Hansard evidence", ""])
        for row in rows:
            lines.append(f"- {row['date']} · {row['house']} · {row['relation']} · [{row['title']}]({row['url']})")
        lines.extend(["", "## Open the views and supporting sources", ""])
        timeline = explorer_link("demo-timeline.json", "timeline", timeline_route(anchor["url"]))
        lines += [f"- [Companion]({SITE}demo.html?example={key})", f"- [Focused Explorer timeline]({timeline})"]
        if key == "microsoft-365":
            graph = explorer_link("graph/okf-explorer.json", "graph", dataset_route(voice["anchor"]["id"]))
            lines.extend([f"- [Statement companion]({SITE}voice-microsoft-365.html)",
                          f"- [Focused Explorer graph]({graph})"])
        lines.extend(f"- [{row['title']}]({row['url']})" for row in example["links"])
        write_document(root / (key + ".md"), fields, "\n".join(lines))
    return entries


def write_ai_guide(site):
    (site / "use-with-ai.html").write_text(f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Use source-linked Hansard evidence in an AI assistant.">
<title>Use Hansard with AI</title>
<link rel="stylesheet" href="site.css">
{HEAD_LINKS}
</head>
<body><main class="guide">
<nav aria-label="Project"><a href="./">A week in Parliament</a></nav>
<h1>Use Hansard with AI</h1>
<p>Give an AI assistant that can open public links the prompt below. Check that it names the sources it read and links to the exact Hansard passages.</p>
<label for="demo-prompt">Microsoft 365 demo prompt</label>
<textarea id="demo-prompt" readonly rows="6" style="display:block; width:100%; font:inherit; margin:.5rem 0">{escape(PROMPT)}</textarea>
<p>If the assistant cannot open links, download the example as Markdown and attach it. For Voice, open the companion and Explorer in a browser so the audience can follow the evidence.</p>
<p class="actions"><a class="primary" href="okf/microsoft-365.md">Open the Microsoft 365 evidence</a>
<a href="demo.html">Open the companion</a></p>
<h2>Explore other examples</h2>
<ul>
<li><a href="okf/palantir-nhs.md">Palantir and the NHS</a></li>
<li><a href="okf/railways-bill.md">Railways Bill</a></li>
<li><a href="november/okf/index.md">November sittings and coverage</a></li>
</ul>
<p><a href="okf/index.md">OKF 0.3 index</a> · <a href="okf-public-access.json">Machine directory</a> · <a href="llms.txt">Plain-text links</a></p>
<p>Hansard is the official record. Earlier name and alias matches can relate to other parliamentary business.</p>
</main></body></html>
""", encoding="utf-8")


def write_discovery(site, title, dates, observed_at, semantic_file, *, month=False):
    base = urljoin(SITE, "november/" if month else "")
    root = site / "okf"
    root.mkdir(exist_ok=True)
    coverage = f"Hansard for both Houses. Captured sittings from {min(dates)} to {max(dates)}."
    if month:
        entries = [index_link("Sittings and relationships", "sittings.md")]
        write_document(root / "sittings.md", {
            "type": "Parliamentary evidence index", "title": "Sittings and relationships",
            "description": coverage, "resource": base + "coverage.json",
            "sources": [{"resource": base + "coverage.json", "title": "Calendar, counts and verification"}],
        }, f"""# Sittings and relationships

{coverage}

Read the [coverage and verification report]({base}coverage.json) for sitting dates, counts by House and historical search limits. Choose a sitting, then open its contribution list and follow a contribution permalink to Hansard or its focused graph and timeline.

- [Contribution and entity finder]({base}history.html)
- [History entry point]({base}history/index.json)
- [Sharded Explorer descriptor]({base}graph/okf-explorer.json)
""")
    else:
        entries = write_examples(site, root)
        write_ai_guide(site)
    write_index(root, title, coverage, "\n".join([
        "# " + title, "", *entries, "", "# Coverage and retrieval", "",
        f"- [Coverage and verification]({base}coverage.json)",
        f"- [Open {('the contribution finder' if month else 'the AI demonstration')}]({base}{'history.html' if month else 'use-with-ai.html'})",
        f"- [Machine directory]({base}okf-public-access.json)",
        (f"- [Week examples]({SITE}okf/index.md)" if month else
         f"- [November sittings and contribution finder]({SITE}november/okf/index.md)"),
    ]))
    core = check_markdown(root)
    graph_path = site / "graph/okf-explorer.json"
    if json.loads(graph_path.read_bytes()).get("okf_version") != CORE_VERSION:
        raise ValueError("Discovery requires an Explorer projection of the verified OKF 0.3 source")
    descriptor = file_reference(site, base, "graph/okf-explorer.json")
    semantic = file_reference(site, base, semantic_file)
    entrypoints = {
        "markdown_index": file_reference(site, base, "okf/index.md"),
        "coverage": file_reference(site, base, "coverage.json"),
        "semantic_graph": {**semantic, "format": "YAML-LD", "compression": "gzip" if semantic_file.endswith(".gz") else None},
    }
    entrypoints.update({path: file_reference(site, base, path) for path in
                        (["history/index.json", "okf/sittings.md"] if month else
                         ["demo.json", "demo-timeline.json", "okf/microsoft-365.md",
                          "okf/palantir-nhs.md", "okf/railways-bill.md"])})
    directory = {
        "schema": "okf-public-access-directory.v1", "title": title, "locale": "en-GB",
        "time_zone": "Europe/London", "observed_on": observed_at[:10],
        "scope": "Independent public Hansard evidence. Supplemental discovery metadata.",
        "related_directory": SITE + ("okf-public-access.json" if month else "november/okf-public-access.json"),
        "bundles": [{
            "title": title, "repository": REPOSITORY, "home": base, "visibility": "public",
            "descriptor": descriptor["url"], "descriptor_sha256": descriptor["sha256"],
            "descriptor_schema": "okf-explorer-large-corpus.v1", "declared_okf_version": CORE_VERSION,
            "core_specification": CORE_SPEC, "semantic_profile": PROFILE,
            "semantic_descriptor": semantic["url"], "core_markdown": core,
            "licence": LICENCE, "coverage": {"from": min(dates), "through": max(dates), "observed_at": observed_at},
            "access_note": "Start with the Markdown index. Retrieve focused records or history by need. Follow official links when citing parliamentary evidence.",
            "entrypoints": entrypoints,
        }],
    }
    dump(site / "okf-public-access.json", directory)
    (site / ".well-known").mkdir(exist_ok=True)
    dump(site / ".well-known/okf.json", directory)
    (site / "llms.txt").write_text("\n".join([
        "# " + title, "", "> " + coverage, "", "## Start here", "",
        f"- [OKF 0.3 Markdown index]({base}okf/index.md): Open this small index first.",
        f"- [Machine directory]({base}okf-public-access.json): Coverage, endpoints and SHA-256 digests.",
        f"- [Coverage and verification]({base}coverage.json): Check dates and search limits before answering.",
        f"- [Companion and views]({base}{'history.html' if month else 'use-with-ai.html'}): See the evidence and its source links.",
        "", "Cite the exact Hansard passages. Treat shared name or alias matches as leads.", "",
    ]), encoding="utf-8")
