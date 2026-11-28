import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from archive import SQL
from capture import dump, sha
import passages
from query import Index


def mention(day, house, identifier, route=None, title="Example"):
    return {"date": day, "house": house, "contribution": route or identifier, "part": "section",
            "order": 1, "url": f"https://hansard.parliament.uk/{house}/{day}/debates/Section/{title}"
            f"#contribution-{identifier}"}


class HistoricalEvidenceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.release = Path(folder.name)
        self.database = self.release / "historical.sqlite"
        self.before, self.gap, self.latest = "2026-10-01", "2026-10-02", "2026-11-03"
        self.normal = mention(self.gap, "Commons", "Archive")
        self.partial = mention(self.gap, "Lords", "Partial")
        self.keep = mention(self.gap, "Lords", "Fallback")
        self.captured = mention("2026-11-02", "Commons", "Capture")
        self.rows = [self.captured, self.keep, mention(self.gap, "Commons", "Suppressed"),
                     mention(self.gap, "Lords", "Partial", "alias", "UpdatedSlug")]
        history = {"mentions": {"topic": [self.captured]},
                   "contributions": {"anchor": {"date": self.latest, "entities": ["topic"],
                                                "part": "anchor-section", "order": 2}},
                   "entities": {"topic": {"label": "Topic"}}}
        dump(self.release / "history.json", history)
        dump(self.release / "analysis-profile.json", {"entities": {"topic": {}}})
        dump(self.release / "receipt.json", {"day_denominators": [{"date": self.latest}],
             "artifacts": {"history.json": {"sha256": "history"}, "analysis-profile.json": {"sha256": "profile"}}})
        self.write_package()
        with sqlite3.connect(self.database) as connection:
            connection.executescript(SQL)
            connection.execute("INSERT INTO metadata VALUES ('profile_sha256','profile')")
            connection.executemany("INSERT INTO sitting VALUES (?,?,?,?,?,?,?)", [
                (self.before, "Commons", "processed", 1, 0, 0, "{}"),
                (self.gap, "Commons", "processed", 1, 1, 1, "{}"),
                (self.gap, "Lords", "source gap", 2, 1, 1, "{}"),
            ])
            for row in (self.normal, self.partial):
                route = row["contribution"]
                connection.execute("INSERT INTO contribution VALUES (?,?,?,?,?,?)",
                                   (route, row["date"], row["house"], row["part"], row["order"],
                                    json.dumps({"url": row["url"]})))
                connection.execute("INSERT INTO mention VALUES (?,?,?,?)", ("topic", row["date"], route, "{}"))

    def write_package(self):
        dump(self.release / "backfill/topic.json", {"entity": "topic", "schema": "hansard-backfill.v1",
             "from": self.before, "through": self.gap, "items": self.rows, "method": "fixture",
             "errors": [], "archive": True})

    def test_gap_preserves_only_distinct_fallback_and_interleaves_pages(self):
        index = Index(self.release, self.database)
        first = index.track("anchor", "topic", limit=2)
        second = index.track("anchor", "topic", limit=2, offset=2, expected_context=first["context_id"])
        self.assertEqual(first["total"], 4)
        self.assertEqual([row["contribution"] for row in first["items"] + second["items"]],
                         ["Capture", "Fallback", "Partial", "Archive"])
        self.assertEqual(first["items"][1]["archive_sitting_status"], "source gap")
        self.assertEqual(first["items"][1]["history_source"], "Hansard search")
        self.assertEqual(second["items"][0]["archive_sitting_status"], "source gap")

    def test_empty_archive_does_not_hide_search_evidence(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("DELETE FROM mention")
            connection.execute("DELETE FROM contribution")
            connection.execute("DELETE FROM sitting")
        answer = Index(self.release, self.database).track("anchor", "topic")
        self.assertIsNone(answer["coverage"]["extension_from"])
        self.assertEqual(answer["total"], 4)

    def test_changed_fallback_content_invalidates_continuation_with_same_count(self):
        index = Index(self.release, self.database)
        earlier = index.track("anchor", "topic", limit=1)
        self.rows[1]["source_value_sha256"] = "changed"
        self.write_package()
        with self.assertRaisesRegex(ValueError, "History was updated"):
            index.track("anchor", "topic", offset=1, expected_context=earlier["context_id"])


class PassageFreshnessTests(unittest.TestCase):
    def test_passage_carries_observation_time_alongside_version_comparison(self):
        access = passages.Passages.__new__(passages.Passages)
        api = "https://hansard-api.parliament.uk/debates/debate/Fixture.json"
        access.locators = {"record": {"capture": {"url": api}, "pointer": "/Items/0",
                                     "url": "https://hansard.parliament.uk/Commons/2026-11-17/debates/Fixture",
                                     "external_id": "item", "source_item_id": 5, "value_sha256": sha(b"Before")}}
        source = {"Items": [{"ExternalId": "item", "ItemId": 5, "Value": "After"}]}
        with mock.patch.object(passages, "retrievable", return_value=(source, "2026-11-28T10:00:00+00:00")):
            result = access.read("record")
        self.assertEqual(result["status"], "source text changed")
        self.assertEqual(result["observed_at"], "2026-11-28T10:00:00+00:00")
        self.assertEqual(result["text"], "After")

    def test_source_observation_is_reused_within_window_and_refetched_after_it(self):
        source = "https://hansard-api.parliament.uk/debates/debate/Fixture.json"
        response = mock.MagicMock(url=source, headers={})
        response.__enter__.return_value = response
        response.read.side_effect = [b'{"version":1}', b'{"version":2}']
        passages.read_source.cache_clear()
        self.addCleanup(passages.read_source.cache_clear)
        with mock.patch.object(passages, "urlopen", return_value=response) as fetch, \
                mock.patch.object(passages.time, "monotonic", side_effect=[10, 20, 130]), \
                mock.patch.object(passages, "now", side_effect=["first", "second"]):
            self.assertEqual(passages.retrievable(source), ({"version": 1}, "first"))
            self.assertEqual(passages.retrievable(source), ({"version": 1}, "first"))
            self.assertEqual(passages.retrievable(source), ({"version": 2}, "second"))
        self.assertEqual(fetch.call_count, 2)
