"""Stateless JSON responses for the MCP Streamable HTTP transport."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json


def serve(port, protocols, dispatch):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(15)
            super().setup()

        def reply(self, status, payload=None):
            body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else b""
            self.send_response(status)
            if body:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/mcp":
                self.reply(404)
                return
            port = self.server.server_port
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            origin = self.headers.get("Origin")
            if self.headers.get("Host") not in hosts or origin and origin not in {"http://" + host for host in hosts}:
                self.reply(403)
                return
            if self.headers.get("MCP-Protocol-Version", "2025-03-26") not in protocols:
                self.reply(400)
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 65536:
                    self.reply(413)
                    return
                request = json.loads(self.rfile.read(length))
                if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
                    raise ValueError("Invalid JSON-RPC envelope")
                response = dispatch(request)
            except (ValueError, TypeError, AttributeError):
                self.reply(400, {"jsonrpc": "2.0", "id": None,
                                 "error": {"code": -32600, "message": "Invalid MCP request"}})
                return
            self.reply(202 if response is None else 200, response)

        def do_GET(self):
            self.reply(405 if self.path == "/mcp" else 404)

        do_DELETE = do_GET

    with HTTPServer(("127.0.0.1", port), Handler) as server:
        server.serve_forever()
