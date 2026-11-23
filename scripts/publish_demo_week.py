"""Publish a prepared demonstration or run the two dated refreshes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
import fcntl
from hashlib import sha256
from pathlib import Path
import subprocess
import time as waiting
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from build_pages import SITE, SOURCE
from capture import dump, now
from prepare_demo_week import ROOT, prepare, read
from query import DEFAULT_DB

ZONE = ZoneInfo("Europe/London")
PAGES_REMOTE = SOURCE + ".git"
PAGES_LOCK = ROOT / ".work/pages-publication.lock"
GIT_AUTH = ("-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential")


@contextmanager
def pages_lock():
    with PAGES_LOCK.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def git(checkout, *command):
    return subprocess.check_output(["git", "-C", str(checkout), *command], text=True, timeout=300).strip()


def matches_remote(name, size, digest):
    url = urljoin(SITE, "" if name == "index.html" else name)
    with urlopen(Request(url, headers={"Accept-Encoding": "identity"}), timeout=30) as response:
        checksum = sha256()
        count = 0
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            checksum.update(chunk)
            count += len(chunk)
        return count == size and checksum.hexdigest() == digest


def verify_public(site, commit):
    raw = (site / "checksums.json").read_bytes()
    expires = waiting.monotonic() + 480
    while waiting.monotonic() < expires:
        try:
            if matches_remote("checksums.json", len(raw), sha256(raw).hexdigest()):
                break
        except (HTTPError, URLError, TimeoutError):
            pass
        waiting.sleep(10)
    else:
        raise RuntimeError("The Pages checksum catalogue has not reached the deployed site.")
    def verify(item):
        name, info = item
        for attempt in range(4):
            try:
                if matches_remote(name, info["bytes"], info["sha256"]):
                    return
            except HTTPError as exc:
                if exc.code not in {404, 408, 429, 500, 502, 503, 504}:
                    raise RuntimeError(f"Could not read published file {name} (HTTP {exc.code}).") from exc
            except (URLError, TimeoutError):
                pass
            if attempt < 3:
                waiting.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"Could not verify the published bytes for {name}.")

    public_assets = [(name, info) for name, info in read(site / "checksums.json").items() if name != ".nojekyll"]
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(verify, public_assets))
    print(f"Verified the published Pages file hashes for {commit[:12]}.", flush=True)


def publish(prepared, checkout):
    descriptor = read(prepared / "prepared.json")
    site = prepared / "site"
    with pages_lock():
        if git(checkout, "branch", "--show-current") != "gh-pages" or git(checkout, "status", "--porcelain"):
            raise ValueError("The Pages checkout must be clean and on gh-pages.")
        git(checkout, *GIT_AUTH, "fetch", PAGES_REMOTE, "gh-pages")
        git(checkout, "rebase", "FETCH_HEAD")
        subprocess.run(["rsync", "-rc", "--delete", "--exclude=/.git", "--exclude=/november/",
                        str(site) + "/", str(checkout) + "/"], check=True)
        git(checkout, "add", "--all")
        if git(checkout, "status", "--porcelain"):
            git(checkout, "diff", "--cached", "--check")
            git(checkout, "commit", "-m", f"Publish verified Hansard through {descriptor['through']}")
        commit = git(checkout, "rev-parse", "HEAD")
        git(checkout, *GIT_AUTH, "push", PAGES_REMOTE, "HEAD:refs/heads/gh-pages")
    verify_public(site, commit)
    dump(prepared / "published.json", {"commit": commit, "through": descriptor["through"],
                                        "verified_at": now(), "url": SITE + "demo.html"})


def wait_until(when):
    while (seconds := (when - datetime.now(ZONE)).total_seconds()) > 0:
        waiting.sleep(min(seconds, 60))


def scheduled(args):
    base = args.prepared
    if not (base / "published.json").is_file():
        raise ValueError("The starting snapshot must have a verified publication receipt.")
    if args.use_cached_demo:
        print("Using verified historical demonstration evidence from the previous publication.", flush=True)
    for through in ("2026-11-18", "2026-11-19"):
        if through <= read(base / "published.json")["through"]:
            continue
        target = args.schedule / through
        target.mkdir(parents=True, exist_ok=True)
        ready_day = date.fromisoformat(through) + timedelta(days=1)
        start = datetime.combine(ready_day, time(6, 15), ZONE)
        stop = datetime.combine(ready_day, time(9, 30), ZONE)
        for candidate in sorted(target.glob("attempt-*"), reverse=True):
            if (candidate / "published.json").is_file():
                base = candidate
                break
        else:
            print(f"Waiting for {through}. First attempt {start.isoformat()}.", flush=True)
            wait_until(start)
            updated = args.updated_base
            if updated and (updated / "published.json").is_file() and (
                read(updated / "published.json")["through"] == read(base / "published.json")["through"]
            ):
                base = updated
            previous = read(base / "prepared.json")
            while datetime.now(ZONE) < stop:
                pending = next((p for p in sorted(target.glob("attempt-*"), reverse=True)
                                if (p / "prepared.json").is_file()), None)
                if pending is None:
                    pending = target / ("attempt-" + datetime.now(ZONE).strftime("%H%M%S"))
                try:
                    if not (pending / "prepared.json").is_file():
                        prepare(argparse.Namespace(
                            through=through, out=pending, base_release=base / "release",
                            base_coverage=base / "coverage.json", snapshot=Path(previous["snapshot"]),
                            people=Path(previous["people"]), database=args.database, explorer=args.explorer,
                            demo_from=base / "site" if args.use_cached_demo else None,
                            reuse_capture=False,
                            history_cache=args.history_cache,
                            history_deadline=stop - timedelta(minutes=25),
                        ))
                    publish(pending, args.checkout)
                    base = pending
                    break
                except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
                    print(f"{now()} {through} attempt failed: {exc}", flush=True)
                    wait_until(min(stop, datetime.now(ZONE) + timedelta(minutes=15)))
            else:
                print(f"Stopped attempts for {through} at {stop.isoformat()}.", flush=True)
    through = read(base / "published.json")["through"]
    dump(args.schedule / "outcome.json", {"verified_through": through, "finished_at": now()})
    return through == "2026-11-19"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--checkout", type=Path, default=ROOT / ".work/pages-preview")
    parser.add_argument("--schedule", type=Path)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--use-cached-demo", action="store_true")
    parser.add_argument("--history-cache", type=Path)
    parser.add_argument("--updated-base", type=Path, help="Use this snapshot if it has been published by refresh time.")
    parser.add_argument("--explorer", type=Path, default=ROOT.parent / "okf-explorer")
    arguments = parser.parse_args()
    if arguments.schedule:
        raise SystemExit(not scheduled(arguments))
    publish(arguments.prepared, arguments.checkout)
