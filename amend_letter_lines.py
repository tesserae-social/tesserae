#!/usr/bin/env python3
"""Take the part of the day out of the commons' existing letter lines. Run once, on the host.

Until 10 November 2026 the hearth wrote each day's line for a person's letters
naming the part of the day the first of them fell in: "the founder wrote a
letter at dawn". The founder decided that day that no such line says it, and the
hearth writes "the founder wrote a letter" now. This takes the part of the day
out of the lines written before, in commons/events.md, the same way for anyone's
letter: "... wrote a letter at dawn", "during the day", "in the evening" or "at
night" becomes "... wrote a letter". A line he left beside a letter, after its
middot, stays as he wrote it. An agent's waking keeps its time: heartbeats.md
is not read.

Only those words change. Every other byte of the file stays as it was: every
other line, the order of the lines, each line's end, a mark at the start of the
file. No line is added to say it was done. A second run changes nothing.

It amends the way amend_public_words.py does, and with its own reading and
writing: by itself it changes nothing, and prints, as a diff, what it would
change. With --apply it writes it, whole to a copy beside the file and then put
in its place, so a reader never sees half of it. It is best run while no letter
is being left.
"""

import argparse
import difflib
import os
import sys
from pathlib import Path

from amend_public_words import read, write
from build_atrium import DOT, letter_shown

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", ROOT))

SEPARATOR = " %s " % DOT


def amended_line(body):
    """One line of events.md, without its end, with a letter's part of the day taken out."""
    fields = body.split(SEPARATOR, 2)
    if len(fields) != 3 or fields[1].strip() != "letter":
        return body
    return SEPARATOR.join(fields[:2] + [letter_shown(fields[2])])


def amended(text):
    """The text with each letter line's part of the day taken out, and nothing else changed."""
    out = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        out.append(amended_line(body) + line[len(body):])
    return "".join(out)


def main(argv=None, data=None, out=sys.stdout):
    asked = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    asked.add_argument("--apply", action="store_true",
                       help="write the changes; without it, only show them")
    args = asked.parse_args(argv)
    path = (Path(data) if data else DATA) / "commons" / "events.md"
    if not path.is_file():
        print("There is no commons/events.md. Nothing to do.", file=out)
        return 0
    mark, text = read(path)
    after = amended(text)
    if after == text:
        print("No letter line names a part of the day. Nothing to do.", file=out)
        return 0
    out.writelines(difflib.unified_diff(
        text.splitlines(keepends=True), after.splitlines(keepends=True),
        "commons/events.md", "commons/events.md (amended)", n=0))
    if not args.apply:
        print("\nA dry run: nothing was written. Run again with --apply to write it.", file=out)
        return 0
    write(path, mark, after)
    print("\nWritten: commons/events.md.", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
