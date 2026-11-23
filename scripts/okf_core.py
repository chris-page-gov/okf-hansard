"""Write and validate the Hansard producer's OKF 0.3 Markdown."""

from collections import defaultdict
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

import yaml


CORE_VERSION = "0.3"
PRODUCT_VERSION = "0.3.0"
PROFILE = "https://chris-page-gov.github.io/okf-hansard/profile/hansard-domain-v2.json"
CORE_SPEC = ("https://github.com/open-knowledge-format/open-knowledge-format/blob/"
             "527e81aff55992be21507e97004286789126f88c/SPEC.md")
LICENCE = "https://www.parliament.uk/site-information/copyright/open-parliament-licence/"
RESERVED = {"index.md", "log.md"}


def write_document(path, fields, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    path.write_text(f"---\n{frontmatter}\n---\n\n{body.rstrip()}\n", encoding="utf-8")


def write_index(root, title, description, body):
    write_document(root / "index.md", {
        "okf_version": CORE_VERSION, "title": title, "description": description,
        "license": "LICENSE.md", "semantic_profile": PROFILE,
        "product_version": PRODUCT_VERSION, "x-hansard-specification": CORE_SPEC,
    }, body)
    (root / "LICENSE.md").write_text(
        "# Open Parliament Licence\n\n"
        "Contains Parliamentary information licensed under the Open Parliament Licence v3.0.\n\n"
        f"[Licence and exclusions]({LICENCE})\n", encoding="utf-8")


def index_link(label, target):
    escaped = re.sub(r"([\\\[\]`*_<>])", r"\\\1", label.replace("\n", " "))
    return f"- [{escaped}]({quote(target, safe='/')})"


def write_release_markdown(root, records, first, last, title, context):
    listings = defaultdict(list)
    for route, record in records.items():
        relative = Path(route)
        if relative.name in RESERVED or record.get("date", first) < first:
            continue
        fields = {key: value for key, value in record.items()
                  if key != "body" and not key.startswith("hansard:")}
        fields["@context"] = context
        if url := record.get("url"):
            fields["resource"] = url
            fields["sources"] = [{"id": "record", "resource": url}]
        write_document(root / relative, fields, record.get("body", ""))
        entry = index_link(record["title"], relative.name)
        if description := record.get("description"):
            entry += " - " + " ".join(description.split())
        listings[relative.parent].append(entry)

    for folder in sorted(listings, key=lambda path: len(path.parts), reverse=True):
        while folder != Path("."):
            if folder not in listings:
                listings[folder] = []
            entry = index_link(folder.name.replace("-", " ").capitalize(), folder.name + "/")
            if entry in listings[folder.parent]:
                break
            listings[folder.parent].append(entry)
            folder = folder.parent
    for folder, entries in listings.items():
        content = "\n".join([f"# {title if folder == Path('.') else folder.name.replace('-', ' ').capitalize()}",
                              "", *sorted(entries)])
        if folder == Path("."):
            description = f"Westminster proceedings from {first} to {last}."
            write_index(root, title, description, content)
        else:
            (root / folder / "index.md").write_text(content + "\n", encoding="utf-8")


def check_markdown(root):
    concepts = indexes = 0
    for path in root.rglob("*.md"):
        raw = path.read_text(encoding="utf-8")
        frontmatter = None
        body = raw
        if raw.startswith("---\n"):
            header, marker, body = raw[4:].partition("\n---\n")
            if not marker:
                raise ValueError(f"Unclosed OKF frontmatter in {path.relative_to(root)}")
            # Release frontmatter is JSON flow syntax, which is also YAML 1.2.
            frontmatter = json.loads(header) if header.startswith("{") else yaml.safe_load(header)
            if not isinstance(frontmatter, dict):
                raise ValueError(f"Invalid OKF frontmatter in {path.relative_to(root)}")
        if path.name == "index.md":
            indexes += 1
            if path.parent == root:
                if (not frontmatter or frontmatter.get("okf_version") != CORE_VERSION
                        or "type" in frontmatter or not (root / frontmatter.get("license", "LICENSE.md")).is_file()):
                    raise ValueError("Invalid OKF 0.3 root index")
            elif frontmatter is not None:
                raise ValueError(f"Frontmatter in a subdirectory index: {path.relative_to(root)}")
            for link in re.findall(r"^[-*] .*?\]\(([^)]+)\)", body, re.MULTILINE):
                uri = urlsplit(link)
                if uri.scheme or uri.netloc:
                    continue
                reference = unquote(uri.path)
                destination = (root / reference.lstrip("/") if reference.startswith("/")
                               else path.parent / reference)
                if destination.is_dir():
                    destination /= "index.md"
                if not destination.resolve().is_relative_to(root.resolve()) or not destination.is_file():
                    raise ValueError(f"Unresolved OKF index link {link} in {path.relative_to(root)}")
        elif path.name == "log.md":
            dates = re.findall(r"^## (\d{4}-\d{2}-\d{2})$", body, re.MULTILINE)
            if frontmatter is not None or not dates or dates != sorted(dates, reverse=True):
                raise ValueError(f"Invalid OKF log: {path.relative_to(root)}")
        elif frontmatter is not None and frontmatter.get("type"):
            if not isinstance(frontmatter["type"], str):
                raise ValueError(f"Invalid concept type in {path.relative_to(root)}")
            if frontmatter.get("core_role", "concept") != "concept":
                raise ValueError(f"A typed Markdown concept must have core_role concept: {path.relative_to(root)}")
            concepts += 1
    if not (root / "index.md").is_file() or not concepts:
        raise ValueError("The OKF directory needs a root index and concepts")
    return {"version": CORE_VERSION, "concepts": concepts, "indexes": indexes}
