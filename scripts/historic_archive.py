"""Run the pre-2007 Hansard archive independently of the live demonstration."""

import argparse
from contextlib import closing
from datetime import UTC, date, datetime
import fcntl
import json
from pathlib import Path
import signal
import sqlite3
import time

from archive import Collector, open_database, run
from capture import dump, now
from model import Entity, Matcher
from query import DEEP_BEFORE, DEEP_DB, DEFAULT_DB

FLOOR = date(1803, 11, 22)
STATE = Path(".work/historic-history")


def retire(state, reason, error=None):
    report = state / "progress.json"
    saved = json.loads(report.read_bytes()) if report.is_file() else {}
    saved.pop("error", None)
    dump(report, {**saved, "state": reason, "last_checkpoint": now(), **({"error": error} if error else {})})


def run_extension(args):
    state = args.state.resolve()
    database = args.database.resolve()
    if database == DEFAULT_DB.resolve():
        raise ValueError("Choose a separate database for the pre-2007 archive.")
    state.mkdir(parents=True, exist_ok=True)
    with (state / "collector.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("The historical collector is already running.") from None
        if args.database == DEEP_DB and not DEEP_DB.parents[1].is_mount():
            retire(state, "SSD unavailable", "Mount ExtSSD-Data before starting the historical collector.")
            return
        try:
            collect(args, state, database)
        except (OSError, ValueError, sqlite3.Error) as exc:
            retire(state, "failed", str(exc))
            raise


def collect(args, state, database):
    pause = state / "pause"
    if pause.exists():
        retire(state, "paused")
        return
    profile = database.with_suffix(".profile.json")
    raw = args.profile.read_bytes()
    if profile.is_file():
        if profile.read_bytes() != raw:
            raise ValueError("The older archive is already pinned to a different matching profile.")
    else:
        profile.parent.mkdir(parents=True, exist_ok=True)
        temporary = profile.with_suffix(".tmp")
        temporary.write_bytes(raw)
        temporary.replace(profile)
    spec = json.loads(raw)
    entities = {key: Entity(key=key, **row) for key, row in spec["entities"].items()}
    matcher = Matcher(entities, spec["ambiguities"])
    matcher.entity_groups = {key: entity.group for key, entity in entities.items()}
    collector = None
    stopped = False

    def stop(*_):
        nonlocal stopped
        stopped = True
        if collector:
            collector.stop()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    while not stopped and not pause.exists():
        current = datetime.now(UTC)
        if args.quiet_from and args.quiet_from <= current < args.quiet_until:
            retire(state, "Friday refresh pause")
            while not stopped and not pause.exists() and current < args.quiet_until:
                time.sleep(min(30, max(0, (args.quiet_until - current).total_seconds())))
                current = datetime.now(UTC)
            continue
        deadline = args.quiet_from if args.quiet_from and current < args.quiet_from else datetime.max.replace(tzinfo=UTC)
        collector = Collector(deadline, pause, args.interval)
        with closing(open_database(database, raw)) as db:
            expected = {"contribution_link_policy": "unique-fragment-v1", "exclusive_before": DEEP_BEFORE}
            with db:
                for key, value in expected.items():
                    db.execute("INSERT OR IGNORE INTO metadata VALUES (?, ?)", (key, value))
                    if db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone() != (value,):
                        raise ValueError("The older archive uses different collection settings.")
            if db.execute("SELECT 1 FROM sitting WHERE day>=? LIMIT 1", (DEEP_BEFORE,)).fetchone():
                raise ValueError("The older archive overlaps the current history window.")
            result = run(db, collector, matcher, DEEP_BEFORE, FLOOR, state / "progress.json",
                         links_only=True, checkpoint_seconds=180)
        if result["state"] == "finished":
            if result["calendar_gaps"] or result["observed_gaps"]:
                retire(state, "finished with source gaps")
            return
    retire(state, "paused")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=DEEP_DB)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--quiet-from", type=datetime.fromisoformat)
    parser.add_argument("--quiet-until", type=datetime.fromisoformat)
    parser.add_argument("--interval", type=float, default=.66)
    args = parser.parse_args()
    if args.interval < .25:
        parser.error("Use a request interval of at least 0.25 seconds.")
    if args.quiet_from or args.quiet_until:
        if not args.quiet_from or not args.quiet_until or not args.quiet_from.tzinfo or not args.quiet_until.tzinfo:
            parser.error("Use both pause times with explicit time-zone offsets.")
        if args.quiet_from >= args.quiet_until:
            parser.error("The end of the pause must follow its start.")
    run_extension(args)


if __name__ == "__main__":
    main()
