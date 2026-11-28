import json
import sqlite3
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import archive
from model import Entity, Matcher


class IdleCollector:
    telemetry = Counter()

    def check(self):
        pass


class ArchiveRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = sqlite3.connect(Path(self.temp.name) / "history.sqlite")
        self.db.executescript(archive.SQL)
        self.db.execute("INSERT INTO metadata VALUES ('profile_sha256','fixture')")
        self.db.execute("INSERT INTO contribution VALUES (?,?,?,?,?,?)",
                        ("route-1", "2006-04-18", "Commons", "debate", 1, '{"source":"retained"}'))
        self.db.execute("INSERT INTO mention VALUES (?,?,?,?)",
                        ("entity", "2006-04-18", "route-1", '{"evidence":"retained"}'))
        source = {"date": "2006-04-18", "house": "Commons", "sources": [{"path": "old.json"}],
                  "roots": [{"path": "old-root.json", "sha256": "old-hash"}], "errors": ["old timeout"]}
        self.db.execute("INSERT INTO sitting VALUES (?,?,?,?,?,?,?)",
                        ("2006-04-18", "Commons", "source gap", 3, 10, 1,
                         json.dumps(source)))
        self.db.commit()
        entity = Entity("entity", "MP", "Example", None)
        self.matcher = Matcher({"entity": entity}, [])
        self.matcher.entity_groups = {"entity": "People"}

    def test_incomplete_retry_keeps_partial_postings_and_source_receipts(self):
        entry = {"date": "2006-04-18", "house": "Commons", "sources": [{"path": "retry.json"}],
                 "roots": [], "errors": ["Writtens: The read operation timed out"]}
        with patch("archive.capture_day", return_value=entry):
            archive.collect_sitting(self.db, IdleCollector(), self.matcher, "2006-04-18", "Commons", True)

        self.assertEqual(self.db.execute("SELECT status,attempts,passages,retained FROM sitting").fetchone(),
                         ("source gap", 4, 10, 1))
        self.assertEqual(self.db.execute("SELECT route FROM contribution").fetchall(), [("route-1",)])
        self.assertEqual(self.db.execute("SELECT route FROM mention").fetchall(), [("route-1",)])
        saved = json.loads(self.db.execute("SELECT source FROM sitting").fetchone()[0])
        self.assertEqual(saved["roots"][0]["sha256"], "old-hash")
        self.assertEqual(saved["sources"][0]["path"], "old.json")
        self.assertEqual(saved["retry_attempts"][0]["sources"][0]["path"], "retry.json")
        self.assertEqual(saved["last_retry_errors"], entry["errors"])

    def test_first_source_failure_is_saved_as_a_retryable_gap(self):
        self.db.execute("DELETE FROM mention")
        self.db.execute("DELETE FROM contribution")
        self.db.execute("DELETE FROM sitting")
        entry = {"date": "2006-04-18", "house": "Commons", "sources": [],
                 "roots": [], "errors": ["Writtens: The read operation timed out"]}
        with patch("archive.capture_day", return_value=entry):
            archive.collect_sitting(self.db, IdleCollector(), self.matcher, "2006-04-18", "Commons", True)

        self.assertEqual(self.db.execute(
            "SELECT status,attempts,passages,retained FROM sitting"
        ).fetchone(), ("source gap", 1, 0, 0))
        self.assertEqual(self.db.execute("SELECT count(*) FROM contribution").fetchone(), (0,))
        self.assertEqual(self.db.execute("SELECT count(*) FROM mention").fetchone(), (0,))
        saved = json.loads(self.db.execute("SELECT source FROM sitting").fetchone()[0])
        self.assertEqual(saved["errors"], entry["errors"])

    def test_calendar_listed_empty_capture_is_retryable_for_normal_archive(self):
        entry = {"date": "2006-04-18", "house": "Commons", "sources": [],
                 "roots": [], "errors": []}
        with patch("archive.capture_day", return_value=entry):
            archive.collect_sitting(self.db, IdleCollector(), self.matcher, "2006-04-18", "Commons")

        self.assertEqual(self.db.execute("SELECT status,attempts FROM sitting").fetchone(),
                         ("source gap", 4))
        saved = json.loads(self.db.execute("SELECT source FROM sitting").fetchone()[0])
        self.assertTrue(saved["last_retry_errors"][0].startswith("The calendar lists a sitting"))

    def test_calendar_reconciles_legacy_terminal_empty_row(self):
        self.db.execute("UPDATE sitting SET status='no published sections'")
        self.db.execute("INSERT INTO calendar VALUES (?,?,?,?)",
                        ("2006-04", "Commons", '["2006-04-18"]', "{}"))
        self.assertEqual(archive.reconcile_calendar_empty_sittings(self.db), 1)
        self.assertEqual(self.db.execute("SELECT status FROM sitting").fetchone(), ("source gap",))

    def test_calendar_reconciliation_leaves_unlisted_legacy_empty_row_alone(self):
        self.db.execute("UPDATE sitting SET status='no published sections'")
        self.db.execute("INSERT INTO calendar VALUES (?,?,?,?)",
                        ("2006-04", "Commons", '["2006-04-19"]', "{}"))
        self.assertEqual(archive.reconcile_calendar_empty_sittings(self.db), 0)
        self.assertEqual(self.db.execute("SELECT status FROM sitting").fetchone(),
                         ("no published sections",))

    def test_complete_retry_replaces_partial_postings_atomically(self):
        entry = {"date": "2006-04-18", "house": "Commons", "sources": [{"path": "complete.json"}],
                 "roots": [{"path": "root.json"}], "errors": []}
        observed = {("2006-04-18", "Commons"): {}}
        with patch("archive.capture_day", return_value=entry), patch(
                "archive.read_sittings", return_value=(None, {}, None, observed)):
            archive.collect_sitting(self.db, IdleCollector(), self.matcher, "2006-04-18", "Commons", True)

        self.assertEqual(self.db.execute("SELECT status,attempts,passages,retained FROM sitting").fetchone(),
                         ("processed", 4, 0, 0))
        self.assertEqual(self.db.execute("SELECT count(*) FROM contribution").fetchone(), (0,))
        self.assertEqual(self.db.execute("SELECT count(*) FROM mention").fetchone(), (0,))


if __name__ == "__main__":
    unittest.main()
