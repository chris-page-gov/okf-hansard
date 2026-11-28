"""Search Hansard for dated gaps in the archive, retaining evidence only."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, nullcontext
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from http.client import HTTPException
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request

from archive import unpack
from capture import HOUSES, MAX_BYTES, dump, now, query, sha
from http_policy import open_source
from model import Entity, Matcher, NS, debate_url, plain
from query import DEFAULT_DB, Index, canonical_digest

FLOOR = date(2007, 1, 1)
METHOD = "Official Hansard spoken and written search, verified against the literal matching profile"
SCHEMA = "hansard-backfill.v1"
PAGE_SIZE = 100


def previous(day):
    return day - timedelta(days=1)


def archive_ranges(db):
    if db is None:
        return {}
    return {house: (first, last, count) for house, first, last, count in db.execute(
        "SELECT house,min(day),max(day),count(*) FROM sitting WHERE status='processed' GROUP BY house"
    )}


def search_periods(first_capture, archive):
    end = previous(date.fromisoformat(first_capture))
    if not archive or set(archive) != set(HOUSES):
        return [(FLOOR, end)] if end >= FLOOR else []
    first = max(date.fromisoformat(row[0]) for row in archive.values())
    last = min(date.fromisoformat(row[1]) for row in archive.values())
    ranges = [(FLOOR, min(previous(first), end)), (max(FLOOR, last + timedelta(days=1)), end)]
    return [(start, stop) for start, stop in ranges if start <= stop]


def search_aliases(matcher):
    found = defaultdict(list)
    for variants in matcher.lookups.values():
        for words, key in variants.items():
            found[key].append(words)
    result = {}
    for key, aliases in found.items():
        shortest = []
        for words in sorted(aliases, key=lambda words: (len(words), words)):
            if not any(any(words[i:i + len(other)] == other for i in range(len(words) - len(other) + 1))
                       for other in shortest):
                shortest.append(words)
        result[key] = [" ".join(words) for words in shortest]
    return result


class Search:
    def __init__(self, cache, deadline=None):
        self.cache = cache
        self.deadline = deadline
        self.lock = threading.Lock()
        self.next_request = 0.0

    def check_deadline(self):
        if self.deadline and datetime.now(timezone.utc) >= self.deadline:
            raise TimeoutError("History search reached the refresh deadline.")

    def request(self, url):
        request = Request(url, headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                                        "User-Agent": "OKF-Hansard-Pilot/0.1"})
        for attempt in range(3):
            self.check_deadline()
            with self.lock:
                time.sleep(max(0, self.next_request - time.monotonic()))
                self.next_request = time.monotonic() + .25
            self.check_deadline()
            try:
                with open_source(request, timeout=15) as response:
                    wire = response.read(MAX_BYTES + 1)
                    raw = unpack(wire, response.headers.get("Content-Encoding", ""))
                if max(len(wire), len(raw)) > MAX_BYTES:
                    raise ValueError("Hansard search response exceeds the capture limit.")
                return json.loads(raw), {"url": url, "sha256": sha(raw), "retrieved_at": now()}
            except (HTTPError, URLError, HTTPException, TimeoutError) as exc:
                if attempt == 2 or isinstance(exc, HTTPError) and exc.code not in {429, 500, 502, 503, 504}:
                    raise
                hint = exc.headers.get("Retry-After", "") if isinstance(exc, HTTPError) else ""
                delay = min(int(hint), 60) if hint.isdigit() else 2 ** attempt
                with self.lock:
                    self.next_request = max(self.next_request, time.monotonic() + delay) if hint else self.next_request
                time.sleep(delay)

    def window(self, key, term, first, last, section, matcher, profile):
        identity = canonical_digest([SCHEMA, key, term, first.isoformat(), last.isoformat(), section, profile])
        path = self.cache / identity[:2] / f"{identity}.json"
        if path.is_file():
            return json.loads(path.read_bytes())

        def divide():
            middle = first + (last - first) // 2
            left = self.window(key, term, first, middle, section, matcher, profile)
            right = self.window(key, term, middle + timedelta(days=1), last, section, matcher, profile)
            result = {"items": left["items"] + right["items"], "sources": left["sources"] + right["sources"]}
            dump(path, result)
            return result

        items, sources, seen = [], [], set()
        total, offset = None, 0
        while total is None or offset < total:
            url = query(f"/search/contributions/{section}.json", searchTerm=f'"{term}"',
                        startDate=first.isoformat(), endDate=last.isoformat(),
                        skip=offset, take=PAGE_SIZE, outputType="List")
            try:
                data, evidence = self.request(url)
            except (TimeoutError, URLError) as exc:
                self.check_deadline()
                if not isinstance(exc, HTTPError) and (last - first).days >= 30:
                    return divide()
                raise
            count = data["TotalResultCount"]
            if total is None and count > 5_000 and first < last:
                return divide()
            rows = data["Results"]
            if (total is not None and total != count) or offset + len(rows) > count or (not rows and offset < count):
                if first < last:
                    return divide()
                raise ValueError("Hansard search pagination returned inconsistent totals.")
            total = count
            sources.append({**evidence, "results": len(rows), "total": total})
            for row_index, row in enumerate(rows):
                item_id = row["ItemId"]
                if item_id in seen:
                    if first < last:
                        return divide()
                    raise ValueError("A Hansard search item was repeated across pages.")
                seen.add(item_id)
                day, house = row["SittingDate"][:10], row["House"]
                if not first.isoformat() <= day <= last.isoformat() or house not in HOUSES:
                    raise ValueError("Hansard search returned an item outside the requested scope.")
                raw = row.get("ContributionTextFull")
                text = plain(raw)
                spans = [span for entity, span in matcher.find(text) if entity == key]
                if not spans:
                    continue
                debate, external = row["DebateSectionExtId"], row["ContributionExtId"]
                if not debate or not (external or item_id):
                    continue
                base = f"{house.lower()}-{day}-{section.lower()}-{debate.lower()}"
                part = f"debate/{base}.md"
                route = f"contribution/{base}-{str(external or item_id).lower()}-{item_id}.md"
                source_url = debate_url(house, day, debate, row["DebateSection"])
                if external:
                    source_url += f"#contribution-{external}"
                items.append({
                    "date": day, "house": house, "contribution": route, "part": part, "url": source_url,
                    "section_title": row["DebateSection"], "attributed_to": row.get("MemberName"),
                    "order": row["OrderInDebateSection"], "source_item_id": item_id, "external_id": external,
                    "source_value_sha256": sha(raw.encode()), "normalised_value_sha256": sha(text.encode()),
                    "capture": evidence, "pointer": f"/Results/{row_index}",
                    "source_field": f"/Results/{row_index}/ContributionTextFull", "spans": spans,
                    "assertion": NS + "backfill:" + sha256(f"{route}|{key}".encode()).hexdigest()[:36],
                })
            offset += len(rows)
        result = {"items": items, "sources": sources}
        dump(path, result)
        return result


def collect(release, database, cache, days, deadline=None):
    index = Index(release, database)
    anchors = [r for r in index.history["contributions"].values() if r["date"] in days]
    latest = {}
    for row in sorted(anchors, key=lambda row: row["date"]):
        latest.update(dict.fromkeys(row["entities"], row["date"]))
    keys = sorted(latest, key=lambda key: (latest[key], key), reverse=True)
    specifications = index.profile["entities"]
    matcher = Matcher({key: Entity(key=key, **spec) for key, spec in specifications.items()})
    aliases = search_aliases(matcher)
    db = index.connect()
    with closing(db) if db is not None else nullcontext() as connection:
        ranges = archive_ranges(connection)
    first = min(row["date"] for row in index.receipt["day_denominators"])
    full, gaps = search_periods(first, {}), search_periods(first, ranges)
    through = previous(date.fromisoformat(first)).isoformat()
    search = Search(cache, deadline)
    output = release / "backfill"
    output.mkdir(exist_ok=True)
    # Use the effective matcher for cache identity, including competing aliases.
    profile = canonical_digest(index.profile)

    def run(key):
        use_archive = set(ranges) == set(HOUSES) and key in index.archive_keys
        saved = index.backfill_for(key)
        if (saved and not saved["errors"] and saved["through"] == through
                and saved["search_terms"] == aliases.get(key, []) and (use_archive or not saved["archive"])):
            return key, len(saved["items"]), 0, saved["archive"]
        periods = gaps if use_archive else full
        items, sources, failures = {}, [], []
        tasks = [(start, stop, term, section) for start, stop in periods for term in aliases.get(key, [])
                 for section in ("Spoken", "Written")]
        for start, stop, term, section in tasks:
            task = {"from": start.isoformat(), "through": stop.isoformat(), "term": term, "section": section}
            try:
                found = search.window(key, term, start, stop, section, matcher, profile)
            except TimeoutError:
                if deadline and datetime.now(timezone.utc) >= deadline:
                    failures.append({**task, "error": "Refresh deadline. The current and remaining searches are pending."})
                    break
                failures.append({**task, "error": "Source timeout."})
            except (OSError, HTTPException, ValueError, KeyError) as exc:
                failures.append({**task, "error": str(exc)})
            else:
                sources.extend(found["sources"])
                for record in found["items"]:
                    items[record["source_item_id"]] = record
        if not aliases.get(key):
            failures.append({"error": "No unambiguous searchable alias in the matching profile."})
        if failures and saved:
            sources.extend(saved["sources"])
            for record in saved["items"]:
                items.setdefault(record["source_item_id"], record)
        result = {
            "schema": SCHEMA, "entity": key, "method": METHOD, "from": FLOOR.isoformat(),
            "through": through, "archive": use_archive,
            "archive_profile_sha256": index.archive_profile_sha256 if use_archive else None,
            "matching_profile_sha256": profile, "search_terms": aliases.get(key, []),
            "search_windows": [[start.isoformat(), stop.isoformat()] for start, stop in periods],
            "errors": failures, "sources": sources,
            "items": sorted(items.values(), key=lambda row: (row["date"], row["order"], row["contribution"]),
                            reverse=True),
        }
        dump(output / f"{key}.json", result)
        return key, len(items), len(failures), use_archive

    with ThreadPoolExecutor(max_workers=6) as workers:
        rows = []
        for row in workers.map(run, keys):
            rows.append(row)
            if len(rows) % 25 == 0:
                print(f"History verified or attempted for {len(rows)} of {len(keys)} entities.", flush=True)
    summary = {"schema": SCHEMA, "dates": sorted(days), "from": FLOOR.isoformat(),
               "through": through, "method": METHOD,
               "archive": ranges, "entities": len(keys),
               "archive_entities": sum(archived for _, _, _, archived in rows),
               "complete": sum(errors == 0 for _, _, errors, _ in rows),
               "search_matches": sum(matches for _, matches, _, _ in rows),
               "exceptions": {key: errors for key, _, errors, _ in rows if errors}}
    dump(output / "manifest.json", summary)
    print(f"History backfill checked {len(keys)} entities, with {len(summary['exceptions'])} incomplete.", flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("--day", required=True, action="append")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--deadline", type=datetime.fromisoformat)
    args = parser.parse_args()
    collect(args.release, args.database, args.cache, set(args.day), args.deadline)
