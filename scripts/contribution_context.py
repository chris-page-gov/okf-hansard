"""Render small, ordered windows onto the verified Hansard contribution capture."""

from collections import defaultdict
from html import escape
import json
import re
from urllib.parse import urlsplit

from capture import dump, sha
from context_dates import publish_dates
from model import read_sittings
from okf_core import LICENCE

SCHEMA = "hansard-contribution-context.v1"
PAGE_TURNS = 8
EXCERPT = 900
PAGE_BYTES = 64 * 1024
CONTEXT_PATH = re.compile(r"context/(\d{4}-\d{2}-\d{2})/[a-f0-9]{20}-[1-9]\d*\.html#turn-[1-9]\d*\Z")


def official(url):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "hansard.parliament.uk":
        raise ValueError("The retained evidence has an unexpected source URL.")
    return url


def sections(rows):
    result = defaultdict(list)
    for route, row in rows.items():
        result[row["part"]].append((route, row))
    for turns in result.values():
        turns.sort(key=lambda item: item[1]["order"])
        if len({row["order"] for _, row in turns}) != len(turns):
            raise ValueError("Ambiguous source order within a debate section.")
    return result


def turn_record(route, row, position):
    text = row["text"]
    truncated = len(text) > EXCERPT
    excerpt = text[:EXCERPT].rstrip() + " …" if truncated else text
    return {"id": route, "position": position, "source_position": row["order"],
            "speaker": row["attributed_to"], "member_id": row.get("member"),
            "hansard": official(row["url"]), "source_field": row["pointer"] + "/Value",
            "source_value_sha256": row["value_sha256"], "source_sha256": row["capture"]["sha256"],
            "text": excerpt, "truncated": truncated,
            **({"source_uin": row["uint"]} if row.get("uint") else {})}


def reviewed_links(release, receipt):
    count = receipt.get("assertions_by_predicate", {}).get("answeredBy", 0)
    result = defaultdict(list)
    if count:
        found = 0
        with (release / "okf-bundle.yamlld").open("rb") as graph:
            for line in graph:
                if not line.startswith(b"- ") or b'vocab:answeredBy"' not in line:
                    continue
                edge = json.loads(line[2:])
                if not edge.get("predicate", {}).get("@id", "").endswith(":vocab:answeredBy"):
                    continue
                found += 1
                question, reply = edge["source_route"], edge["target_route"]
                for source, target, label in ((question, reply, "Reviewed reply"), (reply, question, "Reviewed question")):
                    result[source].append({"id": target, "label": label, "assertion": edge["@id"]})
        if found != count:
            raise ValueError("Reviewed reply assertions disagree with the release receipt.")
    return result


def page_name(section, position):
    return f"{sha(section.encode())[:20]}-{(position - 1) // PAGE_TURNS + 1}.html"


def anchor(section, position):
    return page_name(section, position) + f"#turn-{position}"


def document(title, content):
    return ('<!doctype html><html lang="en-GB"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link rel="icon" href="data:,"><link rel="stylesheet" href="../../site.css">'
            '<style>main{max-width:52rem;margin:auto;padding:1rem;overflow-wrap:anywhere}'
            'article{border-top:1px solid;padding:.7rem}article:target{outline:3px solid currentColor}'
            'details{margin:.5rem 0}nav a{display:inline-block;padding:.5rem}</style>'
            f'<title>{escape(title)} · Hansard</title><main>{content}</main></html>\n')


