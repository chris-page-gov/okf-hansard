"""Check that lazy in-memory FTS use is safe across HTTP worker threads."""

from concurrent.futures import ThreadPoolExecutor
from threading import RLock
import unittest

from hansard_access import Access


class HansardAccessConcurrencyTests(unittest.TestCase):
    def test_concurrent_search_builds_and_uses_one_locked_fts_connection(self):
        access = Access.__new__(Access)
        access.snapshot = "fixture-snapshot"
        access.pointer = {"through": "2026-11-18"}
        access.history = {"days": ["2026-11-18"]}
        access._capture_rows = (
            {"debate-1": {"title": "Budget debate"}},
            {"route-1": {"text": "The budget was discussed.", "attributed_to": "Example MP",
                          "day": "2026-11-18", "house": "Commons", "part": "debate-1",
                          "url": "https://hansard.parliament.uk/Commons/2026-11-18/debates/example"}},
        )
        access.search_db = None
        access._search_lock = RLock()

        def search(_):
            return access.search("budget")

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(search, range(32)))

        self.assertEqual(len(results), 32)
        self.assertTrue(all(result["total"] == 1 for result in results))
        self.assertTrue(all(result["items"][0]["id"] == "route-1" for result in results))
        self.assertIsNotNone(access.search_db)


if __name__ == "__main__":
    unittest.main()
