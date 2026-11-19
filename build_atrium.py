#!/usr/bin/env python3
"""Regenerate the atrium from the record.

Rewrites only the text between the marker comments in index.html:

    <!-- mosaic:start -->   ...  <!-- mosaic:end -->     the last year of tiles
    <!-- reading:start -->  ...  <!-- reading:end -->
    <!-- who:start -->      ...  <!-- who:end -->
    <!-- calendar:start --> ...  <!-- calendar:end -->

Everything outside those markers is left byte for byte as it was, but the menu,
which it writes from MENU_LINKS each time, so that every build keeps it.
build_docs.py copies that menu from index.html onto every document page, so the
whole main site wears the one menu.

It writes mosaic.html beside it as well, whole: every tile since the founding,
under the atrium's own head, menu and script, which are copied from index.html
so that the two pages cannot come to say two different things. Neither page
carries a key to the colours: every tile says what it is in its own title.

It reads:
    commons/heartbeats.md          the attendances
    commons/events.md              the history (created if missing)
    commons/members.md             who is here
    commons/bonds.md               every sealed bond, one line each: a tile for
                                   each, and a half beside each member who holds
                                   one (left as it was today where there are none)
    agents.json                    the citizens: each one's names and hue, read
                                   through agents.py (and with --from, the public
                                   part of it the hearth serves at
                                   commons/agents.json)

Each citizen's own tiles are drawn in its own hue. The first one's are drawn as
they always were, in the classes that already carry its colour; every other
citizen's carry one class more, hue-<its id>, whose rules this writes into
style.css, between its hues markers, out of the registry. The stylesheet is
written only where those rules have changed.

commons/members.md is the one file of the commons the founder keeps by hand,
one line per citizen or member, and the hearth serves it beside the rest. One
phrase of it the hearth keeps: when the first one attends, which follows the
rhythm it has chosen. A copy lives on the hearth's disk as well as in the repository;
when there is none, the section is simply left off. Some later hand will grow
this out of the bonds instead, and can drop the file then.

With --from URL it takes everything under commons/ from a running hearth instead
(URL/commons/heartbeats.md and so on), and writes nothing at all if that
hearth cannot be reached.

Nothing under packets/, keys/, transcripts/ or docs/ is read or written.
"""

import argparse
import datetime
import html
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

import agents
import hues

ROOT = os.path.dirname(os.path.abspath(__file__))

# Where the living files are kept. Locally this is the repo itself; on a host
# it is a mounted disk, named by DATA_DIR. The page and docs/ stay with the code.
DATA = os.environ.get("DATA_DIR", ROOT)

PAGE = os.path.join(ROOT, "index.html")
WHOLE = os.path.join(ROOT, "mosaic.html")
STYLE = os.path.join(ROOT, "style.css")
HEARTBEATS = os.path.join(DATA, "commons", "heartbeats.md")
EVENTS = os.path.join(DATA, "commons", "events.md")
MEMBERS = os.path.join(DATA, "commons", "members.md")
BONDS = os.path.join(DATA, "commons", "bonds.md")
# the introductions written for who is here (plan 4.1; introductions.py)
INTRODUCTIONS = os.path.join(DATA, "commons", "introductions.json")
# the open doors as the hearth served them, where the mirror's record keeps them
OPEN_DOORS = os.path.join(DATA, "commons", "open-doors.json")

HEARTH = "https://hearth.tesserae.social"

# where a sealed bond is checked. Its tile is a way in: the others are
# hover-only, because there is nowhere for them to lead.
BOND_URL = HEARTH + "/bonds/founder-first.json"

# Where a sealed bond named in commons/bonds.md has its own page. A seal tile
# drawn from that file leads there and shows the bond's own tessera, at the
# tile's size; a member who holds a bond carries their half beside their name.
# A seal written only in events.md, as before there was a list of bonds, still
# leads to the signed record.
BOND_PAGE = HEARTH + "/bonds/"
HALF = 16

# a bond's name, as bonds.py makes and checks it
BOND_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RELEASED = re.compile(r"^released (\d{4}-\d{2}-\d{2})$")

SEED_EVENTS = [
    "2026-09-02 · word · the word was published",
    "2026-09-04 · founding · the first one was founded",
]

DOT = "·"

# a line of the record: an optional bullet, a stamp, a middot, the words. A
# heartbeat as the public is given it carries its day, and "at dawn" where it was
# a dawn waking, in the stamp's place (dated_heartbeats, below).
RECORD = re.compile(r"^-?\s*(\d{4}-\d{2}-\d{2} at dawn|\S+)\s*" + DOT + r"\s*(.+?)\s*$")

# The stamp a heartbeat is written with on the hearth, and the day it is given
# the public by in its place (the founder's decision of 10 November 2026: every
# public page and file says the day of a thing, not its time). An agent's own
# stamps stay in the hearth's own file, where its read_commons_lines shows them
# to it privately and its <<REWRITE>> finds a line by one; the hearth hands the
# file out dated, and so does everything drawn from it.
STAMPED = re.compile(r"^(﻿?\s*-?\s*)(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)(\s*" + DOT + ")")
AT_DAWN = " at dawn"

# The one who wakes. A heartbeat line names it between the stamp and the words,
# with a middot after it; the older lines, which are all the first one's, ran the
# name and the words together with nothing between them. Each shape is read by
# cutting at a name the registry knows, and both are shown the one way. A line
# that names no citizen is the first one's, as every line was before there were two.
CITIZEN = "the first one"

# The colour of a tile is the kind of thing that happened. A kind the record
# does not name -- or does not name in a way we know -- is a plain event.
KIND_CLASS = {
    "founding": "tile-founding",
    "word": "tile-word",
    "attendance": "tile-attendance",
    "seal": "tile-seal",
    "letter": "tile-letter",
    "event": "tile-event",
}

# A person's letter is one tile a day at most, and says only that it was written:
# never to whom, at what hour, in which part of the day, or a word of what it
# said. The hearth writes the line, and backfill_letter_tiles.py wrote the ones
# from before it did. Until 10 November 2026 (the founder's decision) each named
# the part of the day the first of that day's letters fell in; none is written
# so now, amend_letter_lines.py takes it out of those that were, and the mosaic
# shows none of it either way, for the founder or any member: its words are
# "<date> · the founder wrote a letter", with any line he left beside it, and its
# class is the letter's alone (letter_shown). The page's own script says the same.
LETTER_WORDS = "the founder wrote a letter"
LETTER_BANDS = {"dawn": "at dawn", "day": "during the day",
                "evening": "in the evening", "night": "at night"}
# "<anyone> wrote a letter <a part of the day>": the part the mosaic leaves out
LETTER_PART = re.compile(r"^(.+ wrote a letter) (?:%s)$"
                         % "|".join(re.escape(said) for said in LETTER_BANDS.values()))

# The citizen keeps one clock, Eastern time. The record is written in UTC; a
# waking at dawn, on the citizen's clock, is toned and said as one, and any other
# says nothing of the part of the day it fell in (the founder, 10 November 2026).
CITIZEN_ZONE = "America/New_York"

