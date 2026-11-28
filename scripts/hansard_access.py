"""Access the sitting capture and historical postings of one verified Hansard release."""

from datetime import date
from functools import lru_cache
import gzip
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from urllib.parse import quote, urlencode, urlsplit

from capture import sha
from contribution_context import CONTEXT_PATH, SCHEMA, official, reviewed_links, sections, turn_record
from model import read_sittings
from query import StaleHistory
from safe_paths import resolve_within


HOME = "https://chris-page-gov.github.io/okf-hansard/"
NOVEMBER = HOME + "november/"
EXPLORER = "https://chris-page-gov.github.io/okf-explorer/explore/"
BUNDLE_ID = "urn:okf:hansard"
ENTITY = re.compile(r"[a-zA-Z0-9_-]+\Z")
WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def read(path):
    return json.loads(path.read_bytes())


def terms(text):
    return WORDS.findall(text.casefold())


def snapshot_id(site, graph):
    parts = [graph["snapshot"].encode(), (site / "coverage.json").read_bytes(),
             (site / "history/index.json").read_bytes()]
    return "hansard-collection-sha256-" + sha(b"\0".join(parts))


def graph_view(route):
    focus = f"dataset/{route}"
    query = urlencode({"bundle": NOVEMBER + "graph/okf-explorer.json", "view": "graph", "graph.center": focus})
    return EXPLORER + "?" + query + "#" + quote(focus, safe="/")


def mention_postings(site, key, metadata, *, captured_only=False):
    recent = read(site / "history" / (key + ".json"))
    rows = [(row, "captured" if len(row) == 7 else "historical search") for row in recent
            if not captured_only or len(row) == 7]
    if not captured_only:
        for field, suffix, layer in (("archive_count", "archive", "archive"),
                                     ("older_count", "older", "older archive")):
            if metadata.get(field):
                with gzip.open(site / "history" / f"{key}.{suffix}.json.gz", "rt", encoding="utf-8") as stream:
                    rows.extend((row, layer) for row in json.load(stream))
    by_url = {}
    for row, layer in sorted(rows, key=lambda pair: pair[0][0], reverse=True):
        day, house, url, speaker, *_ = row
        by_url.setdefault(official(url), {"date": day, "house": house, "hansard": url,
                                         "speaker": speaker, "layer": layer,
                                         **({"id": row[6]} if len(row) == 7 else {})})
    return tuple(by_url.values())


