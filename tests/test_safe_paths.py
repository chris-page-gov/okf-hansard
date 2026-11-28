import tempfile
import unittest
from pathlib import Path

from capture import sha
from model import checked_json, read_sittings
from okf_core import write_release_markdown
from safe_paths import resolve_within


class SafePathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def test_checked_capture_read_accepts_canonical_path_under_symlinked_root(self):
        real = self.base / "capture"
        real.mkdir()
        raw = b'{"items": []}'
        (real / "manifest.json").write_bytes(b'{"ok": true}')
        (real / "data.json").write_bytes(raw)
        alias = self.base / "configured-capture"
        alias.symlink_to(real, target_is_directory=True)

        self.assertEqual(resolve_within(alias, "manifest.json").read_bytes(), b'{"ok": true}')
        self.assertEqual(checked_json(alias, {"path": "data.json", "sha256": sha(raw)}),
                         {"items": []})

    def test_capture_read_rejects_noncanonical_and_symlinked_paths(self):
        root = self.base / "capture"
        root.mkdir()
        outside = self.base / "outside.json"
        outside.write_text('{"outside": true}', encoding="utf-8")
        (root / "linked.json").symlink_to(outside)

        for relative in ("../outside.json", "/outside.json", "folder//item.json",
                         "linked.json"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                checked_json(root, {"path": relative, "sha256": sha(outside.read_bytes())})

    def test_release_writer_checks_routes_and_writes_indexes_through_boundary(self):
        real = self.base / "release-markdown"
        real.mkdir()
        alias = self.base / "configured-release"
        alias.symlink_to(real, target_is_directory=True)
        record = {"title": "Example sitting", "date": "2006-04-18", "body": "# Example\n"}

        write_release_markdown(alias, {"debate/example.md": record}, "2006-04-18",
                               "2006-04-18", "Example", {})

        self.assertTrue((real / "index.md").is_file())
        self.assertTrue((real / "LICENSE.md").is_file())
        self.assertTrue((real / "debate/example.md").is_file())
        self.assertTrue((real / "debate/index.md").is_file())

    def test_section_identifier_must_be_one_component_at_ingestion(self):
        source = {"Overview": {"ExtId": "folder/example"}}
        sitting = {"date": "2006-04-18", "house": "Commons", "roots": [{"section": "Debate"}]}
        with self.assertRaisesRegex(ValueError, "not a single path component"):
            read_sittings(self.base, {"sittings": [sitting]}, "2006-04-18", "2006-04-18",
                          loader=lambda *_: source)

    def test_release_writer_rejects_existing_symlinked_route_component(self):
        root = self.base / "release"
        root.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        (root / "debate").symlink_to(outside, target_is_directory=True)
        record = {"title": "Example", "date": "2006-04-18", "body": "# Example\n"}

        with self.assertRaises(ValueError):
            write_release_markdown(root, {"debate/example.md": record}, "2006-04-18",
                                   "2006-04-18", "Example", {})
        self.assertFalse((outside / "example.md").exists())


if __name__ == "__main__":
    unittest.main()
