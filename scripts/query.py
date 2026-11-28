"""Inspect exact, source-linked matches in the frozen week and rolling history."""

import argparse
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

DEFAULT_RELEASE = Path("releases/current")
DEFAULT_DB = Path("/Volumes/ExtSSD-Data/okf-hansard-cache/history-v1.sqlite")
DEEP_DB = DEFAULT_DB.with_name("history-before-2007.sqlite")
DEEP_BEFORE = "2007-01-01"


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def source_identity(row):
    url = urlsplit(row.get("url") or "")
    path = url.path.split("/")
    if (url.hostname == "hansard.parliament.uk" and len(path) >= 5
            and path[3].casefold() == "debates" and url.fragment.casefold().startswith("contribution-")):
        return row["date"], row.get("house"), path[4].casefold(), url.fragment.casefold()
    return row["contribution"],


def day_after(day):
    return (date.fromisoformat(day) + timedelta(days=1)).isoformat()


def sitting_states(db):
    if db is None:
        return {}
    return {(day, house): (status, attempts, retained) for day, house, status, attempts, retained in
            db.execute("SELECT day,house,status,attempts,retained FROM sitting")}


class Index:
    def __init__(self, release, database=None, older_database=None):
        self.release = release
        self.history = json.loads((release / "history.json").read_bytes())
        self.profile = json.loads((release / "analysis-profile.json").read_bytes())
        self.receipt = json.loads((release / "receipt.json").read_bytes())
        self.bundle_sha256 = self.receipt["artifacts"]["history.json"]["sha256"]
        self.base = self.history["mentions"]
        bound = release / "archive-analysis-profile.json"
        if bound.is_file():
            old_bytes = bound.read_bytes()
            archive_profile = json.loads(old_bytes)
            self.archive_profile_sha256 = hashlib.sha256(old_bytes).hexdigest()
            self.archive_keys = {key for key, spec in self.profile["entities"].items()
                                 if archive_profile["entities"].get(key) == spec}
        else:
            self.archive_profile_sha256 = self.receipt["artifacts"]["analysis-profile.json"]["sha256"]
            self.archive_keys = set(self.profile["entities"])
        self.auxiliary = {}
        supplemental = release / "supplemental"
        if supplemental.is_dir():
            for path in sorted(supplemental.glob("*.json")):
                pkg = json.loads(path.read_bytes())
                if pkg["entity"] in self.profile["entities"]:
                    self.auxiliary[pkg["entity"]] = pkg
        self.database = database
        self.older_database = older_database
        self.backfill = release / "backfill"
        self.source_records = None

    def backfill_for(self, key):
        path = self.backfill / f"{key}.json"
        if path.is_file():
            package = json.loads(path.read_bytes())
            if package["entity"] != key or package["schema"] != "hansard-backfill.v1":
                raise ValueError("The history search package has an unexpected identity.")
            return package
        return None

    def connect(self):
        return self.connect_archive(self.database, self.archive_profile_sha256)

    def connect_older(self):
        if not self.older_database or not self.older_database.is_file():
            return None, set(), None
        raw = self.older_database.with_suffix(".profile.json").read_bytes()
        profile = json.loads(raw)["entities"]
        digest = hashlib.sha256(raw).hexdigest()
        db = self.connect_archive(self.older_database, digest)
        if db is None:
            return None, set(), None
        bounds = dict(db.execute("SELECT key,value FROM metadata WHERE key IN ('exclusive_before','contribution_link_policy')"))
        if bounds != {"exclusive_before": DEEP_BEFORE, "contribution_link_policy": "unique-fragment-v1"}:
            db.close()
            raise ValueError("The pre-2007 archive is missing its expected link policy or date boundary.")
        keys = {key for key, spec in self.profile["entities"].items() if profile.get(key) == spec}
        return db, keys, digest

    @staticmethod
    def connect_archive(database, profile_sha256):
        if not database or not database.is_file():
            return None
        path = database.resolve()
        uri = path.as_uri()
        query = "SELECT value FROM metadata WHERE key='profile_sha256'"
        db = None
        try:
            db = sqlite3.connect(uri + "?mode=ro", uri=True, timeout=5)
            profile = db.execute(query).fetchone()
        except sqlite3.OperationalError:
            if db:
                db.close()
            # SQLite cannot create WAL sidecars on a read-only volume.
            # Use a checkpointed file only when it has no active sidecars.
            if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
                raise
            db = sqlite3.connect(uri + "?mode=ro&immutable=1", uri=True, timeout=5)
            profile = db.execute(query).fetchone()
        if not profile or profile[0] != profile_sha256:
            db.close()
            raise ValueError("The history extension does not match the pilot profile.")
        return db

    @staticmethod
    def archive_rows(db, key, before, limit, offset, since="0001-01-01"):
        rows = db.execute("""
            SELECT m.route, m.day, c.house, c.debate, c.ordinal, c.record, m.evidence
            FROM mention AS m JOIN contribution AS c ON c.route=m.route
            WHERE m.entity=? AND m.day>=? AND m.day<?
            ORDER BY m.day DESC, m.route DESC LIMIT ? OFFSET ?
        """, (key, since, before, limit, offset))
        return [{"contribution": route, "date": day, "house": house, "part": debate, "order": ordinal,
                 **json.loads(document), **json.loads(proof)}
                for route, day, house, debate, ordinal, document, proof in rows]

    def history_page(self, key, captured, archives, limit, offset):
        by_day = defaultdict(list)
        for row in captured:
            by_day[row["date"]].append(row)
        archived_days = {}
        for db, since, before, states in archives:
            for day, count in db.execute("""
                SELECT day,count(*) FROM mention WHERE entity=? AND day>=? AND day<? GROUP BY day
            """, (key, since, before)):
                archived_days[day] = db, count, states

        page = []
        for day in sorted(by_day.keys() | archived_days.keys(), reverse=True):
            retained = by_day[day]
            db, count, states = archived_days.get(day, (None, 0, {}))
            if offset >= len(retained) + count:
                offset -= len(retained) + count
                continue
            page.extend(retained[offset:offset + limit - len(page)])
            if db and len(page) < limit:
                for row in self.archive_rows(db, key, day_after(day), limit - len(page),
                                             max(0, offset - len(retained)), day):
                    state = states.get((day, row["house"]), ("not recorded", 0, 0))[0]
                    page.append({**row, "archive_sitting_status": state})
            if len(page) >= limit:
                break
            offset = 0
        return page

    def search_fallback(self, key, search, captured, archives, prior):
        """Retain fallback evidence where the applicable archive lacks a complete sitting."""
        seen = {source_identity(row) for row in captured}
        matched_days = {}
        retained = []
        for row in search:
            if not prior(row):
                continue
            identity = source_identity(row)
            if identity in seen:
                continue
            day = row["date"]
            status = "not indexed"
            duplicate = False
            for db, since, before, states in archives:
                if since <= day < before:
                    status, _, existing = states.get((day, row["house"]), ("not indexed", 0, 0))
                    if status != "processed" and existing:
                        if day not in matched_days:
                            matches = self.archive_rows(db, key, day_after(day), -1, 0, day)
                            matched_days[day] = {source_identity(match) for match in matches}
                        duplicate = identity in matched_days[day]
                    break
            if status == "processed" or duplicate:
                continue
            seen.add(identity)
            retained.append({**row, "history_source": "Hansard search", "archive_sitting_status": status})
        return retained

    def find(self, term="", day=None, house=None, limit=20, offset=0):
        if self.source_records is None:
            bundle = json.loads((self.release / "okf-bundle.json").read_bytes())
            nodes = bundle["corpora"]["hansard"]["nodes"]
            self.source_records = [
                (route, nodes[route]) for route in self.history["contributions"]
            ]
        if day:
            day = date.fromisoformat(day).isoformat()
        terms = term.casefold().split()
        found = []
        for route, record in self.source_records:
            facets = record["learning_facets"]
            if day and day != record["date"] or house and house not in facets["chamber"]:
                continue
            haystack = " ".join([record["title"], *[v for values in facets.values() for v in values]])
            if not all(token in haystack.casefold() for token in terms):
                continue
            found.append({"id": route, "date": record["date"], "title": record["title"],
                          "url": record["url"], "facets": facets})
        found.sort(key=lambda r: (r["date"], r["title"], r["id"]), reverse=True)
        return {"schema": "hansard-record-search.v1", "total": len(found), "offset": offset,
                "items": found[offset:offset + limit]}

    def track(self, route, entity=None, limit=30, offset=0, expected_context=None):
        if route not in self.history["contributions"]:
            raise ValueError("Contribution ID is outside the pilot week.")
        anchor = self.history["contributions"][route]
        keys = anchor["entities"]
        if entity is not None and entity not in keys:
            raise ValueError("That entity is not an extracted textual match for this contribution.")
        db = self.connect()
        deep = None
        try:
            if db:
                db.execute("BEGIN")
            deep, deep_keys, deep_sha = self.connect_older()
            if deep:
                deep.execute("BEGIN")
            return self._within_snapshot(db, deep, deep_keys, deep_sha, anchor, route, keys, entity, limit, offset,
                                         expected_context)
        finally:
            if db:
                db.close()
            if deep:
                deep.close()

    def _within_snapshot(self, db, deep, deep_keys, deep_sha, anchor, route, keys, entity, limit, offset,
                         expected_context):
        summaries = []
        actual_items = []
        extension_earliest = None
        extension_latest = None
        gaps = 0
        extension_count = 0
        if db:
            extension_earliest, extension_latest, extension_count = db.execute("""
                SELECT min(day),max(day),count(*) FROM sitting WHERE status='processed'
            """).fetchone()
            gaps = db.execute("SELECT count(*) FROM sitting WHERE status='source gap'").fetchone()[0]
        deep_before = min(DEEP_BEFORE, anchor["date"])
        deep_status = {}
        if deep:
            deep_status = {
                status: {"from": start, "through": stop, "sittings": total}
                for status, start, stop, total in deep.execute("""
                    SELECT status,min(day),max(day),count(*) FROM sitting WHERE day<? GROUP BY status
                """, (deep_before,))
            }
        current_states, older_states = sitting_states(db), sitting_states(deep)
        evidence_versions = {}

        def prior(row):
            return row["date"] < anchor["date"] or (
                row["part"] == anchor["part"] and row["order"] < anchor["order"]
            )

        for key in keys:
            entries = self.base.get(key, [])
            prior_base = [row for row in reversed(entries) if prior(row)]
            same_day = sum(row["date"] == anchor["date"] and row["part"] != anchor["part"] for row in entries)
            use_archive = db and key in self.archive_keys
            use_deep = deep and key in deep_keys
            backfill = self.backfill_for(key)
            supplemental = None if backfill else self.auxiliary.get(key)
            archives = []
            archive_since = deep_before if use_deep else "0001-01-01"
            if use_archive:
                archives.append((db, archive_since, anchor["date"], current_states))
            if use_deep:
                archives.append((deep, "0001-01-01", deep_before, older_states))
            package = backfill or supplemental
            fallback = self.search_fallback(key, package["items"], prior_base, archives, prior) if package else []
            if fallback:
                evidence_versions[key] = canonical_digest(fallback)
            count = db.execute("SELECT count(*) FROM mention WHERE entity=? AND day>=? AND day<?",
                               (key, archive_since, anchor["date"])).fetchone()[0] if use_archive else 0
            deep_count = deep.execute("SELECT count(*) FROM mention WHERE entity=? AND day<?",
                                      (key, deep_before)).fetchone()[0] if use_deep else 0
            summaries.append({"id": key, **self.history["entities"][key],
                              "earlier": len(prior_base) + len(fallback) + count + deep_count,
                              "same_day_order_unknown": same_day,
                              "extension_applied": bool(use_archive),
                              **({"older_archive_applied": bool(use_deep), "older_archive_matches": deep_count}
                                 if self.older_database else {}),
                              **({"backfill_coverage": {"from": backfill["from"], "through": backfill["through"],
                                                        "method": backfill["method"], "errors": backfill["errors"],
                                                        "archive_unavailable": backfill["archive"] and not use_archive}}
                                 if backfill else {}),
                              "supplemental_coverage": (
                                  {"from": supplemental["from"], "through": supplemental["through"],
                                   "method": supplemental["method"], "retrieved_at": supplemental["retrieved_at"]}
                                  if supplemental and fallback else None
                              )})
            if key == entity:
                actual_items = self.history_page(key, prior_base + fallback, archives, limit, offset)
        scope = {"base_from": min(row["date"] for row in self.receipt["day_denominators"]),
                 "base_through": anchor["date"], "extension_from": extension_earliest,
                 "extension_through": extension_latest, "extension_processed_sittings": extension_count,
                 "extension_source_gaps": gaps, "archive_profile_sha256": self.archive_profile_sha256,
                 "ordering": "earlier sitting dates or earlier source order in the same section",
                 "method": "literal match against a fixed governed alias profile"}
        if self.older_database:
            scope["older_archive"] = {"available": bool(deep), "exclusive_before": deep_before,
                                      "sittings": deep_status, "profile_sha256": deep_sha}
        context = canonical_digest({"bundle": self.bundle_sha256, "scope": scope,
                                    "contribution": route, "entities": summaries, "search_evidence": evidence_versions,
                                    "sitting_editions": [sorted(states.items()) for states in (current_states, older_states)]})
        if expected_context and expected_context != context:
            raise ValueError("History was updated. Start again at offset zero for a consistent evidence page.")
        selected = next((row for row in summaries if row["id"] == entity), None)
        total = selected["earlier"] if selected else None
        next_offset = offset + len(actual_items) if total is not None and offset + len(actual_items) < total else None
        return {"schema": "hansard-related-evidence.v1", "context_id": context,
                "bundle_sha256": self.bundle_sha256, "coverage": scope,
                "anchor": {"id": route, **anchor}, "entities": summaries, "selected_entity": selected,
                "items": actual_items, "offset": offset, "next_offset": next_offset, "total": total}


