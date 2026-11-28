"""Check skill integrity, fixed URI access and MCP version routing."""

from email.message import Message
import unittest

from capture import sha
from mcp_protocol import (CAPABILITIES_KEY, LEGACY, PROTOCOL, VERSION_KEY, header_error)
from mcp_server import rpc
from mcp_skills import EXTENSION, NAME, URI


class MCPSkillsTests(unittest.TestCase):
    def request(self, method, *, version=PROTOCOL, **params):
        return {"jsonrpc": "2.0", "id": 7, "method": method, "params": {
            "_meta": {VERSION_KEY: version, CAPABILITIES_KEY: {}},
            **params,
        }}

    def call(self, method, **params):
        return rpc(self.request(method, **params), None, None, None)

    def test_discovery_and_complete_manifest_with_exact_bytes(self):
        result = self.call("server/discover")["result"]
        self.assertEqual("complete", result["resultType"])
        self.assertEqual([PROTOCOL, *LEGACY], result["supportedVersions"])
        self.assertEqual({}, result["capabilities"]["extensions"][EXTENSION])
        self.assertIn("resources", result["capabilities"])
        skill, = self.call("skills/list")["result"]["skills"]
        self.assertEqual(skill, self.call("skills/get", uri=URI)["result"]["skill"])
        self.assertEqual(NAME, skill["frontmatter"]["name"])
        listed = self.call("resources/list")["result"]["resources"]
        self.assertEqual({row["uri"] for row in listed}, {row["uri"] for row in skill["resources"]})
        for entry in skill["resources"]:
            received = self.call("resources/read", uri=entry["uri"])["result"]
            content, = received["contents"]
            raw = content["text"].encode("utf-8")
            self.assertEqual((entry["size"], entry["digest"]), (len(raw), "sha256:" + sha(raw)))
            self.assertEqual("public", received["cacheScope"])

    def test_unknown_files_and_protocol_metadata_are_rejected(self):
        for uri in ("file:///etc/passwd", "skill://read-okf-plus/../AGENTS.md", URI + "?x=1", []):
            with self.subTest(uri=uri):
                self.assertEqual(-32602, self.call("resources/read", uri=uri)["error"]["code"])
        self.assertEqual(-32602, self.call("skills/get", uri="skill://example/SKILL.md")["error"]["code"])
        self.assertEqual(-32602, self.call("skills/list", _meta={VERSION_KEY: PROTOCOL})["error"]["code"])
        self.assertEqual(-32022, self.call("skills/list", version="1900-01-01")["error"]["code"])

    def test_same_public_skill_is_readable_as_an_ordinary_legacy_resource(self):
        init = rpc({"id": 1, "method": "initialize", "params": {"protocolVersion": LEGACY[0]}}, None, None, None)
        self.assertEqual(LEGACY[0], init["result"]["protocolVersion"])
        self.assertIn("resources", init["result"]["capabilities"])
        self.assertNotIn("extensions", init["result"]["capabilities"])
        legacy = rpc({"id": 2, "method": "resources/read", "params": {"uri": URI}}, None, None, None)["result"]
        self.assertEqual(self.call("resources/read", uri=URI)["result"]["contents"], legacy["contents"])

    def test_personal_tool_catalogues_are_private(self):
        private = rpc(self.request("tools/list"), None, None, None, access=object(), account=object())["result"]
        public = rpc(self.request("tools/list"), None, None, None, access=object())["result"]
        self.assertIn("hansard_my_briefing", {row["name"] for row in private["tools"]})
        self.assertNotIn("hansard_my_briefing", {row["name"] for row in public["tools"]})
        self.assertEqual(("private", 0), (private["cacheScope"], private["ttlMs"]))

    def test_http_requires_mirrored_modern_routing(self):
        headers = Message()
        headers["Mcp-Method"] = "resources/read"
        headers["MCP-Protocol-Version"] = PROTOCOL
        request = self.request("resources/read", uri=URI)
        self.assertEqual(-32020, header_error(request, headers)["error"]["code"])
        headers["Mcp-Name"] = URI
        self.assertIsNone(header_error(request, headers))
        self.assertEqual(-32020, header_error(self.request("resources/read", uri=URI + "/other"), headers)["error"]["code"])
        headers.replace_header("MCP-Protocol-Version", "1900-01-01")
        unsupported = header_error(self.request("resources/read", uri=URI, version="1900-01-01"), headers)
        self.assertEqual(-32022, unsupported["error"]["code"])
        self.assertEqual(PROTOCOL, unsupported["error"]["data"]["supported"][0])
