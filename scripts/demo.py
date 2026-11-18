"""Build the three Hansard demonstration paths from a verified release."""

import json
from pathlib import Path
from urllib.parse import urlsplit

from capture import dump, sha
from query import DEFAULT_DB, Index

PALANTIR = "/D1EA4BF2-2796-48DD-A144-B9675E614F2A/"
LORDS_MICROSOFT = "/3203E15D-A3FF-40F4-B48C-568BC40BD24F/"
BILL_STAGES = "https://bills.parliament.uk/bills/4030/stages"
COMMONS_RAIL = "https://hansard.parliament.uk/Commons/2026-06-10/debates/D04D1360-E0F8-4D80-B4B4-E9EF69FA9B39/RailwaysBill"
LORDS_RAIL = "https://hansard.parliament.uk/Lords%E2%80%8F/2026-07-07/debates/28bb8967-c343-4820-9833-f7340b982762/LordsChamber"
FACETS = {
    "people": "People", "offices": "Offices and roles", "places": "Places",
    "organisations": "Organisations", "things": "Things and programmes",
    "legislation": "Legislation", "subjects": "Policy subjects",
}
PEOPLE = {
    "Ian Murray": (3966, "https://www.theyworkforyou.com/mp/24872/ian_murray/edinburgh_south"),
    "Baroness Lloyd of Effra": (5414, "https://www.theyworkforyou.com/peer/26695/baroness_lloyd_of_effra"),
    "Martin Wrigley": (5111, "https://www.theyworkforyou.com/mp/26484/martin_wrigley/newton_abbot"),
    "Heidi Alexander": (4038, "https://www.theyworkforyou.com/mp/24953/heidi_alexander/swindon_south"),
    "Lord Hendy of Richmond Hill": (4972, "https://www.theyworkforyou.com/peer/26114/lord_hendy_of_richmond_hill"),
}
READING = {
    "microsoft-365": (
        ("Digital sovereignty (Commons Library)", "https://commonslibrary.parliament.uk/research-briefings/cbp-10547/"),
        ("Cyber Security and Resilience Bill (Commons Library)", "https://commonslibrary.parliament.uk/research-briefings/cbp-10442/"),
    ),
    "palantir-nhs": (
        ("NHS Federated Data Platform (Commons Library)", "https://commonslibrary.parliament.uk/research-briefings/cbp-12264/"),
    ),
    "railways-bill": (
        ("Official Bill stages", BILL_STAGES),
        ("Railways Bill progress (Commons Library)", "https://commonslibrary.parliament.uk/research-briefings/cbp-10538/"),
        ("Railways Bill (Lords Library)", "https://lordslibrary.parliament.uk/research-briefings/lln-2026-0031/"),
    ),
}


def record(day, house, title, relation, url):
    if urlsplit(url).netloc != "hansard.parliament.uk" or urlsplit(url).scheme != "https":
        raise ValueError("A demonstration row needs an official Hansard source.")
    return {"date": day, "house": house, "title": title, "relation": relation, "url": url}


def result_row(row, title, relation):
    return record(row["date"], row["house"], title, relation, row["url"])


def first_match(engine, search, section, speaker, day):
    return next(row for row in engine.find(search, day=day, limit=200)["items"]
                if section in row["url"] and row["title"].startswith(speaker))


def contribution_row(match, relation, title=None):
    return record(match["date"], match["facets"]["chamber"][0],
                  title or match["title"].rsplit(" · ", 1)[0], relation, match["url"])


def facets(match):
    return {FACETS[key]: [v for v in values if v != "Unrecorded"]
            for key, values in match["facets"].items() if key in FACETS}


def add_week_matches(engine, rows, days, term, entity):
    for day in days:
        records = engine.find(term, day=day, limit=500)["items"]
        for house in ("Commons", "Lords"):
            match = next((row for row in reversed(records)
                          if house in row["facets"]["chamber"]
                          and entity in engine.history["contributions"][row["id"]]["entities"]), None)
            if match:
                rows.append(contribution_row(match, "Shared mention"))


