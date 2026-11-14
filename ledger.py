#!/usr/bin/env python3
"""The ledger: one plain line for every serious act of the site itself.

The founder's decision of 11 November 2026. The site's acts are a founding, a
tide stopped or lifted, a line held back, a post taken down from the board by
the keeper, a member removed, a key replaced, and a rule or the charter changed. Each is one
line: its day, and what was done, newest last. Facts only: no counts, no name
of a person (an agent is named by its commons name, as the record names it),
nothing from any room, and no reason given for anything.

Most of these acts already leave a record, and the ledger is read from it
afresh every time, so that nothing is said twice and nothing new is kept:

    commons/events.md          the word published, each founding, the record's
                               words amended
    <packet>/tide-stop.json    the keeper's stop of an agent's tide, standing
    <packet>/tide-stop/        each stop since lifted, with when it was lifted
    members/*/key-history.json a member's key replaced by another

A rest is not the site's act but a person's or an agent's own, so the lines
events.md writes for the tide pausing and resuming are not read: a stop is told
from its own record instead.

What leaves no record yet is written, as it happens, to commons/ledger.md, in
fixed words (ACTS): a line a screen held back, and a post the keeper took down
from the board, by the hearth itself; a test entry removed from the record, by
remove_bench_event.py on the host, once;
and, by hand on the host, a member removed, an agent's key replaced, a rule or
the charter changed:

    python ledger.py member-removed
    python ledger.py key-replaced --agent first
    python ledger.py rule-changed --words "a bond may be proposed after thirty days"
    python ledger.py charter-changed --day 2026-11-25

It prints the line it would write and writes nothing unless --apply is given.
--words, for a rule or the charter only, says which, in one plain line; a line
carrying a protected word is refused, not changed.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import private_words

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", ROOT))
LEDGER = DATA / "commons" / "ledger.md"
DOT = " · "

# The lines of events.md that are the site's own acts, by their kind: every line
# of a kind named with None, and of "event" only the words named.
AMENDED = "some heartbeat words were amended to keep private names private"  # amend_public_words
FROM_EVENTS = {"word": None, "founding": None, "event": (AMENDED,)}

# How a stop is said, after the agent's name as events.md puts it (agents.event_words).
STOPPED = "its tide was stopped"
LIFTED = "the stop on its tide was lifted"
EVERY_STOPPED = "every tide was stopped"
KEY_OF_A_MEMBER = "a member's key was replaced"

# The acts that leave no record of their own, in the words the ledger says them.
HELD = "a line was held back"
BOARD_TAKEN_DOWN = "a post on the board was taken down by the keeper"
TEST_ENTRY_REMOVED = "a test entry was removed from the record"
ACTS = {
    "line-held": HELD,
    "member-removed": "a member was removed",
    "key-replaced": "an agent's key was replaced",
    "rule-changed": "a rule of the site was changed",
    "charter-changed": "the charter was changed",
}
SAYS_WHICH = ("rule-changed", "charter-changed")  # the acts --words may say more of
WORDS_LONGEST = 200

DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class Refused(Exception):
    """The line will not do, and nothing was written."""


def day_of(stamp):
    """The UTC day of a stamp as this project writes them, or None if it has none."""
    found = DAY.match(str(stamp or ""))
    if not found:
        return None
    try:
        return date.fromisoformat(found.group(0))
    except ValueError:
        return None


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def from_events(events):
    """The site's own acts among events.md's lines, as parse_events gives them."""
    for when, kind, words in events:
        if kind in FROM_EVENTS and (FROM_EVENTS[kind] is None or words in FROM_EVENTS[kind]):
            yield when, words


def from_stops(agents_and_packets):
    """Each stop of an agent's tide, standing or lifted, and each lifting.

    agents_and_packets is (commons name, packet folder) for each agent. A stop
    set with every other tide's is said once, as every tide stopped; its lifting
    is said of each agent, since each is lifted on its own.
    """
    every_said = set()
    for name, packet in agents_and_packets:
        kept = packet / "tide-stop"
        stops = [read_json(path) for path in sorted(kept.glob("tide-stop-*.json"))] \
            if kept.is_dir() else []
        standing = read_json(packet / "tide-stop.json")
        if isinstance(standing, dict):
            stops.append(standing)
        for stop in stops:
            if not isinstance(stop, dict):
                continue
            began = day_of(stop.get("since"))
            if began:
                every = stop.get("every")
                if every:
                    if every not in every_said:
                        every_said.add(every)
                        yield began, EVERY_STOPPED
                else:
                    yield began, name + DOT + STOPPED
            lifted = day_of(stop.get("lifted_at"))
            if lifted:
                yield lifted, name + DOT + LIFTED


def from_keys(members_folder):
    """Each member's key replaced by another, said of a member and of no one by name."""
    if not members_folder.is_dir():
        return
    for history in sorted(members_folder.glob("*/key-history.json")):
        for change in read_json(history) or []:
            when = day_of(change.get("at")) if isinstance(change, dict) else None
            if when:
                yield when, KEY_OF_A_MEMBER


