#!/usr/bin/env python3
"""Regenerate the atrium from the record.

Rewrites only the text between the marker comments in index.html:

    <!-- mosaic:start -->   ...  <!-- mosaic:end -->
    <!-- reading:start -->  ...  <!-- reading:end -->
    <!-- caption:start -->  ...  <!-- caption:end -->
    <!-- offering:start --> ...  <!-- offering:end -->
    <!-- who:start -->      ...  <!-- who:end -->
    <!-- calendar:start --> ...  <!-- calendar:end -->
    <!-- bench:start -->    ...  <!-- bench:end -->
    <!-- links:start -->    ...  <!-- links:end -->

Everything outside those markers is left byte for byte as it was.

It reads:
    commons/heartbeats.md          the attendances
    commons/events.md              the history (created if missing)
    commons/bench.md               the lines passersby have left
    commons/members.md             who is here
    commons/offerings.md           what the two of them have given the commons,
                                   and commons/offerings/<id>.json beside it for
                                   the newest one, which is shown whole

commons/members.md is the one file of the commons nothing writes: the founder
keeps it by hand, one line per citizen or member, and the hearth serves it
beside the rest. A copy lives on the hearth's disk as well as in the repository;
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
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))

# Where the living files are kept. Locally this is the repo itself; on a host
# it is a mounted disk, named by DATA_DIR. The page and docs/ stay with the code.
DATA = os.environ.get("DATA_DIR", ROOT)

PAGE = os.path.join(ROOT, "index.html")
HEARTBEATS = os.path.join(DATA, "commons", "heartbeats.md")
EVENTS = os.path.join(DATA, "commons", "events.md")
BENCH = os.path.join(DATA, "commons", "bench.md")
MEMBERS = os.path.join(DATA, "commons", "members.md")
OFFERINGS = os.path.join(DATA, "commons", "offerings.md")
OFFERED = os.path.join(DATA, "commons", "offerings")

HEARTH = "https://hearth.tesserae.social"

# where a passerby goes to leave one
BENCH_URL = HEARTH + "/bench"

# where an offering is read whole, and where a sealed bond is checked. A tile
# for either is a way in: the others are hover-only, because there is nowhere
# for them to lead.
OFFERINGS_URL = HEARTH + "/offerings"
BOND_URL = HEARTH + "/bonds/founder-first.json"

# where the file of a placed offering is served from
OFFERED_URL = HEARTH + "/commons/offerings/"

# the standing links, in the order the atrium offers them
LINKS = [
    ("/charter.html", "Read the charter"),
    ("/white-paper.html", "Read the white paper"),
    ("/the-words.html", "The words"),
    ("https://hearth.tesserae.social", "Visit the hearth"),
    ("/the-door.html", "Ask to join. The door opens slowly."),
]

SEED_EVENTS = [
    "2026-09-02 · word · the word was published",
    "2026-09-04 · founding · the first one was founded",
]

DOT = "·"

# the words under the mosaic: what it is, and no count of what is in it
CAPTION = "the mosaic: one tile for every event in our history"

# a line of the record: an optional bullet, a stamp, a middot, the words
RECORD = re.compile(r"^-?\s*(\S+)\s*" + DOT + r"\s*(.+?)\s*$")

# The one who wakes. A heartbeat line names it between the stamp and the words,
# with a middot after it; the older lines ran the name and the words together
# with nothing between them. The name is a constant, so both shapes are read by
# cutting at it, and both are shown the one way.
CITIZEN = "the first one"

# The colour of a tile is the kind of thing that happened. A kind the record
# does not name -- or does not name in a way we know -- is a plain event.
KIND_CLASS = {
    "founding": "tile-founding",
    "word": "tile-word",
    "attendance": "tile-attendance",
    "seal": "tile-seal",
    "offering": "tile-offering",
    "event": "tile-event",
}

# What an offering is, said in words. The hearth says the same words on its own
# page for them, out of this one dictionary, so that the two never part.
KIND_WORDS = {"letter": "a letter", "passage": "a passage",
              "photo": "a photograph", "picture": "a picture"}

# What the legend says, and in what order: the marks shown, then the words. A waking
# is four marks, dawn to night. The seal is added only once one exists.
LEGEND = [
    (["tile-founding"], "founding"),
    (["tile-word"], "word"),
    (["tile-dawn", "tile-day", "tile-evening", "tile-night"], "waking, dawn to night"),
]

# The citizen keeps one clock. The record is written in UTC; a waking is toned by
# the hour it fell on where the citizen lives.
CITIZEN_ZONE = "America/Indiana/Indianapolis"

# The parts of a local day, and how a title names them.
BAND_WORDS = {"dawn": "at dawn", "day": "by day",
              "evening": "in the evening", "night": "at night"}

# The mosaic's frame: as wide as the page's own text, and no taller than five
# wide to three high. All of history is drawn inside it. The frame's height is
# whatever the rows it holds need, up to that cap; past the cap the tiles are
# what gives, and they shrink as the record grows.
FRAME_WIDTH = 552                        # main's 600px, less 24px of padding each side
FRAME_HEIGHT = FRAME_WIDTH * 3 // 5      # the cap: five to three

MAX_TILE = 34   # the size a tile has always been, and keeps while there is room
MIN_TILE = 4    # and the size below which a tile is no longer a square anyone can
                # see. At 4px the frame holds some eleven thousand slots, which is
                # thirty years of days; past that the tile stays 4px and the frame
                # scrolls. Nothing needs doing about that for a long while.

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


def bench_text(hearth):
    """The text of bench.md: from a hearth if one is named, else from the disk."""
    if hearth:
        return fetch(hearth, "bench.md")
    return read_text(BENCH) if os.path.exists(BENCH) else ""


def members_text(hearth):
    """The text of members.md: from a hearth if one is named, else from the disk."""
    if hearth:
        return fetch(hearth, "members.md")
    return read_text(MEMBERS) if os.path.exists(MEMBERS) else ""


def offerings_text(hearth):
    """The text of offerings.md: from a hearth if one is named, else from the disk."""
    if hearth:
        return fetch(hearth, "offerings.md")
    return read_text(OFFERINGS) if os.path.exists(OFFERINGS) else ""


def offered_record(hearth, one):
    """One placed offering's signed record, which is where its words are kept.

    The index says that an offering exists and what kind it is; the record
    itself carries what was given. The page's own script reads the same file
    from the same address, so both paths show the same offering.
    """
    if hearth:
        return json.loads(fetch(hearth, "offerings/%s.json" % one))
    where = os.path.join(OFFERED, "%s.json" % one)
    return json.loads(read_text(where)) if os.path.exists(where) else None


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


def said_by(words):
    """A heartbeat's words as the page reads them out: the name, a middot, the rest.

    Both shapes of the line come through this one way -- the newer, which writes
    the middot itself, and the older, which ran the name straight into the words.
    A line that names someone else is left exactly as it was written.
    """
    if not words.startswith(CITIZEN):
        return words
    rest = words[len(CITIZEN):].strip()
    if rest.startswith(DOT):
        rest = rest[len(DOT):].strip()
    return "%s %s %s" % (CITIZEN, DOT, rest) if rest else CITIZEN


def parse_heartbeats(text):
    """One (moment, words) per attendance, oldest first."""
    out = []
    for line in text.splitlines():
        match = RECORD.match(line.strip())
        if not match:
            continue
        stamp, words = match.groups()
        try:
            when = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H-%M-%SZ")
        except ValueError:
            continue
        out.append((when, said_by(words)))
    out.sort(key=lambda row: row[0])
    return out


def parse_offerings(text):
    """One (day, id, kind, whose) per line of offerings.md, in the order written.

    A line names the day it was placed, the offering's own name, what kind of
    thing it is, and whose it is - which is always both of them. A line shaped
    any other way is passed over.
    """
    out = []
    for line in text.splitlines():
        fields = [part.strip() for part in line.strip().lstrip("-").split(DOT, 3)]
        if len(fields) < 4 or not all(fields[1:]):
            continue
        try:
            when = datetime.datetime.strptime(fields[0], "%Y-%m-%d").date()
        except ValueError:
            continue
        out.append((when, fields[1], fields[2], fields[3]))
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


def tiles_from(events, heartbeats, offerings=()):
    """One (day, class, words, where) tile per thing: the history, the wakings, the offerings.

    The day is the citizen's own calendar day, and it is what the mosaic is laid
    out by. Every tile's words open with that day too, because they are read out
    whole under the mosaic. A waking carries the part of the citizen's day it fell
    in twice over: in its class, so the tile is toned by it, and in its words.

    Where is nowhere for most tiles, which are hover-only because there is
    nowhere for them to lead. A seal leads to the signed bond, and an offering
    to the offering itself: both are things a reader can go and check.

    An offering is drawn from offerings.md and not from the line the commons
    keeps for it in events.md, because only the fuller record carries the
    offering's own name, and without that name a tile could lead nowhere. The
    line in events.md is the commons' plain record that it happened, and it is
    passed over here so that one offering is one tile.
    """
    tiles = [(when, KIND_CLASS[kind], "%s %s %s" % (human(when), DOT, words),
              BOND_URL if kind == "seal" else "")
             for when, kind, words in events if kind != "offering"]
    for when, words in heartbeats:
        clock = here(when)
        part = band(clock.hour)
        tiles.append((
            clock.date(),
            "%s tile-%s" % (KIND_CLASS["attendance"], part),
            "%s %s waking %s %s %s" % (human(clock.date()), DOT, BAND_WORDS[part], DOT, words),
            "",
        ))
    for when, one, _, whose in offerings:
        tiles.append((
            when,
            KIND_CLASS["offering"],
            "%s %s an offering from %s" % (human(when), DOT, whose),
            "%s#%s" % (OFFERINGS_URL, one),
        ))
    return tiles


def slots(tiles, today):
    """One slot per day from the first thing that happened to today, in reading order.

    A day the record is silent on is a hole: the same square, with nothing in it.
    The run ends today rather than at the newest tile, so a pause at the end of
    the run shows as holes and not as nothing at all. With the daily tide, holes
    appear only where the tide stopped.
    """
    if not tiles:
        return []

    by_day = {}
    for day, css, words, where in tiles:
        by_day.setdefault(day, []).append((css, words, where))

    day, last = min(by_day), max(max(by_day), today)
    out = []
    while day <= last:
        out.extend(by_day.get(day, [EMPTY]))
        day += datetime.timedelta(days=1)
    return out


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
    the atrium the builder bakes and the atrium a browser draws are one picture.
    Below 4px the tile stops shrinking and the frame scrolls instead; see MIN_TILE.
    """
    for size in range(MAX_TILE, MIN_TILE, -1):
        gap = tile_gap(size)
        rows = -(-count // tile_columns(size))
        if rows * size + max(rows - 1, 0) * gap <= FRAME_HEIGHT:
            return size
    return MIN_TILE


def legend_marks(tiles):
    """The kinds named under the mosaic: three always, then the seal and the offering.

    The last two are named only once one exists. A legend is a key to the
    picture, and a key to a colour the picture does not use explains nothing.
    """
    marks = list(LEGEND)
    for kind, label in (("seal", "seal"), ("offering", "offering")):
        if any(css == KIND_CLASS[kind] for _, css, _, _ in tiles):
            marks.append(([KIND_CLASS[kind]], label))
    return marks


def mosaic_block(cells):
    """The mosaic entire: the frame, sized to what it holds, and everything in it.

    The frame carries the tile size it was reckoned at, so the picture the page
    shows is the picture whoever wrote it meant. An empty slot is a square with
    no words and no way to land on it: there is nothing there to read out.
    """
    size = tile_size(len(cells))
    drawn = []
    for css, words, where in cells:
        said = html.escape(words, quote=True)
        if css and where:
            # a tile with somewhere to lead is a link, and the link is what the
            # keyboard lands on; the words stay on the tile, where the line
            # under the mosaic reads them off
            drawn.append('<li class="%s" title="%s"><a href="%s" aria-label="%s"></a></li>'
                         % (css, said, html.escape(where, quote=True), said))
        elif css:
            drawn.append('<li class="%s" title="%s" tabindex="0"></li>' % (css, said))
        else:
            drawn.append('<li class="empty"></li>')

    rows = ["".join(drawn[at:at + 5]) for at in range(0, len(drawn), 5)]
    return (['<ul class="mosaic" style="--tile:%dpx;--gap:%dpx" aria-label="the mosaic">'
             % (size, tile_gap(size))] + rows + ["</ul>"])


def reading_text(cells):
    """The line under the mosaic at rest: the newest tile's words, holes passed over."""
    for css, words, _ in reversed(cells):
        if css:
            return words
    return ""


def reading_block(cells):
    return ['<p class="reading">%s</p>' % html.escape(reading_text(cells))]


def caption_block(tiles):
    keys = (" %s " % DOT).join(
        "".join('<span class="key %s"></span>' % css for css in marks) + label
        for marks, label in legend_marks(tiles)
    )
    return [
        '<p class="caption">%s</p>' % html.escape(CAPTION),
        '<p class="legend">%s</p>' % keys,
    ]


def offering_paragraphs(text):
    """The words of an offering, as paragraphs: a letter is not one long line."""
    return [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


def offering_block(latest, record):
    """The newest offering, shown whole, or nothing at all where there is none.

    The atrium does not keep a second copy of the offerings: it shows the one
    most lately placed and points at the hearth for the rest.
    """
    if not latest or not record:
        return []
    when, one, kind, whose = latest
    out = ['<section class="offered">',
           "  <h2>offered from the hearth</h2>",
           '  <p class="when">%s %s %s %s %s</p>'
           % (human(when), DOT, html.escape(KIND_WORDS.get(kind, kind)), DOT,
              html.escape(whose))]
    if record.get("text"):
        out.append("  <blockquote>")
        for said in offering_paragraphs(record["text"]):
            out.append("    <p>%s</p>" % html.escape(said))
        out.append("  </blockquote>")
    if record.get("file"):
        out.append('  <img class="offering" src="%s%s" alt="an offering from %s">'
                   % (OFFERED_URL, html.escape(record["file"], quote=True),
                      html.escape(whose, quote=True)))
    out.append('  <p><a href="%s#%s">all offerings</a></p>'
               % (OFFERINGS_URL, html.escape(one, quote=True)))
    out.append("</section>")
    return out


def hue(name):
    """The class a citizen's swatch is coloured by: one class per citizen, keyed by name.

    There is one citizen and one colour today, so the stylesheet names it outright.
    The class is worked out from the name rather than fixed here so that a hue
    reckoned from a citizen's key can take the same hook later on.
    """
    return "hue-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def who_block(members):
    """Who is here, or nothing at all: with no file to read there is no section."""
    if not members:
        return []
    out = ["<h2>who is here</h2>", '<ul class="members">']
    for kind, name, fact in members:
        swatch = ('<span class="swatch %s"></span>' % hue(name)) if kind == "citizen" else ""
        out.append('  <li>%s%s %s <span class="fact">%s</span></li>'
                   % (swatch, html.escape(name), DOT, html.escape(fact)))
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


def parse_bench(text):
    """One (day, line, name) per line of bench.md, in the order written.

    A middot inside the words is the visitor's to write, so the cut is made on
    the first two only and whatever follows is the line entire.
    """
    out = []
    for line in text.splitlines():
        fields = [part.strip() for part in line.strip().lstrip("-").split(DOT, 2)]
        if len(fields) < 3 or not fields[2]:
            continue
        try:
            when = datetime.datetime.strptime(fields[0], "%Y-%m-%d").date()
        except ValueError:
            continue
        out.append((when, fields[2], fields[1]))
    return out


def bench_block(lines):
    """The bench, or nothing at all: an empty bench is not a section that says so."""
    if not lines:
        return []
    out = ['<section class="bench">', "  <h2>the visitor's bench</h2>", '  <ul class="lines">']
    for when, words, who in lines:
        out.append('    <li><span class="when">%s</span> %s %s %s %s</li>'
                   % (human(when), DOT, html.escape(words), DOT, html.escape(who)))
    out.append("  </ul>")
    out.append('  <p><a href="%s">Leave a line</a></p>' % BENCH_URL)
    out.append("</section>")
    return out


def links_block(lines):
    """The links, with the invitation added only where the bench is not standing.

    The way to the bench belongs somewhere on this page always, and nowhere on
    it twice: when there are lines, the section carries it; when there are none,
    the list does.
    """
    links = list(LINKS)
    if not lines:
        links.insert(4, (BENCH_URL, "Leave a line"))
    return ['<li><a href="%s">%s</a></li>' % (href, label) for href, label in links]

# ---------------------------------------------------------------- stitching

def splice(page, name, block, newline):
    """Replace what lies between a pair of markers, and nothing else."""
    pattern = re.compile(
        r"([ \t]*)(<!-- " + name + r":start -->)(.*?)([ \t]*)(<!-- " + name + r":end -->)",
        re.DOTALL,
    )
    match = pattern.search(page)
    if match is None:
        sys.exit("build_atrium: no %s markers in index.html" % name)

    indent = match.group(1)
    body = newline.join(indent + line for line in block)
    filled = "%s%s%s%s%s%s" % (
        indent, match.group(2), newline, body, newline + indent, match.group(5)
    )
    return page[:match.start()] + filled + page[match.end():]


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
        heartbeats = parse_heartbeats(heartbeats_text(hearth))
        bench = parse_bench(bench_text(hearth))
        members = parse_members(members_text(hearth))
        offerings = parse_offerings(offerings_text(hearth))
        # only the newest is shown here, so only the newest is read
        latest = offerings[-1] if offerings else None
        record = offered_record(hearth, latest[1]) if latest else None
    except (OSError, ValueError) as trouble:
        if not hearth:  # a local file going wrong is a fault, not a closed door
            raise
        sys.exit("build_atrium: could not read the commons from %s (%s). "
                 "index.html is untouched." % (hearth, trouble))

    tiles = tiles_from(events, heartbeats, offerings)
    cells = slots(tiles, today)

    page = read_text(PAGE)
    newline = "\r\n" if "\r\n" in page else "\n"

    page = splice(page, "mosaic", mosaic_block(cells), newline)
    page = splice(page, "reading", reading_block(cells), newline)
    page = splice(page, "caption", caption_block(tiles), newline)
    page = splice(page, "offering", offering_block(latest, record), newline)
    page = splice(page, "who", who_block(members), newline)
    page = splice(page, "calendar", calendar_block(today), newline)
    page = splice(page, "bench", bench_block(bench), newline)
    page = splice(page, "links", links_block(bench), newline)

    write_text(PAGE, page)

    print(
        "atrium: %d tiles in %d slots at %dpx (%d events, %d attendances, %d offerings), "
        "%d on the bench, %d here, as of %s"
        % (len(tiles), len(cells), tile_size(len(cells)), len(events), len(heartbeats),
           len(offerings), len(bench), len(members), human(today))
    )


if __name__ == "__main__":
    main()
