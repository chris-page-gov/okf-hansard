"""Check the public contributor route and software licence assets."""

from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from build_pages import ROOT, index_page, stage_guides


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.ids = set()
        self.scripts = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if tag == "a":
            self.links.append(attributes["href"])
        if tag == "script":
            self.scripts += 1


class ContributorTourTests(unittest.TestCase):
    def test_tour_and_licences_are_staged_and_navigable_without_script(self):
        with TemporaryDirectory() as folder:
            site = Path(folder)
            stage_guides(site)
            tour = Links((site / "contributor-tour.html").read_text())
            self.assertEqual(0, tour.scripts)
            self.assertEqual(["#ask", "#retrieve", "#trace", "#verify", "#reuse"],
                             [link for link in tour.links if link.startswith("#")])
            self.assertTrue(all(link[1:] in tour.ids for link in tour.links if link.startswith("#")))
            self.assertIn("november/ask.html", tour.links)
            self.assertIn("licences.html", tour.links)
            licences = Links((site / "licences.html").read_text())
            for name in ("LICENSE", "NOTICE.md"):
                self.assertIn(name, licences.links)
                self.assertEqual((ROOT / name).read_bytes(), (site / name).read_bytes())

    def test_phone_finder_remains_the_first_landing_action(self):
        page = index_page({
            "week_contributions_by_day": {"2026-11-18": 2},
            "pilot_graph": {"assertions": 1, "visible_facet_declarations": 1},
            "archive": {"ranges": {"Commons": {"from": "2026-11-18"}}},
        }, "okf-bundle.yamlld", "contribution/example")
        links = Links(page).links
        self.assertEqual("november/ask.html", links[0])
        self.assertIn("contributor-tour.html", links)
        self.assertIn("licences.html", links)
