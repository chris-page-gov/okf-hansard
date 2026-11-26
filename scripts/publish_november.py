"""Refresh and publish the November 2026 records, preserving the week demo."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from hashlib import file_digest
from html import escape
import json
from pathlib import Path
import subprocess
import tarfile
import time
from urllib.error import URLError
from uuid import uuid4

from backfill import collect
from build import build
from build_pages import LOCAL_TEXT, SITE
from capture import HOUSES, dump, fetch, now, query, sha
from descriptor_policy import validate_descriptor_size
from export_history import export_file
from model import checked_json, read_sittings
from okf_core import CORE_VERSION
from passages import build_locators
from people import declarations
from prepare_demo_week import ROOT, carry_history, read
from publish_demo_week import GIT_AUTH, PAGES_REMOTE, ZONE, git, matches_remote, pages_lock
from query import DEFAULT_DB, DEEP_DB, Index
from refresh import refresh
from stage_contribution_views import stage
from verify import check
from voice_evidence import EVIDENCE

FIRST = date(2026, 11, 1)
LAST = date(2026, 11, 30)
STATE = ROOT / ".work/november-2026"
CACHE = ROOT / ".work/history-cache"
ARCHIVE_URL = ("https://github.com/chris-page-gov/okf-hansard/releases/download/"
               "november-2026-history/november-2026-history.tar")
REPO = "chris-page-gov/okf-hansard"
ARCHIVE_TAG = "november-2026-history"
REQUIRED_NOVEMBER_ASSETS = (
    "index.html", "coverage.json", "history.html", "history.js", "history/index.json",
    "graph/okf-explorer.json", "okf-core.json", "walkthrough.html", "walkthrough.json",
    "walkthrough.svg", "walkthrough-mobile.svg", "core-walkthrough.html", "core-walkthrough.json",
    "core-walkthrough.svg", "core-walkthrough-mobile.svg", "okf/index.md", "okf/sittings.md",
    "okf-public-access.json", "checksums.json", "okf-bundle.yamlld.gz", ".well-known/okf.json",
    "llms.txt", "historical-downloads.html", "historical-downloads.json",
    "hansard.json", "ask.html", "ask.md", "ask.js",
)


def builder_fingerprint(root=ROOT):
    """Hash Python generators, profiles and static inputs used to render a site."""
    root = Path(root)
    paths = set((root / "scripts").rglob("*.py"))
    for directory in (root / "profile", root / "docs/pages"):
        paths.update(path for path in directory.rglob("*") if path.is_file())
    paths.update(path for path in (
        root / "docs/pages/site.css", root / "profile/domain.yaml", root / "profile/hansard-domain-v2.json",
        root / "pyproject.toml", root / "uv.lock", root / "compatibility/public-assets/manifest.json",
    ) if path.exists())
    compat = root / "compatibility/public-assets/november"
    if compat.exists():
        paths.update(path for path in compat.rglob("*") if path.is_file())
    rows = []
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(root.resolve())):
            raise ValueError(f"Unsafe November builder input: {path.relative_to(root)}")
        rows.append({"path": path.relative_to(root).as_posix(), "sha256": sha(path.read_bytes())})
    commitment = sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {"sha256": commitment, "files": rows}


def site_cache_identity(site, release, through, *, root=ROOT):
    site = Path(site)
    receipt = Path(release) / "receipt.json"
    catalogue = site / "checksums.json"
    if any(path.is_symlink() or not path.is_file() for path in (receipt, catalogue)):
        raise ValueError("Cannot bind the November cache to missing or unsafe inputs.")
    return {
        "schema": "hansard-november-site-cache.v1",
        "through": through,
        "release_receipt_sha256": sha(receipt.read_bytes()),
        "builder": builder_fingerprint(root),
        "checksums_sha256": sha(catalogue.read_bytes()),
    }


def validate_november_site(site, through=None, expected_release=None, expected_identity=None,
                           require_identity=False, root=ROOT):
    """Fail closed unless every required November entry point is checksummed and intact."""
    site = Path(site)
    if site.is_symlink() or not site.is_dir():
        raise ValueError("The November site must be a real directory.")
    validate_descriptor_size(site)
    manifest_path = site / "checksums.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("The November site has no regular checksum catalogue.")
    try:
        catalogue = read(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("The November checksum catalogue is invalid.") from exc
    if not isinstance(catalogue, dict):
        raise ValueError("The November checksum catalogue must be an object.")
    actual = set()
    for path in site.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"The November site contains a symbolic link: {path.relative_to(site)}")
        if path.is_file() and path.relative_to(site).as_posix() != "checksums.json":
            actual.add(path.relative_to(site).as_posix())
    if actual != set(catalogue):
        unlisted = sorted(actual - set(catalogue))
        absent = sorted(set(catalogue) - actual)
        raise ValueError(f"The November checksum catalogue does not cover the site (unlisted={unlisted}, absent={absent}).")
    required = list(REQUIRED_NOVEMBER_ASSETS)
    if through:
        required.append(f"history/days/{through}.json")
    missing = [name for name in required if name != "checksums.json" and name not in catalogue]
    if missing:
        raise ValueError("The November site is missing required checksummed assets: " + ", ".join(missing))
    for name, entry in catalogue.items():
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not isinstance(entry, dict):
            raise ValueError("The November checksum catalogue contains an unsafe asset reference.")
        path = site / rel
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(site.resolve()):
            raise ValueError(f"The November asset is missing or unsafe: {name}")
        raw = path.read_bytes()
        if entry.get("bytes") != len(raw) or entry.get("sha256") != sha(raw):
            raise ValueError(f"The November asset differs from its checksum catalogue: {name}")
    descriptor = read(site / "graph/okf-explorer.json")
    if (descriptor.get("schema") != "okf-explorer-large-corpus.v1"
            or descriptor.get("kind") != "okf-large-corpus"
            or not all(isinstance(descriptor.get(key), str) and descriptor[key]
                       for key in ("id", "version", "snapshot", "okf_version"))):
        raise ValueError("The November graph descriptor has no complete published identity.")
    if descriptor["okf_version"] != "0.3":
        raise ValueError("The November graph descriptor is not verified OKF 0.3.")
    if expected_release is not None:
        receipt = read(Path(expected_release) / "receipt.json")
        if descriptor["snapshot"] != "hansard-sha256-" + receipt["artifacts"]["okf-bundle.json"]["sha256"]:
            raise ValueError("The November graph descriptor belongs to a different verified release.")
        coverage = read(site / "coverage.json")
        if coverage.get("semantic_graph", {}).get("sha256") != receipt["artifacts"]["okf-bundle.yamlld"]["sha256"]:
            raise ValueError("The November coverage report belongs to a different verified release.")
    core = read(site / "okf-core.json")
    if core.get("okf_version") != "0.3" or not core.get("snapshot"):
        raise ValueError("The November compact descriptor has no verified Core 0.3 identity.")
    compact_case = read(site / "core-walkthrough.json")
    if compact_case.get("descriptor_sha256") != sha((site / "okf-core.json").read_bytes()):
        raise ValueError("The compact walkthrough is not bound to the published compact descriptor.")
    full_case = read(site / "walkthrough.json")
    if (full_case.get("descriptor_sha256") != sha((site / "graph/okf-explorer.json").read_bytes())
            or full_case.get("expected_identity") != {
                key: descriptor[key] for key in ("schema", "id", "version", "snapshot")}):
        raise ValueError("The full walkthrough is not bound to the published graph descriptor.")
    if require_identity and not isinstance(expected_identity, dict):
        raise ValueError("The prepared attempt has no site cache identity.")
    if expected_identity is not None:
        if expected_release is None or not through:
            raise ValueError("Cache identity verification requires its selected release and through-date.")
        if expected_identity != site_cache_identity(site, expected_release, through, root=root):
            raise ValueError("The November site cache identity differs from the prepared attempt.")
    if through:
        day = site / "history" / "days" / f"{through}.json"
        if not day.is_file():
            raise ValueError(f"The November site is missing the through-date record: {day.name}")
    return catalogue


def calendar(output):
    def by_house(house):
        rows, source = fetch(output, f"{house}.json",
                             query("/overview/calendar.json", year=2026, month="11", house=house))
        if any(row["House"] != house or row["ItemDate"][:7] != "2026-11" for row in rows):
            raise ValueError(f"Unexpected Parliament calendar results for {house}.")
        return house, {"dates": sorted({row["ItemDate"][:10] for row in rows}), "source": source}

    with ThreadPoolExecutor(max_workers=2) as workers:
        result = dict(workers.map(by_house, HOUSES))
    dump(output / "manifest.json", result)
    return {house: set(result[house]["dates"]) for house in HOUSES}


def checkpoint_day(snapshot, day, calendars, output, provisional):
    manifest = read(snapshot / "manifest.json")
    entries = {row["house"]: row for row in manifest["sittings"] if row["date"] == day}
    counts = {}
    for house in HOUSES:
        row = entries.get(house)
        scheduled = day in calendars[house]
        if (scheduled and not (row and row["roots"])) or (row and row["errors"]):
            raise ValueError(f"Waiting for a complete {house} source tree for {day}.")
        if row:
            for asset in row["sources"]:
                checked_json(snapshot, asset)
        counts[house] = {"status": "captured" if row and row["roots"] else "no calendar sitting",
                         "roots": len(row["roots"]) if row else 0, "contributions": 0}
    parts, records, divisions, _ = read_sittings(snapshot, {"sittings": list(entries.values())}, day, day)
    for record in records.values():
        counts[record["house"]]["contributions"] += 1
    dump(output / f"{day}.json", {"date": day, "verified_at": now(), "as_published_at": manifest["finished_at"],
                                  "publication_status": "provisional" if provisional else "observed",
                                  "houses": counts, "sections": len(parts), "divisions": len(divisions)})


def checksums(site):
    result = {}
    for file in sorted(site.rglob("*")):
        if not file.is_file():
            continue
        if file.is_symlink() or file.stat().st_size >= 100 * 1024 * 1024:
            raise ValueError(f"Invalid Pages asset: {file.name}")
        relative = file.relative_to(site).as_posix()
        if relative == "checksums.json":
            continue
        raw = file.read_bytes()
        if file.suffix != ".gz" and LOCAL_TEXT.search(raw):
            raise ValueError(f"Local address in public asset: {relative}")
        result[relative] = {"bytes": len(raw), "sha256": sha(raw)}
    dump(site / "checksums.json", result)
    return result


def publish(site, checkout, through, assets, expected_release=None, expected_identity=None):
    catalogue = validate_november_site(site, through, expected_release, expected_identity, require_identity=True)
    if assets != catalogue:
        raise ValueError("The supplied November asset list differs from the validated catalogue.")
    checks = ["checksums.json", *REQUIRED_NOVEMBER_ASSETS, f"history/days/{through}.json"]
    if EVIDENCE in assets:
        checks.append(EVIDENCE)
    checks = list(dict.fromkeys(checks))
    absent = [name for name in checks if name != "checksums.json" and name not in assets]
    if absent:
        raise ValueError("The November publication catalogue omits required assets: " + ", ".join(absent))
    with pages_lock():
        if git(checkout, "status", "--porcelain"):
            raise ValueError("The November Pages checkout contains other changes.")
        git(checkout, *GIT_AUTH, "fetch", PAGES_REMOTE, "gh-pages")
        git(checkout, "checkout", "--detach", "FETCH_HEAD")
        target = checkout / "november"
        target.mkdir(exist_ok=True)
        subprocess.run(["rsync", "-rc", "--delete", str(site) + "/", str(target) + "/"], check=True)
        git(checkout, "add", "--all", "--", "november")
        if git(checkout, "status", "--porcelain"):
            git(checkout, "diff", "--cached", "--check")
            git(checkout, "commit", "-m", f"Publish November Hansard through {through}")
        total = sum(int(line.split()[3]) for line in git(checkout, "ls-tree", "-rl", "HEAD").splitlines())
        if total >= 1_000_000_000:
            raise ValueError(f"The site exceeds the Pages size limit ({total:,} bytes).")
        commit = git(checkout, "rev-parse", "HEAD")
        git(checkout, *GIT_AUTH, "push", PAGES_REMOTE, "HEAD:refs/heads/gh-pages")
    catalogue = site / "checksums.json"
    with catalogue.open("rb") as stream:
        assets["checksums.json"] = {"bytes": catalogue.stat().st_size,
                                    "sha256": file_digest(stream, "sha256").hexdigest()}

    def matches(name):
        entry = assets[name]
        return matches_remote("november/" + name, entry["bytes"], entry["sha256"])

    expires = time.monotonic() + 540
    while time.monotonic() < expires:
        try:
            if matches("checksums.json") and all(matches(name) for name in checks[1:]):
                return {"commit": commit, "through": through, "verified_at": now(), "url": SITE + "november/",
                        "public_hash_samples": checks, "site_bytes": total}
        except (URLError, TimeoutError):
            pass
        time.sleep(15)
    raise RuntimeError("GitHub Pages has not served the expected November assets yet.")


def github_assets():
    raw = subprocess.check_output(["gh", "api", f"repos/{REPO}/releases/tags/{ARCHIVE_TAG}"], timeout=30)
    release = json.loads(raw)
    if release["draft"]:
        raise ValueError("The historical download is still being staged.")
    return {row["name"]: row for row in release["assets"]}


def checked_asset(asset, expected):
    return (asset and asset["state"] == "uploaded" and asset["size"] == expected["bytes"]
            and asset.get("digest") == "sha256:" + expected["sha256"])


def package_hashes(release):
    return {path.stem: sha(path.read_bytes()) for path in (release / "backfill").glob("*.json")
            if path.name != "manifest.json"}


def history_downloads(release, state, through):
    baseline = read(state / "archive-download.json")
    for _ in range(48):
        try:
            assets = github_assets()
        except (subprocess.SubprocessError, ValueError):
            assets = {}
        if checked_asset(assets.get(baseline["name"]), baseline):
            break
        time.sleep(15)
    else:
        raise RuntimeError("The verified baseline YAML-LD download is still awaiting GitHub.")

    downloads = state / "history-downloads.json"
    if downloads.is_file():
        ledger = read(downloads)
    else:
        ledger = {"hashes": package_hashes(Path(read(state / "seed.json")["release"])),
                  "downloads": [{**baseline, "label": "Initial historical YAML-LD snapshot", "url": ARCHIVE_URL}]}
    hashes = package_hashes(release)
    changes = {key: value for key, value in hashes.items() if ledger["hashes"].get(key) != value}
    if not changes:
        return ledger["downloads"]

    identity = sha(json.dumps(changes, sort_keys=True).encode())[:12]
    folder = state / "history-extensions" / identity
    folder.mkdir(parents=True, exist_ok=True)
    tar = folder / f"history-through-{through}-{identity}.tar"
    if not tar.is_file():
        partitions = {}
        index = Index(release, DEFAULT_DB, DEEP_DB)
        for key in sorted(changes):
            path = folder / f"{key}.yamlld.gz"
            count = export_file(index, "1803-11-22", "2026-11-01", [key], path, True)
            raw = path.read_bytes()
            partitions[key] = {"path": path.name, "assertions": count, "bytes": len(raw), "sha256": sha(raw)}
        manifest = folder / "manifest.json"
        dump(manifest, {"schema": "hansard-history-partitions.v1", "partitions": partitions})
        temporary = tar.with_suffix(".tmp")
        with tarfile.open(temporary, "w") as output:
            output.add(manifest, arcname=manifest.name)
            for item in partitions.values():
                output.add(folder / item["path"], arcname=item["path"])
        temporary.replace(tar)
    with tar.open("rb") as stream:
        metadata = {"name": tar.name, "label": f"Historical YAML-LD additions through {through}",
                    "url": ARCHIVE_URL.rsplit("/", 1)[0] + "/" + tar.name,
                    "bytes": tar.stat().st_size, "sha256": file_digest(stream, "sha256").hexdigest()}
    if not checked_asset(assets.get(tar.name), metadata):
        subprocess.run(["gh", "release", "upload", ARCHIVE_TAG, str(tar), "-R", REPO], check=True, timeout=900)
        if not checked_asset(github_assets().get(tar.name), metadata):
            raise RuntimeError("GitHub did not return the expected history extension digest.")
    ledger["hashes"].update(changes)
    ledger["downloads"].append(metadata)
    dump(downloads, ledger)
    return ledger["downloads"]


def write_downloads(site, downloads):
    dump(site / "historical-downloads.json", downloads)
    items = "".join(f'<li><a href="{escape(row["url"], quote=True)}">{escape(row["label"])}</a></li>'
                    for row in downloads)
    (site / "historical-downloads.html").write_text(f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Historical YAML-LD downloads</title><link rel="stylesheet" href="site.css"><link rel="icon" href="data:,"></head>
<body><main class="demo"><p><a href="./">November in Parliament</a></p><h1>Historical YAML-LD downloads</h1>
<p>Start with the initial snapshot. For entities included in a later download, use the newest partition. Each archive includes its own manifest.</p>
<ul>{items}</ul><p><a href="historical-downloads.json">File sizes and checksums</a></p></main></body></html>
""", encoding="utf-8")