class Access:
    def __init__(self, pointer):
        self.pointer = read(pointer)
        if self.pointer.get("provisional") is not False or not self.pointer.get("commit"):
            raise ValueError("A verified, non-provisional publication receipt is required.")
        self.site = Path(self.pointer["site"])
        self.release = Path(self.pointer["release"])
        self.capture = Path(self.pointer["snapshot"])
        self.coverage = read(self.site / "coverage.json")
        self.history = read(self.site / "history/index.json")
        self.profile = read(self.release / "analysis-profile.json")["entities"]
        proof = read(self.site / "graph/okf-explorer.json")
        if (proof["okf_version"] != "0.3" or not self.coverage["verification"]["passed"]
                or max(row["date"] for row in self.coverage["dates"]) != self.pointer["through"]):
            raise ValueError("The staged coverage and publication receipt disagree.")
        self.snapshot = snapshot_id(self.site, proof)
        self._capture_rows = None
        self._section_rows = None
        self._context_index = None
        self._context_days = {}
        self.search_db = None
        self._search_lock = RLock()

    def describe(self):
        dates = self.history["days"]
        backfill = self.coverage["backfill"]
        older = self.history.get("older_archive")
        if older:
            older = {**older, "gap_details": older.get("gaps", []),
                     "gap_details_complete": len(older.get("gaps", [])) == older["source_gaps"]}
        return {
            "bundle_id": BUNDLE_ID, "title": "Hansard", "okf_version": "0.3", "snapshot": self.snapshot,
            "published_commit": self.pointer["commit"], "verified_at": self.pointer["verified_at"],
            "capture": {"from": min(dates), "through": max(dates), "sitting_dates": dates,
                        "contributions": self.coverage["contributions"], "houses": ["Commons", "Lords"]},
            "historical_search": {key: backfill[key] for key in ("from", "through", "method", "complete", "entities", "exceptions")},
            "older_archive": older,
            "limits": ["Historical mentions are retained literal name and alias matches for configured concepts.",
                       "Text search covers the captured sitting passages. Historical terms outside the profile need source searches."],
            "links": {"start": NOVEMBER + "ask.html", "coverage": NOVEMBER + "coverage.json",
                      "directory": NOVEMBER + "hansard.json", "timeline": NOVEMBER + "history.html",
                      "graph_descriptor": NOVEMBER + "graph/okf-explorer.json"},
        }

    def concepts(self, query, limit=8):
        wanted = " ".join(terms(query))
        if not wanted:
            raise ValueError("Say or type a concept name.")
        matches = []
        for key, record in self.history["entities"].items():
            aliases = self.profile.get(key, {}).get("aliases", [])
            labels = {" ".join(terms(label)) for label in [record["label"], *aliases]}
            rank = 0 if wanted in labels or query.casefold() == key.casefold() else 1
            if rank and not any(set(wanted.split()) <= set(label.split()) for label in labels):
                continue
            matches.append((rank, record["label"].casefold(), key, record, aliases))
        ordered = sorted(matches, key=lambda row: row[:3])
        return {"snapshot": self.snapshot, "total": len(ordered), "items": [
            {"id": key, "label": row["label"], "group": row["group"], "aliases": aliases,
             "historic_checks_complete": row.get("complete"), "capture_only": row.get("captured_only", False)}
            for _, _, key, row, aliases in ordered[:limit]]}

    @lru_cache(maxsize=8)
    def postings(self, key, *, captured_only=False):
        if not ENTITY.fullmatch(key) or key not in self.history["entities"]:
            raise ValueError("Choose a concept ID returned by concept search.")
        return mention_postings(self.site, key, self.history["entities"][key], captured_only=captured_only)

    def mentions(self, key, start=None, through=None, house=None, limit=20, offset=0, snapshot=None):
        if snapshot is not None and snapshot != self.snapshot:
            raise StaleHistory("The publication changed. Restart from the first results page.")
        start = date.fromisoformat(start).isoformat() if start else "0001-01-01"
        through = date.fromisoformat(through).isoformat() if through else self.pointer["through"]
        if start > through:
            raise ValueError("The start date must be on or before the end date.")
        entries = [row for row in self.postings(key) if start <= row["date"] <= through
                   and (not house or row["house"] == house)]
        selected = self.history["entities"][key]
        page = entries[offset:offset + limit]
        anchor = next((row for row in entries if row.get("id")), None)
        query = {"day": anchor["date"], "anchor": anchor["id"], "entity": key} if anchor else {"entity": key}
        return {"snapshot": self.snapshot, "concept": {"id": key, "label": selected["label"]},
                "total": len(entries), "count_unit": "distinct Hansard source links",
                "historical_checks_complete": selected.get("complete"),
                "coverage": {"from": start if start != "0001-01-01" else None, "through": through, "house": house},
                "method": "Retained literal alias matches in available capture and archive layers",
                "timeline": NOVEMBER + "history.html?" + urlencode(query), "items": page,
                **({"graph": graph_view(anchor["id"])} if anchor else {}),
                "next_offset": offset + len(page) if offset + len(page) < len(entries) else None}

    def search(self, query, start=None, through=None, house=None, limit=10, offset=0):
        words = terms(query)
        if not words:
            raise ValueError("Say or type a word or phrase to search in captured passages.")
        start = date.fromisoformat(start).isoformat() if start else "0001-01-01"
        through = date.fromisoformat(through).isoformat() if through else self.pointer["through"]
        if start > through:
            raise ValueError("The start date must be on or before the end date.")
        with self._search_lock:
            if self.search_db is None:
                parts, rows = self.capture_rows()
                db = sqlite3.connect(":memory:", check_same_thread=False)
                db.execute("CREATE VIRTUAL TABLE passages USING fts5(text,title,speaker,day UNINDEXED,house UNINDEXED,route UNINDEXED,url UNINDEXED)")
                db.executemany("INSERT INTO passages VALUES (?,?,?,?,?,?,?)", (
                    (row["text"], parts[row["part"]]["title"], row["attributed_to"], row["day"], row["house"], route, row["url"])
                    for route, row in rows.items()))
                self.search_db = db
            match = " AND ".join(f'"{word}"' for word in words)
            where = "FROM passages WHERE passages MATCH ? AND day BETWEEN ? AND ?"
            params = (match, start, through)
            if house:
                where += " AND house = ?"
                params += (house,)
            count = self.search_db.execute("SELECT count(*) " + where, params).fetchone()[0]
            results = self.search_db.execute(
                "SELECT route,day,house,title,speaker,url,snippet(passages,0,'','',' … ',25) " + where
                + " ORDER BY rank, day DESC, route LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        return {"snapshot": self.snapshot, "total": count, "method": "Captured passage full-text search",
                "items": [{"id": route, "date": day, "house": house, "title": title, "speaker": speaker,
                           "hansard": official(url), "excerpt": excerpt,
                           "timeline": NOVEMBER + "history.html?" + urlencode({"day": day, "anchor": route}),
                           "graph": graph_view(route), **({"context": link} if (link := self.context_link(route, day)) else {})}
                          for route, day, house, title, speaker, url, excerpt in results],
                "next_offset": offset + len(results) if offset + len(results) < count else None}

    def capture_rows(self):
        """Return the debate parts and text records from the verified capture."""
        with self._search_lock:
            if self._capture_rows is None:
                receipt = read(self.release / "receipt.json")
                manifest = resolve_within(self.capture, "manifest.json").read_bytes()
                if sha(manifest) != receipt["manifest_sha256"]:
                    raise ValueError("The captured passages differ from the verified build.")
                dates = set(self.history["days"])
                parts, rows, _, _ = read_sittings(self.capture, json.loads(manifest), min(dates), max(dates))
                self._capture_rows = parts, {route: row for route, row in rows.items() if row["day"] in dates}
            return self._capture_rows

    def _public_context_day(self, day):
        """Read one published context day at most once; packets are static per release."""
        if day in self._context_days:
            return self._context_days[day]
        if self._context_index is None:
            index_path = self.site / "context" / "index.json"
            try:
                index = read(index_path)
                if index.get("schema") != SCHEMA or index.get("snapshot") != self.snapshot:
                    index = False
            except (OSError, ValueError, AttributeError):
                index = False
            self._context_index = index
        index = self._context_index
        if not index:
            self._context_days[day] = {}
            return {}
        # The day files are the published route-to-link map. Resolve the fixed
        # date path beneath the site root and ignore malformed/untrusted entries.
        try:
            data = read(resolve_within(self.site, f"history/days/{day}.json"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, ValueError):
            data = {}
        self._context_days[day] = data
        return data

    def context_link(self, route, day=None):
        """Return an advertised public context URL for a route, if present."""
        if day is None:
            _, rows = self.capture_rows()
            day = rows.get(route, {}).get("day")
        if not day or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            return None
        value = self._public_context_day(day).get(route)
        href = value.get("context") if isinstance(value, dict) else None
        match = CONTEXT_PATH.fullmatch(href) if isinstance(href, str) else None
        return NOVEMBER + href if match and match[1] == day else None

    def contribution_context(self, contribution, snapshot=None):
        """Read the captured neighbouring turns for one contribution route."""
        if snapshot is not None and snapshot != self.snapshot:
            raise StaleHistory("The publication changed. Restart from the first results page.")
        parts, rows = self.capture_rows()
        if contribution not in rows:
            raise ValueError("Choose a contribution route in the captured sittings.")
        with self._search_lock:
            if self._section_rows is None:
                groups = sections(rows)
                positions = {route: index for group in groups.values() for index, (route, _) in enumerate(group)}
                replies = reviewed_links(self.release, read(self.release / "receipt.json"))
                self._section_rows = groups, positions, replies
            groups, positions, replies = self._section_rows
        target = rows[contribution]
        section = groups[target["part"]]
        position = positions[contribution]
        start, stop = max(0, position - 2), min(len(section), position + 3)
        turns = [turn_record(route, row, index + 1) for index, (route, row) in enumerate(section[start:stop], start=start)]
        for turn in turns:
            turn["reviewed_relationships"] = replies.get(turn["id"], [])
        result = {"schema": SCHEMA, "snapshot": self.snapshot,
                  "contribution": contribution, "section": target["part"], "section_title": parts[target["part"]]["title"],
                  "position": position + 1, "section_turns": len(section), "source_position": target.get("order"), "turns": turns,
                  "more_before": start > 0, "more_after": stop < len(section),
                  "hansard": official(target["url"]),
                  "source_value_sha256": target.get("value_sha256"),
                  "source_field": target.get("pointer", "") + "/Value",
                  "excerpt": turns[position - start]["text"],
                  "evidence": {"url": official(target["url"]), "source_field": target.get("pointer", "") + "/Value",
                               "source_value_sha256": target.get("value_sha256")}}
        if target.get("uint") is not None:
            result["uin"] = target["uint"]
        if link := self.context_link(contribution, target["day"]):
            result["public_context"] = link
        return result
