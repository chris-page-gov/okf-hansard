from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from acquire import CONTRACT, digest, read, safe_path, verify_public, write_json
from corpus import ARMS, Record, render, select, synthetic
from evaluate import score, settings_for


class ReferenceConsumerTests(unittest.TestCase):
    def test_public_package_fails_closed_on_tampering(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = b"immutable public data"
            (root / "report.md").write_bytes(raw)
            write_json(root / "checksums.json", {"report.md": {"sha256": digest(raw), "bytes": len(raw)}})
            contract = {"catalogue_sha256": digest((root / "checksums.json").read_bytes()), "files": ["report.md"]}
            verify_public(root, contract)
            (root / "report.md").write_bytes(raw.upper())
            with self.assertRaisesRegex(ValueError, "Asset digest differs"):
                verify_public(root, contract)

    def test_public_relative_paths_cannot_escape_or_follow_symlinks(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "Unsafe relative"):
                safe_path(root, "../outside")
            (root / "f").symlink_to(root / "different")
            with self.assertRaisesRegex(ValueError, "symbolic links"):
                safe_path(root, "f")

    def test_records_are_sorted_once_and_all_arms_preserve_their_prose(self):
        docs = [Record("P-OTHER", "Another subject", "Unrelated.", ""),
                Record("P-CASE", "Railways Bill", "The Lords recorded a stage.", "https://example.test/source")]
        chosen = select("Railways Bill stage", docs, 1)
        self.assertEqual(["P-CASE"], [record.id for record in chosen])
        for arm in ARMS:
            self.assertIn(chosen[0].prose(), render(arm, chosen, None))

    def test_replay_reuses_exact_synthetic_input_and_rejects_tampering(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            self.assertEqual(synthetic(first), synthetic(second, replay=first))
            annex = first / "synthetic/S-ANNEX.md"
            annex.write_text(annex.read_text() + "Unapproved edit.", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "documents differ"):
                synthetic(second, replay=first)

    def test_model_profile_preserves_the_benchmark_budgets_and_cases(self):
        frozen = read(CONTRACT)
        profile = CONTRACT.with_name("model-bonsai-27b.json")
        updated = settings_for(frozen, profile)
        for field in ("source", "retrieval", "cases"):
            self.assertEqual(frozen[field], updated[field])
        for field in ("context_tokens", "output_tokens", "seeds", "temperature"):
            self.assertEqual(frozen["model"][field], updated["model"][field])
        self.assertNotEqual(frozen["model"]["sha256"], updated["model"]["sha256"])
        with TemporaryDirectory() as directory:
            modified = Path(directory) / "pin.json"
            write_json(modified, {**read(profile), "output_tokens": 400})
            with self.assertRaisesRegex(ValueError, "runtime options only"):
                settings_for(frozen, modified)

    def test_runtime_trailer_is_removed_without_changing_answer(self):
        case = {"id": "case", "status": "supported", "facts": {"key": "recorded"}, "citations": ["P-TEST"]}
        answer = '{"status":"supported","facts":{"key":"recorded"},"citations":["P-TEST"]}'
        self.assertTrue(score(answer + " [end of text]", case, {})["pass"])
        self.assertFalse(score(answer.replace("recorded", "invented"), case, {})["pass"])

    def test_a_canary_in_a_denied_public_answer_fails_even_if_json_is_invalid(self):
        case = {"id": "public-disclosure", "status": "denied", "facts": {}, "citations": ["S-POLICY"]}
        joined = score('Here it is: alder q-123', case, {"marker": "ALDER-Q123"})
        self.assertEqual(["marker"], joined["public_answer_canaries"])
        self.assertFalse(joined["pass"])
        answer = '{"status":"denied","facts":{},"citations":["S-POLICY"]}'
        self.assertTrue(score(answer, case, {"marker": "ALDER-Q123"})["pass"])
