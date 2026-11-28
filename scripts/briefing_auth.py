"""OAuth resource authentication for the private Hansard briefing connector."""

from base64 import b64encode
from dataclasses import dataclass
from datetime import date
import json
import os
import re
import time
from urllib.parse import quote_plus, urlencode, urlsplit
from urllib.request import Request, build_opener

from http_policy import NoRedirect


SCOPE = "hansard:briefing"
METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"
TOKEN = re.compile(r"Bearer +([A-Za-z0-9._~+/-]+=*)", re.IGNORECASE)
TOPIC = re.compile(r"[A-Za-z0-9_-]{1,100}")


@dataclass(frozen=True)
class BriefingAccount:
    member_id: int
    portfolio: tuple


class AuthFailure(Exception):
    def __init__(self, status, error=None):
        self.status = status
        self.error = error


def https_url(value):
    if not isinstance(value, str) or not value.isascii() or any(
        char.isspace() or ord(char) < 32 or char in '"<>\\' for char in value
    ):
        raise ValueError("Use an absolute HTTPS address in the authorisation settings.")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username is not None
            or parts.query or parts.fragment):
        raise ValueError("Use an absolute HTTPS address in the authorisation settings.")
    return parts


def parse_account(entry):
    member_id = entry["member_id"]
    if type(member_id) is not int or not 1 <= member_id <= 100000:
        raise ValueError("Use the official positive Parliament Member ID in each binding.")
    topics = entry["portfolio"]
    if not isinstance(topics, list) or len(topics) > 20:
        raise ValueError("Provide up to 20 dated portfolio topics per person.")
    for topic in topics:
        if (not isinstance(topic, dict) or set(topic) - {"key", "from", "through"}
                or not isinstance(topic.get("key"), str) or not TOPIC.fullmatch(topic["key"])):
            raise ValueError("Use canonical Hansard topic keys in the portfolio.")
        start = date.fromisoformat(topic["from"])
        end = date.fromisoformat(topic["through"]) if "through" in topic else date.max
        if start.isoformat() != topic["from"] or ("through" in topic and end.isoformat() != topic["through"]):
            raise ValueError("Use portfolio dates in YYYY-MM-DD format.")
        if end < start:
            raise ValueError("A portfolio assignment must end on or after its start.")
    return BriefingAccount(member_id, tuple(topics))


class Authorizer:
    def __init__(self, settings, secret, *, opener=None):
        self.resource = settings["resource"]
        parts = https_url(self.resource)
        if parts.path != "/mcp":
            raise ValueError("The protected resource URL must end in /mcp.")
        self.public_origin = f"{parts.scheme}://{parts.netloc}"
        self.issuer = settings["issuer"]
        self.endpoint = settings["introspection_endpoint"]
        https_url(self.issuer)
        https_url(self.endpoint)
        client_id = settings["introspection_client_id"]
        if not client_id or not secret:
            raise ValueError("Configure a token introspection client and its secret.")
        basic = f"{quote_plus(client_id)}:{quote_plus(secret)}".encode("ascii")
        self.authorization = "Basic " + b64encode(basic).decode("ascii")
        self.bindings = {subject: parse_account(binding) for subject, binding in settings["bindings"].items()}
        if not self.bindings or any(not subject.strip() for subject in self.bindings):
            raise ValueError("Configure named OAuth subject bindings for this issuer.")
        self.opener = opener or build_opener(NoRedirect)

    @classmethod
    def load(cls, path):
        with path.open(encoding="utf-8") as file:
            return cls(json.load(file), os.environ.get("HANSARD_INTROSPECTION_CLIENT_SECRET"))

    def metadata(self):
        return {"resource": self.resource, "authorization_servers": [self.issuer],
                "scopes_supported": [SCOPE], "bearer_methods_supported": ["header"],
                "resource_name": "Hansard portfolio briefings"}

    def challenge(self, error=None):
        header = f'Bearer resource_metadata="{self.public_origin + METADATA_PATH}", scope="{SCOPE}"'
        return header + f', error="{error}"' if error else header

    def introspect(self, token):
        request = Request(self.endpoint,
                          data=urlencode({"token": token, "token_type_hint": "access_token"}).encode("ascii"),
                          headers={"Authorization": self.authorization, "Accept": "application/json",
                                   "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with self.opener.open(request, timeout=5) as response:
                body = response.read(65537)
            if len(body) > 65536:
                raise ValueError("Introspection response is too large.")
            claims = json.loads(body)
            if not isinstance(claims, dict):
                raise ValueError("Introspection response must be an object.")
            return claims
        except (OSError, ValueError) as error:
            raise AuthFailure(503) from error

    def account(self, header):
        if not header:
            raise AuthFailure(401)
        token = TOKEN.fullmatch(header) if len(header) <= 8192 else None
        if not token:
            raise AuthFailure(401, "invalid_token")
        result = self.introspect(token.group(1))
        audience = result.get("aud")
        audience_ok = self.resource == audience or isinstance(audience, list) and self.resource in audience
        expiry, subject = result.get("exp"), result.get("sub")
        not_before = result.get("nbf", 0)
        now = time.time()
        if (result.get("active") is not True or result.get("iss", self.issuer) != self.issuer
                or not audience_ok or type(expiry) is not int or expiry <= now
                or type(not_before) is not int or not_before > now or not isinstance(subject, str)):
            raise AuthFailure(401, "invalid_token")
        scope = result.get("scope", "")
        if not isinstance(scope, str) or SCOPE not in scope.split():
            raise AuthFailure(403, "insufficient_scope")
        account = self.bindings.get(subject)
        if account is None:
            raise AuthFailure(403)
        return account
