"""Normalise captured Hansard records and link conservative textual mentions."""

from collections import defaultdict
from dataclasses import dataclass, field
from html.parser import HTMLParser
import json
import re
from urllib.parse import quote

import yaml
from okf_core import PROFILE
from safe_paths import resolve_within, safe_component

from capture import HANSARD, sha

WEB = "https://hansard.parliament.uk"
LICENCE = "https://www.parliament.uk/site-information/copyright/open-parliament-licence/"
NS = "urn:okf:hansard:"
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
BREAK = re.compile(r"[.!?;]")
CLOCK = r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?"
TERM_TYPES = {
    "Legislation": ("Act", "Bill", "Statutory instrument", "Treaty"),
    "People": ("MP", "Peer", "Parliamentarian", "Public figure"),
    "Places": ("Constituency", "Country", "Nation", "Territory", "Region", "County", "City", "Town"),
    "Organisations": ("Government department", "Government", "Public body", "Regulator", "Company",
                      "Broadcaster", "International organisation", "Association", "Parliamentary committee"),
    "Things": ("Digital service", "Programme", "Review", "Infrastructure", "Technology", "Public office"),
    "Subjects": ("Subject",),
    "Offices": ("Government post", "Opposition post", "Other parliamentary post", "Presiding office"),
}
GROUP_BY_TYPE = {t: g for g, types in TERM_TYPES.items() for t in types}
TAG_LABELS = {
    "hs_8Correction": "Correction",
    "Question": "Question",
    "hs_6bFormalmotion": "Motion",
    "hs_Procedure": "Procedure",
    "Amendment": "Amendment",
}
VISUAL_TAGS = {"hs_ColumnNumber", "hs_6fDate", "hs_date", "hs_6fCntrItalHdg"}