def microsoft(engine, release, new_days):
    sample = json.loads((release / "voice-microsoft-365.json").read_bytes())
    lords = first_match(engine, "Technology Providers", LORDS_MICROSOFT,
                        "Baroness Lloyd of Effra (Lab) · Cyber Security: Public Sector Dependence on Technology Providers · 16",
                        "2026-11-17")
    trace = engine.track(lords["id"], entity="microsoft", limit=75)
    if not any(row["url"] == sample["anchor"]["url"] for row in trace["items"]):
        raise ValueError("The Commons anchor is missing from the Lords Microsoft trace.")
    rows = [
        record("2026-11-16", "Commons", "Ian Murray · Microsoft 365 outage", "Starting contribution", sample["anchor"]["url"]),
        contribution_row(lords, "Shared mention", "Baroness Lloyd of Effra · Public sector dependence on technology providers"),
        *[result_row(row, "Microsoft 365", "Shared mention") for row in sample["earlier_mentions"]],
    ]
    add_week_matches(engine, rows, new_days, "Microsoft", "microsoft")
    return {
        "id": "microsoft-365", "title": "Microsoft 365 outage",
        "summary": f"Ian Murray’s Commons statement and the next day’s Lords question share a Microsoft mention. The index found {len(sample['earlier_mentions'])} earlier matches for Microsoft 365 before the Commons statement.",
        "facets": {"People": ["Ian Murray", "Baroness Lloyd of Effra"],
                   "Offices and roles": ["Minister for Creative Industries, Media and Online Safety"],
                   "Organisations": ["Microsoft", "Cabinet Office"], "Things and programmes": ["Microsoft 365"]},
        "rows": rows,
    }


def palantir(engine, new_days):
    anchor = first_match(engine, "Palantir", PALANTIR, "Martin Wrigley (Newton Abbot)", "2026-11-17")
    company = engine.track(anchor["id"], entity="palantir", limit=500)
    platform = engine.track(anchor["id"], entity="nhs-fdp", limit=3)
    references = [
        ("2026-11-16", "/FBAAF525-AB23-4118-9750-2BC93FF9B428/", "Health and Care: Digital Capability"),
        ("2026-04-16", "/2FDCA71C-D0C1-4738-BEE8-A4BDA311DB99/", "Martin Wrigley · NHS Federated Data Platform"),
    ]
    rows = [contribution_row(anchor, "Starting contribution", "Martin Wrigley · NHS Federated Data Platform: Palantir")]
    for day, section, title in references:
        hit = min((row for row in company["items"] if row["date"] == day and section in row["url"]),
                  key=lambda row: row["order"])
        # His opening contribution references the debate. Link to the debate title.
        rows.append(record(day, hit["house"], title, "Explicit reference", hit["url"].split("#", 1)[0]))
    for hit in platform["items"]:
        rows.append(result_row(hit, "NHS Federated Data Platform", "Shared mention"))
    add_week_matches(engine, rows, new_days, "Palantir", "palantir")
    labels = facets(anchor)
    labels["Offices and roles"] = ["Member for Newton Abbot"]
    return {
        "id": "palantir-nhs", "title": "Palantir and the NHS",
        "summary": f"Martin Wrigley points to Monday’s statement and his April Westminster Hall debate. The index also found {company['total']} earlier matches for Palantir and {platform['total']} for the NHS Federated Data Platform.",
        "facets": labels, "rows": rows,
    }


def railways(engine, new_days):
    rows = [
        record("2026-06-10", "Commons", "Railways Bill · Third Reading", "Formal Bill stage", COMMONS_RAIL),
        record("2026-07-07", "Lords", "Railways Bill · Second Reading", "Formal Bill stage", LORDS_RAIL),
    ]
    if "2026-11-18" in new_days:
        matches = engine.find("Railways Bill", day="2026-11-18", house="Lords", limit=500)["items"]
        stage = next((row for row in matches if row["title"].split(" · ")[1].startswith("Railways Bill")), None)
        if stage:
            rows.append(record("2026-11-18", "Lords", "Railways Bill · Report stage", "Formal Bill stage",
                               stage["url"].split("#", 1)[0]))
    return {
        "id": "railways-bill", "title": "Railways Bill",
        "summary": "Follow Parliament’s Bill 4030 from the Commons to the Lords. The same identifier leads to the official Bill record and the associated Hansard proceedings.",
        "facets": {"People": ["Heidi Alexander", "Lord Hendy of Richmond Hill"],
                   "Organisations": ["Department for Transport"], "Legislation": ["Railways Bill"]},
        "rows": rows,
    }


def add_reference_links(example):
    people = example["facets"]["People"]
    example["biographies"] = {
        name: f"https://members.parliament.uk/member/{PEOPLE[name][0]}/career" for name in people
    }
    example["links"] = [
        {"title": title, "url": url} for title, url in READING[example["id"]]
    ] + [{"title": f"{name} on TheyWorkForYou", "url": PEOPLE[name][1]} for name in people]


