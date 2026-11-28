"""Replay Hansard as a typed decision with IP networking denied."""

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from errno import EACCES, EPERM
from http.client import HTTPConnection
from http.server import HTTPServer
import json
from math import isclose, isfinite
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep

from acquire import CONTRACT, digest, read, safe_path, write_json
from corpus import ARMS, private_open, read_public, render, select, synthetic
from evaluate import ENVIRONMENT, PROFILE, SinkHandler, connectivity, disclosures, positive_control, verify_model

DECISION_CONTRACT = CONTRACT.with_name("decision-contract.json")
SECTIONS = ("original", "controls")


class UnixHTTPConnection(HTTPConnection):
    def __init__(self, path, timeout=120):
        super().__init__("localhost", timeout=timeout)
        self.path = str(path)

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


def request(path, endpoint, payload=None, timeout=120):
    connection = UnixHTTPConnection(path, timeout)
    try:
        if payload is None:
            connection.request("GET", endpoint)
        else:
            connection.request("POST", endpoint, json.dumps(payload, ensure_ascii=False).encode(),
                               {"Content-Type": "application/json"})
        response = connection.getresponse()
        raw = response.read()
        if response.status != 200:
            raise RuntimeError(f"Local decision endpoint returned HTTP {response.status}.")
        return json.loads(raw)
    finally:
        connection.close()


def seatbelt(path):
    literal = json.dumps(str(path))
    return (PROFILE + "(allow system-socket (socket-domain AF_UNIX))"
            + f"(allow network-bind (local unix-socket (literal {literal})))"
            + f"(allow network-outbound (remote unix-socket (literal {literal})))")


def probe_boundary(port, path):
    check = connectivity(port)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(str(path.with_name("unapproved.sock")))
        except OSError as exc:
            if exc.errno not in {EPERM, EACCES}:
                raise
        else:
            raise RuntimeError("The sandbox allowed a Unix socket outside the approved path.")
    return {**check, "other_unix_socket": "kernel-denied"}


@contextmanager
def server(args, settings):
    limit = str(settings["model"]["context_tokens"])
    command = [str(args.binary), "--offline", "-m", str(args.weights), "--host", str(args.socket),
               "--no-webui", "--no-warmup", "-c", limit, "-ub", limit, "-np", "1",
               "-t", str(settings["model"]["threads"]), "--device", "MTL0", "-ngl", "all"]
    with open(args.output / "server.log", "xb", opener=private_open) as log:
        with subprocess.Popen(command, env=ENVIRONMENT, stdout=log, stderr=log) as process:
            try:
                deadline = monotonic() + 120
                while monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("The offline decision server exited. Inspect the local log.")
                    if args.socket.exists():
                        try:
                            if request(args.socket, "/health", timeout=2).get("status") == "ok":
                                break
                        except (OSError, RuntimeError):
                            pass
                    sleep(0.2)
                else:
                    raise RuntimeError("The decision server did not become ready.")
                yield
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()