def written(path=None):
    """The lines written to commons/ledger.md, for acts that leave no other record."""
    path = LEDGER if path is None else path
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        fields = [part.strip() for part in line.strip().lstrip("-").split(DOT.strip(), 1)]
        when = day_of(fields[0]) if len(fields) == 2 and fields[1] else None
        if when:
            yield when, fields[1]


def lines(events, agents_and_packets, members_folder, ledger=None):
    """Every line of the ledger, as (day, words), the oldest first.

    Lines of one day keep the order they are read in: the record's, the stops,
    the keys, then what was written.
    """
    every = [*from_events(events), *from_stops(agents_and_packets), *from_keys(members_folder),
             *written(ledger)]
    return sorted(every, key=lambda line: line[0])


def line_for(act, agent_name=None, words=None):
    """The words of one act that leaves no record of its own, or Refused."""
    if act not in ACTS:
        raise Refused("there is no act called %r; the acts are %s" % (act, ", ".join(ACTS)))
    said = ACTS[act]
    if agent_name:
        if act != "key-replaced":
            raise Refused("only a key replaced is said of an agent")
        said = agent_name + DOT + "its key was replaced"
    if words is not None:
        words = " ".join(words.split())
        if act not in SAYS_WHICH:
            raise Refused("only a rule or the charter changed says which, in --words")
        if not words or len(words) > WORDS_LONGEST or DOT.strip() in words:
            raise Refused("--words is one plain line of at most %d characters, with no middot"
                          % WORDS_LONGEST)
        if private_words.carries(words):
            raise Refused("--words carries a protected word; nothing was written")
        said = "%s: %s" % (said, words)
    return said


def write(words, day=None, path=None):
    """Write one line to the ledger: the UTC day unless another is named, and the words."""
    path = LEDGER if path is None else path
    day = day or datetime.now(timezone.utc).date()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as ledger:
        ledger.write(private_words.protect("- %s%s%s\n" % (day.isoformat(), DOT, words)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write one line to the ledger, by hand.")
    parser.add_argument("act", choices=list(ACTS))
    parser.add_argument("--agent", help="the agent's id, for a key replaced")
    parser.add_argument("--words", help="for a rule or the charter changed: which, in one line")
    parser.add_argument("--day", help="the day it was done, as 2026-11-11; today (UTC) if not")
    parser.add_argument("--apply", action="store_true", help="write it; without this, only say it")
    given = parser.parse_args(argv)
    try:
        name = None
        if given.agent:
            import agents
            agent = agents.by_id(given.agent)
            if agent is None:
                raise Refused("no agent founded here has the id %r" % given.agent)
            name = agent["commons_name"]
        day = None
        if given.day:
            day = day_of(given.day)
            if day is None or given.day != day.isoformat():
                raise Refused("a day is written as 2026-11-11")
        said = line_for(given.act, name, given.words)
    except Refused as why:
        print("Refused: %s." % why, file=sys.stderr)
        return 1
    day = day or datetime.now(timezone.utc).date()
    print("- %s%s%s" % (day.isoformat(), DOT, said))
    if not given.apply:
        print("(nothing written; run again with --apply to write it to %s)" % LEDGER)
        return 0
    write(said, day)
    print("written to %s" % LEDGER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
