"""Request metadata and HTTP routing for the two supported MCP protocol eras."""

from base64 import b64decode
from binascii import Error

from hansard_access import read
from mcp_skills import CONTRACT

MCP = read(CONTRACT)["mcp"]
PROTOCOL = MCP["revision"]
LEGACY = tuple(MCP["compatibility_revisions"])
PROTOCOLS = (PROTOCOL, *LEGACY)
VERSION_KEY = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES_KEY = "io.modelcontextprotocol/clientCapabilities"


def complete(**fields):
    return {"resultType": "complete", **fields}


def cache_fields(private=False):
    return {"ttlMs": 0, "cacheScope": "private"} if private else {"ttlMs": 300000, "cacheScope": "public"}


def error(request, code, message, **data):
    response = {"code": code, "message": message}
    if data:
        response["data"] = data
    return {"jsonrpc": "2.0", "id": request.get("id"), "error": response}


def protocol_error(request, version):
    return error(request, -32022, "Unsupported protocol version", requested=version, supported=list(PROTOCOLS))


def request_version(request):
    params = request.get("params")
    meta = params.get("_meta") if isinstance(params, dict) else None
    return meta.get(VERSION_KEY) if isinstance(meta, dict) else None


def decoded_name(header):
    if header and header.startswith("=?base64?") and header.endswith("?="):
        try:
            return b64decode(header[9:-2], validate=True).decode("utf-8")
        except (Error, UnicodeError):
            return None
    return header


def header_error(request, headers):
    """Validate mirrored routing fields before dispatching a modern request."""
    versions = headers.get_all("MCP-Protocol-Version", [])
    version = versions[0] if len(versions) == 1 else None
    requested = request_version(request)
    if requested is None and version in (*LEGACY, None) and len(versions) <= 1:
        return None
    if not isinstance(requested, str) or version != requested:
        return error(request, -32020, "Missing or mismatched MCP-Protocol-Version header.")
    if version not in PROTOCOLS:
        return protocol_error(request, version)
    if version in LEGACY:
        return None

    method = request.get("method")
    methods = headers.get_all("Mcp-Method", [])
    if not isinstance(method, str) or methods != [method]:
        return error(request, -32020, "Missing or mismatched Mcp-Method header.")
    name_field = {"tools/call": "name", "resources/read": "uri", "prompts/get": "name"}.get(method)
    if name_field:
        names = headers.get_all("Mcp-Name", [])
        name = request["params"].get(name_field)
        if not isinstance(name, str) or len(names) != 1 or decoded_name(names[0]) != name:
            return error(request, -32020, "Missing or mismatched Mcp-Name header.")
    return None
