#!/usr/bin/env python3
"""Give the founder's earlier letters their tiles in the mosaic. Run once, on the host.

The hearth now writes one line to commons/events.md on each day the founder
leaves a letter, naming the part of the day the first of that day's letters
fell in. The letters left before it did have no line, so this finds every day
on which he left at least one - read off the stamps in the letters' own names,
on the citizen's clock, as the mosaic's days are - and writes the missing
lines, each among the others in date order, each naming the part of the day of
that day's first letter by the wakings' own bounds.

No line already there is changed, moved against the others, or taken out, and a
day that already has its line is passed over, so a second run adds nothing.
Nothing of any letter is read but its name.

It prints how many days it added, and nothing else.

The file is written whole to a copy beside it and then put in its place, so a
reader never sees half of it. It is best run while no letter is being left.
"""

import datetime
import os
import re
from zoneinfo import ZoneInfo

from build_atrium import CITIZEN_ZONE, band, is_letter_line, letter_words, parse_events

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", ROOT)

EVENTS = os.path.join(DATA, "commons", "events.md")
LETTERS = os.path.join(DATA, "packets", "first", "letters")

# where the founder's letters are kept: waiting to be read, and read
FOLDERS = ("incoming", "read")

STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")


def first_letters(letters=LETTERS):
    """Each day, on the citizen's clock, the founder left a letter, and the first moment he did.

    A letter moved from incoming to read may be found in both; it is one letter.
    """
    first = {}
    for folder in FOLDERS:
        where = os.path.join(letters, folder)
        if not os.path.isdir(where):
            continue
        for name in os.listdir(where):
            if not (name.startswith("founder-") and name.endswith(".md")):
                continue
            found = STAMP.search(name)
            if not found:
                continue
            at = datetime.datetime.strptime(found.group(), "%Y-%m-%dT%H-%M-%SZ")
            at = at.replace(tzinfo=datetime.timezone.utc).astimezone(ZoneInfo(CITIZEN_ZONE))
            if at.date() not in first or at < first[at.date()]:
                first[at.date()] = at
    return first


def line_day(line):
    """The day a line of events.md is dated, or None for a line that is not one."""
    read = parse_events(line)
    return read[0][0] if read else None


def backfilled(text, first):
    """The text of events.md with a letter line for each day that lacks one.

    first maps each day to the moment of that day's first letter, on the
    citizen's clock. Each new line goes in just before the first dated line
    that is later than its day, or at the end if there is none. Every line
    already there stays exactly as it was written, in the same order. Gives
    back the new text and how many lines were added.
    """
    had = {when for when, kind, words in parse_events(text) if is_letter_line(kind, words)}
    wanted = sorted(day for day in first if day not in had)
    if not wanted:
        return text, 0

    newline = "\r\n" if "\r\n" in text else "\n"

    def said(day):
        return "%s · letter · %s%s" % (day.isoformat(), letter_words(band(first[day].hour)),
                                        newline)

    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        lines[-1] += newline  # a new line after it must not run on from it

    out, at = [], 0
    for line in lines:
        dated = line_day(line)
        while at < len(wanted) and dated is not None and dated > wanted[at]:
            out.append(said(wanted[at]))
            at += 1
        out.append(line)
    out.extend(said(day) for day in wanted[at:])
    return "".join(out), len(wanted)


def main(events=EVENTS, letters=LETTERS):
    with open(events, "rb") as fh:
        raw = fh.read()
    mark = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")

    written, added = backfilled(text, first_letters(letters))
    if added:
        copy = events + ".backfill"
        with open(copy, "wb") as fh:
            fh.write((b"\xef\xbb\xbf" if mark else b"") + written.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(copy, events)
    print(added)
    return added


if __name__ == "__main__":
    main()
