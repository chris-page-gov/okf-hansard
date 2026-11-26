"""Focused safety checks for the protected evidence-index synchroniser."""

import unittest
from unittest.mock import patch

import sync_evidence_index as syncer


class SyncEvidenceIndexTests(unittest.TestCase):
    def test_identical_main_content_returns_without_creating_a_branch(self):
        body = "# Evidence\n\nVerified capture through 2026-11-24.\n"
        with (patch.object(syncer, "_api", return_value={"object": {"sha": "base"}}),
              patch.object(syncer, "_protected") as protection,
              patch.object(syncer, "_get_file", return_value={"content": syncer.b64encode(body.encode()).decode()})):
            result = syncer.sync(body)
        self.assertEqual(result, {"status": "unchanged", "sha": "base"})
        protection.assert_not_called()

    def test_newer_main_marker_prevents_downgrade(self):
        desired = "# Evidence\n\nVerified capture through 2026-11-20.\n"
        current = "# Evidence\n\nVerified capture through 2026-11-24.\n"
        with (patch.object(syncer, "_api", return_value={"object": {"sha": "base"}}),
              patch.object(syncer, "_protected") as protection,
              patch.object(syncer, "_get_file", return_value={"content": syncer.b64encode(current.encode()).decode()})):
            self.assertEqual(syncer.sync(desired), {"status": "newer", "sha": "base"})
        protection.assert_not_called()

    def test_invalid_date_marker_fails_closed(self):
        with self.assertRaisesRegex(syncer.SyncError, "invalid capture-through date"):
            syncer.sync("# Evidence\n\nVerified capture through 2026-99-99.\n")

    def test_capture_header_is_required(self):
        with self.assertRaisesRegex(syncer.SyncError, "one capture-through marker"):
            syncer.sync("# Evidence\n")


if __name__ == "__main__":
    unittest.main()
