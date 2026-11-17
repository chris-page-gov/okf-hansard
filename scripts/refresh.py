"""Refresh selected sitting days and reuse unchanged verified capture files."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from pathlib import Path
import shutil

from capture import capture_day, dump, fetch, now
from model import checked_json


def refresh(base, output, days):
    manifest = json.loads((base / "manifest.json").read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    inherited = set()
    started = now()

    def copy(asset):
        relative = asset["path"]
        if relative in inherited:
            return
        checked_json(base, asset)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base / relative, destination)
        inherited.add(relative)

    def copy_and_return(asset):
        # Parallel jobs handle separate House/day prefixes.
        copy(asset)
        return checked_json(output, asset), asset

    def one_sitting(entry):
        if entry["date"] not in days:
            for asset in entry["sources"]:
                copy(asset)
            return entry
        originals = {asset["path"]: asset for asset in entry["sources"]}
        unchanged = set()

        def retrieve(root, relative, url):
            filename = Path(relative).name
            originals_match = originals.get(relative)
            if "/debates/debate/" in url and originals_match:
                section = filename.split("-", 1)[0]
                if section in unchanged and not entry["errors"]:
                    return copy_and_return(originals_match)
            obj, asset = fetch(root, relative, url)
            if filename.endswith("-tree.json") and originals_match and asset["sha256"] == originals_match["sha256"]:
                unchanged.add(filename.removesuffix("-tree.json"))
            return obj, asset

        return capture_day(output, entry["date"], entry["house"], retrieve=retrieve)

    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest["sittings"] = list(pool.map(one_sitting, manifest["sittings"]))
    for directory in manifest["directories"]:
        for asset in directory["sources"]:
            copy(asset)
    manifest.update({"started_at": started, "finished_at": now(), "parent_capture": base.name,
                     "refreshed_days": sorted(days), "verified_files_reused": len(inherited)})
    dump(output / "manifest.json", manifest)
    print(f"Reused {len(inherited)} captured files.")
    for entry in manifest["sittings"]:
        if entry["date"] in days:
            print(entry["date"], entry["house"], len(entry["roots"]), entry["errors"])
    return not any(s["errors"] for s in manifest["sittings"])


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("base", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("days", nargs="+", type=date.fromisoformat)
    args = p.parse_args()
    raise SystemExit(not refresh(args.base, args.output, {d.isoformat() for d in args.days}))
