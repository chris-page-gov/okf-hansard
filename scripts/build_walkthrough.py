"""Generate a bundle-specific, source-linked complex-question visual."""

import argparse
from html import escape
import gzip
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urlencode

from capture import sha

SITE = "https://chris-page-gov.github.io/okf-hansard/"
READER = "https://chris-page-gov.github.io/okf-explorer/explore/"


def link(url, label):
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def explorer(asset, view, route=""):
    query = urlencode({"bundle": SITE + asset, "view": view})
    return READER + "?" + query + ("#" + quote(route) if route else "")


def graph_record(graph, route):
    locator = json.loads((graph / "records/locator.json").read_bytes())
    value = 0x811C9DC5
    for part in route.encode("utf-8"):
        value = ((value ^ part) * 0x01000193) & 0xFFFFFFFF
    bucket = f"{value >> 24:02x}"
    reference = locator["buckets"][bucket]
    raw = (graph / reference["path"]).read_bytes()
    if sha(raw) != reference["sha256"]:
        raise ValueError("The record route bucket digest does not match its descriptor")
    position = json.loads(raw).get(route)
    if not position:
        raise ValueError(f"Missing required record route {route}")
    rows = json.loads((graph / locator["record_chunks"][position[0]]).read_bytes())
    return rows[position[1]]


def incident_edges(graph, route):
    runtime = json.loads((graph / "relationships/runtime.json").read_bytes())
    locator_ref = runtime["route_locator"]
    locator_raw = (graph / locator_ref["path"]).read_bytes()
    if sha(locator_raw) != locator_ref["sha256"]:
        raise ValueError("The relationship route locator digest does not match its descriptor")
    locator = json.loads(locator_raw)
    prefix = hashlib.sha256(route.encode("utf-8")).hexdigest()[:2]
    bucket_ref = next((row for row in locator["buckets"] if row["bucket"] == prefix), None)
    if bucket_ref is None:
        return []
    bucket_raw = (graph / "relationships" / f"bucket-{prefix}.json.gz").read_bytes()
    if sha(bucket_raw) != bucket_ref["sha256"]:
        raise ValueError("The relationship route bucket digest does not match its descriptor")
    bucket = json.loads(gzip.decompress(bucket_raw))
    route_ref = next((row for row in bucket["routes"] if row["route"] == route), None)
    if route_ref is None:
        return []
    found = []
    for chunk in route_ref["chunks"]:
        rows = json.loads(gzip.decompress((graph / chunk).read_bytes()))
        found.extend(row for row in rows if row["source"] == route or row["target"] == route)
    return found


def week_case(site):
    demo = json.loads((site / "demo.json").read_bytes())
    timeline = json.loads((site / "demo-timeline.json").read_bytes())
    case = next(row for row in demo["examples"] if row["id"] == "railways-bill")
    rows = sorted(case["rows"], key=lambda row: (row["date"], row["house"], row["title"]))
    if len(rows) < 3:
        raise ValueError("The Railways Bill walkthrough requires the complete three-record trail")
    timeline_nodes = timeline["corpora"]["hansard"]["nodes"]
    route = next((node["id"] for node in timeline_nodes.values()
                  if node.get("url") == rows[0]["url"]), None)
    if route is None:
        raise ValueError("The week Railways Bill source is missing from its timeline bundle")
    sources = [{"date": row["date"], "house": row["house"], "title": row["title"], "url": row["url"]}
               for row in rows]
    answer = "The captured trail lists the Commons Third Reading on 10 June, the Lords Second Reading on 7 July, and the Lords Report stage on 18 November 2026. These are three linked records, not a complete legal history of the Bill."
    return {
        "id": "hansard-week-railways-bill-v1",
        "question": "Which recorded stages of Bill 4030 appear in the Commons and Lords, in date order, and what does this evidence not establish?",
        "answer": answer,
        "scope": "Three explicit Hansard stage records surfaced by the week bundle's worked Railways Bill example; the 18 November record is within the captured November extension.",
        "sources": sources,
        "negative_control": "A name or alias match alone does not establish substantive relevance. This trail does not establish enactment, legal effect, or that no other stages occurred.",
        "graph": {"descriptor": "graph/okf-explorer.json", "timeline": "demo-timeline.json", "route": route},
        "coverage": {"from": "2026-11-16", "through": "2026-11-19", "observed_on": "2026-11-20"},
    }