def write_timeline(destination, examples, counts, source_nodes):
    title = "A week in Parliament · Demonstration timeline"
    nodes = {"index.md": {"id": "index.md", "title": title, "type": "Index",
                          "body": "Choose a sitting date or House, then open a record and follow its Hansard link."}}
    verified = {node["url"]: node for node in source_nodes.values()
                if node.get("url") and node.get("hansard_proceedings", {}).get("source_item")}
    groups = []
    for label, rows in [
        *[(example["title"], example["rows"]) for example in examples],
        ("Verified sittings", [record(day, house, f"{house} sitting", "Sitting record",
                                     f"https://hansard.parliament.uk/{house}/{day}")
                               for day in sorted(counts) for house in ("Commons", "Lords")]),
    ]:
        routes = []
        for row in rows:
            route = "source/" + sha(row["url"].encode())[:24] + ".md"
            if route not in nodes:
                nodes[route] = {
                    "id": route, "title": row["title"], "type": row["relation"],
                    "section": "Demonstration evidence", "timestamp": row["date"],
                    "url": row["url"], "resource": row["url"],
                    "body": f"{row['house']} · {row['relation']}\n\n[Read in Hansard]({row['url']})",
                    "learning_facets": {"sitting": [row["date"]], "chamber": [row["house"]],
                                        "connection": [row["relation"]], "example": []},
                }
                source = verified.get(row["url"])
                if source:
                    proceedings = source["hansard_proceedings"]
                    section = source_nodes.get(proceedings["section_id"], {}).get("hansard_proceedings", {})
                    markers = section.get("markers")
                    nodes[route]["hansard_proceedings"] = (
                        {**proceedings, "markers": markers, "marker_source_api": section["source_api"]}
                        if markers else proceedings
                    )
                    if "hansard_summary" in source:
                        nodes[route]["hansard_summary"] = source["hansard_summary"]
            node = nodes[route]["learning_facets"]
            if label not in node["example"]:
                node["example"].append(label)
            routes.append(route)
        groups.append({"title": label, "routes": list(dict.fromkeys(routes))})
    facets = {"sitting": "Sitting date", "chamber": "House", "connection": "Connection", "example": "Example"}
    meta = {"title": title, "default_corpus": "hansard", "corpus_order": ["hansard"],
            "learning_presentation": {"schema": "okf-learning-presentation.v1", "start_route": "index.md",
                                      "groups": groups, "facets": [{"key": k, "label": v} for k, v in facets.items()]}}
    dump(destination / "demo-timeline.json", {
        "schema": "okf-explorer-bundle.v0", "kind": "okf-bundle", "okf_version": "0.2", "meta": meta,
        "corpora": {"hansard": {"id": "hansard", "title": title, "root": "index.md",
                               "assertion_scope": "real-world", "nodes": nodes, "relationships": []}},
    })


def write_demo(release, destination, coverage, database=DEFAULT_DB, baseline=None):
    counts = coverage["week_contributions_by_day"]
    prior_days = baseline["sittings"] if baseline else ("2026-11-16", "2026-11-17")
    new_days = [day for day in counts if day not in prior_days]
    engine = Index(release, database)
    if baseline is None:
        examples = [microsoft(engine, release, new_days), palantir(engine, new_days), railways(engine, new_days)]
    else:
        # The anchor dates have passed. Keep their verified earlier evidence
        # and append only results drawn from newly captured sittings.
        examples = baseline["examples"]
        stories = {story["id"]: story for story in examples}
        add_week_matches(engine, stories["microsoft-365"]["rows"], new_days, "Microsoft", "microsoft")
        add_week_matches(engine, stories["palantir-nhs"]["rows"], new_days, "Palantir", "palantir")
        stories["railways-bill"]["rows"].extend(row for row in railways(engine, new_days)["rows"]
                                                 if row["date"] in new_days)
    for example in examples:
        add_reference_links(example)
        example["rows"].sort(key=lambda r: (r["date"], r["house"], r["title"]), reverse=True)
    dump(destination / "demo.json", {"schema": "hansard-demo.v1", "sittings": counts, "examples": examples})
    source_nodes = json.loads((release / "okf-bundle.json").read_bytes())["corpora"]["hansard"]["nodes"]
    write_timeline(destination, examples, counts, source_nodes)
    lines = ["# A week in Parliament demonstration evidence", "",
             "This file contains links and selected matches from the verified release. A shared mention is a name or alias match.", ""]
    for example in examples:
        lines.extend(["## " + example["title"], "", example["summary"], ""])
        for group, labels in example["facets"].items():
            if labels:
                if group == "People":
                    labels = [f"[{name}]({example['biographies'][name]})" for name in labels]
                lines.append(f"- {group} — {', '.join(labels)}")
        lines.append("")
        for row in example["rows"]:
            lines.append(f"- {row['date']} · {row['house']} · {row['relation']} · [{row['title']}]({row['url']})")
        for link in example.get("links", []):
            lines.append(f"- [{link['title']}]({link['url']})")
        lines.append("")
    lines.append("Contains Parliamentary information licensed under the Open Parliament Licence v3.0.")
    (destination / "demo-evidence.md").write_text("\n".join([*lines, ""]), encoding="utf-8")
