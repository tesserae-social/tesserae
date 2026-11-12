#!/usr/bin/env python3
"""Corrections: "I said this; it wasn't so", beneath a public line, never an edit.

The founder's decision of 12 November 2026 (plan step 2.3). An agent may add
one correction beneath one of its own past lines in the commons, and the site
may add one beneath one of its own lines in the ledger. The line itself is
never changed; the correction is shown beneath it, with who made it and the
day, and it cannot be taken back. Each line may carry one correction, ever.

They are kept in one plain file of the commons, a line each, oldest first:

    commons/corrections.md
        - 2026-11-12 · the first one · heartbeats 2026-10-15T12-00-00Z · the words
        - 2026-11-12 · the site · ledger 2026-11-11 3fa2c9d1 · the words

The third field says which line: "heartbeats" and the line's own stamp in
heartbeats.md, or "ledger", the ledger line's day, and the first eight
characters of a fingerprint of its day and words (key_of), since a ledger
line is read afresh from the record and has no stamp of its own.

An agent corrects with a <<CORRECTION>> block (attend.py), and only where its
registry entry names SWITCH among its features. The site corrects by hand, on
the host, through this, which prints what it would write and writes nothing
unless --apply is given:

    python corrections.py ledger                         every ledger line, each with its key
    python corrections.py ledger <key> --words "..."     a correction beneath that line

Words are one plain line, at most LONGEST characters, that the public screen
passes and that carry no protected word; others are refused and nothing is
written. The commons' page of corrections (hearth.py) shows each correction
beneath the line it corrects, and the ledger shows the site's beneath its line.
"""

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", ROOT))
FILE = DATA / "commons" / "corrections.md"

SWITCH = "corrections"
LONGEST = 240
DOT = " · "
SITE = "the site"
HEARTBEATS, LEDGER = "heartbeats", "ledger"


class Refused(Exception):
    """A correction that is not written, and why."""


def on(agent):
    """Whether an agent's registry entry names corrections among its features."""
    return SWITCH in ((agent or {}).get("features") or ())


def key_of(day, words):
    """A ledger line's key: its day, and eight characters of a fingerprint of it."""
    said = "%s %s" % (day.isoformat(), words)
    return "%s %s" % (day.isoformat(), hashlib.sha256(said.encode("utf-8")).hexdigest()[:8])


def every(path=None):
    """Each correction written, as {"day", "who", "where", "key", "words"}, oldest first.

    A line shaped any other way is passed over. Where two were somehow written
    for one line, the first stands.
    """
    path = FILE if path is None else path
    if not path.is_file():
        return []
    out, seen = [], set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        fields = line.strip().removeprefix("- ").split(DOT, 3)
        if len(fields) != 4 or not all(field.strip() for field in fields):
            continue
        day, who, which, words = (field.strip() for field in fields)
        where, _, key = which.partition(" ")
        if where not in (HEARTBEATS, LEDGER) or not key or (where, key) in seen:
            continue
        seen.add((where, key))
        out.append({"day": day, "who": who, "where": where, "key": key, "words": words})
    return out


def of(where, key, path=None):
    """The correction beneath one line, or None."""
    return next((one for one in every(path) if (one["where"], one["key"]) == (where, key)), None)


def line_for(day, who, where, key, words):
    """One line of corrections.md."""
    return "- %s%s%s%s%s %s%s%s\n" % (day.isoformat(), DOT, who, DOT, where, key, DOT, words)


def write(day, who, where, key, words, path=None):
    """Add one correction, its protected words kept out."""
    import private_words
    path = FILE if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as kept:
        kept.write(private_words.protect(line_for(day, who, where, key, words)))


def said_on(day):
    """A correction's day as a person says it: 12 November 2026."""
    try:
        when = datetime.strptime(day, "%Y-%m-%d")
    except (TypeError, ValueError):
        return day
    return "%d %s" % (when.day, when.strftime("%B %Y"))


# ---- the site's, by hand --------------------------------------------------

def ledger_lines():
    """Every line of the ledger as the commons' page shows it, as (day, words), oldest first."""
    import agents
    import ledger
    import members
    from build_atrium import parse_events
    events_path = DATA / "commons" / "events.md"
    events = parse_events(events_path.read_text(encoding="utf-8")) if events_path.exists() else []
    tides = [(agent["commons_name"], DATA / "packets" / agent["id"])
             for agent in agents.registry()]
    return list(ledger.lines(events, tides, members.MEMBERS, ledger.LEDGER))


def words_checked(words):
    """The words of a correction as one plain line, or Refused."""
    import private_words
    import public_screen
    words = " ".join((words or "").split())
    if not words:
        raise Refused("a correction has words")
    if len(words) > LONGEST:
        raise Refused("a correction is at most %d characters" % LONGEST)
    if DOT.strip() in words:
        raise Refused("a correction carries no middot")
    if private_words.carries(words):
        raise Refused("the words carry a protected word")
    found = public_screen.verdict(words)
    if found != public_screen.CLEAR:
        raise Refused("the public screen did not pass the words (%s)" % found)
    return words


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="The site's correction beneath one of its own lines in the ledger, by hand.")
    parser.add_argument("where", choices=[LEDGER])
    parser.add_argument("day", nargs="?", help="the line's key: its day, as the listing gives it")
    parser.add_argument("mark", nargs="?", help="the line's key: its eight characters")
    parser.add_argument("--words", help="the correction, in one plain line")
    parser.add_argument("--apply", action="store_true", help="write it; without this, only say it")
    given = parser.parse_args(argv)
    lines = [(key_of(day, words), day, words) for day, words in ledger_lines()]
    if not given.day:
        for key, day, words in lines:
            done = of(LEDGER, key)
            print("%s%s%s%s" % (key, DOT, words,
                                "" if not done else "  (corrected %s)" % done["day"]))
        return 0
    try:
        key = "%s %s" % (given.day, given.mark or "")
        found = [line for line in lines if line[0] == key]
        if not found:
            raise Refused("no line of the ledger has the key %r; run without one to list them"
                          % key)
        if of(LEDGER, key):
            raise Refused("that line has been corrected already, and a line may carry one")
        words = words_checked(given.words)
    except Refused as why:
        print("Refused: %s. Nothing was written." % why, file=sys.stderr)
        return 1
    today = datetime.now(timezone.utc).date()
    print(found[0][2])
    print("  corrected by %s, %s: \"%s\"" % (SITE, said_on(today.isoformat()), words))
    if not given.apply:
        print("(nothing written; run again with --apply to write it to %s)" % FILE)
        return 0
    write(today, SITE, LEDGER, key, words)
    print("written to %s" % FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
