"""Exercise bounded HTTP admission and authenticated response isolation."""

from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
import json
import socket
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

from briefing_auth import AuthFailure, Authorizer, SCOPE
from mcp_http import create_server
from mcp_protocol import CAPABILITIES_KEY, PROTOCOL, VERSION_KEY
from mcp_server import BRIEFING_TOOL, rpc


def request():
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": BRIEFING_TOOL["name"], "arguments": {}}}


class MCPHTTPTests(unittest.TestCase):
    def setUp(self):
        settings = {
            "resource": "https://briefings.example.org/mcp",
            "issuer": "https://login.example.org/realm",
            "introspection_endpoint": "https://login.example.org/introspect",
            "introspection_client_id": "test-connector",
            "bindings": {
                "first-user": {"member_id": 101, "portfolio": [{"key": "topic-one", "from": "2026-01-01"}]},
                "second-user": {"member_id": 202, "portfolio": [{"key": "topic-two", "from": "2026-02-01"}]},
            },
        }
        self.authorizer = Authorizer(settings, "test-secret")
        expiry = int((datetime.now(UTC) + timedelta(minutes=2)).timestamp())
        self.authorizer.introspect = Mock(side_effect=lambda token: {
            "active": True, "aud": [self.authorizer.resource], "scope": SCOPE,
            "exp": expiry, "iss": self.authorizer.issuer,
            "sub": {"first-token": "first-user", "second-token": "second-user"}.get(token, "unknown-user"),
        })
        self.access = object()
        self.server = None
        self.server_thread = None

    def start_server(self, dispatch, *, authorizer=None, max_active_requests=8):
        self.server = create_server(0, dispatch, authorizer,
                                    max_active_requests=max_active_requests)
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.addCleanup(self.stop_server)
        return self.server.server_port

    def stop_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server_thread.join(timeout=2)
            self.server = None

    def post(self, port, token=None, *, modern=False):
        connection = HTTPConnection("127.0.0.1", port, timeout=3)
        headers = {"Content-Type": "application/json"}
        body = request()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if modern:
            body["params"]["_meta"] = {VERSION_KEY: PROTOCOL, CAPABILITIES_KEY: {}}
            headers.update({"MCP-Protocol-Version": PROTOCOL, "Mcp-Method": body["method"],
                            "Mcp-Name": BRIEFING_TOOL["name"]})
        connection.request("POST", "/mcp", json.dumps(body), headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_same_briefing_arguments_are_private_per_authenticated_identity(self):
        def dispatch(req, account):
            return rpc(req, None, None, None, self.access, account)

        port = self.start_server(dispatch, authorizer=self.authorizer)
        briefing = Mock(side_effect=lambda access, member_id, portfolio, **kwargs: {
            "member": member_id, "topic": portfolio[0]["key"], "arguments": kwargs})
        with patch("briefings.briefing", briefing):
            first_status, first_headers, first_body = self.post(port, "first-token", modern=True)
            second_status, second_headers, second_body = self.post(port, "second-token", modern=True)
            denied_status, denied_headers, denied_body = self.post(port)

        self.assertEqual((first_status, second_status, denied_status), (200, 200, 401))
        for headers in (first_headers, second_headers, denied_headers):
            self.assertEqual(headers["Cache-Control"], "private, no-store")
        first = json.loads(first_body)["result"]
        second = json.loads(second_body)["result"]
        self.assertEqual(first["structuredContent"]["member"], 101)
        self.assertEqual(second["structuredContent"]["member"], 202)
        self.assertNotEqual(first["structuredContent"]["topic"], second["structuredContent"]["topic"])
        self.assertNotIn("ttlMs", first)
        self.assertNotIn("cacheScope", first)
        self.assertEqual(first["resultType"], "complete")
        self.assertEqual(briefing.call_count, 2)
        self.assertEqual(denied_body, b"")

    def test_unavailable_verified_snapshot_returns_private_retryable_transport_status(self):
        dispatch = Mock(side_effect=AuthFailure(503))
        port = self.start_server(dispatch, authorizer=self.authorizer)
        status, headers, body = self.post(port, "first-token")
        self.assertEqual(status, 503)
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        self.assertEqual(body, b"")

    def test_admission_limit_returns_bounded_no_store_busy_response(self):
        entered, release = Event(), Event()

        def dispatch(req, account):
            entered.set()
            release.wait(timeout=2)
            return {"jsonrpc": "2.0", "id": req["id"], "result": {}}

        port = self.start_server(dispatch, authorizer=self.authorizer, max_active_requests=1)
        first_result = []
        first = Thread(target=lambda: first_result.append(self.post(port, "first-token")))
        first.start()
        self.assertTrue(entered.wait(timeout=2))
        try:
            status, headers, _ = self.post(port, "second-token")
        finally:
            release.set()
        first.join(timeout=3)

        self.assertEqual(status, 503)
        self.assertEqual(headers["Cache-Control"], "private, no-store")
        self.assertEqual(first_result[0][0], 200)

    def test_missing_ambiguous_and_incomplete_lengths_are_rejected_before_dispatch(self):
        dispatch = Mock(return_value={"jsonrpc": "2.0", "id": 1, "result": {}})
        port = self.start_server(dispatch)

        connection = HTTPConnection("127.0.0.1", port, timeout=3)
        connection.putrequest("POST", "/mcp")
        connection.putheader("Content-Type", "application/json")
        connection.endheaders()
        missing = connection.getresponse()
        self.assertEqual(missing.status, 411)
        self.assertEqual(missing.getheader("Cache-Control"), "no-store")
        missing.read()
        connection.close()

        connection = HTTPConnection("127.0.0.1", port, timeout=3)
        connection.putrequest("POST", "/mcp")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "2")
        connection.putheader("Content-Length", "2")
        connection.endheaders()
        duplicate = connection.getresponse()
        self.assertEqual(duplicate.status, 400)
        duplicate.read()
        connection.close()

        with socket.create_connection(("127.0.0.1", port), timeout=3) as raw:
            raw.sendall(b"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:" + str(port).encode()
                        + b"\r\nContent-Type: application/json\r\nContent-Length: 10\r\n\r\n{}")
            raw.shutdown(socket.SHUT_WR)
            response = raw.recv(4096)
        self.assertIn(b"400 Bad Request", response)
        self.assertIn(b"Cache-Control: no-store", response)
        dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