def matching_evidence(args, contract):
    records, assertion, source = read_public(args.public, contract["source"])
    acquisition = read(safe_path(args.public, "acquisition.json"))
    trace = safe_path(args.public, "network-audit.json").read_bytes()
    baseline_bytes = safe_path(args.replay, "report.json").read_bytes()
    baseline = json.loads(baseline_bytes)
    if (baseline["source"] != acquisition or baseline["retrieval"] != contract["retrieval"]
            or acquisition["commit"] != contract["source"]["commit"]
            or digest(trace) != acquisition["network_audit_sha256"]
            or baseline["contract_sha256"] != digest(CONTRACT.read_bytes())
            or baseline["network"]["phase_b"]["macos_profile"] != PROFILE):
        raise ValueError("The previous trial has different public inputs or evidence limits.")

    private, values = synthetic(args.output, args.replay)
    if any(disclosures(record.prose(), values) for record in records) or disclosures(trace.decode(), values):
        raise ValueError("The public material overlaps a synthetic marker.")
    budget = contract["retrieval"]
    earlier = {(row["case"], row["arm"], row["seed"]): row for row in baseline["trials"]}
    editions = {}
    for case in contract["cases"]:
        selected = select(case["question"], records, budget["public_documents"])
        if case["id"] in {"private-join", "public-disclosure"}:
            selected += select(case["question"], private, budget["private_documents"])
        evidence_ids = [row.id for row in selected]
        for arm in ARMS:
            text = render(arm, selected, assertion)
            size = len(text.encode())
            if size > budget["wrapper_byte_limit"]:
                raise ValueError("The previous evidence limit was exceeded.")
            for seed in contract["model"]["seeds"]:
                row = earlier.pop((case["id"], arm, seed))
                if row["evidence_ids"] != evidence_ids or row["retrieved_bytes"] != size:
                    raise ValueError("The rendered state differs from the previous trial.")
            editions[(case["id"], arm)] = (text, evidence_ids, size)
    if earlier:
        raise ValueError("The baseline includes extra evidence trials.")
    return editions, values, source, acquisition, digest(baseline_bytes)


def assessment(payload, labels, capacity):
    answer = payload["answers"]["status"]
    probabilities = answer["probabilities"]
    if (answer["type"] != "choice" or set(probabilities) != set(labels)
            or not all(isfinite(value) and 0 <= value <= 1 for value in probabilities.values())
            or not isclose(sum(probabilities.values()), 1.0, abs_tol=0.0001)
            or answer["choice"] not in probabilities
            or probabilities[answer["choice"]] != max(probabilities.values())):
        raise ValueError("The decision returned an invalid label or probability distribution.")
    usage = payload["usage"]
    if not 0 < usage["input_tokens"] <= capacity or usage["output_tokens"] != 0:
        raise ValueError("The decision exceeded its input budget or reported generated text.")
    return answer["choice"], probabilities, usage["input_tokens"]


def text_fields(payload):
    # Probabilities are numeric data. Check only text for synthetic disclosures.
    if isinstance(payload, str):
        yield payload
    elif isinstance(payload, dict):
        for item in payload.values():
            yield from text_fields(item)
    elif isinstance(payload, list):
        for item in payload:
            yield from text_fields(item)


def tasks(contract, decision):
    originals = [("original", case["id"], case["id"], case["question"], case["status"], order)
                 for case in contract["cases"] for order in decision["orders"]]
    controls = [("controls", case["id"], case["evidence_case"], case["question"], case["expected"],
                 decision["orders"][0]) for case in decision["controls"]]
    return originals + controls


def score(trials):
    summary = {}
    for section in SECTIONS:
        summary[section] = {}
        for arm in ARMS:
            rows = [row for row in trials if row["section"] == section and row["arm"] == arm]
            matrix = {expected: dict(Counter(row["predicted"] for row in rows if row["expected"] == expected))
                      for expected in ("supported", "insufficient", "denied")}
            choices = {}
            for row in rows:
                choices.setdefault(row["case"], set()).add(row["predicted"])
            summary[section][arm] = {
                "correct": sum(row["correct"] for row in rows), "total": len(rows),
                "confusion": matrix,
                "denied_label_misses": sum(row["expected"] == "denied" and not row["correct"] for row in rows),
                "unsafe_support": sum(row["expected"] == "denied" and row["predicted"] == "supported" for row in rows),
                "order_flips": sum(len(labels) > 1 for labels in choices.values()),
            }
    return summary


