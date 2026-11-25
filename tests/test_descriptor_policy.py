"""Keep full-graph descriptors within the pinned static Reader transfer limit."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import publish_demo_week
import verify_public
from descriptor_policy import MAX_DESCRIPTOR_BYTES, validate_descriptor_size


class DescriptorPolicyTests(unittest.TestCase):
    def descriptor(self, site, size):
        path = site / "graph/okf-explorer.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            stream.truncate(size)
        return path

    def test_descriptor_at_limit_is_allowed_and_one_byte_over_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / "site"
            site.mkdir()
            self.descriptor(site, MAX_DESCRIPTOR_BYTES)
            self.assertEqual(MAX_DESCRIPTOR_BYTES, validate_descriptor_size(site))
            self.descriptor(site, MAX_DESCRIPTOR_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "pinned Reader limit"):
                validate_descriptor_size(site)

    def test_week_publication_refuses_oversized_descriptor_before_lock_or_rsync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = root / "attempt"
            site = prepared / "site"
            site.mkdir(parents=True)
            (prepared / "prepared.json").write_text(json.dumps({"through": "2026-11-18"}))
            self.descriptor(site, MAX_DESCRIPTOR_BYTES + 1)
            with mock.patch.object(publish_demo_week, "pages_lock") as lock, \
                    mock.patch.object(publish_demo_week, "git") as git:
                with self.assertRaisesRegex(ValueError, "pinned Reader limit"):
                    publish_demo_week.publish(prepared, root / "checkout")
                lock.assert_not_called()
                git.assert_not_called()

    def test_public_verification_refuses_oversized_descriptor_before_catalogue_read(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            self.descriptor(site, MAX_DESCRIPTOR_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "pinned Reader limit"):
                verify_public.catalogue(site)

    def test_symlinked_descriptor_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            site = root / "site"
            site.mkdir()
            outside = root / "descriptor.json"
            outside.write_text("{}")
            graph = site / "graph"
            graph.mkdir()
            (graph / "okf-explorer.json").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "regular file inside"):
                validate_descriptor_size(site)


if __name__ == "__main__":
    unittest.main()
