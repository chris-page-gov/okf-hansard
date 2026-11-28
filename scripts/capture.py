"""Capture versioned, bounded Hansard API inputs for offline replay."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from safe_paths import resolve_within

HANSARD = "https://hansard-api.parliament.uk"
MEMBERS = "https://members-api.parliament.uk/api/Members/Search"
BILLS = "https://bills-api.parliament.uk/api/v1/Bills"
HOUSES = ("Commons", "Lords")
MAX_BYTES = 20 * 1024 * 1024


def dump(path, value, *, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    formatting = {"separators": (",", ":")} if compact else {"indent": 2}
    tmp.write_text(json.dumps(value, ensure_ascii=False, **formatting) + "\n", encoding="utf-8")
    tmp.replace(path)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fetch(root, relative, url):
    root.mkdir(parents=True, exist_ok=True)
    path = resolve_within(root, relative)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "OKF-Hansard-Pilot/0.1"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=12) as response:
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError(f"Response exceeds capture limit: {url}")
            obj = json.loads(raw)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return obj, {"path": relative, "url": url, "sha256": sha(raw), "retrieved_at": now()}
        except (HTTPError, URLError, TimeoutError) as exc:
            retryable = not isinstance(exc, HTTPError) or exc.code in (429, 500, 502, 503, 504)
            if not retryable or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After", "") if isinstance(exc, HTTPError) else ""
            time.sleep(min(int(retry_after), 20) if retry_after.isdigit() else 2 ** attempt)


def query(path, **params):
    return HANSARD + path + "?" + urlencode(params)


def walk(debate):
    yield debate
    for child in debate.get("ChildDebates", []):
        yield from walk(child)


def capture_day(root, day, house, retrieve=fetch):
    entry = {"date": day, "house": house, "sources": [], "roots": [], "errors": []}

    def get(name, url):
        obj, source = retrieve(root, f"{day}/{house}/{name}.json", url)
        entry["sources"].append(source)
        return obj, source

    try:
        sections, _ = get("sections", query("/overview/sectionsforday.json", date=day, house=house))
        if not isinstance(sections, list) or any(not re.fullmatch(r"[A-Za-z0-9]+", s) for s in sections):
            raise ValueError("Unexpected section index")
    except (OSError, ValueError) as exc:
        entry["errors"].append(f"Section index: {exc}")
        return entry

    for section in sections:
        try:
            trees, _ = get(section + "-tree", query(
                "/overview/sectiontrees.json", date=day, house=house, section=section
            ))
            if not trees:
                raise ValueError("Advertised section has no tree")
            for tree in trees:
                items = tree["SectionTreeItems"]
                expected = {str(item["ExternalId"]).upper() for item in items if item["ExternalId"]}
                seen = set()
                for item in items:
                    if item["ParentId"] is not None:
                        continue
                    ext_id = item["ExternalId"]
                    if not ext_id or not re.fullmatch(r"[A-Za-z0-9-]+", ext_id):
                        raise ValueError("Root has no valid external identifier")
                    url = f"{HANSARD}/debates/debate/{ext_id}.json"
                    debate, source = get(f"{section}-{ext_id}", url)
                    overview = debate["Overview"]
                    if overview["House"] != house or overview["Date"][:10] != day:
                        raise ValueError(f"Unexpected sitting at {url}")
                    seen.update(str(part["Overview"]["ExtId"]).upper() for part in walk(debate))
                    entry["roots"].append({"section": section, "latest": tree.get("LastUpdated"),
                                           "volume": tree.get("VolumeNo"), **source})
                missing = expected - seen
                if missing:
                    entry["errors"].append(f"{section}: {len(missing)} advertised sections missing from roots")
        except (KeyError, TypeError, OSError, ValueError) as exc:
            entry["errors"].append(f"{section}: {exc}")
    return entry


def capture_directory_page(root, name, offset, url, **params):
    return fetch(root, f"directories/{name}-{offset}.json", url + "?" + urlencode(params))


def directory(root, name, url, page_size, maximum, **params):
    first, record = capture_directory_page(root, name, 0, url, skip=0, take=page_size, **params)
    sources = [record]
    actual_size = len(first["items"])
    stop = min(first["totalResults"], maximum)
    if stop and not actual_size:
        raise ValueError(f"{name}: first directory page is empty")
    for offset in range(actual_size or 1, stop, actual_size or 1):
        page, record = capture_directory_page(root, name, offset, url, skip=offset, take=page_size, **params)
        if not page["items"]:
            raise ValueError(f"{name}: empty page at offset {offset}")
        sources.append(record)
    return {"name": name, "advertised": first["totalResults"], "requested": stop,
            "sources": sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--from-date", type=date.fromisoformat, required=True)
    parser.add_argument("--to-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    n = (args.to_date - args.from_date).days + 1
    if not 1 <= n <= 32:
        parser.error("Choose a capture window of 1 to 32 days.")
    args.snapshot.mkdir(parents=True, exist_ok=False)
    jobs = [((args.from_date + timedelta(days=i)).isoformat(), house)
            for i in range(n) for house in HOUSES]
    started = now()
    manifest = {"schema": "hansard-capture.v1", "started_at": started, "sittings": [],
                "directories": [], "directory_errors": []}
    dump(args.snapshot / "manifest.json", manifest)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for entry in pool.map(lambda job: capture_day(args.snapshot, *job), jobs):
            print(entry["date"], entry["house"], len(entry["roots"]), entry["errors"], flush=True)
            manifest["sittings"].append(entry)
            dump(args.snapshot / "manifest.json", manifest)
    for name, url, size, maximum, filters in [
        ("bills", BILLS, 40, 120, {"SortOrder": "DateUpdatedDescending"}),
        ("members-commons", MEMBERS, 20, 650, {"House": 1, "IsCurrentMember": "true"}),
        ("members-lords", MEMBERS, 20, 900, {"House": 2, "IsCurrentMember": "true"}),
    ]:
        try:
            manifest["directories"].append(directory(args.snapshot, name, url, size, maximum, **filters))
        except (KeyError, TypeError, OSError, ValueError) as exc:
            manifest["directory_errors"].append(f"{name}: {exc}")
        dump(args.snapshot / "manifest.json", manifest)
    manifest["finished_at"] = now()
    dump(args.snapshot / "manifest.json", manifest)
    return bool(any(s["errors"] for s in manifest["sittings"]))


if __name__ == "__main__":
    raise SystemExit(main())