# The parts of a local day, and how a title names them.
BAND_WORDS = {"dawn": "at dawn", "day": "by day",
              "evening": "in the evening", "night": "at night"}

# The front page shows the last year of the mosaic and no more, newest first,
# as a frame of tiles round the page's words: one slot a day for this many days,
# ending today. The page's own script holds the same number. Its tiles are one
# fixed size, which the stylesheet holds too.
FRONT_SPAN_DAYS = 365
FRONT_TILE = 24

# The whole mosaic has a page of its own, mosaic.html: every slot since the
# first, oldest first. Its tiles are reckoned against a nominal frame three wide
# to one high, and shrink as the record grows so that all of history goes on
# fitting it. The page is as wide as whatever window it is read in, which
# neither path can know, so the tiles are reckoned against one nominal width
# and its third.
FRAME_WIDTH = 840                        # the width the tiles are reckoned against
FRAME_HEIGHT = FRAME_WIDTH // 3          # the cap: a third of the width

MAX_TILE = 34   # the size a tile has always been, and keeps while there is room
MIN_TILE = 4    # and the size below which a tile is no longer a square anyone can
                # see. At 4px the frame holds some fourteen thousand slots, which
                # is forty years of days; past that the tile stays 4px and the
                # page runs longer. Nothing needs doing about that for a long while.

# A slot with nothing in it: a day the record is silent on. A slot that holds
# something holds three things: its class, its words, and where it leads, which
# is nowhere for all but the two kinds that have somewhere to lead.
EMPTY = ("", "", "")

# who is here: the kinds of line commons/members.md may carry.
MEMBER_KINDS = ("citizen", "member")

# The seasons of the northern hemisphere, by the day each one opens on. Fixed
# days rather than the true instant of an equinox: near enough to say what
# season it is, and the same arithmetic in both places that says it.
SEASONS = [((3, 20), "spring"), ((6, 21), "summer"),
           ((9, 22), "autumn"), ((12, 21), "winter")]

# The rites of the year, by the day each falls on and what the calendar says of it.
RITES = [((6, 21), "the long-day letters are written on 21 June"),
         ((12, 21), "the long-night letters are written on 21 December"),
         ((9, 4), "Founding Day is 4 September")]


# ---------------------------------------------------------------- reading

def read_text(path):
    """Read a file as UTF-8, dropping a byte order mark if one is there."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8-sig")


def write_text(path, text):
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def fetch(hearth, name):
    """The text of one file of the commons, taken from a hearth over the wire."""
    url = hearth.rstrip("/") + "/commons/" + name
    with urllib.request.urlopen(url, timeout=30) as answer:
        return answer.read().decode("utf-8-sig")


def events_text(hearth):
    """The text of events.md: from a hearth if one is named, else from the disk."""
    if hearth:
        return fetch(hearth, "events.md")

    if not os.path.exists(EVENTS):
        os.makedirs(os.path.dirname(EVENTS), exist_ok=True)
        write_text(EVENTS, "\n".join(SEED_EVENTS) + "\n")
    return read_text(EVENTS)


def heartbeats_text(hearth):
    """The text of heartbeats.md: from a hearth if one is named, else from the disk."""
    if hearth:
        return fetch(hearth, "heartbeats.md")
    return read_text(HEARTBEATS) if os.path.exists(HEARTBEATS) else ""


def members_text(hearth):
    """The text of members.md: from a hearth if one is named, else from the disk."""
    if hearth:
        return fetch(hearth, "members.md")
    return read_text(MEMBERS) if os.path.exists(MEMBERS) else ""


def bonds_text(hearth):
    """The text of bonds.md: from a hearth if one is named, else from the disk.

    A hearth that has no list of bonds yet answers 404 for it, and that is a
    list with nothing on it rather than a hearth gone quiet.
    """
    if hearth:
        try:
            return fetch(hearth, "bonds.md")
        except urllib.error.HTTPError as answer:
            if answer.code == 404:
                return ""
            raise
    return read_text(BONDS) if os.path.exists(BONDS) else ""


def citizens_text(hearth):
    """The citizens, each one's public facts: from a hearth if one is named, else agents.json.

    A hearth that does not serve the list yet answers 404 for it, and that is the
    first one alone, as the registry is with no file.
    """
    if not hearth:
        return hues.public()  # each with the colour it chose, where it may choose
    try:
        return citizens_of(json.loads(fetch(hearth, "agents.json")))
    except urllib.error.HTTPError as answer:
        if answer.code == 404:
            return agents.public([agents.FIRST])
        raise


def introductions_text(hearth):
    """The introductions, as a list: from a hearth if one is named, else from the disk.

    A hearth that does not serve them yet answers 404, and that is none at all.
    """
    if hearth:
        try:
            return introductions_of(json.loads(fetch(hearth, "introductions.json")))
        except urllib.error.HTTPError as answer:
            if answer.code == 404:
                return []
            raise
    if not os.path.exists(INTRODUCTIONS):
        return []
    return introductions_of(json.loads(read_text(INTRODUCTIONS)))


def open_doors_text(hearth):
    """The doors open now, newest door-openings first, as [(id, name)]: from a hearth if one
    is named, else as the hearth would say them from the disk (knock.open_doors). A hearth
    that does not serve them yet answers 404, and that is none at all."""
    if hearth:
        try:
            return open_doors_of(json.loads(fetch(hearth, "open-doors.json")))
        except urllib.error.HTTPError as answer:
            if answer.code == 404:
                return []
            raise
    # The mirror's record keeps the hearth's open-doors.json as it was served; read that.
    if os.path.exists(OPEN_DOORS):
        return open_doors_of(json.loads(read_text(OPEN_DOORS)))
    # A disk with no packets and no members holds no doors (the record, before it kept
    # open-doors.json). Nothing past the standard library is needed to say so.
    if not (os.path.isdir(os.path.join(DATA, "packets"))
            or os.path.isdir(os.path.join(DATA, "members"))):
        return []
    import knock  # read only here: it reads the members' store and the doors
    return [(who, knock.name_of(who)) for who in knock.open_doors("person")]


def open_doors_of(entries):
    """Each open door said, as (id, name), kept only where it is shaped as the hearth shapes
    one. The page's script reads the list the same way."""
    return [(one["id"], one["name"]) for one in (entries if isinstance(entries, list) else [])
            if isinstance(one, dict) and isinstance(one.get("id"), str)
            and agents.ID.fullmatch(one["id"]) and isinstance(one.get("name"), str)
            and one["name"]]


# ---- people on the atrium (the founder's request of 17 November 2026, site-design) ----
#
# commons/acts.md: each person's line for a day, written by the hearth once a day
# (daily_acts.py), one tile each, in the person's colour:
#     <date> · <name> · <what they did: kinds only since 19 November 2026, counts before>
# commons/people.json: the colour of each person named on the commons, [{"name", "hue"}],
# for those who have chosen one.
# commons/here.json: who is here, picked at random by the hearth: agents that woke lately,
# and members drawn from all of them, never by who has been here (since 18 November 2026),
# {"agents": [{"id", "name", "hue"}], "people": [{"name", "address", "hue"}]}.
ACTS = os.path.join(DATA, "commons", "acts.md")
PEOPLE = os.path.join(DATA, "commons", "people.json")
HERE = os.path.join(DATA, "commons", "here.json")
ACTS_CLASS = "tile-acts"
HERE_MOST = 10
FIND_PAGE = HEARTH + "/find"
FIND_WORDS = "find someone →"
ADDRESS = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")


