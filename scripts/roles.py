"""Resolve UK Parliament office and constituency labels at a supplied date."""

import argparse
from datetime import date
import json
from pathlib import Path

from model import checked_json, tokens
from people import active_on, office_evidence, resolve_office


def resolve(snapshot, label, when, kind):
    offices, appointments, manifest = office_evidence(snapshot)
    if when > manifest["finished_at"][:10]:
        raise ValueError("The date lies after the captured office and biography snapshot.")
    labels = {}
    if kind == "office":
        hits = resolve_office(label, when, offices, appointments)
        matches = [(series, post_id) for (series, post_id), office in offices.items()
                   if any(tokens(a.removeprefix("The ")) == tokens(label.removeprefix("The "))
                          for a in (office["label"], office["hansard_label"]) if a)]
        for register, receipt in manifest["registers"].items():
            series = "governmentPosts" if register == "GovernmentPosts" else "oppositionPosts"
            for ri, row in enumerate(checked_json(snapshot, receipt)):
                value = row["value"]
                if (series, value["id"]) not in matches:
                    continue
                for hi, holder in enumerate(value["postHolders"]):
                    if active_on(holder["startDate"], holder.get("endDate"), when):
                        person = holder["member"]["value"]
                        labels[person["id"]] = person["nameDisplayAs"]
                        hits.append({"member": person["id"], "series": series,
                                     "entity_id": value["id"], "name": value["name"],
                                     "start": holder["startDate"], "end": holder.get("endDate"),
                                     "source": receipt, "source_field": f"/{ri}/value/postHolders/{hi}"})
    else:
        constituency = label
        for prefix in ("the Member for ", "Member for ", "MP for "):
            if constituency.casefold().startswith(prefix.casefold()):
                constituency = constituency[len(prefix):]
                break
        hits = [row for row in appointments if row["series"] == "representations"
                and (str(row["entity_id"]) == constituency or tokens(row["name"]) == tokens(constituency))
                and active_on(row["start"], row["end"], when)]
    members = sorted({row["member"] for row in hits})
    return {
        "schema": "hansard-dated-role.v1", "kind": kind, "source_label": label, "as_of": when,
        "status": "unique captured match" if len(members) == 1 else ("ambiguous" if members else "unresolved"),
        "capture_finished_at": manifest["finished_at"],
        "coverage": "Captured post registers and biographies of identified Members in the pilot week.",
        "member_ids": members,
        "members": [{"id": member_id, "label": labels.get(member_id),
                     "profile_url": f"https://members.parliament.uk/member/{member_id}",
                     "biography_api": f"https://members-api.parliament.uk/api/Members/{member_id}/Biography"}
                    for member_id in members],
        "sources": [{key: row[key] for key in ("member", "series", "entity_id", "name", "start",
                                              "end", "source", "source_field")} for row in hits],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--kind", choices=("office", "constituency"), required=True)
    parser.add_argument("--people", type=Path, default=Path(".snapshots/members-current"))
    args = parser.parse_args()
    print(json.dumps(resolve(args.people, args.label, args.as_of.isoformat(), args.kind),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
