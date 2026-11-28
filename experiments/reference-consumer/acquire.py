"""Acquire a fixed public Hansard bundle and dependencies, with an HTTPS trace."""

import argparse
from datetime import UTC, datetime
from hashlib import sha256
from http.client import HTTPSConnection
import json
from pathlib import Path
import ssl

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "contract.json"
HOST = "raw.githubusercontent.com"
MAX_FILE = 2 * 1024 * 1024


def digest(data):
    return sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write_json(path, value):
    temporary = path.with_suffix(".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def catalogue(folder, contract):
    raw = safe_path(folder, "checksums.json").read_bytes()
    if digest(raw) != contract["catalogue_sha256"]:
        raise ValueError("Pinned publication catalogue digest differs.")
    return json.loads(raw)


def safe_path(root, relative):
    path = root / relative
    if any(part in {"..", "."} for part in Path(relative).parts) or Path(relative).is_absolute():
        raise ValueError("Unsafe relative asset path.")
    if path.resolve() != root.resolve() / relative:
        raise ValueError("The public bundle may not use symbolic links.")
    return path


def verify_public(folder, contract):
    manifest = catalogue(folder, contract)
    for relative in contract["files"]:
        path = safe_path(folder, relative)
        reference = manifest[relative]
        if not path.is_file() or path.stat().st_size != reference["bytes"] or reference["bytes"] > MAX_FILE:
            raise ValueError(f"Missing or unexpected asset size: {relative}")
        if digest(path.read_bytes()) != reference["sha256"]:
            raise ValueError(f"Asset digest differs: {relative}")
    return manifest


def fetch(remote_path, trace, limit):
    # No credentials, proxy configuration, dynamic URLs or redirects enter this request.
    connection = HTTPSConnection(HOST, context=ssl.create_default_context(), timeout=30)
    event = {"method": "GET", "destination": HOST, "path": remote_path}
    try:
        connection.connect()
        event["peer"] = connection.sock.getpeername()[0]
        connection.request("GET", remote_path, headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        event["status"] = response.status
        if response.status != 200:
            raise ValueError(f"Public fetch returned HTTP {response.status}.")
        data = response.read(limit + 1)
        event["response_bytes"] = len(data)
        if len(data) > limit:
            raise ValueError("The public response exceeds its size bound.")
        return data
    finally:
        connection.close()
        trace.append(event)


def acquire(folder, contract):
    folder.mkdir(parents=True, exist_ok=False)
    source = contract["source"]
    prefix = f"/{source['repository']}/{source['commit']}/"
    trace = []
    try:
        (folder / "checksums.json").write_bytes(fetch(prefix + "checksums.json", trace, MAX_FILE))
        manifest = catalogue(folder, source)
        for relative in source["files"]:
            path = safe_path(folder, relative)
            limit = manifest[relative]["bytes"]
            if not 0 < limit <= MAX_FILE:
                raise ValueError(f"Public file outside size bounds: {relative}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(fetch(prefix + relative, trace, limit))
        verify_public(folder, source)
        return {"completed_at": datetime.now(UTC).isoformat(), "commit": source["commit"],
                "catalogue_sha256": source["catalogue_sha256"], "assets": len(source["files"])}
    finally:
        write_json(folder / "network-audit.json", trace)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("public", type=Path)
    args = parser.parse_args()
    result = acquire(args.public.resolve(), read(CONTRACT))
    trace = (args.public / "network-audit.json").read_bytes()
    write_json(args.public / "acquisition.json", {**result, "network_audit_sha256": digest(trace)})