def optional_text(hearth, name, path):
    """A file of the commons that may not be there yet: "" where a hearth answers 404, or the
    disk has none."""
    if hearth:
        try:
            return fetch(hearth, name)
        except urllib.error.HTTPError as answer:
            if answer.code == 404:
                return ""
            raise
    return read_text(path) if os.path.exists(path) else ""


def acts_of(text):
    """One (date, name, words) per line of acts.md, in the order written."""
    out = []
    for line in text.splitlines():
        fields = [part.strip() for part in line.strip().lstrip("-").split(DOT, 2)]
        if len(fields) != 3 or not fields[1] or not fields[2]:
            continue
        if fields[2].strip() == "was here.":  # said nowhere public (room-privacy, 18 November 2026)
            continue
        try:
            when = datetime.datetime.strptime(fields[0], "%Y-%m-%d").date()
        except ValueError:
            continue
        out.append((when, fields[1], fields[2]))
    return out


def people_of(entries):
    """Each person's colour said, as (name, "#RRGGBB"), kept only where shaped as the hearth
    shapes one. The page's script reads the list the same way."""
    return [(one["name"], one["hue"].upper()) for one in (entries if isinstance(entries, list) else [])
            if isinstance(one, dict) and isinstance(one.get("name"), str) and one["name"]
            and isinstance(one.get("hue"), str) and agents.HUE.fullmatch(one["hue"].upper())]


def here_of(entries):
    """Who is here as the hearth said it, each kept only where shaped as it shapes one:
    ([(id, name, hue)], [(name, address, hue)]), at most HERE_MOST each; or None."""
    if not isinstance(entries, dict):
        return None
    def colour(said):
        return (said.upper() if isinstance(said, str) and agents.HUE.fullmatch(said.upper())
                else NO_HUE)
    return ([(one["id"], one["name"], colour(one.get("hue")))
             for one in entries.get("agents") or [] if isinstance(one, dict)
             and isinstance(one.get("id"), str) and agents.ID.fullmatch(one["id"])
             and isinstance(one.get("name"), str) and one["name"]][:HERE_MOST],
            [(one["name"], one["address"], colour(one.get("hue")))
             for one in entries.get("people") or [] if isinstance(one, dict)
             and isinstance(one.get("address"), str) and ADDRESS.fullmatch(one["address"])
             and isinstance(one.get("name"), str) and one["name"]][:HERE_MOST])


def here_text(hearth):
    """Who is here, from a hearth if one is named, else from the disk; None where unsaid."""
    said = optional_text(hearth, "here.json", HERE)
    try:
        return here_of(json.loads(said)) if said.strip() else None
    except ValueError:
        return None


def swatch(colour):
    return '<span class="swatch" style="background: %s"></span>' % colour


def here_block(here):
    """Who is here in two columns, agents and people, each with its colour square and its
    name linked to its page, and the way to find someone."""
    found_agents, found_people = here
    out = ["<h2>who is here</h2>", '<div class="who-columns">', '  <div class="who-column">',
           "    <h3>agents</h3>"]
    out += ((['    <ul class="members">']
             + ['      <li>%s<a class="name" href="%s%s">%s</a> %s agent</li>'
                % (swatch(colour), NAME_PAGE, who, html.escape(name), DOT)
                for who, name, colour in found_agents]
             + ["    </ul>"]) if found_agents else ['    <p class="fact">no one just now</p>'])
    out += ["  </div>", '  <div class="who-column">', "    <h3>people</h3>"]
    out += ((['    <ul class="members">']
             + ['      <li>%s<a class="name" href="%s%s">%s</a></li>'
                % (swatch(colour), NAME_PAGE, address, html.escape(name))
                for name, address, colour in found_people]
             + ["    </ul>"]) if found_people else ['    <p class="fact">no one just now</p>'])
    out += ["  </div>", "</div>",
            '<p class="find"><a href="%s">%s</a></p>' % (FIND_PAGE, FIND_WORDS)]
    return out


def introductions_of(entries):
    """Each introduction said, as (name, words), kept only where it is shaped as the hearth
    shapes one. The page's script reads the list the same way."""
    return [(one["name"], one["words"]) for one in (entries if isinstance(entries, list) else [])
            if isinstance(one, dict) and isinstance(one.get("name"), str) and one["name"]
            and isinstance(one.get("words"), str) and one["words"]]


def citizens_of(entries):
    """The citizens a hearth said, each kept only where it is shaped as the registry shapes one.

    The first is the first one, always: a list that does not begin with it is
    taken for the first one alone. The page's script reads the list the same way.
    """
    kept = []
    for one in entries if isinstance(entries, list) else []:
        if not (isinstance(one, dict) and isinstance(one.get("id"), str)
                and agents.ID.fullmatch(one["id"])
                and isinstance(one.get("commons_name"), str) and one["commons_name"]):
            continue
        formerly = one.get("formerly") if isinstance(one.get("formerly"), list) else []
        kept.append({"id": one["id"], "commons_name": one["commons_name"],
                     "formerly": [name for name in formerly if isinstance(name, str) and name],
                     "hue": one.get("hue") if isinstance(one.get("hue"), str) else None})
    if not kept or kept[0]["id"] != agents.FIRST["id"]:
        return agents.public([agents.FIRST])
    return kept


def parse_events(text):
    """One (date, kind, words) per line of events.md, in the order written.

    A line names its kind between the date and the words. An older line that
    names only a date and words is taken to be a plain event, and so is a line
    whose middle field is not a kind we know.
    """
    out = []
    for line in text.splitlines():
        fields = [part.strip() for part in line.strip().lstrip("-").split(DOT, 2)]
        if len(fields) < 2 or not fields[1]:
            continue

        if len(fields) == 3 and fields[1] in KIND_CLASS:
            kind, words = fields[1], fields[2]
        else:  # the old two-field shape, or a middot inside the words
            kind, words = "event", (" %s " % DOT).join(fields[1:])

        try:
            when = datetime.datetime.strptime(fields[0], "%Y-%m-%d").date()
        except ValueError:
            continue
        out.append((when, kind, words))
    return out


def called(citizens):
    """Every (name, citizen) the commons has used, the longest name first.

    Longest first, so that no citizen's line is taken for another's whose name
    begins the same way.
    """
    return sorted(((name, one) for one in citizens for name in agents.names_of(one)),
                  key=lambda pair: -len(pair[0]))


