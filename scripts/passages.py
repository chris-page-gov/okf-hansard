"""Resolve a retained record to current official text on demand."""

import argparse
from functools import lru_cache
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from urllib.request import Request

from archive import unpack
from capture import HANSARD, MAX_BYTES, now, sha
from http_policy import open_source
from model import plain, read_sittings
from query import DEFAULT_RELEASE, Index
from safe_paths import resolve_within

LOCATOR_FIELDS = ("external_id", "source_item_id", "value_sha256", "pointer", "url", "section")
SOURCE_CACHE_SECONDS = 120


def build_locators(snapshot, release):
    manifest = json.loads(resolve_within(snapshot, "manifest.json").read_bytes())
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
        for package in self.index.auxiliary.values():
            for row in package["items"]:
                if row["contribution"] == route:
                    return row
        db = self.index.connect()
        if db:
            try:
                row = db.execute("SELECT record FROM contribution WHERE route=?", (route,)).fetchone()
                if row:
                    return json.loads(row[0])
            finally:
                db.close()
        older, _, _ = self.index.connect_older()
        if older:
            try:
                row = older.execute("SELECT record FROM contribution WHERE route=?", (route,)).fetchone()
                if row:
                    return json.loads(row[0])
            finally:
                older.close()
        return None

    def read(self, route, offset=0, limit=6000, expected_sha256=None):
        loc = self.locator(route)
        if not loc:
            raise ValueError("This contribution ID has no retained source locator.")
        root_url = loc["capture"]["url"]
        is_debate = re.fullmatch(re.escape(HANSARD) + r"/debates/debate/[A-Za-z0-9-]+\.json", root_url)
        is_search = re.fullmatch(re.escape(HANSARD) + r"/search/contributions/Spoken\.json\?[a-zA-Z0-9=%_+&.-]+",
                                 root_url)
        if not is_debate and not is_search:
            raise ValueError("The retained Hansard endpoint is outside the allowlist.")
        identifier_field = "ContributionExtId" if is_search else "ExternalId"
        text_field = "ContributionTextFull" if is_search else "Value"
        source_url, pointer, obj = root_url, loc["pointer"], None
        if is_debate and loc.get("section") == "Writtens":
            # A subsection usually answers much faster than a whole historical
            # Written Answers tree. Only accept an exact source item identity.
            path = urlparse(loc["url"]).path
            match = re.search(r"/debates/([A-Za-z0-9-]+)/", path)
            if match:
                candidate = f"{HANSARD}/debates/debate/{match.group(1)}.json"
                try:
                    result, observed_at = retrievable(candidate, 8)
                    hits = [(i, item) for i, item in enumerate(result["Items"])
                            if item["ExternalId"] == loc["external_id"] and item["ItemId"] == loc["source_item_id"]]
                    if len(hits) == 1:
                        source_url, pointer, obj = candidate, f"/Items/{hits[0][0]}", hits[0][1]
                except (OSError, ValueError, KeyError):
                    pass
        if obj is None:
            obj, observed_at = retrievable(root_url, 35 if loc.get("section") == "Writtens" else 12)
            for part in pointer.strip("/").split("/"):
                obj = obj[int(part)] if isinstance(obj, list) else obj[part]
        if obj[identifier_field] != loc["external_id"] or obj["ItemId"] != loc["source_item_id"]:
            return {"schema": "hansard-source-passage.v1", "id": route, "url": loc["url"],
                    "status": "source locator changed", "source_api": source_url, "observed_at": observed_at}
        raw_hash = sha(str(obj[text_field]).encode("utf-8"))
        recorded_hash = loc.get("source_value_sha256") or loc["value_sha256"]
        if expected_sha256 and raw_hash != expected_sha256:
            raise ValueError("The source version no longer matches the requested hash.")
        text = plain(obj[text_field])
        end = min(offset + limit, len(text))
        return {"schema": "hansard-source-passage.v1", "id": route, "url": loc["url"],
                "source_api": source_url, "source_field": pointer + "/" + text_field, "observed_at": observed_at,
                "member_id": obj.get("MemberId"),
                "status": "matches recorded version" if raw_hash == recorded_hash else "source text changed",
                "source_value_sha256": raw_hash, "recorded_source_value_sha256": recorded_hash,
                "characters": len(text), "offset": offset, "next_offset": end if end < len(text) else None,
                "text": text[offset:end]}


def retrievable(url, timeout=12):
    return read_source(url, timeout, int(time.monotonic() // SOURCE_CACHE_SECONDS))


@lru_cache(maxsize=6)
def read_source(url, timeout, window):
    # The monotonic window bounds reuse. The response keeps its own observation time.
    request = Request(url, headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                                    "User-Agent": "OKF-Hansard-Pilot/0.1"})
    with open_source(request, timeout=timeout) as response:
        if response.url != url:
            raise ValueError("The official endpoint redirected.")
        raw = unpack(response.read(MAX_BYTES + 1), response.headers.get("Content-Encoding", ""))
    if len(raw) > MAX_BYTES:
        raise ValueError("The contribution source exceeds the permitted read size.")
    return json.loads(raw), now()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    args = parser.parse_args()
    build_locators(args.build, args.release)
