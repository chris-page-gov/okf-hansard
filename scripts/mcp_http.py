"""Bounded JSON responses for the MCP Streamable HTTP transport."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from threading import BoundedSemaphore
import time

from briefing_auth import AuthFailure, METADATA_PATH
from mcp_protocol import PROTOCOL, header_error, request_version

MAX_ACTIVE_REQUESTS = 8
REQUEST_TIMEOUT_SECONDS = 15
MAX_BODY_BYTES = 65536
LOGGER = logging.getLogger(__name__)


def create_server(port, dispatch, authorizer=None, *, max_active_requests=MAX_ACTIVE_REQUESTS):
    if type(max_active_requests) is not int or max_active_requests < 1:
        raise ValueError("The active request limit must be a positive integer")
    slots = BoundedSemaphore(max_active_requests)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(REQUEST_TIMEOUT_SECONDS)
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
            self.send_header("Cache-Control", "private, no-store" if authorizer else "no-store")
            if challenge:
                self.send_header("WWW-Authenticate", challenge)
            self.end_headers()
            self.wfile.write(body)

        def send_error(self, code, message=None, explain=None):
            # Keep parser errors on the same JSON/no-store policy as MCP replies.
            self.reply(code, {"error": "Invalid HTTP request"})

        def read_body(self, length):
            deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
            remaining = length
            chunks = []
            try:
                while remaining:
                    wait = deadline - time.monotonic()
                    if wait <= 0:
                        raise TimeoutError("Request body read timed out")
                    self.request.settimeout(wait)
                    chunk = self.rfile.read1(min(8192, remaining))
                    if not chunk:
                        raise ValueError("Incomplete request body")
                    chunks.append(chunk)
                    remaining -= len(chunk)
            finally:
                self.request.settimeout(REQUEST_TIMEOUT_SECONDS)
            return b"".join(chunks)

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
            request = None
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if self.headers.get_all("Transfer-Encoding", []):
                    self.reply(400, {"error": "Transfer-Encoding is not supported"})
                    return
                if not lengths:
                    self.reply(411, {"error": "Content-Length is required"})
                    return
                if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                    self.reply(400, {"error": "Invalid Content-Length"})
                    return
                length = int(lengths[0])
                if not 0 < length <= MAX_BODY_BYTES:
                    self.reply(413)
                    return
                try:
                    body = self.read_body(length)
                except TimeoutError:
                    self.reply(408, {"error": "Request body timed out"})
                    return
                except ValueError:
                    self.reply(400, {"error": "Incomplete request body"})
                    return
                request = json.loads(body)
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
                try:
                    response = dispatch(request, account) if authorizer else dispatch(request)
                except AuthFailure:
                    raise
                except Exception:
                    LOGGER.exception("MCP dispatch failed")
                    self.reply(500, {"jsonrpc": "2.0", "id": request.get("id"),
                                     "error": {"code": -32603, "message": "MCP request failed"}})
                    return
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

    class BoundedHTTPServer(ThreadingHTTPServer):
        daemon_threads = True

        def process_request(self, request, client_address):
            if not slots.acquire(blocking=False):
                try:
                    request.settimeout(0.2)
                    request.sendall(
                        b"HTTP/1.1 503 Service Unavailable\r\n"
                        + (b"Content-Length: 0\r\nCache-Control: private, no-store\r\n"
                           if authorizer else b"Content-Length: 0\r\nCache-Control: no-store\r\n")
                        + b"Connection: close\r\n\r\n"
                    )
                except OSError:
                    pass
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except Exception:
                slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                slots.release()

    return BoundedHTTPServer(("127.0.0.1", port), Handler)


def serve(port, dispatch, authorizer=None):
    with create_server(port, dispatch, authorizer) as server:
        server.serve_forever()
