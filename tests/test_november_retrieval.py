"""Replay the published November scores using only the bounded, public evidence."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import runpy
import unittest
from urllib.parse import urlsplit


EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "november-retrieval"
METHODS = ("FTS5", "FTS5 + E5")


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


class NovemberRetrievalTests(unittest.TestCase):
    def test_frozen_trials(self):
        suites = [
            (EXPERIMENT, 21, (17, 17)),
            (EXPERIMENT / "voice", 8, (3, 5)),
        ]
        for directory, count, passes in suites:
            with self.subTest(suite=directory.name):
                self.check_suite(directory, count, passes)

    def check_suite(self, directory, count, passes):
        receipt = read(directory / "verification.json")
        index = receipt.get("index") or read(directory / "index-receipt.json")
        protocol = read(directory / "protocol.json")
        self.assertEqual(digest(directory / "queries.json"), index["query_sha256"])
        self.assertEqual(digest(directory / "protocol.json"), index["protocol_sha256"])
        self.assertEqual(digest(directory / "questions.json"), protocol["question_sha256"])
        self.assertEqual(index["corpus_sha256"], read(EXPERIMENT / "capture.json")["digest"])
        for name, field in (("answers.jsonl", "answers_sha256"), ("scores.json", "scores_sha256"),
                            ("retrieved-passages.json", "rankings_sha256")):
            self.assertEqual(digest(directory / name), receipt[field])
        for name, expected in receipt.get("inputs", {}).items():
            self.assertEqual(digest(directory / name), expected)
        for stage in ("index_network", "answer_network"):
            self.assertEqual(receipt[stage]["sealed_sink_requests"], 0)
            self.assertEqual(receipt[stage]["sink_trace_sha256"], digest(EXPERIMENT / "sink-trace.json"))

        cases = read(directory / "questions.json")
        by_id = {case["id"]: case for case in cases}
        self.assertEqual(len(cases), count)
        expected_keys = {(case["id"], method) for case in cases for method in METHODS}
        answers = [json.loads(line) for line in (directory / "answers.jsonl").read_bytes().splitlines()]
        rankings = read(directory / "retrieved-passages.json")
        for rows in (answers, rankings):
            self.assertEqual(len(rows), count * len(METHODS))
            self.assertEqual({(r["id"], r["method"]) for r in rows}, expected_keys)

        ranked = {(r["id"], r["method"]): r for r in rankings}
        evaluate = runpy.run_path(str(directory / "score.py"))["evaluate"]
        replayed = []
        for answer in answers:
            case = by_id[answer["id"]]
            trial = ranked[answer["id"], answer["method"]]
            passages = trial["passages"]
            self.assertLessEqual(len(passages), protocol["public_documents"])
            self.assertEqual(len({p["route"] for p in passages}), len(passages))
            evidence = []
            for rank, passage in enumerate(passages, 1):
                self.assertEqual(passage["rank"], rank)
                url = urlsplit(passage["url"])
                self.assertEqual((url.scheme, url.netloc), ("https", "hansard.parliament.uk"))
                self.assertTrue(url.fragment.startswith("contribution-"))
                evidence.append(f"# R{rank} {passage['title']} | {passage['speaker']} | "
                                f"{passage['day']} {passage['house']}\n\n{passage['body']}\nSource: {passage['url']}")
            data = "\n\n".join(evidence).encode()
            self.assertEqual(sha256(data).hexdigest(), answer["evidence_sha256"])
            self.assertEqual(len(data), answer["bytes"])
            self.assertLessEqual(len(data), protocol["wrapper_byte_limit"])
            replayed.append(evaluate(case, trial, answer))

        self.assertEqual(replayed, read(directory / "scores.json"))
        totals = Counter(row["method"] for row in replayed if row["strict"])
        self.assertEqual(tuple(totals[method] for method in METHODS), passes)


if __name__ == "__main__":
    unittest.main()
