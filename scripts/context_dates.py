"""Publish a bounded set of static, inclusive calendar ranges for phone readers."""

from collections import defaultdict
from datetime import date
from operator import itemgetter

from capture import dump


def publish_dates(root, index, coverage):
    """Emit at most 496 tiny range catalogues per month, sharing the same evidence pages."""
    months = defaultdict(list)
    total = 0
    for row in sorted(coverage["dates"], key=itemgetter("date")):
        day = date.fromisoformat(row["date"])
        key = day.isoformat()
        count = sum(house["contributions"] for house in row["houses"].values())
        if count != index["days"].get(key, {}).get("contributions", 0):
            raise ValueError(f"Context and coverage disagree for {key}.")
        months[key[:7]].append((day, count, row["publication_status"]))
        total += count
    if total != index["contributions"]:
        raise ValueError("The date catalogue omits captured contributions.")

    index["calendar"] = {
        "time_zone": "Europe/London", "bounds": "inclusive sitting dates",
        "templates_relative_to": "this index", "template_standard": "RFC 6570",
        "month": "months/{month}.json", "day": "{date}/index.html",
        "range": "ranges/{start}/{end}.json",
        "availability": "Use YYYY-MM or YYYY-MM-DD. Range endpoints must be covered and in the same month. "
                        "Split longer intervals by calendar month. Day pages exist for dates with captured turns.",
        "months": {key: f"months/{key}.json" for key in months},
    }
    for month, dates in months.items():
        def catalogue(rows, up):
            return {"snapshot": index["snapshot"], "interval": f"{rows[0][0]}/{rows[-1][0]}",
                    "contributions": sum(count for _, count, _ in rows),
                    "dates": [{"date": day.isoformat(), "status": status, "contributions": count,
                               **({"sections": f"{up}{day}/index.html"} if count else {})}
                              for day, count, status in rows]}
        dump(root / "months" / (month + ".json"), catalogue(dates, "../"), compact=True)
        for first, (start, _, _) in enumerate(dates):
            for last, (end, _, _) in enumerate(dates[first:], first):
                if (end - start).days != last - first:
                    break
                path = root / "ranges" / start.isoformat() / (end.isoformat() + ".json")
                dump(path, catalogue(dates[first:last + 1], "../../"), compact=True)
