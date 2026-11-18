"""Regression checks for the deterministic Hansard pilot."""

from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
import unittest

from archive import Collector, StopRun, open_database
from model import Entity, Matcher, plain, read_sittings
from people import active_on
from query import Index, view_for
from render_view import render


class ModelTests(unittest.TestCase):
    def test_ambiguous_names_do_not_resolve(self):
        entities = {
            "one": Entity("one", "MP", "Alex Example", None),
            "two": Entity("two", "Peer", "Alex Example", None),
        }
        self.assertEqual([], list(Matcher(entities).find("Alex Example made a speech.")))

    def test_acronym_and_exact_source_span(self):
        entities = {"us": Entity("us", "Country", "United States", None, ["US"])}
        text = plain("<p>That helps us.</p><p>The US contributed.</p>")
        self.assertEqual([("us", {"start": 19, "end": 21, "exact": "US"})], list(Matcher(entities).find(text)))

    def test_constituency_alias_requires_a_reference_for_one_word(self):
        matcher = Matcher({"seat": Entity("seat", "Constituency", "Chorley", None)})
        self.assertEqual([], list(matcher.find("I visited Chorley.")))
        hit, = list(matcher.find("The Member for Chorley spoke."))
        self.assertEqual("seat", hit[0])

    def test_repeated_public_section_ids_preserve_distinct_sections(self):
        def section(number, key, title):
            return {"Overview": {"Id": number, "ExtId": key, "Title": title}, "Items": [], "ChildDebates": []}

        first = section(1, "shared", "A distinct sitting section")
        second = section(2, "shared", "Another sitting section")
        root = section(3, "root", "Chamber")
        root["ChildDebates"] = [first, second, first]
        entry = {"date": "2026-11-17", "house": "Commons", "roots": [{"section": "Debate"}]}
        parts, _, _, metrics = read_sittings(None, {"sittings": [entry]}, "2026-11-16", "2026-11-17",
                                               loader=lambda _root, _source: root)
        self.assertEqual(3, len(parts))
        self.assertEqual(1, metrics[entry["date"], entry["house"]]["shared_section_public_ids"])
        self.assertEqual(1, metrics[entry["date"], entry["house"]]["repeated_section_copies"])

    def test_closed_appointment_dates(self):
        self.assertTrue(active_on("2026-07-20", None, "2026-11-17"))
        self.assertFalse(active_on("2026-07-20", "2026-11-17", "2026-11-17"))
        self.assertFalse(active_on(None, None, "2026-11-17"))

    def test_deadline_and_profile_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with open_database(root / "index.sqlite", b"profile-one"):
                pass
            with self.assertRaises(ValueError):
                open_database(root / "index.sqlite", b"profile-two")
            collector = Collector(datetime(2000, 1, 1, tzinfo=UTC), root / "pause", .66)
            with self.assertRaises(StopRun):
                collector.check()


class QueryTests(unittest.TestCase):
    def test_trace_context_and_accessible_view(self):
        path = Path("releases/current")
        if not path.exists():
            self.skipTest("A built pilot release is required.")
        index = Index(path)
        anchors = index.history["contributions"]
        route = next(key for key, row in anchors.items() if "palantir" in row["entities"])
        answer = index.track(route, "palantir", limit=2)
        self.assertGreaterEqual(answer["total"], len(answer["items"]))
        self.assertTrue(all(row["date"] <= answer["anchor"]["date"] for row in answer["items"]))
        with self.assertRaises(ValueError):
            index.track(route, "palantir", expected_context="0" * 64)
        answer["view"] = view_for(answer)
        first = render(answer)
        self.assertIn('<html lang="en-GB">', first)
        self.assertIn('scope="col"', first)
        answer["view"]["rows"][0]["count"] += 1
        with self.assertRaises(ValueError):
            render(answer)


if __name__ == "__main__":
    unittest.main()
