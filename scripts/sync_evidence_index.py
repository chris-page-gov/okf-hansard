"""Synchronise the small evidence index through the protected main branch."""

from base64 import b64decode, b64encode
from datetime import date
import hashlib
import json
import re
import subprocess
import tempfile
import time

REPO = "chris-page-gov/okf-hansard"
PATH = "HANSARD-EVIDENCE.md"
CHECK = "okf-hansard-ci"
WAIT_SECONDS = 180
POLL_SECONDS = 10
MARKER = re.compile(r"^Verified capture through (\d{4}-\d{2}-\d{2})\.$", re.MULTILINE)


class SyncError(RuntimeError):
    """A safe, actionable refusal to modify the repository."""


def _gh(*args, input_text=None):
    result = subprocess.run(["gh", *args], input=input_text, text=True,
                           capture_output=True, check=False, timeout=30)
    if result.returncode:
        # gh errors can contain useful resource details; never echo command/env.
        detail = result.stderr.strip() or result.stdout.strip() or "unknown GitHub error"
        raise SyncError(f"GitHub operation failed: {detail}")
    return result.stdout


def _api(method, endpoint, payload=None):
    args = ["api", endpoint, "--method", method]
    if payload is not None:
        args += ["--input", "-"]
        raw = _gh(*args, input_text=json.dumps(payload))
    else:
        raw = _gh(*args)
    return json.loads(raw) if raw.strip() else None


def _content(entry):
    return b64decode(entry["content"]).decode("utf-8")


def _get_file(ref, repo):
    try:
        return _api("GET", f"repos/{repo}/contents/{PATH}?ref={ref}")
    except SyncError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def _through(text):
    matches = MARKER.findall(text)
    if len(matches) != 1:
        raise SyncError("Evidence index requires exactly one capture-through marker.")
    try:
        return date.fromisoformat(matches[0])
    except ValueError as exc:
        raise SyncError("Evidence index has an invalid capture-through date.") from exc


def _protected(repo):
    try:
        protection = _api("GET", f"repos/{repo}/branches/main/protection")
    except SyncError as exc:
        raise SyncError("Could not verify main branch protection and required checks.") from exc
    contexts = (protection.get("required_status_checks") or {}).get("contexts", [])
    if CHECK not in contexts:
        raise SyncError(f"Protected main does not require the expected {CHECK} check.")


def _checks(sha, repo):
    data = _api("GET", f"repos/{repo}/commits/{sha}/check-runs")
    runs = [run for run in data.get("check_runs", []) if run.get("name") == CHECK]
    if not runs or any(run.get("status") != "completed" for run in runs):
        return False
    if not all(run.get("conclusion") == "success" for run in runs):
        raise SyncError(f"Required {CHECK} check failed; pull request remains open.")
    return True


def _compare(base, tip, repo):
    return _api("GET", f"repos/{repo}/compare/{base}...{tip}")


def sync(content: str, *, repo=REPO):
    """Publish *content* to main via a checked, protected pull request.

    ``repo`` is injectable for tests; production calls use the fixed repository.
    """
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SyncError("Repository name is invalid.")
    if not isinstance(content, str) or not content.endswith("\n"):
        raise SyncError("Evidence index content must be UTF-8 text ending in a newline.")
    desired = content.encode("utf-8")
    through = _through(content)
    base = _api("GET", f"repos/{repo}/git/ref/heads/main")["object"]["sha"]
    current = _get_file(base, repo)
    if current and _content(current) == content:
        return {"status": "unchanged", "sha": base}
    if current:
        existing_through = _through(_content(current))
        if existing_through > through:
            return {"status": "newer", "sha": base}

    _protected(repo)
    digest = hashlib.sha256(desired).hexdigest()[:12]
    branch = f"codex/evidence-index-{base[:12]}-{digest}"
    try:
        _api("POST", f"repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": base})
    except SyncError:
        existing = _api("GET", f"repos/{repo}/git/ref/heads/{branch}")
        comparison = _compare(base, existing["object"]["sha"], repo)
        if comparison.get("status") not in ("ahead", "identical"):
            raise SyncError("The deterministic retry branch is not based on the selected main commit.")
        if any(item["filename"] != PATH or item["status"] not in ("added", "modified")
               for item in comparison.get("files", [])):
            raise SyncError("The retry branch contains changes outside the evidence index.")

    branch_file = _get_file(branch, repo)
    if not branch_file or _content(branch_file) != content:
        payload = {"message": "Update Hansard evidence index", "content": b64encode(desired).decode("ascii"),
                   "branch": branch}
        if branch_file:
            payload["sha"] = branch_file["sha"]
        _api("PUT", f"repos/{repo}/contents/{PATH}", payload)

    if _api("GET", f"repos/{repo}/git/ref/heads/main")["object"]["sha"] != base:
        raise SyncError("Main changed while preparing the evidence index; retry against the new base.")
    owner = repo.split("/")[0]
    prs = _api("GET", f"repos/{repo}/pulls?state=open&head={owner}:{branch}")
    if prs:
        if len(prs) != 1:
            raise SyncError("Expected one open evidence index pull request.")
        pr = prs[0]
        branch_sha = _api("GET", f"repos/{repo}/git/ref/heads/{branch}")["object"]["sha"]
        if pr["base"]["ref"] != "main" or pr["head"]["sha"] != branch_sha:
            raise SyncError("An open retry pull request has changed; refusing to reuse it.")
    else:
        body = ("Automated update of the generated Hansard evidence index.\n\n"
                f"Verified capture through {through.isoformat()}.\n"
                "This pull request is merged only after the required protected check passes.")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
            handle.flush()
            raw = _gh("pr", "create", "--repo", repo, "--head", branch, "--base", "main",
                      "--title", "Update Hansard evidence index", "--body-file", handle.name)
        url = raw.strip().splitlines()[-1]
        pr = _api("GET", f"repos/{repo}/pulls/{url.rstrip('/').split('/')[-1]}")

    head = pr["head"]["sha"]
    comparison = _compare(base, head, repo)
    files = [(item["filename"], item["status"]) for item in comparison.get("files", [])]
    if comparison.get("status") != "ahead" or files not in ([(PATH, "added")], [(PATH, "modified")]):
        raise SyncError("The evidence pull request must change only the index.")
    candidate = _get_file(head, repo)
    if not candidate or _content(candidate) != content:
        raise SyncError("The evidence pull request no longer contains the verified capture.")
    deadline = time.monotonic() + WAIT_SECONDS
    while not _checks(head, repo):
        if time.monotonic() >= deadline:
            raise SyncError(f"Required {CHECK} check did not pass within {WAIT_SECONDS} seconds; PR remains open.")
        time.sleep(POLL_SECONDS)
    if _api("GET", f"repos/{repo}/git/ref/heads/main")["object"]["sha"] != base:
        raise SyncError("Main changed before merge; PR remains open for safe review and retry.")
    if pr.get("mergeable") is False or pr.get("draft"):
        raise SyncError("Pull request is not mergeable; it remains open.")
    result = _api("PUT", f"repos/{repo}/pulls/{pr['number']}/merge",
                  {"sha": head, "merge_method": "squash"})
    merged = _get_file(result["sha"], repo) if result.get("merged") is True else None
    if not merged or _content(merged) != content:
        raise SyncError("Could not verify the merged evidence index.")
    return {"status": "merged", "sha": result["sha"], "pull_request": pr["html_url"]}
