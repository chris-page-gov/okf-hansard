"""Test the evidence and date boundaries of a member's briefing."""

from types import SimpleNamespace
import unittest

from briefings import briefing


class BriefingTests(unittest.TestCase):
    def setUp(self):
        self.urls = [f"https://hansard.parliament.uk/Commons/#contribution-{n}" for n in range(3)]
        rows = [
            {"hansard": self.urls[0], "id": "c1", "date": "2026-11-24", "house": "Commons", "layer": "captured"},
            {"hansard": self.urls[1], "id": "c2", "date": "2026-11-20", "house": "Commons", "layer": "captured"},
            {"hansard": self.urls[2], "date": "2026-10-20", "house": "Commons", "layer": "archive"},
        ]
        records = {
            "c1": {"member": 3966, "attributed_to": "Alex Example", "part": "debate", "url": self.urls[0],
                   "text": "The Synergy programme was discussed in the House."},
            "c2": {"member": 1234, "attributed_to": "Pat Example", "part": "debate", "url": self.urls[1],
                   "text": "The Department provided an update on the Synergy programme."},
        }
        topic = {"label": "Synergy programme", "aliases": ["Synergy contract"]}
        self.access = SimpleNamespace(
            history={"days": ["2026-11-20", "2026-11-24"], "entities": {"synergy-dwp": topic}},
            profile={"synergy-dwp": topic}, pointer={"commit": "abc", "verified_at": "2026-11-25T07:00:00Z"},
            snapshot="hansard-collection-sha256-fixture", postings=lambda _, **options: rows,
            capture_rows=lambda: ({"debate": {"title": "DWP shared services"}}, records))
        self.portfolio = [{"key": "synergy-dwp", "from": "2026-10-01"}]

    def test_separates_exact_member_and_others_using_verified_passages(self):
        answer = briefing(self.access, 3966, self.portfolio)
        topic = answer["topics"][0]
        self.assertEqual(topic["signed_in_member"]["total"], 1)
        self.assertEqual(topic["signed_in_member"]["examples"][0]["hansard"], self.urls[0])
        self.assertEqual(topic["other_contributions"]["examples"][0]["speaker"], "Pat Example")
        self.assertIn("Synergy programme", topic["signed_in_member"]["examples"][0]["excerpt"])
        self.assertEqual(answer["snapshot"], self.access.snapshot)

    def test_dated_assignment_excludes_outside_sittings_and_archive(self):
        self.portfolio[0].update({"through": "2026-11-21"})
        answer = briefing(self.access, 3966, self.portfolio, start="2026-10-19", through="2026-11-25")
        self.assertEqual(answer["requested"]["through"], "2026-11-25")
        self.assertEqual(answer["observed_sitting_dates"], ["2026-11-20", "2026-11-24"])
        topic = answer["topics"][0]
        self.assertEqual(topic["active_sitting_dates"], ["2026-11-20"])
        self.assertEqual(topic["signed_in_member"]["total"], 0)
        self.assertEqual(topic["other_contributions"]["total"], 1)

    def test_empty_capture_and_invalid_windows(self):
        answer = briefing(self.access, 3966, self.portfolio, through="2026-11-10")
        self.assertEqual(answer["observed_sitting_dates"], [])
        self.assertEqual(answer["topics"], [])
        with self.assertRaises(ValueError):
            briefing(self.access, 3966, self.portfolio, start="2026-11-25", through="2026-11-24")
        with self.assertRaises(ValueError):
            briefing(self.access, 3966, self.portfolio, through="20261124")
