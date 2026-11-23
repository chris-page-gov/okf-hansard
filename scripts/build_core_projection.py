"""Build the small Reader bundle from the exact published OKF Markdown."""

import argparse
import hashlib
import json
from pathlib import Path
import re

import yaml

from model import PROFILE
from okf_core import CORE_SPEC, CORE_VERSION, RESERVED


PRODUCT_VERSION = "0.3.0"


def document(path, root):
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    fields = {}
    body = text
    if text.startswith("---\n"):
        header, marker, body = text[4:].partition("\n---\n")
        if not marker:
            raise ValueError(f"Unclosed frontmatter in {path.relative_to(root)}")
        fields = json.loads(header) if header.startswith("{") else yaml.safe_load(header)
        if not isinstance(fields, dict):
            raise ValueError(f"Invalid frontmatter in {path.relative_to(root)}")
    route = path.relative_to(root).as_posix()
    role = "navigation" if path.name in RESERVED else (
        "concept" if isinstance(fields.get("type"), str) else "extension")
    if "core_role" in fields and fields["core_role"] != role:
        raise ValueError(f"Markdown core_role differs from its typed source role: {path.relative_to(root)}")
    if role == "navigation" and path.name == "log.md":
        raise ValueError("This small public source root does not publish a log")
    return {
        "path": route,
        "role": role,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "frontmatter": fields,
        "markdown": text,
        "body": body.removeprefix("\n"),
    }


def build(source_root, output, *, check=False):
    if not source_root.is_dir():
        raise FileNotFoundError(source_root)
    files = sorted(source_root.rglob("*.md"), key=lambda item: item.relative_to(source_root).as_posix())
    if not files or any(path.is_symlink() or not path.is_file() for path in files):
        raise ValueError("The public Markdown root must contain regular files")
    docs = [document(path, source_root) for path in files]
    roots = [item for item in docs if item["path"] == "index.md"]
    if len(roots) != 1 or roots[0]["role"] != "navigation":
        raise ValueError("The public core projection requires exactly one reserved root index")
    concepts = [item for item in docs if item["role"] == "concept"]
    if not concepts:
        raise ValueError("The public core projection must cover at least one typed concept")
    commitment = hashlib.sha256(json.dumps(
        [{"path": item["path"], "sha256": item["sha256"]} for item in docs],
        sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    title = roots[0]["frontmatter"].get("title", source_root.name)
    bundle_slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    descriptor = {
        "schema": "okf-explorer-bundle.v0",
        "kind": "okf-bundle",
        "id": "urn:okf:hansard:public-core:" + bundle_slug,
        "version": PRODUCT_VERSION,
        "snapshot": "hansard-markdown-sha256-" + commitment,
        "okf_version": CORE_VERSION,
        "title": title,
        "core_specification": CORE_SPEC,
        "semantic_profile": PROFILE,
        "source_documents": [{key: item[key] for key in ("path", "role", "sha256", "bytes")} for item in docs],
        "meta": {
            "title": title,
            "profile": PROFILE,
            "okf_core": {"version": CORE_VERSION, "specification": CORE_SPEC},
            "source_document_count": len(docs),
            "core_concept_count": len(concepts),
            "navigation_document_count": sum(item["role"] == "navigation" for item in docs),
            "extension_document_count": sum(item["role"] == "extension" for item in docs),
            "relationship_count": 0,
            "relationship_limit": "This compact core Reader projection contains the exact Markdown documents and does not assert graph relationships. Use the separately digest-bound graph descriptor for graph traversal.",
        },
        "corpora": {
            "hansard": {
                "id": "hansard",
                "title": title,
                "root": "index.md",
                "assertion_scope": "real-world",
                "nodes": {
                    item["path"]: {
                        "id": item["path"],
                        "title": item["frontmatter"].get("title", item["path"]),
                        "type": item["frontmatter"].get("type", "Index" if item["role"] == "navigation" else "Supporting document"),
                        "section": item["role"],
                        "core_role": item["role"],
                        "body": item["body"],
                        "source_markdown": item["markdown"],
                        "source_frontmatter": item["frontmatter"],
                        "source_sha256": item["sha256"],
                        "source_bytes": item["bytes"],
                        "resource": item["frontmatter"].get("resource"),
                        "sources": item["frontmatter"].get("sources", []),
                        "aliases": [],
                        "tags": [],
                    }
                    for item in docs
                },
                "relationships": [],
            }
        },
    }
    target = output / "okf-core.json"
    output.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(descriptor, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if check:
        if not target.is_file() or target.read_bytes() != encoded:
            raise ValueError("okf-core.json differs from the exact Markdown source projection")
    else:
        target.write_bytes(encoded)
    return {"concepts": len(concepts), "indexes": sum(item["path"].endswith("index.md") for item in docs),
            "documents": len(docs), "snapshot": descriptor["snapshot"],
            "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Published Markdown directory, such as site/okf")
    parser.add_argument("output", type=Path, help="Published directory receiving okf-core.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, check=args.check), indent=2))
