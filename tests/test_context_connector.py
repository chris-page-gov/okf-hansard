import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from hansard_access import Access
from mcp_server import ACCESS_TOOLS


class ContributionContextTests(unittest.TestCase):
    def make_access(self, root):
        access = Access.__new__(Access)
        access.site = root
        access.snapshot = "hansard-test-snapshot"
        access._capture_rows = None
        access._section_rows = None
        access._context_index = None
        access._context_days = {}
        access._search_lock = __import__("threading").RLock()
        access.release = root / "release"
        access.release.mkdir(exist_ok=True)
        (access.release / "receipt.json").write_text("{}")
        access.capture = root / "capture"
        access.history = {"days": ["2026-11-02"]}
        access._capture_rows = ({"debate/section.md": {"title": "Section title"}}, {
            f"contribution/turn-{i}.md": {
                "part": "debate/section.md", "day": "2026-11-02", "order": i * 10,
                "capture": {"sha256": "f" * 64}, "text": f"Passage {i}", "url": f"https://hansard.parliament.uk/debates/abc#contribution-{i}",
                "pointer": f"/Items/{i}", "value_sha256": f"hash{i}", "attributed_to": f"Member {i}",
                "member": i + 1, "uint": f"UIN{i}",
            } for i in range(6)
        })
        return access

    def test_context_returns_numbered_neighbours_evidence_and_public_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "context").mkdir()
            (root / "history/days").mkdir(parents=True)
            (root / "context/index.json").write_text(json.dumps({
                "schema": "hansard-contribution-context.v1", "snapshot": "hansard-test-snapshot"}))
            route = "contribution/turn-3.md"
            (root / "history/days/2026-11-02.json").write_text(json.dumps({
                route: {"context": "context/2026-11-02/0123456789abcdef0123-1.html#turn-4"}}))
            access = self.make_access(root)
            result = access.contribution_context(route)
            self.assertEqual([f"contribution/turn-{i}.md" for i in (1, 2, 3, 4, 5)],
                             [turn["id"] for turn in result["turns"]])
            self.assertEqual([2, 3, 4, 5, 6], [turn["position"] for turn in result["turns"]])
            self.assertTrue(result["more_before"])
            self.assertFalse(result["more_after"])
            self.assertEqual("UIN3", result["uin"])
            self.assertEqual("hash3", result["evidence"]["source_value_sha256"])
            self.assertEqual("https://chris-page-gov.github.io/okf-hansard/november/context/2026-11-02/0123456789abcdef0123-1.html#turn-4", result["public_context"])

    def test_stale_public_packet_is_not_mixed_with_local_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "context").mkdir()
            (root / "context/index.json").write_text(json.dumps({
                "schema": "hansard-contribution-context.v1", "snapshot": "stale"}))
            access = self.make_access(root)
            self.assertNotIn("public_context", access.contribution_context("contribution/turn-0.md"))

    def test_context_rejects_stale_snapshot_and_unknown_route(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        access = self.make_access(Path(directory.name))
        with self.assertRaises(ValueError):
            access.contribution_context("contribution/turn-0.md", snapshot="old")
        with self.assertRaises(ValueError):
            access.contribution_context("contribution/missing.md")

    def test_mcp_tool_is_read_only_and_registered(self):
        definition = ACCESS_TOOLS["hansard_contribution_context"]
        self.assertEqual(["contribution"], definition["inputSchema"]["required"])
        self.assertTrue(definition["annotations"]["readOnlyHint"])


if __name__ == "__main__":
    unittest.main()
