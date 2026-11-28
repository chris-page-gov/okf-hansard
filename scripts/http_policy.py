"""Keep upstream requests pinned to their declared URL."""

from urllib.request import HTTPRedirectHandler, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, target):
        return None


open_source = build_opener(NoRedirect()).open
