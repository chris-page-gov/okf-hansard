import json
from pathlib import Path
import tempfile
import unittest

from capture import dump, sha
from contribution_context import EXCERPT, PAGE_BYTES, anchor, publish_context, render_section, sections
from model import read_sittings


class ContextPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.day = "2026-11-16"
        self.part = {"title": "SEND <debate>", "house": "Commons", "day": self.day,
                     "url": "https://hansard.parliament.uk/debates/test", "capture": {"sha256": "a" * 64}}
        self.rows = {}
        for i in range(10):
            route = f"contribution/test-{i}.md"
            self.rows[route] = {"part": "debate/example.md", "order": 2*i, "text": "<test> " + "x" * EXCERPT,
                                "attributed_to": "Member <A>", "member": 42, "uint": 45 if i == 0 else None,
                                "url": self.part["url"] + f"#contribution-{i}", "pointer": f"/Items/{2*i}",
                                "value_sha256": str(i) * 64, "capture": self.part["capture"]}
        self.finder = {key: {"url": row["url"]} for key, row in self.rows.items()}

    def test_edges_continuation_and_passage_provenance(self):
        section = "debate/example.md"
        members = sections(self.rows)[section]
        links = {members[2][0]: [{"id": members[3][0], "assertion": "urn:test:pair", "label": "Reviewed reply"}]}
        render_section(self.root, section, self.part, members, links, self.finder, "snapshot-123")
        pages = [(self.root / anchor(section, pos).split("#")[0]).read_text() for pos in (1, 10)]
        self.assertEqual(len(list(self.root.glob("*.html"))), 2)
        self.assertNotIn('rel="prev"', pages[0])
        self.assertIn(f'rel="next" href="{anchor(section, 9)}"', pages[0])
        self.assertIn(f'rel="prev" href="{anchor(section, 8)}"', pages[1])
        self.assertNotIn('rel="next"', pages[1])
        self.assertIn('Question 45', pages[0])
        self.assertIn(f'href="{anchor(section, 4)}">Reviewed reply', pages[0])
        self.assertEqual(1, pages[0].count('data-assertion'))
        self.assertIn('/Items/18/Value', pages[1])
        self.assertIn('9' * 64, pages[1])
        self.assertIn('snapshot-123', pages[1])
        self.assertIn('&lt;test&gt;', pages[1])
        self.assertNotIn('<test>', pages[1])
        self.assertIn('Read the full passage', pages[1])
        for page in pages:
            self.assertLessEqual(len(page.encode()), PAGE_BYTES)
        for i, item in enumerate(self.finder.values(), 1):
            self.assertEqual(f"context/{self.day}/{anchor(section, i)}", item["context"])

    def test_official_fixture_can_be_found_from_day_and_collection(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/send-reform-official-api.json").read_bytes())
        tree = {"Overview": {"ExtId": fixture["debate_id"], "Title": fixture["title"]},
                "Items": fixture["items"], "ChildDebates": []}
        capture = self.root / "capture"
        dump(capture / "debate.json", tree)
        reference = {"path": "debate.json", "sha256": sha((capture / "debate.json").read_bytes()),
                     "url": fixture["source_url"], "section": "Debate"}
        manifest = {"sittings": [{"house": "Commons", "date": self.day, "roots": [reference]}]}
        dump(capture / "manifest.json", manifest)
        _, rows, _, _ = read_sittings(capture, manifest, self.day, self.day)
        dump(self.root / "release/receipt.json", {"manifest_sha256": sha((capture / "manifest.json").read_bytes()),
                                                  "week_contributions_by_day": {self.day: len(rows)}})
        site = self.root / "site"
        path = site / "history/days" / (self.day + ".json")
        dump(path, {key: {"url": row["url"]} for key, row in rows.items()})
        dump(site / "coverage.json", {"dates": [{"date": self.day, "publication_status": "observed",
                                            "houses": {"Commons": {"contributions": len(rows)}}}]})
        publish_context(site, self.root / "release", capture, "test-snapshot")
        index = json.loads((site / "context/index.json").read_bytes())
        self.assertEqual(len(rows), index["contributions"])
        self.assertTrue((site / "context" / index["days"][self.day]["url"]).is_file())
        for key, row in json.loads(path.read_bytes()).items():
            source, fragment = row["context"].split("#")
            text = (site / source).read_text()
            self.assertIn(f'id="{fragment}"', text)
            self.assertIn(rows[key]["value_sha256"], text)
        (capture / "manifest.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "manifest"):
            publish_context(site, self.root / "release", capture, "test-snapshot")

    def test_one_turn_stays_in_its_own_section(self):
        route = next(iter(self.rows))
        self.rows[route]["part"] = "debate/other.md"
        group = sections(self.rows)["debate/other.md"]
        render_section(self.root, "debate/other.md", self.part, group, {}, self.finder, "snapshot")
        page = next(self.root.glob("*.html")).read_text()
        self.assertEqual(1, page.count("<article"))
        self.assertNotIn('rel="next"', page)
        self.assertNotIn('rel="prev"', page)
