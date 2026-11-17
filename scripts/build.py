"""Build an offline OKF+ pilot from byte-verified official snapshots."""

import argparse
from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import quote

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from capture import dump, sha
from model import (
    Entity, LICENCE, Matcher, NS, PROFILE, TERM_TYPES, WEB, capacity, display,
    load_entities, mention_roles, read_sittings,
)
from people import POST_SERIES, office_evidence

OKF = "https://chris-page-gov.github.io/okf-explorer/ns#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
TITLE = "A week in Parliament"
FACETS = {
    "sitting": "Sitting date",
    "chamber": "House",
    "venue": "Proceedings",
    "business": "Contribution type",
    "speaker_role": "Speaker capacity",
    "period": "Time window",
    "people": "People",
    "offices": "Offices and roles",
    "places": "Places",
    "organisations": "Organisations",
    "things": "Programmes, reviews and technology",
    "legislation": "Legislation",
    "subjects": "Policy subjects",
}
VENUES = {"Debate": "Chamber", "WestHall": "Westminster Hall", "WMS": "Written statements",
          "Petitions": "Petitions", "GEN": "General Committees", "GrandCommittee": "Grand Committee",
          "PBC": "Public Bill Committees"}
PREDICATES = {
    "partOf": ("is recorded in", "records"),
    "sitting": ("took place on", "includes"),
    "spokenBy": ("is attributed to", "is attributed from"),
    "hasRecordedCapacity": ("has recorded capacity", "is used as capacity in"),
    "hasDatedRecord": ("has dated record", "relates to Member"),
    "appointmentTo": ("is appointment to", "has recorded appointment"),
    "representationOf": ("is representation of", "has representation record"),
    "divisionIn": ("is division in", "contains division"),
    "businessConcerns": ("has business concerning", "is business of"),
    "mentions": ("mentions", "is mentioned in"),
    "hasOfficeTitle": ("mentions office title", "is mentioned in"),
}
CONTEXT = {
    "@version": 1.1, "@vocab": NS + "field:", "hansard": NS + "vocab:",
    "rdf": RDF, "okf": OKF, "prov": "http://www.w3.org/ns/prov#",
    "dct": "http://purl.org/dc/terms/", "skos": "http://www.w3.org/2004/02/skos/core#",
    "title": "dct:title", "date": {"@id": "dct:date", "@type": "http://www.w3.org/2001/XMLSchema#date"},
    "source": {"@id": "rdf:subject", "@type": "@id"},
    "predicate": {"@id": "rdf:predicate", "@type": "@id"},
    "target": {"@id": "rdf:object", "@type": "@id"},
    "evidence": {"@id": "prov:hadPrimarySource", "@container": "@set"},
    "authority": {"@id": "okf:authority", "@type": "@json"},
    "rights": {"@id": "okf:rights", "@type": "@json"},
    "learning_facets": {"@id": "okf:learningFacets", "@type": "@json"},
    "details": {"@id": NS + "field:details", "@type": "@json"},
    "spans": {"@id": NS + "field:spans", "@type": "@json"},
    "meta": {"@id": NS + "field:meta", "@type": "@json"},
    "url": {"@id": "https://schema.org/url", "@type": "@id"},
    "resource": {"@id": "dct:source", "@type": "@id"},
}


def compact(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def link(url, label="Official source"):
    return f"[{label}](<{url}>)"


def iri(route):
    return NS + "record:" + route.removesuffix(".md").replace("/", ":")


def digest(value):
    return sha(value.encode("utf-8"))


def safe_markdown(value):
    return re.sub(r"([\\\x60*_{}\[\]<>])", r"\\\1", value)


def evidence(src, web, field, value_hash, suffix, spans=None, structured=False):
    record = {
        "@id": NS + "evidence:" + digest(f"{src['sha256']}|{field}|{suffix}")[:32],
        "type": "Hansard source field" if "hansard-api" in src["url"] else "Members API source field",
        "url": web, "resource": src["url"], "source_artifact": src["path"],
        "source_sha256": src["sha256"], "source_field": field, "source_value_sha256": value_hash,
        "source_value_hash_canonicalization": "sorted-json-utf8-v1" if structured else "utf8-string-v1", "retrieved_at": src["retrieved_at"],
    }
    if spans:
        record["spans"] = spans
        record["normalization"] = NS + "method:plain-text-whitespace-v1"
        record["rationale"] = "Exact ranges in the normalised API contribution value."
    return record


def canonical_field(value):
    return value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)


