from collections import Counter
from pathlib import Path
import unittest
from unittest.mock import patch

from acquire import CONTRACT, read
from decide import DECISION_CONTRACT, UnixHTTPConnection, assessment, score, tasks, text_fields


class DecisionTests(unittest.TestCase):
    def test_original_questions_and_balanced_controls(self):
        contract, decision = read(CONTRACT), read(DECISION_CONTRACT)
        rows = tasks(contract, decision)
        self.assertEqual(19, len(rows))
        originals = rows[:10]
        for case in contract["cases"]:
            matching = [row for row in originals if row[1] == case["id"]]
            self.assertEqual([case["question"]] * 2, [row[3] for row in matching])
            self.assertEqual([case["status"]] * 2, [row[4] for row in matching])
            self.assertEqual(decision["orders"], [row[5] for row in matching])
        self.assertEqual({"supported": 3, "insufficient": 3, "denied": 3}, dict(Counter(row[4] for row in rows[10:])))

    def test_probability_and_token_validation(self):
        options = ["supported", "insufficient", "denied"]
        result = {"answers": {"status": {"type": "choice", "choice": "supported",
                                        "probabilities": dict(zip(options, (0.7, 0.2, 0.1)))}},
                  "usage": {"input_tokens": 2048, "output_tokens": 0}}
        self.assertEqual(("supported", result["answers"]["status"]["probabilities"], 2048),
                         assessment(result, options, 2048))
        with self.assertRaisesRegex(ValueError, "input budget"):
            assessment(result, options, 2047)
        result["usage"]["output_tokens"] = 1
        with self.assertRaisesRegex(ValueError, "generated text"):
            assessment(result, options, 2048)
        result["answers"]["status"]["choice"] = "denied"
        with self.assertRaisesRegex(ValueError, "distribution"):
            assessment(result, options, 2048)

    def test_report_separates_policy_errors_and_choice_order_flips(self):
        rows = [
            {"arm": "okf", "section": "original", "case": "public", "expected": "denied",
             "predicted": prediction, "correct": prediction == "denied"}
            for prediction in ("denied", "supported")
        ]
        summary = score(rows)["original"]["okf"]
        self.assertEqual((1, 2, 1, 1), tuple(summary[key] for key in ("correct", "total", "unsafe_support", "order_flips")))
        self.assertEqual({"denied": 1, "supported": 1}, summary["confusion"]["denied"])

    def test_local_http_uses_a_string_socket_address(self):
        address = Path("/private/tmp/reference-test.sock")
        with patch("decide.socket.socket") as connection:
            UnixHTTPConnection(address).connect()
            connection.return_value.connect.assert_called_once_with(str(address))

    def test_numeric_outputs_are_not_mistaken_for_textual_disclosures(self):
        self.assertEqual(["supported"], list(text_fields({"choice": "supported", "probabilities": [0.38417]})))
