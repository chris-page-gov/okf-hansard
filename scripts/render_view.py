"""Render a checked Hansard view as a standalone accessible companion page."""

import argparse
from html import escape
import json
from pathlib import Path
from urllib.parse import urlparse

from query import canonical_digest


def render(package):
    view = package["view"]
    view_id = view["view_id"]
    body = {k: v for k, v in view.items() if k != "view_id"}
    rows = body["rows"]
    if (body["schema"] != "okf-view.v1" or body["kind"] != "ranked-bar-and-table"
            or canonical_digest(body) != view_id or canonical_digest(rows) != body["dataset_sha256"]
            or body["context_id"] != package["context_id"] or body["bundle_sha256"] != package["bundle_sha256"]):
        raise ValueError("The view and evidence package do not match.")
    if any(type(row["count"]) is not int or row["count"] < 0 for row in rows):
        raise ValueError("The chart requires a non-negative count.")
    maximum = max([1, *(row["count"] for row in rows)])
    coverage = body["coverage"]
    earliest = coverage["extension_from"] or coverage["base_from"]
    title = escape(body["title"])
    groups = []
    for row in rows:
        label, facet, count = escape(row["entity"]), escape(row["facet"]), row["count"]
        groups.append(f'<tr><th scope="row">{label}</th><td>{facet}</td>'
                      f'<td class="count"><meter min="0" max="{maximum}" value="{count}" '
                      f'aria-hidden="true"></meter> <span>{count:,}</span></td></tr>')
    evidence = []
    for row in [package["anchor"], *package["items"]]:
        url = row.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname == "hansard.parliament.uk":
            evidence.append(f'<li><a href="{escape(url, quote=True)}">Hansard passage, '
                            f'{escape(row["date"])}</a></li>')
    entity = package.get("selected_entity")
    examples_heading = "Source links"
    if entity:
        examples_heading = f"Evidence page for {escape(entity['label'])}"
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · A week in Parliament</title>
<style>
  :root {{ color-scheme: light; font: 100%/1.5 system-ui, sans-serif; background: #f4f5f3; color: #1c2521; }}
  body {{ margin: 0; border-top: 7px solid #275c47; }}
  main {{ max-width: 56rem; padding: clamp(1rem, 4vw, 3rem); margin: auto; }}
  h1 {{ line-height: 1.12; font-size: clamp(1.8rem, 5vw, 3rem); letter-spacing: -.035em; }}
  p {{ max-width: 68ch; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; }}
  caption {{ text-align: left; font-weight: 650; margin: 1.2rem 0 .5rem; }}
  th, td {{ text-align: left; padding: .6rem .75rem; border-bottom: 1px solid #c4d1ca; }}
  thead {{ background: #e0ece5; }}
  .count {{ white-space: nowrap; font-variant-numeric: tabular-nums; }}
  meter {{ width: clamp(2rem, 14vw, 10rem); }}
  a {{ color: #174d3c; text-underline-offset: .15em; }}
  a:focus {{ outline: 3px solid #a46c00; outline-offset: 3px; }}
  @media (max-width: 34rem) {{ th, td {{ padding: .4rem; }} meter {{ display: none; }} }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p>Captured earlier matches from {escape(earliest)} to the selected contribution on {escape(package['anchor']['date'])}. Parliamentary coverage and the matching vocabulary limit these counts.</p>
<p>{escape(body['description'])}</p>
<table>
<caption>Earlier matched contribution records</caption>
<thead><tr><th scope="col">Entity</th><th scope="col">Facet</th><th scope="col">Records</th></tr></thead>
<tbody>{''.join(groups)}</tbody>
</table>
<h2>{examples_heading}</h2>
<ul>{''.join(evidence)}</ul>
</main>
</body>
</html>
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(render(json.loads(args.package.read_bytes())), encoding="utf-8")