def month_case(site):
    coverage = json.loads((site / "coverage.json").read_bytes())
    days = coverage["dates"]
    if not days:
        raise ValueError("November walkthrough requires date-by-date coverage evidence")
    latest = max(row["date"] for row in days)
    through_rows = [row for row in days if row["date"] <= latest]
    records = []
    for row in sorted(through_rows, key=lambda item: item["date"]):
        houses = row.get("houses", {})
        contributions = sum(value.get("contributions", 0) for value in houses.values())
        records.append({"date": row["date"], "contributions": contributions,
                        "commons": houses.get("Commons", {}).get("contributions", 0),
                        "lords": houses.get("Lords", {}).get("contributions", 0),
                        "commons_status": houses.get("Commons", {}).get("status", "unrecorded"),
                        "lords_status": houses.get("Lords", {}).get("status", "unrecorded")})
    total = sum(row["contributions"] for row in records)
    route = "dataset/debate/lords-2026-11-18-debate-5ee3bf1a-449e-4d6d-a0ce-f725ce734996.md"
    record = graph_record(site / "graph", route)
    business_edge = next((edge for edge in incident_edges(site / "graph", route)
                          if edge["source"] == route and edge["target"] == "dataset/entity/bill-4030.md"
                          and edge["kind"] == "has business concerning"), None)
    if not business_edge:
        raise ValueError("The 18 November Lords Railways Bill business assertion is absent")
    day = next(row for row in records if row["date"] == "2026-11-18")
    answer = (f"The graph links the 18 November Lords proceedings section ‘{record['title']}’ to Bill 4030 "
              f"with a ‘{business_edge['kind']}’ assertion. Date coverage records {day['commons']:,} Commons "
              f"and {day['lords']:,} Lords contributions that day. It does not establish that the Commons "
              "discussed this Bill or that the Bill passed. The full snapshot records "
              f"{total:,} contributions across {len(records)} date entries through {latest}; a no-calendar-sitting "
              "entry differs from a source gap, and dates after the cutoff remain outside scope.")
    return {
        "id": "hansard-november-coverage-v1",
        "question": f"On 18 November, which House’s proceedings are linked to Bill 4030, what does the same-date coverage say about Commons and Lords activity, and can those records establish that the Commons debated or the Bill passed? How far does this snapshot cover?",
        "answer": answer,
        "scope": f"The generated November coverage record has {len(records)} date entries from {min(row['date'] for row in records)} through {latest}; later November dates are outside this snapshot.",
        "dates": records,
        "sources": [{"title": "18 November Lords Railways Bill proceedings", "url": record["url"]},
                    {"title": "Date-by-date coverage and verification", "url": "coverage.json"},
                    {"title": "November sitting and contribution finder", "url": "history.html"}],
        "negative_control": f"The presence of Commons activity on 18 November does not establish Commons debate on Bill 4030. A search returning no result after {latest} is outside this snapshot’s declared coverage.",
        "graph": {"descriptor": "graph/okf-explorer.json", "history": "history.html",
                  "route": route, "target_route": "dataset/entity/bill-4030.md",
                  "assertion_id": business_edge["id"], "assertion_kind": business_edge["kind"]},
        "coverage": {"from": min(row["date"] for row in records), "through": latest,
                     "contributions": total, "graph_records": coverage.get("graph_records"),
                     "assertions": coverage.get("assertions")},
    }