def prepare(work, previous, limit, today, initial_capture):
    calendars = calendar(work / "calendar")
    snapshot = Path(previous["snapshot"])
    old_days = Path(previous["days"])
    days = work / "days"
    dates = [(FIRST + timedelta(days=n)).isoformat() for n in range((limit - FIRST).days + 1)]
    if initial_capture:
        snapshot = initial_capture
    for day in reversed(dates):
        prior = old_days / f"{day}.json"
        saved = read(prior) if prior.is_file() else None
        scheduled = any(day in calendars[house] for house in HOUSES)
        source_changed = saved and any(
            day in calendars[house] and not saved["houses"][house]["roots"] for house in HOUSES)
        if not initial_capture and scheduled and (
            not saved or saved["publication_status"] == "provisional" or source_changed
        ):
            refreshed = work / ("capture-" + day)
            if not refresh(snapshot, refreshed, {day}):
                raise ValueError(f"Waiting for all advertised sources on {day}.")
            snapshot = refreshed
        checkpoint_day(snapshot, day, calendars, days, day == today.isoformat())
    people = work / "people"
    directory = declarations(people, snapshot, FIRST.isoformat(), limit.isoformat(), Path(previous["people"]))
    if directory["errors"]:
        raise ValueError("One or more Member biographies are awaiting a retry.")
    release = work / "release"
    build(snapshot, people, release, ROOT / "profile/vocabulary.yaml", FIRST.isoformat(), limit.isoformat(),
          ROOT.parent / "okf-explorer", sharded_reader=True, title="November in Parliament")
    if not check(release, snapshot, people, release / "verification.json"):
        raise ValueError("The November graph failed relationship verification.")
    build_locators(snapshot, release)
    carry_history(Path(previous["release"]), release, DEFAULT_DB)
    result = {"format": CORE_VERSION, "through": limit.isoformat(), "snapshot": str(snapshot.resolve()), "days": str(days.resolve()),
              "people": str(people.resolve()), "release": str(release.resolve()), "site": str(work / "site")}
    dump(work / "prepared.json", result)
    return result


