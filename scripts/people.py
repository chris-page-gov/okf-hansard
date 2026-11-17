"""Capture Parliament's dated posts, biographies and constituency representations."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
from pathlib import Path

from capture import dump, fetch, now
from model import checked_json, read_sittings, tokens

MEMBERS_API = "https://members-api.parliament.uk/api"
POST_SERIES = {"governmentPosts": "Government post", "oppositionPosts": "Opposition post",
               "otherPosts": "Other parliamentary post"}
ROLES = {"Government post", "Opposition post", "Other parliamentary post", "Presiding office"}


def active_on(start, end, day):
    # Source dates have day precision. Exclude handover days with an end date
    # as safe evidence for a uniquely identified incumbent.
    return bool(start and start[:10] <= day and (not end or day < end[:10]))


def biography(snapshot, member_id):
    return fetch(snapshot, f"people/member-{member_id}.json",
                 f"{MEMBERS_API}/Members/{member_id}/Biography")


def declarations(snapshot, source, first, last):
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

    def retrieve(member_id):
        try:
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first", type=date.fromisoformat, required=True)
    parser.add_argument("--last", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    manifest = declarations(args.output, args.snapshot, args.first.isoformat(), args.last.isoformat())
    print(f"{len(manifest['biographies'])} biographies, {len(manifest['errors'])} source errors.")


if __name__ == "__main__":
    main()
