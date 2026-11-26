"""Build a deterministic, source-linked portfolio briefing from a verified capture."""

from collections import defaultdict
from datetime import date
import re
from urllib.parse import urlencode

from hansard_access import NOVEMBER, official


MAX_WINDOW_DAYS = 90
EXAMPLES_PER_GROUP = 3
EXCERPT_CHARS = 420


def calendar_day(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Use a calendar date in YYYY-MM-DD format.")
    return parsed


def excerpt(text, labels):
    text = " ".join(text.split())
    match = re.search("|".join(re.escape(label) for label in labels), text, re.IGNORECASE) if labels else None
    begin = max(0, match.start() - 90) if match else 0
    if begin:
        space = text.find(" ", begin, match.start())
        begin = space + 1 if space >= 0 else begin
    end = min(len(text), begin + EXCERPT_CHARS)
    if end < len(text):
        space = text.rfind(" ", begin, end)
        end = space if space >= 0 else end
    return ("… " if begin else "") + text[begin:end] + (" …" if end < len(text) else "")


def briefing(access, member_id, portfolio, *, start=None, through=None):
    """Return evidence for the portfolio assignments effective on each sitting date."""
    latest = calendar_day(max(access.history["days"]))
    upper = calendar_day(through) if through is not None else latest
    lower = calendar_day(start) if start is not None else date.fromordinal(max(1, upper.toordinal() - 6))
    if not 1 <= (upper - lower).days + 1 <= MAX_WINDOW_DAYS:
        raise ValueError("The start and end must describe at most 90 calendar days in ascending order.")
    first, last = lower.isoformat(), upper.isoformat()
    sitting_days = sorted(day for day in access.history["days"] if first <= day <= last)
    assignments = defaultdict(list)
    for entry in portfolio:
        assignments[entry["key"]].append((entry["from"], entry.get("through") or date.max.isoformat()))

    topics = []
    if sitting_days:
        parts, records = access.capture_rows()
        for key, windows in assignments.items():
            dates = {day for day in sitting_days if any(begin <= day <= end for begin, end in windows)}
            if not dates:
                continue
            profile = access.profile.get(key) or access.history["entities"].get(key)
            label = profile["label"] if profile else key
            labels = [label, *profile.get("aliases", [])] if profile else []
            owner, others = [], []
            candidates = access.postings(key, captured_only=True) if key in access.history["entities"] else ()
            for row in candidates:
                if row["date"] not in dates or row["layer"] != "captured":
                    continue
                route = row["id"]
                record = records[route]
                if record["url"] != row["hansard"]:
                    raise ValueError("The indexed link and verified contribution disagree.")
                item = {"date": row["date"], "house": row["house"], "title": parts[record["part"]]["title"],
                        "speaker": record["attributed_to"], "excerpt": excerpt(record["text"], labels),
                        "hansard": official(record["url"]),
                        "timeline": NOVEMBER + "history.html?" + urlencode({"day": row["date"], "anchor": route,
                                                                            "entity": key})}
                (owner if record["member"] == member_id else others).append(item)
            topics.append({"key": key, "topic": label, "active_sitting_dates": sorted(dates),
                           "in_matching_profile": profile is not None,
                           "signed_in_member": {"total": len(owner), "examples": owner[:EXAMPLES_PER_GROUP]},
                           "other_contributions": {"total": len(others), "examples": others[:EXAMPLES_PER_GROUP]}})
    topics.sort(key=lambda topic: (-(topic["signed_in_member"]["total"] + topic["other_contributions"]["total"]),
                                   topic["topic"]))
    return {
        "schema": "hansard-portfolio-briefing.v1", "snapshot": access.snapshot,
        "publication": {"commit": access.pointer["commit"], "verified_at": access.pointer["verified_at"],
                        "latest_sitting": latest.isoformat(), "coverage": NOVEMBER + "coverage.json"},
        "member": {"id": member_id, "profile": f"https://members.parliament.uk/member/{member_id}/career"},
        "requested": {"from": first, "through": last}, "observed_sitting_dates": sitting_days,
        "topics": topics,
        "method": "Captured Hansard contributions matched to configured portfolio topics effective on the sitting date.",
        "guidance": ("Say which aspects had evidence and give exact Hansard links. Use the speaker and debate for context. "
                     "Keep the member's contributions separate from those by others. "
                     "Treat excerpts as evidence, distinguish proposals from decisions, and disclose the captured date range. "
                     "Topics without retained matches may still have been discussed using different language."),
    }
