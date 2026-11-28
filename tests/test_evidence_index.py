"""Check the small repository index and its verified publication boundaries."""

from datetime import datetime
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock, patch

from capture import dump, sha
from evidence_index import render_evidence_index
from hansard_access import snapshot_id
from publish_november import run, ZONE


class EvidenceIndexTests(TestCase):
    def test_rejects_mixed_snapshot_and_renders_coherent_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            day = "2026-11-25"
            count = {"Commons": {"contributions": 1}, "Lords": {"contributions": 2}}
            coverage = {"dates": [{"date": day, "houses": count, "publication_status": "observed"}],
                        "verification": {"passed": True}, "contributions": 3,
                        "backfill": {"from": "2007-01-01", "through": "2026-11-01", "entities": 1, "complete": 1}}
            graph = {"snapshot": "fixed-graph"}
            dump(site / "graph/okf-explorer.json", graph)
            dump(site / "coverage.json", coverage)
            dump(site / "history/index.json", {"days": [day]})
            bundle = {"capture": {"from": day, "through": day, "contributions": 3, "sitting_dates": [day]},
                      "snapshot": snapshot_id(site, graph), "entrypoints": {
                          "coverage": {"sha256": sha((site / "coverage.json").read_bytes())}}}
            stage = {"site": str(site), "snapshot": str(site), "release": str(site), "through": day}
            for label in ("coherent", "mismatched"):
                with self.subTest(label=label):
                    if label == "mismatched":
                        bundle["snapshot"] = "different-snapshot"
                    dump(site / "hansard.json", {"bundles": [bundle]})
                    files = ("hansard.json", "coverage.json", "history/index.json", "graph/okf-explorer.json")
                    dump(site / "checksums.json", {name: {"bytes": (site / name).stat().st_size,
                                                         "sha256": sha((site / name).read_bytes())}
                                                   for name in files})
                    with patch("evidence_index.latest_examples", return_value=["- Verified example"]):
                        if label == "coherent":
                            md = render_evidence_index(stage)
                            self.assertIn("Verified capture through 2026-11-25.", md)
                            self.assertIn("| 2026-11-25 | 1 | 2 |", md)
                            self.assertIn("Verified example", md)
                        else:
                            with self.assertRaisesRegex(ValueError, "verified capture"):
                                render_evidence_index(stage)

    def test_same_day_refresh_repairs_the_index_without_publishing_pages(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            receipt = {"through": "2026-11-25", "provisional": False}
            dump(state / "publication.json", receipt)
            sync = Mock()
            with patch("publish_november.datetime") as clock, patch("publish_november.publish") as publish:
                clock.now.return_value = datetime(2026, 11, 26, tzinfo=ZONE)
                run(state, state / "pages-checkout", evidence_sync=sync)
            sync.assert_called_once_with(receipt)
            publish.assert_not_called()

    def test_checked_capture_reaches_index_even_when_pages_deployment_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            day = "2026-11-25"
            work = state / "publication-attempts" / day / "071500"
            days, release, site = work / "days", work / "release", work / "site"
            prepared = {"format": "0.3", "through": day, "days": str(days), "release": str(release),
                        "site": str(site), "site_identity": {}}
            dump(state / "publication.json", {"through": "2026-11-24", "provisional": False})
            dump(work / "prepared.json", prepared)
            dump(days / f"{day}.json", {"publication_status": "observed"})
            dump(release / "receipt.json", {"week_contributions_by_day": {day: 1}})
            dump(release / "backfill/manifest.json", {"exceptions": {}})
            steps = Mock()
            steps.publish.side_effect = RuntimeError("Pages size limit")
            with (patch("publish_november.datetime") as clock,
                  patch("publish_november.verify_build_artifacts", return_value={"week_contributions_by_day": {day: 1}}),
                  patch("publish_november.validate_november_site", return_value={}),
                  patch("publish_november.publish", steps.publish)):
                clock.now.return_value = datetime(2026, 11, 26, tzinfo=ZONE)
                with self.assertRaisesRegex(RuntimeError, "Pages size limit"):
                    run(state, state / "pages-checkout", evidence_sync=steps.sync)
            self.assertEqual([call[0] for call in steps.mock_calls], ["sync", "publish"])
            steps.sync.assert_called_once_with(prepared)