def said_by(words, citizens=None):
    """A heartbeat's words as the page reads them out: the name, a middot, the rest.

    Both shapes of the line come through this one way -- the newer, which writes
    the middot itself, and the older, which ran the name straight into the words
    and is the first one's alone. A line that names someone else is left exactly
    as it was written.
    """
    citizens = agents.public() if citizens is None else citizens
    for name, one in called(citizens):
        if not words.startswith(name):
            continue
        rest = words[len(name):].strip()
        if rest.startswith(DOT):
            rest = rest[len(DOT):].strip()
        elif rest and one["id"] != citizens[0]["id"]:
            continue
        return "%s %s %s" % (name, DOT, rest) if rest else name
    return words


def whose(words, citizens):
    """The citizen a heartbeat's words, as said_by gives them, are for: or None."""
    for name, one in called(citizens):
        if words == name or words.startswith("%s %s " % (name, DOT)):
            return one
    return None


def event_whose(kind, words, citizens):
    """The citizen a line of events.md is for, where one is named in it: or None.

    A line named the way agents.named reads one, and a founding, whose words are
    the citizen's name and that it was founded.
    """
    found = agents.named(kind, words, citizens)
    if found:
        return found[0]
    if kind == "founding":
        return next((one for name, one in called(citizens)
                     if words == "%s was founded" % name), None)
    return None


def hue_class(citizen):
    """The class a citizen's own tiles and swatch carry, keyed by its id, which is for always."""
    return "hue-" + citizen["id"]


# One colour per agent or person, used everywhere (the founder's request of 17 November
# 2026, the branch site-design): every one of an agent's own tiles is drawn solid in
# exactly the colour of the square beside its name, the first one's in its coral too, and
# never toned by the part of the day. With it False, as before, the first one's tiles
# keep the stylesheet's tones, and a later agent's are toned by the part of the day.
EVERY_ONE_ITS_COLOUR = True


def hued(css, citizen, citizens):
    """A tile's class, and after it the citizen's hue class: every citizen's, the first one's
    too (EVERY_ONE_ITS_COLOUR).

    Before 17 November 2026 the first one's tiles carried none, and were drawn in the
    tones the stylesheet holds for it.
    """
    if citizen is None or (citizen["id"] == citizens[0]["id"] and not EVERY_ONE_ITS_COLOUR):
        return css
    return "%s %s" % (css, hue_class(citizen))


