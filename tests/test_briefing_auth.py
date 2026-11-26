"""Test that a briefing uses the verified OAuth subject and capture."""

from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from briefing_auth import AuthFailure, Authorizer, SCOPE
from mcp_server import rpc, verified_dispatch


def request(method, **params):
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


class BriefingAuthTests(unittest.TestCase):
    def setUp(self):
        self.auth = Authorizer({
            "resource": "https://briefings.example.org/mcp",
            "issuer": "https://login.example.org/realm",
            "introspection_endpoint": "https://login.example.org/introspect",
            "introspection_client_id": "example-connector",
            "bindings": {
                "first-user": {"member_id": 1, "portfolio": [{"key": "topic-one", "from": "2026-11-01"}]},
                "second-user": {"member_id": 2, "portfolio": [{"key": "topic-two", "from": "2026-11-02"}]},
            },
        }, "test-value")
        self.claims = {"active": True, "aud": [self.auth.resource],
                       "scope": SCOPE, "exp": int(time.time()) + 60, "sub": "first-user"}
        self.auth.introspect = Mock(return_value=self.claims)

    def test_subject_binding_uses_each_validated_token(self):
        first = self.auth.account("Bearer example-first")
        self.claims["sub"] = "second-user"
        second = self.auth.account("Bearer example-second")
        self.assertEqual(first.member_id, 1)
        self.assertEqual(second.member_id, 2)
        self.assertEqual(second.portfolio[0]["key"], "topic-two")

    def test_denies_missing_expired_unbound_wrong_audience_and_missing_scope(self):
        with self.assertRaises(AuthFailure) as no_header:
            self.auth.account(None)
        self.assertEqual(no_header.exception.status, 401)
        self.auth.introspect.assert_not_called()
        for change, status in [({"active": False}, 401), ({"exp": 1}, 401), ({"sub": "unknown"}, 403),
                               ({"aud": ["https://elsewhere.example/mcp"]}, 401), ({"scope": "public"}, 403),
                               ({"iss": "https://elsewhere.example"}, 401)]:
            with self.subTest(change=change):
                self.auth.introspect.return_value = {**self.claims, **change}
                with self.assertRaises(AuthFailure) as denied:
                    self.auth.account("Bearer sample-token")
                self.assertEqual(denied.exception.status, status)

    def test_private_tool_uses_only_authenticated_identity(self):
        account = self.auth.account("Bearer sample-token")
        access = object()
        public = rpc(request("tools/list"), None, None, None, access)
        self.assertNotIn("hansard_my_briefing", [tool["name"] for tool in public["result"]["tools"]])
        with patch("briefings.briefing", return_value={"topic": "verified"}) as briefing:
            rejected = rpc(request("tools/call", name="hansard_my_briefing", arguments={"member_id": 2}),
                           None, None, None, access, account)
            self.assertTrue(rejected["result"]["isError"])
            briefing.assert_not_called()
            accepted = rpc(request("tools/call", name="hansard_my_briefing", arguments={}),
                           None, None, None, access, account)
            self.assertFalse(accepted["result"]["isError"])
            briefing.assert_called_once_with(access, 1, account.portfolio)

    def test_reopens_verified_context_on_atomic_publication_change(self):
        with tempfile.TemporaryDirectory() as folder:
            pointer = Path(folder) / "publication.json"
            pointer.write_text("old")
            def load():
                snapshot = pointer.read_text()
                return None, None, None, SimpleNamespace(describe=lambda: {"snapshot": snapshot},
                                                        concepts=None, mentions=None, search=None)

            open_tools = Mock(side_effect=load)
            dispatch = verified_dispatch(pointer, open_tools)
            call = request("tools/call", name="hansard_describe_bundle", arguments={})
            self.assertEqual(dispatch(call, None)["result"]["structuredContent"]["snapshot"], "old")
            replacement = pointer.with_suffix(".tmp")
            replacement.write_text("new")
            replacement.replace(pointer)
            self.assertEqual(dispatch(call, None)["result"]["structuredContent"]["snapshot"], "new")
            self.assertEqual(open_tools.call_count, 2)
