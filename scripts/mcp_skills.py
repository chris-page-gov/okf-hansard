"""Expose the reviewed, instructions-only Hansard skill as MCP resources."""

from functools import cache
from pathlib import Path

import yaml

from capture import sha
from hansard_access import read

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "profile/voice-retrieval.json"
SKILL = read(CONTRACT)["skill"]
NAME = SKILL["name"]
URI = SKILL["uri"]
EXTENSION = SKILL["extension"]
MIME = "text/markdown"


@cache
def skill_files():
    """Load a fixed set of files once so advertised digests match every read."""
    directory = ROOT / "skills" / NAME
    files = {}
    for relative in SKILL["files"]:
        path = directory / relative
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("An unsafe Hansard skill file was configured.")
        files[f"skill://{NAME}/{relative}"] = path.read_bytes()
    raw = files[URI].decode("utf-8")
    opening, frontmatter, _ = raw.split("---\n", 2)
    metadata = yaml.safe_load(frontmatter)
    if opening or metadata["name"] != NAME or not metadata["description"]:
        raise ValueError("The Hansard skill frontmatter does not match its contract.")
    return files, metadata


def entry():
    files, metadata = skill_files()
    return {"uri": URI, "frontmatter": metadata, "resources": [
        {"uri": uri, "digest": f"sha256:{sha(data)}", "size": len(data)}
        for uri, data in files.items()
    ]}


def resource(uri):
    return {"uri": uri, "mimeType": MIME, "name": NAME if uri == URI else uri.rsplit("/", 1)[-1]}


def stage_skill(site):
    destination = site / "skills" / NAME
    files, _ = skill_files()
    for relative in SKILL["files"]:
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[f"skill://{NAME}/{relative}"])


def result_for(method, params):
    files, metadata = skill_files()
    if method == "skills/list":
        return {"skills": [entry()]}
    if method == "skills/get" and params.get("uri") == URI:
        return {"skill": entry()}
    if method == "resources/list":
        listing = [resource(uri) for uri in files]
        listing[0]["description"] = metadata["description"]
        return {"resources": listing}
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    uri = params.get("uri")
    if method == "resources/read" and isinstance(uri, str) and uri in files:
        return {"contents": [{"uri": uri, "mimeType": MIME, "text": files[uri].decode("utf-8")}]}
    raise ValueError("Unknown Hansard skill or resource URI.")
