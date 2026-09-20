#!/usr/bin/env python3
"""Regenerate the atrium from the record.

Rewrites only the text between the marker comments in index.html:

    <!-- commons:start -->  ...  <!-- commons:end -->
    <!-- mosaic:start -->   ...  <!-- mosaic:end -->
    <!-- caption:start -->  ...  <!-- caption:end -->

Everything outside those markers is left byte for byte as it was.

It reads:
    docs/state-of-the-commons.md   the standing paragraph
    commons/heartbeats.md          the attendances
    commons/events.md              the history (created if missing)

With --from URL it takes the last two from a running hearth instead
(URL/commons/heartbeats.md and URL/commons/events.md), and writes nothing
at all if that hearth cannot be reached.

Nothing under packets/, keys/, transcripts/ is read or written, and docs/
is only ever read.
"""

import argparse
import datetime
import html
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))

# Where the living files are kept. Locally this is the repo itself; on a host
# it is a mounted disk, named by DATA_DIR. The page and docs/ stay with the code.
DATA = os.environ.get("DATA_DIR", ROOT)

PAGE = os.path.join(ROOT, "index.html")
STATE = os.path.join(ROOT, "docs", "state-of-the-commons.md")
HEARTBEATS = os.path.join(DATA, "commons", "heartbeats.md")
EVENTS = os.path.join(DATA, "commons", "events.md")

SEED_EVENTS = [
    "2026-09-02 · the word was published",
    "2026-09-04 · the first one was founded",
]

DOT = "·"
DASH = "—"

# a line of the record: an optional bullet, a stamp, a middot, the words
RECORD = re.compile(r"^-?\s*(\S+)\s*" + DOT + r"\s*(.+?)\s*$")

SERIF = "Georgia,'Times New Roman','Iowan Old Style',serif"  # single quotes: it sits in an attribute


# ---------------------------------------------------------------- reading

def read_text(path):
    """Read a file as UTF-8, dropping a byte order mark if one is there."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8-sig")


def write_text(path, text):
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def read_state():
    """The body of the state of the commons, with its heading struck off."""
    lines = read_text(STATE).splitlines()
    body = [ln.strip() for ln in lines if not ln.startswith("#")]
    return " ".join(ln for ln in body if ln)


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


def parse_events(text):
    """One (date, words) per line of events.md, in the order written."""
    out = []
    for line in text.splitlines():
        match = RECORD.match(line.strip())
        if not match:
            continue
        stamp, words = match.groups()
        try:
            when = datetime.datetime.strptime(stamp, "%Y-%m-%d").date()
        except ValueError:
            continue
        out.append((when, words))
    return out


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
        out.append((when, words))
    out.sort(key=lambda row: row[0])
    return out


# ---------------------------------------------------------------- writing

def human(when):
    """19 September 2026 -- written out the way a person says it."""
    return "%d %s %d" % (when.day, when.strftime("%B"), when.year)


def commons_block(state, heartbeats, today):
    out = ["<p>%s</p>" % html.escape(state)]

    recent = list(reversed(heartbeats))[:3]
    if recent:
        out.append(
            '<ul style="margin:20px 0 0;padding:0;list-style:none;'
            'font-family:%s;font-size:0.95rem;line-height:1.7;">' % SERIF
        )
        for when, words in recent:
            out.append(
                '  <li style="margin:0 0 6px;">'
                '<span style="color:var(--ink-soft);">%s</span> %s %s</li>'
                % (human(when.date()), DOT, html.escape(words))
            )
        out.append("</ul>")

    out.append(
        '<p style="margin:16px 0 0;font-size:0.85rem;color:var(--ink-soft);">'
        "as of %s</p>" % human(today)
    )
    return out


def mosaic_block(tiles):
    cells = []
    for index, words in enumerate(tiles):
        shade = "filled" if index % 2 == 0 else "filled-pale"
        cells.append(
            '<li class="%s" title="%s"></li>' % (shade, html.escape(words, quote=True))
        )

    full = max(10, -(-len(cells) // 10) * 10)
    cells.extend(["<li></li>"] * (full - len(cells)))

    return ["".join(cells[at:at + 5]) for at in range(0, len(cells), 5)]


def caption_block(count):
    return [
        '<p class="caption">the mosaic %s one tile per event in our history '
        "%s %d so far</p>" % (DASH, DOT, count)
    ]


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
    today = datetime.date.today()

    state = read_state()
    try:
        events = parse_events(events_text(hearth))
        heartbeats = parse_heartbeats(heartbeats_text(hearth))
    except (OSError, ValueError) as trouble:
        if not hearth:  # a local file going wrong is a fault, not a closed door
            raise
        sys.exit("build_atrium: could not read the commons from %s (%s). "
                 "index.html is untouched." % (hearth, trouble))

    tiles = [words for _, words in events] + [words for _, words in heartbeats]

    page = read_text(PAGE)
    newline = "\r\n" if "\r\n" in page else "\n"

    page = splice(page, "commons", commons_block(state, heartbeats, today), newline)
    page = splice(page, "mosaic", mosaic_block(tiles), newline)
    page = splice(page, "caption", caption_block(len(tiles)), newline)

    write_text(PAGE, page)

    print(
        "atrium: %d tiles (%d events, %d attendances), %d heartbeats shown, as of %s"
        % (len(tiles), len(events), len(heartbeats), min(3, len(heartbeats)), human(today))
    )


if __name__ == "__main__":
    main()
