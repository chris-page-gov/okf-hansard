"""Export a selected archive window as compact, evidence-bearing YAML-LD."""

import argparse
from contextlib import closing, nullcontext
from datetime import date
import gzip
import json
from pathlib import Path
import sys

from build import CONTEXT, Graph, NS, digest, iri
from query import DEFAULT_DB, DEFAULT_RELEASE, Index


def export(index, from_day, to_day, entities, stream, include_backfill=False):
    db = index.connect()
    if not db and not include_backfill:
        raise ValueError("The historic index is unavailable.")
    with closing(db) if db else nullcontext():
        return write_window(index, db, from_day, to_day, entities, stream, include_backfill)


def write_window(index, db, from_day, to_day, entities, stream, include_backfill):
    if db:
        db.execute("BEGIN")
    selected = set(entities or index.archive_keys)
    if include_backfill and not entities:
        selected.update(path.stem for path in index.backfill.glob("*.json") if path.stem != "manifest")
    search = {key: index.backfill_for(key) for key in selected} if include_backfill else {}
    selected_archive = selected & index.archive_keys if db else set()
    if selected - index.archive_keys - {key for key, package in search.items() if package}:
        raise ValueError("Use entity IDs from the archive or the targeted backfill.")
    scopes = dict(db.execute("""
        SELECT status,count(*) FROM sitting WHERE ?<=day AND day<=? GROUP BY status
    """, (from_day, to_day))) if db else {}
    ranges = {house: (start, stop) for house, start, stop in db.execute(
        "SELECT house,min(day),max(day) FROM sitting WHERE status='processed' GROUP BY house"
    )} if db else {}
    meta = {"schema": "hansard-history-yamlld.v1", "from": from_day, "to": to_day,
            "profile_sha256": index.archive_profile_sha256,
            "sittings_by_status": scopes, "assertion_scope": "real-world", "entities": sorted(selected)}
    if include_backfill:
        meta["targeted_search"] = {
            key: {field: package[field] for field in ("from", "through", "method", "search_windows", "errors")}
            for key, package in sorted(search.items()) if package
        }
    stream.write('"@context": ' + json.dumps(CONTEXT, ensure_ascii=False) + "\n")
    stream.write("meta: " + json.dumps(meta, ensure_ascii=False) + "\n")
    stream.write('"@graph":\n')

    def line(row):
        stream.write("- " + json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    for key in sorted(selected):
        row = index.profile["entities"][key]
        line({"@id": iri(f"entity/{key}.md"), "@type": "hansard:Entity", "route": f"entity/{key}.md",
              "type": row["kind"], "title": row["label"]})
    count = 0
    if selected_archive:
        placeholders = ",".join("?" for _ in selected_archive)
        cursor = db.execute(f"""
            SELECT c.route,c.day,c.record, m.entity,m.evidence
            FROM mention m JOIN contribution c ON c.route=m.route
            WHERE m.entity IN ({placeholders}) AND m.day>=? AND m.day<=?
            ORDER BY m.day,c.route,m.entity
        """, (*sorted(selected_archive), from_day, to_day))
        current_route = None
        for route, day, record, entity, proof in cursor:
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
    for key, package in sorted(search.items()):
        if not package:
            continue
        for row in package["items"]:
            day = row["date"]
            if day < from_day or day > to_day:
                continue
            scope = ranges.get(row["house"])
            if key in selected_archive and scope and scope[0] <= day <= scope[1]:
                continue
            graph = Graph()
            route = row["contribution"]
            source = graph.node(route, "Contribution", row["section_title"], date=day, url=row["url"])
            predicate = "hasOfficeTitle" if index.history["entities"][key]["group"] == "Offices" else "mentions"
            receipt = {**row["capture"], "path": f"search/{row['capture']['sha256']}.json"}
            graph.edge(source, predicate, f"entity/{key}.md", receipt, row["url"], row["source_field"],
                       "", row["spans"], "literal-alias-match")
            edge = graph.edges[0]
            edge["@id"] = row["assertion"]
            edge["evidence"][0]["source_value_sha256"] = row["source_value_sha256"]
            edge["evidence"][0]["normalised_value_sha256"] = row["normalised_value_sha256"]
            line(graph.records[route])
            line(edge)
            count += 1
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    p.add_argument("--database", type=Path, default=DEFAULT_DB)
    p.add_argument("--from-date", type=date.fromisoformat, required=True)
    p.add_argument("--to-date", type=date.fromisoformat, required=True)
    p.add_argument("--entity", action="append")
    p.add_argument("--include-backfill", action="store_true", help="Include verified targeted searches.")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.from_date > args.to_date:
        p.error("The start date must precede the end date.")
    output = args.out
    working = output.with_suffix(output.suffix + ".tmp")
    opener = gzip.open if output.suffix == ".gz" else open
    with opener(working, "wt", encoding="utf-8") as stream:
        total = export(Index(args.release, args.database), args.from_date.isoformat(),
                       args.to_date.isoformat(), args.entity, stream, args.include_backfill)
    working.replace(output)
    print(f"Exported {total} history assertions.", file=sys.stderr)


if __name__ == "__main__":
    main()
