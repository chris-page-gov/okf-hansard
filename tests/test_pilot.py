"""Regression checks for the deterministic Hansard pilot."""

from datetime import UTC, date, datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from archive import Collector, StopRun, open_database
from backfill import Search, search_aliases, search_periods
from build import Graph, build, hansard_proceedings, runtime
from build_explorer_graph import HUB_MINIMUM_INCIDENT_ASSERTIONS, ordered_relationships
from capture import dump, sha
from demo import record, write_timeline
from model import Entity, Matcher, plain, read_sittings
from people import active_on
from query import Index, view_for
from render_view import render


class ModelTests(unittest.TestCase):
    def test_bounded_reader_preserves_required_relationship_evidence(self):
        graph = Graph()
        day = "2026-11-18"
        source = graph.node("contribution/sample.md", "Contribution", "Sample", date=day)
        target = graph.node("debate/sample.md", "Proceedings section", "Debate", date=day)
        url = "https://hansard-api.parliament.uk/fixture"
        receipt = {"url": url, "path": "fixture.json", "sha256": sha(b"sample"), "retrieved_at": day + "T20:00:00Z"}
        graph.edge(source, "partOf", target, receipt, url, "/ExternalId", "sample")
        compact = runtime(graph, {}, receipt["retrieved_at"], day, bounded_history=True)
        evidence = compact["corpora"]["hansard"]["relationships"][0]["evidence"][0]
        profile = Path(__file__).resolve().parents[1] / "profile/relationship-runtime-row.schema.json"
        required = json.loads(profile.read_bytes())["properties"]["evidence"]["items"]["required"]
        self.assertFalse(set(required) - set(evidence))

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

    def test_division_without_a_speech_keeps_its_section_and_ancestors(self):
        day = "2026-11-18"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def section(ext_id, title, items, children):
                return {"Overview": {"ExtId": ext_id, "Title": title, "Date": day + "T00:00:00"},
                        "Items": items, "ChildDebates": children}

            division = section("vote", "Deferred vote", [{"ItemType": "Division", "ItemId": 3}], [])
            division_group = section("deferred", "Deferred divisions", [], [division])
            chamber = section("root", "Commons Chamber",
                              [{"ItemType": "Contribution", "ItemId": 1, "Value": "A statement."}],
                              [division_group])
            dump(root / "chamber.json", chamber)
            source = {"section": "Debate", "path": "chamber.json", "url": "https://hansard-api.parliament.uk/",
                      "retrieved_at": day + "T20:00:00Z", "sha256": sha((root / "chamber.json").read_bytes())}
            dump(root / "manifest.json", {"finished_at": source["retrieved_at"], "directories": [],
                                         "directory_errors": [],
                                         "sittings": [{"date": day, "house": "Commons", "roots": [source], "errors": []}]})
            vocabulary = root / "vocabulary.yaml"
            vocabulary.write_text("entities: []\n", encoding="utf-8")
            output = root / "release"
            with patch("build.validate", side_effect=lambda graph, _explorer: len(graph.edges)):
                build(root, None, output, vocabulary, day, day, root)
            corpus = json.loads((output / "okf-bundle.json").read_bytes())["corpora"]["hansard"]
            edges = corpus["relationships"]
            vote, = (edge for edge in edges if edge["kind"] == "is division in")
            self.assertEqual("Deferred vote", corpus["nodes"][vote["target"]]["title"])
            self.assertEqual("/ChildDebates/0/ChildDebates/0/Items/0/ItemId", vote["evidence"][0]["source_field"])
            parent, = (edge for edge in edges
                       if edge["source"] == vote["target"] and edge["predicate"].endswith(":partOf"))
            self.assertEqual("Deferred divisions", corpus["nodes"][parent["target"]]["title"])

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
    def test_timed_out_search_is_split_and_cached(self):
        with tempfile.TemporaryDirectory() as temporary:
            service = Search(Path(temporary))
            calls = []

            def request(url):
                params = parse_qs(urlsplit(url).query)
                window = (params["startDate"][0], params["endDate"][0])
                calls.append(window)
                if window == ("2007-01-01", "2007-02-28"):
                    raise TimeoutError
                return {"TotalResultCount": 0, "Results": []}, {"url": url}

            args = ("entity", "alias", date(2007, 1, 1), date(2007, 2, 28), "Spoken", None, "profile")
            with patch.object(service, "request", side_effect=request):
                result = service.window(*args)
                self.assertEqual(service.window(*args), result)
            self.assertEqual(len(result["sources"]), 2)
            self.assertEqual(calls, [("2007-01-01", "2007-02-28"),
                                     ("2007-01-01", "2007-01-30"),
                                     ("2007-01-31", "2007-02-28")])

    def test_backfill_searches_dates_outside_the_common_archive(self):
        ranges = {"Commons": ("2007-11-08", "2026-10-29", 2788),
                  "Lords": ("2007-11-09", "2026-10-28", 2808)}
        self.assertEqual(search_periods("2026-11-02", ranges), [
            (date(2007, 1, 1), date(2007, 11, 8)),
            (date(2026, 10, 29), date(2026, 11, 1)),
        ])
        self.assertEqual(search_periods("2026-11-02", {}), [
            (date(2007, 1, 1), date(2026, 11, 1)),
        ])
        matcher = Matcher({"a": Entity("a", "Constituency", "Bicester", None, [], "fixture"),
                           "b": Entity("b", "Organisation", "Department of Health", None,
                                       ["The Department of Health", "DHSC"], "fixture")})
        self.assertEqual(search_aliases(matcher), {
            "a": ["constituency of bicester", "member for bicester", "constituency of the bicester"],
            "b": ["dhsc", "department of health"],
        })

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