def render_section(output, section, part, members, links, day_rows, snapshot):
    count = len(members)
    positions = {route: index for index, (route, _) in enumerate(members, 1)}
    for start in range(1, count + 1, PAGE_TURNS):
        stop = min(count, start + PAGE_TURNS - 1)
        title = part["title"]
        nav = ['<a href="index.html">Sections on this date</a>']
        if start > 1:
            nav.append(f'<a rel="prev" href="{anchor(section, start - 1)}">Earlier turns</a>')
        if stop < count:
            nav.append(f'<a rel="next" href="{anchor(section, stop + 1)}">Later turns</a>')
        body = [f'<nav>{" ".join(nav)}</nav><h1>{escape(title)}</h1>',
                f'<p>{escape(part["house"])} · {part["day"]} · Turns {start}–{stop} of {count} in this section.</p>',
                '<p>Hansard speaking order. A reviewed question or reply has its own link. '
                'Open Hansard for the full wording of any excerpt.</p>']
        for position in range(start, stop + 1):
            route, row = members[position - 1]
            turn = turn_record(route, row, position)
            if day_rows[route]["url"] != turn["hansard"]:
                raise ValueError("Context and finder disagree on the official contribution link.")
            day_rows[route]["context"] = "context/" + part["day"] + "/" + anchor(section, position)
            source = escape(turn["hansard"], quote=True)
            name = escape(turn["speaker"] or "Speaker unlabelled")
            if isinstance(turn["member_id"], int) and turn["member_id"] > 0:
                name = f'<a href="https://members.parliament.uk/member/{turn["member_id"]}/career">{name}</a>'
            uin = f' · Question {escape(str(turn["source_uin"]))}' if "source_uin" in turn else ""
            body.append(f'<article id="turn-{position}"><h2>Turn {position} · {name}{uin}</h2>'
                        f'<p>{escape(turn["text"])}</p><a href="{source}">'
                        f'{"Read the full passage" if turn["truncated"] else "Read this contribution"} in Hansard</a>')
            for link in links.get(route, []):
                target = positions[link["id"]]
                body.append(f' · <a data-assertion="{escape(link["assertion"], quote=True)}" '
                            f'href="{anchor(section, target)}">{link["label"]} · turn {target}</a>')
            body.append(f'<details><summary>Source evidence</summary><p>{escape(route)}<br>'
                        f'{escape(turn["source_field"])}<br>Source value SHA-256 {turn["source_value_sha256"]}'
                        '</p></details></article>')
        body.append(f'<footer><a href="{escape(official(part["url"]), quote=True)}">Hansard section</a>'
                    f' · <a href="{LICENCE}">Open Parliament Licence</a><details><summary>Capture and snapshot</summary>'
                    f'<p>Source file SHA-256 {part["capture"]["sha256"]}<br>{escape(snapshot)}</p></details></footer>')
        raw = document(title, "".join(body)).encode()
        if len(raw) > PAGE_BYTES:
            raise ValueError("Contribution context page exceeds the phone download limit.")
        path = output / page_name(section, start)
        with path.open("xb") as stream:
            stream.write(raw)


def publish_context(site, release, capture, snapshot):
    receipt = json.loads((release / "receipt.json").read_bytes())
    raw = (capture / "manifest.json").read_bytes()
    if sha(raw) != receipt["manifest_sha256"]:
        raise ValueError("Context source manifest differs from the release receipt.")
    sittings = json.loads(raw)["sittings"]
    links = reviewed_links(release, receipt)
    index = {"schema": SCHEMA, "snapshot": snapshot, "page_turns": PAGE_TURNS, "max_page_bytes": PAGE_BYTES,
             "excerpt_characters": EXCERPT, "contributions": 0, "days": {}}
    root = site / "context"
    root.mkdir()
    for day, expected in sorted(receipt["week_contributions_by_day"].items()):
        day_site = root / day
        day_site.mkdir()
        manifest = {"sittings": [s for s in sittings if s["date"] == day]}
        parts, rows, _, _ = read_sittings(capture, manifest, day, day)
        path = site / "history/days" / (day + ".json")
        finder = json.loads(path.read_bytes())
        if len(rows) != expected or rows.keys() != finder.keys():
            raise ValueError(f"The verified release, capture and finder disagree for {day}.")
        entries = []
        lookup = {}
        for section, members in sections(rows).items():
            part = parts[section]
            render_section(day_site, section, part, members, links, finder, snapshot)
            lookup[section] = {"stem": page_name(section, 1).split("-")[0],
                               "order": [row["order"] for _, row in members]}
            entries.append(f'<li><a href="{anchor(section, 1)}">{escape(part["title"])}</a>'
                           f' · {escape(part["house"])} · {len(members)} turns</li>')
        (day_site / "index.html").write_text(document(day, f'<h1>Contributions on {day}</h1><ul>'
                                                       + "".join(entries) + "</ul>"), encoding="utf-8")
        dump(day_site / "turns.json", {"snapshot": snapshot, "page_turns": PAGE_TURNS, "sections": lookup}, compact=True)
        dump(path, finder, compact=True)
        index["days"][day] = {"url": f"{day}/index.html", "turn_lookup": f"{day}/turns.json", "contributions": expected}
        index["contributions"] += expected
    publish_dates(root, index, json.loads((site / "coverage.json").read_bytes()))
    dump(root / "index.json", index)
