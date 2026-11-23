"""Export a selected archive window as compact, evidence-bearing YAML-LD."""

import argparse
from contextlib import ExitStack
from datetime import date
import gzip
import io
import json
from pathlib import Path
import sys

from build import CONTEXT, Graph, NS, digest, iri
from capture import dump, sha
from query import DEFAULT_DB, DEFAULT_RELEASE, Index


def export(index, from_day, to_day, entities, stream, include_backfill=False):
    with ExitStack() as resources:
        db = index.connect()
        if db:
            resources.callback(db.close)
        older, older_keys, older_profile = index.connect_older()
        if older:
            resources.callback(older.close)
        if not db and not older and not include_backfill:
            raise ValueError("The historic index is unavailable.")
        return write_window(index, db, from_day, to_day, entities, stream, include_backfill,
                            older, older_keys, older_profile)


def write_window(index, db, from_day, to_day, entities, stream, include_backfill,
                 older=None, older_keys=(), older_profile=None):
    if db:
        db.execute("BEGIN")
    if older:
        older.execute("BEGIN")
    selected = set(entities) if entities else set(index.archive_keys if db else ()) | set(older_keys)
    if include_backfill and not entities:
        selected.update(path.stem for path in index.backfill.glob("*.json") if path.stem != "manifest")
    search = {key: index.backfill_for(key) for key in selected} if include_backfill else {}
    selected_archive = selected & index.archive_keys if db else set()
    selected_older = selected.intersection(older_keys)
    if selected - selected_archive - selected_older - {key for key, package in search.items() if package}:
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
    if older:
        meta["older_archive"] = {"profile_sha256": older_profile, "entities": sorted(selected_older),
                                "sittings_by_status": dict(older.execute("""
                                    SELECT status,count(*) FROM sitting WHERE day BETWEEN ? AND ? GROUP BY status
                                """, (from_day, to_day)))}
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
    for connection, keys in ((older, selected_older), (db, selected_archive)):
        if not keys:
            continue
        placeholders = ",".join("?" for _ in keys)
        cursor = connection.execute(f"""
            SELECT c.route,c.day,c.record, m.entity,m.evidence
            FROM mention m JOIN contribution c ON c.route=m.route
            WHERE m.entity IN ({placeholders}) AND m.day>=? AND m.day<=?
            ORDER BY m.day,c.route,m.entity
        """, (*sorted(keys), from_day, to_day))
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


def export_file(index, first, last, entities, output, include_backfill):
    working = output.with_suffix(output.suffix + ".tmp")
    if output.suffix == ".gz":
        with working.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=4, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8") as stream:
                count = export(index, first, last, entities, stream, include_backfill)
    else:
        with working.open("w", encoding="utf-8") as stream:
            count = export(index, first, last, entities, stream, include_backfill)
    working.replace(output)
    return count


def export_partitions(index, first, last, output, include_backfill):
    with ExitStack() as resources:
        db = index.connect()
        if db:
            resources.callback(db.close)
        older, older_keys, _ = index.connect_older()
        if older:
            resources.callback(older.close)
        keys = set(index.archive_keys if db else ()) | older_keys
    if include_backfill:
        keys.update(path.stem for path in index.backfill.glob("*.json") if path.stem != "manifest")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "hansard-history-partitions.v1", "from": first, "through": last,
                "bundle_sha256": index.bundle_sha256, "partitions": {}}
    total = 0
    for key in sorted(keys):
        path = output / f"{key}.yamlld.gz"
        count = export_file(index, first, last, [key], path, include_backfill)
        encoded = path.read_bytes()
        manifest["partitions"][key] = {"path": path.name, "assertions": count, "bytes": len(encoded),
                                       "sha256": sha(encoded)}
        total += count
    dump(output / "manifest.json", manifest)
    return total


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    p.add_argument("--database", type=Path, default=DEFAULT_DB)
    p.add_argument("--older-database", type=Path)
    p.add_argument("--from-date", type=date.fromisoformat, required=True)
    p.add_argument("--to-date", type=date.fromisoformat, required=True)
    p.add_argument("--entity", action="append")
    p.add_argument("--include-backfill", action="store_true", help="Include verified targeted searches.")
    outputs = p.add_mutually_exclusive_group(required=True)
    outputs.add_argument("--out", type=Path)
    outputs.add_argument("--out-dir", type=Path, help="Write independently retrievable entity partitions.")
    args = p.parse_args()
    if args.from_date > args.to_date:
        p.error("The start date must precede the end date.")
    if args.out_dir and args.entity:
        p.error("Use --out to export selected entities.")
    index = Index(args.release, args.database, args.older_database)
    first, last = args.from_date.isoformat(), args.to_date.isoformat()
    if args.out_dir:
        total = export_partitions(index, first, last, args.out_dir, args.include_backfill)
    else:
        total = export_file(index, first, last, args.entity, args.out, args.include_backfill)
    print(f"Exported {total} history assertions.", file=sys.stderr)


if __name__ == "__main__":
    main()
