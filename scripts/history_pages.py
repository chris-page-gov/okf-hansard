"""Project verified history to reusable, per-entity Pages assets."""

from collections import defaultdict
import gzip
import json
from pathlib import Path
import shutil
from urllib.parse import urlparse

from backfill import FLOOR, archive_ranges
from capture import dump
from query import DEEP_BEFORE, Index, canonical_digest

ROOT = Path(__file__).resolve().parents[1]


def source_row(day, house, url, attribution):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "hansard.parliament.uk":
        raise ValueError("History contains an unexpected Hansard evidence link.")
    return [day, house, url, attribution or ""]


def archive_asset(db, identity, key, target, cache, since=FLOOR.isoformat()):
    path = cache / identity / f"{key}.json.gz"
    receipt = path.with_suffix(".count")
    if not path.is_file() or not receipt.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        working = path.with_suffix(".tmp")
        count = 0
        with working.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, compresslevel=4) as stream:
            stream.write(b"[")
            for day, house, record in db.execute("""
                SELECT m.day,c.house,c.record FROM mention m JOIN contribution c ON c.route=m.route
                WHERE m.entity=? AND m.day>=?
                ORDER BY m.day DESC,m.route DESC
            """, (key, since)):
                row = json.loads(record)
                link = source_row(day, house, row["url"], row["attributed_to"])
                stream.write((b",\n" if count else b"\n") + json.dumps(link, ensure_ascii=False,
                             separators=(",", ":")).encode())
                count += 1
            stream.write(b"\n]")
        working.replace(path)
        receipt.write_text(str(count), encoding="ascii")
    if target:
        shutil.copyfile(path, target)
    return int(receipt.read_text(encoding="ascii"))


def archive_identity(database, profile, ranges):
    wal = database.with_name(database.name + "-wal")
    return canonical_digest([profile, ranges, database.stat().st_mtime_ns,
                             wal.stat().st_mtime_ns if wal.is_file() and wal.stat().st_size else None])


def contribution_axes(corpus, anchors):
    groups = {"is recorded in": "Proceedings", "is attributed to": "Speakers",
              "has recorded capacity": "Recorded capacities"}
    entities = {}
    postings = defaultdict(list)
    for edge in corpus["relationships"]:
        route = edge["source"]
        group = groups.get(edge["kind"])
        if route not in anchors or not group:
            continue
        target = edge["target"]
        related = corpus["nodes"][target]
        key = "activity-" + canonical_digest([group, target])[:24]
        entities[key] = {"label": related["title"], "group": group, "type": related["type"],
                         "route": target, "captured_only": True}
        node = corpus["nodes"][route]
        metadata = node["hansard_proceedings"]
        anchor = anchors[route]
        anchor["entities"].append(key)
        postings[key].append([*source_row(anchor["date"], metadata["house"], anchor["url"],
                                          metadata.get("speaker")), anchor["section"], anchor["order"], route])
    return entities, postings


def write(release, destination, database, cache, *, older_database=None, focused_views=False):
    manifest = release / "backfill" / "manifest.json"
    if not manifest.is_file():
        return
    receipt = json.loads(manifest.read_bytes())
    index = Index(release, database, older_database)
    day_set = set(receipt["dates"])
    corpus = json.loads((release / "okf-bundle.json").read_bytes())["corpora"]["hansard"]
    nodes = corpus["nodes"]
    anchors = {route: {**{field: row[field] for field in ("date", "url", "order")},
                       "entities": list(row["entities"]), "section": row["part"], "title": nodes[route]["title"]}
               for route, row in index.history["contributions"].items() if row["date"] in day_set}
    extra_entities, extra_postings = contribution_axes(corpus, anchors) if focused_views else ({}, {})
    keys = {key for record in anchors.values() for key in record["entities"]}
    assets = destination / "history"
    assets.mkdir()
    results = {}
    db = index.connect()
    older = None
    older_scope = None
    try:
        if db:
            db.execute("BEGIN")
        ranges = archive_ranges(db)
        latest = max(row[1] for row in ranges.values()) if ranges else None
        if db:
            identity = archive_identity(database, index.archive_profile_sha256, ranges)
        older, older_keys, older_profile = index.connect_older()
        if older:
            older.execute("BEGIN")
            older_ranges = archive_ranges(older)
            older_identity = archive_identity(older_database, older_profile, older_ranges)
            older_scope = {"ranges": older_ranges, "profile_sha256": older_profile,
                           "source_gaps": older.execute("SELECT count(*) FROM sitting WHERE status='source gap'").fetchone()[0]}
        for key in sorted(keys):
            if key in extra_entities:
                dump(assets / f"{key}.json", sorted(extra_postings[key], key=lambda row: (row[0], row[4], row[5]),
                                                   reverse=True))
                results[key] = extra_entities[key]
                continue
            package = index.backfill_for(key)
            use_archive = db is not None and key in index.archive_keys
            if package and package["archive"] and not use_archive:
                archive_unavailable = True
            else:
                archive_unavailable = False
            archive_count = archive_asset(db, identity, key, assets / (key + ".archive.json.gz"),
                                          cache) if use_archive else 0
            older_count = archive_asset(older, older_identity, key, assets / (key + ".older.json.gz"),
                                        cache, "1803-11-22") if older and key in older_keys else 0
            entries = []
            for row in (package["items"] if package else []):
                if use_archive and ranges[row["house"]][0] <= row["date"] <= ranges[row["house"]][1]:
                    continue
                entries.append([*source_row(row["date"], row["house"], row["url"], row["attributed_to"]),
                                None, None])
            for row in index.base.get(key, []):
                speaker = row.get("attributed_to") or nodes.get(row["contribution"], {}).get(
                    "hansard_proceedings", {}).get("speaker")
                entry = [*source_row(row["date"], row["house"], row["url"], speaker),
                         row["part"], row["order"]]
                if focused_views and row["contribution"] in anchors:
                    entry.append(row["contribution"])
                entries.append(entry)
            entries.sort(key=lambda row: (row[0], row[4] or "", row[5] or 0), reverse=True)
            dump(assets / (key + ".json"), entries)
            if focused_views:
                dump(assets / (key + ".month.json"), [row for row in entries if len(row) == 7])
            results[key] = {**index.history["entities"][key], "archive_count": archive_count,
                            "search_count": sum(row[4] is None for row in entries),
                            "search_windows": package["search_windows"] if package else [],
                            "complete": bool(package and not package["errors"] and not archive_unavailable),
                            "errors": len(package["errors"]) if package else None}
            if older_count:
                results[key]["older_count"] = older_count
    finally:
        if db:
            db.close()
        if older:
            older.close()
    view = {"schema": "hansard-history-pages.v1", "from": receipt["from"],
            "days": receipt["dates"], "archive_through": latest, "entities": results}
    if focused_views:
        daily = {day: {} for day in receipt["dates"]}
        for route, row in anchors.items():
            daily[row["date"]][route] = row
        for day, records in daily.items():
            dump(assets / "days" / f"{day}.json", records)
        view["focused_views"] = True
        view["month_entity_shards"] = True
    else:
        view["contributions"] = anchors
    if older_scope:
        view["older_archive"] = {"exclusive_before": DEEP_BEFORE, **older_scope}
    dump(assets / "index.json", view)
    for name in ("history.html", "history.js"):
        shutil.copyfile(ROOT / "docs/pages" / name, destination / name)
