import unittest
from unittest.mock import Mock

from mcp_server import rpc
from query import StaleHistory


class ToolDiagnosticTests(unittest.TestCase):
    def test_filesystem_details_do_not_reach_read_only_clients(self):
        access = Mock()
        access.describe.side_effect = FileNotFoundError("/fixture/private/details.json")
        with self.assertLogs("mcp_server", level="WARNING") as logs:
            response = rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": "hansard_describe_bundle"}},
                           None, None, None, access)
        result = response["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["status"], "unavailable")
        self.assertNotIn("/fixture/private", str(result))
        self.assertIn("FileNotFoundError", logs.output[0])

    def test_trace_and_mentions_can_request_a_new_page_after_refresh(self):
        access = Mock()
        access.mentions.side_effect = StaleHistory()
        response = rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "hansard_mentions", "arguments": {"key": "topic"}}},
                       None, None, None, access)
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(response["result"]["structuredContent"]["status"], "stale evidence page")
