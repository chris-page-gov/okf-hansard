"""Export a selected archive window as compact, evidence-bearing YAML-LD."""

import argparse
from datetime import date
import gzip
import json
from pathlib import Path
import sys

from build import CONTEXT, Graph, NS, digest, iri
from query import DEFAULT_DB, DEFAULT_RELEASE, Index


def export(index, from_day, to_day, entities, stream):
    db = index.connect()
    if not db:
        raise ValueError("The historic index is unavailable.")
    db.execute("BEGIN")
    profile = index.profile["entities"]
    selected = set(entities or index.archive_keys)
    if selected - index.archive_keys:
        raise ValueError("Use entity IDs from the pilot matching profile.")
    scopes = dict(db.execute("""
        SELECT status,count(*) FROM sitting WHERE ?<=day AND day<=? GROUP BY status
    """, (from_day, to_day)))
    meta = {"schema": "hansard-history-yamlld.v1", "from": from_day, "to": to_day,
            "profile_sha256": index.archive_profile_sha256,
            "sittings_by_status": scopes, "assertion_scope": "real-world", "entities": sorted(selected)}
    stream.write('"@context": ' + json.dumps(CONTEXT, ensure_ascii=False) + "\n")
    stream.write("meta: " + json.dumps(meta, ensure_ascii=False) + "\n")
    stream.write('"@graph":\n')

    def line(row):
        stream.write("- " + json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    try:
        for key in sorted(selected):
            row = profile[key]
            line({"@id": iri(f"entity/{key}.md"), "@type": "hansard:Entity", "route": f"entity/{key}.md",
                  "type": row["kind"], "title": row["label"]})
        count = 0
        cursor = db.execute("""
            SELECT c.route,c.day,c.record, m.entity,m.evidence
            FROM contribution c JOIN mention m ON m.route=c.route
            WHERE c.day>=? AND c.day<=? ORDER BY c.day,c.route,m.entity
        """, (from_day, to_day))
        current_route = None
        for route, day, record, entity, proof in cursor:
            if entity not in selected:
                continue
            if current_route != route:
                if current_route is not None:
                    line(graph.records[current_route])
                current_route = route
                metadata = json.loads(record)
                graph = Graph()
                target = graph.node(route, "Contribution", f"{metadata['attributed_to'] or metadata['kind']} · {day}",
                                    date=day, url=metadata["url"], details=metadata)
            parsed = json.loads(proof)
            predicate = "hasOfficeTitle" if parsed["assertion"] == NS + "assertion:" + digest(
                f"{route}|hasOfficeTitle|entity/{entity}.md"
            )[:36] else "mentions"
            aid = graph.edge(target, predicate, f"entity/{entity}.md", metadata["capture"], metadata["url"],
                             metadata["pointer"] + "/Value", "", parsed["spans"], "literal-alias-match")
            if aid != parsed["assertion"]:
                raise ValueError("Archive assertion does not match its recomputed identity.")
            edge = graph.edges.pop()
            edge["evidence"][0]["source_value_sha256"] = metadata["value_sha256"]
            edge["evidence"][0]["normalised_value_sha256"] = metadata["normalised_sha256"]
            line(edge)
            count += 1
        if current_route is not None:
            line(graph.records[current_route])
        return count
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    p.add_argument("--database", type=Path, default=DEFAULT_DB)
    p.add_argument("--from-date", type=date.fromisoformat, required=True)
    p.add_argument("--to-date", type=date.fromisoformat, required=True)
    p.add_argument("--entity", action="append")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.from_date > args.to_date:
        p.error("The start date must precede the end date.")
    output = args.out
    working = output.with_suffix(output.suffix + ".tmp")
    opener = gzip.open if output.suffix == ".gz" else open
    with opener(working, "wt", encoding="utf-8") as stream:
        total = export(Index(args.release, args.database), args.from_date.isoformat(),
                       args.to_date.isoformat(), args.entity, stream)
    working.replace(output)
    print(f"Exported {total} history assertions.", file=sys.stderr)


if __name__ == "__main__":
    main()