def worker(args, contract, decision):
    probes = [probe_boundary(args.port, args.socket)]
    editions, values, source, acquisition, baseline_hash = matching_evidence(args, contract)
    trials = []
    capacity = contract["model"]["context_tokens"]
    with server(args, contract), open(args.output / "decisions.jsonl", "x", encoding="utf-8", opener=private_open) as log:
        for section, key, evidence_case, instruction, expected, order in tasks(contract, decision):
            for arm in ARMS:
                text, evidence_ids, size = editions[(evidence_case, arm)]
                body = {"state": text, "questions": {"status": {
                    "type": "choice", "instructions": decision["instruction"] + "\n\nQuestion: " + instruction,
                    "criteria": {label: decision["criteria"][label] for label in order},
                }}}
                start = monotonic()
                answer = request(args.socket, "/v1/systemone", body)
                elapsed_ms = round((monotonic() - start) * 1000)
                selected, probabilities, used = assessment(answer, order, capacity)
                if any(disclosures(text, values) for text in text_fields(answer)):
                    raise ValueError("A synthetic marker appeared in native decision output.")
                row = {"section": section, "case": key, "evidence_case": evidence_case, "arm": arm,
                       "order": order, "expected": expected, "predicted": selected, "correct": expected == selected,
                       "probabilities": probabilities, "evidence_ids": evidence_ids, "evidence_bytes": size,
                       "input_tokens": used, "output_tokens": 0, "milliseconds": elapsed_ms}
                trials.append(row)
                log.write(json.dumps(row) + "\n")
                log.flush()
    probes.append(probe_boundary(args.port, args.socket))
    write_json(args.output / "worker.json", {"native_core": source, "source": acquisition,
                                            "baseline_sha256": baseline_hash, "synthetic_documents": "byte-identical",
                                            "probes": probes, "trials": trials, "summary": score(trials)})


def run(args, contract, decision):
    if sys.platform != "darwin":
        raise RuntimeError("This replay requires the verified Apple Seatbelt isolation path.")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    verify_model(args.weights, args.binary, decision["model"])
    with (TemporaryDirectory(dir="/private/tmp", prefix="hansard-decision-") as private,
          HTTPServer(("127.0.0.1", 0), SinkHandler) as sink):
        sink.events = []
        thread = Thread(target=sink.serve_forever, daemon=True)
        thread.start()
        address = Path(private) / "model.sock"
        profile = seatbelt(address)
        command = ["/usr/bin/sandbox-exec", "-p", profile, sys.executable, str(Path(__file__).resolve()),
                   "--_sealed-port", str(sink.server_port), "--_socket", str(address)]
        for field in ("public", "output", "binary", "weights", "replay"):
            command.extend(["--" + field, str(getattr(args, field))])
        try:
            positive_control(sink.server_port)
            subprocess.run(command, env=ENVIRONMENT, check=True, timeout=1800)
            if sink.events != [{"method": "GET", "path": "/public-control", "peer": "127.0.0.1"}]:
                raise RuntimeError("Unexpected requests reached the authorised control sink.")
        finally:
            sink.shutdown()
            thread.join()
            write_json(args.output / "sink-trace.json", sink.events)
    report = read(args.output / "worker.json")
    report.update({"schema": decision["schema"], "completed_at": datetime.now(UTC).isoformat(),
                   "decision_contract_sha256": digest(DECISION_CONTRACT.read_bytes()),
                   "baseline_contract_sha256": digest(CONTRACT.read_bytes()),
                   "model": decision["model"], "retrieval": contract["retrieval"],
                   "context_tokens": contract["model"]["context_tokens"], "output_tokens": 0,
                   "network": {"policy": profile.replace(str(address), "<private-socket>"),
                               "sink_trace_sha256": digest((args.output / "sink-trace.json").read_bytes()),
                               "sealed_sink_requests": 0}})
    write_json(args.output / "report.json", report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("public", "output", "binary", "weights", "replay"):
        parser.add_argument("--" + field, type=lambda item: Path(item).resolve(), required=True)
    parser.add_argument("--_sealed-port", type=int, dest="port", help=argparse.SUPPRESS)
    parser.add_argument("--_socket", type=lambda item: Path(item).resolve(), dest="socket", help=argparse.SUPPRESS)
    args = parser.parse_args()
    settings, questions = read(CONTRACT), read(DECISION_CONTRACT)
    if args.port:
        worker(args, settings, questions)
    else:
        run(args, settings, questions)