def run(state, checkout, initial_capture=None, through=None, *, attempts_root=None):
    today = datetime.now(ZONE).date()
    pointer = state / "publication.json"
    evening = state / "capture-2026-11-19-evening"
    if not pointer.is_file() and today == date(2026, 11, 19) and (evening / "manifest.json").is_file():
        initial_capture = initial_capture or evening
    initial = initial_capture is not None
    previous = read(pointer) if pointer.is_file() else read(state / "seed.json")
    limit = through or min(LAST, today if initial else today - timedelta(days=1))
    if through and (not initial_capture or not FIRST <= through <= min(LAST, today)):
        raise ValueError("Provide a verified snapshot and a November date through today.")
    if limit < FIRST or (pointer.is_file() and previous["through"] == LAST.isoformat()
                         and not previous["provisional"] and today > LAST):
        return
    if limit.isoformat() < previous["through"]:
        return
    if pointer.is_file() and previous["through"] == limit.isoformat() and not previous["provisional"]:
        return
    provisional = limit == today
    if attempts_root is not None and not attempts_root.is_dir():
        raise ValueError(f"The configured publication staging directory is unavailable: {attempts_root}")
    candidates = (attempts_root or state / "publication-attempts") / limit.isoformat()
    cached = next(((path, candidate) for path in sorted(candidates.glob("*/prepared.json"), reverse=True)
                   if (candidate := read(path)).get("format") == CORE_VERSION
                   and read(Path(candidate["days"]) / f"{limit.isoformat()}.json")["publication_status"]
                   == ("provisional" if provisional else "observed")), None)
    if cached:
        prepared_path, current = cached
    else:
        work = (candidates / datetime.now(ZONE).strftime("%H%M%S")).resolve()
        current = prepare(work, previous, limit, today, initial_capture)
        prepared_path = work / "prepared.json"
    release = Path(current["release"])
    days = set(read(release / "receipt.json")["week_contributions_by_day"])
    previous_result = release / "backfill/manifest.json"
    if not previous_result.is_file() or read(previous_result)["exceptions"]:
        history = collect(release, DEFAULT_DB, CACHE / "search", days,
                          datetime.now(ZONE) + timedelta(hours=5))
        if history["exceptions"]:
            raise RuntimeError(f"History incomplete for {len(history['exceptions'])} entities. Saved results are reusable.")
    site = Path(current["site"])
    try:
        validate_november_site(site, current["through"], release, current.get("site_identity"),
                               require_identity=True)
    except ValueError:
        attempt = site.parent / ("staging-" + datetime.now(ZONE).strftime("%H%M%S") + "-" + uuid4().hex[:8])
        attempt.mkdir(parents=True, exist_ok=False)
        output = attempt / "site"
        stage(release, Path(current["days"]), output, DEFAULT_DB, DEEP_DB, CACHE / "public",
              "historical-downloads.html", snapshot=Path(current["snapshot"]))
        write_downloads(output, history_downloads(release, state, current["through"]))
        checksums(output)
        current["site"] = str(output)
        current["site_identity"] = site_cache_identity(output, release, current["through"])
        site = output
    assets = validate_november_site(site, current["through"], release, current.get("site_identity"),
                                    require_identity=True)
    dump(prepared_path, current)
    remote = publish(site, checkout, current["through"], assets, release, current.get("site_identity"))
    dump(pointer, {**current, **remote, "provisional": provisional})
    print(f"{now()} Published and verified November through {current['through']}.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--checkout", type=Path, default=STATE / "pages-checkout")
    parser.add_argument("--attempts-root", type=Path,
                        help="Stage new attempts in an existing directory, for example on the SSD.")
    parser.add_argument("--initial-capture", type=Path)
    parser.add_argument("--verified-through", type=date.fromisoformat,
                        help="Use the supplied capture through this date.")
    args = parser.parse_args()
    run(args.state, args.checkout, args.initial_capture, args.verified_through, attempts_root=args.attempts_root)