def svg(case, month):
    if month:
        rows = case["dates"]
        width, row_height = 900, 24
        maximum = max((row["contributions"] for row in rows), default=1) or 1
        height = 80 + row_height * len(rows)
        bars = []
        for i, row in enumerate(rows):
            y = 42 + i * row_height
            count = row["contributions"]
            length = round(500 * count / maximum)
            colour = "#176b5b" if count else "#a5a5a5"
            bars.append(f'<text x="18" y="{y+14}">{row["date"]}</text><rect x="135" y="{y}" width="{length}" height="16" fill="{colour}"/><text x="{145+length}" y="{y+14}">{count:,} contributions</text>')
        return f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 {width} {height}"><title id="title">Daily contribution coverage</title><desc id="desc">Observed November date entries through {escape(case["coverage"]["through"])}; grey zero bars denote dates with no captured contributions, not dates beyond the snapshot.</desc><text x="18" y="24">Date</text><text x="135" y="24">Contributions by House</text>{"".join(bars)}</svg>'
    rows = case["sources"]
    width, height = 900, 180
    positions = [100, 410, 720]
    points = []
    for i, (row, x) in enumerate(zip(rows, positions)):
        title = escape(row["title"])
        label = f'{row["date"]} · {row["house"]}'
        points.append(f'<g><circle cx="{x}" cy="80" r="20" fill="#176b5b"/><text x="{x}" y="125" text-anchor="middle">{escape(label)}</text><text x="{x}" y="146" text-anchor="middle">{title[:45]}</text></g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 {width} {height}"><title id="title">Railways Bill stage trail</title><desc id="desc">Three source-linked records in chronological order; each marker opens the official Hansard record.</desc><line x1="100" y1="80" x2="720" y2="80" stroke="#777" stroke-width="3"/>{"".join(points)}</svg>'


def build(site, *, month=False):
    case = month_case(site) if month else week_case(site)
    reader_interaction = {
        "keyboard_navigation": "Focus the target graph node and press Enter to open its record.",
        "target_route": "dataset/entity/bill-4030.md",
        "keyboard_acceptance": "replayable",
        "pointer_selection": "not-accepted",
    }
    if not month:
        reader_interaction["pointer_limitation"] = (
            "The weekly graph's Bill node mouse hit area was intercepted by an overlapping SVG label hit area. "
            "Keyboard activation passed; pointer selection was not accepted."
        )
    case["reader_interaction"] = reader_interaction
    visual = svg(case, month) + "\n"
    case["svg_sha256"] = sha(visual.encode())
    case["source_projection_sha256"] = sha((site / "okf-core.json").read_bytes())
    (site / "walkthrough.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (site / "walkthrough.svg").write_text(visual, encoding="utf-8")
    source_links = ([link(row["url"], f'{row["date"]} · {row["house"]} · {row["title"]}') for row in case["sources"]]
                    if not month else [link(row["url"], row["title"]) for row in case["sources"]])
    descriptor = case["graph"]["descriptor"]
    graph_url = explorer(descriptor, "graph")
    other = (explorer("demo-timeline.json", "timeline", case["graph"].get("route", ""))
             if not month else "history.html")
    html = f'''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Hansard source walkthrough</title><link rel="stylesheet" href="site.css"><style>main{{max-width:70rem;margin:2rem auto;padding:0 1rem;font:1rem/1.55 system-ui}}svg{{max-width:100%;height:auto}}svg text{{font:13px system-ui}}.negative{{border-left:4px solid #7a3e00;padding:.5rem 1rem;background:#fff6e5}}.sources li{{margin:.6rem 0}}</style></head>
<body><main><p><a href="okf/index.md">OKF source index</a></p><h1>Question, evidence and coverage</h1><h2>Question</h2><p>{escape(case["question"])}</p><h2>Answer from the inspected bundle</h2><p>{escape(case["answer"])}</p><p><strong>Scope:</strong> {escape(case["scope"])}</p><h2>Visual source trail</h2>{visual}<h2>Sources</h2><ul class="sources">{"".join("<li>"+item+"</li>" for item in source_links)}</ul><h2>Graph and Reader</h2><p>{link(graph_url, "Open the graph in OKF Explorer")} · {link(other, "Open the related timeline or date finder")}</p><p>To follow the Bill 4030 graph node, focus it and press Enter. The browser journey checks the exact destination route.</p>{f'<p class="negative"><strong>Pointer limitation:</strong> {escape(reader_interaction["pointer_limitation"])}</p>' if reader_interaction.get("pointer_limitation") else ''}<p class="negative"><strong>Negative control:</strong> {escape(case["negative_control"])}</p><p>See the <a href="walkthrough.json">machine-readable walkthrough and source references</a>, <a href="okf-core.json">focused core Reader projection</a>, <a href="graph/okf-explorer.json">full source and graph descriptor</a> and <a href="coverage.json">coverage receipt</a>.</p></main></body></html>'''
    (site / "walkthrough.html").write_text(html, encoding="utf-8")
    return {"id": case["id"], "svg_sha256": case["svg_sha256"],
            "projection_sha256": case["source_projection_sha256"],
            "source_count": len(case.get("sources", [])),
            "coverage": case["coverage"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("--month", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.site, month=args.month), indent=2))