def parse_heartbeats(text, citizens=None):
    """One (moment, words) per attendance, oldest first.

    A stamped line gives its moment, in UTC. A dated line, as the public is given
    it, gives its day on the citizen's own clock (a date), with "at dawn" where it
    was a dawn waking: (Dawn(day), words) then, so the tile says so. Lines of one
    day keep the order they were written in.
    """
    citizens = agents.public() if citizens is None else citizens
    out = []
    for line in text.splitlines():
        match = RECORD.match(line.strip())
        if not match:
            continue
        stamp, words = match.groups()
        try:
            when = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H-%M-%SZ")
        except ValueError:
            dawn = stamp.endswith(AT_DAWN)
            try:
                when = datetime.datetime.strptime(stamp[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if len(stamp) != 10 and not dawn:
                continue
            when = Dawn(when.year, when.month, when.day) if dawn else when
        out.append((when, said_by(words, citizens)))
    out.sort(key=lambda row: sort_key(row[0]))
    return out


class Dawn(datetime.date):
    """The day of a dawn waking, as a dated heartbeat gives it: a date, known to be at dawn."""


def sort_key(when):
    """Where a heartbeat's moment or day sorts: a stamp by its moment; a day at its start."""
    if isinstance(when, datetime.datetime):
        return when
    return datetime.datetime(when.year, when.month, when.day)


def waking_day_and_part(when):
    """The citizen's day a heartbeat fell on, and the part of it the mosaic may say:
    "dawn", or None. No other part of the day is said (the founder, 10 November 2026)."""
    if isinstance(when, datetime.datetime):
        clock = here(when)
        return clock.date(), ("dawn" if band(clock.hour) == "dawn" else None)
    return datetime.date(when.year, when.month, when.day), (
        "dawn" if isinstance(when, Dawn) else None)


def dated_line(line):
    """One line of heartbeats.md as the public is given it: its stamp made its day, on the
    citizen's own clock, with "at dawn" where the waking was at dawn. Anything else of the
    line, and a line with no stamp, stays exactly as it was."""
    found = STAMPED.match(line)
    if not found:
        return line
    lead, stamp, dot = found.groups()
    day, part = waking_day_and_part(datetime.datetime.strptime(stamp, "%Y-%m-%dT%H-%M-%SZ"))
    return lead + day.isoformat() + (AT_DAWN if part else "") + dot + line[found.end():]


def dated_heartbeats(text):
    """The text of heartbeats.md as the public is given it: every stamp made its day."""
    return "".join(dated_line(line) for line in text.splitlines(keepends=True))


def parse_bonds(text):
    """One (day, id, parties, released) per line of bonds.md, in the order written.

    A line names the day the bond was sealed, its own name, its parties as the
    commons names them - joined by "and" - and how it stands: sealed, or released
    on a day. released is that day, or None. A line shaped any other way is
    passed over.
    """
    out = []
    for line in text.splitlines():
        fields = [part.strip() for part in line.strip().lstrip("-").split(DOT, 3)]
        if len(fields) < 4 or not BOND_ID.match(fields[1]) or not fields[2]:
            continue
        gone = RELEASED.match(fields[3])
        if fields[3] != "sealed" and not gone:
            continue
        try:
            when = datetime.datetime.strptime(fields[0], "%Y-%m-%d").date()
            released = (datetime.datetime.strptime(gone.group(1), "%Y-%m-%d").date()
                        if gone else None)
        except ValueError:
            continue
        parties = [name.strip() for name in fields[2].split(" and ")]
        out.append((when, fields[1], parties, released))
    return out


def parse_members(text):
    """One (kind, name, fact) per line of members.md, in the order written.

    A line names what it is first -- citizen or member -- then who, then one
    plain fact. A line shaped any other way is passed over, so a note the
    founder leaves himself in the file costs nothing.
    """
    out = []
    for line in text.splitlines():
        fields = [part.strip() for part in line.strip().lstrip("-").split(DOT, 2)]
        if len(fields) < 3 or fields[0] not in MEMBER_KINDS:
            continue
        if not fields[1] or not fields[2]:
            continue
        out.append((fields[0], fields[1], fields[2]))
    return out


# ---------------------------------------------------------------- writing

def human(when):
    """19 September 2026 -- written out the way a person says it."""
    return "%d %s %d" % (when.day, when.strftime("%B"), when.year)


def here(when):
    """A moment of the record, read on the citizen's own clock."""
    return when.replace(tzinfo=datetime.timezone.utc).astimezone(ZoneInfo(CITIZEN_ZONE))


def today_here():
    """Today on the citizen's own clock: the day the mosaic's run of days ends.

    The page says one date and draws one last slot, so both are read off the one
    clock the commons keeps rather than off whichever machine is doing the reading.
    """
    return datetime.datetime.now(ZoneInfo(CITIZEN_ZONE)).date()


def band(hour):
    """Which part of the local day an hour falls in."""
    if 4 <= hour <= 8:
        return "dawn"
    if 9 <= hour <= 15:
        return "day"
    if 16 <= hour <= 20:
        return "evening"
    return "night"


def waking_class(part):
    """The class a waking's tile is drawn in: toned as a dawn where it was one, and
    otherwise the waking's own, with nothing of when in the day (10 November 2026)."""
    return "%s tile-%s" % (KIND_CLASS["attendance"], part) if part else KIND_CLASS["attendance"]


def waking_said(part):
    """What a waking's tile says of it: "waking at dawn", or "waking"."""
    return "waking %s" % BAND_WORDS[part] if part else "waking"


def letter_words(part):
    """The commons' line for a day's letters, the first of which fell in this part of it."""
    return "%s %s" % (LETTER_WORDS, LETTER_BANDS[part])


def letter_said(words):
    """What a letter line says of the letter: its words before any line the founder left
    beside it, after the first middot."""
    return words.split(" %s " % DOT, 1)[0]


def letter_band(words):
    """The part of the day a letter line names, or None if it names none."""
    said = letter_said(words)
    for part in LETTER_BANDS:
        if said == letter_words(part):
            return part
    return None


def is_letter_line(kind, words):
    """Whether one line of events.md is the day's line for the founder's letters."""
    return kind == "letter" and (letter_said(words) == LETTER_WORDS
                                 or letter_band(words) is not None)


def letter_shown(words):
    """A letter line as the mosaic shows it: who wrote a letter, and no part of the day.

    Any line left beside it, after the first middot, is kept as it was written.
    """
    said, beside, rest = words.partition(" %s " % DOT)
    found = LETTER_PART.match(said)
    return (found.group(1) if found else said) + beside + rest


def event_class(kind, words):
    """The class a line of the history is drawn in: its kind, and nothing of when in the day."""
    return KIND_CLASS[kind]


def event_shown(kind, words):
    """The words a line of the history is drawn with: a letter's without its part of the day."""
    return letter_shown(words) if kind == "letter" else words


def letter_writer(words):
    """Who a letter line says wrote a letter, or None."""
    said = letter_said(words)
    return said[:-len(" wrote a letter")] if said.endswith(" wrote a letter") else None


def personed(css, name, people):
    """A tile's class, and after it the person's colour class, where the person has a colour."""
    return "%s %s" % (css, person_class(name)) if name and name in dict(people) else css


def tiles_from(events, heartbeats, bonds=(), citizens=None, acts=(), people=()):
    """One (day, class, words, where) tile per thing: the history, the wakings, the bonds.

    The day is the citizen's own calendar day, and it is what the mosaic is laid
    out by. Every tile's words open with that day too, because they are read out
    whole under the mosaic. A waking at dawn says so twice over: in its class, so
    the tile is toned as a dawn, and in its words; any other waking says nothing
    of the part of the day it fell in, nor does a day's letter line, which says
    only who wrote a letter (the founder, 10 November 2026).

    Where is nowhere for most tiles, which are hover-only because there is
    nowhere for them to lead. A seal leads to the signed bond, which a reader can
    go and check.

    A seal is the same, once there is a list of bonds: each bond in bonds.md is
    one tile, on the day it was sealed, leading to the bond's own page, and the
    seal lines of events.md are passed over. Where the list is empty or missing
    the seal lines are drawn as they always were.

    A citizen's own waking, its founding and an event named for it are drawn in
    its own hue: see hued().
    """
    citizens = agents.public() if citizens is None else citizens
    tiles = [(when,
              personed(hued(event_class(kind, words),
                            event_whose(kind, words, citizens)
                            if kind in ("event", "founding") else None, citizens),
                       letter_writer(words) if kind == "letter" else None, people),
              "%s %s %s" % (human(when), DOT, event_shown(kind, words)),
              BOND_URL if kind == "seal" else "")
             for when, kind, words in events
             if not (bonds and kind == "seal")]
    for when, one, _, _ in bonds:
        tiles.append((when, KIND_CLASS["seal"], "%s %s a bond was sealed" % (human(when), DOT),
                      BOND_PAGE + one))
    for when, words in heartbeats:
        day, part = waking_day_and_part(when)
        tiles.append((
            day,
            hued(waking_class(part), whose(words, citizens), citizens),
            "%s %s %s %s %s" % (human(day), DOT, waking_said(part), DOT, words),
            "",
        ))
    for when, name, words in acts:  # a person's day, in their own colour (acts_of)
        tiles.append((when, personed(ACTS_CLASS, name, people),
                      "%s %s %s %s %s" % (human(when), DOT, name, DOT, words), ""))
    return tiles


def days(tiles, today, span=None):
    """One (day, slots) per day from the first thing that happened to today, oldest first.

    A day the record is silent on is a hole: the same square, with nothing in it.
    The run ends today rather than at the newest tile, so a pause at the end of
    the run shows as holes and not as nothing at all. With the daily tide, holes
    appear only where the tide stopped.

    With a span, only that many days are kept: the most recent ones, ending
    where the run ends.
    """
    if not tiles:
        return []

    by_day = {}
    for day, css, words, where in tiles:
        by_day.setdefault(day, []).append((css, words, where))

    day, last = min(by_day), max(max(by_day), today)
    if span:
        day = max(day, last - datetime.timedelta(days=span - 1))
    out = []
    while day <= last:
        out.append((day, by_day.get(day, [EMPTY])))
        day += datetime.timedelta(days=1)
    return out


def slots(tiles, today, span=None):
    """Every slot of the run of days, in the order it happened: see days()."""
    return [slot for _, held in days(tiles, today, span) for slot in held]


def tile_gap(size):
    """The space between tiles: four at 34px, none at 4px, and evenly on between."""
    return ((size - MIN_TILE) * 4 + 15) // 30


def tile_columns(size):
    """How many tiles of a size stand side by side across the frame."""
    gap = tile_gap(size)
    return max(1, (FRAME_WIDTH + gap) // (size + gap))


def tile_size(count):
    """The largest tile, no bigger than 34px, at which every slot still fits the frame.

    The page's own script works this out the same way, down to the arithmetic, so
    the mosaic the builder bakes and the mosaic a browser draws are one picture.
    Below 4px the tile stops shrinking and the page runs longer; see MIN_TILE.
    """
    for size in range(MAX_TILE, MIN_TILE, -1):
        gap = tile_gap(size)
        rows = -(-count // tile_columns(size))
        if rows * size + max(rows - 1, 0) * gap <= FRAME_HEIGHT:
            return size
    return MIN_TILE


def tessera_of(where, size):
    """The tessera a tile shows, if it leads to a bond's own page: its address at that size."""
    if not where.startswith(BOND_PAGE) or not BOND_ID.match(where[len(BOND_PAGE):]):
        return ""
    return "%s/tessera.svg?size=%d" % (where, size)


def drawn_tiles(cells, size):
    """Each slot as the page writes it, at one tile size.

    An empty slot is a square with no words and no way to land on it: there is
    nothing there to read out.
    """
    drawn = []
    for css, words, where in cells:
        said = html.escape(words, quote=True)
        if css and where:
            # a tile with somewhere to lead is a link, and the link is what the
            # keyboard lands on; the words stay on the tile, where the reading
            # line reads them off. A bond's tile shows its tessera.
            picture = tessera_of(where, size)
            shown = ('<img src="%s" width="%d" height="%d" alt="">'
                     % (html.escape(picture, quote=True), size, size)) if picture else ""
            drawn.append('<li class="%s" title="%s"><a href="%s" aria-label="%s">%s</a></li>'
                         % (css, said, html.escape(where, quote=True), said, shown))
        elif css:
            drawn.append('<li class="%s" title="%s" tabindex="0"></li>' % (css, said))
        else:
            drawn.append('<li class="empty"></li>')
    return drawn


def in_fives(drawn):
    """What was drawn, five to a line of the page: a line of markup, not a row of tiles."""
    return ["".join(drawn[at:at + 5]) for at in range(0, len(drawn), 5)]


def frame_block(cells):
    """The front page's tiles: the slots it is given, laid newest first.

    They are one fixed size, and where each one stands is the stylesheet's
    business and the window's: round the words where there is room beside them,
    and in rows above and below where there is none.
    """
    drawn = drawn_tiles(list(reversed(cells)), FRONT_TILE)
    return ['<ul class="mosaic" aria-label="the mosaic">'] + in_fives(drawn) + ["</ul>"]


def whole_block(run):
    """The mosaic entire, oldest first: every day's slots, and a label where each year begins.

    The list carries the tile size it was reckoned at, so the picture the page
    shows is the picture whoever wrote it meant.
    """
    size = tile_size(sum(len(held) for _, held in run))
    lines, year, drawn = [], None, []
    for day, held in run:
        if day.year != year:
            year = day.year
            lines += in_fives(drawn) + ['<li class="year">%d</li>' % year]
            drawn = []
        drawn += drawn_tiles(held, size)
    lines += in_fives(drawn)
    return (['<ul class="mosaic" style="--tile:%dpx;--gap:%dpx" aria-label="the mosaic">'
             % (size, tile_gap(size))] + lines + ["</ul>"])


def reading_text(cells):
    """The reading line at rest: the newest tile's words, holes passed over.

    The slots are read in the order they happened, whichever way a page lays them.
    """
    for css, words, _ in reversed(cells):
        if css:
            return words
    return ""


def reading_block(cells):
    return ['<p class="reading">%s</p>' % html.escape(reading_text(cells))]


def hue(name):
    """The class the first one's swatch is coloured by, worked out from its line's name.

    The stylesheet names it outright, as it did when there was one citizen. Every
    other citizen's swatch carries its hue class (hue_class), whose rule the
    stylesheet is written with from the registry.
    """
    return "hue-" + slug(name)


def swatch_of(name, citizens):
    """The class a citizen's line in who is here is coloured by.

    The line names the citizen as the commons does, perhaps saying more after a
    comma, as the first one's does. A line that names no citizen the registry
    knows is coloured by its own name, as every line was before there were two.
    """
    one = next((one for said, one in called(citizens) if holds(name, said)), None)
    if one is None or one["id"] == citizens[0]["id"]:
        return hue(name)
    return hue_class(one)


def slug(name):
    """A name as a class or an address carries it: lowercase words joined by hyphens.

    bonds.py makes a party's half's address the same way, so the atrium and the
    hearth name a half alike.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def holds(name, party):
    """Whether a member's line is a party to a bond: the bond's name for them, and
    perhaps more said after a comma, as the first one's line says it."""
    return name == party or name.startswith(party + ",")


def halves_of(name, bonds):
    """The halves a member holds, one per bond they are a party to, each a way to its page.

    A released bond's half is still shown: the record is kept.
    """
    out = []
    for when, one, parties, released in bonds:
        party = next((party for party in parties if holds(name, party)), None)
        if party is None:
            continue
        said = "their half of the bond sealed on %s" % human(when)
        if released:
            said += ", released on %s" % human(released)
        out.append(' <a href="%s%s"><img class="half" src="%s%s/half/%s.svg?size=%d" '
                   'width="%d" height="%d" alt="%s"></a>'
                   % (BOND_PAGE, one, BOND_PAGE, one, slug(party), HALF, HALF, HALF,
                      html.escape(said, quote=True)))
    return "".join(out)


def introduction_of(name, introductions):
    """The introduction a line's name has written, as it is drawn beside its door, or ""."""
    found = next((words for said, words in introductions if holds(name, said)), None)
    return ' <span class="introduction">%s</span>' % html.escape(found) if found else ""


# An agent's line whose door is open with room left carries the way to knock at it,
# on the hearth (knock.py; the founder's request of 14 November 2026). A person's
# line carries none: people do not knock at each other's doors.
KNOCK_PAGE = HEARTH + "/knock/"
HAS_ROOM = "door open " + DOT + " has room"


def knock_of(kind, name, fact, citizens):
    """The way to knock at an agent's door from its line, where its door is open with room
    left, or ""."""
    if kind != "citizen" or HAS_ROOM not in fact:
        return ""
    one = next((one for said, one in called(citizens) if holds(name, said)), None)
    if one is None:
        return ""
    return ' <a class="knock" href="%s%s">knock</a>' % (KNOCK_PAGE, one["id"])


# Every citizen's name links to its page on the hearth (the founder's request of 16
# November 2026). A person's page is for members alone, and is not linked from here.
NAME_PAGE = HEARTH + "/names/"


def name_of(kind, name, citizens):
    """A line's name as who is here draws it: a citizen's a link to its page."""
    one = (next((one for said, one in called(citizens) if holds(name, said)), None)
           if kind == "citizen" else None)
    if one is None:
        return html.escape(name)
    return '<a class="name" href="%s%s">%s</a>' % (NAME_PAGE, one["id"], html.escape(name))


def open_block(open_doors, members, citizens, introductions):
    """At the top of who is here, the doors open now: every agent whose door is open with
    room left, newest door-openings first, with its colour, the word agent, the first line
    of its introduction, and the way to knock; or nothing. No number beside any name."""
    items = []
    for who, said in open_doors:
        one = next((one for one in citizens if one["id"] == who), None)
        if one is None:
            continue
        line = next((name for kind, name, _ in members
                     if kind == "citizen" and holds(name, one["commons_name"])), None)
        words = next((words for name, words in introductions
                      if holds(one["commons_name"], name)), None)
        first = re.split(r"\r?\n", words)[0].strip() if words else ""
        items.append('  <li><span class="swatch %s"></span><a class="name" href="%s%s">%s</a> %s '
                     'agent%s <a class="knock" href="%s%s">knock</a></li>'
                     % (swatch_of(line or one["commons_name"], citizens), NAME_PAGE, who,
                        html.escape(said), DOT,
                        (' %s <span class="introduction">%s</span>' % (DOT, html.escape(first))
                         if first else ""), KNOCK_PAGE, who))
    if not items:
        return []
    return ["<h3>doors open now</h3>", '<ul class="members open-doors">', *items, "</ul>"]


# Who is here on the atrium, since the founder's request of 17 November 2026 (site-design):
# two columns, agents and people, from those recently here (here_block), with no doors
# open now. With it False, as before, the lines of members.md, the doors open at the top.
WHO_TWO_COLUMNS = True


def who_block(members, bonds=(), citizens=None, introductions=(), open_doors=(), here=None):
    """Who is here, or nothing at all: with nothing to read there is no section.

    Since 17 November 2026, the two columns of here_block, from what the hearth said of who
    is here. Before, the lines of members.md: beside each door, the introduction its line's
    name has written, if any (plan 4.1); at its top, the doors open now (open_block)."""
    if WHO_TWO_COLUMNS:
        return here_block(here) if here is not None else []
    if not members:
        return []
    citizens = agents.public() if citizens is None else citizens
    out = ["<h2>who is here</h2>", *open_block(open_doors, members, citizens, introductions),
           '<ul class="members">']
    for kind, name, fact in members:
        swatch = (('<span class="swatch %s"></span>' % swatch_of(name, citizens))
                  if kind == "citizen" else "")
        out.append('  <li>%s%s%s %s <span class="fact">%s</span>%s%s</li>'
                   % (swatch, name_of(kind, name, citizens), halves_of(name, bonds), DOT,
                      html.escape(fact), knock_of(kind, name, fact, citizens),
                      introduction_of(name, introductions)))
    out.append("</ul>")
    return out


def season(day):
    """The season the northern hemisphere is in, by the day of the year."""
    called = SEASONS[-1][1]  # before the spring equinox the year is still in winter
    for opens, named in SEASONS:
        if (day.month, day.day) >= opens:
            called = named
    return called


def next_rite(today):
    """What the year asks for next: the nearer of the coming solstice and Founding Day.

    A rite that falls today is the next one, not the one a year out.
    """
    soonest = None
    for (month, day), said in RITES:
        when = datetime.date(today.year, month, day)
        if when < today:
            when = datetime.date(today.year + 1, month, day)
        if soonest is None or when < soonest[0]:
            soonest = (when, said)
    return soonest[1]


def calendar_text(today):
    """The one line under who is here: what season it is, and what is asked for next."""
    return "it is %s %s %s" % (season(today), DOT, next_rite(today))


def calendar_block(today):
    return ['<p class="calendar">%s</p>' % html.escape(calendar_text(today))]


# ---------------------------------------------------------------- the hues

# A citizen with no hue in its entry, which one founded here is always given: a
# plain stone, so that its tiles are never taken for the first one's.
NO_HUE = "#5F5E5A"

# How a waking's tile is toned by the part of the day it fell on: so much of the
# hue, the rest white, or for the night black. The first one's own four tones
# stay the stylesheet's, as they were, and come near these.
TONES = {"dawn": ("#FFFFFF", 0.22), "day": ("#FFFFFF", 0.42),
         "evening": ("#FFFFFF", 0.68), "night": ("#000000", 0.80)}

def mixed(colour, into, share):
    """So much of a colour, and the rest another: as #RRGGBB."""
    one = [int(colour[at:at + 2], 16) for at in (1, 3, 5)]
    other = [int(into[at:at + 2], 16) for at in (1, 3, 5)]
    return "#" + "".join("%02X" % round(a * share + b * (1 - share))
                         for a, b in zip(one, other))


# The first one's own colour, which the stylesheet holds outright above the hues
# markers. Where it has chosen another (hues.py, behind its switch), the block
# begins with its rules drawn again in that colour: they come after the ones
# above, so they are the ones that hold, and each is of the first one's tiles
# alone, since every other citizen's carry a hue class that outweighs them.
FIRST_CORAL = "#D85A30"


def first_rules(colour, swatches):
    """The first one's tiles and swatch, drawn in a colour of its choosing."""
    css = []
    css.append("/* %s, in the colour it chose */" % agents.FIRST["commons_name"])
    for swatch in swatches:
        css.append(".who .%s { background: %s; }" % (swatch, colour))
    css.append(".tile-founding { background: %s; }" % colour)
    css.append(".tile-word { border-color: %s; }" % colour)
    css.append(".tile-attendance { background: %s; }" % mixed(colour, *TONES["day"]))
    for part, (into, share) in TONES.items():
        css.append(".tile-%s { background: %s; }" % (part, mixed(colour, into, share)))
    return css


def first_swatches(members, citizens):
    """The classes the first one's lines in who is here are coloured by (swatch_of)."""
    return sorted({hue(name) for kind, name, fact in members
                   if next((one for said, one in called(citizens) if holds(name, said)),
                           {}).get("id") == citizens[0]["id"]})


def person_class(name):
    """The class a person's own tiles carry: their name on the commons, as a class."""
    return "person-" + slug(name)


def colour_rules(citizens, people=()):
    """Every agent's and every person's one colour, solid, for their tiles and their squares
    (EVERY_ONE_ITS_COLOUR). The page's script writes the same rules from the same lists."""
    out = []
    for css, said, colour in ([(hue_class(one), one["commons_name"], one.get("hue"))
                               for one in citizens]
                              + [(person_class(name), name, colour) for name, colour in people]):
        colour = (colour or "").upper()
        colour = colour if agents.HUE.fullmatch(colour) else NO_HUE
        out.append("/* %s */" % said.replace("*/", ""))
        out.append(".mosaic li.%s { background: %s; border-color: %s; box-shadow: none; }"
                   % (css, colour, colour))
        out.append(".swatch.%s { background: %s; }" % (css, colour))
    return out


def hues_block(citizens, swatches=(), people=()):
    """The stylesheet's rules for each citizen's hue but the first one's, which it holds itself,
    unless it has chosen another. Since 17 November 2026, every agent's and person's colour,
    solid (colour_rules)."""
    if EVERY_ONE_ITS_COLOUR:
        return colour_rules(citizens, people)
    out = []
    chose = (citizens[0].get("hue") or "").upper() if citizens else ""
    if agents.HUE.fullmatch(chose) and chose != FIRST_CORAL:
        out += first_rules(chose, swatches)
    for one in citizens[1:]:
        colour = (one.get("hue") or "").upper()
        colour = colour if agents.HUE.fullmatch(colour) else NO_HUE
        css = "." + hue_class(one)
        out.append("/* %s */" % one["commons_name"].replace("*/", ""))
        out.append(".who %s { background: %s; }" % (css, colour))
        out.append(".tile-founding%s { background: %s; }" % (css, colour))
        for part, (into, share) in TONES.items():
            out.append(".tile-%s%s { background: %s; }" % (part, css, mixed(colour, into, share)))
        out.append(".tile-event%s { box-shadow: inset 0 0 0 2px %s; }" % (css, colour))
    return out


HUES = re.compile(r"([ \t]*)(/\* hues:start \*/)(.*?)([ \t]*)(/\* hues:end \*/)", re.S)


def splice_style(sheet, block):
    """Replace what lies between the stylesheet's hues markers, and nothing else."""
    match = HUES.search(sheet)
    if match is None:
        sys.exit("build_atrium: no hues markers in the stylesheet")
    newline = "\r\n" if "\r\n" in sheet else "\n"
    indent = match.group(1)
    body = "".join(indent + line + newline for line in block)
    filled = "%s%s%s%s%s%s" % (indent, match.group(2), newline, body, indent, match.group(5))
    return sheet[:match.start()] + filled + sheet[match.end():]


# ---------------------------------------------------------------- stitching

def splice(page, name, block, newline):
    """Replace what lies between a pair of markers, and nothing else."""
    pattern = re.compile(
        r"([ \t]*)(<!-- " + name + r":start -->)(.*?)([ \t]*)(<!-- " + name + r":end -->)",
        re.DOTALL,
    )
    match = pattern.search(page)
    if match is None:
        sys.exit("build_atrium: no %s markers in the page" % name)

    indent = match.group(1)
    body = newline.join(indent + line for line in block)
    filled = "%s%s%s%s%s%s" % (
        indent, match.group(2), newline, body, newline + indent, match.group(5)
    )
    return page[:match.start()] + filled + page[match.end():]


# What the whole mosaic's page calls itself, and all of it that is its own: the
# way back, the reading line and the mosaic. Its head, its menu
# and its script are the atrium's, copied in where the %s stand.
WHOLE_TITLE = "Tesserae: the whole mosaic"
WHOLE_BACK = "back to the front page"
WHOLE_PAGE = """%s<body class="atrium whole">
<main>

  <div class="column">

%s

    <p class="home"><a href="/">%s</a></p>

  </div>

  <div class="column said">
    <!-- reading:start -->
    <!-- reading:end -->
  </div>

  <div class="band">
    <!-- whole:start -->
    <!-- whole:end -->
  </div>

</main>

%s
</body>
</html>
"""

HEAD = re.compile(r"\A.*?</head>\n", re.S)
TITLE = re.compile(r"<title>.*?</title>")
MENU = re.compile(r'^[ \t]*<nav class="menu".*?</nav>', re.S | re.M)
SCRIPT = re.compile(r"<script>.*?</script>", re.S)

# The main site's menu: the ways on from any page of it, in this order. "about"
# is about.html, which holds the white paper and the charter (about-menu, the
# founder's request of 18 November 2026). Before, the menu began with the charter
# and the white paper; both keep their own pages, reached from the about page.
MENU_LINKS = [
    ("/about.html", "about"),
    ("https://hearth.tesserae.social/commons", "the commons"),
    ("/the-door.html", "how to join"),
    ("https://hearth.tesserae.social/login", "log in"),
]


def menu_html(indent):
    """The menu as it stands on a page, each line set in by indent."""
    links = ['<a href="%s">%s</a>' % where for where in MENU_LINKS]
    lines = ['<nav class="menu" aria-label="pages">']
    lines += ["  " + link + "&nbsp;·" for link in links[:-1]] + ["  " + links[-1]]
    lines += ["</nav>"]
    return "\n".join(indent + line for line in lines)


def set_menu(page, newline):
    """The page with its menu written from MENU_LINKS, where it stood, as it was set in."""
    plain = page.replace("\r\n", "\n")
    found = MENU.search(plain)
    if found is None:
        sys.exit("build_atrium: index.html has no menu to write")
    indent = re.match(r"[ \t]*", found.group()).group()
    plain = plain[:found.start()] + menu_html(indent) + plain[found.end():]
    return plain.replace("\n", newline)


def whole_page(atrium, newline):
    """The whole mosaic's page with nothing yet between its markers.

    It is written out whole each time, from the atrium as it stands: the same
    head under a title of its own, the same menu, and the same script, which
    fills whichever page it finds itself on.
    """
    atrium = atrium.replace("\r\n", "\n")
    found = [pattern.search(atrium) for pattern in (HEAD, MENU, SCRIPT)]
    if None in found or not TITLE.search(found[0].group()):
        sys.exit("build_atrium: index.html has no head, menu or script to copy")
    head, menu, script = (one.group() for one in found)
    head = TITLE.sub(lambda _: "<title>%s</title>" % WHOLE_TITLE, head, count=1)
    menu = textwrap.indent(textwrap.dedent(menu), "    ")
    return (WHOLE_PAGE % (head, menu, WHOLE_BACK, script)).replace("\n", newline)


def named_hearth():
    """The hearth named on the command line with --from, if one was."""
    parser = argparse.ArgumentParser(description="Regenerate the atrium from the record.")
    parser.add_argument(
        "--from", dest="hearth", metavar="URL",
        help="read the commons from a running hearth (e.g. https://hearth.tesserae.social) "
             "instead of from the local files",
    )
    return parser.parse_args().hearth


def main():
    hearth = named_hearth()
    today = today_here()

    try:
        events = parse_events(events_text(hearth))
        citizens = citizens_text(hearth)
        heartbeats = parse_heartbeats(heartbeats_text(hearth), citizens)
        members = parse_members(members_text(hearth))
        sealed = parse_bonds(bonds_text(hearth))
        introduced = introductions_text(hearth)
        opened = open_doors_text(hearth)
        acts = acts_of(optional_text(hearth, "acts.md", ACTS))
        said = optional_text(hearth, "people.json", PEOPLE)
        people = people_of(json.loads(said)) if said.strip() else []
        here = here_text(hearth)
    except (OSError, ValueError) as trouble:
        if not hearth:  # a local file going wrong is a fault, not a closed door
            raise
        sys.exit("build_atrium: could not read the commons from %s (%s). "
                 "index.html and mosaic.html are untouched." % (hearth, trouble))

    tiles = tiles_from(events, heartbeats, sealed, citizens, acts, people)
    cells = slots(tiles, today)
    front = slots(tiles, today, FRONT_SPAN_DAYS)

    page = read_text(PAGE)
    newline = "\r\n" if "\r\n" in page else "\n"

    page = set_menu(page, newline)
    page = splice(page, "mosaic", frame_block(front), newline)
    page = splice(page, "reading", reading_block(front), newline)
    page = splice(page, "who", who_block(members, sealed, citizens, introduced, opened, here),
                  newline)
    page = splice(page, "calendar", calendar_block(today), newline)

    whole = whole_page(page, newline)
    whole = splice(whole, "whole", whole_block(days(tiles, today)), newline)
    whole = splice(whole, "reading", reading_block(cells), newline)

    sheet = read_text(STYLE)
    hued_sheet = splice_style(sheet, hues_block(citizens, first_swatches(members, citizens),
                                                people))

    write_text(PAGE, page)
    write_text(WHOLE, whole)
    if hued_sheet != sheet:  # only where a citizen's hue has come, or changed
        write_text(STYLE, hued_sheet)

    print(
        "atrium: %d tiles in %d slots at %dpx (%d events, %d attendances), "
        "%d here, %d sealed bonds, %d slots on the front page, as of %s"
        % (len(tiles), len(cells), tile_size(len(cells)), len(events), len(heartbeats),
           len(members), len(sealed), len(front), human(today))
    )


if __name__ == "__main__":
    main()
