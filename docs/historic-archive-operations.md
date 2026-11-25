# Extend the Hansard archive before 2007

The collector works backwards from 31 December 2006 towards 22 November 1803, using the Commons and Lords calendars. It runs independently of the live demonstration. The GitHub Pages history continues to use the published snapshot while the older index grows. The one-off collection pause runs from 5.45 am to 9.45 am UK time on Friday 20 November 2026, around the scheduled refresh.

## What qualifies as a contribution link

Parliament’s API exposes sitting calendars, section trees and source item identifiers in sampled historic years. The collector retains only matches with a source-issued contribution identifier and a unique contribution fragment within the debate. It retains the source locator, digest and match spans, and processes the retrieved text in memory. Literal matching uses the pinned Wednesday profile, including the 309 entities identified on 18 November.

A real browser opened the exact contribution fragments in samples from both Houses in 1803 and from 1940, 2003, 2004, 2005 and 2006. These checks establish the link format. Publication, attribution and digitisation quality vary by sitting. The report records failed calendars or sittings, and each sitting receipt counts matched passages that lack a unique link. Parliament’s website still lists an availability gap for 2004 to 2006, so check the recorded coverage before summarising that period. [Historic Hansard](https://api.parliament.uk/historic-hansard/index.html) · [Hansard availability notice](https://hansard.parliament.uk/search) · [Commons contribution on 22 November 1803](https://hansard.parliament.uk/Commons/1803-11-22/debates/aff47fd4-eabf-479c-9532-323fce335df0/KingsSpeech#contribution-5fdac5bb-5d61-4d6e-bf0b-2aa10d24fe15) · [Lords contribution on 22 November 1803](https://hansard.parliament.uk/Lords/1803-11-22/debates/590866a7-7503-4903-910a-8fb7303ddfa8/HouseOfLords#contribution-de3fce59-4ae8-45cf-b03f-6f77661c54a4)

## Status and storage

| Item | Location |
| --- | --- |
| Database and matching profile | `/Volumes/ExtSSD-Data/okf-hansard-cache/history-before-2007.sqlite` and `history-before-2007.profile.json` beside it |
| Progress, skipped-source receipts and calendar gaps | `.work/historic-history/progress.json` |
| Collector output and errors | `.work/historic-history/collector.log` and `.work/historic-history/collector-errors.log` |
| macOS worker | `uk.co.chrispage.okf-hansard.historic-archive`, with its property list in `.work/historic-history/` |
| Pinned input | `.work/historic-history/analysis-profile.json` |

Run from the repository root. Read the report to see whether the job is running, paused, finished or finished with source gaps. The earliest processed sitting measures progress. It can precede an unresolved gap.

    jq '{state, last_checkpoint, earliest_processed, latest_processed, sittings_by_status, mentions, observed_gaps, calendar_gaps}' .work/historic-history/progress.json

## Pause, resume and finish

To pause, create the marker and wait for the report to show `paused`. Each completed sitting is a transaction, so a restart reuses it. The same marker works during the Friday pause.

    touch .work/historic-history/pause

To resume, mount the SSD and remove the marker.

    rm .work/historic-history/pause

For a worker already loaded into the current macOS login session, use `kickstart`. If it was unloaded or the Mac restarted, use `bootstrap`.

    launchctl kickstart "gui/$(id -u)/uk.co.chrispage.okf-hansard.historic-archive"
    launchctl bootstrap "gui/$(id -u)" "$PWD/.work/historic-history/uk.co.chrispage.okf-hansard.historic-archive.plist"

To finish and tidy up, pause first and wait for the checkpoint. Then unload the worker and check SQLite while the collector is stopped. Keep the database, its matching profile and the progress report together. Export or back up via SQLite while preserving that profile. The local lock file and diagnostic logs can be archived with the report. A resumed scan retries recorded source gaps and leaves successful sittings in place.

    launchctl bootout "gui/$(id -u)/uk.co.chrispage.okf-hansard.historic-archive"
    uv run --locked python - <<'PY'
    from contextlib import closing
    from pathlib import Path
    import sqlite3

    path = Path("/Volumes/ExtSSD-Data/okf-hansard-cache/history-before-2007.sqlite")
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True)) as db:
        assert db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0] == 0
        assert db.execute("PRAGMA quick_check").fetchall() == [("ok",)]
    PY

## Query from the Mac

Use a release that contains the current contribution and pass the older database explicitly. The trace joins available evidence in date order and reports coverage for the older archive. The local stdio server accepts the same option.

    uv run --locked python scripts/query.py --release RELEASE --older-database /Volumes/ExtSSD-Data/okf-hansard-cache/history-before-2007.sqlite trace CONTRIBUTION_ROUTE --entity ENTITY_ID
    uv run --locked python scripts/mcp_server.py --release RELEASE --older-database /Volumes/ExtSSD-Data/okf-hansard-cache/history-before-2007.sqlite

A laptop can open the public companion and existing published history without this disk. See the [Voice and storage matrix](voice-and-visual-ui.md#voice-and-storage) for the local-host and web distinction.

## Recover timed-out sittings

The large historic written-answer roots can take longer to assemble than other Hansard responses. The collector gives those roots a longer read window and retries them. A failed retry records the new error and keeps the earlier partial contribution and match rows. The repair command works on an isolated SQLite copy and leaves unresolved dates available for another retry.

Run `scripts/historic_archive.py --retry-gaps` with the archived `--database` and `--profile`, a separate `--staged-database`, a `--report` path and an ISO deadline with a time-zone offset. Review the report and its source receipts. Then run `scripts/apply_archive_repair.py` with `--database`, `--staged`, `--backup` and `--report`. Use a new backup path. It applies only verified replacements for currently unresolved House sittings, in one transaction. Regenerate the history projection so the public index and downloadable evidence reflect the repaired rows.

The repair on 25 November 2026 covered Commons written answers on 18 November 2004, 12 September 2005, 27 February 2006 and 18 April 2006. The older archive's date range and alias profile still specify which historical questions it can answer.
