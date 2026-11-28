"""Reproduce the Android SEND attribution failure against the normal producer."""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from build import build
from capture import dump

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/send-reform-official-api.json"
LEDGER = ROOT / "evaluation/runs/2026-11-28/evidence.json"
PREDICATE = "urn:okf:hansard:vocab:answeredBy"


class ReviewedReplyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = json.loads(FIXTURE.read_bytes())
        self.ledger = json.loads(LEDGER.read_bytes())
        self.schema = self.root / "profiles/bundle-wiki/v1/semantic-assertion.schema.json"
        self.schema.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "profile/semantic-assertion.schema.json", self.schema)
        self.snapshot = self.root / "capture"
        self.snapshot.mkdir()

    def build_fixture(self, items):
        # Only the endpoint fields are source excerpts. This small envelope and
        # retrieval timestamp are fixture metadata. Its digest covers its actual bytes.
        tree = {"Overview": {"ExtId": self.data["debate_id"], "Title": self.data["title"]},
                "Items": items, "ChildDebates": []}
        source_path = self.snapshot / "debate.json"
        dump(source_path, tree)
        self.source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        source = {"path": "debate.json", "url": self.data["source_url"], "sha256": self.source_hash,
                  "retrieved_at": "2026-11-28T00:00:00Z", "section": "Debate"}
        day = self.data["date"]
        sitting = {"date": day, "house": self.data["house"], "roots": [source], "errors": []}
        dump(self.snapshot / "manifest.json", {"finished_at": source["retrieved_at"], "directories": [],
                                               "directory_errors": [], "sittings": [sitting]})
        out = self.root / "release"
        with contextlib.redirect_stdout(io.StringIO()):
            build(self.snapshot, None, out, ROOT / "profile/vocabulary.yaml", day, day, self.root)
        corpus = json.loads((out / "okf-bundle.json").read_bytes())["corpora"]["hansard"]
        replies = [row for row in corpus["relationships"] if row["predicate"] == PREDICATE]
        semantic = [json.loads(line[2:]) for line in (out / "okf-bundle.yamlld").read_text().splitlines()[3:]]
        assertions = {row["@id"]: row for row in semantic if row.get("predicate", {}).get("@id") == PREDICATE}
        self.assertEqual({row["id"] for row in replies}, set(assertions))
        pairs = {}
        for row in replies:
            sem = assertions[row["id"]]
            self.assertEqual((sem["source_route"], sem["target_route"]), (row["source"], row["target"]))
            self.assertEqual(sem["evidence"], row["evidence"])
            endpoints = tuple(corpus["nodes"][row[side]]["url"] for side in ("source", "target"))
            pairs[endpoints] = row["evidence"]
        self.assertEqual(len(pairs), len(replies))
        return pairs

    def test_both_reviewed_pairs_and_endpoint_provenance(self):
        pairs = self.build_fixture(self.data["items"])
        self.assertEqual(len(pairs), 2)
        for q, a in (("Q0", "R0"), ("Q", "R")):
            urls = (self.ledger[q]["url"], self.ledger[a]["url"])
            points = pairs[urls]
            for role, key, ev in zip(("question", "answer"), (q, a), points, strict=True):
                pin = self.ledger[key]
                index = pin["item_index"]
                item = self.data["items"][index]
                self.assertEqual(item["ExternalId"], pin["url"].split("#contribution-")[1])
                self.assertEqual(item["ItemId"], pin["item_id"])
                self.assertEqual(hashlib.sha256(item["Value"].encode()).hexdigest(), pin["source_value_sha256"])
                self.assertEqual(ev["source_value_sha256"], pin["source_value_sha256"])
                self.assertEqual(ev["field_provenance"], role)
                self.assertEqual(ev["url"], pin["url"])
                self.assertEqual(ev["resource"], pin["source_api"])
                self.assertEqual(ev["source_field"], f"/Items/{index}/Value")
                self.assertEqual(ev["source_artifact"], "debate.json")
                self.assertEqual(ev["source_sha256"], self.source_hash)
        self.assertNotIn((self.ledger["Q"]["url"], self.ledger["R0"]["url"]), pairs)

    def test_three_record_retrieval_cannot_substitute_the_earlier_reply(self):
        pairs = self.build_fixture(self.data["items"][:3])
        self.assertEqual(set(pairs), {(self.ledger["Q0"]["url"], self.ledger["R0"]["url"])})

    def test_registering_the_opening_reply_for_the_appeals_question_is_rejected(self):
        reviews = json.loads((ROOT / "profile/reviewed-replies.json").read_bytes())
        opening, supplementary = reviews[0]["pairs"]
        supplementary["answer"] = opening["answer"]
        incorrect = self.root / "incorrect-replies.json"
        dump(incorrect, reviews)
        with patch("build.REVIEWED_REPLIES", incorrect), self.assertRaisesRegex(ValueError, "reply order"):
            self.build_fixture(self.data["items"])

    def test_changed_endpoint_needs_review(self):
        for index in range(4):
            for field, new_value in (("Value", "Corrected text"), ("MemberId", 1)):
                with self.subTest(index=index, field=field):
                    items = copy.deepcopy(self.data["items"])
                    items[index][field] = new_value
                    with self.assertRaisesRegex(ValueError, "needs review"):
                        self.build_fixture(items)

    def test_reply_before_its_question_is_rejected(self):
        items = list(self.data["items"])
        items[2], items[3] = items[3], items[2]
        with self.assertRaisesRegex(ValueError, "reply order"):
            self.build_fixture(items)
