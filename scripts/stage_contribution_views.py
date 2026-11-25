"""Stage a verified sitting range as a focused graph and timeline."""

import argparse
from datetime import date
import gzip
from html import escape
import json
from pathlib import Path
import shutil
from urllib.parse import urlencode

from build_explorer_graph import build as build_graph
from build_pages import BUILD_CREDIT
from capture import dump
from discovery import HEAD_LINKS, write_discovery
from history_pages import write as write_history
from okf_core import CORE_VERSION
from query import DEFAULT_DB
from retained_public_assets import stage as retain_public_assets
from voice_pages import publish_voice

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_bytes())


def write_landing(output, coverage, archive_url):
    days = coverage["dates"]
    counts = {row["date"]: sum(house["contributions"] for house in row["houses"].values()) for row in days}
    archive_link = (f'<a href="{escape(archive_url, quote=True)}">Download historical YAML-LD</a>'
                    if archive_url else "")
    items = []
    for row in days:
        value = row["date"]
        day = date.fromisoformat(value)
        label = f"{day.day} {day:%B %Y}"
        count = counts[value]
        count_label = f"{count:,} contributions" if count else "No sitting"
        if count:
            href = escape("history.html?" + urlencode({"day": value}), quote=True)
            label = f'<a href="{href}">{label}</a>'
        if row["publication_status"] == "provisional":
            count_label += " (provisional)"
        items.append(f"<li>{label} · {count_label}</li>")
    (output / "index.html").write_text(f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>November in Parliament</title>
<link rel="stylesheet" href="site.css">
{HEAD_LINKS}
</head>
<body><main class="demo">
<h1>November in Parliament</h1>
<p>{coverage["contributions"]:,} captured contributions from both Houses. Choose a date and contribution to open its graph or follow related passages over time.</p>
<p class="actions"><a href="ask.html">Ask your AI about Hansard</a>
<a href="history.html">Open contribution timeline</a>
<a href="walkthrough.html">View the source-linked coverage walkthrough</a>
<a href="okf/index.md">Open the OKF index for AI</a>
<a href="okf-bundle.yamlld.gz">Download the YAML-LD graph</a>
{archive_link}
<a href="coverage.json">Read the coverage and verification report</a></p>
<h2>Sitting dates</h2>
<ul>{''.join(items)}</ul>
<p>Contains Parliamentary information licensed under the <a href="https://www.parliament.uk/site-information/copyright/open-parliament-licence/">Open Parliament Licence v3.0</a>.</p>
<p>{escape(BUILD_CREDIT)}</p>
</main></body></html>
""", encoding="utf-8")


def stage(release, checkpoints, output, database, older_database, cache, archive_url=None):
    if archive_url is None:
        archive_url = 'historical-downloads.html'
    receipt = read(release / "receipt.json")
    verified = read(release / "verification.json")
    backfill = read(release / "backfill" / "manifest.json")
    days = [read(path) for path in sorted(checkpoints.glob("*.json"), reverse=True)]
    counts = {row["date"]: sum(house["contributions"] for house in row["houses"].values()) for row in days}
    expected = receipt["week_contributions_by_day"]
    if not verified["passed"] or verified["assertions"] != receipt["assertions"] or (
        {day: count for day, count in counts.items() if count} != expected or sorted(expected) != backfill["dates"]
    ):
        raise ValueError("The graph, history scope and verified day counts must agree.")
    if verified.get("okf_core", {}).get("version") != CORE_VERSION:
        raise ValueError("The public snapshot requires verified OKF 0.3 source.")

    output.mkdir(parents=True, exist_ok=True)
    graph = output / "graph"
    if graph.exists():
        descriptor = read(graph / "okf-explorer.json")
        if descriptor["snapshot"] != "hansard-sha256-" + receipt["artifacts"]["okf-bundle.json"]["sha256"]:
            raise ValueError("The existing graph was built from a different release.")
    else:
        build_graph(release, graph)
    write_history(release, output, database, cache, older_database=older_database, focused_views=True)
    archive_manifest = output / "historical-yamlld/manifest.json"
    if archive_manifest.is_file():
        partitions = read(archive_manifest)
        if partitions["bundle_sha256"] != receipt["artifacts"]["history.json"]["sha256"]:
            raise ValueError("The historical YAML-LD partitions belong to a different release.")
        history_index = output / "history/index.json"
        catalogue = read(history_index)
        for key, item in partitions["partitions"].items():
            if key in catalogue["entities"]:
                catalogue["entities"][key]["yamlld"] = "historical-yamlld/" + item["path"]
        dump(history_index, catalogue)
        archive_url = "historical-yamlld/manifest.json"
    shutil.copyfile(ROOT / "docs/pages/site.css", output / "site.css")
    history = (output / "history.html").read_text(encoding="utf-8")
    history = history.replace('>A week in Parliament</a>', '>November in Parliament</a>')
    for page in ("demo.html", "methodology.html"):
        history = history.replace(f'href="{page}"', f'href="https://chris-page-gov.github.io/okf-hansard/{page}"')
    (output / "history.html").write_text(history, encoding="utf-8")
    with (release / "okf-bundle.yamlld").open("rb") as source, (output / "okf-bundle.yamlld.gz").open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=4, mtime=0) as stream:
            shutil.copyfileobj(source, stream)
    coverage = {"dates": days, "contributions": sum(expected.values()), "graph_records": receipt["graph_records"],
                "assertions": receipt["assertions"], "semantic_graph": receipt["artifacts"]["okf-bundle.yamlld"],
                "backfill": backfill, "verification": verified}
    dump(output / "coverage.json", coverage)

    write_landing(output, coverage, archive_url)
    write_discovery(output, "November in Parliament", expected, max(row["verified_at"] for row in days),
                    "okf-bundle.yamlld.gz", month=True)
    publish_voice(output, release)
    retain_public_assets(output, 'november')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--older-database", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    stage(args.release, args.checkpoints, args.out, args.database, args.older_database, args.cache)
