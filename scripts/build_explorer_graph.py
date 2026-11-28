"""Project a verified Hansard release into Explorer's route-scoped runtime."""

import argparse
from collections import Counter, defaultdict
import gzip
from hashlib import file_digest
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from capture import sha
from build_core_projection import document as read_core_document
from okf_core import PRODUCT_VERSION

PROFILE = Path(__file__).resolve().parents[1] / "profile"
RECORDS_PER_CHUNK = 32
RELATIONSHIPS_PER_CHUNK = 96
HUB_MINIMUM_INCIDENT_ASSERTIONS = 72
MAX_ROUTE_CHUNKS = 64
MAX_ROUTE_ROWS = 100_000
MAX_ROUTE_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ROUTE_RETAINED_TEXT_UNITS = 32 * 1024 * 1024
MAX_ROW_RETAINED_TEXT_UNITS = 32 * 1024
CORE_SOURCE_DETAILS_PATH = "core-source-binding.json"
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


def publish_records(root, records, snapshot, core_documents):
    locations = defaultdict(dict)
    chunks = []
    for start in range(0, len(records), RECORDS_PER_CHUNK):
        rows = []
        ordinal = len(chunks)
        for index, (identifier, source) in enumerate(records[start:start + RECORDS_PER_CHUNK]):
            route = dataset_route(identifier)
            core = core_documents.get(identifier)
            row = {
                "name": identifier, "route": route, "title": source["title"],
                "record_type": source["type"], "notes": source.get("body") or source.get("description") or "",
                "resource_count": 0, "tags": [], "formats": [],
                "core_role": core["role"] if core else "extension",
            }
            if core:
                row.update({"source_markdown": core["markdown"], "source_frontmatter": core["frontmatter"],
                            "source_sha256": core["sha256"], "source_bytes": core["bytes"]})
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


def ordered_relationships(relationships):
    degree = Counter(route for edge in relationships for route in {edge["source"], edge["target"]})

    def shard_order(edge):
        source, target = edge["source"], edge["target"]
        hub = min((source, target), key=lambda route: (-degree[route], route))
        if degree[hub] >= HUB_MINIMUM_INCIDENT_ASSERTIONS:
            return 0, hub, source, target, edge["id"]
        return 1, source, source, target, edge["id"]

    return sorted(relationships, key=shard_order)


def retained_text_bound(row):
    # UTF-8 JSON bytes conservatively bound the UTF-16 length of the text it
    # stores. The Reader also retains aliases for the source and target routes.
    aliases = len(row["source"].encode("utf-8")) + len(row["target"].encode("utf-8"))
    return len(json_bytes(row)) + aliases


