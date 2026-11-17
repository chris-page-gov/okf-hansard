"""Resolve a retained record to current official text on demand."""

import argparse
from functools import lru_cache
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from capture import HANSARD, MAX_BYTES, sha
from model import plain, read_sittings
from query import DEFAULT_RELEASE, Index

LOCATOR_FIELDS = ("external_id", "source_item_id", "value_sha256", "pointer", "url")


def build_locators(snapshot, release):
    manifest = json.loads((snapshot / "manifest.json").read_bytes())
    history = json.loads((release / "history.json").read_bytes())
    dates = [row["date"] for row in history["contributions"].values()]
    _, records, _, _ = read_sittings(snapshot, manifest, min(dates), max(dates))
    routes = set(history["contributions"])
    routes.update(row["contribution"] for rows in history["mentions"].values() for row in rows)
    payload = {route: {**{key: records[route][key] for key in LOCATOR_FIELDS},
                       "capture": records[route]["capture"]} for route in sorted(routes)}
    path = release / "source-locators.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(payload)} retained source locators · {sha(path.read_bytes())}")


class Passages:
    def __init__(self, index):
        self.index = index
        self.locators = json.loads((index.release / "source-locators.json").read_bytes())

    def locator(self, route):
        if route in self.locators:
            return self.locators[route]
        db = self.index.connect()
        if not db:
            return None
        try:
            row = db.execute("SELECT record FROM contribution WHERE route=?", (route,)).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            db.close()

    def read(self, route, offset=0, limit=6000, expected_sha256=None):
        loc = self.locator(route)
        if not loc:
            raise ValueError("This contribution ID has no retained source locator.")
        root_url = loc["capture"]["url"]
        if not re.fullmatch(re.escape(HANSARD) + r"/debates/debate/[A-Za-z0-9-]+\.json", root_url):
            raise ValueError("The retained Hansard endpoint is outside the allowlist.")
        obj = retrievable(root_url)
        for part in loc["pointer"].strip("/").split("/"):
            obj = obj[int(part)] if isinstance(obj, list) else obj[part]
        if obj["ExternalId"] != loc["external_id"] or obj["ItemId"] != loc["source_item_id"]:
            return {"schema": "hansard-source-passage.v1", "id": route, "url": loc["url"],
                    "status": "source locator changed", "source_api": root_url}
        raw_hash = sha(str(obj["Value"]).encode("utf-8"))
        if expected_sha256 and raw_hash != expected_sha256:
            raise ValueError("The source version no longer matches the requested hash.")
        text = plain(obj["Value"])
        end = min(offset + limit, len(text))
        return {"schema": "hansard-source-passage.v1", "id": route, "url": loc["url"],
                "source_api": root_url, "source_field": loc["pointer"] + "/Value",
                "status": "matches recorded version" if raw_hash == loc["value_sha256"] else "source text changed",
                "source_value_sha256": raw_hash, "recorded_source_value_sha256": loc["value_sha256"],
                "characters": len(text), "offset": offset, "next_offset": end if end < len(text) else None,
                "text": text[offset:end]}


@lru_cache(maxsize=6)
def retrievable(url):
    # Source pages are held in process memory only. A restart observes a new version.
    with urlopen(Request(url, headers={"Accept": "application/json",
                                       "User-Agent": "OKF-Hansard-Pilot/0.1"}), timeout=12) as response:
        if response.url != url:
            raise ValueError("The official endpoint redirected.")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("The contribution source exceeds the permitted read size.")
    return json.loads(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    args = parser.parse_args()
    build_locators(args.build, args.release)
