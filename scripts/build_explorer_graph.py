"""Project a verified Hansard release into Explorer's route-scoped runtime."""

import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from capture import sha

PROFILE = Path(__file__).resolve().parents[1] / "profile"
RECORDS_PER_CHUNK = 32
RELATIONSHIPS_PER_CHUNK = 512
PLANE = "recorded"
PLANE_IRI = "urn:okf:hansard:relationship-plane:recorded"


def json_bytes(document):
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def write(root, path, document, compressed=False):
    body = json_bytes(document)
    if compressed:
        body = gzip.compress(body, mtime=0)
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    return {"path": path, "sha256": sha(body), "bytes": len(body)}


def dataset_route(route):
    return "dataset/" + route


def fnv_bucket(route):
    value = 0x811c9dc5
    for part in route.encode("utf-8"):
        value = ((value ^ part) * 0x01000193) & 0xffffffff
    return f"{value >> 24:02x}"


def publish_records(root, records, snapshot):
    locations = defaultdict(dict)
    chunks = []
    for start in range(0, len(records), RECORDS_PER_CHUNK):
        rows = []
        ordinal = len(chunks)
        for index, (identifier, source) in enumerate(records[start:start + RECORDS_PER_CHUNK]):
            route = dataset_route(identifier)
            row = {
                "name": identifier, "route": route, "title": source["title"],
                "record_type": source["type"], "notes": source.get("body") or source.get("description") or "",
                "resource_count": 0, "tags": [], "formats": [],
            }
            for field in ("url", "hansard_proceedings", "hansard_summary", "semantic_id"):
                if field in source:
                    row[field] = source[field]
            if source.get("date"):
                row["date"] = source["date"]
            rows.append(row)
            locations[fnv_bucket(route)][route] = [ordinal, index]
        chunks.append(write(root, f"records/chunk-{ordinal:04d}.json", rows))
    buckets = {
        bucket: write(root, f"records/bucket-{bucket}.json", routes)
        for bucket, routes in sorted(locations.items())
    }
    locator = write(root, "records/locator.json", {
        "schema": "okf-record-locator-sharded.v1", "algorithm": "fnv1a32-prefix-2",
        "snapshot": snapshot, "records": len(records), "chunk_size": RECORDS_PER_CHUNK,
        "record_chunks": [chunk["path"] for chunk in chunks], "buckets": buckets, "bucket_count": len(buckets),
    })
    return chunks, locator


