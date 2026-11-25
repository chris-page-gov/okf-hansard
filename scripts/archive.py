"""Extend Hansard history with an incremental, resumable metadata-only cache."""

import argparse
from collections import Counter
from datetime import UTC, date, datetime, timedelta
import gzip
from hashlib import sha256
from http.client import HTTPException
import json
from pathlib import Path
import re
import signal
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from capture import HOUSES, MAX_BYTES, capture_day, dump, now, query, sha
from model import Entity, Matcher, NS, mention_roles, read_sittings

HANDLED_HOST = "hansard-api.parliament.uk"
SQL = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calendar (
  month TEXT NOT NULL, house TEXT NOT NULL, days TEXT NOT NULL, source TEXT NOT NULL,
  PRIMARY KEY (month, house)
);
CREATE TABLE IF NOT EXISTS sitting (
  day TEXT NOT NULL, house TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL,
  passages INTEGER NOT NULL, retained INTEGER NOT NULL, source TEXT NOT NULL,
  PRIMARY KEY (day, house)
);
CREATE TABLE IF NOT EXISTS contribution (
  route TEXT PRIMARY KEY, day TEXT NOT NULL, house TEXT NOT NULL, debate TEXT NOT NULL,
  ordinal INTEGER NOT NULL, record TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS contribution_sitting ON contribution(day, house);
CREATE TABLE IF NOT EXISTS mention (
  entity TEXT NOT NULL, day TEXT NOT NULL, route TEXT NOT NULL REFERENCES contribution(route),
  evidence TEXT NOT NULL, PRIMARY KEY (entity, day, route)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS mention_route ON mention(route);
"""


class StopRun(Exception):
    """Stop between completed transactions."""


def brief(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def unpack(raw, encoding):
    if encoding.lower() != "gzip":
        return raw
    import io
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        return stream.read(MAX_BYTES + 1)


class Collector:
    def __init__(self, deadline, pause_path, minimum_interval):
        self.deadline = deadline
        self.pause_path = pause_path
        self.minimum_interval = minimum_interval
        self.next_request = 0.0
        self.asked_to_stop = False
        self.telemetry = Counter()

    def check(self):
        if self.asked_to_stop or datetime.now(UTC) >= self.deadline or self.pause_path.exists():
            raise StopRun

    def stop(self, *_args):
        self.asked_to_stop = True

    def wait(self, delay):
        until = time.monotonic() + delay
        while not self.asked_to_stop and time.monotonic() < until:
            self.check()
            time.sleep(min(0.5, max(0, until - time.monotonic())))
        self.check()

    def get(self, _root, relative, url):
        host = urlparse(url)
        if host.scheme != "https" or host.hostname != HANDLED_HOST:
            raise ValueError(f"Unapproved Hansard source: {url}")
        request = Request(url, headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                                        "User-Agent": "OKF-Hansard-Pilot/0.1"})
        for attempt in range(3):
            self.wait(max(0, self.next_request - time.monotonic()))
            self.next_request = time.monotonic() + self.minimum_interval
            self.telemetry["requests"] += 1
            try:
                # Some historical Written Answers roots take over a minute
                # to assemble. Their 35s timeout produced retryable gaps even
                # when the official API returned a complete response.
                written_root = Path(relative).name.startswith("Writtens-") and "/debates/debate/" in url
                remaining = max(0.05, (self.deadline - datetime.now(UTC)).total_seconds())
                with urlopen(request, timeout=min(120 if written_root else 10, remaining)) as response:
                    target = urlparse(response.url)
                    if target.scheme != "https" or target.hostname != HANDLED_HOST:
                        raise ValueError(f"Unexpected redirect for {url}")
                    wire = response.read(MAX_BYTES + 1)
                    self.telemetry["wire_bytes"] += len(wire)
                    raw = unpack(wire, response.headers.get("Content-Encoding", ""))
                    if len(raw) > MAX_BYTES or len(wire) > MAX_BYTES:
                        raise ValueError(f"Response exceeds capture limit: {url}")
                    obj = json.loads(raw)
                    meta = {
                        "path": relative, "url": url, "sha256": sha(raw), "retrieved_at": now(),
                        "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified"),
                    }
                    return obj, meta
            except (HTTPError, URLError, HTTPException, TimeoutError) as exc:
                self.telemetry["http_errors"] += 1
                retryable = not isinstance(exc, HTTPError) or exc.code in (408, 429, 500, 502, 503, 504)
                if attempt == 2 and isinstance(exc, HTTPException):
                    raise OSError(f"{url}: {exc}") from exc
                if not retryable or attempt == 2:
                    raise
                header = exc.headers.get("Retry-After", "") if isinstance(exc, HTTPError) else ""
                delay = min(int(header), 300) if header.isdigit() else 2 ** (attempt + 1)
                self.wait(delay)


def open_database(path, vocabulary_bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SQL)
    identity = sha256(vocabulary_bytes).hexdigest()
    with db:
        row = db.execute("SELECT value FROM metadata WHERE key='profile_sha256'").fetchone()
        if row and row[0] != identity:
            raise ValueError("The cache belongs to a different matching profile.")
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('profile_sha256', ?)", (identity,))
        db.execute("INSERT OR IGNORE INTO metadata VALUES ('schema', 'hansard-history-db.v1')")
    return db


def read_calendar(db, collector, month, house):
    key = month.isoformat()[:7]
    cached = db.execute("SELECT days FROM calendar WHERE month=? AND house=?", (key, house)).fetchone()
    if cached:
        collector.telemetry["calendars_reused"] += 1
        return json.loads(cached[0])
    response, receipt = collector.get(None, f"calendar/{key}/{house}.json", query(
        "/overview/calendar.json", year=month.year, month=f"{month.month:02d}", house=house
    ))
    if any(row["ItemDate"][:7] != key or row["House"] != house for row in response):
        raise ValueError(f"Unexpected calendar results for {key} {house}")
    days = sorted({row["ItemDate"][:10] for row in response}, reverse=True)
    with db:
        db.execute("INSERT INTO calendar VALUES (?,?,?,?)", (key, house, brief(days), brief(receipt)))
    return days


def contribution_link(record):
    external = str(record.get("external_id") or "")
    url = urlparse(record["url"])
    debate = re.match(r"^/(?:Commons|Lords)/\d{4}-\d\d-\d\d/debates/([A-Za-z0-9-]+)(?:/|$)", url.path, re.I)
    if (re.fullmatch(r"[A-Za-z0-9-]+", external) and url.scheme == "https"
            and url.netloc == "hansard.parliament.uk" and debate and url.fragment == f"contribution-{external}"):
        return (debate[1].casefold(), url.fragment.casefold())
    return None


def collect_sitting(db, collector, matcher, day, house, links_only=False):
    previous = db.execute("SELECT status, attempts, passages, retained FROM sitting WHERE day=? AND house=?",
                          (day, house)).fetchone()
    if previous and previous[0] in ("processed", "no published sections"):
        collector.telemetry["sittings_reused"] += 1
        return
    attempts = previous[1] + 1 if previous else 1
    roots = {}

    def transient(_root, relative, url):
        value, receipt = collector.get(None, relative, url)
        if "/debates/debate/" in url:
            roots[relative] = value
        return value, receipt

    entry = capture_day(None, day, house, retrieve=transient)
    records = {}
    metrics = {}
    if entry["roots"]:
        try:
            _, records, _, observed = read_sittings(
                None, {"sittings": [entry]}, "9999-01-01", "9999-01-01",
                loader=lambda _root, source: roots.pop(source["path"]),
            )
            metrics = observed[(day, house)]
        except (ValueError, KeyError, TypeError) as exc:
            entry["errors"].append(f"Normalisation: {exc}")
    elif links_only and not entry["errors"]:
        entry["errors"].append("The calendar lists a sitting and its section index is empty.")
    link_counts = Counter(contribution_link(row) for row in records.values()) if links_only else {}
    bundles, mentions = [], []
    for route, record in records.items():
        collector.check()
        found = mention_roles(record, matcher)
        if not found:
            continue
        if links_only:
            link = contribution_link(record)
            if not link or link_counts[link] != 1:
                collector.telemetry["matched_passages_without_unique_contribution_link"] += 1
                metrics["matched_passages_without_unique_contribution_link"] = (
                    metrics.get("matched_passages_without_unique_contribution_link", 0) + 1)
                continue
        meta = {k: record[k] for k in (
            "kind", "pointer", "url", "external_id", "source_item_id", "member",
            "attributed_to", "value_sha256", "normalised_sha256", "section",
        )}
        meta["capture"] = record["capture"]
        bundles.append((route, day, house, record["part"], record["order"], brief(meta)))
        for key, spans in found.items():
            predicate = "hasOfficeTitle" if matcher.entity_groups[key] == "Offices" else "mentions"
            material = f"{route}|{predicate}|entity/{key}.md"
            assertion = NS + "assertion:" + sha(material.encode())[:36]
            mentions.append((key, day, route, brief({"assertion": assertion, "spans": spans})))
    status = "source gap" if entry["errors"] else ("processed" if entry["roots"] else "no published sections")
    entry["metrics"] = dict(metrics)
    # A retry that still has source errors is only a partial observation. Keep
    # the last successful postings and receipts intact until a complete capture
    # can replace them atomically. This also keeps network timeouts retryable.
    replace_postings = not entry["errors"]
    source = entry
    if previous:
        old = db.execute("SELECT source FROM sitting WHERE day=? AND house=?", (day, house)).fetchone()
        prior_source = json.loads(old[0]) if old else {}
        attempts_history = list(prior_source.get("retry_attempts", []))
        attempts_history.append(entry)
        source = {**prior_source,
                  "sources": prior_source.get("sources", []) + entry.get("sources", []),
                  "roots": prior_source.get("roots", []) + entry.get("roots", []),
                  "errors": entry["errors"], "retry_attempts": attempts_history,
                  "last_retry_errors": entry["errors"]}
    with db:
        db.execute("INSERT OR REPLACE INTO sitting VALUES (?,?,?,?,?,?,?)",
                   (day, house, status, attempts, len(records) if replace_postings else previous[2],
                    len(bundles) if replace_postings else previous[3], brief(source)))
        if replace_postings:
            # A complete repeat capture atomically replaces that sitting's postings.
            if previous:
                db.execute("""DELETE FROM mention WHERE route IN (
                    SELECT route FROM contribution WHERE day=? AND house=?)""", (day, house))
                db.execute("DELETE FROM contribution WHERE day=? AND house=?", (day, house))
            db.executemany("INSERT INTO contribution VALUES (?,?,?,?,?,?)", bundles)
            db.executemany("INSERT INTO mention VALUES (?,?,?,?)", mentions)
    collector.telemetry["sittings_checked"] += 1
    if entry["errors"]:
        print(f"{day} {house} source gap ({attempts}): {'; '.join(entry['errors'])}", flush=True)


def progress(db, collector, before, start_time, state, month=None):
    statuses = dict(db.execute("SELECT status,count(*) FROM sitting GROUP BY status"))
    earliest, latest, passages, retained = db.execute("""
        SELECT min(day),max(day),sum(passages),sum(retained) FROM sitting
        WHERE status='processed' OR retained>0
    """).fetchone()
    counts = db.execute("SELECT count(*),count(DISTINCT entity) FROM mention").fetchone()
    gaps = [
        {"date": day, "house": house, "attempts": attempts, "errors": json.loads(raw)["errors"]}
        for day, house, attempts, raw in db.execute(
            "SELECT day,house,attempts,source FROM sitting WHERE status='source gap' ORDER BY day DESC, house"
        )
    ]
    return {
        "schema": "hansard-history-progress.v1", "state": state, "last_checkpoint": now(),
        "started_at": start_time, "deadline": collector.deadline.isoformat(), "exclusive_before": before,
        "current_month": month, "earliest_processed": earliest, "latest_processed": latest,
        "sittings_by_status": statuses, "source_passages": passages or 0,
        "matched_contributions": retained or 0, "mentions": counts[0], "entity_keys_with_matches": counts[1],
        "observed_gaps": gaps, "this_run": dict(collector.telemetry),
        "profile_sha256": db.execute("SELECT value FROM metadata WHERE key='profile_sha256'").fetchone()[0],
    }


def previous_month(month):
    return (month - timedelta(days=1)).replace(day=1)


def run(db, collector, matcher, before, floor, report, *, links_only=False, checkpoint_seconds=30):
    started = now()
    month = (date.fromisoformat(before) - timedelta(days=1)).replace(day=1)
    current_month = month
    state = "finished"
    calendar_gaps = []

    def checkpoint(state):
        p = progress(db, collector, before, started, state, current_month.isoformat()[:7])
        p["calendar_gaps"] = calendar_gaps
        dump(report, p)
        return p

    last_checkpoint = 0.0
    try:
        while month >= floor.replace(day=1):
            collector.check()
            current_month = month
            checks_at_start = collector.telemetry["sittings_checked"]
            scheduled = []
            for house in HOUSES:
                try:
                    scheduled += [(day, house) for day in read_calendar(db, collector, month, house)]
                except (OSError, KeyError, ValueError) as exc:
                    calendar_gaps.append({"month": month.isoformat()[:7], "house": house, "error": str(exc)})
            for day, house in sorted(scheduled, reverse=True):
                if floor.isoformat() <= day < before:
                    collect_sitting(db, collector, matcher, day, house, links_only)
                    if time.monotonic() - last_checkpoint >= checkpoint_seconds:
                        last_checkpoint = time.monotonic()
                        checkpoint("running")
            gaps = list(db.execute("SELECT day,house FROM sitting WHERE status='source gap' AND attempts=1 AND day LIKE ?",
                                   (month.isoformat()[:7] + "%",)))
            for day, house in gaps:
                collector.check()
                if floor.isoformat() <= day < before:
                    collect_sitting(db, collector, matcher, day, house, links_only)
            if collector.telemetry["sittings_checked"] > checks_at_start:
                p = checkpoint("running")
                print(f"{p['current_month']} • {p['matched_contributions']} matched contributions • "
                      f"{p['mentions']} mention links • {len(p['observed_gaps'])} unresolved sitting gaps", flush=True)
            month = previous_month(month)
    except StopRun:
        state = "paused" if collector.pause_path.exists() or collector.asked_to_stop else "deadline reached"
    except Exception:
        checkpoint("failed")
        raise
    finally:
        db.execute("PRAGMA wal_checkpoint(PASSIVE)")
    return checkpoint(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--before", type=date.fromisoformat, required=True)
    parser.add_argument("--floor", type=date.fromisoformat, default=date(1803, 11, 22))
    parser.add_argument("--deadline", type=datetime.fromisoformat, required=True)
    parser.add_argument("--pause-file", type=Path, default=Path(".work/pause-history"))
    parser.add_argument("--interval", type=float, default=0.66)
    args = parser.parse_args()
    if args.deadline.tzinfo is None or args.interval < 0.25:
        parser.error("Use an explicit deadline offset and a request interval of at least 0.25 seconds.")
    raw = args.profile.read_bytes()
    profile = json.loads(raw)
    entities = {key: Entity(key=key, **row) for key, row in profile["entities"].items()}
    matcher = Matcher(entities, profile["ambiguities"])
    matcher.entity_groups = {key: entity.group for key, entity in entities.items()}
    collector = Collector(args.deadline, args.pause_file, args.interval)
    signal.signal(signal.SIGTERM, collector.stop)
    signal.signal(signal.SIGINT, collector.stop)
    with open_database(args.database, raw) as db:
        run(db, collector, matcher, args.before.isoformat(), args.floor, args.report)


if __name__ == "__main__":
    main()
