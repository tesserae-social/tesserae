#!/usr/bin/env python3
"""Take the one test line about the bench out of the record. Run once, on the host.

The founder's request of 14 November 2026. The bench is gone. Its one line in
commons/events.md was the founder's own test:

    2026-09-21 · event · a line was taken off the bench

This script removes that line from events.md and writes one line to the ledger:

    - <today> · a test entry was removed from the record

Nothing else in events.md changes. Before events.md is rewritten, a copy of it
as it was is kept outside the commons, in DATA_DIR/events-before-bench-removal-
<stamp>.md, served to no one, so that the change can be undone by hand.

It also says whether commons/bench.md is still on the disk. An empty one is
removed with --apply; one with any line in it is left where it is, and said.

Without --apply it only says what it would do and writes nothing. It refuses to
change anything unless it finds exactly one such line. Run it twice and the
second run finds nothing to do and writes nothing.

    python remove_bench_event.py            what it would do
    python remove_bench_event.py --apply    do it

The atrium (index.html, mosaic.html) is drawn from events.md by the mirror job,
so its tile for that line goes at the job's next run after this one.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import ledger

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", ROOT))
EVENTS = DATA / "commons" / "events.md"
BENCH = DATA / "commons" / "bench.md"

# The words of the one line, after its day and its kind.
TEST_WORDS = "a line was taken off the bench"
KIND = "event"


def is_the_test_line(line):
    """Whether one line of events.md is a line taken off the bench."""
    fields = [part.strip() for part in line.strip().lstrip("-").split("·")]
    return len(fields) == 3 and fields[1] == KIND and fields[2] == TEST_WORDS


def main(argv=None):
    parser = argparse.ArgumentParser(description="Remove the bench's test line from events.md.")
    parser.add_argument("--apply", action="store_true", help="do it; without this, only say it")
    given = parser.parse_args(argv)

    if not EVENTS.is_file():
        print("No events.md at %s. Nothing to do." % EVENTS)
        return 0
    raw = EVENTS.read_bytes()
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    found = [line for line in lines if is_the_test_line(line)]

    if not found:
        print("No line about the bench is in events.md. Nothing to do.")
    elif len(found) > 1:
        print("Refused: %d lines about the bench are in events.md, not one. Nothing was "
              "written. They are:" % len(found), file=sys.stderr)
        for line in found:
            print("  " + line.rstrip("\r\n"), file=sys.stderr)
        return 1
    else:
        print("Would remove from events.md:" if not given.apply else "Removing from events.md:")
        print("  " + found[0].rstrip("\r\n"))
        said = ledger.TEST_ENTRY_REMOVED
        day = datetime.now(timezone.utc).date()
        print("Would write to the ledger:" if not given.apply else "Writing to the ledger:")
        print("  - %s%s%s" % (day.isoformat(), ledger.DOT, said))
        if given.apply:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
            kept = DATA / ("events-before-bench-removal-%s.md" % stamp)
            kept.write_bytes(raw)
            left = "".join(line for line in lines if not is_the_test_line(line))
            EVENTS.write_bytes(left.encode("utf-8"))
            ledger.write(said, day, path=DATA / "commons" / "ledger.md")
            print("Done. events.md as it was is kept at %s." % kept)

    if BENCH.is_file():
        if BENCH.read_text(encoding="utf-8").strip():
            print("commons/bench.md still has lines in it. It is no longer served. "
                  "It is left where it is.")
        elif given.apply:
            BENCH.unlink()
            print("Removed the empty commons/bench.md.")
        else:
            print("Would remove the empty commons/bench.md.")
    if not given.apply:
        print("(nothing written; run again with --apply to do it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