def publish_relationships(root, records, relationships, snapshot, generated):
    rows = []
    identifiers = set()
    row_schema = json.loads((PROFILE / "relationship-runtime-row.schema.json").read_bytes())
    validator = Draft202012Validator(row_schema)
    for edge in sorted(relationships, key=lambda row: (row["source"], row["target"], row["id"])):
        if edge["id"] in identifiers:
            raise ValueError(f"Duplicate assertion identity: {edge['id']}")
        identifiers.add(edge["id"])
        source, target = records[edge["source"]], records[edge["target"]]
        rows.append({
            **edge, "schema": "okf-relationship-runtime-row.v1", "assertion_id": edge["id"],
            "source": dataset_route(edge["source"]), "target": dataset_route(edge["target"]),
            "source_iri": source["semantic_id"], "target_iri": target["semantic_id"],
            "source_label": source["title"], "target_label": target["title"],
            "predicate_iri": edge["predicate"], "direction": "source-to-target",
            "active": True, "lifecycle": "active", "plane": PLANE_IRI,
        })
    incidents = defaultdict(lambda: {"ids": set(), "chunks": set()})
    chunks = []
    for start in range(0, len(rows), RELATIONSHIPS_PER_CHUNK):
        path = f"relationships/chunk-{len(chunks):04d}.json.gz"
        shard = rows[start:start + RELATIONSHIPS_PER_CHUNK]
        for row in shard:
            validator.validate(row)
        binding = write(root, path, shard, compressed=True)
        chunks.append({**binding, "id": f"urn:okf:hansard:{path}",
                       "count": len(shard), "media_type": "application/json", "content_encoding": "gzip"})
        for edge in shard:
            for route in {edge["source"], edge["target"]}:
                incidents[route]["ids"].add(edge["id"])
                incidents[route]["chunks"].add(path)
    bucket_rows = defaultdict(list)
    for route, incident in sorted(incidents.items()):
        paths = sorted(incident["chunks"])
        identifiers = sorted(incident["ids"])
        if len(paths) > 64 or len(identifiers) > 100_000:
            raise ValueError(f"Assertion coverage exceeds the Reader limits for {route}")
        counts = {"planes": 1, "incident_assertions": len(identifiers),
                  "active_incident_assertions": len(identifiers), "chunk_references": len(paths),
                  "active_chunk_references": len(paths)}
        bucket_rows[sha(route.encode("utf-8"))[:2]].append({
            "route": route, "chunks": paths, "counts": counts,
            "planes": [{"name": PLANE, "assertions": len(identifiers),
                        "assertion_ids_sha256": sha(json_bytes(identifiers)), "chunks": paths}],
        })
    buckets = []
    totals = Counter()
    for bucket, routes in sorted(bucket_rows.items()):
        counts = {"routes": len(routes), "plane_commitments": len(routes)}
        for field in ("incident_assertions", "active_incident_assertions", "chunk_references"):
            counts[field] = sum(row["counts"][field] for row in routes)
        totals.update(counts)
        binding = write(root, f"relationships/bucket-{bucket}.json.gz", {
            "schema": "okf-rich-relationship-route-locator-bucket.v1",
            "generated_at": generated, "hash_algorithm": "sha256-utf8-first-byte-hex",
            "bucket": bucket, "routes": routes, "counts": counts,
        }, compressed=True)
        buckets.append({**binding, **counts, "bucket": bucket, "content_encoding": "gzip"})
    locator = write(root, "relationships/locator.json", {
        "schema": "okf-rich-relationship-route-locator.v1", "generated_at": generated,
        "hash_algorithm": "sha256-utf8-first-byte-hex",
        "bucket_path_template": "relationships/bucket-{prefix}.json.gz", "buckets": buckets,
        "counts": {**totals, "buckets": len(buckets)},
    })
    return write(root, "relationships/runtime.json", {
        "@id": "urn:okf:hansard:relationship-runtime", "schema": "okf-rich-relationship-runtime-manifest.v1",
        "snapshot": snapshot, "generated_at": generated, "semantic_manifest": "source.json",
        "assertion_contract": "schemas/semantic-assertion.schema.json",
        "row_contract": "schemas/relationship-runtime-row.schema.json",
        "default_planes": [PLANE], "route_locator": {
            "path": locator["path"], "sha256": locator["sha256"],
            "id": "urn:okf:hansard:relationship-locator", "routes": len(incidents), "buckets": len(buckets),
        },
        "planes": [{"id": PLANE_IRI, "name": PLANE, "active": True, "lifecycle": "active",
                    "authority_classes": ["derived"], "assertions": len(rows), "chunks": chunks}],
        "totals": {"active_assertions": len(rows), "historical_assertions": 0,
                   "rejected_assertions": 0, "all_assertions": len(rows), "chunks": len(chunks)},
        "loading_policy": "Load the selected route's digest-bound incident relationships.",
    })


def build(release, root):
    raw = (release / "okf-bundle.json").read_bytes()
    receipt = json.loads((release / "receipt.json").read_bytes())
    digest = sha(raw)
    if receipt["artifacts"]["okf-bundle.json"] != {"sha256": digest, "bytes": len(raw)}:
        raise ValueError("Explorer input differs from the release receipt")
    bundle = json.loads(raw)
    corpus = bundle["corpora"]["hansard"]
    title = bundle["meta"]["title"]
    generated = bundle["generated_at"]
    snapshot = f"hansard-sha256-{digest}"
    nodes, edges = corpus["nodes"], corpus["relationships"]
    root.mkdir(parents=True, exist_ok=False)
    (root / "schemas").mkdir()
    for name in ("semantic-assertion.schema.json", "relationship-runtime-row.schema.json"):
        (root / "schemas" / name).write_bytes((PROFILE / name).read_bytes())
    write(root, "source.json", {"snapshot": snapshot, "artifacts": receipt["artifacts"]})
    chunks, record_locator = publish_records(root, sorted(nodes.items()), snapshot)
    relationship_runtime = publish_relationships(root, nodes, edges, snapshot, generated)
    counts = {"datasets": len(nodes), "records": len(nodes), "resources": 0, "publishers": 0, "relationships": len(edges)}
    overview = write(root, "overview.json", {"title": title, "snapshot": snapshot, "counts": counts})
    manifest = write(root, "manifest.json", {
        "title": title, "snapshot": snapshot, "generated_at": generated, "counts": counts,
        "indexes": {"overview": overview, "record_locator": record_locator, "relationship_runtime": relationship_runtime},
        "chunks": {"datasets": [chunk["path"] for chunk in chunks], "relationships": [], "publishers": [], "resources": []},
        "shards": {"datasets": chunks},
    })
    write(root, "okf-explorer.json", {
        "schema": "okf-explorer-large-corpus.v1", "kind": "okf-large-corpus",
        "title": title, "snapshot": snapshot, "counts": counts,
        "entrypoints": {"data_manifest": manifest, "overview_index": overview,
                        "record_locator": record_locator, "relationship_runtime": relationship_runtime},
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.release, args.out)
