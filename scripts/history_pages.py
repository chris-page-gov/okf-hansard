"""Project verified history to reusable, per-entity Pages assets."""

import gzip
import json
from pathlib import Path
import shutil
from urllib.parse import urlparse

from backfill import FLOOR, archive_ranges
from capture import dump
from query import Index, canonical_digest

ROOT = Path(__file__).resolve().parents[1]


def source_row(day, house, url, attribution):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "hansard.parliament.uk":
        raise ValueError("History contains an unexpected Hansard evidence link.")
    return [day, house, url, attribution or ""]


def archive_asset(db, identity, key, target, cache):
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
            """, (key, FLOOR.isoformat())):
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


def archive_identity(index, ranges):
    database = index.database
    wal = database.with_name(database.name + "-wal")
    return canonical_digest([index.archive_profile_sha256, ranges, database.stat().st_mtime_ns,
                             wal.stat().st_mtime_ns if wal.is_file() and wal.stat().st_size else None])


def write(release, destination, database, cache):
    manifest = release / "backfill" / "manifest.json"
    if not manifest.is_file():
        return
    receipt = json.loads(manifest.read_bytes())
    index = Index(release, database)
    day_set = set(receipt["dates"])
    nodes = json.loads((release / "okf-bundle.json").read_bytes())["corpora"]["hansard"]["nodes"]
    anchors = {route: {**{field: row[field] for field in ("date", "entities", "url", "order")},
                       "section": row["part"], "title": nodes[route]["title"]}
               for route, row in index.history["contributions"].items() if row["date"] in day_set}
    keys = {key for record in anchors.values() for key in record["entities"]}
    db = index.connect()
    assets = destination / "history"
    assets.mkdir()
    results = {}
    try:
        if db:
            db.execute("BEGIN")
        ranges = archive_ranges(db)
        latest = max(row[1] for row in ranges.values()) if ranges else None
        if db:
            identity = archive_identity(index, ranges)
        for key in sorted(keys):
            package = index.backfill_for(key)
            use_archive = db is not None and key in index.archive_keys
            if package and package["archive"] and not use_archive:
                archive_unavailable = True
            else:
                archive_unavailable = False
            archive_count = archive_asset(db, identity, key, assets / (key + ".archive.json.gz"),
                                          cache) if use_archive else 0
            entries = []
            for row in (package["items"] if package else []):
                if use_archive and ranges[row["house"]][0] <= row["date"] <= ranges[row["house"]][1]:
                    continue
                entries.append([*source_row(row["date"], row["house"], row["url"], row["attributed_to"]),
                                None, None])
            for row in index.base.get(key, []):
                entries.append([*source_row(row["date"], row["house"], row["url"], row.get("attributed_to")),
                                row["part"], row["order"]])
            entries.sort(key=lambda row: (row[0], row[4] or "", row[5] or 0), reverse=True)
            dump(assets / (key + ".json"), entries)
            results[key] = {**index.history["entities"][key], "archive_count": archive_count,
                            "search_count": sum(row[4] is None for row in entries),
                            "search_windows": package["search_windows"] if package else [],
                            "complete": bool(package and not package["errors"] and not archive_unavailable),
                            "errors": len(package["errors"]) if package else None}
    finally:
        if db:
            db.close()
    dump(assets / "index.json", {"schema": "hansard-history-pages.v1", "from": receipt["from"],
                                "days": receipt["dates"], "archive_through": latest,
                                "entities": results, "contributions": anchors})
    for name in ("history.html", "history.js"):
        shutil.copyfile(ROOT / "docs/pages" / name, destination / name)
