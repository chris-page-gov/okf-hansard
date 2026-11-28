"""Prepare a verified week snapshot and an unpublished Pages directory."""

import argparse
from contextlib import closing
from datetime import datetime, timedelta, time
import json
from pathlib import Path
import shutil
import subprocess
from zoneinfo import ZoneInfo

from backfill import collect
from build import build
from build_pages import stage
from capture import HOUSES, dump, now, sha
from passages import build_locators
from people import declarations
from query import DEFAULT_DB, Index
from refresh import refresh
from safe_paths import resolve_within
from verify import check

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_bytes())


def carry_history(previous, release, database):
    shutil.copyfile(previous / "archive-analysis-profile.json", release / "archive-analysis-profile.json")
    old = read(previous / "analysis-profile.json")["entities"]
    current = read(release / "analysis-profile.json")["entities"]
    supplemental = release / "supplemental"
    supplemental.mkdir()
    for asset in (previous / "supplemental").glob("*.json"):
        entity = read(asset)["entity"]
        if entity in current and old.get(entity) == current[entity]:
            shutil.copyfile(asset, supplemental / asset.name)
    if (previous / "backfill" / "manifest.json").is_file():
        backfill = release / "backfill"
        backfill.mkdir()
        for asset in (previous / "backfill").glob("*.json"):
            if asset.stem in current and old.get(asset.stem) == current[asset.stem]:
                shutil.copyfile(asset, backfill / asset.name)
    if database is None:
        return None, len(list(supplemental.glob("*.json")))
    connection = Index(release, database).connect()
    if connection is None:
        raise ValueError("The verified historical cache is unavailable.")
    with closing(connection):
        count = connection.execute("SELECT count(*) FROM sitting WHERE status='processed'").fetchone()[0]
    return count, len(list(supplemental.glob("*.json")))


def cached_demo(site, expected_days):
    raw = (site / "demo.json").read_bytes()
    integrity = read(site / "checksums.json")["demo.json"]
    if sha(raw) != integrity["sha256"] or len(raw) != integrity["bytes"]:
        raise ValueError("The cached demonstration does not match its publication receipt.")
    data = json.loads(raw)
    if data["sittings"] != expected_days:
        raise ValueError("The cached demonstration belongs to a different release.")
    return data


def prepare(args):
    previous = args.base_release.resolve()
    base = read(previous / "receipt.json")
    baseline = cached_demo(args.demo_from, base["week_contributions_by_day"]) if args.demo_from else None
    database = None if baseline else args.database
    dates = sorted(base["week_contributions_by_day"])
    first, prior = dates[0], dates[-1]
    if args.through < prior:
        raise ValueError("The new snapshot must include the existing coverage.")
    end = datetime.fromisoformat(args.through).date()
    ready = datetime.combine(end + timedelta(days=1), time(6, 15), ZoneInfo("Europe/London"))
    if args.through > prior and datetime.now(ZoneInfo("Europe/London")) < ready:
        raise ValueError("Wait for the next morning’s published Hansard snapshot.")
    args.out.mkdir(parents=True, exist_ok=False)
    snapshot = args.snapshot or ROOT / ".snapshots" / base["capture"]
    people = args.people or ROOT / ".snapshots" / base["people_capture"]
    if args.through > prior:
        last = datetime.fromisoformat(prior).date()
        added = {(last + timedelta(days=offset)).isoformat() for offset in range(1, (end - last).days + 1)}
        if args.reuse_capture:
            if not args.snapshot or not args.people:
                raise ValueError("Pass both the retrieved sitting and Member snapshots.")
            people_receipt = read(resolve_within(people, "manifest.json"))
        else:
            capture = args.out / "capture"
            if not refresh(snapshot, capture, added):
                raise ValueError("One or more advertised sources could not be retrieved.")
            snapshot = capture
        manifest = read(resolve_within(snapshot, "manifest.json"))
        if any(item["errors"] for item in manifest["sittings"]):
            raise ValueError("The sitting snapshot lists source errors.")
        observed = {(item["date"], item["house"]) for item in manifest["sittings"] if item["roots"]}
        if {(day, house) for day in added for house in HOUSES} - observed:
            raise ValueError("Both Houses must have published data for every added day.")
        if not args.reuse_capture:
            people_out = args.out / "people"
            people_receipt = declarations(people_out, snapshot, first, args.through, previous=people)
            people = people_out
        if people_receipt["errors"]:
            raise ValueError("One or more Member biographies could not be checked.")

    release = args.out / "release"
    build(snapshot, people, release, ROOT / "profile/vocabulary.yaml", first, args.through, args.explorer)
    report = release / "verification.json"
    if not check(release, snapshot, people, report):
        raise ValueError("The full graph did not pass source and relationship verification.")
    build_locators(snapshot, release)
    archive_sittings, supplements = carry_history(previous, release, database)
    final = read(args.base_coverage)
    if archive_sittings is not None and archive_sittings != sum(
        row["processed_sittings"] for row in final["archive"]["ranges"].values()
    ):
        raise ValueError("The historical cache differs from its verified coverage.")
    for asset in ("example-earlier-mentions.yamlld", "example-related-evidence.json",
                  "example-related-view.html", "voice-microsoft-365.html", "voice-microsoft-365.json"):
        shutil.copyfile(previous / asset, release / asset)
    receipt = read(release / "receipt.json")
    if sorted(receipt["week_contributions_by_day"]) != [
        (datetime.fromisoformat(first).date() + timedelta(days=offset)).isoformat()
        for offset in range((end - datetime.fromisoformat(first).date()).days + 1)
    ]:
        raise ValueError("The new build does not cover every intended sitting date.")
    summary = {"requested": supplements, "successes": supplements, "exceptions": {}}
    dump(release / "supplement-status.json", summary)
    history_cache = getattr(args, "history_cache", None)
    if history_cache:
        historic_days = {day for day in receipt["week_contributions_by_day"] if day >= "2026-11-18"}
        if historic_days:
            final["history_backfill"] = collect(release, args.database, history_cache / "search", historic_days,
                                                getattr(args, "history_deadline", None))
    coverage = args.out / "coverage.json"
    final.update({
        "local_release": release.name,
        "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "observed_at": now(),
        "pilot_graph": read(report),
        "week_contributions_by_day": receipt["week_contributions_by_day"],
        "supplemental_searches": summary,
        "core_artifacts": receipt["artifacts"],
    })
    dump(coverage, final)
    stage(release, coverage, args.out / "site", args.database if history_cache else database, baseline,
          history_cache / "public" if history_cache else None)
    dump(args.out / "prepared.json", {"through": args.through, "snapshot": str(snapshot.resolve()),
                                      "people": str(people.resolve()), "coverage": str(coverage.resolve())})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--through", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-release", type=Path, default=ROOT / "releases/current")
    parser.add_argument("--base-coverage", type=Path, default=ROOT / "releases/final-coverage.json")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--people", type=Path)
    parser.add_argument("--reuse-capture", action="store_true",
                        help="Use the supplied sitting and Member snapshots without retrieving them again.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--demo-from", type=Path, help="Reuse verified earlier evidence from a published Pages directory.")
    parser.add_argument("--history-cache", type=Path, help="Cache targeted searches and prepare per-entity history.")
    parser.add_argument("--explorer", type=Path, default=ROOT.parent / "okf-explorer")
    prepare(parser.parse_args())
