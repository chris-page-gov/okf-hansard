from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
import unittest
from urllib.error import HTTPError

from http_policy import open_source


class HTTPPolicyTests(unittest.TestCase):
    def test_source_redirect_is_reported_without_opening_its_target(self):
        paths = []

        class Fixture(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                paths.append(self.path)
                self.send_response(302 if self.path == "/original" else 200)
                if self.path == "/original":
                    self.send_header("Location", "/new-location")
                self.end_headers()

        with HTTPServer(("127.0.0.1", 0), Fixture) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with self.assertRaises(HTTPError) as rejected:
                    open_source(f"http://127.0.0.1:{server.server_port}/original", timeout=3)
                self.assertEqual(rejected.exception.code, 302)
                rejected.exception.close()
            finally:
                server.shutdown()
                worker.join(timeout=3)
        self.assertEqual(paths, ["/original"])
