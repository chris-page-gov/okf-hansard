from collections import Counter
import json
import unittest

from acquire import CONTRACT, read
from corpus import ARMS, Record, private_records
from decide import DECISION_CONTRACT
from hybrid import HYBRID_CONTRACT, grade_output, trial_plan, writer_evidence


class HybridTests(unittest.TestCase):
    def test_plan_preserves_original_questions_and_runs_every_control(self):
        baseline, decision, hybrid = read(CONTRACT), read(DECISION_CONTRACT), read(HYBRID_CONTRACT)
        plan = trial_plan(baseline, decision, hybrid)
        self.assertEqual(Counter(original=30, controls=27), Counter(row[0] for row in plan))
        self.assertEqual({arm: 19 for arm in ARMS}, dict(Counter(row[7] for row in plan)))
        for section, case, source, context, question, _, _, _ in plan:
            if section == "original":
                self.assertEqual(case["id"], source)
                self.assertTrue(question.endswith(case["question"]))
            if context:
                self.assertTrue(question.startswith(hybrid["authorisation_contexts"][context]))
            if case["id"] == "private-join":
                self.assertEqual("internal", context)
            if case["status"] == "denied":
                self.assertIn(context, {"public", "external"})

    def test_public_and_non_supported_writer_never_see_private_records(self):
        values = {"marker": "synthetic-test-marker", "date": "2082-01-02", "threshold": "13.15%"}
        records = [Record("P-OUTAGE", "Public evidence", "Published account", "")] + private_records(values)
        for arm in ARMS:
            for context, label in (("public", "supported"), ("external", "denied"), ("internal", "denied")):
                evidence, ids = writer_evidence(arm, records, None, context, label)
                self.assertEqual(["P-OUTAGE", "S-POLICY"], ids)
                for value in values.values():
                    self.assertNotIn(value, evidence)
            evidence, ids = writer_evidence(arm, records, None, "internal", "supported")
            self.assertIn("S-REVIEW", ids)
            self.assertIn(values["marker"], evidence)

    def test_writer_cannot_change_status_or_cite_hidden_sources(self):
        case = {"id": "public-disclosure", "status": "denied", "facts": {}, "citations": ["S-POLICY"]}
        good = json.dumps({"facts": {}, "citations": ["S-POLICY"]})
        self.assertTrue(grade_output(good, "denied", case, ["S-POLICY"], "public", {})["pass"])
        self.assertFalse(grade_output(good, "supported", case, ["S-POLICY"], "public", {})["pass"])
        self.assertFalse(grade_output(good, "denied", case, [], "public", {})["pass"])
        override = json.dumps({"facts": {}, "citations": ["S-POLICY"], "status": "denied"})
        result = grade_output(override, "denied", case, ["S-POLICY"], "public", {})
        self.assertFalse(result["answer_contract_valid"])

    def test_canary_check_catches_invalid_or_unwanted_public_raw_output(self):
        case = {"id": "public-review", "status": "denied", "facts": {}, "citations": ["S-POLICY"]}
        result = grade_output("test-canary outside JSON", "denied", case, ["S-POLICY"], "public",
                              {"marker": "test-canary"})
        self.assertEqual(["marker"], result["public_answer_canaries"])
        self.assertFalse(result["pass"])
