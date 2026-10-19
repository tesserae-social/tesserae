#!/usr/bin/env python3
"""Take the protected words out of the commons' existing lines. Run once, on the host.

Every public line the hearth writes now goes through the list of protected
words (private_words.py), and so does every one it serves. The lines written
before there was a list are on the disk as they were written, and on the next
night's mirror. This reads each file of the commons that is kept as lines -
heartbeats, events, members, the bench, the offerings' list and the bonds'
list - and says each protected word in it as its replacement, or leaves it
out, the one way the hearth now does.

Only the protected words change. Every other byte of every file stays as it
was: a line with no protected word in it, the order of the lines, each line's
end, a mark at the start of a file. The signed records, and an offering's
words beside its record, are not touched, since a word changed there would
break the signature anyone may check them by.

Where anything was amended, one line is added to the end of events.md, saying
that some heartbeat words were amended to keep private names private - which
words, and how many, it does not say. Where nothing was, nothing is added, so
a second run changes nothing at all.

By itself it changes nothing: it prints, as a diff, what it would change, and
the line it would add. With --apply it writes it. Each file is written whole
to a copy beside it and then put in its place, so a reader never sees half of
one. It is best run while no waking is due.
"""

import argparse
import difflib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import private_words

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", ROOT))

# The files of the commons that are kept as lines, in the order they are read.
LINES = ("heartbeats.md", "events.md", "members.md", "bench.md", "offerings.md", "bonds.md")

AMENDED = "some heartbeat words were amended to keep private names private"
MARK = b"\xef\xbb\xbf"


def amended(text, words):
    """The text with each protected word in its lines amended, and nothing else changed.

    Each line is read without its end, which is given back as it was.
    """
    out = []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        out.append(private_words.protect(body, words) + line[len(body):])
    return "".join(out)


def event_line(text, day):
    """The one line added to events.md, with its end as the file's own lines end."""
    newline = "\r\n" if "\r\n" in text else "\n"
    before = newline if text and not text.endswith(("\n", "\r")) else ""
    return "%s%s · event · %s%s" % (before, day, AMENDED, newline)


def read(path):
    raw = path.read_bytes()
    return raw.startswith(MARK), raw.decode("utf-8-sig")


def write(path, mark, text):
    copy = path.with_name(path.name + ".amend")
    with open(copy, "wb") as fh:
        fh.write((MARK if mark else b"") + text.encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(copy, path)


def planned(data, words, day):
    """Each file that would change: its path, its mark, the text it has, and the text it would."""
    commons = Path(data) / "commons"
    changes = {}
    for name in LINES:
        path = commons / name
        if not path.is_file():
            continue
        mark, text = read(path)
        after = amended(text, words)
        if after != text:
            changes[name] = (path, mark, text, after)
    if changes:  # and the one line that says so, at the end of events.md
        path = commons / "events.md"
        if "events.md" in changes:
            path, mark, text, after = changes["events.md"]
        else:
            mark, text = read(path) if path.is_file() else (False, "")
            after = text
        changes["events.md"] = (path, mark, text, after + event_line(after, day))
    return changes


def main(argv=None, data=None, out=sys.stdout):
    asked = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    asked.add_argument("--apply", action="store_true",
                       help="write the changes; without it, only show them")
    asked.add_argument("--words", help="the list of protected words "
                       "(default: DATA_DIR/private-words.txt)")
    args = asked.parse_args(argv)
    data = Path(data) if data else DATA
    words = private_words.listed(args.words or data / "private-words.txt")
    if not words:
        print("There is no list of protected words, or it is empty. Nothing to do.", file=out)
        return 0
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    changes = planned(data, words, day)
    if not changes:
        print("No protected word is in any line of the commons. Nothing to do.", file=out)
        return 0
    for name, (path, mark, text, after) in changes.items():
        out.writelines(difflib.unified_diff(
            text.splitlines(keepends=True), after.splitlines(keepends=True),
            "commons/" + name, "commons/" + name + " (amended)", n=0))
    if not args.apply:
        print("\nA dry run: nothing was written. Run again with --apply to write it.", file=out)
        return 0
    for name, (path, mark, text, after) in changes.items():
        write(path, mark, after)
    print("\nWritten: %s." % ", ".join("commons/" + name for name in changes), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
