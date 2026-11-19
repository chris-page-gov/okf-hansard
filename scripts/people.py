"""Capture Parliament's dated posts, biographies and constituency representations."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from functools import lru_cache
import json
from pathlib import Path
import shutil
from urllib.request import Request, urlopen

from capture import MAX_BYTES, dump, fetch, now, sha
from model import checked_json, read_sittings, tokens

MEMBERS_API = "https://members-api.parliament.uk/api"
POST_SERIES = {"governmentPosts": "Government post", "oppositionPosts": "Opposition post",
               "otherPosts": "Other parliamentary post"}
ROLES = {"Government post", "Opposition post", "Other parliamentary post", "Presiding office"}


def member_career_url(member_id):
    if type(member_id) is not int or member_id < 1:
        raise ValueError("Expected a positive Parliament Member ID.")
    return f"https://members.parliament.uk/member/{member_id}/career"


def active_on(start, end, day):
    # Source dates have day precision. Exclude handover days with an end date
    # as safe evidence for a uniquely identified incumbent.
    return bool(start and start[:10] <= day and (not end or day < end[:10]))


def biography(snapshot, member_id):
    return fetch(snapshot, f"people/member-{member_id}.json",
                 f"{MEMBERS_API}/Members/{member_id}/Biography")


def declarations(snapshot, source, first, last, previous=None):
    manifest = json.loads((source / "manifest.json").read_bytes())
    _, records, _, _ = read_sittings(source, manifest, first, last)
    member_ids = sorted({r["member"] for r in records.values()
                         if r["scope"] == "Pilot week" and r["member"]})
    snapshot.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": "hansard-people-capture.v1", "started_at": now(),
                "biographies": {}, "registers": {}, "errors": {}}
    for name in ("GovernmentPosts", "OppositionPosts"):
        _, receipt = fetch(snapshot, f"people/{name}.json", f"{MEMBERS_API}/Posts/{name}")
        manifest["registers"][name] = receipt

    previous_assets = (json.loads((previous / "manifest.json").read_bytes())["biographies"]
                       if previous else {})

    def retrieve(member_id):
        try:
            previous_asset = previous_assets.get(str(member_id))
            if previous_asset:
                checked_json(previous, previous_asset)
                destination = snapshot / previous_asset["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(previous / previous_asset["path"], destination)
                return str(member_id), previous_asset, None
            _, receipt = biography(snapshot, member_id)
            return str(member_id), receipt, None
        except (OSError, ValueError) as exc:
            return str(member_id), None, str(exc)

    with ThreadPoolExecutor(max_workers=4) as pool:
        for member_id, receipt, error in pool.map(retrieve, member_ids):
            if receipt:
                manifest["biographies"][member_id] = receipt
            else:
                manifest["errors"][member_id] = error
    manifest["finished_at"] = now()
    dump(snapshot / "manifest.json", manifest)
    return manifest


def office_evidence(snapshot):
    if snapshot is None:
        return {}, [], None
    manifest = json.loads((snapshot / "manifest.json").read_bytes())
    offices, appointments = {}, []
    for name, receipt in manifest["registers"].items():
        series = "governmentPosts" if name == "GovernmentPosts" else "oppositionPosts"
        for wrapper in checked_json(snapshot, receipt):
            value = wrapper["value"]
            offices[(series, value["id"])] = {
                "label": value["name"], "hansard_label": value.get("hansardName"),
                "source": receipt["url"], "kind": POST_SERIES[series], "series": series,
            }
    for member_id, receipt in manifest["biographies"].items():
        data = checked_json(snapshot, receipt)["value"]
        for series in [*POST_SERIES, "representations", "partyAffiliations", "houseMemberships"]:
            for index, entry in enumerate(data.get(series, [])):
                entity_id = entry["id"]
                if series in POST_SERIES:
                    offices.setdefault((series, entity_id), {
                        "label": entry["name"], "hansard_label": None, "source": receipt["url"],
                        "kind": POST_SERIES[series], "series": series,
                    })
                appointments.append({"member": int(member_id), "series": series, "entity_id": entity_id,
                                     "name": entry["name"], "start": entry["startDate"],
                                     "end": entry["endDate"], "source": receipt,
                                     "source_field": f"/value/{series}/{index}", "value": entry})
    return offices, appointments, manifest


def resolve_office(office_label, day, offices, appointments):
    candidates = {key for key, office in offices.items()
                  if any(tokens(label.removeprefix("The ")) == tokens(office_label.removeprefix("The "))
                         for label in (office["label"], office["hansard_label"]) if label)}
    return [row for row in appointments
            if (row["series"], row["entity_id"]) in candidates
            and active_on(row["start"], row["end"], day)]


@lru_cache(maxsize=64)
def current_biography(member_id, observation_hour):
    url = f"{MEMBERS_API}/Members/{member_id}/Biography"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "OKF-Hansard-Pilot/0.1"})
    with urlopen(request, timeout=12) as response:
        if response.url != url:
            raise ValueError("The Members API endpoint redirected.")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Members API response exceeds the read limit.")
    return json.loads(raw), {"url": url, "sha256": sha(raw), "retrieved_at": now()}


def member_as_of(snapshot, member_id, day):
    if type(member_id) is not int or not 1 <= member_id <= 100000:
        raise ValueError("Use a source-assigned positive integer Member ID.")
    requested = date.fromisoformat(day)
    current = datetime.now(timezone.utc)
    if requested > current.date():
        raise ValueError("The requested effective date is in the future.")
    manifest = json.loads((snapshot / "manifest.json").read_bytes())
    receipt = manifest["biographies"].get(str(member_id))
    if receipt and receipt["retrieved_at"][:10] >= day:
        data = checked_json(snapshot, receipt)
        mode = "captured biography"
    else:
        data, receipt = current_biography(member_id, current.isoformat(timespec="hours"))
        mode = "official biography retrieved on demand"
    series_rows = []
    for series in ("representations", "houseMemberships", *POST_SERIES, "partyAffiliations", "committeeMemberships"):
        for index, row in enumerate(data["value"].get(series, [])):
            if active_on(row.get("startDate"), row.get("endDate"), day):
                series_rows.append({"series": series, "id": row.get("id"), "label": row.get("name"),
                                    "effective_from": row["startDate"], "effective_to": row.get("endDate"),
                                    "house": row.get("house"), "source_field": f"/value/{series}/{index}",
                                    "detail": row.get("additionalInfo"), "detail_source": row.get("additionalInfoLink")})
    return {"schema": "hansard-member-as-of.v1", "member_id": member_id, "as_of": day, "mode": mode,
            "status": "dated entries found" if series_rows else "no captured entries active on this date",
            "profile_url": f"https://members.parliament.uk/member/{member_id}",
            "source": receipt, "entries": series_rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first", type=date.fromisoformat, required=True)
    parser.add_argument("--last", type=date.fromisoformat, required=True)
    parser.add_argument("--reuse", type=Path)
    args = parser.parse_args()
    manifest = declarations(args.output, args.snapshot, args.first.isoformat(), args.last.isoformat(), args.reuse)
    print(f"{len(manifest['biographies'])} biographies, {len(manifest['errors'])} source errors.")


if __name__ == "__main__":
    main()
