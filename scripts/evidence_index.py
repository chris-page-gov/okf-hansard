"""Render the small, self-contained Markdown evidence index for GitHub."""

import argparse
from collections import defaultdict
from html import escape
import json
from pathlib import Path

from capture import now, sha
from hansard_access import official, read, snapshot_id
from model import read_sittings


INDEX = "HANSARD-EVIDENCE.md"
MAX_BYTES = 32 * 1024
LICENCE = "https://www.parliament.uk/site-information/copyright/open-parliament-licence/"


def checked_asset(site, catalogue, name):
    raw = (site / name).read_bytes()
    if catalogue.get(name) != {"bytes": len(raw), "sha256": sha(raw)}:
        raise ValueError(f"The evidence index input differs from its staged checksums: {name}.")
    return raw


def latest_examples(snapshot, release, day):
    manifest = (snapshot / "manifest.json").read_bytes()
    if sha(manifest) != read(release / "receipt.json")["manifest_sha256"]:
        raise ValueError("The evidence index requires the verified source capture.")
    parts, records, _, _ = read_sittings(snapshot, json.loads(manifest), day, day)
    proceedings = defaultdict(list)
    for record in records.values():
        if record["day"] == day:
            proceedings[record["part"]].append(record)
    rows = []
    for house in ("Commons", "Lords"):
        routes = sorted((route for route in proceedings if parts[route]["house"] == house),
                        key=lambda route: (-len(proceedings[route]), route))
        for route in routes[:3]:
            ordered = sorted(proceedings[route], key=lambda row: row["order"])
            selected = next((row for row in ordered if row["attributed_to"] and len(row["text"]) >= 120), ordered[0])
            text = " ".join(selected["text"].split())
            if len(text) > 300:
                text = text[:300].rsplit(" ", 1)[0] + " …"
            title = escape(parts[route]["title"]).replace("[", r"\[").replace("]", r"\]")
            attribution = escape(selected["attributed_to"] or "Speaker unlabelled")
            rows.extend([f"- {house}. [{title}]({official(selected['url'])})",
                         f"  {attribution}. “{escape(text)}”"])
    return rows


def render_evidence_index(current):
    site = Path(current["site"])
    catalogue = read(site / "checksums.json")

    def load(name):
        return json.loads(checked_asset(site, catalogue, name))

    bundle = load("hansard.json")["bundles"][0]
    coverage = load("coverage.json")
    graph = load("graph/okf-explorer.json")
    checked_asset(site, catalogue, "history/index.json")
    capture = bundle["capture"]
    days = sorted(coverage["dates"], key=lambda row: row["date"])
    houses = ("Commons", "Lords")
    contributions = {row["date"]: sum(row["houses"][house]["contributions"] for house in houses) for row in days}
    sitting_dates = [day for day, count in contributions.items() if count]
    total = sum(contributions.values())
    if (not coverage["verification"]["passed"] or bundle["snapshot"] != snapshot_id(site, graph)
            or bundle["entrypoints"]["coverage"]["sha256"] != catalogue["coverage.json"]["sha256"]
            or not sitting_dates or sitting_dates != capture["sitting_dates"]
            or total != coverage["contributions"] or total != capture["contributions"]
            or capture["through"] != sitting_dates[-1]
            or days[-1]["date"] != current["through"]
            or any(row["publication_status"] != "observed" for row in days)):
        raise ValueError("The evidence index inputs disagree with the verified capture.")
    backfill = coverage["backfill"]
    latest = sitting_dates[-1]
    older = bundle.get("older_archive")
    lines = [
        "# Hansard evidence index", "",
        f"Verified capture through {current['through']}.",
        f"Latest sitting {latest}.",
        f"Snapshot `{bundle['snapshot']}`.", "",
        "Use the excerpts and exact Hansard links in this file to ground an answer. "
        "Give the sitting dates used and cite contributions for statements. "
        "This file contains selected evidence and counts from the public OKF+ 0.3 Hansard collection.", "",
        "## Coverage", "",
        f"{capture['contributions']:,} text contributions from Commons and Lords sittings "
        f"across {len(sitting_dates)} dates, from {sitting_dates[0]} to {latest}.", "",
        f"Historical alias checks ran from {backfill['from']} to {backfill['through']} inclusive. "
        f"{backfill['complete']:,} of {backfill['entities']:,} configured checks completed. "
        "A retained match records a name or alias. Check the linked passage for which subject it describes.",
    ]
    if older:
        ranges = older["ranges"].values()
        lines.extend(["", f"A separate matching profile covers processed sittings from "
                           f"{min(row[0] for row in ranges)} to {max(row[1] for row in ranges)} "
                           f"with {older['source_gaps']} recorded unresolved source gaps in that processed range."])
    lines.extend(["", "| Sitting date | Commons contributions | Lords contributions |",
                  "| --- | ---: | ---: |"])
    for row in days:
        if contributions[row["date"]]:
            counts = [row["houses"][house]["contributions"] for house in houses]
            lines.append(f"| {row['date']} | {counts[0]:,} | {counts[1]:,} |")
    lines.extend(["", f"## Selected evidence from {latest}", "",
                  "Up to three proceedings per House, ordered by the number of captured contributions. "
                  "Each link opens the quoted contribution.", "",
                  *latest_examples(Path(current["snapshot"]), Path(current["release"]), latest)])
    if worked := bundle.get("voice_evidence", {}).get("synergy-dwp"):
        raw = checked_asset(site, catalogue, "synergy-evidence.txt")
        if (worked["snapshot"] != bundle["snapshot"] or worked["sha256"] != sha(raw)
                or worked["bytes"] != len(raw)):
            raise ValueError("The Synergy example refers to a different evidence snapshot.")
        evidence = raw.decode("utf-8")
        head = evidence.splitlines()
        if head[1:3] != [f"Snapshot {bundle['snapshot']}", f"Latest sitting {latest}"]:
            raise ValueError("The Synergy example header does not match verified coverage.")
        _, context = evidence.split("\nProgramme and contract\n", 1)
        body = context.split("\nContribution timeline ", 1)[0].strip()
        lines.extend(["", "## Worked example — Synergy programme", "", head[3], "",
                      "Programme and contract", "", body])
    lines.extend(["", f"Contains Parliamentary information licensed under the "
                      f"[Open Parliament Licence v3.0]({LICENCE}).", ""])
    content = "\n".join(lines)
    if len(content.encode("utf-8")) > MAX_BYTES:
        raise ValueError("The Markdown evidence index exceeds its 32 KiB reading budget.")
    return content


def update_index(current):
    from sync_evidence_index import sync

    result = sync(render_evidence_index(current))
    print(f"{now()} Repository evidence index {result['status']} at {result['sha']}.", flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication", type=Path, required=True)
    options = parser.parse_args()
    print(render_evidence_index(read(options.publication)), end="")
