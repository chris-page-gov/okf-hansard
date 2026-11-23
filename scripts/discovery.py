"""Publish a small, source-linked entry point for web and file-based AI clients."""

from hashlib import file_digest
from html import escape
import json
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin

from capture import dump
from build_explorer_graph import dataset_route
from demo import timeline_route
from model import PROFILE
from build_core_projection import build as build_core_projection
from build_walkthrough import build as build_walkthrough
from okf_core import CORE_SPEC, CORE_VERSION, LICENCE, PRODUCT_VERSION, check_markdown, index_link, write_document, write_index


SITE = "https://chris-page-gov.github.io/okf-hansard/"
REPOSITORY = "https://github.com/chris-page-gov/okf-hansard"
EXPLORER = "https://chris-page-gov.github.io/okf-explorer/"
PROMPT = (
    f"Read {SITE}okf/index.md and open the Railways Bill evidence. "
    "Which stages of the Bill does the bundle show in the Commons and the Lords? "
    "Put them in date order and link to the Hansard records, the official Bill stages and the companion timeline. "
    "Say which sources you could open."
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
<label for="demo-prompt">Ask about the Railways Bill</label>
<textarea id="demo-prompt" readonly rows="6" style="display:block; width:100%; font:inherit; margin:.5rem 0">{escape(PROMPT)}</textarea>
<p>If the assistant cannot open links, download the example as Markdown and attach it. For Voice, open the companion and Explorer in a browser so the audience can follow the evidence.</p>
<p class="actions"><a class="primary" href="okf/railways-bill.md">Open the Railways Bill evidence</a>
<a href="walkthrough.html">View the source-linked question walkthrough</a>
<a href="demo.html?example=railways-bill">Open the Railways Bill companion</a></p>
<h2>Explore other examples</h2>
<ul>
<li><a href="okf/palantir-nhs.md">Palantir and the NHS</a></li>
<li><a href="okf/microsoft-365.md">Commons statement on the Microsoft 365 outage</a></li>
<li><a href="november/okf/index.md">November sittings and coverage</a></li>
</ul>
<p><a href="okf/index.md">OKF 0.3 index</a> · <a href="okf-public-access.json">Machine directory</a> · <a href="llms.txt">Plain-text links</a></p>
<p><a href="okf-core.json">Compact core Reader projection</a> · <a href="walkthrough.html">Source-linked question walkthrough</a></p>
<p>Hansard is the official record. Earlier name and alias matches can relate to other parliamentary business.</p>
</main></body></html>
""", encoding="utf-8")


def write_discovery(site, title, dates, observed_at, semantic_file, *, month=False):
    base = urljoin(SITE, "november/" if month else "")
    coverage_receipt = json.loads((site / "coverage.json").read_bytes())
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
        f"- [Compact core Reader projection]({base}okf-core.json)",
        f"- [Full source core and graph records]({base}graph/okf-explorer.json)",
        f"- [Source-linked question walkthrough]({base}walkthrough.html)",
        f"- [Open {('the contribution finder' if month else 'the AI demonstration')}]({base}{'history.html' if month else 'use-with-ai.html'})",
        f"- [Machine directory]({base}okf-public-access.json)",
        (f"- [Week examples]({SITE}okf/index.md)" if month else
         f"- [November sittings and contribution finder]({SITE}november/okf/index.md)"),
    ]))
    core_projection = build_core_projection(root, site)
    walkthrough = build_walkthrough(site, month=month)
    if not month:
        profile_output = site / "profile" / "hansard-domain-v2.json"
        profile_output.parent.mkdir(parents=True, exist_ok=True)
        profile_output.write_bytes((Path(__file__).resolve().parents[1] / "profile" / "hansard-domain-v2.json").read_bytes())
        profile_source = profile_output.parent / "domain.yaml"
        profile_source.write_bytes((Path(__file__).resolve().parents[1] / "profile" / "domain.yaml").read_bytes())
    core = check_markdown(root)
    graph_path = site / "graph/okf-explorer.json"
    if json.loads(graph_path.read_bytes()).get("okf_version") != CORE_VERSION:
        raise ValueError("Discovery requires an Explorer projection of the verified OKF 0.3 source")
    descriptor = file_reference(site, base, "graph/okf-explorer.json")
    large_descriptor = json.loads(graph_path.read_bytes())
    full_core = large_descriptor.get("core_source", {})
    semantic = file_reference(site, base, semantic_file)
    entrypoints = {
        "markdown_index": file_reference(site, base, "okf/index.md"),
        "core_reader_projection": file_reference(site, base, "okf-core.json"),
        "full_source_core_and_graph": file_reference(site, base, "graph/okf-explorer.json"),
        "walkthrough": file_reference(site, base, "walkthrough.html"),
        "walkthrough_data": file_reference(site, base, "walkthrough.json"),
        "walkthrough_visual": file_reference(site, base, "walkthrough.svg"),
        "coverage": file_reference(site, base, "coverage.json"),
        "semantic_graph": {**semantic, "format": "YAML-LD", "compression": "gzip" if semantic_file.endswith(".gz") else None},
    }
    profile_bytes = (Path(__file__).resolve().parents[1] / "profile" / "hansard-domain-v2.json").read_bytes()
    with (Path(__file__).resolve().parents[1] / "profile" / "hansard-domain-v2.json").open("rb") as profile_stream:
        profile_digest = file_digest(profile_stream, "sha256").hexdigest()
    entrypoints["semantic_profile"] = {
        "url": PROFILE,
        "sha256": profile_digest,
        "bytes": len(profile_bytes),
    }
    domain_source = Path(__file__).resolve().parents[1] / "profile" / "domain.yaml"
    with domain_source.open("rb") as domain_stream:
        domain_digest = file_digest(domain_stream, "sha256").hexdigest()
    entrypoints["domain_source"] = {
        "url": SITE + "profile/domain.yaml",
        "sha256": domain_digest,
        "bytes": domain_source.stat().st_size,
    }
    for markdown in sorted(root.rglob("*.md")):
        relative = markdown.relative_to(site).as_posix()
        entrypoints[relative] = file_reference(site, base, relative)
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
            "product_version": PRODUCT_VERSION,
            "core_projection": core_projection,
            "full_source_access": {
                "schema": full_core.get("schema"), "descriptor": descriptor["url"],
                "descriptor_sha256": descriptor["sha256"], "snapshot": full_core.get("snapshot"),
                "source_documents": full_core.get("source_documents"),
                "concepts": full_core.get("concepts"),
                "navigation_documents": full_core.get("navigation_documents"),
                "extension_documents": full_core.get("extension_documents"),
                "relationship_assertions": full_core.get("relationship_assertions"),
                "detail_resource": full_core.get("detail_resource"),
            },
            "walkthrough": walkthrough,
            "semantic_descriptor": semantic["url"], "core_markdown": core,
            "licence": LICENCE, "coverage": {"from": min(dates), "through": max(dates), "observed_at": observed_at},
            **({"history_finder": {"state": "partial", "search_through": coverage_receipt["history_backfill"]["through"],
                                   "unsearched_interval": coverage_receipt["history_backfill_gap"],
                                   "detail": "The separate November bundle contains the captured proceedings for these dates."}}
               if not month and coverage_receipt.get("history_backfill_gap") else {}),
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
