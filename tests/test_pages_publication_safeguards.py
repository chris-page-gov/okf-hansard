import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from capture import dump, sha
import publish_demo_week as publisher


def november_coverage(day, status="observed", verified_at="2026-11-28T07:15:09+00:00"):
    return {"dates": [{"date": day, "publication_status": status, "verified_at": verified_at}]}


class PagesPublicationSafeguards(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.checkout = self.root / "checkout"

    def preflight(self, candidate, published, through, *, november, size=500):
        dump(self.site / "coverage.json", candidate)
        tree = ("100644 blob abcd 200\tcoverage.json\0"
                "100644 blob abcd 300\tnovember/coverage.json\0")
        with mock.patch.object(publisher, "git", side_effect=[tree, json.dumps(published)]) as git:
            result = publisher.preflight_release(self.site, self.checkout, through, size, november=november)
        coverage_path = "november/coverage.json" if november else "coverage.json"
        self.assertEqual(git.call_args_list[-1], mock.call(self.checkout, "show", "FETCH_HEAD:" + coverage_path))
        return result

    def test_november_rejects_three_ways_a_prepared_candidate_can_fall_behind(self):
        current = november_coverage("2026-11-27")
        for day, status, time in (
            ("2026-11-26", "observed", "2026-11-28T08:00:00+00:00"),
            ("2026-11-27", "provisional", "2026-11-28T08:00:00+00:00"),
            ("2026-11-27", "observed", "2026-11-28T07:14:09+00:00"),
        ):
            with self.subTest(day=day, status=status, time=time):
                with self.assertRaisesRegex(ValueError, "older or provisional"):
                    self.preflight(november_coverage(day, status, time), current, day, november=True)

    def test_same_day_observed_result_can_replace_a_provisional_capture(self):
        day = "2026-11-27"
        candidate = november_coverage(day)
        published = november_coverage(day, "provisional")
        self.assertEqual(self.preflight(candidate, published, day, november=True), 700)

    def test_new_november_capture_cannot_remove_an_observed_day(self):
        published = november_coverage("2026-11-27")
        candidate = november_coverage("2026-11-28")
        candidate["dates"] += november_coverage("2026-11-27", "provisional")["dates"]
        with self.assertRaisesRegex(ValueError, "remove previously observed Hansard dates"):
            self.preflight(candidate, published, "2026-11-28", november=True)

    def test_forecast_counts_the_preserved_scope_and_rejects_the_size_limit(self):
        day = "2026-11-19"
        coverage = {"week_contributions_by_day": {day: 1}, "observed_at": "2026-11-20T08:21:29+00:00"}
        self.assertEqual(self.preflight(coverage, coverage, day, november=False), 800)
        with mock.patch.object(publisher, "PAGES_LIMIT", 800):
            with self.assertRaisesRegex(ValueError, "would exceed the Pages size limit"):
                self.preflight(coverage, coverage, day, november=False)

    def test_week_rejects_a_checksummed_stage_missing_the_contributor_tour(self):
        dump(self.root / "prepared.json", {"through": "2026-11-19"})
        manifest = {}
        for name in publisher.REQUIRED_WEEK_ASSETS - {"contributor-tour.html"}:
            path = self.site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            data = name.encode()
            path.write_bytes(data)
            manifest[name] = {"bytes": len(data), "sha256": sha(data)}
        dump(self.site / "checksums.json", manifest)
        with mock.patch.object(publisher, "git") as git:
            with self.assertRaisesRegex(ValueError, "missing required Pages assets: contributor-tour.html"):
                publisher.publish(self.root, self.checkout)
        git.assert_not_called()

    def test_november_receipt_is_kept_when_pages_advance_then_written_for_the_current_commit(self):
        current = {"commit": "new", "through": "2026-11-27"}
        superseded = {"commit": "old", "through": "2026-11-26"}
        pointer = self.root / "publication.json"
        dump(pointer, current)
        with mock.patch.object(publisher, "PAGES_LOCK", self.root / "pages.lock"), \
                mock.patch.object(publisher, "git", return_value="new\trefs/heads/gh-pages"):
            with self.assertRaisesRegex(RuntimeError, "Pages advanced during verification"):
                publisher.write_current_receipt(self.checkout, pointer, superseded)
            self.assertEqual(publisher.read(pointer), current)
            pointer.unlink()
            publisher.write_current_receipt(self.checkout, pointer, current)
            self.assertEqual(publisher.read(pointer), current)