def view_for(package):
    """A host-neutral view declaration bound to the answer and its data."""
    rows = [{"entity": item["label"], "facet": item["group"], "count": item["earlier"],
             "entity_id": item["id"], "route": item["route"], "drill_down": {
                 "tool": "hansard_trace", "arguments": {
                     "contribution": package["anchor"]["id"], "entity": item["id"],
                     "expected_context": package["context_id"],
                 }
             }} for item in package["entities"]]
    rows.sort(key=lambda row: (-row["count"], row["facet"], row["entity"]))
    view = {
        "schema": "okf-view.v1", "status": "experimental", "kind": "ranked-bar-and-table",
        "title": "Earlier mention records by related entity",
        "description": "Counts are contribution records per entity. A passage may appear under several entities.",
        "encoding": {"label": "entity", "measure": "count", "facet": "facet", "unit": "contribution records"},
        "aggregation": "distinct contribution records, per entity",
        "coverage": package["coverage"], "context_id": package["context_id"],
        "bundle_sha256": package["bundle_sha256"], "dataset_sha256": canonical_digest(rows),
        "accessible_alternative": "table", "rows": rows,
    }
    return {**view, "view_id": canonical_digest(view)}


def pagination(parser):
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--older-database", type=Path, help="Read a verified, separate pre-2007 archive.")
    command = parser.add_subparsers(required=True, dest="command")
    search = command.add_parser("find")
    search.add_argument("term", nargs="?", default="")
    search.add_argument("--date")
    search.add_argument("--house", choices=("Commons", "Lords"))
    pagination(search)
    trace = command.add_parser("trace")
    trace.add_argument("route")
    trace.add_argument("--entity")
    trace.add_argument("--context")
    trace.add_argument("--view", action="store_true")
    pagination(trace)
    args = parser.parse_args()
    if args.offset < 0 or not 1 <= args.limit <= 500:
        parser.error("Use a non-negative offset and a page size of 1 to 500.")
    index = Index(args.release, args.database, args.older_database)
    if args.command == "find":
        answer = index.find(args.term, args.date, args.house, args.limit, args.offset)
    else:
        answer = index.track(args.route, args.entity, args.limit, args.offset, args.context)
        if args.view:
            answer["view"] = view_for(answer)
    print(json.dumps(answer, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
