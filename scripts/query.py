"""Inspect exact, source-linked matches in the frozen week and rolling history."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3

DEFAULT_RELEASE = Path("releases/current")
DEFAULT_DB = Path("/Volumes/ExtSSD-Data/okf-hansard-cache/history-v1.sqlite")


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class Index:
    def __init__(self, release, database=None):
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
        self.source_records = None

    def connect(self):
        if not self.database or not self.database.is_file():
            return None
        path = self.database.resolve()
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
        if not profile or profile[0] != self.archive_profile_sha256:
            db.close()
            raise ValueError("The history extension does not match the pilot profile.")
        return db

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
        try:
            if db:
                db.execute("BEGIN")
            return self._within_snapshot(db, anchor, route, keys, entity, limit, offset, expected_context)
        finally:
            if db:
                db.close()

    def _within_snapshot(self, db, anchor, route, keys, entity, limit, offset, expected_context):
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

        def prior(row):
            return row["date"] < anchor["date"] or (
                row["part"] == anchor["part"] and row["order"] < anchor["order"]
            )

        for key in keys:
            entries = self.base.get(key, [])
            prior_base = [row for row in reversed(entries) if prior(row)]
            same_day = sum(row["date"] == anchor["date"] and row["part"] != anchor["part"] for row in entries)
            supplemental = self.auxiliary.get(key)
            use_archive = db and key in self.archive_keys
            if supplemental and not use_archive:
                prior_base.extend(row for row in supplemental["items"] if prior(row))
            count = 0
            if use_archive:
                count = db.execute("SELECT count(*) FROM mention WHERE entity=? AND day<?",
                                   (key, anchor["date"])).fetchone()[0]
            summaries.append({"id": key, **self.history["entities"][key],
                              "earlier": len(prior_base) + count, "same_day_order_unknown": same_day,
                              "extension_applied": bool(use_archive),
                              "supplemental_coverage": (
                                  {"from": supplemental["from"], "through": supplemental["through"],
                                   "method": supplemental["method"], "retrieved_at": supplemental["retrieved_at"]}
                                  if supplemental and not use_archive else None
                              )})
            if key != entity:
                continue
            remaining = limit
            if offset < len(prior_base):
                actual_items.extend(prior_base[offset:offset + remaining])
                remaining = limit - len(actual_items)
            if db and remaining and key in self.archive_keys:
                rows = db.execute("""
                    SELECT m.route, m.day, c.house, c.debate, c.ordinal, c.record, m.evidence
                    FROM mention AS m JOIN contribution AS c ON c.route=m.route
                    WHERE m.entity=? AND m.day<?
                    ORDER BY m.day DESC, m.route DESC LIMIT ? OFFSET ?
                """, (key, anchor["date"], remaining, max(0, offset - len(prior_base))))
                for contribution, day, house, debate, ordinal, document, proof in rows:
                    actual_items.append({"contribution": contribution, "date": day, "house": house,
                                         "part": debate, "order": ordinal, **json.loads(document),
                                         **json.loads(proof)})
        scope = {"base_from": min(row["date"] for row in self.receipt["day_denominators"]),
                 "base_through": anchor["date"], "extension_from": extension_earliest,
                 "extension_through": extension_latest, "extension_processed_sittings": extension_count,
                 "extension_source_gaps": gaps, "archive_profile_sha256": self.archive_profile_sha256,
                 "ordering": "earlier sitting dates or earlier source order in the same section",
                 "method": "literal match against a fixed governed alias profile"}
        context = canonical_digest({"bundle": self.bundle_sha256, "scope": scope,
                                    "contribution": route, "entities": summaries})
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
    index = Index(args.release, args.database)
    if args.command == "find":
        answer = index.find(args.term, args.date, args.house, args.limit, args.offset)
    else:
        answer = index.track(args.route, args.entity, args.limit, args.offset, args.context)
        if args.view:
            answer["view"] = view_for(answer)
    print(json.dumps(answer, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
