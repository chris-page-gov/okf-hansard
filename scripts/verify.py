"""Verify pilot digests, relationship locators, text ranges and reader facets."""

import argparse
from collections import Counter
from functools import lru_cache
from hashlib import file_digest
import json
from pathlib import Path

from rdflib import Graph, RDF, URIRef

from build import BUILD_ARTIFACTS, canonical_field, digest
from capture import dump, sha
from model import plain
from okf_core import CORE_VERSION, RESERVED, check_markdown


def pointer(value, ref):
    for part in ref.lstrip("/").split("/"):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def verify_build_artifacts(release, *, expected_version=None):
    path = release / "receipt.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing regular Hansard build receipt.")
    receipt = json.loads(path.read_bytes())
    if not isinstance(receipt, dict):
        raise ValueError("The Hansard build receipt is not an object.")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("The Hansard build receipt has no artefact inventory.")
    if expected_version is not None:
        if receipt.get("schema") != "hansard-build-receipt.v1" or receipt.get("okf_version") != expected_version:
            raise ValueError("The cached Hansard build receipt has an incompatible schema or OKF version.")
        if not set(BUILD_ARTIFACTS) <= artifacts.keys():
            raise ValueError("The cached Hansard build receipt is missing required artefacts.")
    for name, facts in artifacts.items():
        artifact = release / name
        if not name or Path(name).name != name or "\\" in name or artifact.is_symlink() or not artifact.is_file():
            raise ValueError(f"Unsafe or missing Hansard build artefact: {name}")
        if not isinstance(facts, dict) or artifact.stat().st_size != facts.get("bytes"):
            raise ValueError(f"Artefact integrity mismatch: {name}")
        with artifact.open("rb") as stream:
            if file_digest(stream, "sha256").hexdigest() != facts.get("sha256"):
                raise ValueError(f"Artefact integrity mismatch: {name}")
    return receipt


def check(release, source, people, report):
    receipt = verify_build_artifacts(release)

    @lru_cache(maxsize=64)
    def resource(root, path, expected):
        raw = (root / path).read_bytes()
        if sha(raw) != expected:
            raise ValueError(f"Capture file digest mismatch: {path}")
        return json.loads(raw)

    predicates = Counter()
    failed = Counter()
    failures = []
    graph_rows = {}
    samples = {}
    with (release / "okf-bundle.yamlld").open(encoding="utf-8") as stream:
        context = json.loads(stream.readline().split(": ", 1)[1])
        header = stream.readline()
        if not header.startswith("meta: ") or stream.readline().strip() != '"@graph":':
            raise ValueError("Unexpected YAML-LD layout")
        for line in stream:
            row = json.loads(line.removeprefix("- "))
            if "predicate" not in row:
                graph_rows[row["@id"]] = row
                continue
            key = row["predicate"]["@id"]
            predicates[key] += 1
            samples.setdefault(key, row)
            for ev in row["evidence"]:
                root = source if "hansard-api" in ev["resource"] else people
                try:
                    value = pointer(resource(root, ev["source_artifact"], ev["source_sha256"]), ev["source_field"])
                    if digest(canonical_field(value)) != ev["source_value_sha256"]:
                        raise ValueError("Source value hash differs")
                    if ev.get("spans"):
                        selected = plain(value)
                        if "normalised_value_sha256" in ev and digest(selected) != ev["normalised_value_sha256"]:
                            raise ValueError("Normalised value hash differs")
                        for span in ev["spans"]:
                            if selected[span["start"]:span["end"]] != span["exact"]:
                                raise ValueError("Text position does not recover the asserted span")
                except (ValueError, KeyError, IndexError) as exc:
                    failed[(key, str(exc))] += 1
                    if len(failures) < 15:
                        failures.append({"predicate": key, "error": str(exc),
                                         "source": ev["resource"], "field": ev["source_field"]})
    sample_node_ids = {sample[side]["@id"] for sample in samples.values() for side in ("source", "target")}
    sample_graph = {"@context": context, "@graph": [
        *[graph_rows[node_id] for node_id in sorted(sample_node_ids)], *samples.values()
    ]}
    rdf = Graph().parse(data=json.dumps(sample_graph), format="json-ld")
    for sample in samples.values():
        statement = URIRef(sample["@id"])
        source_id = URIRef(sample["source"]["@id"])
        target_id = URIRef(sample["target"]["@id"])
        predicate = URIRef(sample["predicate"]["@id"])
        if (statement, RDF.subject, source_id) not in rdf or (source_id, predicate, target_id) not in rdf:
            raise ValueError(f"Missing direct or reified RDF triple for {statement}")
    bundle = json.loads((release / "okf-bundle.json").read_bytes())
    declared = bundle["meta"]["learning_presentation"]["facets"]
    nodes = bundle["corpora"]["hansard"]["nodes"]
    week = [n for n in nodes.values() if n["section"] == "Pilot week"]
    for facet in declared:
        values = {v for node in week for v in node["learning_facets"][facet["key"]] if v != "Unrecorded"}
        if len(values) < 2:
            raise ValueError(f"No meaningful separation for facet {facet['key']}")
    result = {"schema": "hansard-verification.v1", "passed": not failed,
              "assertions": sum(predicates.values()), "predicates": len(predicates),
              "rdf_sample_triples": len(rdf), "visible_facet_declarations": len(declared),
              "contributions": len(week), "failures": [{"predicate": k, "error": e, "count": n}
                                                       for (k, e), n in failed.items()],
              "failure_examples": failures}
    if receipt.get("okf_version") == CORE_VERSION:
        if (bundle.get("okf_version") != CORE_VERSION
                or json.loads(header.removeprefix("meta: "))["okf_core"]["version"] != CORE_VERSION
                or len(graph_rows) != receipt["semantic_records"]
                or any(Path(row["route"]).name in RESERVED for row in graph_rows.values())):
            raise ValueError("OKF 0.3 version or semantic concept count differs from the build receipt")
        result["okf_core"] = check_markdown(release / "markdown")
    dump(report, result)
    print(json.dumps({k: v for k, v in result.items() if k != "failure_examples"}, indent=2))
    return not failed


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--snapshot", type=Path, required=True)
    p.add_argument("--people", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    raise SystemExit(not check(args.release, args.snapshot, args.people, args.report))