class PlainText(HTMLParser):
    """Keep text inert and preserve separation between block elements."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif tag in ("p", "br", "li", "td", "tr", "div"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ("p", "li", "td", "tr", "div"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value):
    parser = PlainText()
    parser.feed(str(value or ""))
    parser.close()
    return " ".join("".join(parser.parts).split())


def tokens(text):
    return tuple(m.group().casefold() for m in TOKEN.finditer(text))


def display(value):
    return " ".join(str(value or "").split())


def checked_json(snapshot, source):
    raw = resolve_within(snapshot, source["path"]).read_bytes()
    if sha(raw) != source["sha256"]:
        raise ValueError(f"Capture digest mismatch for {source['path']}")
    return json.loads(raw)


@dataclass
class Entity:
    key: str
    kind: str
    label: str
    source: str | None
    aliases: list = field(default_factory=list)
    scheme: str = "pilot lexicon"

    @property
    def group(self):
        return GROUP_BY_TYPE[self.kind]

    @property
    def route(self):
        return f"entity/{self.key}.md"


def load_entities(snapshot, manifest, vocabulary):
    table = {}
    for key, kind, label, source, aliases in yaml.safe_load(vocabulary.read_text())["entities"]:
        key = key.lower()
        if key in table:
            raise ValueError(f"Duplicate entity {key}")
        table[key] = Entity(key, kind, label, source, aliases)

    for directory in manifest["directories"]:
        for source in directory["sources"]:
            rows = checked_json(snapshot, source)["items"]
            for row in rows:
                if directory["name"] == "bills":
                    key = f"bill-{row['billId']}"
                    kind = "Act" if row["isAct"] else "Bill"
                    # A former Bill title remains an alias on a legislative
                    # process only while the identity is represented as a Bill.
                    aliases = [row["formerShortTitle"]] if row.get("formerShortTitle") and not row["isAct"] else []
                    table.setdefault(key, Entity(key, kind, row["shortTitle"],
                                                 f"https://bills.parliament.uk/bills/{row['billId']}",
                                                 aliases, "Parliament Bills API"))
                    continue

                member = row["value"]
                member_id = member["id"]
                name = member["nameDisplayAs"]
                full_title = member.get("nameFullTitle")
                membership = member.get("latestHouseMembership") or {}
                kind = "MP" if membership.get("house") == 1 else "Peer"
                key = f"member-{member_id}"
                aliases = [full_title] if full_title else []
                if kind == "MP":
                    untitled = re.sub(r"^(?:(?:Dr|Sir|Dame|Mr|Ms|Mrs|Miss|Rt Hon)\s+)+", "", name)
                    if len(tokens(untitled)) >= 2:
                        aliases.append(untitled)
                table[key] = Entity(key, kind, name, f"https://members.parliament.uk/member/{member_id}",
                                    aliases, "Parliament Members API")
                if kind == "MP" and membership.get("membershipFromId") and membership.get("membershipFrom"):
                    constituency_id = membership["membershipFromId"]
                    key = f"constituency-{constituency_id}"
                    table[key] = Entity(
                        key, "Constituency", membership["membershipFrom"],
                        f"https://members.parliament.uk/constituency/{constituency_id}/overview",
                        [], "Parliament Members API",
                    )
    return table


class Matcher:
    """Longest unambiguous label matching, with inspectable literal spans."""

    def __init__(self, entities, excluded_aliases=()):
        excluded = {tokens(alias) for alias in excluded_aliases}
        candidate_keys = defaultdict(set)
        self.case_required = set()
        for entity in entities.values():
            for alias in [entity.label, *entity.aliases]:
                key = tokens(alias)
                if not key:
                    continue
                # Single-token constituency labels can also be town names.
                # They match only in an explicit constituency reference.
                if entity.kind == "Constituency":
                    for prefix in ("member for", "constituency of", "constituency of the"):
                        candidate_keys[tokens(prefix) + key].add(entity.key)
                    if len(key) == 1:
                        continue
                if len(key) == 1 and len(key[0]) < 3 and not alias.isupper():
                    continue
                candidate_keys[key].add(entity.key)
                if len(key) == 1 and alias.isupper() and len(alias) <= 8:
                    self.case_required.add(key)
        self.lookups = defaultdict(dict)
        self.ambiguities = {}
        for alias, keys in candidate_keys.items():
            if len(keys) == 1 and alias not in excluded:
                self.lookups[alias[0]][alias] = next(iter(keys))
            else:
                self.ambiguities[" ".join(alias)] = sorted(keys)
        self.lengths = {first: sorted({len(a) for a in candidates}, reverse=True)
                        for first, candidates in self.lookups.items()}

    def find(self, text):
        words = list(TOKEN.finditer(text))
        normalised = tuple(m.group().casefold() for m in words)
        index = 0
        while index < len(words):
            candidates = self.lookups.get(normalised[index], {})
            for length in self.lengths.get(normalised[index], ()):
                if index + length > len(words):
                    continue
                end = index + length
                alias = normalised[index:end]
                if alias not in candidates:
                    continue
                start_char, end_char = words[index].start(), words[end - 1].end()
                exact = text[start_char:end_char]
                if alias in self.case_required and not exact.isupper():
                    continue
                if length > 1 and BREAK.search(exact):
                    continue
                yield candidates[alias], {"start": start_char, "end": end_char, "exact": exact}
                index = end
                break
            else:
                index += 1


def debate_url(house, day, ext_id, title):
    label = "".join(ch for ch in title if ch.isalnum() or ch in "-(),")
    return f"{WEB}/{house}/{day}/debates/{ext_id}/{quote(label, safe='()-')}"


def contribution_kind(item, section):
    tag = item.get("HRSTag") or ""
    if section == "WMS":
        return "Written statement" if item.get("MemberId") or item.get("UIN") else "Written statement record"
    if section == "Petitions":
        return "Petition"
    if section == "Correction":
        return "Correction"
    if tag in TAG_LABELS:
        return TAG_LABELS[tag]
    if "Amendment" in tag or tag == "hs_TabledBy":
        return "Amendment"
    if item.get("MemberId") or item.get("AttributedTo"):
        return "Spoken contribution"
    return "Unattributed passage"


def capacity(attribution, entity):
    name = attribution.casefold()
    if "speaker" in name or "chairman of ways and means" in name or "chair of ways and means" in name:
        return "Presiding officer"
    if any(role in name for role in ("minister", "secretary of state", "attorney general", "solicitor general",
                                      "lord chancellor", "paymaster general")):
        return "Minister or law officer"
    if entity and entity.kind in ("MP", "Peer"):
        return entity.kind
    return "Capacity unrecorded"


def mention_roles(record, matcher):
    annotations = defaultdict(list)
    for key, span in matcher.find(record["text"]):
        annotations[key].append(span)
    return dict(annotations)


def read_sittings(snapshot, manifest, first_day, last_day, loader=checked_json):
    """Read all source roots once and bind every retained atom to a JSON pointer."""
    parts, records, divisions = {}, {}, {}
    metrics = defaultdict(lambda: defaultdict(int))
    versions = defaultdict(list)

    def visit(day, house, section, reference, tree, pointer, parent):
        overview = tree["Overview"]
        ext_id = safe_component(overview["ExtId"])
        key = f"{house.lower()}-{day}-{section.lower()}-{ext_id.lower()}"
        title = plain(overview["Title"])
        url = debate_url(house, day, ext_id, title)
        prior = versions[key]
        if prior:
            # Historical exports sometimes repeat a section or reuse its public
            # external ID for distinct adjacent sections. Check the payload,
            # then retain genuine variants under their source numeric IDs.
            if any(title == previous_title and tree["Items"] == previous["Items"]
                   and tree["ChildDebates"] == previous["ChildDebates"] for previous_title, previous in prior):
                metrics[(day, house)]["repeated_section_copies"] += 1
                return
            origin = safe_component(overview.get("Id") or sha(pointer.encode())[:16])
            key = f"{key}-section-{origin}"
            metrics[(day, house)]["shared_section_public_ids"] += 1
        prior.append((title, tree))
        route = f"debate/{key}.md"
        if route in parts:
            raise ValueError(f"Distinct discussions have the same public and numeric identifiers: {route}")
        parts[route] = {"title": title, "house": house, "day": day, "section": section,
                        "parent": parent, "capture": reference, "pointer": pointer, "url": url,
                        "ext_id": ext_id, "raw_title": overview["Title"], "volume": overview.get("VolumeNo"),
                        "source_version": overview.get("ContentLastUpdated"), "time_markers": []}
        scope = "Pilot week" if first_day <= day <= last_day else "Earlier record"
        for index, item in enumerate(tree["Items"]):
            item_type = item["ItemType"]
            if item_type == "Timestamp":
                clock = item.get("Value")
                if isinstance(clock, str) and re.fullmatch(CLOCK, clock):
                    parts[route]["time_markers"].append({
                        "value": f"{day}T{clock}", "source_item": index + 1,
                        "source_field": f"{pointer}/Items/{index}/Value",
                    })
            if item_type == "Division":
                division_id = item.get("ExternalId") or item["ItemId"]
                if scope == "Pilot week":
                    divisions[f"division/{key}-{safe_component(division_id)}.md"] = {
                        "part": route, "id": division_id, "capture": reference,
                        "pointer": f"{pointer}/Items/{index}", "item": item,
                    }
                metrics[(day, house)]["divisions"] += 1
                continue
            if item_type != "Contribution":
                metrics[(day, house)][item_type] += 1
                continue
            metrics[(day, house)]["source_contribution_items"] += 1
            text = plain(item["Value"])
            if not text or item.get("HRSTag") in VISUAL_TAGS:
                metrics[(day, house)]["layout_or_empty"] += 1
                continue
            ext = item.get("ExternalId")
            item_id = item.get("ItemId")
            locator = f"{pointer}/Items/{index}"
            identifier = safe_component(ext or item_id or sha(locator.encode())[:16]).lower()
            entry = f"contribution/{key}-{identifier}.md"
            if entry in records:
                # Real source can return repeated external IDs within a debate.
                # Preserve the distinct occurrence at its stable API item ID.
                if not item_id:
                    raise ValueError(f"Repeated contribution without API item ID: {entry}")
                entry = f"contribution/{key}-{identifier}-{safe_component(item_id)}.md"
                if entry in records:
                    raise ValueError(f"Reused contribution identity: {entry}")
                metrics[(day, house)]["repeated_external_id"] += 1
            attribution = item.get("AttributedTo")
            records[entry] = {
                "part": route, "scope": scope, "capture": reference, "pointer": locator, "day": day,
                "house": house, "section": section, "kind": contribution_kind(item, section),
                "member": item.get("MemberId"), "attributed_to": display(attribution),
                "raw_attribution": attribution,
                "external_id": ext, "source_item_id": item_id, "hrs_tag": item.get("HRSTag"),
                "uint": item.get("UIN"), "order": index, "text": text,
                "value_sha256": sha(str(item["Value"]).encode()), "normalised_sha256": sha(text.encode()),
                "url": url + (f"#contribution-{ext}" if ext else ""),
            }
            timecode = item.get("Timecode")
            if isinstance(timecode, str) and re.fullmatch(
                rf"{re.escape(day)}T{CLOCK}(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?", timecode,
            ):
                records[entry]["timecode"] = timecode
            metrics[(day, house)]["retained_passages"] += 1
        for index, child in enumerate(tree["ChildDebates"]):
            visit(day, house, section, reference, child, f"{pointer}/ChildDebates/{index}", route)

    for sitting in manifest["sittings"]:
        day = safe_component(sitting["date"])
        house = safe_component(sitting["house"])
        metrics[(day, house)]
        for root in sitting["roots"]:
            visit(day, house, safe_component(root["section"]), root,
                  loader(snapshot, root), "", None)
    return parts, records, divisions, metrics