class Graph:
    def __init__(self):
        self.records = {}
        self.edges = []

    def node(self, route, typ, title, **extra):
        if route in self.records:
            return route
        semantic_type = "".join(re.findall(r"[A-Za-z]+", typ))
        self.records[route] = {"@id": iri(route), "@type": f"hansard:{semantic_type}",
                               "type": typ, "title": title, "route": route, **extra}
        return route

    def edge(self, source, predicate, target, receipt, url, field, value, spans=None, method="source-field"):
        sid = NS + "assertion:" + digest(f"{source}|{predicate}|{target}")[:36]
        label, inverse = PREDICATES[predicate]
        pred = NS + f"vocab:{predicate}"
        observation = evidence(receipt, url, field, digest(canonical_field(value)), sid, spans, structured=not isinstance(value, str))
        assertion = {
            "@id": sid, "@type": ["rdf:Statement", "okf:RelationshipAssertion"],
            "source": {"@id": iri(source)}, "predicate": {"@id": pred}, "target": {"@id": iri(target)},
            "source_route": source, "target_route": target, "kind": label, "label": label,
            "inverse_label": inverse, "assertion_status": "normalized", "assertion_scope": "real-world",
            "authority": {"class": "derived", "label": "OKF Hansard pilot", "source": receipt["url"]},
            "derivation": NS + "method:" + method, "observed_at": receipt["retrieved_at"],
            "evidence": [observation], "rights": {
                "source": LICENCE, "assertion": "Parliamentary source with Open Parliament Licence exclusions."
            },
        }
        self.edges.append(assertion)
        key = f"hansard:{predicate}"
        self.records[source].setdefault(key, []).append({"@id": iri(target)})
        return sid


def meta_for(first, last, dates, roots):
    return {
        "title": TITLE, "default_corpus": "hansard", "corpus_order": ["hansard"],
        "profile": PROFILE, "semantic_descriptor": "okf-bundle.yamlld",
        "learning_presentation": {
            "schema": "okf-learning-presentation.v1",
            "title": TITLE, "start_route": "index.md",
            "introduction": f"Westminster proceedings from {first} to {last}, with earlier matched mentions.",
            "groups": [{"title": d, "routes": [roots[d]]} for d in dates],
            "facets": [{"key": key, "label": label} for key, label in FACETS.items() if key != "period"],
        },
    }


def runtime(graph, meta, finished):
    records = {}
    for route, record in graph.records.items():
        fields = {key: value for key, value in record.items()
                  if not key.startswith(("hansard:", "@", "details"))}
        if record.get("section") == "Earlier record":
            fields["body"] = link(record["url"], "Read the earlier passage in Hansard")
        records[route] = {**fields, "id": route, "semantic_id": record["@id"],
                          "section": record.get("section", "Index"),
                          "status": "draft", "trust_tier": "working"}
    relationships = []
    for edge in graph.edges:
        relationships.append({
            "id": edge["@id"], "source": edge["source_route"], "target": edge["target_route"],
            "source_iri": edge["source"]["@id"], "target_iri": edge["target"]["@id"],
            "predicate": edge["predicate"]["@id"], "kind": edge["kind"], "label": edge["label"],
            "inverse_label": edge["inverse_label"], "assertion_status": edge["assertion_status"],
            "assertion_scope": edge["assertion_scope"], "observed_at": edge["observed_at"],
            "derivation": edge["derivation"], "authority": edge["authority"],
            "evidence": [{k: v for k, v in item.items() if k != "source_artifact"}
                         for item in edge["evidence"]], "rights": edge["rights"],
        })
    return {
        "schema": "okf-explorer-bundle.v0", "kind": "okf-bundle", "okf_version": "0.2",
        "generated_at": finished, "meta": meta,
        "corpora": {"hansard": {"id": "hansard", "title": TITLE, "root": "index.md",
                               "assertion_scope": "real-world", "nodes": records,
                               "relationships": relationships}},
    }


