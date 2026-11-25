"""Replay one acceptance journey over both MCP transports and probe installed clients."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from capture import dump
from hansard_access import BUNDLE_ID, read


SERVER = Path(__file__).resolve().with_name("mcp_server.py")
PROTOCOL = "2025-11-25"
CLIENTS = {
    "ChatGPT mobile": {"text", "voice"},
    "Codex desktop": {"text", "voice"},
    "Codex CLI": {"text"},
    "Claude mobile": {"text", "voice"},
    "Claude Code": {"text"},
    "Gemini mobile": {"text", "voice"},
    "Gemini CLI": {"text"},
    "VS Code": {"text"},
    "GitHub Copilot CLI": {"text"},
    "Microsoft Copilot mobile": {"text", "voice"},
    "Microsoft 365 Copilot": {"text", "voice"},
}
CASES = {"discovery", "history", "capture", "fallback"}


def request(number, method, params=None):
    return {"id": number, "jsonrpc": "2.0", "method": method, "params": params or {}}


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def journey(exchange, expected):
    response = exchange(request(1, "initialize", {"protocolVersion": PROTOCOL,
                        "capabilities": {}, "clientInfo": {"name": "hansard-replay", "version": "1"}}))
    check(response["result"]["protocolVersion"] == PROTOCOL, "The MCP negotiation differs.")
    exchange({"jsonrpc": "2.0", "method": "notifications/initialized"})
    listed = {row["name"] for row in exchange(request(2, "tools/list"))["result"]["tools"]}

    def call(number, name, **kwargs):
        check(name in listed, f"Tool {name} is undiscoverable.")
        reply = exchange(request(number, "tools/call", {"name": name, "arguments": kwargs}))["result"]
        check(not reply["isError"], f"Tool {name} failed: {reply['structuredContent']}")
        return reply["structuredContent"]

    scope = call(3, "hansard_describe_bundle")
    check(scope["bundle_id"] == BUNDLE_ID and scope["capture"]["contributions"] == expected, "Wrong capture scope.")
    check(scope["historical_search"]["through"] == "2026-11-01", "Wrong end date for pre-capture history.")
    concept = call(4, "hansard_resolve_concept", query="Synergy programme")
    check(concept["items"][0]["id"] == "synergy-dwp", "Expected Synergy concept not resolved.")
    first = call(5, "hansard_mentions", key="synergy-dwp", limit=2, snapshot=scope["snapshot"])
    page, links = first, []
    while True:
        links.extend(row["hansard"] for row in page["items"])
        if page["next_offset"] is None:
            break
        check(len(links) == page["next_offset"] <= first["total"], "Invalid result cursor.")
        page = call(6 + len(links), "hansard_mentions", key="synergy-dwp", limit=30,
                    offset=page["next_offset"], snapshot=scope["snapshot"])
    check(len(set(links)) == len(links) == first["total"] > 2, "The mention pages omitted or repeated links.")
    check(all(url.startswith("https://hansard.parliament.uk/") for url in links), "Incorrect source links.")
    search = call(400, "hansard_search_passages", query="Civil Service pension scheme", limit=3)
    check(search["total"] > 0 and all(row["excerpt"] and row["hansard"] for row in search["items"]), "Capture search lacks source text evidence.")
    negative = call(401, "hansard_search_passages", query="Civil Service pension scheme", through="2026-11-01")
    check(negative["total"] == 0, "Capture-only query leaked into an out-of-scope date.")
    return {"protocol": PROTOCOL, "snapshot": scope["snapshot"], "capture": scope["capture"],
            "history_through": scope["historical_search"]["through"],
            "scope_gaps": (scope["older_archive"] or {}).get("source_gaps"), "mentions": len(links),
            "first_mention": links[0], "history_links": links, "timeline": first["timeline"],
            "capture_examples": [row["hansard"] for row in search["items"]],
            "text_search_total": search["total"], "tools": sorted(listed)}


def assess(receipts, expected):
    """Check observed client answers against the same evidence served by MCP."""
    outcomes = {}
    for row in receipts:
        client, mode, case = row["client"], row["mode"], row["case"]
        if mode not in CLIENTS.get(client, ()) or case not in CASES:
            raise ValueError(f"Unknown client, mode or case: {client}, {mode}, {case}")
        key = (client, mode, case)
        if key in outcomes:
            raise ValueError(f"Repeated client case: {key}")
        if row.get("blocker"):
            outcomes[key] = {"status": "blocked", "details": [row["blocker"]]}
            continue

        evidence = row.get("observed", {})
        failures = []
        elapsed = row.get("seconds")
        if not isinstance(elapsed, (float, int)) or isinstance(elapsed, bool) or not 0 < elapsed <= 180:
            failures.append("Time to cited answer must be positive and at most 180 seconds.")
        if evidence.get("snapshot") != expected["snapshot"]:
            failures.append("Answer did not identify the verified snapshot.")

        links = evidence.get("links", [])
        if case == "discovery":
            wanted = {"capture_from": expected["capture"]["from"], "capture_through": expected["capture"]["through"],
                      "contributions": expected["capture"]["contributions"],
                      "history_through": expected["history_through"], "scope_gaps": expected["scope_gaps"],
                      "disclosed_alias_scope": True}
        elif case == "history":
            wanted = {"total": expected["mentions"], "timeline": expected["timeline"], "disclosed_alias_scope": True}
            if set(links) != set(expected["history_links"]) or len(links) != expected["mentions"]:
                failures.append("The cited Hansard links differ from the complete retained results.")
        elif case == "capture":
            wanted = {"out_of_scope_results": 0}
            if not set(links).intersection(expected["capture_examples"]):
                failures.append("Cite at least one of the three requested capture results.")
        else:
            wanted = {"disclosed_supplied_scope": True, "unknown_concept_reported": True}
            if not links or not set(links).issubset(expected["history_links"]):
                failures.append("The fallback must cite links from the supplied evidence.")

        failures.extend(f"Incorrect or missing {field}." for field, value in wanted.items()
                        if evidence.get(field) != value)
        outcomes[key] = {"status": "failed" if failures else "passed", "details": failures}
    return [
        {"client": client, "mode": mode, "case": case,
         **outcomes.get((client, mode, case), {"status": "pending", "details": []})}
        for client, modes in CLIENTS.items() for mode in sorted(modes) for case in sorted(CASES)
    ]


@contextmanager
def serve(command):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with subprocess.Popen([*command, "--http", str(port)], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL) as process:
        try:
            start = time.monotonic()
            while time.monotonic() - start < 30:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError("The HTTP server did not start.")
                    time.sleep(0.10)
            else:
                raise RuntimeError("The HTTP server did not open its socket.")
            yield f"http://127.0.0.1:{port}/mcp"
        finally:
            process.terminate()


def check_http(url, expected):
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
               "MCP-Protocol-Version": PROTOCOL}

    def exchange(message):
        with urlopen(Request(url, data=json.dumps(message).encode(), headers=headers), timeout=35) as response:
            if "id" not in message:
                check(response.status == 202 and not response.read(), "Unexpected notification response.")
                return None
            return json.load(response)

    for call, status in ((Request(url), 405), (Request(url, data=b'{}', headers={**headers, "Origin": "https://other.example"}), 403)):
        try:
            urlopen(call, timeout=5)
        except HTTPError as exc:
            check(exc.code == status, f"Unexpected HTTP response {exc.code}.")
        else:
            raise RuntimeError("Unexpected accepted HTTP request.")
    return journey(exchange, expected)


def check_stdio(command, expected):
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as process:
        def exchange(message):
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            return json.loads(process.stdout.readline()) if "id" in message else None

        try:
            return journey(exchange, expected)
        finally:
            process.stdin.close()


def installed_clients(url, scratch):
    def probe(binary, operands, directory, env=None):
        return subprocess.run([binary, *operands], cwd=directory, env=env, capture_output=True, text=True, timeout=35)

    name = "hansard-voice-test"
    outcomes = {}
    for label, executable in (("Codex CLI", "codex"), ("Claude Code", "claude"), ("Gemini CLI", "gemini"),
                              ("GitHub Copilot CLI", "copilot"), ("VS Code", "code")):
        binary = shutil.which(executable)
        if not binary:
            outcomes[label] = {"readiness": "command unavailable", "answer_test": "pending"}
            continue
        version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20)
        report = {"version": version.stdout.splitlines()[0] if version.stdout else None,
                  "readiness": "binary available", "answer_test": "pending"}
        directory = scratch / executable
        directory.mkdir()
        try:
            if executable == "gemini":
                added = probe(binary, ["mcp", "add", "--scope", "project", "--transport", "http", name, url], directory)
                connected = probe(binary, ["mcp", "list"], directory) if not added.returncode else added
                line = next((row for row in connected.stdout.splitlines() if name in row), "")
                report["readiness"] = "MCP connected" if re.search(r"\bConnected\b", line) else "project MCP connection unconfirmed"
            elif executable == "claude":
                config = directory / "config"
                config.mkdir()
                env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config), "DISABLE_AUTOUPDATER": "1"}
                added = probe(binary, ["mcp", "add", "--scope", "local", "--transport", "http", name, url], directory, env)
                connected = probe(binary, ["mcp", "get", name], directory, env) if not added.returncode else added
                report["readiness"] = "MCP connected" if re.search(r"\bStatus:.*\bConnected\b", connected.stdout) else "isolated MCP connection unconfirmed"
            elif executable == "codex":
                connected = probe(binary, ["mcp", "-c", f'mcp_servers.{name}.url="{url}"', "get", name, "--json"], directory)
                report["readiness"] = "HTTP configuration accepted" if not connected.returncode and url in connected.stdout else "HTTP configuration unconfirmed"
            elif executable == "copilot":
                dump(directory / "mcp-config.json", {"mcpServers": {name: {"type": "http", "url": url, "tools": ["*"]}}})
                connected = probe(binary, ["mcp", "get", name, "--json"], directory,
                                  {**os.environ, "COPILOT_HOME": str(directory)})
                report["readiness"] = "isolated HTTP configuration accepted" if not connected.returncode and url in connected.stdout else "isolated HTTP configuration unconfirmed"
        except subprocess.TimeoutExpired:
            report["readiness"] = "project MCP probe timed out"
        outcomes[label] = report
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication", type=Path, required=True)
    parser.add_argument("--probe-clients", action="store_true", help="Check installed clients without asking models to answer.")
    parser.add_argument("--receipts", type=Path, help="Score recorded text and voice answers against the publication.")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    pointer = args.publication.resolve()
    expected = read(Path(read(pointer)["site"]) / "coverage.json")["contributions"]
    command = [sys.executable, str(SERVER), "--publication", str(pointer)]
    stdio = check_stdio(command, expected)
    workspace = args.out.resolve().parent if args.out else Path.cwd() / ".work"
    workspace.mkdir(parents=True, exist_ok=True)
    with serve(command) as url, tempfile.TemporaryDirectory(dir=workspace, prefix="hansard-client-") as scratch:
        http = check_http(url, expected)
        check(http == stdio, "HTTP and stdio evidence differ.")
        clients = installed_clients(url, Path(scratch)) if args.probe_clients else {}
    answers = assess(read(args.receipts) if args.receipts else [], stdio)
    result = {"stdio": stdio, "streamable_http": http, "clients": clients, "answers": answers}
    if args.out:
        dump(args.out, result)
    print(json.dumps(result, indent=2))
    if any(row["status"] == "failed" for row in answers):
        sys.exit(1)


if __name__ == "__main__":
    main()
