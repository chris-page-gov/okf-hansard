"""Stateless JSON responses for the MCP Streamable HTTP transport."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json

from briefing_auth import AuthFailure, METADATA_PATH
from mcp_protocol import PROTOCOL, header_error, request_version


def serve(port, dispatch, authorizer=None):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(15)
            super().setup()

        def log_message(self, message, *args):
            if authorizer is None:
                super().log_message(message, *args)

        def reply(self, status, payload=None, challenge=None):
            body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else b""
            self.send_response(status)
            if body:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if challenge:
                self.send_header("WWW-Authenticate", challenge)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/mcp":
                self.reply(404)
                return
            if not self.valid_origin():
                self.reply(403)
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415)
                return
            account = None
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    self.reply(413)
                    return
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                    raise ValueError("Invalid JSON-RPC envelope")
                if authorizer:
                    headers = self.headers.get_all("Authorization", [])
                    if len(headers) > 1:
                        raise AuthFailure(401, "invalid_token")
                    account = authorizer.account(headers[0] if headers else None)
                problem = header_error(request, self.headers)
                if problem:
                    self.reply(400, problem)
                    return
                response = dispatch(request, account) if authorizer else dispatch(request)
            except AuthFailure as exc:
                challenge = authorizer.challenge(exc.error) if exc.status == 401 or exc.error else None
                self.reply(exc.status, challenge=challenge)
                return
            except (ValueError, TypeError, AttributeError):
                self.reply(400, {"jsonrpc": "2.0", "id": None,
                                 "error": {"code": -32600, "message": "Invalid MCP request"}})
                return
            if response is None:
                self.reply(202)
                return
            code = response.get("error", {}).get("code")
            status = ({-32600: 400, -32601: 404, -32022: 400}.get(code, 200)
                      if request_version(request) == PROTOCOL else 200)
            self.reply(status, response)

        def valid_origin(self):
            port = self.server.server_port
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            origins = {"http://" + host for host in hosts}
            if authorizer:
                origins.add(authorizer.public_origin)
            origin = self.headers.get("Origin")
            return self.headers.get("Host") in hosts and (not origin or origin in origins)

        def do_GET(self):
            if (self.path == "/mcp" or self.path == METADATA_PATH) and not self.valid_origin():
                self.reply(403)
                return
            if authorizer and self.path == METADATA_PATH:
                self.reply(200, authorizer.metadata())
                return
            self.reply(405 if self.path == "/mcp" else 404)

        def do_DELETE(self):
            if self.path == "/mcp" and not self.valid_origin():
                self.reply(403)
                return
            self.reply(405 if self.path == "/mcp" else 404)

    with HTTPServer(("127.0.0.1", port), Handler) as server:
        server.serve_forever()