def write_markdown(out, graph, first, last):
    for route, record in graph.records.items():
        # The Explorer and YAML-LD planes contain all records. Markdown
        # provides portable entry points for the week and vocabulary.
        if record.get("date", first) < first:
            continue
        fields = {k: v for k, v in record.items() if k != "body" and not k.startswith("hansard:")}
        fields["@context"] = CONTEXT if route == "index.md" else [PROFILE + "context.jsonld",
                                                                  {"hansard": NS + "vocab:"}]
        if route == "index.md":
            fields["okf_version"] = "0.2"
            fields["description"] = f"Westminster proceedings from {first} to {last}."
        path = out / "markdown" / route
        path.parent.mkdir(parents=True, exist_ok=True)
        fm = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
        path.write_text("---\n" + fm + "\n---\n\n" + record.get("body", "") + "\n", encoding="utf-8")


def build(snapshot, people_snapshot, out, vocabulary, first, last, explorer):
    raw = (snapshot / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    finished = manifest["finished_at"]
    parts, records, divisions, metrics = read_sittings(snapshot, manifest, first, last)
    entities = load_entities(snapshot, manifest, vocabulary)
    offices, appointments, people_manifest = office_evidence(people_snapshot)

    # Office titles are matchable entities even when no office-holder can be
    # resolved. Only evidenced person-to-appointment edges carry occupancy.
    for (series, post_id), office in offices.items():
        alias = office["hansard_label"]
        key = f"office-{series.lower()}-{post_id}"
        entities[key] = Entity(key, office["kind"], office["label"], office["source"],
                               [alias, alias.removeprefix("The ")] if alias else [], "Members post register")
    matcher = Matcher(entities)
    matches = {route: mention_roles(record, matcher) for route, record in records.items()}
    current = {route for route, row in records.items() if row["scope"] == "Pilot week"}
    business = {route: dict(matcher.find(part["title"])) for route, part in parts.items()}
    focus = {key for route in current for key in [*matches[route], *business[records[route]["part"]]]}
    graph = Graph()
    postings = defaultdict(list)
    trace = {}
    day_routes = {}
    graph.node("index.md", "Index", TITLE, body=(
        f"# {TITLE}\n\n"
        "Explore the Commons and Lords contribution records and follow named entities back through earlier sittings.\n\n"
        "Each textual match is a discovery aid. Follow its evidence to read the contribution in context."
    ))
    for day in sorted({records[route]["day"] for route in current}):
        day_routes[day] = graph.node(f"sitting/{day}.md", "Sitting day", day, date=day,
                                    section="Sittings", body=f"# {day}\n\n" + "\n\n".join(
                                        link(f"{WEB}/{house}/{day}", f"{house} Hansard")
                                        for house in ("Commons", "Lords")))
    used_parts = {records[route]["part"] for route in current}
    kept = current | {route for route in records if focus.intersection(matches[route])}
    used_parts.update(records[route]["part"] for route in kept)
    for route in list(used_parts):
        parent = parts[route]["parent"]
        while parent:
            used_parts.add(parent)
            parent = parts[parent]["parent"]

    def entity_node(key):
        entity = entities[key]
        text = f"# {safe_markdown(entity.label)}\n\n{entity.kind}. Matched on recorded names or aliases."
        if entity.source:
            text += f"\n\n{link(entity.source, 'Identity reference')}"
        return graph.node(entity.route, entity.kind, entity.label, section="Entities", body=text,
                          details={"aliases": entity.aliases, "scheme": entity.scheme, "identity": entity.source},
                          **({"url": entity.source} if entity.source else {}))

    for route in sorted(used_parts):
        part = parts[route]
        title = part["title"] or "Untitled proceedings"
        graph.node(route, "Proceedings section", title, date=part["day"], section="Proceedings",
                   url=part["url"], body=f"# {safe_markdown(title)}\n\n" + link(part["url"], "Read in Hansard"),
                   details={"date": part["day"], "house": part["house"], "venue": part["section"],
                            "external_id": part["ext_id"], "source_version": part["source_version"]})
    for route in sorted(used_parts):
        part = parts[route]
        field = part["pointer"] + "/Overview/ExtId"
        if part["parent"]:
            graph.edge(route, "partOf", part["parent"], part["capture"], part["url"], field, part["ext_id"])
        elif part["day"] in day_routes:
            graph.edge(route, "sitting", day_routes[part["day"]], part["capture"],
                       part["url"], part["pointer"] + "/Overview/Date", part["day"] + "T00:00:00")
        for key, span in sorted(business[route].items()):
            if key in focus:
                graph.edge(route, "businessConcerns", entity_node(key), part["capture"], part["url"],
                           part["pointer"] + "/Overview/Title", part["raw_title"], [span], "title-label-match")

    for route in sorted(kept):
        row = records[route]
        part = parts[row["part"]]
        matched = {key: spans for key, spans in matches[route].items() if key in focus}
        title = f"{row['attributed_to'] or row['kind']} · {part['title']} · {row['order'] + 1}"
        person_key = f"member-{row['member']}"
        if row["member"] and person_key not in entities:
            entities[person_key] = Entity(person_key, "Parliamentarian", row["attributed_to"] or person_key,
                                          f"https://members.parliament.uk/member/{row['member']}", [],
                                          "Hansard MemberId")
        person = entities.get(person_key)
        speaker_capacity = capacity(row["attributed_to"], person)
        facets = {key: [] for key in FACETS}
        facets.update({"sitting": [row["day"]], "chamber": [row["house"]],
                       "venue": [VENUES.get(row["section"], row["section"])], "business": [row["kind"]],
                       "speaker_role": [speaker_capacity], "period": [row["scope"]]})
        if person:
            facets["people"].append(person.label)
        for key in set(matched) | set(business[row["part"]]):
            entity = entities[key]
            facets[entity.group.lower()].append(entity.label)
        if speaker_capacity in ("Minister or law officer", "Presiding officer"):
            facets["offices"].append(speaker_capacity)
        facets = {key: sorted(set(values)) or ["Unrecorded"] for key, values in facets.items()}
        notes = f"## Related matters\n\n"
        if matched:
            grouped = defaultdict(list)
            for key in sorted(matched, key=lambda k: entities[k].label.casefold()):
                grouped[entities[key].group].append(safe_markdown(entities[key].label))
            notes += "\n".join(f"- **{group}** — {', '.join(labels)}" for group, labels in sorted(grouped.items()))
        else:
            notes += "The pilot vocabulary found no textual matches in this passage."
        body = (f"# {safe_markdown(title)}\n\n"
                f"{row['day']} · {row['house']} · {VENUES.get(row['section'], row['section'])}\n\n"
                f"{link(row['url'], 'Read the recorded passage')} · {link(row['capture']['url'], 'API source')}\n\n"
                f"{notes}")
        details = {
            "external_id": row["external_id"], "api_item_id": row["source_item_id"],
            "member_id": row["member"], "attributed_to": row["attributed_to"],
            "speaker_capacity": speaker_capacity, "source_field": row["pointer"] + "/Value",
            "source_api": row["capture"]["url"], "source_sha256": row["capture"]["sha256"],
            "value_sha256": row["value_sha256"], "normalised_sha256": row["normalised_sha256"],
            "source_version": part["source_version"], "classification": row["hrs_tag"],
        }
        graph.node(route, "Contribution", title, date=row["day"], section=row["scope"], url=row["url"],
                   body=body, description=f"{part['title']} · {row['house']}", details=details,
                   learning_facets=facets)
        graph.edge(route, "partOf", row["part"], row["capture"], row["url"],
                   row["pointer"] + ("/ExternalId" if row["external_id"] else "/ItemId"),
                   row["external_id"] or row["source_item_id"])
        if person:
            graph.edge(route, "spokenBy", entity_node(person_key), row["capture"], row["url"],
                       row["pointer"] + "/MemberId", row["member"])
        if row["attributed_to"] and speaker_capacity in ("Minister or law officer", "Presiding officer"):
            # Keep the title exactly as Parliament reported it, scoped to the
            # ascription, even where no unique post ID has been established.
            ascribed = row["attributed_to"]
            if person and person.label in ascribed:
                ascribed = ascribed.split(person.label, 1)[0].rstrip(" (")
            actor_label = ascribed.rstrip(" (") or speaker_capacity
            role = f"role/{digest(actor_label.casefold())[:24]}.md"
            graph.node(role, "Recorded capacity", actor_label, section="Offices and roles",
                       body=f"# {safe_markdown(actor_label)}\n\nCapacity recorded by Hansard.")
            graph.edge(route, "hasRecordedCapacity", role, row["capture"], row["url"],
                       row["pointer"] + "/AttributedTo", row["attributed_to"])
        if route in current:
            trace[route] = {"entities": sorted(matched), "date": row["day"], "part": row["part"],
                            "order": row["order"], "url": row["url"]}
        for key, spans in sorted(matched.items()):
            predicate = "hasOfficeTitle" if entities[key].group == "Offices" else "mentions"
            aid = graph.edge(route, predicate, entity_node(key), row["capture"], row["url"],
                             row["pointer"] + "/Value", row["text"], spans, "literal-alias-match")
            # The normalised text hash is separate from the hash of the raw API Value.
            graph.edges[-1]["evidence"][0]["source_value_sha256"] = row["value_sha256"]
            graph.edges[-1]["evidence"][0]["normalised_value_sha256"] = row["normalised_sha256"]
            postings[key].append({
                "contribution": route, "date": row["day"], "part": row["part"], "order": row["order"],
                "assertion": aid, "url": row["url"], "spans": spans, "house": row["house"],
            })

    for route, division in sorted(divisions.items()):
        part = parts[division["part"]]
        node = graph.node(route, "Division", f"Recorded division · {part['title']}", date=part["day"],
                          section="Divisions", url=part["url"],
                          body=f"# Recorded division\n\n{link(part['url'], 'Read proceedings and vote')}")
        graph.edge(node, "divisionIn", division["part"], division["capture"], part["url"],
                   division["pointer"] + "/ExternalId", division["id"])

    add_appointments(graph, entities, appointments, entity_node)
    index = {"schema": "hansard-history.v1", "contributions": trace, "entities": {
        key: {"label": entities[key].label, "type": entities[key].kind, "group": entities[key].group,
              "route": entities[key].route} for key in sorted(postings)
    }, "mentions": {key: sorted(value, key=lambda r: (r["date"], r["part"], r["order"]))
                    for key, value in sorted(postings.items())}}
    meta = meta_for(first, last, sorted(day_routes), day_routes)
    checked = validate(graph, explorer)
    breakdown = [{"date": day, "house": house, **dict(counts)} for (day, house), counts in sorted(metrics.items())]
    counts = Counter(row["day"] for route, row in records.items() if route in current)
    receipt = {
        "schema": "hansard-build-receipt.v1", "status": "local-pilot", "capture": snapshot.name,
        "manifest_sha256": sha(raw), "capture_finished_at": finished,
        "people_capture": people_snapshot.name if people_snapshot else None,
        "people_source_errors": people_manifest["errors"] if people_manifest else {},
        "day_denominators": breakdown, "source_sittings": manifest["sittings"],
        "source_errors": [s for s in manifest["sittings"] if s["errors"]],
        "directory_errors": manifest["directory_errors"], "week_contributions_by_day": dict(sorted(counts.items())),
        "earlier_matched_contributions": len(kept - current), "anchor_entities": len(focus),
        "current_with_text_matches": sum(bool(row["entities"]) for row in trace.values()),
        "graph_records": len(graph.records), "assertions": len(graph.edges), "validated_assertions": checked,
        "assertions_by_predicate": dict(Counter(e["predicate"]["@id"].rsplit(":", 1)[-1] for e in graph.edges)),
        "ambiguous_aliases": matcher.ambiguities, "facet_counts": {
            facet: dict(Counter(value for route in current for value in graph.records[route]["learning_facets"][facet]))
            for facet in FACETS
        },
    }
    out.mkdir(parents=True, exist_ok=False)
    compact(out / "okf-bundle.json", runtime(graph, meta, finished))
    compact(out / "history.json", index)
    declarations = {key: {"kind": entities[key].kind, "label": entities[key].label,
                          "source": entities[key].source, "aliases": entities[key].aliases,
                          "scheme": entities[key].scheme} for key in sorted(focus)}
    compact(out / "analysis-profile.json", {"schema": "hansard-match-profile.v1",
                                             "entities": declarations,
                                             "ambiguities": matcher.ambiguities})
    # JSON syntax is a YAML 1.2 subset. Flow entries keep this YAML-LD
    # serialisation small while preserving a real, self-contained @context.
    with (out / "okf-bundle.yamlld").open("w", encoding="utf-8") as stream:
        stream.write('"@context": ' + json.dumps(CONTEXT, ensure_ascii=False) + "\n")
        stream.write("meta: " + json.dumps(meta, ensure_ascii=False) + "\n")
        stream.write('"@graph":\n')
        for item in list(graph.records.values()) + graph.edges:
            stream.write("- " + json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")
    write_markdown(out, graph, first, last)
    receipt["artifacts"] = {name: {"bytes": (out / name).stat().st_size, "sha256": sha((out / name).read_bytes())}
                            for name in ("okf-bundle.json", "history.json", "okf-bundle.yamlld", "analysis-profile.json")}
    dump(out / "receipt.json", receipt)
    if receipt["artifacts"]["okf-bundle.json"]["bytes"] >= 64 * 1024 * 1024:
        raise ValueError("Explorer projection exceeds the reader byte ceiling")
    print(json.dumps({k: receipt[k] for k in ("week_contributions_by_day", "earlier_matched_contributions",
                                             "anchor_entities", "graph_records", "assertions", "artifacts")}, indent=2))


def add_appointments(graph, entities, appointments, entity_node):
    for row in appointments:
        person = f"member-{row['member']}"
        if person not in entities:
            continue
        series, item_id = row["series"], row["entity_id"]
        if not row["start"] or series not in {*POST_SERIES, "representations"}:
            continue
        start = row["start"][:10]
        end = row["end"][:10] if row["end"] else None
        kind = "Representation period" if series == "representations" else "Appointment"
        label = f"{row['name']} · {start}" + (f" to {end}" if end else "")
        occurrence = f"appointment/{person}-{series.lower()}-{item_id}-{start}.md"
        sov = row["source"]
        url = entities[person].source
        graph.node(occurrence, kind, label, section="Appointments", url=url,
                   details={"valid_from": start, "valid_to": end, "series": series, "source": sov["url"]},
                   body=f"# {safe_markdown(label)}\n\n{link(url, 'Parliament member profile')}")
        graph.edge(entity_node(person), "hasDatedRecord", occurrence, sov, url, row["source_field"], row["value"])
        entity_key = f"constituency-{item_id}" if series == "representations" else f"office-{series.lower()}-{item_id}"
        if entity_key not in entities and series == "representations":
            entities[entity_key] = Entity(entity_key, "Constituency", row["name"],
                                          f"https://members.parliament.uk/constituency/{item_id}/overview", [],
                                          "Parliament Members API")
        graph.edge(occurrence, "representationOf" if series == "representations" else "appointmentTo",
                   entity_node(entity_key), sov, url, row["source_field"], row["value"])


def validate(graph, explorer):
    schema = json.loads((explorer / "profiles/bundle-wiki/v1/semantic-assertion.schema.json").read_bytes())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    seen = set()
    for edge in graph.edges:
        if edge["@id"] in seen:
            raise ValueError(f"Repeated assertion {edge['@id']}")
        seen.add(edge["@id"])
        for side in ("source", "target"):
            route = edge[f"{side}_route"]
            if graph.records[route]["@id"] != edge[side]["@id"]:
                raise ValueError(f"Unresolved {side} route {route}")
        validator.validate(edge)
    return len(seen)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--people", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, default=Path("profile/vocabulary.yaml"))
    parser.add_argument("--explorer", type=Path, default=Path("../okf-explorer"))
    parser.add_argument("--first", type=date.fromisoformat, required=True)
    parser.add_argument("--last", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    build(args.snapshot, args.people, args.out, args.vocabulary, args.first.isoformat(),
          args.last.isoformat(), args.explorer)


if __name__ == "__main__":
    main()
