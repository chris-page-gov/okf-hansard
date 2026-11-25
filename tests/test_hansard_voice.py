"""Check the bounded dataset and transport-neutral voice tool contract."""

import gzip
import json
from pathlib import Path
import tempfile
import unittest

from capture import dump
from hansard_access import Access, BUNDLE_ID
from mcp_server import rpc
from voice_pages import publish_voice


class VoiceTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)
        self.site = self.work / "site"
        self.release = self.work / "release"
        self.pointer = self.work / "publication.json"
        self.hansard = "https://hansard.parliament.uk/Commons/"
        dump(self.pointer, {"site": str(self.site), "release": str(self.release), "snapshot": str(self.work / "capture"),
                            "through": "2026-11-24", "commit": "fixture", "provisional": False,
                            "verified_at": "2026-11-25T07:00:00Z"})
        dump(self.site / "coverage.json", {"dates": [{"date": "2026-11-24"}], "contributions": 1,
             "verification": {"passed": True}, "backfill": {"from": "2007-01-01", "through": "2026-11-01",
             "method": "literal match", "complete": 1, "entities": 1, "exceptions": {}}})
        dump(self.site / "graph/okf-explorer.json", {"schema": "okf-explorer-large-corpus.v1", "okf_version": "0.3", "snapshot": "fixture-verified"})
        dump(self.site / "history/index.json", {"days": ["2026-11-24"], "entities": {
             "synergy-dwp": {"label": "Synergy programme", "group": "Things", "complete": True, "archive_count": 2}},
             "older_archive": {"ranges": {"Commons": ["2003-02-25", "2006-12-19", 1]}, "source_gaps": 1}})
        dump(self.release / "analysis-profile.json", {"entities": {"synergy-dwp": {"aliases": ["Synergy programme", "DWP Synergy"]}}})
        captured = ["2026-11-24", "Commons", self.hansard + "2026-11-24/#contribution-1", "Member", "section", 1, "route"]
        earlier = ["2026-10-26", "Commons", self.hansard + "2026-10-26/#contribution-2", "Member"]
        dump(self.site / "history/synergy-dwp.json", [captured, [*earlier, None, None]])
        (self.site / "history/synergy-dwp.archive.json.gz").write_bytes(gzip.compress(json.dumps([earlier]).encode()))

    def test_scope_and_complete_paging_have_one_snapshot(self):
        access = Access(self.pointer)
        scope = access.describe()
        self.assertEqual(scope["bundle_id"], BUNDLE_ID)
        self.assertEqual(scope["historical_search"]["through"], "2026-11-01")
        self.assertFalse(scope["older_archive"]["gap_details_complete"])
        concept = access.concepts("DWP Synergy")["items"][0]
        self.assertEqual(concept["id"], "synergy-dwp")
        first = access.mentions(concept["id"], limit=1)
        second = access.mentions(concept["id"], limit=1, offset=first["next_offset"], snapshot=first["snapshot"])
        self.assertEqual(first["total"], 2)
        self.assertEqual(first["items"][0]["date"], "2026-11-24")
        self.assertEqual(second["items"][0]["date"], "2026-10-26")
        self.assertIsNone(second["next_offset"])
        with self.assertRaisesRegex(ValueError, "publication changed"):
            access.mentions(concept["id"], snapshot="old")
        with self.assertRaises(ValueError):
            access.mentions("../../receipt")

    def test_unverified_publication_cannot_be_selected(self):
        row = json.loads(self.pointer.read_bytes())
        dump(self.pointer, {**row, "provisional": True})
        with self.assertRaisesRegex(ValueError, "non-provisional"):
            Access(self.pointer)

    def test_mcp_discovery_and_scope_tool(self):
        access = Access(self.pointer)
        init = rpc({"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}, None, None, None, access)
        self.assertEqual(init["result"]["protocolVersion"], "2025-03-26")
        listed = rpc({"id": 2, "method": "tools/list"}, None, None, None, access)
        self.assertIn("hansard_describe_bundle", {item["name"] for item in listed["result"]["tools"]})
        answer = rpc({"id": 3, "method": "tools/call", "params": {"name": "hansard_describe_bundle"}}, None, None, None, access)
        self.assertEqual(answer["result"]["structuredContent"]["snapshot"], access.snapshot)

    def test_discovery_publishes_one_collection_and_small_copyable_entry(self):
        for name in ("okf/index.md", "history.html", "okf-bundle.yamlld.gz"):
            target = self.site / name
            target.parent.mkdir(exist_ok=True)
            target.write_text("fixture", encoding="utf-8")
        publish_voice(self.site, self.release)
        publication = json.loads((self.site / "hansard.json").read_bytes())
        self.assertEqual([row["id"] for row in publication["bundles"]], [BUNDLE_ID])
        self.assertIn("1 November 2026 inclusive", (self.site / "ask.md").read_text())
        self.assertIn('data-copy="evidence"', (self.site / "ask.html").read_text())


if __name__ == "__main__":
    unittest.main()
