"""Regression checks for the deterministic Hansard pilot."""

from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
import unittest

from archive import Collector, StopRun, open_database
from build import hansard_proceedings
from build_explorer_graph import HUB_MINIMUM_INCIDENT_ASSERTIONS, ordered_relationships
from demo import record, write_timeline
from model import Entity, Matcher, plain, read_sittings
from people import active_on
from query import Index, view_for
from render_view import render


class ModelTests(unittest.TestCase):
    def test_demo_timeline_copies_exact_contribution_evidence_and_keeps_unmatched_dates(self):
        day = "2026-11-17"
        section = "section/debate.md"
        debate = f"https://hansard.parliament.uk/Commons/{day}/debates/example"
        url = f"{debate}#contribution-example"
        marker = {"value": f"{day}T19:14:00", "source_item": 3, "source_field": "/Items/2/Value"}
        proceedings = {"section_id": section, "source_item": 4, "contribution_time": f"{day}T19:15:00"}
        summary = {"source": url, "text": "The speaker asked for a review."}
        source_nodes = {
            section: {"url": debate, "hansard_proceedings": {"markers": [marker], "source_api": "https://api.example.test"}},
            "contribution/speech.md": {"url": url, "hansard_proceedings": proceedings, "hansard_summary": summary},
        }
        rows = [record(day, "Commons", "Example speech", "Worked example", url),
                record(day, "Commons", "Example debate", "Debate record", debate)]
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            write_timeline(destination, [{"title": "Example", "rows": rows}], {day: 1}, source_nodes)
            nodes = json.loads((destination / "demo-timeline.json").read_bytes())["corpora"]["hansard"]["nodes"]
        by_url = {node.get("url"): node for node in nodes.values()}
        self.assertEqual(by_url[url]["hansard_proceedings"]["contribution_time"], f"{day}T19:15:00")
        self.assertEqual(by_url[url]["hansard_proceedings"]["markers"], [marker])
        self.assertEqual(by_url[url]["hansard_summary"], summary)
        self.assertNotIn("hansard_proceedings", by_url[debate])
        self.assertEqual(by_url[debate]["timestamp"], day)

    def test_relationship_shards_keep_a_hub_together_in_stable_order(self):
        hub = "entity/hub"
        edges = [
            {"source": f"contribution/{index:03d}", "target": hub, "id": f"hub-{index:03d}"}
            for index in range(HUB_MINIMUM_INCIDENT_ASSERTIONS)
        ]
        ordinary = {"source": "contribution/000", "target": "entity/other", "id": "ordinary"}
        ordered = ordered_relationships([ordinary, *reversed(edges)])
        self.assertEqual([*edges, ordinary], ordered)

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

    def test_timecode_and_marker_keep_different_source_pointers(self):
        tree = {
            "Overview": {"Id": 1, "ExtId": "debate", "Title": "Test debate"},
            "Items": [
                {"ItemType": "Timestamp", "Value": "19:14:00", "Timecode": None},
                {"ItemType": "Contribution", "ExternalId": "aa", "Value": "A timed contribution.",
                 "Timecode": "2026-11-17T19:15:00"},
                {"ItemType": "Contribution", "ExternalId": "bb", "Value": "An untimed contribution."},
            ],
            "ChildDebates": [],
        }
        entry = {"date": "2026-11-17", "house": "Commons",
                 "roots": [{"section": "Debate", "url": "https://hansard-api.parliament.uk/fixture"}]}
        parts, records, _, _ = read_sittings(None, {"sittings": [entry]}, "2026-11-16", "2026-11-17",
                                             loader=lambda _root, _source: tree)
        section_route, part = next(iter(parts.items()))
        timed, untimed = [hansard_proceedings(part, section_route, row) for row in records.values()]
        self.assertEqual("2026-11-17T19:15:00", timed["contribution_time"])
        self.assertEqual("/Items/1/Timecode", timed["source_field"])
        self.assertEqual(2, timed["source_item"])
        self.assertEqual(3, untimed["source_item"])
        self.assertNotIn("contribution_time", untimed)
        self.assertEqual([{"value": "2026-11-17T19:14:00", "source_item": 1,
                           "source_field": "/Items/0/Value"}], hansard_proceedings(part, section_route)["markers"])

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