def publish_relationships(root, records, relationships, snapshot, generated):
    rows = []
    identifiers = set()
    row_schema = json.loads((PROFILE / "relationship-runtime-row.schema.json").read_bytes())
    validator = Draft202012Validator(row_schema)
    for edge in ordered_relationships(relationships):
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
    chunk_budgets = {}
    for start in range(0, len(rows), RELATIONSHIPS_PER_CHUNK):
        path = f"relationships/chunk-{len(chunks):04d}.json.gz"
        shard = rows[start:start + RELATIONSHIPS_PER_CHUNK]
        retained_bound = 0
        for row in shard:
            validator.validate(row)
            bound = retained_text_bound(row)
            if bound > MAX_ROW_RETAINED_TEXT_UNITS:
                raise ValueError(f"Assertion text exceeds the Reader limit for {row['id']}")
            retained_bound += bound
        binding = write(root, path, shard, compressed=True)
        chunk_budgets[path] = (len(shard), binding["bytes"], retained_bound)
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
        shard_rows, compressed_bytes, retained_bound = map(sum, zip(*(chunk_budgets[path] for path in paths)))
        if (
            len(paths) > MAX_ROUTE_CHUNKS
            or max(len(identifiers), shard_rows) > MAX_ROUTE_ROWS
            or compressed_bytes > MAX_ROUTE_COMPRESSED_BYTES
            or retained_bound > MAX_ROUTE_RETAINED_TEXT_UNITS
        ):
            raise ValueError(
                f"Assertion coverage for {route} exceeds the Reader limits "
                f"({len(paths)} shards, {shard_rows} shard rows, {compressed_bytes} compressed bytes, "
                f"{retained_bound} retained text units at most)"
            )
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
    title = bundle["meta"]["title"]
    generated = bundle["generated_at"]
    semantic_path = release / "okf-bundle.yamlld"
    with semantic_path.open("rb") as stream:
        semantic_digest = file_digest(stream, "sha256").hexdigest()
    with semantic_path.open(encoding="utf-8") as stream:
        context_line = stream.readline()
        meta_line = stream.readline()
        graph_marker = stream.readline().strip()
        if not context_line.startswith('"@context": ') or graph_marker != '"@graph":':
            raise ValueError("Full YAML-LD graph has an unexpected serialisation")
        json.loads(context_line.split(": ", 1)[1])
        semantic_meta = json.loads(meta_line.removeprefix("meta: "))
        if semantic_meta["okf_core"]["version"] != "0.3":
            raise ValueError("Full YAML-LD graph is not an OKF 0.3 source")
        source_nodes, source_edges = [], []
        for line in stream:
            if not line.startswith("- "):
                raise ValueError("Full YAML-LD graph has a non-JSON graph row")
            row = json.loads(line[2:])
            (source_edges if "source_route" in row else source_nodes).append(row)
    if semantic_meta["okf_core"]["version"] != "0.3":
        raise ValueError("Full YAML-LD graph is not an OKF 0.3 source")
    snapshot = f"hansard-sha256-{digest}"
    nodes = {}
    iri_by_route = {}
    for source in source_nodes:
        route = source["route"]
        iri_by_route[route] = source["@id"]
        nodes[route] = {
            "title": source["title"], "type": source["type"], "body": source.get("body", ""),
            "semantic_id": source["@id"], "url": source.get("url"), "date": source.get("date"),
            "hansard_proceedings": source.get("hansard_proceedings"),
            "hansard_summary": source.get("hansard_summary"),
        }
        nodes[route] = {key: value for key, value in nodes[route].items() if value is not None}
    edges = []
    for row in source_edges:
        edges.append({
            "id": row["@id"], "source": row["source_route"], "target": row["target_route"],
            "source_iri": row["source"]["@id"], "target_iri": row["target"]["@id"],
            "predicate": row["predicate"]["@id"], "kind": row["kind"], "label": row["label"],
            "inverse_label": row["inverse_label"], "assertion_status": row["assertion_status"],
            "assertion_scope": row["assertion_scope"], "observed_at": row["observed_at"],
            "derivation": row["derivation"], "authority": row["authority"],
            "evidence": row["evidence"], "rights": row["rights"],
        })
    if len(edges) != len(source_edges) or any(edge["source"] not in nodes or edge["target"] not in nodes for edge in edges):
        raise ValueError("Full YAML-LD relationships reference missing source nodes")
    markdown_root = release / "markdown"
    source_paths = sorted(markdown_root.rglob("*.md"), key=lambda path: path.relative_to(markdown_root).as_posix())
    core_documents = {path.relative_to(markdown_root).as_posix(): read_core_document(path, markdown_root)
                      for path in source_paths}
    source_only_concepts = [item for item in core_documents.values()
                            if item["role"] == "concept" and item["path"] not in nodes]
    support_documents = [item for item in core_documents.values()
                         if item["path"] not in nodes and item["role"] != "concept"]
    core_manifest = [{"path": item["path"], "role": item["role"], "sha256": item["sha256"],
                      "bytes": item["bytes"],
                      "record_route": dataset_route(item["path"]) if item["role"] == "concept" or item["path"] in nodes else None,
                      "access": "record_chunks" if item["role"] == "concept" or item["path"] in nodes else "source_manifest"}
                     for item in (core_documents[path] for path in sorted(core_documents))]
    core_snapshot = sha(json_bytes(core_manifest))
    source_only_rows = []
    for item in source_only_concepts:
        fields = item["frontmatter"]
        source_only_rows.append((item["path"], {
            "title": fields.get("title", item["path"]), "type": fields.get("type", "Core concept"),
            "body": item["body"], "semantic_id": fields.get("@id"),
            "url": fields.get("url"), "date": fields.get("date"),
        }))
    record_rows = [*nodes.items(), *source_only_rows]
    root.mkdir(parents=True, exist_ok=False)
    (root / "schemas").mkdir()
    for name in ("semantic-assertion.schema.json", "relationship-runtime-row.schema.json"):
        (root / "schemas" / name).write_bytes((PROFILE / name).read_bytes())
    write(root, "source.json", {"snapshot": snapshot, "artifacts": receipt["artifacts"],
                               "full_semantic_source": {"path": "okf-bundle.yamlld",
                                                        "sha256": semantic_digest,
                                                        "bytes": semantic_path.stat().st_size,
                                                        "assertions": len(edges),
                                                        "records": len(nodes)}})
    chunks, record_locator = publish_records(root, sorted(record_rows), snapshot, core_documents)
    relationship_runtime = publish_relationships(root, nodes, edges, snapshot, generated)
    counts = {"datasets": len(record_rows), "records": len(record_rows), "resources": 0,
              "publishers": 0, "relationships": len(edges)}
    overview = write(root, "overview.json", {"title": title, "snapshot": snapshot, "counts": counts})
    manifest = write(root, "manifest.json", {
        "title": title, "snapshot": snapshot, "generated_at": generated, "counts": counts,
        "indexes": {"overview": overview, "record_locator": record_locator, "relationship_runtime": relationship_runtime},
        "chunks": {"datasets": [chunk["path"] for chunk in chunks], "relationships": [], "publishers": [], "resources": []},
        "shards": {"datasets": chunks},
    })
    support_manifest = [{key: item[key] for key in
                         ("path", "role", "sha256", "bytes", "markdown", "frontmatter", "body")}
                        for item in support_documents]
    details_document = {
        "schema": "okf-core-source-binding-details.v1",
        "snapshot": "hansard-markdown-sha256-" + core_snapshot,
        "documents": core_manifest,
        "support_documents": support_manifest,
    }
    details_schema = json.loads((PROFILE / "core-source-binding-details.schema.json").read_bytes())
    Draft202012Validator(details_schema).validate(details_document)
    source_details = write(root, CORE_SOURCE_DETAILS_PATH, details_document)
    source_details.update({"media_type": "application/json", "content_encoding": "identity"})
    core_source = {
        "schema": "okf-core-source-binding.v2", "snapshot": "hansard-markdown-sha256-" + core_snapshot,
        "core_specification": bundle["meta"]["okf_core"]["specification"],
        "semantic_profile": bundle["meta"].get("profile"),
        "source_documents": len(core_manifest),
        "concepts": sum(item["role"] == "concept" for item in core_manifest),
        "concept_records": sum(item["role"] == "concept" for item in core_manifest),
        "source_only_concept_records": len(source_only_concepts),
        "navigation_documents": sum(item["role"] == "navigation" for item in core_manifest),
        "extension_documents": sum(item["role"] == "extension" for item in core_manifest),
        "extension_records_without_markdown": len(set(nodes) - set(core_documents)),
        "relationship_assertions": len(edges), "detail_resource": "record_chunks",
        "source_manifest": source_details,
        "relationship_limit": "All concepts, navigation documents and extensions are preserved as exact Markdown in record detail shards. The existing graph relationship shards retain the complete assertion set.",
    }
    binding_schema = json.loads((PROFILE / "core-source-binding.schema.json").read_bytes())
    Draft202012Validator(binding_schema).validate(core_source)
    write(root, "okf-explorer.json", {
        "schema": "okf-explorer-large-corpus.v1", "kind": "okf-large-corpus",
        "id": "urn:okf:hansard:bundle:" + "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-"),
        "version": PRODUCT_VERSION,
        "okf_version": bundle["okf_version"],
        "title": title, "snapshot": snapshot, "counts": counts,
        "core_source": core_source,
        "entrypoints": {"data_manifest": manifest, "overview_index": overview,
                        "record_locator": record_locator, "relationship_runtime": relationship_runtime},
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.release, args.out)
