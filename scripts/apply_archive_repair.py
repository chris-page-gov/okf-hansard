"""Apply verified sitting repairs from a staged SQLite archive with a backup."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from capture import dump, now


def apply(database, staged, backup):
    database, staged, backup = (path.resolve() for path in (database, staged, backup))
    if len({database, staged, backup}) != 3 or backup.exists():
        raise ValueError("Choose distinct archive paths and a new backup path.")
    source_uri = database.as_uri()
    with closing(sqlite3.connect(source_uri + "?mode=rw", uri=True, timeout=10)) as db:
        db.execute("ATTACH DATABASE ? AS repaired", (staged.as_uri() + "?mode=ro",))
        if db.execute("PRAGMA repaired.quick_check").fetchone() != ("ok",):
            raise ValueError("The staged archive failed integrity verification.")
        with db:
            db.execute("BEGIN IMMEDIATE")
            identities = [dict(db.execute(f"SELECT key,value FROM {schema}.metadata"))
                          for schema in ("main", "repaired")]
            if identities[0] != identities[1] or identities[0].get("exclusive_before") != "2007-01-01":
                raise ValueError("The archive metadata does not identify the same older collection.")
            repairs = []
            for day, house, passages, retained, receipt in db.execute("""
                SELECT n.day,n.house,n.passages,n.retained,n.source
                FROM main.sitting o JOIN repaired.sitting n USING(day,house)
                WHERE o.status='source gap' AND n.status='processed'
                ORDER BY n.day,n.house
            """).fetchall():
                proof = json.loads(receipt)
                if (proof["errors"] or not proof["roots"] or not all(row.get("sha256") for row in proof["roots"])
                        or day != proof["date"] or house != proof["house"]):
                    raise ValueError(f"The staged source receipt for {day} {house} is incomplete.")
                repairs.append({"date": day, "house": house, "passages": passages, "retained": retained})
            if not repairs:
                raise ValueError("No verified repairs match the current archive's unresolved sittings.")
            with closing(sqlite3.connect(source_uri + "?mode=ro", uri=True)) as before, \
                    closing(sqlite3.connect(backup)) as saved:
                before.backup(saved)
                if saved.execute("PRAGMA quick_check").fetchone() != ("ok",):
                    raise ValueError("The original archive backup failed integrity verification.")
            for item in repairs:
                key = item["date"], item["house"]
                db.execute("DELETE FROM main.mention WHERE route IN (SELECT route FROM main.contribution WHERE day=? AND house=?)", key)
                db.execute("DELETE FROM main.contribution WHERE day=? AND house=?", key)
                db.execute("INSERT INTO main.contribution SELECT * FROM repaired.contribution WHERE day=? AND house=?", key)
                db.execute("""
                    INSERT INTO main.mention SELECT m.* FROM repaired.mention m
                    JOIN repaired.contribution c ON c.route=m.route WHERE c.day=? AND c.house=?
                """, key)
                db.execute("INSERT OR REPLACE INTO main.sitting SELECT * FROM repaired.sitting WHERE day=? AND house=?", key)
            if db.execute("PRAGMA main.quick_check").fetchone() != ("ok",):
                raise ValueError("The updated archive failed integrity verification.")
            remaining = db.execute("SELECT count(*) FROM main.sitting WHERE status='source gap'").fetchone()[0]
    return {"schema": "hansard-historic-repair-application.v1", "applied_at": now(), "repairs": repairs,
            "remaining_gaps": remaining, "backup": str(backup)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("database", "staged", "backup", "report"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    options = parser.parse_args()
    dump(options.report, apply(options.database, options.staged, options.backup))
