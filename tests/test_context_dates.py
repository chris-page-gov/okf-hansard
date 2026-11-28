from pathlib import Path
import json
import tempfile
import unittest
from urllib.parse import urljoin

from context_dates import publish_dates


class DateRangeTests(unittest.TestCase):
    def test_inclusive_ranges_omit_gaps_and_stop_at_month_end(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dates = [("2026-10-30", 1), ("2026-10-31", 0), ("2026-11-01", 0), ("2026-11-03", 3)]
            coverage = {"dates": [{"date": day, "publication_status": "observed", "houses": {
                "Commons": {"contributions": count}}} for day, count in reversed(dates)]}
            index = {"snapshot": "s", "contributions": 4,
                     "days": {day: {"contributions": count} for day, count in dates if count}}
            publish_dates(root, index, coverage)
            self.assertEqual(["2026-10", "2026-11"], list(index["calendar"]["months"]))
            path = root / index["calendar"]["range"].format(start="2026-10-30", end="2026-10-31")
            record = json.loads(path.read_bytes())
            self.assertGreater(len(path.read_text().splitlines()), len(record["dates"]))
            self.assertEqual("2026-10-30/2026-10-31", record["interval"])
            self.assertEqual(1, record["contributions"])
            self.assertEqual((root / "2026-10-30/index.html").as_uri(),
                             urljoin(path.as_uri(), record["dates"][0]["sections"]))
            self.assertNotIn("sections", record["dates"][1])
            self.assertFalse((root / "ranges/2026-10-31/2026-11-01.json").exists())
            self.assertFalse((root / "ranges/2026-11-01/2026-11-03.json").exists())
            one = json.loads((root / "ranges/2026-11-03/2026-11-03.json").read_bytes())
            self.assertEqual(3, one["contributions"])
