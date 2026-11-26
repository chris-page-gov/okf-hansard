"""Assemble a small, source-linked worked example from one verified capture."""

from datetime import date
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from capture import sha
from hansard_access import NOVEMBER, mention_postings, read
from model import read_sittings


EVIDENCE = "synergy-evidence.txt"
CONCEPT = "synergy-dwp"
CONTEXT = Path(__file__).resolve().parents[1] / "docs/pages/synergy-context.txt"
LICENCE = "https://www.parliament.uk/site-information/copyright/open-parliament-licence/"
EXCERPT_STARTS = {
    "1c38a799-dcb2-4c84-b75b-f4cc17102aaf": ("Synergy is a programme",),
    "e6dd9520-0578-40fb-bf50-bb08418b8e15": ("I have five specific requests",),
    "315a45fd-8d44-4dc1-a49e-ad7d7e53859b": ("Preparation for the Synergy transition", "The current SSCL contracts"),
    "c5d39272-f04c-4c72-b5aa-e873b1d845d8": ("I urge",),
}


def human_date(value):
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {parsed:%B %Y}"


def quote_passage(record):
    text = " ".join(record["text"].split())
    if len(text) <= 900:
        return [text]
    centres = EXCERPT_STARTS.get(record["external_id"].lower(), ("Synergy",))
    excerpts = []
    for centre in centres:
        match = re.search(re.escape(centre), text, re.IGNORECASE)
        start = match.start() if match else max(0, text.lower().find("synergy") - 75)
        stop = min(start + 620, len(text))
        if stop < len(text):
            stop = text.rfind(" ", start, stop)
        excerpts.append(("… " if start else "") + text[start:stop] + (" …" if stop < len(text) else ""))
    return excerpts


def coverage_details(coverage, history, days):
    backfill = coverage["backfill"]
    first, last = human_date(backfill["from"]), human_date(backfill["through"])
    lines = [
        f"Capture contains {coverage['contributions']:,} text contributions on {len(days)} sitting dates "
        f"from {human_date(days[0])} to {human_date(days[-1])}.",
        "Sitting dates (ISO) " + ", ".join(days) + ".",
        "A House marked ‘no calendar sitting’ had no sitting listed in the official parliamentary "
        "calendar for that date. Missing required sources for a scheduled House stop publication.",
        f"Configured historical checks ran from {first} to {last} inclusive. "
        f"{backfill['complete']:,} of {backfill['entities']:,} entity checks completed.",
    ]
    archive = backfill.get("archive")
    if archive:
        start = human_date(max(row[0] for row in archive.values()))
        end = human_date(min(row[1] for row in archive.values()))
        indexed = backfill["archive_entities"]
        lines.append(f"The main local archive supplies matches from {start} to {end} for "
                     f"{indexed:,} entities in its matching profile. The official Hansard search fills "
                     "the windows outside that span for those entities and checks the full historical "
                     "window for entities outside the archive profile.")
    if older := history.get("older_archive"):
        ranges = older["ranges"].values()
        lines.append(f"A separate older index uses its own matching profile. Its processed House sittings "
                     f"span {human_date(min(row[0] for row in ranges))} to {human_date(max(row[1] for row in ranges))}. "
                     f"It records {older['source_gaps']} unresolved source gaps in that processed range.")
    lines.append("Source verification and capture scope are recorded in the coverage file linked below.")
    lines.append("Historical matches use configured names and aliases. A matched name alone does not establish the programme identity.")
    return lines


def write_evidence(site, release, capture, coverage, history, snapshot):
    manifest = (capture / "manifest.json").read_bytes()
    if sha(manifest) != read(release / "receipt.json")["manifest_sha256"]:
        raise ValueError("The worked evidence requires the verified sitting capture.")
    postings = mention_postings(site, CONCEPT, history["entities"][CONCEPT])
    captured = [row for row in postings if row["layer"] == "captured"]
    previous = [row for row in postings if row["layer"] != "captured"]
    days = history["days"]
    parts, records, _, _ = read_sittings(capture, json.loads(manifest),
                                         min(row["date"] for row in captured), max(row["date"] for row in captured))
    timeline = NOVEMBER + "history.html?" + urlencode({"entity": CONCEPT})
    sections = [
        "Synergy programme in Hansard",
        f"Snapshot {snapshot}",
        f"Latest sitting {days[-1]}",
        f"{len(postings)} distinct retained Hansard links. {len(captured)} captured contributions and "
        f"{len(previous)} historical alias matches.",
        "",
        *coverage_details(coverage, history, days),
        "",
        CONTEXT.read_text(encoding="utf-8").strip(),
        "",
        "Captured contributions and Hansard excerpts",
    ]
    for source in sorted(captured, key=lambda row: (row["date"], records[row["id"]]["order"])):
        record = records[source["id"]]
        if record["url"] != source["hansard"]:
            raise ValueError("A worked example's source link differs from the captured passage.")
        venue = "Commons, Westminster Hall" if record["section"] == "WestHall" else source["house"]
        sections.extend(("", f"{human_date(source['date'])} · {venue} · {source['speaker']}",
                         parts[record["part"]]["title"], source["hansard"],
                         *(f"“{excerpt}”" for excerpt in quote_passage(record))))
    sections.extend(("", "Earlier alias matches",
                     "These links are candidates identified by the historical matcher.",
                     f"The main local archive supplies {sum(row['layer'] == 'archive' for row in previous)}. "
                     f"The older index supplies {sum(row['layer'] == 'older archive' for row in previous)}."))
    sections.extend(f"- {human_date(row['date'])} · {row['house']} · {row['speaker'] or 'Speaker unlabelled'} · {row['hansard']}"
                    for row in previous)
    sections.extend(("", f"Contribution timeline {timeline}", f"Coverage {NOVEMBER}coverage.json",
                     f"Contains Parliamentary information licensed under the Open Parliament Licence v3.0 {LICENCE}", ""))
    content = "\n".join(sections)
    (site / EVIDENCE).write_text(content, encoding="utf-8")
    return content
