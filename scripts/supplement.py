"""Backfill new week entities with scoped official spoken-contribution searches."""

import argparse
from datetime import date
import json
from pathlib import Path
import re
from time import sleep
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from build import digest
from capture import dump
from capture import HANSARD, MAX_BYTES, now, sha
from model import Entity, Matcher, NS, debate_url, plain
from people import MEMBERS_API, active_on
from query import DEFAULT_RELEASE


def get(url):
    with urlopen(Request(url, headers={"Accept": "application/json",
                                       "User-Agent": "OKF-Hansard-Pilot/0.1"}), timeout=12) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Supplement source exceeds the response limit.")
    return json.loads(raw), {"url": url, "sha256": sha(raw), "retrieved_at": now()}


def scope(entity):
    key, label = entity.key, entity.label
    if entity.kind in {"Peer", "MP"}:
        member_id = int(key.split("-")[-1])
        biography, source = get(f"{MEMBERS_API}/Members/{member_id}/Biography")
        periods = biography["value"]["houseMemberships"]
        if entity.kind == "Peer":
            return label.split()[-1], periods, source
        text = re.sub(r"^(?:(?:Dr|Sir|Dame|Mr|Ms|Mrs|Miss|Rt Hon)\s+)+", "", label)
        return f'"{text}"', periods, source
    if entity.kind == "Constituency":
        constituency_id = int(key.split("-")[-1])
        identity, source = get(f"{MEMBERS_API}/Location/Constituency/{constituency_id}/Representations")
        dates = [r["representation"]["membershipStartDate"]
                 for r in identity["value"] if r["representation"]["membershipStartDate"]]
        periods = [{"startDate": min(dates), "endDate": None}] if dates else []
        return f'"{label}"', periods, source
    if entity.kind == "Bill" and key.startswith("bill-"):
        bill_id = int(key.split("-")[-1])
        stages, source = get(f"https://bills-api.parliament.uk/api/v1/Bills/{bill_id}/Stages")
        times = [sitting["date"] for stage in stages["items"] for sitting in stage["stageSittings"]]
        periods = [{"startDate": min(times), "endDate": None}] if times else []
        return f'"{label}"', periods, source
    raise ValueError("This supplement requires a source-identified Member, constituency or Bill.")


def supplement(release, key, since, until):
    roster = json.loads((release / "analysis-profile.json").read_bytes())["entities"]
    entity = Entity(key=key, **roster[key])
    search_term, periods, identity_source = scope(entity)
    if not periods:
        raise ValueError("The source returned no effective dates for this entity.")
    since = max(since, min(period["startDate"][:10] for period in periods if period.get("startDate")))
    if until < since:
        raise ValueError("The entity has no recorded effective dates in the requested window.")
    matcher = Matcher({key: entity})
    retained = {}
    sources = []
    counts = []
    offset = 0
    while True:
        query = urlencode({"searchTerm": search_term, "startDate": since, "endDate": until,
                           "skip": offset, "take": 20, "outputType": "List"})
        data, src = get(f"{HANSARD}/search/contributions/Spoken.json?{query}")
        sleep(.5)
        sources.append(src)
        counts.append(data["TotalResultCount"])
        results = data["Results"]
        for row_index, row in enumerate(results):
            day = row["SittingDate"][:10]
            if not any(active_on(p["startDate"], p["endDate"], day) for p in periods):
                continue
            text = plain(row.get("ContributionTextFull"))
            spans = [span for _, span in matcher.find(text)]
            ext = row["ContributionExtId"]
            ext_debate = row["DebateSectionExtId"]
            house = row["House"]
            if not spans or not ext or not ext_debate:
                continue
            part = f"debate/{house.lower()}-{day}-debate-{ext_debate.lower()}.md"
            route = f"contribution/{part.removeprefix('debate/').removesuffix('.md')}-{ext.lower()}.md"
            value_hash = sha(row["ContributionTextFull"].encode())
            url = debate_url(house, day, ext_debate, row["DebateSection"]) + f"#contribution-{ext}"
            retained[route] = {
                "contribution": route, "date": day, "house": house, "part": part, "url": url,
                "order": row["OrderInDebateSection"], "external_id": ext, "source_item_id": row["ItemId"],
                "source_value_sha256": value_hash, "capture": src, "spans": spans,
                "pointer": f"/Results/{row_index}", "source_field": f"/Results/{row_index}/ContributionTextFull",
                "assertion": NS + "supplement:" + digest(f"{route}|{key}")[:36],
            }
        offset += len(results)
        if offset >= data["TotalResultCount"]:
            break
        if not results or offset > 20000:
            raise ValueError("Search pagination is incomplete.")
    if len(set(counts)) != 1:
        raise ValueError("Search result coverage changed between pages.")
    package = {"schema": "hansard-supplemental-history.v1", "entity": key, "method": "spoken contribution search",
               "from": since, "through": until, "retrieved_at": now(), "returned_candidates": offset,
               "identity_source": identity_source, "periods": periods, "sources": sources,
               "items": sorted(retained.values(), key=lambda row: (row["date"], row["order"]), reverse=True)}
    output = release / "supplemental"
    output.mkdir(exist_ok=True)
    dump(output / f"{key}.json", package)
    print(f"{key}: retained {len(retained)} of {offset} candidates.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("entity")
    p.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    p.add_argument("--from-date", type=date.fromisoformat, required=True)
    p.add_argument("--to-date", type=date.fromisoformat, required=True)
    args = p.parse_args()
    supplement(args.release, args.entity, args.from_date.isoformat(), args.to_date.isoformat())
