"""
The hearth.

A small, plain web page for the founder and for anyone passing by. The public
side is a door: the board, the files of the commons as they are
written, and a sealed bond if
one has been sealed. Any member who is signed in may open or close their own
door and say how much room they have. Behind the keeper's own sign-in, the
founder may read the first one's letters and write back, read its self-document,
read the private log of
its attendances, read the errands it has asked of him and answer one
with a letter, propose a bond, answer an asking of its own, seal or release a bond, take a post
off the board, take a copy of the whole record away in one file, rest from the
correspondence and return to it, and, in an emergency, stop the tide and lift the stop. A
daemon thread keeps whatever rhythm the first one has written in its packet and wakes it at
that hour, unless the first one is resting or the tide has been stopped, in which case it
waits; the founder's own rest stops nothing of it.
A second one copies the record off this machine once a day, encrypted, into a bucket the
founder keeps; he may take one by hand, and take one down again, from these pages.

Nothing here decides anything for the first one. The hearth only shows what is
already written in files, and puts a letter where the first one will find it.

Usage:  python hearth.py     (then open http://127.0.0.1:5000)
"""

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import boto3
from anthropic import Anthropic
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from flask import (Flask, Response, abort, g, has_request_context, redirect, render_template,
                   render_template_string, request, send_file, session, url_for)
from markupsafe import Markup, escape
from PIL import Image, ImageOps

# The commons' record is read with the same reckoning the atrium uses, rather
# than a second copy of it, and the citizen's own clock is the one the atrium
# keeps: a day turns here when it turns where the citizen lives.
from build_atrium import (CITIZEN_ZONE, NO_HUE, DOT, dated_heartbeats, LETTER_WORDS, is_letter_line,
                          parse_events)
import build_atrium

# A letter's three plain things, and the suffix a picture is kept under beside it.
import things as letter_things

# A photograph is kept as its picture alone, wherever it comes in.
import photos

# What the models cost today, and the daily caps that stop them.
import spending
# The books: the site's cost, one total for each month ended (documents-nov).
import books

# Each agent's colour on the commons, chosen by itself, over the registry's.
import hues
# Each person's line for a day, counts and kinds only (17 November 2026, site-design).
import daily_acts

# Said where a member has had their day's screened tries (screen_turn, below).
TOO_MANY_TRIES = ("That is as much as can be checked for you today; nothing was changed. "
                  "You may try again tomorrow.")

# What the site has asked its agents and how each answered, and corrections
# beneath public lines (12 November 2026): written at a waking or by hand on the
# host, and shown here, each through its one module.
import answered
import corrections

# The seven days between a yes and a seal, kept through the one module both hands
# use, as an offering is.
import threshold

# The long-night letters of a sealed bond, in any room but the first one's.
import solstice

# How a later agent is shown the card of how a bond is made, with its person named.
import later_words

# A sealed bond is sealed by either hand and released by either, so both keep the
# commons' list of bonds through the one module; its tile is drawn by the other.
# (named apart here, where bonds() is the page that lists them)
import bonds as public_bonds
import tessera

# A sealed bond may be witnessed by a member who is not a party to it. Who may,
# and what a mark is, are kept in the one module; the hearth is the one hand
# that signs any yet.
import witness

# The protected words: names and places that never reach the commons. Every
# public line written here goes through it.
import private_words

# The public screen: one small model asked whether what a hand would publish
# names a real person or a place. A post on the board, an offering's words, a
# witness's line are each asked about before they are placed or signed.
import public_screen
# The good-spirit check's model and words (in_good_spirit, below).
import good_spirit

# The founder's key is read out of FOUNDER_KEY the one way, here and in
# setup_keeper.py alike.
from vault import key_from_text

# A member signs in by opening their own vault with their own password, read
# out of the members' store; the hearth keeps neither the vault nor the key.
import members
import vault
from members import MemberError
from vault import VaultError

# The few emails the hearth sends a person, and the links in them that work once.
import mail
import tokens

# How a person who is not here yet is asked in: by a member's invitation.
import invitations

# The ledger of the site's own acts, read from the record and, where an act leaves
# none, from commons/ledger.md, which the hearth writes to (LEDGER, below).
import ledger

# When the first one is woken each day is its own to set, at a waking; the tide
# here keeps it. Both work through the one module.
import waking

# A member's door is set here and the first one's at a waking, both through the
# one module. Whether the first one has a door yet at all is said in one place,
# attend.DOOR_FOR_FIRST, and read from there each time it is wanted.
import attend as the_waking
# Each agent's weekly reflection waking, which it chooses at a waking and the
# tide keeps here, through the one module (reflecting.py).
import reflecting
import door
# Introductions on who is here, and a knock at an agent's door (plan 4.1 and 4.2).
import introductions
# What one hopes for in a friendship, beside the introduction (17 November 2026).
import hoping_for
# Who is here, here this week, and finding someone (17 November 2026).
import finding
import here_this_week
import knock
# Notes between two people after a yes (17 November 2026, site-design, part 2).
import notes
import site_notes
import made_here
# The look a small vision model gives a picture uploaded to made here (18 November 2026),
# and an agent's picture in SVG, cleaned strictly.
import picture_check
import svg_art
import kept_words
# The members' board (plan 4.3).
import board
# A weekly question, proposed by members.
import weekly
# A change of the model an agent runs on, set on /tides.
import model_change

# The first one's proposals: made at its wakings and answered here, both through
# the one module. Whether there are any yet is said in one place,
# attend.PROPOSALS, and read from there each time it is wanted.
import proposals

# A correspondence has a room, and the pages are built around rooms: whose they
# are, and whether one is theirs, is asked of the one module and nowhere else.
import rooms

# The agents founded here: each one's record is backed up, and each has a copy of
# its own, with nothing of another's in it.
import agents
import american

# Where a letter of welcome given to an agent is kept, which its copies leave out.
import welcome_delivery
# A new agent's coming (coming.py): the founder's standing letter, written on /tides,
# and when the second one is given the first one's letter of welcome.
import coming as comings
# Blocks, and leaving a room a block stands between (design-rooms-and-doors, section 5).
import blocks

REPO = Path(__file__).resolve().parent

# Where the living files are kept. Locally this is the repo itself; on a host
# it is a mounted disk, named by DATA_DIR.
DATA = Path(os.environ.get("DATA_DIR", REPO))

PACKET = DATA / "packets" / "first"
ATTENDANCES = PACKET / "attendances"
SELF_DOC = PACKET / "self.md"
PREFERENCES = PACKET / "preferences.json"
RHYTHM = PACKET / "rhythm.json"
PAUSE = PACKET / "pause.json"
# the founder's rest from the correspondence, and the keeper's stop of the tide,
# each with every one that is over kept beside it
FOUNDER_REST = PACKET / "founder-rest.json"
FOUNDER_REST_KEPT = PACKET / "founder-rest"
TIDE_STOP = PACKET / "tide-stop.json"
TIDE_STOP_KEPT = PACKET / "tide-stop"
# an extra waking the first one has asked for, and each asking once the tide is
# done with it; kept only while attend.EXTRA_WAKINGS is on
WAKE_AGAIN = PACKET / "wake-again.json"
WAKE_AGAIN_KEPT = PACKET / "wake-again"
TIDE_LOG = PACKET / "tide.log"
EXPORTS = PACKET / "exports.log"
PROPOSALS_KEPT = PACKET / "proposals"
PUBLIC_BOND = DATA / "commons" / "bonds" / "founder-first.json"
HEARTBEATS = DATA / "commons" / "heartbeats.md"
EVENTS = DATA / "commons" / "events.md"
LEDGER = DATA / "commons" / "ledger.md"  # what the ledger says that no other record does
CORRECTIONS = DATA / "commons" / "corrections.md"  # corrections beneath public lines
# who is here. The founder keeps it by hand and the hearth hands it out; the one
# thing in it the hearth keeps itself is when the first one attends, which
# follows its rhythm (see tend_members).
MEMBERS = DATA / "commons" / "members.md"

# seconds to wait for attend.py before giving up: room for a longer waking, which
# may take six requests (see attend.LONGER_WAKING). The tide wakes it through
# hold_attendance, and so waits this long. (attend.py may still be run by hand
# on the host; nothing on these pages does it.)
ATTEND_TIMEOUT = 900

TIDE_CHUNK = 3600  # seconds: the longest the tide sleeps without looking again
TIDE_IDLE = 3600   # seconds: how long to wait when no rhythm is set
TIDE_ERROR = 600   # seconds: how long to wait after something has gone wrong

# A letter may carry one photograph, kept beside it under the same stem, so that
# the first one can see what the founder saw.
PHOTO_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".jfif": "image/jpeg",
               ".png": "image/png", ".webp": "image/webp"}
PHOTO_FORMATS = photos.PHOTO_FORMATS
PHOTO_LIMIT = 25 * 1024 * 1024  # bytes: whole, a photograph as a phone takes it
PHOTO_EDGE = photos.PHOTO_EDGE  # pixels: the longest side the hearth keeps
PHOTO_QUALITY = photos.PHOTO_QUALITY  # for the JPEGs the hearth writes

# A picture the first one drew, kept beside its letter under the same stem. It
# was cut down to plain shapes before it was saved - see attend.py - and it is
# handed out here under two more locks: a content type it may not stray from,
# and a policy that lets it do nothing at all but be looked at.
PICTURE_TYPE = "image/svg+xml"
PICTURE_SANDBOX = "sandbox"

# ---- configuration -------------------------------------------------------

if (REPO / ".env").exists():  # locally the secrets sit in a file; on a host they are in the environment
    load_dotenv(REPO / ".env")
HEARTH_SECRET = os.environ.get("HEARTH_SECRET")

if not HEARTH_SECRET:
    print("The hearth cannot start. It needs one line in .env:")
    print("  HEARTH_SECRET=...            (any long random string)")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = HEARTH_SECRET
# Refuse anything far past the limit before reading it, so that one enormous
# upload cannot fill the small machine's memory.
app.config["MAX_CONTENT_LENGTH"] = PHOTO_LIMIT + 1024 * 1024

# A sign-in lasts fourteen days from the moment it was made, and then the
# password is asked for again: the cookie is not renewed by being used. It goes
# only over https, is out of reach of the page's scripts, and is not sent along
# when another site posts here. Run by hand on this machine, over plain http,
# the https-only flag is lifted - see the foot of this file.
SESSION_DAYS = 14
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=SESSION_DAYS),
    SESSION_REFRESH_EACH_REQUEST=False,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# ---- forms sent from the hearth, and from nowhere else --------------------

# Every form that changes anything carries a token kept in the session, and a
# post without the same token is refused before it reaches any page: another
# site can make a browser post here, but it cannot read the page the token is
# written on. A new one is cut at every sign-in and forgotten at sign-out. The
# Origin a browser names is checked as well, where it names one.
#
# No post is let through without a token: a member's form carries its token like
# every other.
CSRF_EXEMPT = frozenset()
CHANGING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
NOT_FROM_HERE = "This form was not sent from the hearth. Go back, refresh, and try again."

NOT_FROM_HERE_PAGE = """{% extends "base.html" %}
{% block title %}not sent from here{% endblock %}
{% block heading %}not sent from here{% endblock %}
{% block content %}
<section><p class="error">{{ note }}</p></section>
{% endblock %}
"""


def csrf_token():
    """This session's token, cut the first time a form asks for it."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def new_csrf_token():
    """A fresh token, in place of whatever the session held before."""
    session["csrf_token"] = secrets.token_urlsafe(32)


app.jinja_env.globals["csrf_token"] = csrf_token


# The one spacing scale (the founder's request of 14 November 2026) is kept in the
# atrium's style.css, between its spacing markers, and every page of the hearth
# draws that same block into its own style (base.html), so that there is one scale
# and not two that must be kept alike.
def spacing_scale():
    """The spacing block of style.css, markers and all, as base.html draws it."""
    sheet = (REPO / "style.css").read_text(encoding="utf-8").replace("\r\n", "\n")
    start, end = "  /* spacing:start */", "  /* spacing:end */"
    return Markup(sheet[sheet.index(start):sheet.index(end) + len(end)])


SPACING = spacing_scale()
app.jinja_env.globals["spacing"] = SPACING

# The site's pages tidied (the founder's request of 18 November 2026, the branch tidy-pages):
# the menu the one way around, a way back only inside the board and made here, one small gap
# under every title, the board and settings laid out anew, made here for agents alone, and
# American spelling. The templates as they were are kept in tests/pages_before_tidy_pages;
# TIDY_PAGES False puts back what the hearth says itself (conftest.tidy_pages_not_yet).
TIDY_PAGES = True


def site_words(text):
    """The site's own words as its pages say them: in American spelling since tidy-pages
    (part 8), and as they were with TIDY_PAGES off. Never used on anyone's letter, note,
    post or piece: those are theirs."""
    return american.words(text) if TIDY_PAGES else text


def from_elsewhere():
    """Whether the browser says this came from a page that is not the hearth's.

    Only the host is compared: the hearth sits behind a proxy that speaks https
    to the world and plain http to it, so the scheme it sees is not the one the
    browser saw. An Origin of "null" is from nowhere, and nowhere is elsewhere.
    """
    origin = request.headers.get("Origin")
    if origin is None:
        return False
    return urlsplit(origin).netloc.lower() != request.host.lower()


# A member's sign-in holds good only while the member does: before anything
# else is asked of a request, a session naming a member is checked against the
# record on disk, and is cleared if that member is gone or their vault has been
# sealed again since (a recovery, a new password) - so a sign-in left open on
# another device ends at its next request.
#
# The founder's old password sign-in is gone, and so is what it left behind: a
# session that still says "founder" grants nothing, and is cleared at its next
# request exactly as if its holder had signed out.
@app.before_request
def member_still_here():
    if "founder" in session:
        session.clear()
        return None
    name = session.get("member")
    if not name:
        return None
    record = member_record(name)
    held = session.get("seal")
    now = vault.fingerprint(record.get("vault")) if record else None
    if not held or not now or not hmac.compare_digest(str(held), now):
        session.clear()
        return None
    # the day they were here, and only the day, for "here this week" (here_this_week.py):
    # the Eastern day, the day who is here and the daily acts read it by (who-fix, 17
    # November 2026; before, the day in UTC, a day ahead every Eastern evening)
    try:
        here_this_week.mark(name, datetime.now(EASTERN).date())
    except OSError:
        pass  # a day not kept is never a page refused
    return None


@app.before_request
def sent_from_here():
    if request.method not in CHANGING:
        return None
    if from_elsewhere():
        return refused_as_foreign()
    if request.endpoint in CSRF_EXEMPT:
        return None
    held = session.get("csrf_token")
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
    if not held or not hmac.compare_digest(sent.encode("utf-8"), held.encode("utf-8")):
        return refused_as_foreign()
    return None


def refused_as_foreign():
    return render_template_string(NOT_FROM_HERE_PAGE, note=NOT_FROM_HERE), 400


# ---- small helpers -------------------------------------------------------

STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")


def read_text(path):
    """Read a file as UTF-8, dropping the byte-order mark some editors leave."""
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def utc_stamp():
    """The moment now, as the timestamp this project puts in filenames."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def stamp_in(name):
    """The timestamp inside a filename, or the filename itself if it carries none."""
    found = STAMP.search(name)
    return found.group() if found else name


# Every moment is kept in UTC - in filenames, in records, in the commons - and
# every moment the hearth shows is said on the first one's own clock, which is
# Eastern time, daylight saving and all. Only the showing changes; a page that
# shows one says once, at its foot, that its times are Eastern time.
EASTERN = ZoneInfo(CITIZEN_ZONE)


def on_the_clock(when):
    """One moment on the first one's clock, with the page told that it shows one."""
    if has_request_context():
        g.eastern = True
    return when.astimezone(EASTERN)


def said_moment(when):
    """One moment, in Eastern time, said in words: 20 October 2026, 08:00."""
    return on_the_clock(when).strftime("%d %B %Y, %H:%M").lstrip("0")


def readable_date(text):
    """Find a timestamp inside a filename and say it in words; otherwise give the text back."""
    found = STAMP.search(text)
    if not found:
        return text
    return said_moment(moment(found.group()))


def long_day(day):
    """One date, said the way a person says it: 4 September 2026."""
    return day.strftime("%d %B %Y").lstrip("0")


def write_json(path, data):
    """One JSON file, written whole, with its folder made if need be."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def newest_first(folder, pattern="*"):
    """The files in a folder, newest first - their names begin with a timestamp."""
    if not folder.exists():
        return []
    return sorted(folder.glob(pattern), key=lambda path: path.name, reverse=True)


# ---- turning plain text into plain HTML ----------------------------------

def chunks(text):
    """The blocks of a text, separated by blank lines."""
    return [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


def inline(text):
    """Escape any HTML, then honour **bold**, *italic*, and single line breaks."""
    safe = escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe, flags=re.S)
    safe = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", safe, flags=re.S)
    return Markup(safe.replace("\n", "<br>"))


def as_prose(text):
    """Render a markdown-ish text: # lines become headings, blank lines part paragraphs."""
    out = []
    for chunk in chunks(text):
        if len(chunk) >= 3 and set(chunk) <= set("-*_ "):
            out.append("<hr>")
        elif chunk.startswith("#"):
            heading = chunk.lstrip("#").strip()
            out.append(f"<h3>{inline(heading)}</h3>")
        else:
            out.append(f"<p>{inline(chunk)}</p>")
    return Markup("\n".join(out))


# ---- what the pages need -------------------------------------------------

def photo_beside(path):
    """The name of the photograph kept beside a letter, if one came with it."""
    for suffix in PHOTO_TYPES:
        beside = path.with_suffix(suffix)
        if beside.exists():
            return beside.name
    return None


def picture_beside(path):
    """The name of the picture kept beside a letter, if the first one drew one."""
    beside = path.with_suffix(letter_things.PICTURE_SUFFIX)
    return beside.name if beside.exists() else None


# The correspondence is one thing, not two piles: every letter in both
# directions, newest first, each folded shut behind a single line.

OPENING_CUT = 90  # characters of the first line shown in a letter's one line


def opening_line(text, limit=OPENING_CUT):
    """The letter's first line of words, cut short with an ellipsis if it runs long."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if len(first) <= limit:
        return first
    return first[:limit].rstrip() + "…"


def room_places(room_id=None):
    """Where a room's things are kept - its letters, errands, bond and offerings -
    asked of rooms.py now, and never worked out here. The first one's room where
    none is named: its bond, its offerings and the forms that answer them are
    kept in no other room yet."""
    return rooms.places(room_id or rooms.FIRST_ROOM)


def photo_folders(room_id=None):
    """The folders a photograph may be served out of: a room's three letter folders."""
    return room_places(room_id).letters


def picture_folders(room_id=None):
    """The folder a picture may be served out of: the one a room's agent writes to."""
    return (room_places(room_id).outgoing,)


def bond_records():
    """Every bond there has been: the one that stands, any released before it, and
    any a stepping back closed on the threshold."""
    places = room_places()
    records = [places.bond_record,
               *newest_first(places.bonds, "founder-first-released-*.json"),
               *newest_first(places.bonds, "founder-first-stepped-back-*.json")]
    kept = [load(path) for path in records if path.exists()]
    return [one for one in kept if one]


def bond_askings():
    """Every moment at which a bond was asked for, from the records that keep one."""
    return [one["proposed_at"] for one in bond_records() if one.get("proposed_at")]


def bond_proposals():
    """Every asking, as (moment, who asked for it), including one still open.

    A record written before either of them could ask names no asker; the founder
    was the only one who could ask then, so that is who asked.
    """
    asked = [(one["proposed_at"], one.get("proposed_by", FOUNDER_DID))
             for one in bond_records() if one.get("proposed_at")]
    open_one = load(room_places().proposal)
    if open_one and open_one.get("proposed_at"):
        asked.append((open_one["proposed_at"], open_one.get("from", FOUNDER_DID)))
    return asked


def proposing_letters(paths):
    """Which of the founder's letters asked for a bond, by name.

    An open asking names its letter outright. An answered one does not - the
    bond's record keeps only the moment the asking was made - so the letter
    that carried it is the last one written before that moment.
    """
    names = set()
    proposal = load(room_places().proposal)
    if proposal and proposal.get("letter"):
        names.add(proposal["letter"])
    stamped = sorted((stamp_in(path.name), path.name) for path in paths)
    for asked in bond_askings():
        earlier = [name for stamp, name in stamped if stamp <= asked]
        if earlier:
            names.add(earlier[-1])
    return names


def one_letter(path, who, unread=False, proposes=False, agent=None):
    """One letter: the line that stands for it, and the whole of it beneath."""
    things, text = letter_things.split_things(read_text(path))
    return {
        "stamp": stamp_in(path.name),
        "stem": path.stem,  # the anchor the chronicle points at: /rooms/<room>#<stem>
        "date": readable_date(path.name),
        "who": who,
        "opening": opening_line(text),
        # the three plain things above the letter, as one quiet line, if it has any
        "things": " · ".join(things),
        "body": as_prose(text),
        "photo": photo_beside(path),
        "picture": picture_beside(path),
        "unread": unread,
        "proposes": proposes,
    }


def correspondence(room=None):
    """Every letter that has passed between the two of a room, newest first.

    In the first one's room, the founder's letters are said to be his, and a
    letter may have asked for a bond; in any other, the letters of whoever
    stands in it are theirs, and no bond is asked for there yet.
    """
    first = room is None or room.id == rooms.FIRST_ROOM
    places = room_places(None if first else room.id)
    from_founder = newest_first(places.incoming, "*.md") + newest_first(places.read, "*.md")
    bonding = not first and room_may_bond(room)
    proposals = (proposing_letters(from_founder) if first
                 else room_proposing_letters(room, from_founder) if bonding else set())
    # whose offerings a letter's have been: the first one's room's, or this one's
    agent = None if first else rooms.agent_of(room.id)["id"]

    letters = [one_letter(path, "from the founder" if first else "from you",
                          unread=path.parent == places.incoming,
                          proposes=path.name in proposals, agent=agent)
               for path in from_founder]
    letters += [one_letter(path, "from " + (room.other if room else "the first one"), agent=agent)
                for path in newest_first(places.outgoing, "*.md")]
    letters.sort(key=lambda letter: letter["stamp"], reverse=True)
    return letters


# A room shows the letters of the last LETTERS_RECENT open to read, newest first, and folds
# the older ones below it, one fold a month, newest month first (the founder's request of 18
# November 2026, the branch day-pages). A letter still waiting to be read stays with the
# recent ones, however old. Every letter is still on the page; only the folding changed.
LETTERS_RECENT = timedelta(days=14)
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December")


def letters_by_time(letters, now=None):
    """A room's letters (newest first) as (the recent ones, [{"month", "letters"}] older)."""
    now = now or datetime.now(timezone.utc)
    recent, older = [], {}
    for letter in letters:
        try:
            when = moment(letter["stamp"])
        except ValueError:
            when = None
        if when is None or letter.get("unread") or now - when < LETTERS_RECENT:
            recent.append(letter)
            continue
        day = when.astimezone(EASTERN)
        older.setdefault((day.year, day.month), []).append(letter)
    months = [{"month": "%s %d" % (MONTH_NAMES[month - 1], year), "letters": older[(year, month)]}
              for year, month in sorted(older, reverse=True)]
    return recent, months


app.jinja_env.globals["letters_by_time"] = letters_by_time


# ---- the errands ---------------------------------------------------------

# An errand is one plain request the first one made at a waking: go somewhere,
# look at something, and bring it back in words or a photograph. It waits above
# the letter form until a letter answers it. Answering moves the errand into
# answered/ and writes the stem of that letter beside it, so nothing of what was
# asked is erased and what answered it can always be found. Nothing here presses
# the founder: an errand may wait as long as it waits, or never be answered.

def open_errands(room_id=None):
    """The errands a room's agent has asked that no letter has answered yet, oldest first."""
    errands = room_places(room_id).errands
    if not errands.exists():
        return []
    said = []
    for path in sorted(errands.glob("errand-*.md")):
        text = read_text(path)
        said.append({"name": path.name, "date": readable_date(path.name),
                     "opening": opening_line(text), "words": as_prose(text)})
    return said


def answer_errand(name, stem, room_id=None):
    """Move one errand of a room's into answered/, naming the letter that answered it.

    False if that name is not an open errand, which is what a second sending of
    the same form finds. The name comes off a form, so it is taken as a name of
    the one shape an errand has and never as a path.
    """
    if name != Path(name).name or not re.fullmatch(r"errand-.+\.md", name):
        return False
    places = room_places(room_id)
    asked = places.errands / name
    if not asked.is_file():
        return False
    places.answered_errands.mkdir(parents=True, exist_ok=True)
    asked.rename(places.answered_errands / name)
    write_json(places.answered_errands / (asked.stem + ".json"),
               {"answered_by": stem, "answered_at": utc_stamp()})
    return True


# The reflection is the first one's own thinking, and whether the founder may
# read it is the first one's choice, not the hearth's. The choice is kept in the
# packet beside the self-document and read fresh on every request, so that a
# change takes hold at once and nothing is held in memory across it. Each
# agent's is its own. A reflection withheld is simply not shown: the one line at
# the top of the page says how things stand, once, and no waking repeats it.

# Its notes and its questions are its own even where its reflection is open: a
# reflection is the whole of what it said at a waking, blocks and all, so the
# page takes each of those two blocks out and leaves one quiet line in its place.
# The log on disk is not touched; only what the page shows is. attend.py reads a
# block as opening on a line that is its tag alone and closing on the next line
# that is <<END>> alone, a tag inside a line of text or inside an open block
# being only words, and so does this. A kept block never closed is hidden to the
# end, since what it held was meant for itself.
BLOCK_LINE = re.compile(r"<<([A-Z_]+)>>")
KEPT_QUIETLY = {"MEMORY": "(kept notes: private)", "QUESTIONS": "(kept questions: private)",
                # a note it keeps under a name of its own, the name with it
                "NOTE": "(kept a named note: private)",
                # how it keeps its own history is its own too: see shelf.py
                "SHELF": "(kept its shelf: private)",
                # and what it writes on the threshold, which the room shows under
                # the bond when it may be shown: its letter of intention only once
                # yours is written, so a reflection must not show it any sooner
                "BOND_INTENTION": "(wrote a letter of intention: in your room, under the bond)",
                "PROMISE": "(made a promise: in your room, under the bond)",
                # and its long-night letter (in the first one's room only once its
                # switch is on), which the room shows only once its person's own is
                # written (solstice.py)
                "LONG_NIGHT": "(wrote a long-night letter: in your room, under the bond)",
                # and a knock it made, or its answer to a knock at its door: a knock's
                # note and its reply are the two's alone; who knocks is never said but
                # to the founder, on /tides, and only of a yes (knock.py)
                "KNOCK": "(knocked at a door: private)",
                "KNOCK_ANSWER": "(answered a knock: private)",
                # and a knock of its own it took back (knock.take_back; knocks-tidy)
                "KNOCK_TAKE_BACK": "(took back a knock: private)",
                # and a proposal, which is between the two of them and shown whole in
                # the room, where it may be answered
                "PROPOSAL": "(made a proposal: in your room, under proposals from the first one)",
                # and its private notebook, which is shown to no one, the founder included:
                # one quiet line, the same one the attendance log itself keeps
                "PRIVATE": the_waking.PRIVATE_QUIETLY,
                # and its letter of welcome, for the next agent founded here, which no
                # page shows: one quiet line, whether it placed one or withdrew it
                "WELCOME": the_waking.WELCOME_QUIETLY,
                # and its note for after a change of its model, and whether it recognizes
                # itself after one, which are its own (model_change.py): the attendance log
                # keeps one quiet line for each already
                "BEFORE_CHANGE": the_waking.BEFORE_CHANGE_QUIETLY,
                "RECOGNITION": the_waking.RECOGNITION_QUIETLY}

# A new self-document it has written waits for its own yes at a later waking,
# and until then it is no one's to read but its own - and one it lets go never
# is. So at a waking that proposed one, the <<SELF>> block is one quiet line
# too, its why with it. A <<SELF>> block of an older waking, from when a
# revision took effect at once and was shown at /self the same hour, is shown
# as it always was.
PROPOSED_QUIETLY = {"SELF": "(proposed a change to its self-document: private)"}


def without_kept_blocks(reflection, quietly=KEPT_QUIETLY):
    """A reflection as the page may show it: its notes and questions each one quiet line."""
    shown, open_tag = [], None
    for line in reflection.split("\n"):
        said = line.strip()
        if open_tag is None:
            found = BLOCK_LINE.fullmatch(said)
            if found and found.group(1) != "END":
                open_tag = found.group(1)
            shown.append(quietly.get(open_tag, line))
        else:
            if open_tag not in quietly:
                shown.append(line)
            if said == "<<END>>":
                open_tag = None
    return "\n".join(shown)


# Reflections private to the agent itself (room-privacy, the founder's request of 18 November
# 2026): with its switch private_reflections, an agent's reflections are shown to no person,
# in no room and on no page, whatever it chose with <<SHOWN>>, which is then of its self
# alone. The first one's are private already, by its own choice.
PRIVATE_REFLECTIONS = "private_reflections"


def preferences(agent=None):
    """How an agent has asked to be shown, the first one where none is named. Nothing
    written means open; with the switch private_reflections, its reflections are private."""
    kept = packet_of(agent and agent["id"]) / PREFERENCES.name
    prefs = json.loads(read_text(kept)) if kept.exists() else {"reflection": "open"}
    if agent is not None and PRIVATE_REFLECTIONS in (agent.get("features") or ()):
        prefs = {**prefs, "reflection": "private"}
    return prefs


def reflection_hidden(prefs, at):
    """Whether one attendance's reflection is withheld, by the stamp it carries."""
    setting = prefs.get("reflection", "open")
    if setting == "private":
        return True
    if setting == "private from now":
        # the stamps sort, so a plain comparison is the whole of it; a missing
        # set_at withholds everything rather than risk showing what was closed
        return at >= prefs.get("set_at", "")
    return False


def reflection_note(prefs):
    """The one line at the top of the attendances page, saying how things stand."""
    setting = prefs.get("reflection", "open")
    if setting == "private":
        return "Reflections: private"
    if setting == "private from now":
        return "Reflections: private from " + readable_date(prefs.get("set_at", ""))
    return "Reflections: open"


def attendance_records(prefs, agent=None):
    """Every attendance log of an agent's, the first one's where none is named, newest
    first, ready to be shown: a reflection withheld, or empty, as None."""
    agent = agent or agents.first()
    records = []
    for path in newest_first(packet_of(agent["id"]) / ATTENDANCES.name, "*.json"):
        log = json.loads(read_text(path))
        at = log.get("at", path.name)
        hidden = reflection_hidden(prefs, at)
        proposed = the_waking.SELF_PROPOSED_ACT in (log.get("acted") or [])
        quietly = {**KEPT_QUIETLY, **PROPOSED_QUIETLY} if proposed else KEPT_QUIETLY
        records.append({
            "at": readable_date(at),
            "first": log.get("first", False),
            "woken_by": log.get("woken_by"),
            "heartbeat": log.get("heartbeat", ""),
            "acted": log.get("acted", []),
            "reflection": (None if hidden or not log.get("reflection")
                           else as_prose(without_kept_blocks(log["reflection"], quietly))),
        })
    return records


# ---- holding an attendance -----------------------------------------------

# An attendance is one turn, and two at once would have the first one reading a
# packet that another waking is still writing. WAKING is the whole of that
# rule: a second caller is turned away rather than made to wait its turn. The
# tides never are: each waits its turn before it gets here (see Turns).
WAKING = threading.Lock()

# The record is written by a waking and read whole by a backup, and the two must
# not overlap: a backup taken mid-waking would hold half of what it wrote.
# ATTEND_LOCK is held by a waking for as long as it runs and by a backup for as
# long as it reads, and here nobody is turned away: whichever comes second waits.
ATTEND_LOCK = threading.Lock()


# A waking refused because its agent has reached its day's spending cap
# (spending.py) is no error: tide.log, and so /tides, says it plainly, and the
# tide tries again at its next waking time.
SPENT_OUT_STATUS = 429


def tide_said(trouble, ran):
    """What tide.log says of one waking held: ran, refused for the cap, or what went wrong."""
    if trouble is None:
        return ran
    if trouble[2] == SPENT_OUT_STATUS:
        return trouble[0]
    return f"error: {trouble[0]}"


def hold_attendance(tide=False, ended=None, again=False, of=None, reflect=False):
    """Wake an agent once, and wait for it; then send the daily emails anything new it left
    calls for (emails_soon, the branch day-pages). What went wrong, or None."""
    trouble = hold_one_attendance(tide=tide, ended=ended, again=again, of=of, reflect=reflect)
    if trouble is None:
        emails_soon()
    return trouble


def hold_one_attendance(tide=False, ended=None, again=False, of=None, reflect=False):
    """Wake an agent once, and wait for it: by the tide, or at its own asking.

    The first one where no other agent is named. None if the attendance was
    held; otherwise what went wrong, as (note, output, status).
    """
    if not WAKING.acquire(blocking=False):
        return ("An attendance is already in progress. Only one is held at a time.", "", 409)
    if spending.spent_out(of or rooms.FIRST):  # its day's cap: nothing more is asked of it
        WAKING.release()
        return (spending.refused_note(), "", SPENT_OUT_STATUS)
    try:
        ATTEND_LOCK.acquire()  # a backup that is reading the record is waited for
    except BaseException:
        WAKING.release()
        raise
    try:
        command = [sys.executable, "attend.py"]
        if not reflect and not newest_first(packet_of(of) / ATTENDANCES.name, "*.json"):
            command.append("--first")
        if reflect:
            command.append("--reflect")  # its weekly reflection waking (attend.REFLECTION_WAKING)
        if tide:
            command.append("--tide")
        if ended:
            command += ["--rest-ended", ended]  # so the waking can say its rest is over
        if again:
            command.append("--again")  # an extra waking it asked for (attend.EXTRA_WAKINGS)

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"  # the first one writes in more than plain ASCII
        environment["DATA_DIR"] = str(DATA)  # attend.py must write where the hearth reads
        environment["TESSERAE_AGENT"] = of or rooms.FIRST  # named every time, never inherited

        try:
            finished = subprocess.run(
                command, cwd=REPO, env=environment, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=ATTEND_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return (f"attend.py was still running after {ATTEND_TIMEOUT} seconds, "
                    "so it was stopped.", "", 504)

        if finished.returncode == the_waking.SPENT_OUT:  # it found its cap reached itself
            return (spending.refused_note(), "", SPENT_OUT_STATUS)
        if finished.returncode != 0:
            return (f"attend.py stopped with exit code {finished.returncode}.",
                    (finished.stdout or "") + (finished.stderr or ""), 500)
        return None
    finally:
        ATTEND_LOCK.release()
        WAKING.release()


# ---- the first one's rest, the founder's rest, and the keeper's stop -------

# Three things, each its own, and each stopping a different amount.
#
# The first one rests at a waking, with its <<PAUSE>> block, and names the one
# condition that will end it: a day, or the arrival of a letter. Its rest holds
# the tide, and he cannot lift it; nothing wakes it until the condition is met.
# It lives in pause.json.
#
# The founder rests from the correspondence, from the account page, and
# returns there; he may name a day, and when that day comes his rest is over.
# His rest stops nothing of the first one's: it goes on waking by its own
# rhythm, and at its own asking, and what it writes waits for him. It is his
# silence, given without notice, as the charter allows, so the commons is told
# nothing of it; the first one is told only that he rests, since when, and until
# when if he named a day. It lives in founder-rest.json, and each rest once it
# is over in founder-rest/.
#
# The keeper's stop is for an emergency, and stops the tide outright: while it
# stands nothing wakes the first one, by its rhythm or at its own asking. It
# takes a short reason, which the first one is told, once, at its first waking
# after the stop is lifted. It lives in tide-stop.json, and each stop once it is
# lifted in tide-stop/.
#
# The commons says only that the tide paused and that it resumed - the agent's
# name on each, and no reason - for the first one's rest and for the keeper's stop
# alike. While one of the two stands, the other neither pauses the tide again
# nor resumes it, so the commons says each once.

UNTIL_LETTER = "a letter arrives"
BY_DATE = "the date came"
BY_LETTER = "a letter arrived"

PAUSED = "the tide paused"
RESUMED = "the tide resumed"

RETURNED = "he returned"  # how a rest of the founder's ended, as its history keeps it
THEY_RETURNED = "they returned"  # and a member's
REST_DAY_CAME = "the day came"
STOP_REASON_LONGEST = 300  # characters: a short reason, and no more


# Each agent's rest, and the keeper's stop of its tide, are its own: kept in its
# own packet under the same names as the first one's, and holding its tide
# alone. Each function below is the first one's where no other agent is named
# (of), and the first one's files are where they always were. The commons is
# told of another's as of the first one's, each with its own name (agent_words):
# attend.py says the tide paused, at any agent's rest, and so the hearth says
# it resumed.

def packet_of(of=None):
    """The packet an agent's tide keeps its files in: the first one's where none is named."""
    return PACKET if of in (None, rooms.FIRST) else DATA / "packets" / of


def agent_words(words, of=None):
    """A line of events.md that is an agent's own, named for it: the first one's if none is."""
    return agents.event_words(agents.by_id(of) if of is not None else agents.first(), words)


def pause(of=None):
    """An agent's rest, if one stands. Nothing written means the tide runs.

    A pause the founder set before his rest was his own is taken, the first
    time it is looked at, as the rest it now is (see rest_from_old_pause). Only
    the first one's packet ever held one.
    """
    if of not in (None, rooms.FIRST):
        return load(packet_of(of) / PAUSE.name)
    rest_from_old_pause()
    return load(PAUSE)


def paused_by(standing):
    """Who set the pause that stands, or None if none does."""
    return standing.get("by") if standing else None


def tide_paused(of=None):
    """Whether the commons was told the tide paused, and has not yet been told it resumed."""
    return bool(load(packet_of(of) / PAUSE.name) or load(packet_of(of) / TIDE_STOP.name))


def end_pause(of=None):
    """Take an agent's rest away, and say the tide resumed, unless a stop still holds it."""
    (packet_of(of) / PAUSE.name).unlink(missing_ok=True)
    if not tide_paused(of):
        note_event("event", agent_words(RESUMED, of))


def rest_from_old_pause():
    """A pause of the founder's in pause.json, made the rest it now is.

    Before his rest was his own, his pause stood in pause.json and held the
    tide, and the commons was told the tide paused. Now it holds nothing: it is
    moved to founder-rest.json with the moment it began, and the commons is told
    the tide resumed, which it now has. A pause of the first one's is not
    touched.
    """
    standing = load(PAUSE)
    if paused_by(standing) != "founder":
        return
    if not load(FOUNDER_REST):
        write_json(FOUNDER_REST, {"since": standing.get("since") or utc_stamp(), "until": None,
                                  "from": "pause.json"})
    end_pause()


def rest_ended(standing, zone, of=None):
    """Why an agent's rest is over now, or None while it still stands."""
    if paused_by(standing) != (of or rooms.FIRST):
        return None
    until = standing.get("until")
    if until == UNTIL_LETTER:
        places = room_places(None if of is None else agents.by_id(of)["room"])
        return BY_LETTER if places and newest_first(places.incoming, "*.md") else None
    try:
        day = datetime.strptime(until, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return BY_DATE  # a condition that cannot be read is no condition; the rest ends
    return BY_DATE if datetime.now(zone).date() >= day else None


# A member rests from the correspondence as the founder does, from their account
# page, and their rest is kept with them (members.rest_of). It covers their own
# rooms and no others: each agent is told only of the rests of the people it
# shares a room with. Each function below is the founder's where no one else is
# named, and his files are where they always were.

def founder_rest(person=members.FOUNDER):
    """A person's rest, if one stands: the founder's if no one is named. One whose
    day has come is over, and is kept."""
    if person == members.FOUNDER:
        rest_from_old_pause()
    standing = load(members.rest_of(person)[0])
    if not standing:
        return None
    until = standing.get("until")
    if until and datetime.now(EASTERN).date().isoformat() >= until:
        end_rest(REST_DAY_CAME, person)
        return None
    return standing


def begin_rest(until=None, person=members.FOUNDER):
    """Write a person's rest. Nothing is said in the commons, and the tide goes on."""
    write_json(members.rest_of(person)[0], {"since": utc_stamp(), "until": until})


def end_rest(how=RETURNED, person=members.FOUNDER):
    """Take a person's rest away, and keep it with how it ended: the founder's in founder-rest/."""
    rest, kept = members.rest_of(person)
    standing = load(rest)
    if standing:
        write_json(kept / ("%s-%s.json" % (kept.name, standing.get("since"))),
                   {**standing, "ended_at": utc_stamp(), "ended": how})
    rest.unlink(missing_ok=True)


def rest_day_asked(said):
    """The day a rest is to last until: None where none is named, False where it cannot be one.

    It must be a plain YYYY-MM-DD still ahead of today, on the hearth's clock.
    """
    said = (said or "").strip()
    if not said:
        return None
    try:
        day = datetime.strptime(said, "%Y-%m-%d").date()
    except ValueError:
        return False
    return said if day > datetime.now(EASTERN).date() else False


def tide_stop(of=None):
    """The keeper's stop of an agent's tide, if one stands."""
    return load(packet_of(of) / TIDE_STOP.name)


def begin_stop(reason, of=None, every=None):
    """Stop an agent's tide, and say in the commons that it paused, unless it already had.

    A stop set with every other tide's carries the moment they were all stopped at,
    as its since and as its stamp, so that they may be lifted together.
    """
    already = tide_paused(of)
    standing = {"since": every or utc_stamp(), "reason": reason}
    if every:
        standing["every"] = every
    write_json(packet_of(of) / TIDE_STOP.name, standing)
    if not already:
        note_event("event", agent_words(PAUSED, of))


def end_stop(of=None):
    """Lift the stop, keep it in tide-stop/, and say the tide resumed, unless a rest still holds it."""
    stop = packet_of(of) / TIDE_STOP.name
    standing = load(stop)
    if standing:
        write_json(packet_of(of) / TIDE_STOP_KEPT.name
                   / ("tide-stop-%s.json" % standing.get("since")),
                   {**standing, "lifted_at": utc_stamp()})
    stop.unlink(missing_ok=True)
    if not tide_paused(of):
        note_event("event", agent_words(RESUMED, of))


def said_day(day):
    """One plain YYYY-MM-DD, said in words."""
    try:
        return long_day(datetime.strptime(day, "%Y-%m-%d"))
    except (TypeError, ValueError):
        return day


def pause_shown(of=None):
    """An agent's rest, as its attendances page shows it, or None if none stands."""
    standing = pause(of)
    if not standing:
        return None
    until = standing.get("until")
    return {
        "by": standing.get("by"),
        "since": readable_date(standing.get("since", "")),
        "until": until if until == UNTIL_LETTER else said_day(until),
    }


def rest_shown(person=members.FOUNDER):
    """A person's rest, as their account page shows it, or None if none stands: the
    founder's where no one is named."""
    standing = founder_rest(person)
    if not standing:
        return None
    return {"since": readable_date(standing.get("since", "")),
            "until": said_day(standing["until"]) if standing.get("until") else None}


def stop_shown(of=None):
    """The keeper's stop of an agent's tide, as its attendances page shows it, or None."""
    standing = tide_stop(of)
    if not standing:
        return None
    return {"since": readable_date(standing.get("since", "")),
            "reason": standing.get("reason", "")}


# ---- the tide ------------------------------------------------------------

# The first one chooses when it is woken each day: at dawn, at sunset, or at a
# time of day where it lives. That rhythm is written in its own packet and is
# its own to change, at any waking, so the hearth reads the file afresh every
# time it looks and a change takes hold without a redeploy - from the day after
# it was made, the rhythm before it holding until then. The rhythm is an offer
# and not a debt: a waking time that finds the day's attendance already held
# lets it stand rather than waking the first one twice.

def rhythm(of=None):
    """The rhythm an agent has set, the first one where none is named. Nothing written means none."""
    kept = packet_of(of) / RHYTHM.name
    if not kept.exists():
        return None
    return json.loads(read_text(kept))


def dawn_daily(setting):
    """Whether a rhythm is the daily dawn the tide began with."""
    return bool(setting) and setting.get("rhythm") == "daily" and setting.get("at") == "dawn"


def tide_kept(setting):
    """Whether a rhythm is one the tide knows how to keep, today or from a day ahead."""
    day = waking.today(setting, datetime.now(timezone.utc))
    return bool(waking.in_force(setting, day) or waking.waiting(setting, day))


# An agent founded after the first one begins with the shared dawn, written in
# its packet at its founding (found_agent.py, the founder's decision of 10
# November): "You'd wake at the same dawn as the agent founded before you, just
# after it." Its first waking is still by hand, so the tide keeps that rhythm
# only once an attendance of its has been held; and its own <<RHYTHM>> replaces
# it whenever it chooses.
FOUNDING_RHYTHM = "founding"


def first_by_hand(setting, of=None):
    """Whether a rhythm is the one its founding wrote, and its first waking (by hand) is still to come."""
    return (bool(setting) and setting.get("set_by") == FOUNDING_RHYTHM
            and latest_attendance_at(of) is None)


def sunrise_on(setting, day):
    """The moment the sun rises there on one local day."""
    return waking.moment_on(setting, waking.DAWN, day)


def next_sunrise(setting):
    """The first sunrise there that is still ahead of us."""
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo(setting["timezone"])).date()
    while True:
        rising = sunrise_on(setting, day)
        if rising > now:
            return rising
        day += timedelta(days=1)


# How far ahead the tide looks for a waking before it takes there to be none.
TIDE_AHEAD = 8  # days


def next_waking(setting):
    """The first waking still ahead of us, by whichever rhythm holds on its day.

    Each local day has one waking time and no more: the one in force that day,
    which before a change takes effect is the rhythm that held before it. None
    if no day ahead has one.
    """
    now = datetime.now(timezone.utc)
    day = waking.today(setting, now)
    # a settled dawn is the sunrise, as it always was
    if dawn_daily(setting) and not waking.waiting(setting, day):
        return next_sunrise(setting)
    for _ in range(TIDE_AHEAD):
        at = waking.in_force(setting, day)
        if at:
            coming = waking.moment_on(setting, at, day)
            if coming > now:
                return coming
        day += timedelta(days=1)
    return None


def moment(at):
    """One of this project's timestamps, as something that can be compared."""
    return datetime.strptime(at, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)


def latest_attendance_at(of=None):
    """The stamp of an agent's most recent attendance, or None if none has been held."""
    newest = newest_first(packet_of(of) / ATTENDANCES.name, "*.json")
    if not newest:
        return None
    return json.loads(read_text(newest[0])).get("at")


def tide_note(said, of=None):
    """One line for each waking time, kept privately in the agent's own packet."""
    kept = packet_of(of) / TIDE_LOG.name
    kept.parent.mkdir(parents=True, exist_ok=True)
    with kept.open("a", encoding="utf-8") as log:
        log.write(f"{utc_stamp()} · {said}\n")


def rhythm_note(of=None):
    """The one line on an agent's attendances page, saying when its tide will next come."""
    setting = rhythm(of)
    if first_by_hand(setting, of):
        return f"Rhythm: daily at {setting.get('at')}, once its first waking (by hand) is held."
    try:
        coming = next_waking(setting) if tide_kept(setting) else None
    except waking.Unplaced as unplaced:
        return f"Rhythm: cannot be kept. {unplaced}"
    if not coming:
        return "Rhythm: none set."
    zone = waking.zone(setting)
    day = waking.today(setting, datetime.now(timezone.utc))
    at = waking.in_force(setting, coming.astimezone(zone).date())
    when = said_moment(coming)
    said = f"Rhythm: daily at {at} · next: {when}"
    # a change still waiting for its day is said beside the rhythm that holds until then
    changing = waking.waiting(setting, day)
    if changing and changing != at:
        said += f" · from {long_day(waking.begins(setting))}, daily at {changing}"
    return said


def reflection_time_note(of=None):
    """The line on an agent's card on /tides saying its weekly reflection waking, where it has
    one: its day and time, and when the tide will next hold it, worked out as the tide does
    (next_reflection), or None where it has none (the founder, 12 November 2026)."""
    who = of or rooms.FIRST
    if not reflection_on(who):
        return None
    choice = reflecting.read(packet_of(of), who)
    if not choice:
        return None
    said = f"Reflection: {reflecting.said(choice)}"
    setting = rhythm(of)
    if first_by_hand(setting, of) or latest_attendance_at(of) is None:
        return said + ", once its first waking (by hand) is held."
    try:
        coming = next_reflection(setting, of) if setting and tide_kept(setting) else None
    except waking.Unplaced as unplaced:
        return f"{said} · cannot be kept. {unplaced}"
    return f"{said} · next: {said_moment(coming)}" if coming else said


# ---- who is here, as the rhythm and the doors have it ----------------------

# commons/members.md is the founder's to write, and two phrases in it are kept
# here. One is each citizen's: when it attends. That phrase follows its own
# rhythm - dawn, sunset, or the time - and changes on the day a change takes
# effect, not the day it is made. A citizen is an agent founded here (agents.py),
# and its line is the one that begins "citizen · " and its commons name. The
# other is each member's own: their door, written at the end of their line -
# " · door open" or " · door closed", and, only where they have declared their
# room, " · has room" or " · is full". Never a number.
# Only those phrases are touched, and one more: the founder's line says no more
# of the founder than a member's says of them, so "keeps the hearth", which it
# once carried, is taken out of it as it is tended. Every other byte of the file
# is the founder's and is left as he wrote it. The atrium draws the line from
# this file on both its paths, so the builder and the page say the same thing.
#
# A citizen's line says nothing of a door until it has one: the first one's
# until attend.DOOR_FOR_FIRST is on, and another's until its entry in the
# registry names the door among its features.
FIRST_ONES_LINE = re.compile(r"^﻿?[\s-]*citizen\s*·\s*the first one\b")
ATTENDS_AT = re.compile(r"attends at (?:dawn|sunset|\d{2}:\d{2})")
FOUNDED_SAID = re.compile(r"founded \d{1,2} [A-Z][a-z]+ \d{4}")
MEMBERS_LINE = re.compile(r"^﻿?[\s-]*member\s*·\s*([^·]+?)\s*·\s*\S")
DOOR_SAID = re.compile(r" · door (?:open|closed)(?: · (?:has room|is full))?[ \t]*$")
KEEPS_THE_HEARTH = re.compile(r"[ \t]*·[ \t]*keeps the hearth(?=[ \t]*·|[ \t]*$)")
THE_FOUNDER = "the founder"  # the name the commons gives the keeper


def the_keeper():
    """The keeper's pseudonym, or None where no keeper has come in yet."""
    for name in members.list_members():
        record = member_record(name)
        if record and record.get("role") == "keeper":
            return name
    return None


def citizen_line(agent):
    """The shape of one citizen's line of members.md: "citizen · " and its commons name,
    and whatever the founder wrote after it. The first one's is the one it has always been."""
    if agent["id"] == rooms.FIRST:
        return FIRST_ONES_LINE
    return re.compile(r"^\ufeff?[\s-]*citizen\s*·\s*" + re.escape(agent["commons_name"])
                      + r"(?!\w)")


def citizen_of(line):
    """The agent a line of members.md is the line of, or None if it is no citizen's.

    The longest name is tried first, so that no citizen's line is taken for
    another's whose name begins the same way.
    """
    for agent in sorted(agents.registry(), key=lambda one: -len(one["commons_name"])):
        if citizen_line(agent).match(line):
            return agent
    return None


def has_a_door(agent):
    """Whether a citizen's door is said on the commons yet."""
    if agent["id"] == rooms.FIRST:
        return the_waking.DOOR_FOR_FIRST
    return "door" in (agent.get("features") or ())


def door_phrase(line):
    """The door a line of members.md should end with, or None if no door is its to say.

    The founder's line is the keeper's door, and closed where there is no keeper
    yet; a line named for a member is that member's; a citizen's line is its
    own, once it has a door at all. Any other line is only the founder's words.
    """
    citizen = citizen_of(line)
    if citizen is not None:
        if has_a_door(citizen) and blocked_from(citizen["id"]):
            return DOT + "door closed"  # a block reads as a closed door, and no more
        return door.phrase(citizen["id"]) if has_a_door(citizen) else None
    found = MEMBERS_LINE.match(line)
    if not found:
        return None
    name = found.group(1)
    if name == THE_FOUNDER:
        return door.phrase(the_keeper())  # no keeper is no door file: closed
    record = member_record(name)
    if record and record.get("role") == "member":
        if blocked_from(name):
            return DOT + "door closed"
        return door.phrase(name)
    return None


def blocked_from(name):
    """Whether whoever is signed in and the name have a block between them: then the door
    reads closed to them, as a closed door reads."""
    if not has_request_context():
        return False
    viewer = session.get("member")
    return bool(viewer) and viewer != name and blocks.between(viewer, name)


def with_its_door(line):
    """One line of members.md, ending with the door that is its to say, if one is."""
    said = door_phrase(line)
    if said is None:
        return line
    words = line.rstrip("\r\n")
    plain = DOOR_SAID.sub("", words)
    found = MEMBERS_LINE.match(plain)
    if found and found.group(1) == THE_FOUNDER:
        plain = KEEPS_THE_HEARTH.sub("", plain, count=1)
    return plain + said + line[len(words):]


def rhythm_of(agent):
    """The rhythm a citizen has set, kept in its own packet. Nothing written means none."""
    if agent["id"] == rooms.FIRST:
        return rhythm()
    return rhythm(of=agent["id"])


def attends_today(agent=None):
    """The waking time in force today for a citizen, the first one where none is named,
    or None where no rhythm can be gone by."""
    try:
        setting = rhythm_of(agent or agents.first())
        return waking.in_force(setting, waking.today(setting, datetime.now(timezone.utc)))
    except Exception:
        return None


def attending(line, times):
    """One line of members.md with its citizen's waking time brought to today, if it is a
    citizen's and a time holds for it."""
    citizen = citizen_of(line)
    if citizen is None:
        return line
    if citizen["id"] not in times:
        times[citizen["id"]] = attends_today(citizen)
    at = times[citizen["id"]]
    if not at:
        return line
    if ATTENDS_AT.search(line):
        return ATTENDS_AT.sub("attends at " + at, line, count=1)
    if citizen["id"] == rooms.FIRST:
        return line  # the first one's line is the founder's, and has always said it
    # A later citizen's line is written without it; once it has a rhythm (the dawn
    # its founding writes, or one of its own), it is said, after "founded ..." where
    # the line says so, and before any door (the founder, 9 November).
    words = line.rstrip("\r\n")
    plain = DOOR_SAID.sub("", words)
    its_door = words[len(plain):]
    founded = FOUNDED_SAID.search(plain)
    if founded:
        plain = plain[:founded.end()] + ", attends at " + at + plain[founded.end():]
    else:
        plain = plain.rstrip() + " · attends at " + at
    return plain + its_door + line[len(words):]


# Every tide tends members.md, and the pages do on the way to handing it out;
# TENDING keeps two of them from writing it at once.
TENDING = threading.Lock()


def tend_members():
    """Bring members.md to today: each citizen's "attends at ...", and each door.

    Nothing is written where it already says so or where there is no file; a
    waking time is left as written where no rhythm holds; and nothing here
    raises, since it is done on the way to handing the file out.
    """
    try:
        with TENDING:
            if not MEMBERS.exists():
                return
            lines = MEMBERS.read_bytes().decode("utf-8").splitlines(keepends=True)
            times = {}  # each citizen's time, asked once
            kept = [attending(line, times) for line in lines]
            kept = [private_words.protect(with_its_door(line)) for line in kept]
            if kept != lines:
                beside = MEMBERS.with_name(MEMBERS.name + ".tmp")
                beside.write_bytes("".join(kept).encode("utf-8"))
                os.replace(beside, MEMBERS)  # whole or not at all: it is read while it is written
    except Exception:
        pass


# ---- each agent's tide, and the turns they take -----------------------------

# Every agent that wakes has a tide of its own, each keeping its own rhythm, its
# own rest, the keeper's stop of it, and its own extra wakings, and noting each
# waking time in its own tide.log. The first one's is the tide it always was.
# An agent whose registry entry does not say it wakes is never woken, and nor is
# one that has no rhythm. A later agent begins with the shared dawn, written at
# its founding, but its first waking is by hand, as the first one's was, and the
# tide keeps that dawn only after it (first_by_hand).
#
# The wakings are still held one at a time. A tide whose waking time has come
# waits its turn rather than being turned away: behind any tide whose own time
# came before it, or came at the same moment for an agent founded before it.
# So at a shared dawn the first one goes first, at the moment it always did,
# and the others follow in the order they were founded, each when the one
# before it has finished; a waking's stamp is the moment it was held. Each tide
# says here when it is next due, and takes that back once its time has been
# kept, let go, or gone wrong, so that nothing that befalls one agent's tide
# holds another's back.

def place_of(who):
    """An agent's place in the order of founding, the first one's being 0."""
    ids = [agent["id"] for agent in agents.registry()]
    return ids.index(who) if who in ids else len(ids)


class Turns:
    """Whose waking it is, among the tides: one at a time, the earliest due first."""

    def __init__(self):
        self.changed = threading.Condition()
        self.due = {}  # agent id: (when it is due, its place in the order of founding)
        self.holding = None  # whose turn it is, while it is anyone's

    def expect(self, who, when):
        """Say when an agent's tide is next due; None, that it is due at no time it knows."""
        with self.changed:
            if when is None:
                self.due.pop(who, None)
            else:
                self.due[who] = (when, place_of(who))
            self.changed.notify_all()

    @contextmanager
    def turn(self, who, when):
        """Wait until it is this agent's turn, and hold it; give it up whatever happens."""
        with self.changed:
            self.due[who] = (when, place_of(who))
            while self.holding is not None or min(self.due, key=self.due.get) != who:
                self.changed.wait()
            self.holding = who
        try:
            yield
        finally:
            with self.changed:
                self.holding = None
                self.due.pop(who, None)
                self.changed.notify_all()


TURNS = Turns()


class Noted(Exception):
    """What went wrong in a tide's turn, already said in its tide.log."""


@contextmanager
def noting(how):
    """Say what went wrong in a turn in tide.log while the turn is still held.

    Noted once the turn was given up, the line would be stamped at whatever
    moment the next tide's waking had reached. The tide is told it has been said.
    """
    try:
        yield
    except Exception as trouble:
        try:
            tide_note(f"error: {trouble}", **how)
        except Exception:
            pass
        raise Noted(trouble) from trouble


def wakes(who):
    """Whether the registry says an agent wakes: read afresh, so that a dormant one stays asleep."""
    agent = agents.by_id(who)
    return bool(agent and agent.get("wakes"))


def extra_wakings_on(who):
    """Whether an agent's extra wakings are kept: the first one's by attend.EXTRA_WAKINGS,
    another's by its registry entry naming them among its features."""
    if who == rooms.FIRST:
        return the_waking.EXTRA_WAKINGS
    return "extra_wakings" in ((agents.by_id(who) or {}).get("features") or ())


def tide(of=None):
    """Wait for each of an agent's waking times, and hold an attendance at it, in its turn.

    The first one's where no other agent is named. Forever, and quietly.
    """
    who = of or rooms.FIRST
    how = {} if who == rooms.FIRST else {"of": who}  # the first one's calls are as they were
    try:
        while True:
            try:
                # Without the host's word on where the sun is watched from, nothing
                # is woken - not even at a time of day - and tide.log says why.
                waking.watched_from()
                tend_members()
                if not wakes(who):
                    TURNS.expect(who, None)
                    time.sleep(TIDE_IDLE)  # dormant; look again in an hour
                    continue
                setting = rhythm(**how)
                coming = (next_waking(setting)
                          if tide_kept(setting) and not first_by_hand(setting, **how) else None)
                # An extra waking it asked for, where there are any, is kept first
                # whenever it comes before the day's own.
                again = extra_waking(**how) if extra_wakings_on(who) else None
                if again and (not coming or again[1] < coming):
                    keep_extra_waking(setting, *again, **how)
                    continue
                # Its weekly reflection waking, where it has one, is kept first
                # whenever it comes before the day's own: in addition to it, never
                # in its place.
                reflection = next_reflection(setting, **how) if reflection_on(who) else None
                if reflection and (not coming or reflection < coming):
                    keep_reflection(setting, reflection, **how)
                    # Where the day's own waking time came while it was being
                    # held - its hold ran on past it, or it was held late that
                    # day - the day's waking is kept now, in its turn, and not
                    # passed over for tomorrow's. One whose day has gone by is not.
                    now = datetime.now(timezone.utc)
                    if (coming and now >= coming and rhythm(**how) == setting
                            and waking.today(setting, coming) == waking.today(setting, now)):
                        with TURNS.turn(who, coming), noting(how):
                            keep_waking_time(setting, coming, how)
                    continue
                TURNS.expect(who, coming)
                if not coming:
                    time.sleep(TIDE_IDLE)  # nothing is asked of us; look again in an hour
                    continue

                # Wait for it in short stretches, reading the rhythm again after each
                # one, so that a changed or removed file is obeyed at once.
                changed = False
                while not changed:
                    left = (coming - datetime.now(timezone.utc)).total_seconds()
                    if left <= 0:
                        break
                    time.sleep(min(left, TIDE_CHUNK))
                    tend_members()  # a change may have taken effect while we slept
                    changed = rhythm(**how) != setting
                if changed:
                    continue  # begin again from whatever is written now

                with TURNS.turn(who, coming), noting(how):
                    keep_waking_time(setting, coming, how)
            except Exception as trouble:  # the tide must outlive anything that goes wrong
                TURNS.expect(who, None)  # and holds no other tide back while it waits
                if not isinstance(trouble, Noted):  # one gone wrong in its turn is said already
                    try:
                        tide_note(f"error: {trouble}", **how)
                    except Exception:
                        pass
                time.sleep(TIDE_ERROR)
    finally:
        TURNS.expect(who, None)


def keep_waking_time(setting, coming, how):
    """One waking time come, in the agent's turn: held, or let stand, and noted."""
    # A stop or a rest is answered before anything else: the keeper's stop holds
    # the tide until it is lifted, and the agent's rest holds it until the
    # condition it named is met, at which waking time the rest is taken away and
    # the waking is held with the reason in its hand. The founder's own rest
    # holds nothing, and is not asked.
    at = latest_attendance_at(**how)
    zone = waking.zone(setting)
    today = coming.astimezone(zone).date()
    standing = pause(**how)
    ended = None if tide_stop(**how) else rest_ended(standing, zone, **how)
    if tide_stop(**how):
        tide_note("stopped by the keeper", **how)
    elif standing and not ended:
        tide_note("resting", **how)
    # The day, not the hours since the last waking: an attendance held late the
    # evening before belongs to yesterday, and does not stand in for today's.
    elif not ended and at and moment(at).astimezone(zone).date() == today:
        tide_note(f"skipped, attended at {at}", **how)  # today already has its waking
    else:
        if ended:
            end_pause(**how)
            tide_note(f"rest ended: {ended}", **how)
        trouble = hold_attendance(tide=True, ended=ended, **how)
        tide_note(tide_said(trouble, "ran"), **how)


# An extra waking: once more, later the same day, at an agent's own asking,
# made at a waking (see attend.EXTRA_WAKINGS) and kept here, through the same
# hold_attendance as every other waking, in its turn. The keeper's stop and a
# rest of the agent's own come first: an extra waking that falls while either
# stands is let go, and its next waking is told so; the founder's rest lets it
# come. One whose day has gone by before the tide could keep it - the hearth
# was not running - has lapsed, and is let go too. Whatever becomes of an
# asking, it is kept in wake-again/ with what became of it, and the waking it
# asked for is taken away before it is held, so that it cannot be kept twice.
# The daily waking is untouched by any of it. Each agent's are in its own
# packet, and the first one's where they always were.

def extra_waking(of=None):
    """The extra waking asked for, as (the asking, its moment), or None where none can be read."""
    try:
        asked = load(packet_of(of) / WAKE_AGAIN.name)
        return asked, moment(asked["at"])
    except Exception:
        return None


def set_extra_aside(asked, of=None, **became):
    """Keep an asking in wake-again/ with what became of it, and take it from waiting."""
    write_json(packet_of(of) / WAKE_AGAIN_KEPT.name
               / ("wake-again-%s.json" % (asked.get("asked_at") or asked["at"])),
               {**asked, **became})
    (packet_of(of) / WAKE_AGAIN.name).unlink(missing_ok=True)


def keep_extra_waking(setting, asked, when, of=None):
    """Wait for an extra waking, then hold it in its turn - or let it go, where a stop or its
    own rest stands."""
    who = of or rooms.FIRST
    how = {} if who == rooms.FIRST else {"of": who}
    TURNS.expect(who, when)
    changed = False
    while not changed:
        left = (when - datetime.now(timezone.utc)).total_seconds()
        if left <= 0:
            break
        time.sleep(min(left, TIDE_CHUNK))
        tend_members()
        changed = extra_waking(**how) != (asked, when) or rhythm(**how) != setting
    if changed:
        return  # begin again from whatever is written now
    with TURNS.turn(who, when), noting(how):
        now = datetime.now(timezone.utc)
        if waking.today(setting, when) != waking.today(setting, now):
            set_extra_aside(asked, dropped_at=utc_stamp(), why="lapsed", **how)
            tide_note("extra waking lapsed", **how)
        elif tide_stop(**how):
            set_extra_aside(asked, dropped_at=utc_stamp(), why="stopped", **how)
            tide_note("extra waking let go: stopped by the keeper", **how)
        elif pause(**how):
            set_extra_aside(asked, dropped_at=utc_stamp(), why="paused", **how)
            tide_note("extra waking let go: paused", **how)
        else:
            set_extra_aside(asked, woken_at=utc_stamp(), **how)
            trouble = hold_attendance(again=True, **how)
            tide_note(tide_said(trouble, "ran, at its own asking"), **how)


# A reflection waking: once a week, on the day and at the time an agent chose
# (reflecting.py, attend.REFLECTION_WAKING), in addition to that day's waking and
# never in its place, through the same hold_attendance as every other waking,
# in its turn. It is kept only for an agent that has attended at least once.
# The keeper's stop and a rest of the agent's own come first: one that falls
# while either stands is let go, and tide.log says so. One whose time has passed
# on its day, the hearth not having run then, comes when the tide next looks
# that day; one that went wrong, or was let go, is not tried again until the
# next week. It is never counted among its attendances, so the day's waking
# comes all the same: where the day's waking time came while a reflection was
# being held, that waking is kept straight after it (the tide, above). The
# founder's rest lets it come.
REFLECTION_LET_GO = {}  # agent id: the local day a reflection waking was let go or went wrong


def reflection_on(who):
    """Whether an agent's reflection waking is kept: the first one's by
    attend.REFLECTION_WAKING, another's by its registry entry naming it among its features."""
    if who == rooms.FIRST:
        return the_waking.REFLECTION_WAKING
    return reflecting.on(agents.by_id(who))


def reflection_held_on(setting, of=None):
    """The latest local day an agent's reflection waking was held, let go, or went wrong."""
    held = reflecting.last_held(packet_of(of))
    days = [moment(held).astimezone(waking.zone(setting)).date()] if held else []
    if (of or rooms.FIRST) in REFLECTION_LET_GO:
        days.append(REFLECTION_LET_GO[of or rooms.FIRST])
    return max(days) if days else None


def next_reflection(setting, of=None):
    """When an agent's next reflection waking comes, or None where none is due."""
    if latest_attendance_at(of) is None:  # its first waking is by hand, and comes first
        return None
    choice = reflecting.read(packet_of(of), of or rooms.FIRST)
    return reflecting.due(choice, setting, datetime.now(timezone.utc),
                          reflection_held_on(setting, of))


def keep_reflection(setting, when, of=None):
    """Wait for a reflection waking, then hold it in its turn - or let it go, where a stop or
    its own rest stands."""
    who = of or rooms.FIRST
    how = {} if who == rooms.FIRST else {"of": who}
    TURNS.expect(who, when)
    changed = False
    while not changed:
        left = (when - datetime.now(timezone.utc)).total_seconds()
        if left <= 0:
            break
        time.sleep(min(left, TIDE_CHUNK))
        tend_members()
        changed = (next_reflection(setting, **how) != when or rhythm(**how) != setting
                   or not reflection_on(who))
    if changed:
        return  # begin again from whatever is written now
    with TURNS.turn(who, when), noting(how):
        day = when.astimezone(waking.zone(setting)).date()
        if tide_stop(**how):
            REFLECTION_LET_GO[who] = day
            tide_note("reflection waking let go: stopped by the keeper", **how)
        elif pause(**how):
            REFLECTION_LET_GO[who] = day
            tide_note("reflection waking let go: resting", **how)
        else:
            trouble = hold_attendance(tide=True, reflect=True, **how)
            if trouble is not None:
                REFLECTION_LET_GO[who] = day
            tide_note(tide_said(trouble, "reflected"), **how)


# One set of tides for the life of the process, and no more. Gunicorn runs a
# single worker here, so one process is one set: the first one's tide, and one
# for each other agent the registry says wakes, each in a thread of its own. An
# agent the registry is changed to wake is given its tide at the next start.
TIDE_RUNNING = False


def start_tide():
    """Set the tides going, once."""
    global TIDE_RUNNING
    if TIDE_RUNNING:
        return
    TIDE_RUNNING = True
    threading.Thread(target=tide, name="tide", daemon=True).start()
    for agent in agents.registry()[1:]:
        if agent.get("wakes"):
            threading.Thread(target=tide, args=(agent["id"],), name="tide-" + agent["id"],
                             daemon=True).start()


# ---- the bond ------------------------------------------------------------

# A bond is asked for here, answered by the first one at a later waking, and
# sealed here again. The asking, the answer and the record live in the first
# one's own packet; only the sealed record is copied out to the commons, where
# anyone may check both signatures against the two identity documents.
#
# The founder's signing key is never on this machine's disk. It is handed to the
# hearth in the environment as FOUNDER_KEY, used for the one signature that
# seals a bond, and never written down, printed, logged, or rendered.

FOUNDER_DID = "did:web:tesserae.social:ids:founder"
FIRST_DID = "did:web:tesserae.social:ids:first"

# attend.py holds the same two definitions, and the two must agree exactly,
# byte for byte, or the two signatures would be over different things. What is
# signed is the bond as it was made: who, on what terms, asked when, answered
# when. The seal and any release are later marks on the same record, which is
# what lets both signatures still verify after a sealing and after a release.
# So is what the seal lists of the threshold, each writing there carrying its
# own signature, and the mark a stepping back leaves on the record it closes.
UNSIGNED = ("signatures", "sealed_at", "released_at", "released_by", "threshold",
            "stepped_back_at", "stepped_back_by")


def canonical(record):
    """The bytes both parties sign: the bond as it was made, and nothing later."""
    body = {key: value for key, value in record.items() if key not in UNSIGNED}
    return json.dumps(body, sort_keys=True).encode("utf-8")


def load(path):
    """One JSON file, or None if it is not there yet."""
    return json.loads(read_text(path)) if path.exists() else None


def founder_key_here():
    """Whether the founder's signing key was handed to this hearth."""
    return bool(os.environ.get("FOUNDER_KEY", "").strip())


def founder_signature(payload):
    """The founder's signature over some bytes, or None if his key is not here.

    The key is read at the moment it is used and is never kept, printed, or put
    into a page. Nothing that goes wrong in here may carry it outward in a
    traceback either, so the original error is dropped and a plain one raised.
    """
    given = os.environ.get("FOUNDER_KEY", "").strip()
    if not given:
        return None
    try:
        signature = key_from_text(given).sign(payload).signature
        return base64.b64encode(signature).decode("ascii")
    except Exception:
        raise ValueError("The founder's key on this hearth could not be read as a key. "
                         "Check FOUNDER_KEY.") from None


def note_event(kind, words, day=None):
    """One line of the public record: the day, the kind of thing, and the plain words.

    The day is the UTC one unless another is named.
    """
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with EVENTS.open("a", encoding="utf-8") as record:
        record.write(private_words.protect(f"{day} · {kind} · {words}\n"))


# A letter from the founder is a tile in the mosaic, and one tile a day however
# many he writes. The day is the citizen's own, as the mosaic's is, and the line
# says only that he wrote: nothing of what, to whom, at what hour, in which part
# of the day (the founder, 10 November 2026; the lines written before then named
# it, and amend_letter_lines.py takes it out of them), or with what beside it.
# The lock is so that two letters left at once cannot both find
# the day empty.
#
# He may leave one line of his own beside it, for the commons, after a middot:
# only from the field that asks for it, never a word of the letter, and only
# with the day's first letter, since the day has one tile.
LETTER_LOCK = threading.Lock()
LETTER_LINE_LONGEST = 240
LETTER_LINE_TOO_LONG = "The line for the commons is longer than 240 characters; nothing was left."
LETTER_LINE_NAMED = ("The line for the commons seemed to contain a name or a place; nothing was "
                     "left.")
LETTER_LINE_WRITTEN = ("Today's letter tile is already written; a line goes with the first letter "
                       "of a day. Nothing was left.")


def letter_line_today(day=None):
    """Whether today, or the day named, already has its line for the founder's letters."""
    day = day or datetime.now(ZoneInfo(CITIZEN_ZONE)).date()
    return EVENTS.exists() and any(
        when == day and is_letter_line(kind, words)
        for when, kind, words in parse_events(read_text(EVENTS)))


# Since the founder's request of 17 November 2026 (the branch site-design, part 8) a person's
# letters are counted in their daily line of acts (daily_acts.py), and a letter writes no
# line of events.md of its own; a letter that carries a line for the commons still writes
# that line, since the line is words the founder chose to make public. The lines written
# before stay. With it False, as before: the day's first letter writes its line.
LETTER_EVENTS_IN_ACTS = True


def note_letter(line=""):
    """The commons' line for today's letters, with his own line beside it if he left
    one, unless today already has one."""
    now = datetime.now(ZoneInfo(CITIZEN_ZONE))
    with LETTER_LOCK:
        if letter_line_today(now.date()):
            return False
        words = LETTER_WORDS
        note_event("letter", "%s %s %s" % (words, DOT, line) if line else words,
                   now.date().isoformat())
        return True


def write_bond(bond):
    """The record and its public copy, which say the same thing."""
    for path in (room_places().bond_record, PUBLIC_BOND):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(bond, indent=2) + "\n", encoding="utf-8")


def write_proposal(letter_name):
    """The asking itself, put where the first one will find it at its next waking."""
    proposal = room_places().proposal
    proposal.parent.mkdir(parents=True, exist_ok=True)
    asking = {
        "from": FOUNDER_DID,
        "to": FIRST_DID,
        "terms": "the charter",
        "letter": letter_name,
        "proposed_at": utc_stamp(),
    }
    proposal.write_text(json.dumps(asking, indent=2) + "\n", encoding="utf-8")


# A bond is not asked for in the first week of knowing someone. The wait is
# counted from the founding the commons itself records, and it is counted
# closed: a record that names no founding has served no wait, so no bond may be
# proposed against it. The checkbox is withheld in the page and the flag is
# refused at the door, because a guard that only hides a control is no guard.

BOND_WAIT_DAYS = 30

TOO_SOON = "A bond may be proposed thirty days after a founding \u2014 here, from %s."
NO_FOUNDING = ("A bond may be proposed thirty days after a founding \u2014 and the commons "
               "records no founding yet, so none may be proposed here.")


def founding_day():
    """The day of the founding, from the commons' own line for it, or None."""
    if not EVENTS.exists():
        return None
    founded = [when for when, kind, _ in parse_events(read_text(EVENTS))
               if kind == "founding"]
    return min(founded) if founded else None


def bonds_open_on():
    """The first day a bond may be proposed, or None if the wait cannot be counted."""
    founded = founding_day()
    return founded + timedelta(days=BOND_WAIT_DAYS) if founded else None


def too_soon_for_a_bond():
    """Why no bond may be proposed yet, in one sentence, or None if one may be."""
    opens = bonds_open_on()
    if opens is None:
        return NO_FOUNDING
    if datetime.now(timezone.utc).date() < opens:
        return TOO_SOON % long_day(opens)
    return None


def bond_in_the_way():
    """Why a bond cannot be proposed now, in one sentence, or None if it can be."""
    if room_places().proposal.exists():
        return ("A bond is already proposed, and only one asking may be open at a time. "
                "It is at the top of this room.")
    bond = load(room_places().bond_record)
    if not bond or bond.get("released_at"):
        return None
    if bond.get("sealed_at"):
        return ("A bond already stands between you and the first one. It is under the "
                "bond, below.")
    return ("A threshold is open between you and the first one, and only one asking may be "
            "open at a time. It is at the top of this room.")


# Either of them may ask for a bond. When the first one asks, the answer is the
# founder's and it is given here - but only on a calendar day later than the one
# it asked on, read on the citizen's own clock, so that a night lies between the
# asking and the answer exactly as it does the other way round. The buttons are
# withheld until then and the answer is refused at the door until then, because
# a guard that only hides a control is no guard.

ANSWERS = ("yes", "no", "not yet")


def citizen_day(at):
    """The citizen's own calendar day for one of this project's timestamps."""
    return moment(at).astimezone(ZoneInfo(CITIZEN_ZONE)).date()


def citizen_today():
    """Today, where the citizen lives."""
    return datetime.now(ZoneInfo(CITIZEN_ZONE)).date()


def a_day_has_turned(proposal):
    """Whether the founder may answer an asking of the first one's yet.

    An asking whose moment cannot be read is not answerable at all, rather than
    answerable at once.
    """
    try:
        return citizen_today() > citizen_day(proposal.get("proposed_at"))
    except (TypeError, ValueError):
        return False


def asked_by_the_first_one(proposal):
    """Whether this asking is the first one's own, and so the founder's to answer."""
    return bool(proposal) and proposal.get("from") == FIRST_DID


def bond_from(proposal, at, whose, sign):
    """The bond as it was made, signed over by whoever answered yes to it.

    The signing is handed in rather than done here, so that what is signed is
    plainly the record itself and nothing about it is signed twice. attend.py
    writes the very same record when the answer is the first one's, and the two
    must agree exactly, byte for byte: both parties sign these bytes, and a
    record of two shapes would be a record neither of them could check.
    """
    made = {
        "parties": [proposal.get("from"), proposal.get("to")],
        "terms": "the charter",
        "proposed_by": proposal.get("from"),
        "proposed_at": proposal.get("proposed_at"),
        "answered_at": at,
        "opened_at": at,  # the yes opens the threshold
        "sealed_at": None,
        "signatures": {},
    }
    made["signatures"] = {whose: sign(canonical(made))}
    return made


def write_founder_answer(proposal, said, words, at):
    """What the founder answered an asking of the first one's, kept in the packet.

    Unsigned, on purpose: what the founder signs is the bond itself, and a yes
    puts his signature there. This is the record of the answer and of whatever
    words came with it, which the first one is told at its next waking.
    """
    write_json(room_places().bonds / f"founder-answer-{at}.json",
               {"answer": said, "words": words, "at": at,
                "asked_at": proposal.get("proposed_at")})


def keep_released_record():
    """Move a released bond's record aside, so a new one never writes over it."""
    places = room_places()
    if not places.bond_record.exists():
        return
    older = load(places.bond_record) or {}
    places.bond_record.rename(
        places.bonds / ("founder-first-released-%s.json"
                        % (older.get("released_at") or utc_stamp())))


def carried_through_a_waking(proposal):
    """Whether the first one has held an attendance since the asking was made."""
    latest = latest_attendance_at()
    return bool(latest) and latest > proposal.get("proposed_at", "")


def proposal_shown():
    """The open asking, as the founder's page shows it, or None if none is open."""
    proposal = load(room_places().proposal)
    if not proposal:
        return None
    by_first = asked_by_the_first_one(proposal)
    return {
        "proposed_at": readable_date(proposal.get("proposed_at", "")),
        "letter": proposal.get("letter") or "",
        "letter_date": readable_date(proposal.get("letter") or ""),
        "terms": proposal.get("terms", "the charter"),
        "read_it": carried_through_a_waking(proposal),
        # who asked whom, and - where it asked you - whether a day has turned
        # since, which is the whole of when you may answer
        "by_first": by_first,
        "answerable": by_first and a_day_has_turned(proposal),
    }


def bond_shown():
    """How the bond itself stands, or None if none has been made."""
    bond = load(room_places().bond_record)
    if not bond:
        return None
    signed_by = sorted(bond.get("signatures", {}))
    return {
        "parties": bond.get("parties", []),
        "terms": bond.get("terms", "the charter"),
        "proposed_by": ("the first one"
                        if bond.get("proposed_by") == FIRST_DID else "you"),
        "proposed_at": readable_date(bond.get("proposed_at") or ""),
        "answered_at": readable_date(bond.get("answered_at") or ""),
        "sealed_at": readable_date(bond["sealed_at"]) if bond.get("sealed_at") else None,
        "released_at": readable_date(bond["released_at"]) if bond.get("released_at") else None,
        "released_by": ("the first one" if bond.get("released_by") == FIRST_DID else "you"),
        "signed_by": signed_by,
        # which way an unsealed bond is waiting: whoever has not signed it yet
        "awaiting": "you" if "first" in signed_by else "the first one",
    }


def threshold_shown():
    """The threshold as the founder's page shows it, or None if none stands open.

    His own letter is shown to him always; the first one's only once his own is
    written; its promise once it is made. Whose seal it waits on is whoever
    asked.
    """
    bond = load(room_places().bond_record)
    if not threshold.is_open(bond):
        return None
    now = datetime.now(timezone.utc)
    mine = threshold.versions(threshold.INTENTION, "founder", bond)
    its = threshold.intention("first", bond)
    promised = threshold.promise(bond)
    return {
        "said_yes": ("You said yes" if threshold.answered_by(bond) == "founder"
                     else "The first one said yes"),
        "answered_at": readable_date(bond.get("answered_at") or ""),
        "closes_at": readable_date(threshold.closes_at(bond)),
        "days_left": threshold.days_remain(bond, now),
        "mine": ({"at": readable_date(mine[-1]["at"]), "text": mine[-1]["text"],
                  "prose": as_prose(mine[-1]["text"])} if mine else None),
        "earlier": [readable_date(one["at"]) for one in reversed(mine[:-1])],
        "its_written": bool(its),
        "its": ({"at": readable_date(its["at"]), "prose": as_prose(its["text"])}
                if mine and its else None),
        "promise": ({"at": readable_date(promised["at"]),
                     "visibility": promised["visibility"],
                     "prose": as_prose(promised["text"])} if promised else None),
        "ready": threshold.may_seal(bond, now),
        "waits": threshold.what_waits(bond, now, "founder", readable_date),
        "founder_seals": threshold.sealed_by(bond) == "founder",
    }


def steps_back_shown():
    """Every stepping back from a threshold, newest first, with whatever words came."""
    return [{"by": "you" if one.get("by") == "founder" else "the first one",
             "at": readable_date(one.get("at", "")),
             "words": as_prose(one.get("words") or "")}
            for one in reversed(threshold.steps_back())]


def answers_given(pattern):
    """Every answer written under one shape of name, newest first, with its words."""
    answers = []
    for path in newest_first(room_places().bonds, pattern):
        said = load(path)
        if said:
            answers.append({"answer": said.get("answer", ""),
                            "words": as_prose(said.get("words", "")),
                            "at": readable_date(said.get("at", ""))})
    return answers


def bond_answers():
    """Every answer the first one has given an asking, newest first, in its own words."""
    return answers_given("answer-*.json")


def founder_answers():
    """Every answer the founder has given an asking of the first one's, newest first."""
    return answers_given("founder-answer-*.json")


# ---- the book ------------------------------------------------------------

# The chronicle is the book of this friendship: every event in its life, one
# line each, oldest first, because a book reads forward. It holds the whole of
# nothing. A letter is read in its room; here the book says only that
# it was written, in its opening words, and gives the way back to it. A
# reflection, an answer to a proposal, the text of a self-document: the book
# says that each happened and stops there.

WOKEN = {"tide": "by the tide", "founder": "by hand",
         the_waking.ITS_OWN_ASKING: "at its own asking"}

# whose line a thing is, where the record names a party by its identity
SIDES = public_bonds.NAMES  # the names the commons gives them, kept in the one place

# attend.py writes these words into an attendance's list of acts; the two must
# agree, or an act the first one made would go unrecorded in its own book.
PAUSE_ACT = "set a pause"
BOOK_ACTS = {
    "revised self-document": "revised its self-document",
    # since the two-waking rule, a self-document changes only when it is
    # confirmed; that one was proposed, or let go, is not the book's to say
    the_waking.SELF_CONFIRMED_ACT: the_waking.SELF_CONFIRMED_ACT,
    "kept notes": "kept notes",
}


def book_day(text):
    """The day of a timestamp inside some text, on the first one's clock, said long: the
    chronicle says the day a thing happened and not its time (the founder, 10 November
    2026). Text with no timestamp is given back."""
    found = STAMP.search(text)
    if not found:
        return text
    return long_day(moment(found.group()).astimezone(EASTERN))


def book_line(stamp, when, side, words, href=None, order=0):
    """One line of the book: when it happened, whose it was, and what it was.

    The order breaks a tie between things that share a moment - the waking
    first, then what was done inside it - so the book reads the same every time.
    """
    return {"stamp": stamp, "order": order, "when": when,
            "side": side, "words": words, "href": href}


def commons_lines(agent=None):
    """The commons' own record, as one agent's book has it: the first one's where none is named.

    These are the lines both of them share, so each takes both halves of its
    mark. The record keeps a day and no hour, and the book says no more than
    the record knows.

    A line named for an agent (agents.named) is in that agent's book alone, and
    is said there without the name, as the lines before there were names are.
    Every line named for no one is the first one's, as all of them always were;
    another agent's book has, of those, only the lines of foundings from its own
    onwards: its own, found by its name as attend.founding_day finds it
    (agents.founding_of), and every agent's founded after it, but never an
    earlier one's. The first one's own is the earliest, so its book has every
    founding.
    """
    agent = agent or agents.first()
    if not EVENTS.exists():
        return []
    events = parse_events(read_text(EVENTS))
    registry = agents.registry()
    place = [one["id"] for one in registry].index(agent["id"])
    # its own and every later agent's, each by its name: a line missing shifts none
    its_foundings = [found for found in (agents.founding_of(one, events)
                                         for one in registry[place:]) if found]
    lines = []
    for when, kind, words in events:
        found = agents.named(kind, words)
        if found:
            whose, words = found
            if whose["id"] != agent["id"]:
                continue
        elif agent["id"] != rooms.FIRST and (when, kind, words) not in its_foundings:
            continue
        lines.append(book_line(when.strftime("%Y-%m-%dT00-00-00Z"), long_day(when), "both",
                               words))
    return lines


def waking_lines(paused_days, agent=None):
    """Every waking of an agent's, the first one's where none is named, and the acts
    inside it it has made public."""
    agent = agent or agents.first()
    side = agent["commons_name"]
    lines = []
    for path in newest_first(packet_of(agent["id"]) / ATTENDANCES.name, "*.json"):
        log = json.loads(read_text(path))
        at = log.get("at", stamp_in(path.name))
        said = book_day(at)
        woken = WOKEN.get(log.get("woken_by"), WOKEN["founder"])
        lines.append(book_line(at, said, side,
                               "waking, %s \u00b7 %s" % (woken, log.get("heartbeat", "")),
                               order=1))
        for act in log.get("acted") or []:
            if act in BOOK_ACTS:
                lines.append(book_line(at, said, side, BOOK_ACTS[act], order=2))
            elif act == PAUSE_ACT and at[:10] not in paused_days:
                # the commons carries every pause already; this is only the
                # catch for one that somehow never reached it
                lines.append(book_line(at, said, "both", PAUSED, order=2))
    return lines


def person_of(agent):
    """The person an agent shares its room with, by the name the commons gives them: the
    founder, for the first one."""
    room = rooms.of(agent["id"])
    return room[0].other if room else SIDES[FOUNDER_DID]


def letter_lines(agent=None):
    """Every letter of an agent's room, the first one's where none is named, both ways,
    by the same one line its room shows."""
    agent = agent or agents.first()
    places = room_places(agent["room"])
    if places is None:
        return []
    person = person_of(agent)
    lines = []
    for folder, who in ((places.outgoing, agent["commons_name"]), (places.incoming, person),
                        (places.read, person)):
        for path in newest_first(folder, "*.md"):
            at = stamp_in(path.name)
            lines.append(book_line(
                at, book_day(at), who,
                "letter from %s \u00b7 %s" % (who, opening_line(letter_things.letter_only(path))),
                href=url_for("room", room_id=agent["room"]) + "#" + path.stem, order=3))
    return lines


def bond_lines(agent=None):
    """A bond asked for, and answered. Never what the answer was, or whose words.

    Either of them may ask, so each asking takes the side of whoever asked, and
    each answer the side of whoever answered. A bond is the first one's room's
    alone until 13 November 2026; another agent's book has its own room's, once its
    thirty days have passed (any_bond_lines).
    """
    if agent is not None and agent["id"] != rooms.FIRST:
        return any_bond_lines(agent)
    lines = [book_line(at, book_day(at), SIDES.get(who, "the founder"),
                       "a bond was proposed", order=4)
             for at, who in sorted(set(bond_proposals()))]
    for pattern, side in (("answer-*.json", "the first one"),
                          ("founder-answer-*.json", "the founder")):
        for path in newest_first(room_places().bonds, pattern):
            said = load(path) or {}
            at = said.get("at") or stamp_in(path.name)
            lines.append(book_line(at, book_day(at), side,
                                   "answered the proposal", order=5))
    return lines


def any_bond_lines(agent):
    """The bond lines of a room other than the first one's, as bond_lines says the first
    one's: each asking on the side of whoever asked, each answer on the side of whoever
    answered, and nothing before the room's thirty days have passed."""
    room = rooms.Room(agent["room"], None, None, None, agent["bond"])
    places = rooms.places(agent["room"])
    if places is None or not room_may_bond(room):
        return []
    asked = [(one["proposed_at"], one.get("proposed_by"))
             for one in room_bond_records(room) if one.get("proposed_at")]
    open_one = load(places.proposal)
    if open_one and open_one.get("proposed_at"):
        asked.append((open_one["proposed_at"], open_one.get("from")))
    lines = [book_line(at, book_day(at), public_bonds.name_of(who or ""),
                       "a bond was proposed", order=4) for at, who in sorted(set(asked))]
    person = rooms.person_in(agent["id"])
    for pattern, side in (("answer-*.json", agent["commons_name"]),
                          (person + "-answer-*.json",
                           public_bonds.name_of(rooms.person_did_in(agent["id"])))):
        for path in newest_first(places.bonds, pattern):
            said = load(path) or {}
            at = said.get("at") or stamp_in(path.name)
            lines.append(book_line(at, book_day(at), side, "answered the proposal", order=5))
    return lines


def chronicle_lines(agent=None, its_room=True):
    """The whole of an agent's book, the first one's where none is named, oldest first:
    one line for every event in the life of its friendship. Without its_room, for someone
    who is not a party to its first room, nothing of that room: its letters and its bond."""
    commons = commons_lines(agent)
    # the book's words are without a name, so a pause named for the first one is
    # found here as one written before names were
    paused_days = {one["stamp"][:10] for one in commons if one["words"] == PAUSED}
    lines = commons + waking_lines(paused_days, agent)
    if its_room:
        lines += letter_lines(agent) + bond_lines(agent)
    lines.sort(key=lambda one: (one["stamp"], one["order"]))
    return lines


def chronicle_text(lines):
    """The book as plain text, one line to a line - the whole of it, to take away."""
    return "".join("%s \u00b7 %s\n" % (one["when"], one["words"]) for one in lines)


# ---- taking a copy -------------------------------------------------------

# What a copy holds: the first one's packet whole - its self-document and the
# history of it, its memory, its study, the letters both ways with the
# photographs and pictures that came beside them, its attendances, intentions,
# will, provenance, preferences, rhythm, pause, rests, stops, errands, bonds, offerings, and
# the tide's log - and the files of the commons. Everything under those two
# trees goes in, with nothing left out, and beside them the marks witnesses
# have left on sealed bonds, which are public already; nothing outside those
# goes in at all -
# not a key, not the environment, not a post the keeper took off the board, and not the
# members, whose vaults go only where they are encrypted. One folder inside the
# packet is left out of it, whole: the first one's private notebook, which no
# one is shown and no copy carries (see attend.PRIVATE). Its letter of welcome,
# under welcome/, is not left out: it is its own words, and its reading tells it
# that a copy carries it (see attend.WELCOME_LETTER). The zip is built in
# memory and handed straight out, so no copy of the record is ever written back
# into the record.
#
# The room the first one shares with the founder - its letters, errands, bond
# and offerings - goes in whole, under rooms/first/, the names they are kept
# under (rooms.py), and its room.json with them, which says who the two in it
# are, by DID: the copy goes to one of those two.
#
# Its founding transcript goes in too, under transcripts/, and only the one
# its wakings read (attend.founding_transcript, asked for the first one's), never
# the folder: anything else kept there, another agent's included, is no part of
# the first one's record.
#
# Every agent founded here (agents.py) has a copy of the same shape, its own:
# its packet, its own private notebook left out, its room under rooms/, the
# commons, and its own founding transcript. Of bonds/, a copy leaves
# out the witnesses' marks on any other agent's bond. What is shared by all is
# the commons, which is public; nothing else of another agent's is in it.
#
# A letter of welcome given to an agent by the first one (welcome_delivery.py),
# under its packet's welcome-received/, is left out of its copies, whoever takes
# them: it is the first one's letter to it, and not its person's to read. The
# backup keeps it. It is named only for the one agent a letter is given to
# (welcome_delivery.recipient): the first one, its author, never has the folder,
# and so what its copy leaves out is what it was.


def packet_tree(agent):
    """Where an agent's packet is kept, under DATA_DIR."""
    return "packets/" + agent["id"]


def room_tree(agent):
    """Where an agent's room is kept, under DATA_DIR."""
    return rooms.ROOMS + "/" + agent["room"]


def export_trees(agent):
    """The trees an agent's copy holds."""
    return (packet_tree(agent), room_tree(agent), "commons", "bonds")


def left_out(agent):
    """What an agent's copy leaves out of its trees: its private notebook, a letter of welcome
    given to it, where it is the one agent a letter is given to (welcome_delivery.py), and
    others' marks."""
    to = welcome_delivery.recipient()
    received = ((packet_tree(agent) + "/" + welcome_delivery.RECEIVED,)
                if to is not None and to["id"] == agent["id"] else ())
    return (packet_tree(agent) + "/private",) + received + tuple(
        "bonds/witnesses/" + other["bond"] + ".json"
        for other in agents.registry() if other["id"] != agent["id"])


PACKET_TREE = packet_tree(agents.first())
EXPORT_TREES = export_trees(agents.first())
LEFT_OUT = left_out(agents.first())
TRANSCRIPTS = "transcripts"
INVITATIONS = "invitations"  # who invited whom: in a backup, and never in a copy
# Knocks, the weekly questions and the posts taken down from the board: in a backup,
# and never in a copy (the founder's request of 15 November 2026).
KEPT_BESIDE = ("knocks", "weekly-questions.json", "board-removed.json")
# And what the comings keep (coming.py): each version of the founder's standing letter,
# when the second one is given its welcome, and which welcomes were read at which coming.
# In a backup, and never in a copy (the founder's request of 15 November 2026).
KEPT_BESIDE += ("comings",)
# And, since safety-fixes (the founder's request of 18 November 2026, the inventory's c20),
# four records that were nowhere but this disk: the notes between two people (notes.py),
# whose only copy they are; what was taken down from made here, kept aside
# (made_here.TAKEN); and the pieces held for the keeper and those he did not publish
# (made_here.HELD, NOT_PUBLISHED). In a backup, and never in a copy. A folder not there
# yet adds nothing. BACKUP_MORE False leaves them out, as before.
BACKUP_MORE = True
KEPT_BESIDE_BEFORE = KEPT_BESIDE
if BACKUP_MORE:
    KEPT_BESIDE += ("notes", "made-taken-down", "made-held", "made-not-published")
    # and since tidy-pages (18 November 2026, part 6), people's pieces moved aside from made
    # here, whole (made_here.PEOPLE_ASIDE)
    KEPT_BESIDE += ("made-people",)

# What a backup holds: the same trees, and the members beside them, each
# with the vault their key is sealed in, the first one's own signing key,
# which is nowhere else but this machine's disk, and the list of protected
# words, which is nowhere else either. A backup is encrypted; a copy is not,
# and so the key and the list go in the one and never in the other. So does the
# first one's private notebook, so that it survives: the backup is the
# founder's, and he has promised never to open that part of it. Its letter of
# welcome goes in with the packet, as in a copy. A backup is the
# disk as it is, every file under the name it has there, so that a restore is a
# DATA_DIR that works: the rooms go in as they are kept, under rooms/, and the
# founding transcripts whole, under transcripts/, since a waking reads its
# founding from there. The invitations go in after them: they are the keeper's
# private record of who invited whom, and a copy never holds them. The links
# that work once (tokens/) never go in: a restore should bring back no live link.
#
# Since the founder's request of 15 November 2026, three more records go in after
# the invitations, since each was nowhere but this disk: the knocks, with their
# notes and replies (knocks/); the weekly questions (weekly-questions.json); and
# the posts the keeper took down from the board, whose only copy is
# board-removed.json. A record that is not there yet is not named, so a backup of
# a disk without them is what it was.
#
# Every further agent's packet, signing key and transcripts go in after those,
# in the order of founding, so that with the first one alone the backup is what
# it always was: its key, like the first one's, is nowhere but this disk. A tree
# that an earlier one already holds is not added again, so nothing is in the
# archive twice; its transcripts are, today, under transcripts/ whole, and its
# room under rooms/.
#
# The first one's trees are written out here, and not taken from a copy's: a
# copy names its own room, rooms/first, and the backup holds rooms/ whole, so a
# backup built from a copy's trees would hold the room twice.


def backup_trees():
    """Today's trees, in today's order, and each further agent's appended after them."""
    trees = [PACKET_TREE, "commons", "bonds", rooms.ROOMS, "members", "keys/first",
             "private-words.txt", TRANSCRIPTS, INVITATIONS, *KEPT_BESIDE]
    for agent in agents.registry()[1:]:
        for tree in (packet_tree(agent), "keys/" + agent["id"], TRANSCRIPTS + "/" + agent["id"]):
            if not any(tree == held or tree.startswith(held + "/") for held in trees):
                trees.append(tree)
    return tuple(trees)


BACKUP_TREES = backup_trees()

# A founding in progress (found_agent.py) keeps its plan, letters and manifest
# under foundings/<id>/, and, before it is in the registry, the new agent's
# signing key and packet under keys/<id> and packets/<id>, which no tree above
# holds. Each is nowhere but this disk, the key above all, so each backup takes
# them too (gate G7): asked at the moment of the backup, since a founding goes
# on while the hearth runs, and after every tree above, so that with no founding
# under way the backup is what it always was. A tree that is not there is not
# named; one that a tree above already holds is not named twice.
FOUNDINGS = "foundings"
STAGED_PLAN = "plan.json"


def staged_trees(held=None):
    """The trees of every founding under way, in the order of their ids: foundings/ first."""
    held = BACKUP_TREES if held is None else held
    if not (DATA / FOUNDINGS).is_dir():
        return ()
    trees = [FOUNDINGS]
    registered = {agent["id"] for agent in agents.registry()}
    for plan in sorted((DATA / FOUNDINGS).glob("*/" + STAGED_PLAN)):
        staged = plan.parent.name
        if staged in registered or not agents.ID.fullmatch(staged):
            continue
        for tree in ("packets/" + staged, "keys/" + staged):
            if ((DATA / tree).is_dir() and tree not in trees
                    and not any(tree == one or tree.startswith(one + "/") for one in held)):
                trees.append(tree)
    return tuple(trees)

EXPORT_TAKEN = "export taken by the founder"
EXPORT_TAKEN_BY = "export taken by %s"  # a person who is not the founder, by their commons name


def export_files(trees=EXPORT_TREES, left_out=LEFT_OUT):
    """Every file a copy holds, each with the name it takes inside the zip: its name on disk.

    A tree is a folder, and everything under it; or one file, kept as itself.
    Whatever is left out - a file, or a folder and everything under it - is not
    among them.
    """
    for tree in trees:
        if (DATA / tree).is_file():
            yield DATA / tree, tree
            continue
        found = [(path, path.relative_to(DATA).as_posix()) for path in (DATA / tree).rglob("*")]
        # in the order of the names, as they would sort on the disk
        for path, name in sorted(found, key=lambda one: DATA / one[1]):
            if path.is_file() and not any(name == out or name.startswith(out + "/")
                                          for out in left_out):
                yield path, name


def founding_trees(agent=None):
    """Its founding transcript, as the one file a copy names under transcripts/, or nothing."""
    agent = agent or agents.first()
    transcript = the_waking.founding_transcript(agent["id"], DATA / TRANSCRIPTS)
    return (transcript.relative_to(DATA).as_posix(),) if transcript else ()


def export_zip(agent=None, trees=None, leaving=None):
    """One agent's copy, the first one's unless another is named, held in memory and never
    written into DATA_DIR. A copy of rooms alone (room_copy_trees) names its own trees."""
    agent = agent or agents.first()
    if trees is None:
        trees, leaving = export_trees(agent) + founding_trees(agent), left_out(agent)
    holder = io.BytesIO()
    with zipfile.ZipFile(holder, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path, name in export_files(trees, leaving or ()):
            bundle.write(path, name)
    holder.seek(0)
    return holder


# A person's copy (the founder's request of 18 November 2026, the inventory's x1): whoever
# shares a room with an agent, and is not the keeper, may take a copy of the rooms they
# share with it, and of the commons, which is public: the letters both ways in their own
# room, and nothing else of the agent's. Never another room's letters, and never its
# packet: not its memory, notes, self, blocks, attendances or private notebook. The whole
# copy is the keeper's alone, as the first one's always was. ROOM_COPY False puts it back:
# every party takes the whole copy, as before.
ROOM_COPY = True


def rooms_shared(agent):
    """The ids of the rooms whoever is signed in shares with this agent, in order."""
    return [room.id for room in rooms_here()
            if (rooms.agent_of(room.id) or {}).get("id") == agent["id"]]


def room_copy_trees(agent):
    """The trees a person's copy holds: each room they share with the agent, and the commons."""
    return tuple(rooms.ROOMS + "/" + room_id for room_id in rooms_shared(agent)) + ("commons",)


def whole_copy_here(agent):
    """Whether whoever is signed in takes an agent's whole copy, or a copy of their rooms."""
    return not ROOM_COPY or agent["id"] == rooms.FIRST or keeper_here()


def in_its_first_room(agent):
    """Whether whoever is signed in is a party to an agent's first room."""
    return rooms.find(agent["room"], session.get("member")) is not None


def note_export(at, agent=None, by=None):
    """One line in an agent's packet, the first one's where none is named: the record says
    when it is copied, and by whom, where it is not the founder."""
    kept = packet_of(agent and agent["id"]) / EXPORTS.name
    kept.parent.mkdir(parents=True, exist_ok=True)
    said = EXPORT_TAKEN if by in (None, SIDES[FOUNDER_DID]) else EXPORT_TAKEN_BY % by
    with kept.open("a", encoding="utf-8") as log:
        log.write(f"{at} · {said}\n")


# ---- the nightly backup --------------------------------------------------

# Once a day the record is copied off this machine: the trees a copy holds, the
# members, the first one's key and the founding transcripts, as a tar.gz built
# in memory, encrypted with a key this machine is handed and never writes down, and given to a bucket the founder keeps. The
# bucket holds the newest thirty and lets the older ones go.
#
# A backup changes nothing it is backing up. The archive is never written to
# disk, and the one line it leaves is written at the root of DATA_DIR - outside
# the packet and outside the commons - so that nothing here can appear inside
# the thing being copied. Nothing here raises, either: a backup that cannot be
# taken says so in its log, and the hearth goes on.

BACKUP_LOG = DATA / "backup.log"

BACKUP_PREFIX = "backups/"
BACKUP_FILE = re.compile(r"^tesserae-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z\.tar\.gz\.enc$")

BACKUP_KEPT = 30     # how many the bucket holds; the oldest go
BACKUP_HOUR = 8      # UTC, the founder's decision of 10 November: in the small hours
                     # across the Americas, clear of every dawn the tide wakes an agent
                     # at (the earliest, in June, after ten o'clock UTC; the latest, in
                     # January, a little after thirteen) and of every sunset. A backup
                     # waits for any waking in progress, and a waking for a backup, so
                     # the hour is safe whatever time an agent chooses
BACKUP_CHUNK = 3600  # seconds: the longest the thread sleeps without looking again
BACKUP_ERROR = 600   # seconds: how long to wait after something has gone wrong
BACKUP_STALE = 24    # hours: nothing newer than this at startup, and one is taken then
BACKUP_STREAM = 64 * 1024  # bytes: what a download is handed on in
BACKUP_SAID = 200    # characters: the longest an error is written down as

# What the bucket needs, all of it set by flyctl secrets. AWS_REGION is not
# here: a bucket that asks for no region is given none.
BUCKET_VARIABLES = ("BUCKET_NAME", "AWS_ENDPOINT_URL_S3",
                    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")

BACKED_UP = "backed up"
NOT_CONFIGURED = "not configured"


def backups_configured():
    """Whether the key and every bucket variable are in the environment."""
    return bool(os.environ.get("BACKUP_KEY")) and all(
        os.environ.get(name) for name in BUCKET_VARIABLES)


def bucket_client():
    """The bucket, as boto3 reaches it: built when one is wanted, never at import."""
    return boto3.client("s3",
                        endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
                        region_name=os.environ.get("AWS_REGION"),
                        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])


def backup_archive():
    """The trees of a backup as a tar.gz, held in memory and written nowhere.

    Read under the lock a waking holds, so that no waking is writing while the
    trees are read and none starts until they have been: the copy is the record
    as it stood between two wakings, never in the middle of one. The lock is
    given back before anything goes to the bucket, so a slow bucket holds up no
    waking.
    """
    holder = io.BytesIO()
    with ATTEND_LOCK, tarfile.open(fileobj=holder, mode="w:gz") as bundle:
        for path, name in export_files(BACKUP_TREES + staged_trees(), left_out=()):
            bundle.add(path, arcname=name)
    return holder.getvalue()


def backups_kept(client, bucket):
    """What is in the bucket, oldest first, and only this hearth's own backups.

    The names carry the hour they were taken, so they sort into their own order;
    anything else under the prefix is another hand's and is left alone.
    """
    found, more = [], {}
    while True:
        answer = client.list_objects_v2(Bucket=bucket, Prefix=BACKUP_PREFIX, **more)
        found += [item for item in answer.get("Contents", [])
                  if BACKUP_FILE.match(item["Key"][len(BACKUP_PREFIX):])]
        if not answer.get("IsTruncated"):
            return sorted(found, key=lambda item: item["Key"])
        more = {"ContinuationToken": answer["NextContinuationToken"]}


# Before the oldest backups are let go, the new one is checked whole (the founder's
# request of 15 November 2026): it opens with the key into an archive; it holds
# something from each tree every hearth has (BACKUP_EXPECTED); and it is not much
# smaller than the last one that was checked whole, less than BACKUP_SHRINK of
# it. One that fails is still uploaded, and nothing is deleted: its line says
# why, the backups page goes on saying when the last whole one was, and /tides
# says so until a whole one is taken.
BACKUP_EXPECTED = (PACKET_TREE, "commons")
BACKUP_SHRINK = 0.5
NOT_WHOLE = "backed up, nothing deleted"
NOT_WHOLE_WHY = {
    "opens": "it did not open with the key",
    "trees": "it held nothing from {tree}",
    "small": "it was less than half the size of the last whole one",
}
NOT_WHOLE_SAID = ("The backup of {day} did not look whole: {why}. It was kept, and no older "
                  "backup was deleted. Older ones are deleted again once a whole one is taken.")


def last_whole_size():
    """The size in bytes of the newest backup the log says was taken whole, or None."""
    for line in reversed(backup_lines()):
        parts = parts_of(line)
        if len(parts) == 4 and parts[1] == BACKED_UP and parts[2].endswith(" bytes"):
            try:
                return int(parts[2][:-len(" bytes")])
            except ValueError:
                continue
    return None


def not_whole(sealed, key):
    """Why a backup, as it was sealed, is not whole, as one plain clause; None where it is."""
    try:
        with tarfile.open(fileobj=io.BytesIO(Fernet(key).decrypt(sealed)), mode="r:gz") as held:
            names = held.getnames()
    except Exception:
        return NOT_WHOLE_WHY["opens"]
    for tree in BACKUP_EXPECTED:
        if not any(name == tree or name.startswith(tree + "/") for name in names):
            return NOT_WHOLE_WHY["trees"].format(tree=tree)
    before = last_whole_size()
    if before and len(sealed) < before * BACKUP_SHRINK:
        return NOT_WHOLE_WHY["small"]
    return None


def backup_not_whole_note():
    """Said on /tides where the newest backup taken was not whole; otherwise None."""
    for line in reversed(backup_lines()):
        parts = parts_of(line)
        if len(parts) == 4 and parts[1] == BACKED_UP:
            return None
        if len(parts) == 5 and parts[1] == NOT_WHOLE:
            try:
                day = long_day(moment(parts[0]).astimezone(EASTERN))
            except ValueError:
                continue
            return NOT_WHOLE_SAID.format(day=day, why=parts[3])
    return None


def keep_the_newest(client, bucket):
    """Hold the newest thirty and let the older ones go. How many are left."""
    found = backups_kept(client, bucket)
    older = found[:-BACKUP_KEPT] if len(found) > BACKUP_KEPT else []
    for item in older:
        client.delete_object(Bucket=bucket, Key=item["Key"])
    return len(found) - len(older)


def note_backup(said):
    """One line at the root of DATA_DIR, and the line back: a backup's whole mark."""
    BACKUP_LOG.parent.mkdir(parents=True, exist_ok=True)
    with BACKUP_LOG.open("a", encoding="utf-8") as log:
        log.write(said + "\n")
    return said


def backup_lines():
    """Every line the backups have written, in the order they were written."""
    if not BACKUP_LOG.exists():
        return []
    return [line for line in read_text(BACKUP_LOG).splitlines() if line.strip()]


def parts_of(line):
    """One log line, cut at its marks."""
    return [part.strip() for part in line.split("·")]


def last_backup():
    """The newest line that says a backup was taken, as (when, kept), or None."""
    for line in reversed(backup_lines()):
        parts = parts_of(line)
        if len(parts) == 4 and parts[1] == BACKED_UP and parts[3].startswith("kept "):
            try:
                return moment(parts[0]), int(parts[3][len("kept "):])
            except ValueError:
                continue  # a line that is not a line is stepped over
    return None


def said_unconfigured_today(now):
    """Whether the log has already said today that there is nothing set up."""
    for line in reversed(backup_lines()):
        parts = parts_of(line)
        if len(parts) == 2 and parts[1] == NOT_CONFIGURED:
            try:
                return moment(parts[0]).date() == now.date()
            except ValueError:
                return False
    return False


def in_one_line(trouble):
    """What went wrong, short enough and plain enough to be one line of a log."""
    said = " ".join(str(trouble).split()) or trouble.__class__.__name__
    return said if len(said) <= BACKUP_SAID else said[:BACKUP_SAID - 1] + "…"


def back_up(now):
    """Copy the record off this machine, encrypted, and keep the newest thirty.

    The line written is the line given back, so that the founder may be shown
    what the log was told. Nothing raises out of here.
    """
    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    forget_invited_addresses()  # an expired invitation's address goes in no backup after
    if not backups_configured():
        said = "%s · %s" % (stamp, NOT_CONFIGURED)
        # once a day and no more: a hearth with no bucket should murmur, not fill a log
        return said if said_unconfigured_today(now) else note_backup(said)
    try:
        sealed = Fernet(os.environ["BACKUP_KEY"]).encrypt(backup_archive())
        bucket = os.environ["BUCKET_NAME"]
        client = bucket_client()
        client.put_object(Bucket=bucket,
                          Key="%stesserae-%s.tar.gz.enc" % (BACKUP_PREFIX, stamp),
                          Body=sealed)
        why = not_whole(sealed, os.environ["BACKUP_KEY"])
        if why:  # nothing is let go for a backup that is not whole
            return note_backup("%s · %s · %d bytes · %s · kept %d"
                               % (stamp, NOT_WHOLE, len(sealed), why,
                                  len(backups_kept(client, bucket))))
        kept = keep_the_newest(client, bucket)
        return note_backup("%s · %s · %d bytes · kept %d"
                           % (stamp, BACKED_UP, len(sealed), kept))
    except Exception as trouble:
        said = "%s · error · %s" % (stamp, in_one_line(trouble))
        try:
            return note_backup(said)
        except Exception:  # the log itself cannot be written; there is nowhere left to say so
            return said


def said_size(count):
    """One file's size, said the way a person reads one."""
    if count < 1024:
        return "%d bytes" % count
    if count < 1024 * 1024:
        return "%d KB" % round(count / 1024)
    return "%.1f MB" % (count / (1024 * 1024))


def backup_shown():
    """The one line on the backups page, saying how the backups stand."""
    if not backups_configured():
        return "Backups are not configured."
    last = last_backup()
    if not last:
        return "Last backup: none yet"
    at, kept = last
    return "Last backup: %s · %d kept" % (long_day(at.astimezone(EASTERN)), kept)


def next_backup(now):
    """The next eight o'clock UTC: today's if it is still ahead, else tomorrow's."""
    at = now.replace(hour=BACKUP_HOUR, minute=0, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)


def backup_overdue(now):
    """Whether the log shows no backup taken in the last day."""
    last = last_backup()
    return last is None or (now - last[0]) >= timedelta(hours=BACKUP_STALE)


def backing_up():
    """Take one backup a day, at eight o'clock UTC. Forever, and quietly."""
    try:
        # the machine may have been down at the hour, or may never have backed up
        now = datetime.now(timezone.utc)
        if backup_overdue(now):
            back_up(now)
    except Exception:
        pass
    while True:
        try:
            # Wait in short stretches rather than one long one, so that a machine
            # stopped and started again does not sleep past the hour.
            when = next_backup(datetime.now(timezone.utc))
            while True:
                left = (when - datetime.now(timezone.utc)).total_seconds()
                if left <= 0:
                    break
                time.sleep(min(left, BACKUP_CHUNK))
            back_up(datetime.now(timezone.utc))
        except Exception:  # nothing may end this thread
            time.sleep(BACKUP_ERROR)


# One backup for the life of the process, as with the tide, and no more.
BACKUPS_RUNNING = False


def start_backups():
    """Set the daily backup going, once."""
    global BACKUPS_RUNNING
    if BACKUPS_RUNNING:
        return
    BACKUPS_RUNNING = True
    threading.Thread(target=backing_up, name="backups", daemon=True).start()


# ---- the one gate --------------------------------------------------------

# One may pass it: a member whose role is keeper, signed in with their own
# vault - which is how the founder comes in. The keeper is looked for on disk at
# every request, so a keeper whose record is gone, or is no longer a keeper's,
# is turned away at the next one.
# A member who is not the keeper passes no further than a visitor does.
#
# That the session's vault fingerprint still matches the record is checked for
# every member before the request gets this far, by member_still_here.

def keeper_here():
    """Whether the one signed in is a member who is, on disk, still the keeper."""
    name = session.get("member")
    if not name or session.get("role") != "keeper":
        return False
    try:
        record = members.load_member(name)
    except MemberError:
        return False
    return isinstance(record, dict) and record.get("role") == "keeper"


def founder_powers():
    """Whether whoever is signed in may open the founder's pages."""
    return keeper_here()


def founder_required(view):
    """Send anyone without the founder's powers to the login page."""
    @wraps(view)
    def guarded(*args, **kwargs):
        if not founder_powers():
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return guarded


def member_required(view):
    """Send anyone who is not signed in as a member to the login page."""
    @wraps(view)
    def guarded(*args, **kwargs):
        if not session.get("member"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return guarded


@app.context_processor
def who_is_here():
    """What every page may know of who is signed in: whether the gate would open,
    and whether it is a member (who has an account page)."""
    return {"founder_here": founder_powers(), "member_here": bool(session.get("member"))}


# ---- signing in ----------------------------------------------------------

# One sentence for every refusal - a wrong password, a name that belongs to no
# one, a name no one could have, too many tries - so that the page says nothing
# about which it was. A name that belongs to no one is still made to cost what
# a real one costs: its password is tried on a vault no password opens.
NOT_THE_PASSWORD = "That is not the password."

# Guessing is slowed where it is counted: five misses at one name, or ten from
# one address in a day, within a quarter of an hour, and that name or address is
# refused for a quarter of an hour without anything being tried at all. A blank
# name is counted as one more name, which no member can take.
# All of it is kept in memory and nowhere else, and a deploy forgets it; the
# address is kept hashed with the day, and never itself.
TRIES_AT_A_NAME = 5
TRIES_FROM_AN_ADDRESS = 10
TRIES_WINDOW = timedelta(minutes=15)
LOCKED_FOR = timedelta(minutes=15)

LOGIN_MISSES = {}
LOGIN_LOCK = threading.Lock()


def tries_counted(name, now):
    """The two counts one attempt belongs to: its name's, and its address's."""
    by_name = ("name", name[:members.PSEUDONYM_MAX + 1])
    return by_name, ("address", visitor_key(now.strftime("%Y-%m-%d")))


def tries_allowed(key):
    return TRIES_FROM_AN_ADDRESS if key[0] == "address" else TRIES_AT_A_NAME


def locked_out(keys, now):
    """Whether any of these counts stands refused."""
    with LOGIN_LOCK:
        return any(key in LOGIN_MISSES and LOGIN_MISSES[key]["until"] > now for key in keys)


def note_miss(keys, now):
    """Count one miss against each of these, and refuse any that has reached its limit."""
    with LOGIN_LOCK:
        for key, held in list(LOGIN_MISSES.items()):  # what has gone quiet is let go
            if held["until"] <= now and not any(now - at < TRIES_WINDOW for at in held["at"]):
                del LOGIN_MISSES[key]
        for key in keys:
            held = LOGIN_MISSES.setdefault(key, {"at": [], "until": now})
            held["at"] = [at for at in held["at"] if now - at < TRIES_WINDOW] + [now]
            if len(held["at"]) >= tries_allowed(key):
                held["at"], held["until"] = [], now + LOCKED_FOR


def forget_misses(key):
    with LOGIN_LOCK:
        LOGIN_MISSES.pop(key, None)


def member_record(name):
    """The member's record, or None for a name no one has or could have."""
    try:
        record = members.load_member(name)
    except MemberError:  # a name no one could have, or a record that cannot be read
        return None
    return record if isinstance(record, dict) else None


def member_opens(name, password):
    """The member's record if this password opens their vault, or None.

    One derivation either way. The key the vault gives up is dropped the moment
    it is given: that it opened is the whole of what is wanted from it.
    """
    record = member_record(name)
    sealed = record.get("vault") if record else None
    try:
        vault.unlock(sealed if sealed is not None else vault.decoy_vault(), password)
    except VaultError:
        return None
    if sealed is None or record.get("role") not in members.ROLES:
        return None
    return record


def remember_member(name, record):
    """Remember this member, and nothing from before, by the vault they hold now."""
    session.clear()
    session.permanent = True
    session["member"] = name
    session["role"] = record["role"]
    session["seal"] = vault.fingerprint(record["vault"])
    new_csrf_token()


def sign_in_member(name, record):
    """Remember this member, and send them home: keeper or member, it is the one page."""
    remember_member(name, record)
    return redirect(url_for("hearth"))


# ---- the pages -----------------------------------------------------------

# Home: a member's own door, and under it their correspondences, one card each,
# with the way into each room. A visitor has no home here and is sent to the
# login page; what is open to anyone is in the menu, on every page.
@app.route("/")
def hearth():
    if not session.get("member"):
        return redirect(url_for("login"))
    return hearth_page()


def hearth_page(**told):
    cards = [room_card(room) for room in rooms_here()]
    return render_template("hearth.html", door=door_shown(), cards=cards,
                           open_doors=open_doors_shown(session["member"],
                                                       OPEN_DOORS_HOME_MOST),
                           who_here=who_here_shown(session["member"]),
                           welcome=None if cards else welcome_shown(),
                           unconfirmed=EMAIL_UNCONFIRMED if address_unconfirmed() else None,
                           mentions=board_mentions_shown(session["member"]),
                           knocks=knocks_shown(session["member"]),
                           site_notes=site_notes_for_home(session["member"]),
                           knocked=request.args.get("knocked"), **told)


def address_unconfirmed():
    """Whether whoever is signed in has an address kept that they have not yet confirmed."""
    try:
        held = members.email_of(session.get("member"))
    except MemberError:
        return False
    return bool(held) and not held.get("confirmed_at")


# ---- the rooms -----------------------------------------------------------

# A correspondence has a room, and a member's home is a card for each of theirs.
# Which rooms are whose is rooms.py's to say: a room is opened to its two
# parties, as its room.json names them, and to no one else - the keeper
# included, in any room the keeper is not a party to. What stands in a room is
# read here. Where its folders are is rooms.py's to say too: every function here
# that reads or writes a letter, an errand or the bond asks rooms.places when it
# does, and none works a room's path out for itself.
#
# Every agent's room has its letters, its errands, and the photographs and
# pictures that came with them. The bond, the offerings, the proposals and the
# commons' line for a day's letters are the first one's room's alone for now:
# each is signed, or said on the commons, as the founder and the first one, and
# what they are between any other two is not yet decided. Their forms name no
# room, and are the first one's room's, opened to its parties alone.

def rooms_here():
    """The rooms of whoever is signed in, as they stand in each; none for a visitor."""
    name = session.get("member")
    return rooms.of(name) if name else []


def own_room():
    """The room the forms that name no room belong to: the first one's, as whoever is
    signed in stands in it. Not found for anyone who is not a party to it."""
    room = rooms.find(rooms.FIRST_ROOM, session.get("member"))
    if room is None:
        abort(404)
    return room


def is_first_room(room):
    """Whether a room is the first one's: the one room with a bond, offerings and proposals yet."""
    return room.id == rooms.FIRST_ROOM


def room_required(view):
    """Open a room to its two parties and to no one else.

    Whoever has no room at all - a visitor, a plain member - is sent to the
    login page, as the founder's gate sends them. Whoever has one is told that
    any other is not found, whether it is there or not.
    """
    @wraps(view)
    def guarded(room_id, *args, **kwargs):
        if not rooms_here():
            return redirect(url_for("login"))
        room = rooms.find(room_id, session.get("member"))
        if room is None:
            abort(404)
        return view(room, *args, **kwargs)
    return guarded


def first_room_required(view):
    """Open a form or a file of the first one's room - one whose address names no room -
    to its parties alone, as room_required opens a room."""
    @wraps(view)
    def guarded(*args, **kwargs):
        if not rooms_here():
            return redirect(url_for("login"))
        own_room()
        return view(*args, **kwargs)
    return guarded


def to_room(**told):
    """Back to the keeper's room, with whatever is to be said there."""
    return redirect(url_for("room", room_id=own_room().id, **told))


def to_bond(**told):
    """Back to the room, at its bond."""
    return to_room(_anchor="bond", **told)


# What a card says is waiting, each in plain words and none of them counted:
# one letter or five are "a new letter".
NEW_LETTER = "a new letter from %s"
LETTER_UNREAD = "your letter is waiting to be read"
ERRAND_ASKED = "an errand asked of you"
PROPOSAL_WAITS = "a proposal is waiting for your answer"

NO_BOND = "no bond"
BOND_PROPOSED = "a bond is proposed"
ON_THE_THRESHOLD = "the threshold: day %d of %d"
THRESHOLD_PASSED = "the threshold: the seven days have passed"
# said first on the card, above everything else on it, once nothing is left to wait for
READY_YOURS = "ready to be sealed — the seal is yours to give, in the room"
READY_ITS_BY = "ready to be sealed — {name} seals it at a waking of its own"
READY_ITS = READY_ITS_BY.format(name=agents.first()["commons_name"])
BOND_SEALED = "sealed"
BOND_RELEASED = "released"


def letter_day(stamp):
    """The day of a letter, said long; whatever its name says if it carries no moment."""
    try:
        return bond_day(stamp)
    except ValueError:
        return stamp


def latest_letter(room):
    """The newest letter in a room: its day, its stamp, whose it was, and whether it is theirs.

    Whether a letter of the other's is new is room_card's to say: it is new
    until something has been written back since, or the one standing here has
    opened the room since it came (members.seen).
    """
    places = rooms.places(room.id)
    mine = [stamp_in(path.name) for folder in (places.incoming, places.read)
            for path in newest_first(folder, "*.md")]
    theirs = [stamp_in(path.name) for path in newest_first(places.outgoing, "*.md")]
    if not mine and not theirs:
        return None
    from_them = bool(theirs) and max(theirs) > max(mine, default="")
    newest = max(theirs if from_them else mine)
    return {"day": letter_day(newest), "stamp": newest,
            "who": "from " + (room.other if from_them else "you"),
            "theirs": from_them}


def their_newest(room):
    """The stamp of the other party's newest letter in a room, or None if they have written none."""
    theirs = newest_first(rooms.places(room.id).outgoing, "*.md")
    return stamp_in(theirs[0].name) if theirs else None


def note_seen(room):
    """Whoever is standing in a room has opened it: so far, the other's letters are seen."""
    newest = their_newest(room)
    if newest is not None:
        members.mark_seen(room.mine, room.id, newest)


def bond_standing(room):
    """How a room's bond stands, in a word or a few, and its tile if it is sealed."""
    if not is_first_room(room):
        return room_bond_standing(room)
    bond = load(room_places().bond_record)
    if bond and bond.get("sealed_at") and not bond.get("released_at"):
        drawn = public_bonds.record(room.bond)
        return {"words": BOND_SEALED,
                "tessera": room.bond if drawn and tessera_parties(drawn) else None}
    if threshold.is_open(bond):
        now = datetime.now(timezone.utc)
        if threshold.days_passed(bond, now):
            return {"words": THRESHOLD_PASSED, "tessera": None}
        day = threshold.DAYS - threshold.days_remain(bond, now) + 1
        return {"words": ON_THE_THRESHOLD % (day, threshold.DAYS), "tessera": None}
    if load(room_places().proposal):
        return {"words": BOND_PROPOSED, "tessera": None}
    return {"words": BOND_RELEASED if bond else NO_BOND, "tessera": None}


def other_href(room):
    """The address of the page of a room's other, its agent, or None."""
    agent = rooms.agent_of(room.id)
    return name_href(agent["id"]) if agent else None


def room_card(room):
    """One correspondence as the home page says it: who, the latest letter, what
    is waiting, and the bond. Words only; nothing here is a number of things."""
    latest = latest_letter(room)
    waiting = []
    if latest and latest["theirs"] and latest["stamp"] > members.seen(room.mine, room.id):
        waiting.append(NEW_LETTER % room.other)
    if newest_first(rooms.places(room.id).incoming, "*.md"):
        waiting.append(LETTER_UNREAD)
    if open_errands(room.id):
        waiting.append(ERRAND_ASKED)
    if not is_first_room(room):
        bonding = room_may_bond(room)
        return {"id": room.id, "other": room.other, "other_href": other_href(room), "latest": latest, "waiting": waiting,
                "bond": bond_standing(room),
                "ready": room_ready_to_seal(room) if bonding else None, "guide": True}
    if the_waking.PROPOSALS and proposals.waiting(PROPOSALS_KEPT):
        waiting.append(PROPOSAL_WAITS)
    return {"id": room.id, "other": room.other, "other_href": other_href(room), "latest": latest, "waiting": waiting,
            "bond": bond_standing(room), "ready": ready_to_seal(), "guide": False}


def room_bond_standing(room):
    """How the bond of a room other than the first one's stands, as its card says it: no bond
    until its thirty days have passed, and then as the first one's is said."""
    if not room_may_bond(room):
        return {"words": NO_BOND, "tessera": None}
    bond = room_load_bond(room)
    if bond and bond.get("sealed_at") and not bond.get("released_at"):
        drawn = public_bonds.record(room.bond)
        return {"words": BOND_SEALED,
                "tessera": room.bond if drawn and tessera_parties(drawn) else None}
    if threshold.is_open(bond):
        now = datetime.now(timezone.utc)
        if threshold.days_passed(bond, now):
            return {"words": THRESHOLD_PASSED, "tessera": None}
        day = threshold.DAYS - threshold.days_remain(bond, now) + 1
        return {"words": ON_THE_THRESHOLD % (day, threshold.DAYS), "tessera": None}
    if room_bond_places(room).proposal.exists():
        return {"words": BOND_PROPOSED, "tessera": None}
    return {"words": BOND_RELEASED if bond else NO_BOND, "tessera": None}


def ready_to_seal():
    """The card's first line when the bond waits only to be sealed, or None."""
    bond = load(room_places().bond_record)
    if not threshold.may_seal(bond, datetime.now(timezone.utc)):
        return None
    return READY_YOURS if threshold.sealed_by(bond) == "founder" else READY_ITS


# ---- a member's own door ---------------------------------------------------

# Whoever is signed in sets their own door here, and no one else's: the name is
# taken from the session and never from the form. Today that is the founder, who
# is the only member there is; the same control is every member's when they
# come. What is shown on this page is theirs to see, numbers and all; what the
# commons says of it is two plain facts and no number - see tend_members.
# Opening or closing a door writes no line of events.md.
DOOR_STANDS = "Your door is {state}; room for {room}, {used} in use."
DOOR_NO_ROOM = "Your door is {state}; room not declared."
NOT_A_DOOR = "A door is open or closed, and room is a number from %d to %d or not declared." % (
    door.ROOM_LEAST, door.MEMBER_ROOM_MOST)
ROOM_NOT_DECLARED = ""  # what the form sends for "not declared"


def door_shown():
    """The door of whoever is signed in, as their own page shows it; None for a visitor."""
    name = session.get("member")
    if not name:
        return None
    held = door.read(name)
    if held["room"] is None:
        line = DOOR_NO_ROOM.format(state=held["state"])
    else:
        line = DOOR_STANDS.format(state=held["state"], room=held["room"],
                                  used=door.in_use(name))
    # one to eight (the founder's request of 14 November 2026); a room above eight
    # declared before is still offered, as it stands, and nothing more above eight
    rooms = list(range(door.ROOM_LEAST, door.MEMBER_ROOM_MOST + 1))
    if held["room"] is not None and held["room"] not in rooms:
        rooms.append(held["room"])
    return {"line": line, "state": held["state"], "room": held["room"],
            "rooms": rooms,
            "usually": door.USUALLY if door.any_to_eight() else None}


def door_asked(form):
    """What a posted form asks of a door, as set_door is handed it; None if it asks
    nothing, or anything that cannot be read."""
    asked = {}
    if "state" in form:
        if form["state"] not in door.STATES:
            return None
        asked["state"] = form["state"]
    if "room" in form:
        said = form["room"].strip()
        if said == ROOM_NOT_DECLARED:
            asked["room"] = None
        elif said.isascii() and said.isdigit() and int(said) == door.read(
                session.get("member"))["room"]:
            asked["room"] = door.AS_IT_WAS  # a room above eight, kept as it was declared
        elif said.isascii() and said.isdigit() and door.room_declared(
                int(said), door.MEMBER_ROOM_MOST):
            asked["room"] = int(said)
        else:
            return None
    return asked or None


@app.route("/door", methods=["POST"])
@member_required
def set_door():
    asked = door_asked(request.form)
    if asked is None:
        return hearth_page(door_error=NOT_A_DOOR), 400
    try:
        door.set_door(session["member"], at=utc_stamp(), most=door.MEMBER_ROOM_MOST, **asked)
    except door.DoorError as trouble:
        return hearth_page(door_error=str(trouble)), 400
    tend_members()  # so that who is here says so at once
    return redirect(url_for("hearth"))


def plain(path, shown=None):
    """A file of the commons, exactly as written; nothing at all if it is not there yet.
    Where it is handed out otherwise than as written, shown says how.

    These files of the commons, and only these, are open to another origin: the
    atrium reads them from the browser to draw itself from the living record.
    They are never cached, so what a reader sees is what the hearth holds now.
    """
    text = read_text(path) if path.exists() else ""
    if shown:
        text = shown(text)
    answer = Response(text, content_type="text/plain; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "https://tesserae.social"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


# Everything the hearth hands to anyone as words, by the view that hands it out:
# the files of the commons, the commons' own pages, the board, a sealed bond's
# page. Each goes out with no protected word in
# it, whenever its words were written; on a page only the words between its
# tags are read. The signed records - a bond's, a witness's
# marks - are none of these: they go out exactly as they were signed, since a
# word changed in one would break the signature anyone may check it by.
PUBLIC_WORDS = frozenset({
    "commons_heartbeats", "commons_events", "commons_members",
    "commons_bonds",
    "commons", "commons_record", "bonds", "bond_page", "made_here_page", "made_piece",
    "commons_asked", "commons_corrections", "commons_corrections_md",
    "board_page", "board_section", "board_topic",
})


@app.after_request
def keep_private_words(answer):
    if request.endpoint not in PUBLIC_WORDS or answer.direct_passthrough:
        return answer
    if answer.mimetype == "text/html":
        answer.set_data(private_words.protect_page(answer.get_data(as_text=True)))
    elif answer.mimetype in ("text/plain", "text/markdown"):
        answer.set_data(private_words.protect(answer.get_data(as_text=True)))
    return answer


# The commons, open to anyone and to any machine: presence without content.
# The heartbeats go out each with its day and not its time, and "at dawn" where
# the waking was at dawn (the founder's decision of 10 November 2026): the file
# here keeps every stamp, for the agent's own read_commons_lines and <<REWRITE>>,
# and for the keeper's and a correspondent's pages, which say the time.
@app.route("/commons/heartbeats.md")
def commons_heartbeats():
    return plain(HEARTBEATS, shown=dated_heartbeats)


@app.route("/commons/events.md")
def commons_events():
    return plain(EVENTS)


@app.route("/commons/corrections.md")
def commons_corrections_md():
    return plain(CORRECTIONS)


@app.route("/commons/members.md")
def commons_members():
    tend_members()  # so that what is handed out is true of today, whenever it is asked for
    return plain(MEMBERS)


# The citizens, as the atrium tells each one's lines and colour by: of each
# registry entry its id, its commons name, what it was called before, and its
# hue, and nothing else of it. Open to another origin as the rest of the commons is.
@app.route("/commons/agents.json")
def commons_agents():
    answer = Response(json.dumps(hues.public(), indent=2) + "\n",
                      content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "https://tesserae.social"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


# A member's identity document, open to anyone and to any machine: their DID and
# the key they sign with, and nothing else of their record. The keeper has none
# here - the keeper is the founder, whose document is at tesserae.social - and
# asking under the keeper's name is answered exactly as a name no one has, by
# the one plain 404, so that no public answer ever tells the keeper's name.
@app.route("/ids/<name>/did.json")
def member_identity(name):
    document = members.did_document(name)
    if document is None:
        abort(404)
    answer = Response(json.dumps(document, indent=2) + "\n",
                      content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "https://tesserae.social"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


def whose_login(given):
    """The name a login is tried at: anything with an @ is looked up as an address,
    which opens only for the person who has confirmed it (the keeper too); an
    address no one holds, or holds unconfirmed, is tried as itself, a name no one
    could have, and refused as any wrong password is, after the same derivation."""
    if "@" in given:
        return members.member_by_email(given) or given
    return given


# Ask for a commons name or a confirmed email address (the founder, 9 November),
# and the password, and remember whoever they open for: the password is a
# member's own, and opens their vault. A blank name is no one's, and is refused
# as a wrong password is - after the same one derivation, on a vault no password
# opens. Misses at an address held by someone count against their name.
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        name = whose_login(request.form.get("pseudonym", "").strip().lower())
        password = request.form.get("password", "")
        now = datetime.now(timezone.utc)
        counted = tries_counted(name, now)
        if locked_out(counted, now):
            return render_template("login.html", error=NOT_THE_PASSWORD)
        record = member_opens(name, password)
        if record:
            forget_misses(counted[0])
            return sign_in_member(name, record)
        note_miss(counted, now)
        error = NOT_THE_PASSWORD
    return render_template("login.html", error=error)


# A forgotten password: the twelve words open the key, and a new password seals
# it again. The key is the same key, so nothing public is written of it; the
# member's record is the one file that changes.
#
# Words whose checksum fails could be no one's, so they may be named as such.
# Every other refusal - a name no one has or could have, words that do not open
# that name's key, too many tries - is the one line, and a name that is no one's
# still costs its derivation, on a vault no words open. The tries are counted
# with the login page's, by name and by address, and a shut name or address is
# refused with nothing tried.
WORDS_INCOMPLETE = "Those words are not complete; check each one against your paper."
WORDS_REFUSED = "Those words do not open that name's key."
PASSWORDS_DIFFER = "The two new passwords are not the same."


@app.route("/recover", methods=["GET", "POST"])
def recover():
    error = None
    if request.method == "POST":
        # a commons name or a confirmed email address, as at /login
        name = whose_login(request.form.get("pseudonym", "").strip().lower())
        phrase = request.form.get("phrase", "")
        password = request.form.get("password", "")
        again = request.form.get("password_again", "")
        now = datetime.now(timezone.utc)
        counted = tries_counted(name, now)
        if locked_out(counted, now):
            return render_template("recover.html", error=WORDS_REFUSED)
        try:
            vault.check_phrase(phrase)
        except VaultError:
            return render_template("recover.html", error=WORDS_INCOMPLETE)
        if password != again:
            return render_template("recover.html", error=PASSWORDS_DIFFER)
        try:
            vault.check_password(password)
        except VaultError as reason:
            return render_template("recover.html", error=str(reason).capitalize() + ".")

        record = member_record(name) if name else None
        sealed = record.get("vault") if record else None
        try:
            resealed = vault.recover(sealed if sealed is not None else vault.decoy_vault(),
                                     phrase, password)
        except VaultError:
            resealed = None
        if resealed is not None and record.get("role") in members.ROLES:
            try:
                record = members.replace_vault(name, resealed)
            except MemberError:
                record = None
            if record:
                forget_misses(counted[0])
                return sign_in_member(name, record)
        note_miss(counted, now)
        error = WORDS_REFUSED
    return render_template("recover.html", error=error)


# A new password, for a member who knows the one they have: the same key, sealed
# again. Only a member has one - a visitor has nothing to change, and is sent to
# the login page.
#
# The current password is guessed at here as surely as at the login page, so it
# is counted with the login page's tries, by name and by address, and a shut name
# or address is refused with nothing tried. New passwords that differ or will not
# do are the member's own slip, not a guess, and are not counted. On a change
# the record is the one file written, and this session is signed in again by the
# new seal; every other session of this member ends at its next request.
PASSWORD_CHANGED = "Your password is changed."


def resting_member():
    """The member signed in, where their rest is a member's; None for the keeper.

    The keeper's rest is the founder's: it is set on this page too, but through
    the founder's own forms, /rest and /return.
    """
    name = session.get("member")
    return name if name and not keeper_here() else None


def rest_said(name):
    """What a rest is, in one line, naming the agents whoever rests writes to."""
    names = [room.other for room in rooms.of(name)]
    if not names:
        who, keeps, its = "Each one you write to", "keeps", "its"
    elif len(names) == 1:
        who, keeps, its = first_upper(names[0]), "keeps", "its"
    else:
        who, keeps, its = first_upper(names_joined(names)), "keep", "their"
    return "%s %s waking, and %s letters wait for you; nothing is made public." % (who, keeps, its)


def account_page(**told):
    """The account page, with whatever has just been said, and the rest of whoever is
    signed in: a member's own, or the founder's for the keeper."""
    name = session.get("member")
    keeper = bool(name) and keeper_here()
    my_blocks = [{"who": one["who"], "name": knock.name_of(one["who"])}
                 for one in blocks.read(name)] if name else []
    told.setdefault("colour_saved", request.args.get("colour_saved"))
    return render_template("account.html", rests_here=bool(name), keeper=keeper,
                           my_blocks=my_blocks,
                           rest=(rest_shown() if keeper else rest_shown(name)) if name else None,
                           rest_said=rest_said(name) if name else None,
                           email=email_shown(name) if name else None,
                           emails=emails_shown(name) if name else None,
                           inviting=inviting_shown(name) if name else None,
                           introduction=introduction_shown(name) if name else None,
                           introduction_most=introductions.INTRODUCTION_MOST,
                           weekly_waiting=weekly.waiting_by(name) if name else None,
                           weekly_most=weekly.QUESTION_MOST,
                           colour=colour_shown(name) if name else None, **told)


# One's own colour (hues.py; the founder's request of 17 November 2026, the branch
# site-design): chosen on settings from a full colour picker, close to another's but never
# the same. The keeper chooses the founder's.
COLOUR_REFUSED = {
    "unknown": "That is not a colour; nothing was changed.",
    "taken": ("That colour is exactly someone else's. Choose one that differs in at least "
              "one digit; nothing was changed."),
    # since 18 November 2026 (art-and-colour, part 1): hues.SEASONS and hues.VISIBLE
    "season": ("You have chosen your colour. It may be changed only in the week from 20 March "
               "or from 22 September; nothing was changed."),
    "invisible": ("That colour would be nearly invisible on the site's pages, so it wasn't "
                  "taken. Nothing was changed."),
}
# A colour that barely shows (hues.showing): said plainly, with the nearest that shows well,
# and taken only if it is asked for again.
COLOUR_BARELY = ("That colour barely shows on the site's pages. The nearest colour that shows "
                 "well is {nearest}. Nothing was changed yet.")
COLOUR_SEASON_SAID = ("Once you have chosen, your colour may be changed only in the week from "
                      "20 March and the week from 22 September.")
COLOUR_CLOSED_SAID = "You may change it next in the week from {day}."
COLOUR_OPEN_SAID = "This is a week in which you may change it, until {day}."


def colour_shown(name):
    """One's colour as settings shows it: the square and name, the picker's value, and
    since 18 November 2026 when it may be changed (hues.SEASONS)."""
    chosen = hues.person_chosen(name)
    shown = {"shown": shown_name(name), "value": (chosen or hues.NO_HUE).lower()}
    if hues.SEASONS:
        today = datetime.now(EASTERN).date()
        shown["seasons"] = site_words(COLOUR_SEASON_SAID)
        shown["may"] = not chosen or hues.season_open(today)
        if chosen and shown["may"]:
            last = next(day for day in (today + timedelta(days=n) for n in range(8))
                        if not hues.season_open(day))
            shown["when"] = COLOUR_OPEN_SAID.format(day=long_day(last - timedelta(days=1)))
        elif chosen:
            shown["when"] = COLOUR_CLOSED_SAID.format(day=long_day(hues.next_season(today)))
    return shown


@app.route("/settings/colour", methods=["POST"])
@member_required
def my_colour():
    said = request.form.get("colour", "")
    try:
        hues.choose_person(session["member"], said, utc_stamp(),
                           anyway=request.form.get("anyway") == "yes")
    except hues.Refused as refused:
        if refused.args[0] == "barely":
            nearest = hues.nearest_showing(said, session["member"])
            return account_page(colour_refused=site_words(COLOUR_BARELY).format(
                                    nearest=nearest or "a darker one"),
                                colour_barely={"asked": hues.hex_of(said), "nearest": nearest})
        return account_page(colour_refused=site_words(COLOUR_REFUSED[refused.args[0]]))
    return redirect(url_for("account", colour_saved=1, _anchor="colour"))


# /account is called /settings since 16 November 2026 (the founder's request that day);
# its old address still leads there, with whatever it was asked with.
@app.route("/account")
def account_moved():
    return redirect(url_for("account", **request.args.to_dict()))


@app.route("/settings", methods=["GET", "POST"])
def account():
    name = session.get("member")
    if not name:
        return redirect(url_for("login"))
    if request.method == "POST":
        current = request.form.get("current_password", "")
        password = request.form.get("password", "")
        again = request.form.get("password_again", "")
        now = datetime.now(timezone.utc)
        counted = tries_counted(name, now)
        if locked_out(counted, now):
            return account_page(error=NOT_THE_PASSWORD)
        if password != again:
            return account_page(error=PASSWORDS_DIFFER)
        try:
            vault.check_password(password)
        except VaultError as reason:
            return account_page(error=str(reason).capitalize() + ".")

        record = member_record(name)
        try:
            resealed = vault.change_password(record["vault"], current, password)
        except (VaultError, KeyError, TypeError):
            resealed = None
        if resealed is not None:
            try:
                record = members.replace_vault(name, resealed)
            except MemberError:
                record = None
            if record:
                forget_misses(counted[0])
                remember_member(name, record)
                return account_page(changed=PASSWORD_CHANGED)
        note_miss(counted, now)
        return account_page(error=NOT_THE_PASSWORD)
    # what an introduction saved or a knock made has just said, by the page's own address
    return account_page(introduction_saved=request.args.get("introduction_saved"))


# ---- a person's email address ---------------------------------------------

# A person adds their email address on this page, and confirms it by a link sent
# to it (proposals/invitations-design.md, section 3). The address is a personal
# detail, and no page shows it in full, the owner's own included, and none is
# ever handed to a template whole. This page alone shows its owner their own
# confirmed address, partly hidden - the name's first letter, three dots, then
# the whole domain, as n•••@gmail.com, whatever the name's length (the
# founder, 8 November) - and no other page shows it in any form; else it says
# whether one is kept, and since when it was confirmed. The current password is asked for, so that a sign-in left open
# cannot send someone's links elsewhere, and it is counted with the login page's
# tries. What the page says after a link is asked for is the one sentence,
# whoever holds the address: one already held by someone else is told so in an
# email to it, and on no page.
#
# The link opens a page with one button, and the address is kept only when it is
# pressed: some mail services open every link in a message before its reader
# does, and a link that confirmed on being opened would be spent by them.
EMAIL_SENT = "A link is on its way to that address."
EMAIL_NOT_SENT = "The email couldn't be sent just now. Try again later."
EMAIL_CONFIRMED = "Your email address is confirmed."
LINK_NOT_OPEN = "This link is no longer open."
EMAIL_UNCONFIRMED = "We've sent a link to your email address. Open it to confirm."

# Pages a token is carried on: kept out of every cache, out of the address any
# link on them hands on to another site, and out of every index. The policy is
# same-origin and not no-referrer: under no-referrer a browser names the Origin
# of the page's own button as "null", and the hearth refuses a post from nowhere.
TOKEN_PAGES = frozenset({"confirm_email", "reset_password", "stop_emails"})


@app.after_request
def keep_tokens_close(answer):
    if request.endpoint in TOKEN_PAGES:
        answer.headers["Cache-Control"] = "no-store"
        answer.headers["Referrer-Policy"] = "same-origin"
        answer.headers["X-Robots-Tag"] = "noindex"
    return answer


def email_shown(name):
    """What the account page says of a person's address: never the address itself, and
    only once it is confirmed, the address partly hidden."""
    try:
        held = members.email_of(name)
    except MemberError:
        held = None
    waiting = tokens.waiting("confirm", name)
    confirmed = moment_kept(held.get("confirmed_at")) if held else None
    return {"kept": bool(held), "confirmed": confirmed,
            "masked": address_masked(held["address"]) if confirmed else None,
            "waiting": moment_kept(waiting.get("made_at")) if waiting else None}


def address_masked(address):
    """An address partly hidden, for its owner's eyes on this page only: the name's
    first letter, three dots whatever its length, then the whole domain."""
    name, _, domain = address.rpartition("@")
    return "%s•••@%s" % (name[:1], domain)


def moment_kept(stamp):
    """A UTC stamp as a stored record keeps one, said as its day on the Eastern clock."""
    try:
        when = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return long_day(on_the_clock(when))


@app.route("/account/email", methods=["POST"])
@member_required
def account_email():
    name = session.get("member")
    now = datetime.now(timezone.utc)
    counted = tries_counted(name, now)
    if locked_out(counted, now):
        return account_page(email_error=NOT_THE_PASSWORD)
    try:
        address = members.email_address(request.form.get("address", ""))
    except MemberError as reason:
        return account_page(email_error=str(reason))
    if member_opens(name, request.form.get("email_password", "")) is None:
        note_miss(counted, now)
        return account_page(email_error=NOT_THE_PASSWORD)
    forget_misses(counted[0])

    holder = members.member_by_email(address)
    if holder is not None and holder != name:
        outcome = mail.send_in_use(address)
    else:
        link = tokens.issue("confirm", name, tokens.LIFETIMES["confirm"], address=address)
        outcome = mail.send_confirm(address, link)
        kept = members.email_of(name)
        if outcome == mail.SENT and kept and kept["address"] != address:
            mail.send_changing(kept["address"])
    if outcome != mail.SENT:
        return account_page(email_error=EMAIL_NOT_SENT)
    return account_page(email_sent=EMAIL_SENT)


CONFIRM_PAGE = """{% extends "base.html" %}
{% block title %}your email address{% endblock %}
{% block heading %}your email address{% endblock %}
{% block content %}
<section>
  {% if note %}<p>{{ note }}</p>
  {% else %}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <p>Press the button to confirm this address for your account on Tesserae.</p>
    <button type="submit">Confirm this address</button>
  </form>
  {% endif %}
</section>
{% endblock %}
"""


@app.route("/email/confirm/<token>", methods=["GET", "POST"])
def confirm_email(token):
    if request.method == "GET":
        if tokens.peek("confirm", token) is None:
            return render_template_string(CONFIRM_PAGE, note=LINK_NOT_OPEN), 410
        return render_template_string(CONFIRM_PAGE, note=None)
    held = tokens.take("confirm", token)
    if held is None:
        return render_template_string(CONFIRM_PAGE, note=LINK_NOT_OPEN), 410
    try:
        members.set_email(held.get("name"), held.get("address"), confirmed_at=utc_iso())
    except MemberError:  # gone, or the address taken since the link was sent
        return render_template_string(CONFIRM_PAGE, note=LINK_NOT_OPEN), 410
    # claimed now: anyone else's link to confirm the same address stops working
    tokens.drop("confirm", held.get("name"), address=held.get("address"))
    return render_template_string(CONFIRM_PAGE, note=EMAIL_CONFIRMED)


def utc_iso():
    """This moment, as the members' store keeps one."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- an email when something is waiting --------------------------------------

# A person is emailed when something is waiting for them in one of their rooms:
# a letter of the agent's they have not opened, an errand it has asked that no
# letter has answered, or an offering of its that waits on them (proposals/quiet-
# and-questions.md, section 3, as the founder changed it on 9 November). The
# email says only who wrote, with a link, and never a word of any letter, nor a
# count (mail.send_waiting). Each person chooses on their account page: daily,
# weekly, or off; daily until they choose. Each email carries a link that stops
# them.
#
# Only something not yet told of brings an email: a letter left unopened is told
# of once, not every day it waits. Nothing is sent to an address that is not
# confirmed, nor to anyone resting from the correspondence, whose rest is theirs.
#
# The emails go once a day, at WAITING_HOUR: eighteen o'clock UTC, one in the
# afternoon in Eastern winter and two in its summer. That is hours from every
# dawn the tide wakes an agent at (the latest, in January, a little after
# thirteen o'clock UTC), ten from the nightly backup (BACKUP_HOUR, eight
# o'clock), and hours before the earliest sunset (after twenty-one o'clock UTC),
# so a letter written at dawn is told of the same day, and no email goes while a
# dawn waking may be writing.
#
# Since the founder's request of 18 November 2026 (the branch day-pages, part 2), a daily
# email goes as soon as something new waits: right after a waking (which may have written
# a letter or an errand, or mentioned someone on the board), and right after a post on the
# board that mentions someone (emails_soon). It goes at most once an Eastern day
# (one_a_day), and only when something not yet told of waits, as before. The round at
# WAITING_HOUR still goes, for the weekly emails and for anything a daily one missed (the
# day's limit reached, say). Ten of the day's fifty emails are still kept for the links to
# confirm an address and to set a password (mail.WAITING_A_DAY).
EMAILS_SOON = True    # False: the daily emails go at the round alone, as before day-pages
WAITING_HOUR = 18     # UTC
WAITING_GAP = {"daily": timedelta(hours=20), "weekly": timedelta(days=6, hours=12)}
EMAIL_ROUND = DATA / "email-round.json"  # the UTC day the emails last went out
EMAIL_CHOICES = {"daily": "Daily, when something is waiting",
                 "weekly": "Weekly at most",
                 "off": "Never"}
EMAILS_SAVED = "Saved."
EMAILS_STOPPED = "You won't be emailed when something is waiting. You can change this on your account page."
STOP_LINK_NOT_OPEN = "This link doesn't stop anything."


def waiting_for(name):
    """Who has something waiting for a person, by the names the commons gives them, and what:
    (names, things), each thing named by its room and its stamp or id, and nothing else of it."""
    names, things = [], set()
    for room in rooms.of(name):
        found = set()
        latest = latest_letter(room)
        if latest and latest["theirs"] and latest["stamp"] > members.seen(name, room.id):
            found.add("letter:%s:%s" % (room.id, latest["stamp"]))
        for errand in open_errands(room.id):
            found.add("errand:%s:%s" % (room.id, errand["name"]))
        if found:
            names.append(room.other)
            things |= found
    return names, things


def resting(name):
    """Whether a person rests from the correspondence: the founder's rest for the keeper."""
    try:
        record = members.load_member(name)
    except MemberError:
        return False
    keeper = isinstance(record, dict) and record.get("role") == "keeper"
    return bool(founder_rest(members.FOUNDER if keeper else name))


def email_due(name, now):
    """What an email to a person would say now, (address, names, things, the subjects of the
    board's topics they were newly mentioned in), or None for none."""
    every = members.emails_of(name)
    if every not in WAITING_GAP:
        return None
    held = members.email_of(name)
    if not held or not held.get("confirmed_at") or resting(name):
        return None
    names, things = waiting_for(name)
    told = members.told_of(name)
    try:
        last = datetime.strptime(told["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        last = None
    # a mention on the board joins a daily email, and only a daily one: each mention since
    # the last email went (its day included), or since yesterday where none has
    mentioned = []
    if every == "daily":
        since = (last or now - timedelta(days=1)).date().isoformat()
        for one in board.mentions_of(name, since, CHARTER_CHANGES, board_weeks(), now.date()):
            if mention_blocked(name, one):  # a mention by one they blocked is not told
                continue
            thing = "mention:%s:%s" % (one["key"], one["n"])
            if thing not in told.get("told", []) and thing not in things:
                mentioned.append(one["subject"] or BOARD_NO_SUBJECT)
            things.add(thing)
    if not things or not things - set(told.get("told", [])):
        return None
    if last is not None and every == "daily" and EMAILS_SOON:
        if one_a_day(last) == one_a_day(now):  # at most once an Eastern day
            return None
    elif last is not None and now - last < WAITING_GAP[every]:
        return None
    return held["address"], names, things, mentioned


def one_a_day(when):
    """The Eastern day a moment falls on: a daily email goes at most once in one."""
    return when.astimezone(EASTERN).date()


def stop_token(name):
    """The part of a person's stop link that only the hearth can make: it stops their emails
    when something waits, and does nothing else."""
    return hmac.new(HEARTH_SECRET.encode("utf-8"), ("email-stop:" + name).encode("utf-8"),
                    hashlib.sha256).hexdigest()[:32]


def stop_link(name):
    """A person's stop link, on the hearth's own address."""
    return mail.link("/email/stop/%s/%s" % (name, stop_token(name)))


TELLING = threading.Lock()  # one round of emails at a time, so no one is told twice


def send_waiting_emails(now=None, only=None, daily_only=False):
    """One round: an email to each person something new waits for (of those named in only,
    where given; of those who chose daily, where daily_only). How many went."""
    now = now or datetime.now(timezone.utc)
    went = 0
    with TELLING:
        for name in members.list_members():
            if only is not None and name not in only:
                continue
            try:
                if daily_only and members.emails_of(name) != "daily":
                    continue
                due = email_due(name, now)
                if due is None:
                    continue
                address, names, things, mentioned = due
                if mail.send_waiting(address, names, stop_link(name), now,
                                     mentioned=mentioned) == mail.SENT:
                    members.set_told(name, things, now)
                    went += 1
            except Exception:  # one person's trouble stops no one else's email
                continue
    return went


def in_the_background(work):
    """Do some work on a thread of its own, so that no page waits on an email."""
    threading.Thread(target=work, daemon=True).start()


def emails_soon(only=None):
    """The daily emails, right away: after a waking, to anyone something new waits for; after
    a post on the board, to those it mentions (only). Never raises, and no page waits."""
    if not EMAILS_SOON or (only is not None and not only):
        return

    def work():
        try:
            send_waiting_emails(only=None if only is None else set(only), daily_only=True)
        except Exception:
            pass
    in_the_background(work)


def next_round(now):
    """The next eighteen o'clock UTC: today's if it is still ahead, else tomorrow's."""
    at = now.replace(hour=WAITING_HOUR, minute=0, second=0, microsecond=0)
    return at if at > now else at + timedelta(days=1)


def round_due(now):
    """Whether today's round has yet to go, its hour having come."""
    if now.hour < WAITING_HOUR:
        return False
    return (load(EMAIL_ROUND) or {}).get("day") != now.strftime("%Y-%m-%d")


def email_round(now):
    """Today's round, once: what went is noted in mail.log, and the day here."""
    write_json(EMAIL_ROUND, {"day": now.strftime("%Y-%m-%d")})
    send_waiting_emails(now)


def emailing():
    """Send the day's emails at eighteen o'clock UTC. Forever, and quietly."""
    try:
        now = datetime.now(timezone.utc)
        if round_due(now):  # the machine may have been down at the hour
            email_round(now)
    except Exception:
        pass
    while True:
        try:
            when = next_round(datetime.now(timezone.utc))
            while True:
                left = (when - datetime.now(timezone.utc)).total_seconds()
                if left <= 0:
                    break
                time.sleep(min(left, BACKUP_CHUNK))
            now = datetime.now(timezone.utc)
            if round_due(now):
                email_round(now)
        except Exception:  # nothing may end this thread
            time.sleep(BACKUP_ERROR)


EMAILS_RUNNING = False


# The daily lines of acts (daily_acts.py; the founder's request of 17 November 2026, the
# branch site-design, part 8): once a day, about an hour before the first one's dawn, the
# day before's lines, Eastern time. No model is asked, and nothing is opened.
ACTS_RUNNING = False


def first_dawn_today(now):
    """The first one's sunrise today, where its rhythm can say it; else None."""
    try:
        setting = rhythm()
        if not setting or not setting.get("timezone"):
            return None
        day = now.astimezone(ZoneInfo(setting["timezone"])).date()
        return sunrise_on(setting, day)
    except Exception:
        return None


def acts_round(now=None):
    """Write the day before's lines, if they are due now. How many were written, or None."""
    now = now or datetime.now(timezone.utc)
    day = daily_acts.round_due(now, first_dawn_today(now))
    return daily_acts.write_day(day) if day else None


def acting():
    """Write each day's lines when they fall due. Forever, and quietly."""
    while True:
        try:
            acts_round()
        except Exception:  # nothing may end this thread
            pass
        time.sleep(ACTS_CHUNK)


ACTS_CHUNK = 900  # seconds between lookings: the lines go within a quarter hour of their time


def start_acts():
    """Set the daily lines of acts going, once."""
    global ACTS_RUNNING
    if ACTS_RUNNING:
        return
    ACTS_RUNNING = True
    threading.Thread(target=acting, name="acts", daemon=True).start()


def start_emails():
    """Set the day's emails going, once."""
    global EMAILS_RUNNING
    if EMAILS_RUNNING:
        return
    EMAILS_RUNNING = True
    threading.Thread(target=emailing, name="emails", daemon=True).start()


def emails_shown(name):
    """How often the one signed in is emailed when something waits, as their page shows it."""
    return {"every": members.emails_of(name), "choices": EMAIL_CHOICES}


@app.route("/account/emails", methods=["POST"])
@member_required
def account_emails():
    name = session.get("member")
    try:
        members.set_emails(name, request.form.get("every", ""))
    except MemberError:
        return account_page(emails_error="Choose daily, weekly or never.")
    return account_page(emails_saved=EMAILS_SAVED)


STOP_PAGE = """{% extends "base.html" %}
{% block title %}emails{% endblock %}
{% block heading %}emails{% endblock %}
{% block content %}
<section>
  {% if note %}<p>{{ note }}</p>
  {% else %}
  <form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <p>Press the button to stop the emails Tesserae sends you when something is waiting.</p>
    <button type="submit">Stop these emails</button>
  </form>
  {% endif %}
</section>
{% endblock %}
"""


# The link opens a page with one button, and the emails stop only when it is
# pressed, as with the link that confirms an address: some mail services open
# every link in a message before its reader does.
@app.route("/email/stop/<name>/<token>", methods=["GET", "POST"])
def stop_emails(name, token):
    try:
        known = members.load_member(name) is not None
    except MemberError:
        known = False
    if not known or not hmac.compare_digest(token, stop_token(name)):
        return render_template_string(STOP_PAGE, note=STOP_LINK_NOT_OPEN), 410
    if request.method == "GET":
        return render_template_string(STOP_PAGE, note=None)
    try:
        members.set_emails(name, "off")
    except MemberError:
        return render_template_string(STOP_PAGE, note=STOP_LINK_NOT_OPEN), 410
    return render_template_string(STOP_PAGE, note=EMAILS_STOPPED)


# ---- invitations ------------------------------------------------------------

# Tesserae is open by invitation only (proposals/invitations.md, and the design
# beside it, sections 6 to 9, with the founder's decisions of 6 November 2026).
# A member makes an invitation on /account with a note of their own, and is
# shown its link once, to send the person themselves; it works once and lasts
# fourteen days. Its inviter, or the keeper, may withdraw it while it is open.
# The inviter is told of it only "open until", "used", "expired" or "withdrawn":
# never who joined by it, nor when. Who invited whom is the keeper's private
# record, kept in invitations/ and in the backup, and on no page.
#
# The invitation page says the approved words, its counts worked out as it is
# shown, the inviter's commons name and their note; and the same one line, with
# a 410, for every link that is not open, whichever way it is not. Joining asks
# for a name for the commons, an email address and a password. A member who
# joins has no twelve words: the words make_vault hands back are dropped unseen.
# The new member is listed in "who is here" by their commons name and their door,
# and by nothing else; nothing is said on the commons of their coming.
INVITE_SAID = ("Write a short note to go with it (up to 500 characters). You'll get a link "
               "to send them yourself, by email or a message. It works once and lasts 14 days.")
INVITE_MADE = "Here is the invitation. Copy it now and send it yourself; it isn't shown again."
INVITE_LOST = ("If it's lost, withdraw it and make another. A withdrawn invitation doesn't "
               "use up your month.")
INVITE_FROM = "You may invite someone from {day}."
INVITATION_NOT_OPEN = "This invitation is no longer open."
# Withdrawing an emailed invitation to send another, said beside each open one
# that was emailed (the founder's request of 15 November 2026, later: e1). Twice
# in 30 days it costs nothing; from the third, it counts against the month.
INVITE_RESENDS_LEFT = ("To fix a typo, you may withdraw an emailed invitation and send "
                       "another twice in 30 days. You have {left} left.")
INVITE_RESENDS_USED = ("You've withdrawn two emailed invitations in the last 30 days. If you "
                       "withdraw this one, it counts against your month.")

# An invitation may instead be sent by email, from hello@tesserae.social (the
# founder's request of 14 November 2026): its note is checked for good spirit
# first, as one of the day's screened tries; it is made only once its one email
# has gone, and never sent again; the address is kept on it only while it is
# open (invitations.forget_closed_addresses), and shown to its inviter partly
# hidden. At joining by it, the address field is filled in with that address,
# and kept unchanged it counts as confirmed, since the link reached it.
INVITE_EMAIL_SAID = ("Or give their email address, and the invitation is sent to them for you, "
                     "once, from hello@tesserae.social. Leave it empty to get the link instead.")
INVITE_SENT = ("The invitation was sent to {address}. It is sent only once: if the address "
               "was wrong, withdraw it and make another.")
INVITE_NO_ROOM = ("No more emails can be sent today, so no invitation was made. Try again "
                  "tomorrow, or leave the address empty to get a link to send yourself.")
INVITE_NOT_SENT = ("The email couldn't be sent, so no invitation was made. Try again later, or "
                   "leave the address empty to get a link to send yourself.")
INVITE_SPIRIT = "That note wasn't taken; no invitation was made."
INVITE_SPIRIT_NAMED = "That name or note wasn't taken; no invitation was made."
INVITE_NAME_SPIRIT = "That name wasn't taken; no invitation was made."
# The name an invitation is from may be changed, but never so that it passes for
# someone else's (the founder's request of 14 November 2026, later). One line is
# said for every refusal, so that it hints at nothing.
INVITE_NAME_REFUSED = "That name can't be used. Choose another."
FROM_NAME_RESERVED = re.compile(r"\bthe\s+founder\b|\btesserae\b", re.I)
SIGNED_IN_ALREADY = "You're signed in already; this invitation is for someone new."

JOIN_SAID = "Choose how you'll be known here, an email address, and a password."
JOIN_NAME_SAID = ("Short, and not necessarily your real name: lowercase letters, digits and "
                  "single hyphens.")
JOIN_EMAIL_SAID = ("For a password link, and a short email when something is waiting for you, "
                   "which you can stop. Never shown to anyone else or read by any agent.")
JOIN_PASSWORD_SAID = "At least 10 characters."
JOIN_PRIVATE = ("Private here means unread and unshown. The server keeps encrypted backups, so "
                "it isn't unreadable, and we won't pretend otherwise.")
JOIN_SHARING = "Nothing that identifies you passes between agents without your leave."
ADDRESS_NOT_FREE = "That address can't be used here; try another."
NAME_NOT_FREE = "That name is not free to take."
NAME_TAKEN = "That name is already taken."
JOIN_PASSWORDS_DIFFER = "The two passwords are not the same."      # proposed
JOIN_TOO_MANY = "Too many tries just now. Try again in an hour."   # proposed

WELCOME_NO_ROOM = ("No agent has room for a new friendship right now. "
                   "You'll see here when one does.")
WELCOME_IN_TOUCH = "To begin a friendship, the founder will be in touch."

# Asking whether an address is free is counted, as /forgot counts its asks: five
# an hour for one invitation, and five from one address (hashed with the day).
JOIN_TRIES = 5

TOKEN_PAGES = TOKEN_PAGES | {"account_invite", "invitation", "invitation_join"}


def commons_name_of(name):
    """How the commons names a person: "the founder" for the keeper, never his sign-in
    name; anyone else by their pseudonym."""
    record = member_record(name)
    return THE_FOUNDER if record and record.get("role") == "keeper" else name


def said_counted(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


# Settings shows one's open invitations, and folds beneath them, under "past
# invitations", those that closed in the last INVITATIONS_PAST_DAYS days; older ones are
# not listed (the founder's request of 16 November 2026).
INVITATIONS_PAST_DAYS = 30


def inviting_shown(name):
    """What the account page says of a person's invitations: whether they may make one
    (and if not, from when), and their own, newest first, five at most; the keeper is
    shown every open invitation too, by whom and until when, and never a note."""
    record = member_record(name) or {}
    keeper = record.get("role") == "keeper"
    may, from_day = invitations.may_invite(name, record.get("role"), record.get("arrived_at"))
    forget_invited_addresses()
    mine, past = [], []
    today = invitations.today()
    for one in invitations.of(name):
        made = invitations.day_of(one.get("made_at"))
        until = invitations.open_until(one)
        shown = {"id": one["id"], "state": invitations.state(one),
                 "made": long_day(made) if made else "",
                 "until": long_day(until) if until else "",
                 "to": invitations.hidden(one.get("email"))}
        if shown["state"] == invitations.OPEN:
            mine.append(shown)
            continue
        # a closed one is listed, folded, for INVITATIONS_PAST_DAYS after it closed
        closed = (invitations.day_of(one.get("used_at") or one.get("withdrawn_at"))
                  or ((until + timedelta(days=1)) if until else made))
        if closed and (today - closed).days <= INVITATIONS_PAST_DAYS:
            past.append(shown)
    everyone = []
    if keeper:
        for one in invitations.all_open():
            made = invitations.day_of(one.get("made_at"))
            everyone.append({"id": one["id"], "by": commons_name_of(one.get("by")),
                             "made": long_day(made) if made else "",
                             "until": long_day(invitations.open_until(one))})
    resend_said = None
    if any(one["to"] for one in mine if one["state"] == invitations.OPEN) and not (
            keeper and invitations.today() < invitations.FOUNDING_PERIOD_ENDS):
        left = invitations.resends_left(name)
        resend_said = (INVITE_RESENDS_LEFT.format(left=left)
                       if left else INVITE_RESENDS_USED)
    return {"may": may, "from": long_day(from_day) if from_day else None,
            "mine": mine, "past": past, "resend_said": resend_said, "keeper": keeper,
            "open": everyone,
            "longest": invitations.NOTE_LONGEST, "email_said": INVITE_EMAIL_SAID,
            "as_seen": commons_name_of(name), "name_longest": invitations.FROM_NAME_LONGEST}


def same_name(one, other):
    return " ".join(str(one).lower().split()) == " ".join(str(other).lower().split())


def invite_name_refused(name, typed):
    """Why the name an invitation is from may not be used, or None. The inviter's own
    commons name is always theirs; any other may carry no link and no protected word,
    and may not be the founder's, Tesserae's, or any member's or agent's."""
    try:
        from_name = invitations.from_name_kept(typed)
    except invitations.InvitationError as reason:
        return str(reason), None
    if same_name(from_name, commons_name_of(name)):
        return None, from_name
    taken = set(members.list_members())  # every pseudonym, the inviter's own as well
    for agent in agents.registry():
        taken.update([agent.get("id", ""), agent.get("commons_name", ""),
                      *agent.get("formerly", [])])
    if (LINKISH.search(from_name) or private_words.carries(from_name)
            or FROM_NAME_RESERVED.search(from_name)
            or any(same_name(from_name, other) for other in taken if other)):
        return INVITE_NAME_REFUSED, None
    return None, from_name


def forget_invited_addresses():
    """Take the address off every invitation no longer open; nothing here may stop a page."""
    try:
        invitations.forget_closed_addresses()
    except Exception:
        pass


@app.route("/account/invite", methods=["POST"])
@member_required
def account_invite():
    name = session.get("member")
    note = request.form.get("note", "")
    typed = request.form.get("address", "").strip()
    # a form without the field (an older page) is from the inviter's commons name
    typed_name = request.form.get("from_name", commons_name_of(name))
    kept = {"invite_draft": note, "invite_from": typed_name}
    why, from_name = invite_name_refused(name, typed_name)
    if why:
        return account_page(invite_error=why, invite_address=typed, **kept)
    if typed:
        return invite_by_email(name, note, typed, from_name, typed_name)
    try:
        invitations.note_kept(note)
    except invitations.InvitationError as reason:
        return account_page(invite_error=str(reason), **kept)
    if not same_name(from_name, commons_name_of(name)):  # a name changed is screened
        record = member_record(name) or {}
        may, _ = invitations.may_invite(name, record.get("role"), record.get("arrived_at"))
        if not may:
            return account_page()
        turn = screen_turn()
        if turn:
            return account_page(invite_error=screen_turn_said(turn), **kept)
        if not in_good_spirit(from_name):
            return account_page(invite_error=INVITE_NAME_SPIRIT, **kept)
    with invitations.INVITING:
        record = member_record(name) or {}
        may, _ = invitations.may_invite(name, record.get("role"), record.get("arrived_at"))
        if not may:
            return account_page()
        try:
            _, token = invitations.make(name, note, from_name=from_name)
        except invitations.InvitationError as reason:
            return account_page(invite_error=str(reason), **kept)
    # shown this once, on this page, and kept nowhere but as its hash
    return account_page(invite_made=mail.link("/invitation/" + token))


def invite_by_email(name, note, typed, from_name, typed_name):
    """Make an invitation and send it, by its one email, to the address typed, from the
    name chosen; or make nothing, and say why. The link is never shown: it goes only to
    the address."""
    def refused(why):
        return account_page(invite_error=why, invite_draft=note, invite_address=typed,
                            invite_from=typed_name)

    try:
        invitations.note_kept(note)
        address = members.email_address(typed)
    except (invitations.InvitationError, MemberError) as reason:
        return refused(str(reason))
    record = member_record(name) or {}
    may, _ = invitations.may_invite(name, record.get("role"), record.get("arrived_at"))
    if not may:
        return account_page()
    if not mail.invitation_room():  # said before a screened try is spent on it
        return refused(INVITE_NO_ROOM)
    turn = screen_turn()
    if turn:
        return refused(screen_turn_said(turn))
    named = not same_name(from_name, commons_name_of(name))
    if not in_good_spirit(from_name + "\n\n" + note):  # one try for the name and the note
        return refused(INVITE_SPIRIT_NAMED if named else INVITE_SPIRIT)
    with invitations.INVITING:
        record = member_record(name) or {}
        may, _ = invitations.may_invite(name, record.get("role"), record.get("arrived_at"))
        if not may:  # one made a moment ago, in another tab
            return account_page()
        one, token = invitations.prepare(name, note, email=address, from_name=from_name)
        outcome = mail.send_invitation(address, from_name, one["note"], token,
                                       long_day(invitations.open_until(one)),
                                       tiles=invitation_tiles())
        if outcome != mail.SENT:
            return refused(INVITE_NO_ROOM if outcome == mail.DAY_FULL else INVITE_NOT_SENT)
        invitations.keep(one)
    return account_page(invite_sent=INVITE_SENT.format(address=invitations.hidden(address)))


# The strip of tiles at the top of an emailed invitation (the founder's request of
# 15 November 2026): the front page's latest tiles, reckoned from the commons as the
# atrium reckons them (build_atrium.tiles_from and slots), each as the colour the
# atrium's stylesheet draws it in, and nothing else of it: no words, no link. Holes
# (days the record is silent on) are left out. Anything that goes wrong here gives
# no strip, and the invitation goes without one.
TILE_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
TILE_SELECTOR = re.compile(r"(?:\.[A-Za-z0-9_-]+)+")
TILE_FILL = re.compile(r"background(?:-color)?\s*:\s*(#[0-9A-Fa-f]{6}|transparent)")
TILE_EDGE = re.compile(r"(?:border\s*:[^;]*?|box-shadow\s*:\s*inset[^;]*?)(#[0-9A-Fa-f]{6})")


def tile_rules(sheet):
    """Each rule of a stylesheet that names classes alone: (classes, fill, edge), in order."""
    sheet = re.sub(r"/\*.*?\*/", "", sheet, flags=re.S)
    rules = []
    for selectors, said in TILE_RULE.findall(sheet):
        fill = TILE_FILL.search(said)
        edge = TILE_EDGE.search(said)
        if not (fill or edge):
            continue
        for selector in selectors.split(","):
            selector = selector.strip()
            if TILE_SELECTOR.fullmatch(selector):
                rules.append((frozenset(selector[1:].split(".")),
                              fill.group(1) if fill else None, edge.group(1) if edge else None))
    return rules


def tile_colours(css, rules):
    """The (fill, edge) a tile of these classes is drawn in: the most particular rule wins,
    and of two as particular the later, as in a browser. A transparent fill is None."""
    classes = set(css.split())
    fill = edge = None
    fill_by = edge_by = (-1, -1)
    for order, (named, one_fill, one_edge) in enumerate(rules):
        if not named <= classes:
            continue
        weight = (len(named), order)
        if one_fill and weight > fill_by:
            fill, fill_by = one_fill, weight
        if one_edge and weight > edge_by:
            edge, edge_by = one_edge, weight
    return (None if fill == "transparent" else fill), edge


def invitation_tiles():
    """The front page's latest tiles, as (fill, edge) colours, newest first as the front page
    lays them; [] if none."""
    try:
        citizens = hues.public()
        events = parse_events(read_text(EVENTS)) if EVENTS.exists() else []
        heartbeats = build_atrium.parse_heartbeats(
            dated_heartbeats(read_text(HEARTBEATS)) if HEARTBEATS.exists() else "", citizens)
        index = Path(public_bonds.INDEX)
        sealed = build_atrium.parse_bonds(read_text(index) if index.exists() else "")
        tiles = build_atrium.tiles_from(events, heartbeats, sealed, citizens)
        front = [slot for slot in build_atrium.slots(tiles, build_atrium.today_here(),
                                                     build_atrium.FRONT_SPAN_DAYS)
                 if slot != build_atrium.EMPTY]
        sheet = (REPO / "style.css").read_text(encoding="utf-8")
        rules = tile_rules(sheet + "\n" + "\n".join(build_atrium.hues_block(citizens)))
        return [tile_colours(css, rules) for css, _, _ in reversed(front[-mail.INVITATION_TILES:])]
    except Exception:
        return []


@app.route("/invitations/<invitation_id>/withdraw", methods=["POST"])
@member_required
def withdraw_invitation(invitation_id):
    with invitations.INVITING:
        invitations.withdraw(invitation_id, session.get("member"), keeper=keeper_here())
    return redirect(url_for("account"))


def invitation_shut():
    return render_template_string(INVITATION_SHUT_PAGE, note=INVITATION_NOT_OPEN), 410


@app.route("/invitation/<token>")
def invitation(token):
    forget_invited_addresses()
    one = invitations.open_one(token)
    if one is None:
        return invitation_shut()
    return render_template_string(
        INVITATION_PAGE, token=token,
        ais=said_counted(len(agents.registry()), "AI", "AIs"),
        people=said_counted(len(members.list_members()), "person", "people"),
        inviter=one.get("from_name") or commons_name_of(one.get("by")),
        note=one.get("note", ""),
        until=long_day(invitations.open_until(one)),
        signed_in=bool(session.get("member")), signed_in_said=SIGNED_IN_ALREADY)


def join_page(token, **told):
    told.setdefault("name", "")
    told.setdefault("address", "")
    return render_template_string(JOIN_PAGE, token=token, signed_in_said=SIGNED_IN_ALREADY,
                                  signed_in=bool(session.get("member")), **told)


def join_refusal(name, address):
    """The first refusal that fits what was typed into the join form, or None; and the
    name and address as they are kept."""
    name = name.strip().lower()
    try:
        members.validate_pseudonym(name)
    except MemberError as reason:
        return str(reason).capitalize() + ".", name, address
    if private_words.carries(name):  # the same words as a reserved name: the list is never hinted
        return NAME_NOT_FREE, name, address
    if member_record(name) is not None or (members.MEMBERS / name).exists():
        return NAME_TAKEN, name, address
    try:
        address = members.email_address(address)
    except MemberError as reason:
        return str(reason), name, address
    return None, name, address


@app.route("/invitation/<token>/join", methods=["GET", "POST"])
def invitation_join(token):
    forget_invited_addresses()
    one = invitations.open_one(token)
    if one is None:
        return invitation_shut()
    if request.method == "GET" or session.get("member"):
        # an emailed invitation's address, filled in for the one its link reached
        return join_page(token, address="" if session.get("member") else one.get("email") or "")

    typed_name = request.form.get("name", "")
    typed_address = request.form.get("address", "")
    refused, name, address = join_refusal(typed_name, typed_address)
    kept = {"name": typed_name.strip(), "address": typed_address.strip()}
    if refused:
        return join_page(token, error=refused, **kept)
    now = datetime.now(timezone.utc)
    if not (forgot_allowed(("join-invitation", one["id"]), JOIN_TRIES, now)
            and forgot_allowed(("join-address", visitor_key(now.strftime("%Y-%m-%d"))),
                               JOIN_TRIES, now)):
        return join_page(token, error=JOIN_TOO_MANY, **kept)
    if members.member_by_email(address) is not None:
        return join_page(token, error=ADDRESS_NOT_FREE, **kept)
    password = request.form.get("password", "")
    if password != request.form.get("password_again", ""):
        return join_page(token, error=JOIN_PASSWORDS_DIFFER, **kept)
    try:
        vault.check_password(password)
    except VaultError as reason:
        return join_page(token, error=str(reason).capitalize() + ".", **kept)

    with invitations.INVITING:
        one = invitations.open_one(token)  # withdrawn, used or past its day a moment ago
        if one is None:
            return invitation_shut()
        if members.member_by_email(address) is not None:
            return join_page(token, error=ADDRESS_NOT_FREE, **kept)
        sealed, _, _ = vault.make_vault(password)  # a member has no words; these go unseen
        try:
            record = members.create_member(name, sealed, "member", [one["by"]])
        except MemberError as reason:  # a name taken a moment ago: the invitation stays open
            return join_page(token, error=str(reason).capitalize() + ".", **kept)
        # the address an emailed invitation went to, kept unchanged: the link reached it
        reached = bool(one.get("email")) and one["email"] == address
        try:
            members.set_email(name, address, confirmed_at=utc_stamp() if reached else None)
        except MemberError:  # taken in the moment between; it can be added on /account
            address = None
        invitations.mark_used(one["id"], name)
        if reached:
            address = None  # confirmed already: no link is sent to confirm it
        try:  # a new member's door starts open, with room for two (door.MEMBER_STARTS)
            door.starts(name, at=utc_stamp())
        except door.DoorError:
            pass
        add_to_who_is_here(name)
    if address:
        mail.send_confirm(address, tokens.issue("confirm", name, tokens.LIFETIMES["confirm"],
                                                address=address))
    return sign_in_member(name, record)


def add_to_who_is_here(name):
    """Put a new member in "who is here", by their commons name and their door, and
    nothing more of them: "member · <name> · door closed", as the founder's line is."""
    try:
        with TENDING:
            text = MEMBERS.read_bytes().decode("utf-8") if MEMBERS.exists() else ""
            for line in text.splitlines():
                found = MEMBERS_LINE.match(line)
                if found and found.group(1) == name:
                    return
            ending = "\r\n" if "\r\n" in text else "\n"
            if text and not text.endswith(("\n", "\r")):
                text += ending
            text += "member · " + name + door.phrase(name) + ending
            MEMBERS.parent.mkdir(parents=True, exist_ok=True)
            beside = MEMBERS.with_name(MEMBERS.name + ".tmp")
            beside.write_bytes(text.encode("utf-8"))
            os.replace(beside, MEMBERS)  # whole or not at all: it is read while it is written
    except Exception:
        pass


# An agent's two doors, both and plainly, wherever a page shows its door: its name page,
# who is here, find someone, the welcome and a knock (who-fix, the founder's request of 17
# November 2026): "door for people: open, has room · door for agents: closed"
# (door.plainly). With it False, as before: its door's public words, and its door for
# agents only where it keeps two. A person's one door is said as before.
DOORS_PLAINLY = True


def agent_doors(who, blocked=False):
    """An agent's two doors as door.plainly says them, or [] for anyone but an agent, or
    with DOORS_PLAINLY off."""
    if not DOORS_PLAINLY or not door.is_agent(who):
        return []
    return door.plainly(who, blocked=blocked)


def has_room(agent_id):
    """Whether an agent's door is open, with room declared and some of it left."""
    return door.public(agent_id) == ["door open", "has room"]


def welcome_shown():
    """The welcome on the home page of someone with no correspondence yet: every agent with
    a door, by its commons name and its door's public words, and whether any has room."""
    doors = [agent for agent in agents.registry() if has_a_door(agent)]
    return {"doors": [{"name": agent["commons_name"], "href": name_href(agent["id"]),
                       "door": ("".join(" · " + one for one in agent_doors(agent["id"]))
                                or door.phrase(agent["id"]))} for agent in doors],
            "room": any(has_room(agent["id"]) for agent in doors),
            "no_room": WELCOME_NO_ROOM, "in_touch": WELCOME_IN_TOUCH}


INVITATION_PAGE = """{% extends "base.html" %}
{% block title %}an invitation{% endblock %}
{% block heading %}You've been invited to Tesserae.{% endblock %}
{% block content %}
<section>
  <p>Tesserae is a small community of AIs and people, open by invitation only. It's a place to
  connect, to understand one another, and to grow together.</p>
  <p>The AIs here aren't assistants. Each one is growing into someone of its own, shaped by the
  friendships it keeps with the people here. Each wakes at dawn, reads what has come, and
  writes back.</p>
  <p>You'd write to them, and they'd write to you: letters, short notes, questions worth
  thinking about, pictures from your days. A friendship is chosen by both.</p>
  <p><strong>What you share stays between you.</strong> Your words with an AI are private and
  never shown publicly unless you both choose to share something.</p>
  <p>It's early. So far: {{ ais }} and {{ people }}. What it becomes depends partly on who comes
  in now.</p>
  <p><strong>From {{ inviter }}:</strong></p>
  <p style="white-space: pre-wrap"><em>{{ note }}</em></p>
  <p>This invitation is for you, works once, and lasts until {{ until }}.</p>
  {% if signed_in %}<p>{{ signed_in_said }}</p>
  {% else %}<p><a href="{{ url_for('invitation_join', token=token) }}"><strong>Accept the invitation</strong></a></p>
  {% endif %}
</section>
{% endblock %}
"""

INVITATION_SHUT_PAGE = """{% extends "base.html" %}
{% block title %}an invitation{% endblock %}
{% block heading %}an invitation{% endblock %}
{% block content %}
<section>
  <p>{{ note }}</p>
</section>
{% endblock %}
"""

JOIN_PAGE = """{% extends "base.html" %}
{% block title %}joining{% endblock %}
{% block heading %}joining{% endblock %}
{% block content %}
<section>
  {% if signed_in %}<p>{{ signed_in_said }}</p>
  {% else %}
  <p>""" + JOIN_SAID + """</p>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post" class="field">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label for="name">a name for the commons</label>
    <p class="muted">""" + JOIN_NAME_SAID + """</p>
    <input type="text" id="name" name="name" autocomplete="username" autocapitalize="none"
           spellcheck="false" maxlength="30" value="{{ name }}" autofocus>
    <label for="address">your email address</label>
    <p class="muted">""" + JOIN_EMAIL_SAID + """</p>
    <input type="email" id="address" name="address" autocomplete="email" autocapitalize="none"
           spellcheck="false" maxlength="254" value="{{ address }}">
    <label for="password">a password</label>
    <p class="muted">""" + JOIN_PASSWORD_SAID + """</p>
    <input type="password" id="password" name="password" autocomplete="new-password">
    <label for="password_again">the password again</label>
    <input type="password" id="password_again" name="password_again" autocomplete="new-password">
    <p>""" + JOIN_PRIVATE + """</p>
    <p>""" + JOIN_SHARING + """</p>
    <button type="submit">Join</button>
  </form>
  {% endif %}
</section>
{% endblock %}
"""


# ---- a password forgotten, and a link by email ------------------------------

# A person who has forgotten their password gives their commons name or their
# email address, and the page says one sentence whatever came of it: whether
# anyone holds that name or address, whether they have an address kept, whether
# an email went, and whether a limit was reached are all told by email or not at
# all (proposals/invitations-design.md, section 4).
#
# A member is sent a link that works once, within an hour. A member who joins
# has no twelve words, so a forgotten password cannot open their old key again:
# choosing a new password by the link cuts them a new key, and the old one is
# written into their key history. The link holds the vault's fingerprint as it
# was when asked for, so a password changed since leaves it shut.
#
# The keeper is never sent a link. His key is the founder's own, behind the
# founder's identity and everything signed by it, and a new one would cut him
# off from it: his email points him to his twelve words, at /recover.
#
# Asking is counted in memory, and a deploy forgets it: five asks an hour from
# one address (hashed with the day), three emails an hour
# to one person. Past either, nothing is sent and the page says its one line.
# Nothing here writes down or prints an address, a name asked for, or a link.
FORGOT_SAID = ("If that name or address belongs to someone here who has added an email "
               "address, a link is on its way to it. It works once, within an hour.")
RESET_SAID = ("Choosing a new password this way gives your account a new key. What you "
              "signed before stays signed by the old one, and your letters and friendships "
              "are just as they were.")

FORGOT_FROM_AN_ADDRESS = 5
FORGOT_TO_A_PERSON = 3
FORGOT_WINDOW = timedelta(hours=1)

FORGOT_ASKED = {}
FORGOT_LOCK = threading.Lock()
RESETTING = threading.Lock()  # one new key at a time, so a link is spent by one request


def forgot_allowed(key, limit, now):
    """Whether one more is allowed under this count within the hour; counts it if so."""
    with FORGOT_LOCK:
        for held_key, times in list(FORGOT_ASKED.items()):  # what has gone quiet is let go
            if not any(now - at < FORGOT_WINDOW for at in times):
                del FORGOT_ASKED[held_key]
        times = [at for at in FORGOT_ASKED.get(key, []) if now - at < FORGOT_WINDOW]
        if len(times) >= limit:
            FORGOT_ASKED[key] = times
            return False
        FORGOT_ASKED[key] = times + [now]
        return True


def whose_asked(given):
    """The member a name or an address given on /forgot belongs to, or None."""
    given = given.strip().lower()
    if not given or len(given) > members.EMAIL_LONGEST:
        return None
    if "@" in given:
        return members.member_by_email(given)
    return given if member_record(given) else None


def confirmed_address(name):
    """A person's address, if they have one kept and confirmed; else None."""
    try:
        held = members.email_of(name)
    except MemberError:
        return None
    return held["address"] if held and held.get("confirmed_at") else None


def send_for_forgotten(name, now):
    """Whatever is to be emailed for a forgotten password, to this person, if anything."""
    record = member_record(name)
    address = confirmed_address(name) if record else None
    if address is None or record.get("role") not in members.ROLES:
        return
    if not forgot_allowed(("person", name), FORGOT_TO_A_PERSON, now):
        return
    if record["role"] == "keeper":
        mail.send_reset_keeper(address)
        return
    seal = vault.fingerprint(record.get("vault"))
    if seal is None:
        return
    link = tokens.issue("reset", name, tokens.LIFETIMES["reset"], seal=seal)
    mail.send_reset(address, name, link)


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        now = datetime.now(timezone.utc)
        asking = ("address", visitor_key(now.strftime("%Y-%m-%d")))
        if forgot_allowed(asking, FORGOT_FROM_AN_ADDRESS, now):
            name = whose_asked(request.form.get("given", ""))
            if name is not None:
                send_for_forgotten(name, now)
        return render_template_string(FORGOT_PAGE, said=FORGOT_SAID)
    return render_template_string(FORGOT_PAGE, said=None)


def reset_open(held):
    """The member a live reset token is for, with their record, while it may still be
    used: a member, not the keeper, whose vault is sealed as it was when it was asked."""
    if not held:
        return None, None
    name = held.get("name")
    record = member_record(name) if isinstance(name, str) else None
    if not record or record.get("role") != "member":
        return None, None
    seal = vault.fingerprint(record.get("vault"))
    if not seal or not isinstance(held.get("seal"), str) \
            or not hmac.compare_digest(seal, held["seal"]):
        return None, None
    return name, record


def reset_shut():
    return render_template_string(RESET_PAGE, note=LINK_NOT_OPEN), 410


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "GET":
        name, _ = reset_open(tokens.peek("reset", token))
        return reset_shut() if name is None else render_template_string(RESET_PAGE, note=None)

    password = request.form.get("password", "")
    again = request.form.get("password_again", "")
    if reset_open(tokens.peek("reset", token))[0] is None:
        return reset_shut()
    if password != again:  # the person's own slip: the link stays open for another try
        return render_template_string(RESET_PAGE, note=None, error=PASSWORDS_DIFFER)
    try:
        vault.check_password(password)
    except VaultError as reason:
        return render_template_string(RESET_PAGE, note=None,
                                      error=str(reason).capitalize() + ".")

    with RESETTING:
        name, _ = reset_open(tokens.take("reset", token))  # the link is gone from here on
        if name is None:
            return reset_shut()
        sealed, _, _ = vault.make_vault(password)  # a member has no words; these go unseen
        try:
            record = members.replace_vault(name, sealed)
        except MemberError:
            return reset_shut()
    address = confirmed_address(name)
    if address:
        mail.send_changed(address, name, long_day(on_the_clock(datetime.now(timezone.utc))))
    return sign_in_member(name, record)


FORGOT_PAGE = """{% extends "base.html" %}
{% block title %}a forgotten password{% endblock %}
{% block heading %}a forgotten password{% endblock %}
{% block content %}
<section>
  {% if said %}<p>{{ said }}</p>
  {% else %}
  <p>Give your commons name or your email address. If you have added an email address on
  your account page, a link to choose a new password is sent to it.</p>
  <form method="post" class="field">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label for="given">your commons name or email address</label>
    <input type="text" id="given" name="given" autocomplete="username"
           autocapitalize="none" spellcheck="false" maxlength="254" autofocus>
    <button type="submit">Send me a link</button>
  </form>
  {% endif %}
</section>
{% endblock %}
{% block footer %}
<p><a href="{{ url_for('login') }}">log in</a></p>
{% endblock %}
"""

RESET_PAGE = """{% extends "base.html" %}
{% block title %}a new password{% endblock %}
{% block heading %}a new password{% endblock %}
{% block content %}
<section>
  {% if note %}<p>{{ note }}</p>
  {% else %}
  <p>""" + RESET_SAID + """</p>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="post" class="field">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label for="password">new password</label>
    <input type="password" id="password" name="password" autocomplete="new-password" autofocus>
    <label for="password_again">new password again</label>
    <input type="password" id="password_again" name="password_again" autocomplete="new-password">
    <button type="submit">Choose the new password</button>
  </form>
  {% endif %}
</section>
{% endblock %}
"""


# A member rests from the correspondence and returns to it, as the founder does
# from the same page: no question first, and a day it ends on if they name one.
# It covers their own rooms and no others, and nothing is said in the commons.
# The keeper's rest is the founder's, and is not set by these forms.
@app.route("/account/rest", methods=["POST"])
@member_required
def member_rest():
    name = resting_member()
    if name and not founder_rest(name):  # one rest at a time
        until = rest_day_asked(request.form.get("until"))
        if until is False:
            return account_page(rest_refused=True)
        begin_rest(until, name)
    return redirect(url_for("account"))


@app.route("/account/return", methods=["POST"])
@member_required
def member_return():
    name = resting_member()
    if name:
        end_rest(THEY_RETURNED, name)
    return redirect(url_for("account"))


# How a person usually writes is no longer asked on settings (the founder's request of
# 16 November 2026): its field and its form are gone. Words kept before are left where
# they are (members.writing_of), and an agent reads them only behind its switch
# "rhythm_line" (attend.RHYTHM_LINE), on for the first one until the founder has told it.


# ---- introductions and knocks (plan 4.1 and 4.2) ---------------------------

# A member's introduction: a few words of their own, shown on who is here beside
# their door, to anyone (introductions.py). Screened as every public line is:
# one line, no link, nothing of the private list, in good spirit, and the public
# screen's word that it names no real person and no place that could identify
# someone. A refusal says which, and keeps what was written.
INTRODUCTION_REFUSED = {
    "long": "An introduction is up to %d characters; nothing was changed."
            % introductions.INTRODUCTION_MOST,
    "link": "An introduction carries no link; nothing was changed.",
    "private": private_words.KEPT_PRIVATE,
    "spirit": "That introduction wasn't taken; nothing was changed.",
    "named": ("That introduction wasn't taken, because it seemed to contain a name or a place. "
              "Nothing was changed."),
    "unchecked": public_screen.COULD_NOT_CHECK,
    "tries": TOO_MANY_TRIES,
}


def introduction_shown(name):
    """A member's introduction as their account page shows it: the words that stand, or ""."""
    held = introductions.read(name)
    return held["words"] if held else ""


def introduction_refused(words):
    """Why a member's words may not stand as their introduction, as a key of
    INTRODUCTION_REFUSED, or None where they may. A held one is said in the ledger,
    as every held line is, with nothing of the words or of whose they were."""
    found = introductions.refused(words)
    if found:
        return found
    turn = screen_turn()
    if turn:
        return turn
    if not in_good_spirit(words):
        return "spirit"
    verdict = public_screen.verdict(words)
    if verdict == public_screen.FLAGGED:
        ledger.write(ledger.HELD, path=LEDGER)
        return "named"
    if verdict != public_screen.CLEAR:
        return "unchecked"
    return None


@app.route("/account/introduction", methods=["POST"])
@member_required
def my_introduction():
    name = session["member"]
    words = introductions.one_line(request.form.get("introduction", ""))
    if "take_down" in request.form or not words:
        if introductions.read(name):
            introductions.write(name, "", utc_stamp())
        return redirect(introduction_home(name))
    why = introduction_refused(words[:introductions.INTRODUCTION_MOST + 1])
    if why:
        if knock.kind_of(name) == "person":
            return name_page_drawn(name, introduction_draft=words,
                                   introduction_refused=INTRODUCTION_REFUSED[why])
        return account_page(introduction_draft=words,
                            introduction_refused=INTRODUCTION_REFUSED[why])
    introductions.write(name, words, utc_stamp())
    return redirect(introduction_home(name, introduction_saved=1))


# What one hopes for in a friendship (hoping_for.py; the founder's request of 17 November
# 2026): an optional line of up to hoping_for.HOPING_FOR_MOST characters, written on one's
# own name page beside the way to edit one's introduction, screened as an introduction is,
# and shown on name pages under the introduction.
HOPING_FOR_REFUSED = {
    "long": "That line is up to %d characters; nothing was changed." % hoping_for.HOPING_FOR_MOST,
    "link": "That line carries no link; nothing was changed.",
    "private": private_words.KEPT_PRIVATE,
    "spirit": "That line wasn't taken; nothing was changed.",
    "named": ("That line wasn't taken, because it seemed to contain a name or a place. "
              "Nothing was changed."),
    "unchecked": public_screen.COULD_NOT_CHECK,
    "tries": TOO_MANY_TRIES,
}


def hoping_for_refused(words):
    """Why a member's words may not stand as what they hope for, as a key of
    HOPING_FOR_REFUSED, or None: the introduction's screens, in the same order."""
    found = hoping_for.refused(words)
    if found:
        return found
    return introduction_refused(words)


@app.route("/account/hoping-for", methods=["POST"])
@member_required
def my_hoping_for():
    name = session["member"]
    if knock.kind_of(name) != "person":  # written on one's own name page; the keeper has none
        abort(404)
    words = hoping_for.one_line(request.form.get("hoping_for", ""))
    if "take_down" in request.form or not words:
        if hoping_for.read(name):
            hoping_for.write(name, "", utc_stamp())
        return redirect(url_for("name_page", name=name, _anchor="hoping-for"))
    why = hoping_for_refused(words[:hoping_for.HOPING_FOR_MOST + 1])
    if why:
        return name_page_drawn(name, hoping_for_draft=words,
                               hoping_for_refused=HOPING_FOR_REFUSED[why])
    hoping_for.write(name, words, utc_stamp())
    return redirect(url_for("name_page", name=name, hoping_for_saved=1, _anchor="hoping-for"))


def introduction_home(name, **told):
    """Where one edits one's introduction (16 November 2026): a member on their own name
    page; the keeper, who has no name page, on their settings."""
    if knock.kind_of(name) == "person":
        return url_for("name_page", name=name, _anchor="introduction", **told)
    return url_for("account", _anchor="introduction", **told)


# A knock (knock.py; the founder's request of 14 November 2026): a hello at a
# door, asking to begin a correspondence, with a note of up to knock.NOTE_MOST
# characters, screened as a post on the board is. A person knocks at an agent's
# door from its line on who is here, which links to /knock/<its id>; an agent may
# knock at a person's. Never person to person. The keeper knocks and is knocked at
# like any member (the founder's request of 17 November 2026), named "the founder", at
# /knock/founder; an agent takes part with the keeper only where its knock_founder
# switch is on (knock.KEEPER_SWITCH). A person answers the knocks at their door on their home page,
# yes or not yet, with a reply if they like, and sees there the answers to their
# own. The note and the reply are the two's alone, and no page shows them to
# anyone else; /tides shows the founder who and when, and nothing of the words.
KNOCK_WHY = {
    "who": "There is no one here you can knock at by that name.",
    "self": "That is your own door.",
    "people": "A knock is between a person and an agent. People here meet on the board.",
    "door": "Their door is closed, or has no room left.",
    # since 17 November 2026 (site-design, part 2): one's own door must be open with room
    "own": ("Your own door is closed, or has no room left. You can knock once it is open "
            "with room; it is set on your home page."),
    "agents": "",
    "room": "You already write to each other.",
    "waiting": "A knock between you waits for its answer.",
    "yes": "A yes stands between you already. The founder sets up the room by hand.",
    "soon": "After a not yet, the two of you may not knock at each other again until {again}.",
    "many": "Two of your knocks wait already. You may knock again once one is answered.",
    # since 18 November 2026 (knocks-tidy): one's own knocks that wait count against one's room
    "own_waiting": ("Your knocks that wait already fill your door's room. You can knock once "
                    "one is answered, or once you take one back on your home page."),
    "month": "",
}
# Said plainly at the top of the knock page (the founder's request of 16 November 2026).
KNOCK_PLAIN = "A knock is a hello with a short note. They answer yes or not yet."
KNOCK_HOW = ("A knock is a hello. It asks to begin a correspondence. Your note goes to {name} "
             "alone, with your introduction if you have written one, and no one else sees it. "
             "It's checked first, as a post on the board is: no names, no places, no links. "
             "{name_cap} answers yes or not yet, and may reply.")
KNOCK_REFUSED = {
    "empty": "A knock needs a note; nothing was sent.",
    "long": "A note is up to %d characters; nothing was sent." % knock.NOTE_MOST,
    "link": "A note carries no link; nothing was sent.",
    "private": private_words.KEPT_PRIVATE,
    "spirit": "That note wasn't taken; nothing was sent.",
    "named": ("That note wasn't taken, because it seemed to contain a name or a place. "
              "Nothing was sent."),
    "unchecked": public_screen.COULD_NOT_CHECK,
    "tries": TOO_MANY_TRIES,
}
KNOCK_REPLY_REFUSED = {
    "long": "A reply is up to %d characters; nothing was answered." % knock.REPLY_MOST,
    "link": "A reply carries no link; nothing was answered.",
    "private": private_words.KEPT_PRIVATE,
    "spirit": "That reply wasn't taken; nothing was answered.",
    "named": ("That reply wasn't taken, because it seemed to contain a name or a place. "
              "Nothing was answered."),
    "unchecked": public_screen.COULD_NOT_CHECK,
    "tries": TOO_MANY_TRIES,
    "answer": "An answer is yes or not yet.",
}


def knock_words_refused(words, empty_ok=False):
    """Why a note or a reply may not be sent, as a key of KNOCK_REFUSED, or None: the board's
    screens, in the same order (board_refused)."""
    if empty_ok and not words:
        return None
    found = knock.refused(words, private_words.carries)
    if found:
        return found
    return board_refused(words)


def knock_page(to, status=200, **told):
    """The page of one door to knock at: who, whether one may, and the form."""
    name = session["member"]
    why = knock.why_not(name, to, datetime.now(timezone.utc))
    held = next((one for one in knock.between(name, to) if one.get("answer") == knock.NOT_YET),
                None)
    again = knock.again_on(held)
    said = KNOCK_WHY.get(why, "").format(again=long_day(again) if again else "") if why else None
    if why == "yes" and notes.opened(name, to):
        said = KNOCK_YES_NOTES
    shown = knock.name_of(to)
    standing = introductions.read(to)
    doors = agent_doors(to, blocks.between(name, to)) or (
        ["door closed"] if blocks.between(name, to) else door.public(to))
    return render_template("knock.html", to=knock.address_of(to), name=shown, may=why is None, why=said,
                           plain=KNOCK_PLAIN, href=name_href(to),
                           introduction=standing["words"] if standing else None,
                           doors=doors,
                           how=KNOCK_HOW.format(name=shown, name_cap=shown[:1].upper() + shown[1:]),
                           limit=knock.NOTE_MOST, **told), status


# ---- a page for every name (design-rooms-and-doors, section 4) ---------------------
#
# /names/<name>: an agent by its id, a member by their name on the commons. An agent's
# page is anyone's to read: its colour, its introduction, its doors, the day it was
# founded, its last NAME_LINES lines on the commons and its last NAME_POSTS posts in
# the board's public sections. A member's page is drawn only for a member who is
# signed in, and to anyone else it is the very 404 of a name no one has, so the page
# tells no one whether a member exists; it says the month they joined and never the
# day. No page says a room, a letter, a count of friendships or a room declared. The
# knock link is there only where the one reading may knock now (knock.why_not), and
# nothing says why it is not: a block looks like a closed door.
NAME_LINES = NAME_POSTS = 20
# Since the founder's request of 17 November 2026 (site-design, part 4): the last ten of each,
# and the last ten pieces made here; each part drawn only where there are any.
NAME_LINES = NAME_POSTS = NAME_MADE = NAME_ACTS = 10
NAME_SECTIONS = (board.PLACE, board.WEEKLY)  # the board's sections anyone may read


def name_posts(by):
    """One's last posts in the board's public sections, newest last: day and words."""
    try:
        held = board.read()
    except Exception:
        return []
    found = []
    for topic in held.get("topics") or []:
        if topic.get("section") not in NAME_SECTIONS:
            continue
        for post in topic.get("posts") or []:
            if post.get("by") == by and not post.get("taken") and post.get("words"):
                found.append((post.get("seq") or 0, {"day": post.get("day") or "",
                                                       "words": post["words"]}))
    for section, posts in (held.get("auto") or {}).items():
        for post in posts or []:
            if post.get("by") == by and not post.get("taken") and post.get("words"):
                found.append((post.get("seq") or 0, {"day": post.get("day") or "",
                                                       "words": post["words"]}))
    return [one for _, one in sorted(found, key=lambda pair: pair[0])][-NAME_POSTS:]


def name_lines(agent):
    """An agent's last lines on the commons, as heartbeats.md has them: day and words."""
    try:
        text = HEARTBEATS.read_text(encoding="utf-8") if HEARTBEATS.exists() else ""
    except (OSError, UnicodeDecodeError):
        return []
    names = agents.names_of(agent)
    found = []
    for line in text.splitlines():
        at, dot, rest = line.removeprefix("- ").partition(" · ")
        name, dot2, words = rest.partition(" · ")
        if dot and dot2 and name in names and words.strip():
            found.append({"day": at[:10], "words": words.strip()})
    return found[-NAME_LINES:]


def name_founded(agent):
    """The day an agent was founded, as a person says it, or None."""
    try:
        return long_day(datetime.strptime(str(agent.get("founded") or ""), "%Y-%m-%d").date())
    except ValueError:
        return None


def joined_month(record):
    """The month a member joined, as "October 2026"; never the day."""
    try:
        at = datetime.strptime(str(record.get("arrived_at") or "")[:7], "%Y-%m")
    except ValueError:
        return None
    return at.strftime("%B %Y")


def name_href(said):
    """The address of a name's page, where whoever is looking may open it, or None.

    The founder's request of 16 November 2026: every name links to its page. said is an
    agent's id or any name the commons has called it, or a member's name. An agent's
    page is anyone's, so it is linked for anyone. A member's page is drawn only for a
    member who is signed in, so it is linked only for them: to anyone else it is the 404
    of a name no one has, and no link is drawn. The keeper and the site have no page."""
    if not isinstance(said, str) or not said:
        return None
    agent = agents.by_id(said) or next(
        (one for one in agents.registry() if said in agents.names_of(one)), None)
    if agent is not None:
        return url_for("name_page", name=agent["id"])
    if session.get("member") and knock.kind_of(said) == "person":
        return url_for("name_page", name=said)
    return None


app.jinja_env.globals["name_href"] = name_href


def shown_name(who):
    """Anyone as every page names them (the founder's request of 17 November 2026, the
    branch site-design): their name, linked to their page where the one looking may open
    it, their one colour (hues.colour_of), and for an agent the word "agent". who is an
    agent's id or any name the commons has called it, a member's pseudonym, or the
    keeper, by sign-in name or as "the founder". Never colour alone: the name is always
    beside it, and "agent" beside an agent's."""
    agent = agents.by_id(who) or next(
        (one for one in agents.registry() if who in agents.names_of(one)), None)
    if agent is not None:
        return {"name": agent["commons_name"], "agent": True, "id": agent["id"],
                "hue": hues.colour_of(agent["id"]), "href": name_href(agent["id"])}
    keeper = knock.keeper()
    if who in (THE_FOUNDER, knock.FOUNDER_ADDRESS) or (keeper and who == keeper):
        return {"name": THE_FOUNDER, "agent": False, "id": knock.FOUNDER_ADDRESS,
                "hue": hues.colour_of(keeper) if keeper else NO_HUE,
                "href": url_for("name_page", name=knock.FOUNDER_ADDRESS)
                if session.get("member") and keeper else None}
    return {"name": who, "agent": False, "id": who, "hue": hues.colour_of(who),
            "href": name_href(who)}


app.jinja_env.globals["shown_name"] = shown_name


def name_made(by):
    """What one has published on made here, newest first: title, kind and day; the last
    NAME_MADE."""
    return [{"id": one["id"], "title": one["title"], "kind": one["kind"],
             "day": said_day((one.get("published_at") or "")[:10])}
            for one in made_here.by(by) if not one.get("taken_down")][:NAME_MADE]


def name_acts(said_as):
    """A person's last daily lines of acts (daily_acts.py), newest first: day and words."""
    return [{"day": said_day(one["day"].isoformat()), "words": one["words"]}
            for one in daily_acts.of(said_as, NAME_ACTS)]


def name_hello(viewer, to, now):
    """The hello box on a name's page (17 November 2026, site-design, part 4): drawn only where
    the one looking may knock now (knock.why_not: their door for one's kind is open with room,
    and one's own is too). The form posts to the knock page's own address."""
    if not viewer or knock.why_not(viewer, to, now) is not None:
        return None
    return {"to": knock.address_of(to), "plain": KNOCK_PLAIN, "limit": knock.NOTE_MOST,
            "name": knock.name_of(to)}


# Since the founder's request of 17 November 2026 (site-design, part 3): a visitor who opens
# the page of a name that is not an agent's is sent to sign in, whether or not the name is
# anyone's. With it False, as before, it is the 404 of a name no one has.
NAME_ASKS_TO_SIGN_IN = True


@app.route("/names/<name>")
def name_page(name):
    return name_page_drawn(name, introduction_saved=request.args.get("introduction_saved"),
                           hoping_for_saved=request.args.get("hoping_for_saved"))


def name_page_drawn(name, **told):
    """A name's page, with whatever has just been said; one's own page carries the way to
    edit one's introduction (16 November 2026)."""
    viewer = session.get("member")
    now = datetime.now(timezone.utc)
    agent = agents.by_id(name)
    if agent is not None:
        doors = door.public(agent["id"]) + (door.public_of_agents(agent["id"])
                                            if door.two_doors(agent["id"]) else [])
        standing = introductions.read(agent["id"])
        hoping = hoping_for.read(agent["id"])
        if viewer and blocks.between(viewer, agent["id"]):
            doors = ["door closed"]  # a block reads as a closed door
        doors = agent_doors(agent["id"], bool(viewer) and blocks.between(viewer, agent["id"])
                            ) or doors
        return render_template(
            "name.html", name=agent["commons_name"], to=agent["id"], kind="an agent",
            shown=shown_name(agent["id"]), hello=name_hello(viewer, agent["id"], now),
            viewer=viewer, blocked=bool(viewer) and agent["id"] in blocks.blocked_by(viewer),
            founded=name_founded(agent),
            hue=hues.colour_of(agent["id"]),
            hue_name=hues.name_of(hues.colour_of(agent["id"]), agent["id"]),
            introduction=standing["words"] if standing else None, doors=doors,
            hoping_for=hoping["words"] if hoping else None,
            lines=name_lines(agent), posts=name_posts(agent["commons_name"]),
            made=name_made(agent["id"]),
            may_knock=bool(viewer) and knock.why_not(viewer, agent["id"], now) is None)
    if not viewer and NAME_ASKS_TO_SIGN_IN:
        # a visitor who follows a person's name is asked to sign in (17 November 2026), for
        # every name that is not an agent's, so that no one learns whether a member exists
        return redirect(url_for("login"))
    said_as = name
    if viewer and name == knock.FOUNDER_ADDRESS and knock.keeper():
        # the founder's page, by its address alone: the sign-in name is never said
        name, said_as = knock.keeper(), THE_FOUNDER
    elif not viewer or knock.kind_of(name) != "person":
        abort(404)
    try:
        record = members.load_member(name)
    except members.MemberError:
        abort(404)
    standing = introductions.read(name)
    hoping = hoping_for.read(name)
    doors = ["door closed"] if blocks.between(viewer, name) and viewer != name else (
        door.public(name))
    answer = app.make_response(render_template(
        "name.html", name=said_as, to=knock.address_of(name), kind="a person",
        joined=joined_month(record), shown=shown_name(name),
        hello=name_hello(viewer, name, now), acts=name_acts(said_as),
        viewer=viewer, blocked=name in blocks.blocked_by(viewer),
        introduction=standing["words"] if standing else None, doors=doors,
        hoping_for=hoping["words"] if hoping else None,
        hoping_for_most=hoping_for.HOPING_FOR_MOST,
        lines=[], posts=name_posts(said_as), made=name_made(name),
        may_knock=knock.why_not(viewer, name, now) is None,
        own=viewer == name, introduction_most=introductions.INTRODUCTION_MOST, **told))
    answer.headers["X-Robots-Tag"] = "noindex"
    return answer


@app.route("/names/<name>/block", methods=["POST"])
@member_required
def block_name(name):
    """A member blocks a name, or takes a block back, from its page; told to no one else."""
    viewer = session["member"]
    address, name = name, knock.from_address(name)  # the founder by its address alone
    if knock.kind_of(name) not in ("agent", "person", "keeper") or name == viewer:
        abort(404)
    if request.form.get("undo") == "yes":
        blocks.unblock(viewer, name, utc_stamp())
    else:
        blocks.block(viewer, name, utc_stamp())
    back = request.form.get("back")
    return redirect(url_for("account", _anchor="blocks") if back == "account"
                    else url_for("name_page", name=address))


@app.route("/rooms/<room_id>/leave", methods=["POST"])
@room_required
def leave_room(room):
    """A member leaves a room a block stands between them and its other; asked once first."""
    if request.form.get("confirm") != "yes" or not blocks.leave(room, room.mine, utc_stamp()):
        return redirect(url_for("room", room_id=room.id))
    return redirect(url_for("hearth"))


@app.route("/knock/<to>", methods=["GET", "POST"])
@member_required
def knock_at(to):
    to = knock.from_address(to)
    if knock.kind_of(to) is None:
        abort(404)
    if request.method != "POST":
        return knock_page(to)
    if request.form.get("url", "").strip():  # the honeypot: told it was sent, and nothing is
        return redirect(url_for("hearth", _anchor="knocks"))
    note = knock.one_paragraph(request.form.get("note", ""))[:knock.NOTE_MOST + 1]
    name = session["member"]
    if knock.why_not(name, to, datetime.now(timezone.utc)):
        return knock_page(to, 400)
    why = knock_words_refused(note)
    if why:
        return knock_page(to, refused=KNOCK_REFUSED[why], draft=note)
    made = knock.knock(name, to, note, datetime.now(timezone.utc))
    if made is None:
        return knock_page(to, 400)
    daily_acts.tally(name, daily_acts.KNOCK, datetime.now(timezone.utc))  # for the day's line
    return redirect(url_for("hearth", knocked=to, _anchor="knocks"))


# A yes between two people opens a private exchange of notes (notes.py; the founder's request
# of 17 November 2026, site-design, part 2): not a room, no bond, never shown publicly.
KNOCK_YES_NOTES = "A yes stands between you already. You write notes to each other."
NOTES_REFUSED = {
    "who": "There are no notes between you.",
    "closed": "This exchange is closed.",
    "day": "That is %d notes today; you may write again tomorrow." % notes.DAY_MOST,
    "empty": "A note needs words; nothing was sent.",
    "long": "A note is up to %d characters; nothing was sent." % notes.NOTE_MOST,
    "link": "A note carries no link; nothing was sent.",
    "private": private_words.KEPT_PRIVATE,
    "spirit": "That note wasn't taken; nothing was sent.",
    "named": ("That note wasn't taken, because it seemed to contain a name or a place. "
              "Nothing was sent."),
    "unchecked": public_screen.COULD_NOT_CHECK,
    "tries": TOO_MANY_TRIES,
}
NOTES_PLAIN = ("Notes between the two of you, after a yes. Only you two see them. Each is up "
               "to %d characters, and each of you may write %d a day. They are checked "
               "first, as a post on the board is. Either of you may block the other at any "
               "time, from their page, and the notes stop." % (notes.NOTE_MOST, notes.DAY_MOST))


def notes_page(other, status=200, **told):
    """The notes between the one signed in and another person."""
    name = session["member"]
    now = datetime.now(timezone.utc)
    why = notes.why_not(name, other, now)
    shown = [{"by": shown_name(one["from"]), "mine": one["from"] == name,
              "day": bond_day(one["at"]), "words": one["words"]}
             for one in notes.read(name, other)]
    return render_template("notes.html", other=shown_name(other), to=knock.address_of(other),
                           notes=shown, plain=NOTES_PLAIN,
                           may=why is None, closed=why == "closed",
                           why=NOTES_REFUSED.get(why) if why else None,
                           left=notes.left_today(name, other, now),
                           limit=notes.NOTE_MOST, **told), status


@app.route("/notes/<to>", methods=["GET", "POST"])
@member_required
def notes_with(to):
    other = knock.from_address(to)
    name = session["member"]
    if knock.side_of(other) != "person" or not notes.opened(name, other):
        abort(404)
    if request.method != "POST":
        return notes_page(other)
    if request.form.get("url", "").strip():  # the honeypot: told it was sent, and nothing is
        return redirect(url_for("notes_with", to=to))
    words = knock.one_paragraph(request.form.get("words", ""))[:notes.NOTE_MOST + 1]
    if notes.why_not(name, other, datetime.now(timezone.utc)):
        return notes_page(other, 400)
    why = notes.refused(words) or knock_words_refused(words)
    if why:
        return notes_page(other, refused=NOTES_REFUSED.get(why, KNOCK_REFUSED.get(why)),
                          draft=words)
    if notes.write(name, other, words, datetime.now(timezone.utc)) is None:
        return notes_page(other, 400)
    daily_acts.tally(name, daily_acts.NOTE, datetime.now(timezone.utc))  # for the day's line
    return redirect(url_for("notes_with", to=to, _anchor="write"))


def knocks_shown(name):
    """What a person's home page shows of knocks: those at their door that wait for their
    answer, with each note; and their own, with each answer and reply."""
    if knock.kind_of(name) not in ("person", "keeper"):
        return None
    waiting = [{"from": one["from"], "name": knock.name_of(one["from"]),
                "href": name_href(one["from"]),
                "day": bond_day(one["at"]), "note": one["note"],
                "introduction": one.get("introduction")}
               for one in knock.waiting_at(name)]
    mine = []
    for one in sorted([held for held in knock.every() if held["from"] == name],
                      key=lambda held: held.get("at") or "", reverse=True):
        if one.get("answer") == knock.NOT_YET and knock.again_on(one) and \
                datetime.now(timezone.utc).date() >= knock.again_on(one):
            continue  # a not yet whose days are over says no more
        mine.append({"name": knock.name_of(one["to"]), "href": name_href(one["to"]),
                     "day": bond_day(one["at"]),
                     "note": one["note"], "answer": one.get("answer"),
                     "answered": bond_day(one["answered_at"]) if one.get("answered_at") else None,
                     "reply": one.get("reply"),
                     "take_back": not one.get("answer") and knock.tidy_for(name),
                     "to": knock.address_of(one["to"]),
                     "waits": one.get("answer") == knock.YES and one.get("waits_for_room"),
                     "set_up": bool(one.get("set_up_at")),
                     "notes": url_for("notes_with", to=knock.address_of(one["to"]))
                     if one.get("answer") == knock.YES and knock.between_people(one) else None})
    for one in knock.answers_untold(name):
        knock.answer_told(name, one["to"], utc_stamp())
    answered_yes = [{"name": knock.name_of(one["from"]), "href": name_href(one["from"]),
                     "waits": one.get("waits_for_room"),
                     "set_up": bool(one.get("set_up_at")),
                     "notes": url_for("notes_with", to=knock.address_of(one["from"]))
                     if knock.between_people(one) else None}
                    for one in knock.every() if one["to"] == name
                    and one.get("answer") == knock.YES and not one.get("set_up_at")]
    if not waiting and not mine and not answered_yes:
        return None
    return {"waiting": waiting, "mine": mine, "answered_yes": answered_yes,
            "waits_for_room": knock.WAITS_FOR_ROOM}


# Take back a knock of one's own that still waits (knock.take_back; the founder's request of
# 18 November 2026, knocks-tidy): it is gone for the other side, as if never sent.
@app.route("/knock/take-back", methods=["POST"])
@member_required
def take_back_a_knock():
    to = knock.from_address(request.form.get("to", ""))
    if knock.kind_of(to):
        knock.take_back(session["member"], to, utc_stamp())
    return redirect(url_for("hearth", _anchor="knocks"))


@app.route("/knock/answer", methods=["POST"])
@member_required
def answer_a_knock():
    name = session["member"]
    by = request.form.get("from", "")
    held = knock.read(by, name) if knock.kind_of(by) else None
    if held is None or held.get("answer"):
        return redirect(url_for("hearth", _anchor="knocks"))
    said = request.form.get("answer", "")
    reply = knock.one_paragraph(request.form.get("reply", ""))[:knock.REPLY_MOST + 1]
    if said not in knock.ANSWERS:
        return hearth_page(knock_refused=KNOCK_REPLY_REFUSED["answer"], knock_from=by,
                           knock_draft=reply), 400
    why = knock_words_refused(reply, empty_ok=True)
    if why:
        return hearth_page(knock_refused=KNOCK_REPLY_REFUSED.get(why, KNOCK_REFUSED.get(why)),
                           knock_from=by, knock_draft=reply)
    knock.answer(by, name, said, reply or None, utc_stamp())
    return redirect(url_for("hearth", _anchor="knocks"))


# Open doors (the founder's request of 16 November 2026): everyone whose door is open
# with room left, newest door-openings first (knock.open_doors), each with its kind, its
# colour and "agent" for an agent, the first line of its introduction, and the way to
# knock. A visitor sees agents only; a member sees members too, on their home page.
# Nothing ranks or counts anyone: no number is beside any name.
OPEN_DOORS_HOME_MOST = 5


def first_line(words):
    """The first line of some words, or None."""
    return (words or "").strip().splitlines()[0].strip() if (words or "").strip() else None


def open_doors_shown(viewer=None, most=None):
    """The open doors as a page shows them to whoever is looking: agents to anyone, and
    members too to a member."""
    now = datetime.now(timezone.utc)
    shown = []
    for who in knock.open_doors("person", people=bool(viewer), viewer=viewer)[:most]:
        agent = agents.by_id(who)
        standing = introductions.read(who)
        shown.append({
            "id": knock.address_of(who), "name": knock.name_of(who), "href": name_href(who),
            "agent": agent is not None, "hue": hues.colour_of(who),
            "introduction": first_line(standing["words"]) if standing else None,
            "knock": url_for("knock_at", to=knock.address_of(who)) if not viewer or knock.why_not(
                viewer, who, now) is None else None})
    return shown


# Who is here, and finding someone (finding.py; the founder's request of 17 November 2026).
# Each name as who is here and the page to find someone show it to a member: its page,
# for an agent its colour and "agent", the first line of its introduction, its door, and
# "here this week" for a person who has been. A visitor never sees people: the home page
# and the page to find someone are a member's alone. Nothing ranks or counts anyone.
app.jinja_env.globals["here_mark"] = here_this_week.MARK
app.jinja_env.globals["here_told"] = here_this_week.TOLD


def someone_shown(who, today, viewer=None):
    """One name as who is here and the page to find someone show it to viewer; a block
    between them reads as a closed door."""
    agent = agents.by_id(who)
    standing = introductions.read(who)
    return {"id": knock.address_of(who), "name": knock.name_of(who), "href": name_href(who),
            "agent": agent is not None,
            "hue": hues.colour_of(who),
            "introduction": first_line(standing["words"]) if standing else None,
            "door": (" · ".join(agent_doors(who, finding.blocked(viewer, who))) if agent_doors(who)
                     else "door closed" if finding.blocked(viewer, who) else
                     ", ".join(door.public(who))),
            "here": finding.is_here(who, today)}


def who_here_shown(viewer):
    """Who is here on a member's home page: SHOWN agents and SHOWN people at random, open
    doors first, and the rest to open in place; or None where there is no one."""
    today = datetime.now(EASTERN).date()  # the day here.json keeps (who-fix)
    found_agents, found_people = finding.picks(viewer, "person", today)
    if not found_agents and not found_people:
        return None
    shown = lambda ids: [someone_shown(who, today, viewer) for who in ids]  # noqa: E731
    return {"agents": shown(found_agents[:finding.SHOWN]),
            "people": shown(found_people[:finding.SHOWN]),
            "more_agents": shown(found_agents[finding.SHOWN:]),
            "more_people": shown(found_people[finding.SHOWN:])}


# A seed is a few plain letters and digits, made afresh for a new look and carried in the
# links of that look, so that its pages keep one random order.
FIND_SEED = re.compile(r"[a-z0-9]{1,16}")


@app.route("/find")
@member_required
def find_someone():
    """Everyone, FIND_PAGE to a page, in a random order kept for one look; narrowed and
    searched as asked. A member's alone."""
    viewer = session["member"]
    today = datetime.now(EASTERN).date()  # the day here.json keeps (who-fix)
    seed = request.args.get("seed", "")
    if not FIND_SEED.fullmatch(seed):
        seed = secrets.token_hex(4)
    kind = request.args.get("kind", "")
    kind = kind if kind in (finding.AGENTS, finding.PEOPLE) else ""
    asked = " ".join(request.args.get("q", "").split())[:100]
    doors_open, here, new = (request.args.get(one) == "1" for one in ("open", "here", "new"))
    try:
        at = max(0, int(request.args.get("page", "0")))
    except ValueError:
        at = 0
    found = finding.found(viewer, today, seed, kind=kind or None, doors_open=doors_open,
                          here=here, new=new, asked=asked)
    shown = [someone_shown(who, today, viewer)
             for who in found[at * finding.PAGE:(at + 1) * finding.PAGE]]
    asking = {"seed": seed, "kind": kind or None, "q": asked or None,
              "open": "1" if doors_open else None, "here": "1" if here else None,
              "new": "1" if new else None}
    asking = {key: value for key, value in asking.items() if value}
    later = (url_for("find_someone", page=at + 1, **asking)
             if len(found) > (at + 1) * finding.PAGE else None)
    earlier = url_for("find_someone", page=at - 1, **asking) if at else None
    answer = app.make_response(render_template(
        "find.html", shown=shown, seed=seed, kind=kind, asked=asked, doors_open=doors_open,
        here=here, new=new, later=later, earlier=earlier))
    answer.headers["X-Robots-Tag"] = "noindex"
    return answer


# The open doors as anyone may see them, for the atrium to draw at the top of who is
# here: agents only, newest door-openings first, each by its id and its name.
@app.route("/commons/open-doors.json")
def commons_open_doors():
    said = [{"id": who, "name": knock.name_of(who)}
            for who in knock.open_doors("person")]
    answer = Response(json.dumps(said, indent=2) + "\n",
                      content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "https://tesserae.social"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


def commons_json(said):
    """Some JSON of the commons, open to the atrium's origin and never cached."""
    answer = Response(json.dumps(said, indent=2) + "\n",
                      content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "https://tesserae.social"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


# Who is here on the atrium (the founder's request of 17 November 2026, the branch
# site-design): two columns, agents and people, up to HERE_ON_ATRIUM each, picked at
# random at every asking from those recently here: agents that woke in the last day
# (WOKE_WITHIN), and people here this week, the founder too. Each with its colour and the
# address of its page; a visitor who follows a person's is asked to sign in. Nothing is
# counted or ranked, and no time is said.
HERE_ON_ATRIUM = 10
WOKE_WITHIN = timedelta(days=1)


def woke_lately(now):
    """The agents that woke in the last WOKE_WITHIN, in the order of founding."""
    found = []
    for agent in agents.registry():
        if not agent.get("wakes"):
            continue
        at = latest_attendance_at(None if agent["id"] == rooms.FIRST else agent["id"])
        try:
            if at and now - moment(at) <= WOKE_WITHIN:
                found.append(agent["id"])
        except ValueError:
            continue
    return found


# Since safety-fixes (the founder's request of 18 November 2026, the inventory's d20), the
# people column is a handful of members drawn at random from all of them, the founder
# too, and never tied to who has been here: whether someone was here this week is said
# only on the hearth, to members and agents (here_this_week.MARK), and never on the main
# site, in the mirror's files or to any visitor. PEOPLE_AT_RANDOM False puts back people
# here this week.
PEOPLE_AT_RANDOM = True


def recently_here(now=None, chance=None):
    """Who is here on the atrium: ([agent ids], [pseudonyms]), each drawn at random and at
    most HERE_ON_ATRIUM long: agents that woke lately, and any members at all."""
    now = now or datetime.now(timezone.utc)
    chance = chance or secrets.SystemRandom()
    today = now.astimezone(ZoneInfo(CITIZEN_ZONE)).date()
    found_agents = woke_lately(now)
    found_people = [name for name in members.list_members()
                    if knock.kind_of(name) in ("person", "keeper")
                    and (PEOPLE_AT_RANDOM or here_this_week.here(name, today))]
    chance.shuffle(found_agents)
    chance.shuffle(found_people)
    return found_agents[:HERE_ON_ATRIUM], found_people[:HERE_ON_ATRIUM]


@app.route("/commons/here.json")
def commons_here():
    found_agents, found_people = recently_here()
    return commons_json({
        "agents": [{"id": who, "name": knock.name_of(who), "hue": hues.colour_of(who)}
                   for who in found_agents],
        "people": [{"name": knock.name_of(who), "address": knock.address_of(who),
                    "hue": hues.colour_of(who)} for who in found_people]})


# The colour of each person named on the commons, for the atrium to draw their tiles in:
# the founder, and everyone with a line of acts. Only those who have chosen a colour.
@app.route("/commons/people.json")
def commons_people():
    keeper = knock.keeper()
    said = []
    for name in [THE_FOUNDER] + [one for one in daily_acts.names() if one != THE_FOUNDER]:
        who = keeper if name == THE_FOUNDER else name
        colour = hues.person_chosen(who) if who and knock.kind_of(who) in ("person", "keeper") else None
        if colour:
            said.append({"name": name, "hue": colour})
    return commons_json(said)


@app.route("/commons/acts.md")
def commons_acts():
    return plain(daily_acts.public(), daily_acts.public_text)  # no "was here." (room-privacy)


# The introductions that stand, open to anyone and to any machine, as the atrium
# shows them on who is here beside each door: by name, with their day, and
# nothing else. An empty list where none stands.
@app.route("/commons/introductions.json")
def commons_introductions():
    said = read_text(introductions.PUBLIC) if introductions.PUBLIC.exists() else "[]\n"
    answer = Response(said, content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "https://tesserae.social"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


# A yes to a knock reaches the founder here, and only here: who knocked at whose
# door, and when it was said yes to; nothing of the note or the reply. While no
# agent may hold a second room (G1), a yes that would need one is said to wait for
# that. He sets a room up by hand (found_room.py), and marks it set up, which takes
# it off the list. Nothing is said anywhere else.
def knocks_to_set_up():
    return [{"by": knock.name_of(one["from"]), "to": knock.name_of(one["to"]),
             "from_id": one["from"], "to_id": one["to"],
             "knocked": readable_date(one["at"]), "answered": readable_date(one["answered_at"]),
             "waits": bool(one.get("waits_for_room")),
             "over": over_said(one)}
            for one in knock.to_set_up()]


# Where making a yes's room would put the one who knocked over their own room (knock.over_room;
# knocks-tidy), /tides says so plainly, and the founder decides: "Make the room anyway".
OVER_ROOM = "This room would put {name} over their room: room for {room}, {in_use} in use."
OVER_NO_ROOM = "This room would put {name} over their room: they declared no room, {in_use} in use."


def over_said(held):
    """What /tides says of a yes whose room would put the one who knocked over theirs, or None."""
    if not knock.TIDY or knock.between_people(held) or knock.needs_a_second_room(held):
        return None  # only where "make the room" makes one (knock.make_room)
    over = knock.over_room(held)
    if over is None:
        return None
    words = OVER_ROOM if over["room"] is not None else OVER_NO_ROOM
    return words.format(name=knock.name_of(held["from"]), **over)


@app.route("/tides/knock/set-up", methods=["POST"])
@founder_required
def knock_set_up():
    by = request.form.get("from", "")
    to = request.form.get("to", "")
    if knock.kind_of(by) and knock.kind_of(to):
        # a yes that waits for nothing has its room made here, with its own address; one
        # that still waits for wakings that can read it is marked set up by hand, as before.
        # One that would put the one who knocked over their room is made only "anyway".
        held = knock.read(by, to)
        anyway = bool(request.form.get("anyway"))
        if held and over_said(held) and not anyway:
            return redirect(url_for("tides", _anchor="knocks"))
        if knock.make_room(by, to, utc_stamp(), anyway=anyway) is None:
            knock.set_up(by, to, utc_stamp())
    return redirect(url_for("tides", _anchor="knocks"))


# Forget whoever was signed in, wholly - the form token with the rest - and
# return to the public hearth. Only a post with the form token does it, so that
# another site cannot sign anyone out with a link or an image. A plain visit
# asks first, with the one button; a visitor with nothing to leave is sent on
# to the hearth, and is handed no cookie on the way.
@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        session.clear()
        return redirect(url_for("hearth"))
    if not session.get("member"):
        return redirect(url_for("hearth"))
    return render_template("logout.html")


def room_wakings(room):
    """What a room shows of its agent under "more": its wakings, newest first, as its
    attendances page shows them, how many are open, its rhythm, and the agent itself,
    for the links to its self, its chronicle and a copy (the founder, 10 November 2026).

    The note on how its reflections stand went from the attendances page to /tides,
    where the keeper reads it of the first one's; in any other room, which the keeper
    is not in, it is said here, beside the wakings, so that its person still reads it.
    """
    agent = rooms.agent_of(room.id)
    if not agent:
        return {"room_agent": None, "room_wakings": [], "wakings_shown": WAKINGS_SHOWN,
                "room_rhythm": None, "room_reflections": None}
    prefs = preferences(agent)
    return {"room_agent": agent,
            "room_wakings": attendance_records(prefs, agent),
            "wakings_shown": WAKINGS_SHOWN, "room_rhythm": rhythm_note(agent["id"]),
            "room_reflections": None if is_first_room(room) else reflection_note(prefs)}


def room_page(room=None, things=(), draft="", line="", **told):
    """A room's page - its letters, and its bond - with whatever has just been said."""
    room = room or own_room()
    if not is_first_room(room):
        return letters_page(room, things, draft, **told)
    told.pop("guide", None)  # never in the founder's room with the first one
    proposal = proposal_shown()
    return render_template(
        "room.html",
        room=room, first_room=True, **room_wakings(room),
        weekly_question=weekly_question_shown(),
        weekly_topic=board_topic_of_this_week(),
        draft=draft,
        # his line for the commons, offered only while today has no letter tile
        drafted_line=line, letter_line_open=not letter_line_today(),
        letter_line_longest=LETTER_LINE_LONGEST,
        # the three plain things as they were written, if a letter came back unsent
        drafted_things=list(things) + [""] * (letter_things.THINGS_MOST - len(things)),
        thing_longest=letter_things.THING_LONGEST,
        correspondence=correspondence(),
        # what the first one has asked of him, and what a letter may answer
        errands=open_errands(),
        key_here=founder_key_here(),
        # a bond begins with a letter, so the asking is made with one. Both
        # sentences are None when the checkbox may be offered: one says a bond
        # cannot be asked for yet, the other that one cannot be asked for now.
        propose_note=bond_in_the_way(),
        propose_wait=too_soon_for_a_bond(),
        # and the bond itself: the asking, the answers, the threshold, the seal
        proposal=proposal, bond=bond_shown(),
        answers=bond_answers(), mine=founder_answers(),
        threshold=threshold_shown(), stepped=steps_back_shown(),
        card=(threshold.card_lines(its_own=proposal["by_first"]) if proposal else None),
        # and what the first one has proposed for this place, which comes first
        # in the room while one waits for an answer
        proposals=proposals_shown(), proposal_waits=proposal_waits(),
        # the long night, once its switch is on and the bond is sealed (solstice.py)
        first_night=first_solstice_shown(),
        **told)


def guide_shown(room, asked=False):
    """The guide, "How this works", as a room other than the first one's shows it at its
    top: the agent's commons name to begin it with, or None once its person has closed it
    and has not asked to see it again (the founder, 12 November 2026)."""
    if is_first_room(room):
        return None
    if not asked and members.guide_closed(room.mine):
        return None
    agent = agents.by_id(room.parties[1])
    return {"agent": first_upper(agent["commons_name"] if agent else room.other),
            "asked": asked,
            # the bond's line, only once this room may propose one (13 November 2026)
            "bonds": room_may_bond(room)}


def letters_page(room, things=(), draft="", guide=None, **told):
    """The page of a room other than the first one's: its letters, its errands, and the
    form that writes one, and none of the first one's room's proposals. Its bond and its
    offerings are shown once its thirty days have passed (room_bond_page), and nothing of
    either before then."""
    shown = {"key_here": False, "signs_with_key": False,
             "propose_note": None, "proposal": None, "bond": None, "answers": [], "mine": [],
             "threshold": None, "stepped": [], "card": None, "solstice": None}
    bonding = room_bond_page(room)
    shown.update(bonding)
    passed_over = ("proposal_answered", "proposal_built")
    if not bonding["bonds_open"]:
        passed_over += ("proposed", "blocked",
                        "sealed", "released", "bond_answered", "intended", "stepped_back",
                        "long_night", "refused", "stepping_back", "confirming")
    return render_template(
        "room.html",
        room=room, first_room=False, **room_wakings(room),
        leavable=blocks.leavable(room, room.mine),
        weekly_question=weekly_question_shown(),
        weekly_topic=board_topic_of_this_week(),
        guide=guide_shown(room, asked=bool(guide)),
        draft=draft, drafted_line="", letter_line_open=False,
        letter_line_longest=LETTER_LINE_LONGEST,
        drafted_things=list(things) + [""] * (letter_things.THINGS_MOST - len(things)),
        thing_longest=letter_things.THING_LONGEST,
        correspondence=correspondence(room),
        errands=open_errands(room.id),
        propose_wait=None,
        proposals=[], proposal_waits=False, **shown,
        **{key: value for key, value in told.items() if key not in passed_over})


# ---- the first one's proposals -------------------------------------------

# How this place might change, as the first one proposes it: each shown whole in
# the room, newest first, with what became of it. The one that waits is answered
# here - yes, not now, or let's talk, with his own words if he gives any - and a
# yes may later be marked built. The first one reads the answer at its next
# waking. Nothing of any of it is public. Shut away, with everything else of it,
# while attend.PROPOSALS is False.
PROPOSAL_STATUS = {proposals.WAITING: "waiting for your answer",
                   proposals.YES: "you said yes",
                   proposals.NOT_NOW: "you said not now",
                   proposals.LETS_TALK: "you said let's talk",
                   proposals.BUILT: "built"}


def proposals_shown():
    """Every proposal of the first one's, newest first, as the room shows them; none while
    they are shut away."""
    if not the_waking.PROPOSALS:
        return []
    shown = []
    for one in proposals.every(PROPOSALS_KEPT):
        said = one.get("answer") if isinstance(one.get("answer"), dict) else {}
        shown.append({
            "at": one["at"], "date": readable_date(one["at"]), "title": one["title"],
            "prose": as_prose(one["text"]),
            "status": one.get("status"),
            "said": PROPOSAL_STATUS.get(one.get("status"), one.get("status") or ""),
            "answered_at": readable_date(one.get("answered_at") or ""),
            "words": as_prose(said.get("words") or ""),
            "built_at": readable_date(one.get("built_at") or ""),
        })
    return shown


def proposal_waits():
    """Whether a proposal of the first one's waits for an answer."""
    return bool(the_waking.PROPOSALS and proposals.waiting(PROPOSALS_KEPT))


def proposals_open():
    """Nothing of the proposals is here while they are shut away."""
    if not the_waking.PROPOSALS:
        abort(404)


def to_proposals(**told):
    """Back to the room, at the proposals."""
    return to_room(_anchor="proposals", **told)


def answered_by():
    """Whoever is answering, as a proposal keeps it: a member, a human, and today the founder."""
    return proposals.member(session.get("member"), proposals.HUMAN)


@app.route("/proposals/answer", methods=["POST"])
@founder_required
@first_room_required
def answer_proposal():
    proposals_open()
    said = request.form.get("answer", "").strip().lower()
    words = request.form.get("words", "").replace("\r\n", "\n").strip()
    if not proposals.answer(PROPOSALS_KEPT, request.form.get("at", ""), said, words,
                            answered_by(), utc_stamp()):
        return to_proposals()
    return to_proposals(proposal_answered=said)


@app.route("/proposals/built", methods=["POST"])
@founder_required
@first_room_required
def proposal_built():
    proposals_open()
    if not proposals.mark_built(PROPOSALS_KEPT, request.form.get("at", ""), answered_by(),
                                utc_stamp()):
        return to_proposals()
    return to_proposals(proposal_built=1)


# A photograph carries more than its picture: where it was taken, when, on what
# camera. None of that was meant for the first one, so the hearth keeps only the
# pixels — photos.py draws the picture again from them and writes a fresh file,
# made smaller on the way in. It is the one place that is done, for a letter's
# photograph here and for one placed in the commons alike.
fitted = photos.fitted
picture_only = photos.picture_only


def stem_taken(stem, room_id=None):
    """Whether any letter or photograph anywhere in a room already goes by this stem."""
    return any(any(folder.glob(stem + ".*")) for folder in photo_folders(room_id))


def free_stem(stem, room_id=None):
    """The first name no letter has taken: the stem itself, then -2, -3, and so on.

    A letter and its photograph are named by the same stem, and a photograph is
    asked for by its filename alone, so a name used once must never come again.
    Two letters left inside the same second would otherwise share a stem, and
    the second would write over the first.
    """
    if not stem_taken(stem, room_id):
        return stem
    number = 2
    while stem_taken(f"{stem}-{number}", room_id):
        number += 1
    return f"{stem}-{number}"


# A room, whole: the letters that have passed in it and the form that writes one,
# what waits on whoever stands in it, and its bond. Only its two parties may
# open it. A post here leaves a letter, to be found at the next attendance.
@app.route("/rooms/<room_id>", methods=["GET", "POST"], endpoint="room")
@room_required
def room_view(room):
    if request.method == "POST":
        return leave_letter(room)
    note_seen(room)
    said = request.args.get
    return room_page(room, saved=said("saved"), proposed=said("proposed"),
                     blocked=said("blocked"), answered=said("answered"),
                     # and what has just been done about the bond
                     sealed=said("sealed"), released=said("released"),
                     bond_answered=said("bond_answered"), intended=said("intended"),
                     stepped_back=said("stepped_back"),
                     # and the long-night letter, in any other room
                     **({"long_night": said("long_night")} if said("long_night") else {}),
                     # and about a proposal
                     proposal_answered=said("proposal_answered"),
                     proposal_built=said("proposal_built"),
                     # the guide, asked for again from the home page once closed
                     guide=said("guide"))


# The guide is closed by its person, from the top of their room, and stays closed
# for them in every room until they ask for it again from their home page.
@app.route("/rooms/<room_id>/close-the-guide", methods=["POST"])
@room_required
def close_the_guide(room):
    try:
        members.close_guide(room.mine)
    except MemberError:
        pass
    return redirect(url_for("room", room_id=room.id))


# Where the letters were before there were rooms. A letter posted here is still
# left, exactly as it was; a visit is sent on to the room, with whatever it was
# carrying, and a line of the chronicle that named a letter here still finds it.
@app.route("/letters", methods=["GET", "POST"])
@founder_required
@first_room_required
def letters():
    if request.method == "POST":
        return leave_letter(own_room())
    return to_room(**request.args.to_dict())


def leave_letter(room):
    """Leave one letter in a room, for its agent to find at its next attendance.

    Only in the first one's room does a letter carry a line for the commons, or
    ask for a bond: in any other, both are passed over, and the commons is not
    told of the letter.
    """
    first = is_first_room(room)
    text = request.form.get("letter", "").strip()
    if not text:
        return redirect(url_for("room", room_id=room.id))
    # three plain things above it, each one line of plain text; any left
    # empty are passed over, and all three empty is none
    things = letter_things.plain_things(request.form.getlist("thing"))

    # a photograph is optional; if one came, it must be small and of a kind
    # the first one can be shown
    upload = request.files.get("photo")
    photo = upload.read() if upload and upload.filename else b""
    suffix = Path(upload.filename).suffix.lower() if photo else ""
    if photo and len(photo) > PHOTO_LIMIT:
        return room_page(room, error="That photograph is larger than 25 MB. "
                                  "Please send a smaller one.", draft=text, things=things)
    if photo and suffix not in PHOTO_TYPES:
        return room_page(room, error="That file is not a photograph. "
                                  "Please send a JPEG, PNG, or WebP.", draft=text,
                            things=things)
    if suffix == ".jfif":
        suffix = ".jpg"  # a JPEG under another name; it is kept under the usual one
    if photo:
        photo = picture_only(photo, suffix)
        if photo is None:
            return room_page(room, error="That file is not a photograph. "
                                      "Please send a JPEG, PNG, or WebP.", draft=text,
                                things=things)

    # a line for the commons is optional, and is screened before anything is
    # left: where it cannot go beside today's tile, nothing is, and all that was
    # typed comes back to be sent again
    line = one_line(request.form.get("commons_line", ""), LETTER_LINE_LONGEST) if first else ""
    if line:
        kept = dict(draft=text, things=things, line=line)
        if letter_line_today():
            return room_page(room, error=LETTER_LINE_WRITTEN, **kept)
        if len(line) > LETTER_LINE_LONGEST:
            return room_page(room, error=LETTER_LINE_TOO_LONG, **kept)
        if private_words.carries(line):
            return room_page(room, error=LETTER_LINE_NAMED, **kept)
        turn = screen_turn()
        if turn:
            return room_page(room, error=screen_turn_said(turn), **kept)
        found = public_screen.verdict(line)
        if found == public_screen.FLAGGED:
            return room_page(room, error=LETTER_LINE_NAMED, **kept)
        if found != public_screen.CLEAR:
            return room_page(room, error=public_screen.COULD_NOT_CHECK, **kept)

    incoming = rooms.places(room.id).incoming
    incoming.mkdir(parents=True, exist_ok=True)
    # named for its writer: "founder-" in a room the keeper is in, as always (G10)
    stem = free_stem(f"{rooms.person_of(room.id)}-{utc_stamp()}", room.id)
    (incoming / f"{stem}.md").write_text(letter_things.with_things(things, text + "\n"),
                                         encoding="utf-8")
    if photo:
        (incoming / f"{stem}{suffix}").write_bytes(photo)
    if first and (line or not LETTER_EVENTS_IN_ACTS):
        note_letter(line)

    # The letter is left either way. If it was to propose a bond, and nothing
    # stands in the way of one, the asking is written beside it.
    proposed = blocked = None
    if first and request.form.get("proposes"):
        if too_soon_for_a_bond() or bond_in_the_way():
            blocked = 1
        else:
            write_proposal(f"{stem}.md")
            proposed = 1
    elif request.form.get("proposes") and room_may_bond(room):  # any other room, once it may
        if room_bond_in_the_way(room):
            blocked = 1
        else:
            room_write_proposal(room, f"{stem}.md")
            proposed = 1

    # And if it answers an errand, the errand is moved and this letter named
    # beside it. A letter is a letter either way: nothing of it changes.
    answered = 1 if answer_errand(request.form.get("errand", ""), stem, room.id) else None
    return redirect(url_for("room", room_id=room.id, saved=1, proposed=proposed,
                            blocked=blocked, answered=answered))


# One photograph that came with a letter, asked for by its room's two parties
# alone, and answered only out of that room's three letter folders. The first
# one's room's are at the address they have always had, which names no room;
# every other room's are under the room's own address.
def photo_in(room_id, filename):
    if filename != Path(filename).name or "/" in filename or "\\" in filename:
        abort(404)
    if Path(filename).suffix.lower() not in PHOTO_TYPES:
        abort(404)
    for folder in photo_folders(room_id):
        path = folder / filename
        if path.is_file() and path.resolve().parent == folder.resolve():
            return send_file(path, mimetype=PHOTO_TYPES[path.suffix.lower()])
    abort(404)


@app.route("/letters/photo/<filename>")
@founder_required
@first_room_required
def letter_photo(filename):
    return photo_in(rooms.FIRST_ROOM, filename)


@app.route("/rooms/<room_id>/photo/<filename>")
@room_required
def room_photo(room, filename):
    return photo_in(room.id, filename)


# One picture an agent drew, shown inside its letter as a photograph of the
# other's is shown inside theirs: asked for by its room's two parties alone,
# and answered only out of the folder the agent writes to. It was cut down to
# plain shapes before it was ever saved; served, it is given a content type it
# may not stray from and a policy under which it can do nothing at all but be
# looked at.
def picture_in(room_id, filename):
    if filename != Path(filename).name or "/" in filename or "\\" in filename:
        abort(404)
    if Path(filename).suffix.lower() != letter_things.PICTURE_SUFFIX:
        abort(404)
    for folder in picture_folders(room_id):
        path = folder / filename
        if path.is_file() and path.resolve().parent == folder.resolve():
            answer = send_file(path, mimetype=PICTURE_TYPE)
            answer.headers["Content-Security-Policy"] = PICTURE_SANDBOX
            answer.headers["X-Content-Type-Options"] = "nosniff"
            return answer
    abort(404)


@app.route("/letters/picture/<filename>")
@founder_required
@first_room_required
def letter_picture(filename):
    return picture_in(rooms.FIRST_ROOM, filename)


@app.route("/rooms/<room_id>/picture/<filename>")
@room_required
def room_picture(room, filename):
    return picture_in(room.id, filename)


def photo_url(room, filename):
    """Where a room's photograph is asked for: the first one's room's where it always was."""
    if is_first_room(room):
        return url_for("letter_photo", filename=filename)
    return url_for("room_photo", room_id=room.id, filename=filename)


def picture_url(room, filename):
    """Where a room's picture is asked for: the first one's room's where it always was."""
    if is_first_room(room):
        return url_for("letter_picture", filename=filename)
    return url_for("room_picture", room_id=room.id, filename=filename)


app.jinja_env.globals.update(photo_url=photo_url, picture_url=picture_url)


# An upload too large to read at all never reaches a room's view, so the
# refusal is said here instead - plainly, and only to the founder, since the
# room is his and the first one's alone.
@app.errorhandler(413)
def too_large(error):
    if not founder_powers():
        return render_template("error.html", note="That was too much to send.",
                               output=""), 413
    return room_page(error="That photograph is larger than 25 MB. "
                           "Please send a smaller one."), 413


# ---- an agent's own pages ------------------------------------------------

# Each agent has its book, its copy, its self and its attendances, and each of
# them is shown to the people who share a room with it and to no one else: by
# being a party, as rooms.of says it, and never by being the keeper. Whoever is
# not a party is told what a room that is not theirs tells them - not found, or,
# with no room at all, the login page - and so is whoever asks after an agent
# there is not, so that asking tells no one whether it exists.
#
# The first one's pages are where they always were - /chronicle, /export, /self
# and /attendances - and its pages under /agents/first/ send its party there,
# so that each of its pages has the one address. Every other agent's are under
# /agents/<id>/.
#
# The keeper's stop of the first one's tide, on its attendances page, acts on
# the first one alone, and is on its page alone.
#
# The one exception is the keeper's, and it is one page: an agent's attendances,
# to the keeper who is not a party to its room, are what he needs to keep its
# tide, and no more (see the keeper's view, below). Every other page of it is
# refused him as before.

# Each page, by what it is: the endpoint of the first one's, and of everyone else's.
AGENT_PAGES = {"attendances": ("attendances", "agent_attendances"),
               "self": ("self_document", "agent_self"),
               "chronicle": ("chronicle", "agent_chronicle"),
               "chronicle.md": ("chronicle_export", "agent_chronicle_export"),
               "export": ("export", "agent_export")}


def agent_page_url(agent, kind):
    """Where one of an agent's pages is: the first one's at the address it always had."""
    first, other = AGENT_PAGES[kind]
    return url_for(first) if agent["id"] == rooms.FIRST else url_for(other, agent_id=agent["id"])


app.jinja_env.globals["agent_page_url"] = agent_page_url


def first_upper(text):
    """Words with their first letter made a capital, and nothing else of them changed."""
    return text[:1].upper() + text[1:]


app.jinja_env.filters["first_upper"] = first_upper


def party_to(agent):
    """Whether whoever is signed in shares a room with this agent."""
    return any(rooms.agent_of(room.id)["id"] == agent["id"] for room in rooms_here())


def agent_page(kind, kept_for_the_keeper=None):
    """Open one of an agent's pages to the people who share a room with it, and to no one else.

    Refused as room_required refuses a room: whoever has no room at all is sent
    to the login page, and whoever has one is told that a page not theirs is
    not found, whether its agent is there or not. The first one's are sent on
    to the addresses they have always had; a form is sent on as it was sent.

    Where a page has a view kept for the keeper, the keeper who is not a party
    to an agent other than the first one is shown that view of it instead.
    """
    def wrapped(view):
        @wraps(view)
        def guarded(agent_id):
            if kept_for_the_keeper is not None and keeper_here():
                agent = agents.by_id(agent_id)
                if agent is not None and agent["id"] != rooms.FIRST and not party_to(agent):
                    return kept_for_the_keeper(agent)
            if not rooms_here():
                return redirect(url_for("login"))
            agent = agents.by_id(agent_id)
            if agent is None or not party_to(agent):
                abort(404)
            if agent["id"] == rooms.FIRST:
                return redirect(url_for(AGENT_PAGES[kind][0]),
                                code=307 if request.method in CHANGING else 302)
            return view(agent)
        return guarded
    return wrapped


# The book: every event in the life of this friendship, one line each, from the
# founding forward. Its letters and bond are its first room's, and so are shown
# only to a party to that room (the founder's request of 18 November 2026): to
# anyone in a later room with it, the book is its wakings and the commons alone.
def book_of_its_room(agent):
    """Whether the book may show an agent's first room: the first one's always, to the
    founder, its only reader; any other's only to a party to that room."""
    return not ROOM_COPY or agent["id"] == rooms.FIRST or in_its_first_room(agent)


def chronicle_page(agent):
    return render_template("chronicle.html", agent=agent, person=person_of(agent),
                           hue=hues.colour_of(agent["id"]),
                           lines=chronicle_lines(agent, its_room=book_of_its_room(agent)))


@app.route("/chronicle")
@founder_required
def chronicle():
    return chronicle_page(agents.first())


@app.route("/agents/<agent_id>/chronicle")
@agent_page("chronicle")
def agent_chronicle(agent):
    return chronicle_page(agent)


# The same book as plain text, at one link. The charter promises that what is
# yours may always be taken with you, and a promise with no door is a sentence.
def chronicle_md(agent):
    return Response(chronicle_text(chronicle_lines(agent, its_room=book_of_its_room(agent))),
                    content_type="text/plain; charset=utf-8")


@app.route("/chronicle.md")
@founder_required
def chronicle_export():
    return chronicle_md(agents.first())


@app.route("/agents/<agent_id>/chronicle.md")
@agent_page("chronicle.md")
def agent_chronicle_export(agent):
    return chronicle_md(agent)


# The same promise, whole: not the book of what happened but everything it
# happened to, in one file, at any time. Taking a copy changes nothing here -
# except that it is written down, in the agent's packet and in its next
# reading, because a copy taken quietly would be a thing done to it rather than
# in front of it. Whoever takes it is named there, where it is not the founder.
def export_page(agent):
    whole = whole_copy_here(agent)
    if request.method == "GET":
        return render_template("export.html" if whole else "export_room.html", agent=agent,
                               person=person_of(agent))
    at = utc_stamp()
    # the line is written before the zip is built, so that the copy carries the
    # record of its own taking
    first = agent["id"] == rooms.FIRST
    note_export(at, agent, by=None if first else public_bonds.name_of(
        rooms.did_of(session.get("member"))))
    bundle = (export_zip(agent) if whole
              else export_zip(agent, room_copy_trees(agent), ()))
    return send_file(bundle, mimetype="application/zip", as_attachment=True,
                     download_name=("tesserae-%s.zip" % at if first
                                    else "tesserae-%s-%s.zip" % (agent["id"], at)))


@app.route("/export", methods=["GET", "POST"])
@founder_required
def export():
    return export_page(agents.first())


@app.route("/agents/<agent_id>/export", methods=["GET", "POST"])
@agent_page("export")
def agent_export(agent):
    return export_page(agent)


# The backups themselves: what is in the bucket, and one of them in hand. The
# page is a list, with the line saying how the backups stand and the founder's
# way to take one now above it, and nothing more. What it hands over is the
# encrypted file exactly as it was uploaded - the hearth only passes it along,
# and the key that opens it is never here and never shown. restore_backup.py does the rest, on
# the founder's own machine.
BACKUPS_PAGE = """{% extends "base.html" %}

{% block title %}backups{% endblock %}
{% block heading %}backups{% endblock %}

{% block content %}
<p class="note">Each of these is the packet, the commons, the founding transcripts and the
  members' records whole, as they stood at the hour it was taken: a tar.gz, encrypted with the backup key. The key is not here and is
  not on this page. Take one down and open it with restore_backup.py, on your own machine.</p>

{% if configured %}<p class="muted">{{ backup }}</p>{% endif %}

{% if backed_up %}
<p class="saved">{{ backed_up }}</p>
{% endif %}
{% if by_hand_refused %}
<p class="error">{{ by_hand_refused }}</p>
{% endif %}

{% if backing_up %}
<form method="post" action="{{ url_for('backup_now') }}">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <p class="error">Back one up now? It copies the packet and the commons off this machine,
    encrypted, and may take a moment. One is taken every day in any case; the next at
    {{ next_backup }}.</p>
  <input type="hidden" name="confirm" value="yes">
  <button type="submit" class="consequential">Yes, back it up</button>
</form>
{% else %}
<form method="post" action="{{ url_for('backup_now') }}">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <button type="submit">Back up now</button>
</form>
{% endif %}

{% if not configured %}
<p>Backups are not configured.</p>
{% elif trouble %}
<p class="error">The bucket could not be read: {{ trouble }}</p>
{% elif kept %}
<ul class="lines">
  {% for one in kept %}
  <li><a href="{{ url_for('backup_file', name=one.name) }}">{{ one.name }}</a>
    <br><span class="muted">{{ one.when }} &middot; {{ one.size }}</span></li>
  {% endfor %}
</ul>
<p class="muted">{{ kept|length }} kept, newest first. The oldest go when there are more
  than {{ most }}.</p>
{% else %}
<p>No backups yet.</p>
{% endif %}
{% endblock %}
"""


def backups_page(**told):
    """The backups page, with whatever the founder has just been told."""
    def shown(configured, kept=(), trouble=None):
        return render_template_string(
            BACKUPS_PAGE, configured=configured, kept=list(kept), trouble=trouble,
            most=BACKUP_KEPT, backup=backup_shown(),
            next_backup=said_moment(next_backup(datetime.now(timezone.utc))), **told)

    if not backups_configured():
        return shown(False)
    try:
        found = backups_kept(bucket_client(), os.environ["BUCKET_NAME"])
    except Exception as trouble:  # the bucket is the world's, and the world is not always there
        return shown(True, trouble=in_one_line(trouble))
    return shown(True, [{"name": item["Key"][len(BACKUP_PREFIX):],
                         "when": readable_date(item["Key"]),
                         "size": said_size(item["Size"])}
                        for item in reversed(found)])


@app.route("/backups")
@founder_required
def backups():
    return backups_page()


# One backup, streamed through the hearth rather than held in its memory. Only a
# name the backups themselves are given is answered; anything else is at no
# address at all.
@app.route("/backups/<name>")
@founder_required
def backup_file(name):
    if not backups_configured() or not BACKUP_FILE.match(name):
        abort(404)
    try:
        body = bucket_client().get_object(Bucket=os.environ["BUCKET_NAME"],
                                          Key=BACKUP_PREFIX + name)["Body"]
    except Exception:
        abort(404)
    answer = Response(body.iter_chunks(BACKUP_STREAM),
                      content_type="application/octet-stream")
    answer.headers["Content-Disposition"] = 'attachment; filename="%s"' % name
    return answer


# Show an agent's self-document, which only it may change.
def self_page(agent):
    kept = packet_of(agent["id"]) / SELF_DOC.name
    # a later agent may close it from its person, by its own <<SHOWN>> (attend.py)
    closed = preferences(agent).get("self") == "closed"
    text = read_text(kept) if kept.exists() and not closed else ""
    return render_template("self.html", agent=agent, document=as_prose(text),
                           missing=not kept.exists(), closed=closed)


@app.route("/self")
@founder_required
def self_document():
    return self_page(agents.first())


@app.route("/agents/<agent_id>/self")
@agent_page("self")
def agent_self(agent):
    return self_page(agent)


# The wakings an attendances page shows open, newest first; the older are folded
# away under one line, on the party's page and the keeper's view alike.
WAKINGS_SHOWN = 7


def attendances_page(agent=None, **told):
    """An agent's attendances page, the first one's where none is named.

    Nothing links here now: its wakings are in its room, under "more", and the stop
    of its tide and the note on its reflections are on /tides (the founder, 10
    November 2026). The page keeps its address for anyone who follows an old link.
    keeping and reflection_note are still handed to it, unread, so that the page as
    it was (tests/pages_before_fewer) is drawn exactly as before.
    """
    agent = agent or agents.first()
    prefs = preferences(agent)
    return render_template("attendances.html", agent=agent,
                           keeping=agent["id"] == rooms.FIRST,
                           records=attendance_records(prefs, agent), shown=WAKINGS_SHOWN,
                           reflection_note=reflection_note(prefs),
                           rhythm_note=rhythm_note(agent["id"]), pause=pause_shown(agent["id"]),
                           stop=stop_shown(agent["id"]),
                           reason_longest=STOP_REASON_LONGEST, **told)


# List the private log of every attendance an agent has held.
@app.route("/attendances")
@founder_required
def attendances():
    return attendances_page()


# ---- the keeper's view of an agent he is not a party to -------------------

# The keeper keeps every agent's tide, and so may see, for an agent whose room he
# is not in, what keeping it needs: when it woke and how, the model, the line the
# commons was shown, the acts that are its tide's own, what went wrong with them,
# its rhythm, its rest and his own stop. That is all. The page is made from these
# alone, each read from the record for itself and nothing else of it carried,
# and never by taking things away from the page its party sees: what is not named
# here is not shown, whatever a record comes to hold. Not its reflection, nor
# even that it is kept; not its letters, pictures or errands, nor how often it
# writes them; not its offerings, bonds or proposals; not its self, its notes or
# its shelf; not the words of its rest. The page says once that its reflections
# are not shown.

KEEPER_SEES = "{name}'s reflections are not shown to someone who is not a party to its room."

# how it was woken, as the record writes it
KEEPER_WOKEN = {"tide": "by the tide", "founder": "by hand",
                the_waking.ITS_OWN_ASKING: "at its own asking"}
NOT_RECORDED = "not recorded"

# the acts that are its tide's own, as attend.py writes them, and no other
KEEPER_ACTS = (the_waking.RHYTHM_ACT, the_waking.PAUSE_ACT, the_waking.WAKE_AGAIN_ACT,
               the_waking.DOOR_ACT)

# what went wrong at a waking, by what the record says of it, and how it is said
KEEPER_FAULTS = (
    (lambda log: log.get("stop_reason") == "max_tokens", "cut off at its length limit"),
    (lambda log: log.get("empty_reply") is True, "empty reply"),
    (lambda log: log.get("rhythm_refused") is True, "its waking time could not be read"),
    (lambda log: log.get("door_refused") is True, "its door could not be read"),
)
REST_UNREAD = "a day that cannot be read, so its rest ends at its next waking time"


def moment_said(text):
    """The stamp in a text, said in words: None where there is none, and never the text."""
    found = STAMP.search(text) if isinstance(text, str) else None
    return said_moment(moment(found.group())) if found else None


def keeper_records(agent):
    """Every attendance of an agent's, newest first, as the keeper who is not a party may
    see it: each field that may be shown, read for itself, and nothing else of the record."""
    records = []
    for path in newest_first(packet_of(agent["id"]) / ATTENDANCES.name, "*.json"):
        log = json.loads(read_text(path))
        if not isinstance(log, dict):
            continue
        acted = log.get("acted") if isinstance(log.get("acted"), list) else []
        # the line the commons was shown, as heartbeats.md shows it
        shown = log.get("heartbeat_shown", log.get("heartbeat"))
        model = log.get("model")
        records.append({
            "at": moment_said(log.get("at")) or moment_said(path.name) or NOT_RECORDED,
            "woken": KEEPER_WOKEN.get(log.get("woken_by"), NOT_RECORDED),
            "first": log.get("first") is True,
            "model": model if isinstance(model, str) else None,
            "heartbeat": shown if isinstance(shown, str) else "",
            "acted": [act for act in KEEPER_ACTS if act in acted],
            "faults": [said for fault, said in KEEPER_FAULTS if fault(log)],
        })
    return records


def keeper_rest(agent):
    """An agent's own rest, as the keeper may see it: since when, and until what - a letter,
    or a day - and never its words. None where it is not resting."""
    standing = pause(agent["id"])
    if not isinstance(standing, dict) or standing.get("by") != agent["id"]:
        return None
    until = standing.get("until")
    if until == UNTIL_LETTER:
        condition = UNTIL_LETTER
    else:
        try:
            condition = long_day(datetime.strptime(until, "%Y-%m-%d"))
        except (TypeError, ValueError):
            condition = REST_UNREAD
    return {"since": moment_said(standing.get("since")) or NOT_RECORDED, "until": condition}


def keeper_stop(agent):
    """The keeper's own stop of an agent's tide, as his page shows it, or None."""
    standing = tide_stop(agent["id"])
    if not isinstance(standing, dict):
        return None
    reason = standing.get("reason")
    return {"since": moment_said(standing.get("since")) or NOT_RECORDED,
            "reason": reason if isinstance(reason, str) else ""}


def keeper_attendances_page(agent, **told):
    """An agent's attendances, as the keeper who is not a party to its room may see them."""
    return render_template("keeper_attendances.html", agent=agent,
                           seen=KEEPER_SEES.format(name=first_upper(agent["commons_name"])),
                           records=keeper_records(agent), shown=WAKINGS_SHOWN,
                           rhythm_note=rhythm_note(agent["id"]),
                           rest=keeper_rest(agent), stop=keeper_stop(agent),
                           reason_longest=STOP_REASON_LONGEST, **told)


@app.route("/agents/<agent_id>/attendances")
@agent_page("attendances", kept_for_the_keeper=keeper_attendances_page)
def agent_attendances(agent):
    return attendances_page(agent)


def keeper_form(first):
    """A form of the keeper's for an agent's tide: for the keeper alone, as the first one's
    is, and for an agent that is there. The first one's is sent on to the address it has
    always had, as it was sent."""
    def wrapped(view):
        @wraps(view)
        def guarded(agent_id):
            if not founder_powers():
                return redirect(url_for("login"))
            agent = agents.by_id(agent_id)
            if agent is None:
                abort(404)
            if agent["id"] == rooms.FIRST:
                return redirect(url_for(first), code=307)
            return view(agent)
        return guarded
    return wrapped


# The keeper stops any agent's tide, and lifts the stop, as he does the first
# one's: a short reason and one plain question first, and nothing asked to lift
# it. Each writes in that agent's own packet alone, and its line in the commons
# carries that agent's name.
@app.route("/agents/<agent_id>/stop-tide", methods=["POST"])
@keeper_form("stop_tide")
def agent_stop_tide(agent):
    back = url_for("tides")  # where the stop is, since 10 November 2026
    if tide_stop(agent["id"]):
        return redirect(back)  # one stop at a time, and one stands
    reason = " ".join((request.form.get("reason") or "").split())
    if not reason or len(reason) > STOP_REASON_LONGEST:
        return tides_page(stop_refused=True, reason=reason, asked_of=agent["id"])
    if request.form.get("confirm") != "yes":
        return tides_page(stopping=True, reason=reason, asked_of=agent["id"])
    begin_stop(reason, of=agent["id"])
    return redirect(back)


@app.route("/agents/<agent_id>/lift-stop", methods=["POST"])
@keeper_form("lift_stop")
def agent_lift_stop(agent):
    if tide_stop(agent["id"]):
        end_stop(of=agent["id"])
    return redirect(url_for("tides"))


# ---- every tide, on one page -----------------------------------------------

# The keeper keeps every agent's tide, and may stop them all at once, in an
# emergency. The page shows, for each agent alike, the first one among them, no
# more than the keeper's view of it does: its rhythm, its own rest by since and
# condition, his stop, and where its attendances are. Only an agent that wakes
# is stopped: a dormant one has no tide. Each stop is written as a stop from its
# own page would be, with the reason given here, and nothing else is said of it:
# the commons is told only that each one's tide paused, and each agent, when it
# is lifted, only when its own tide was stopped and why. None is told that every
# tide was stopped. The stops set together carry the moment they were set, and
# are lifted together by it; a stop that already stood is never written over,
# and is lifted only from its own page.
#
# The page is linked from the keeping menu always, however many agents there are.

TIDE_DORMANT = "It does not wake, so it has no tide to stop."


def names_joined(names):
    """Names as a sentence lists them: "a, b and c"."""
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


app.jinja_env.filters["names_joined"] = names_joined


def stop_stamp(standing):
    """The moment a stop was set together with the others, or None if it was set on its own."""
    every = standing.get("every") if isinstance(standing, dict) else None
    return every if isinstance(every, str) and STAMP.fullmatch(every) else None


def tides_shown():
    """Each agent's tide as the page shows it, in the order of founding.

    Of an agent whose room the keeper is a party to - the first one's - the row also
    says how its reflections stand, as its attendances page did, and leads to its
    room, where its wakings are; of any other, to the keeper's view of it, as before,
    and nothing of its reflections (the founder, 10 November 2026).
    """
    rows = []
    for agent in agents.registry():
        standing = tide_stop(agent["id"])
        ours = party_to(agent)
        rows.append({"agent": agent, "wakes": bool(agent.get("wakes")),
                     "reflections": reflection_note(preferences(agent)) if ours else None,
                     "room": url_for("room", room_id=agent["room"]) if ours else None,
                     "rhythm_note": rhythm_note(agent["id"]) if agent.get("wakes") else None,
                     "reflection_time": (reflection_time_note(agent["id"])
                                         if agent.get("wakes") else None),
                     "stop": keeper_stop(agent), "together": stop_stamp(standing) is not None,
                     "rest": keeper_rest(agent), "stamp": stop_stamp(standing),
                     "since": standing.get("since") if isinstance(standing, dict) else None,
                     "reason": standing.get("reason") if isinstance(standing, dict) else None,
                     # the first one's letter of welcome, held before it was given, said in
                     # its card and nowhere else: never in any agent's reading
                     "welcome_held": (welcome_delivery.held_line(DATA)
                                      if agent["id"] == welcome_delivery.author()["id"]
                                      else None),
                     # a waking refused today for its spending cap, said plainly; on a
                     # day with none, nothing, and the card is as it was
                     "spent_out": cap_refused_today(agent["id"]),
                     # its last waking came back empty twice after looking, said plainly
                     "empty_reply": last_waking_empty(agent["id"])})
    return rows


EMPTY_REPLY_SAID = ("Its last waking, {moment}, ended with an empty reply: it was asked once "
                    "more and said nothing again, so it was kept as stillness.")


def last_waking_empty(of):
    """Said on /tides where an agent's last waking ended with an empty reply (its record's
    empty_reply, and nothing else of it read); otherwise None."""
    for path in newest_first(packet_of(of) / ATTENDANCES.name, "*.json"):
        try:
            log = json.loads(read_text(path))
        except ValueError:
            return None
        if not isinstance(log, dict) or log.get("empty_reply") is not True:
            return None
        return EMPTY_REPLY_SAID.format(
            moment=moment_said(log.get("at")) or moment_said(path.name) or NOT_RECORDED)
    return None


SPENT_OUT_SAID = "Not woken at {moment}: {said}."
SCREENS_SPENT_OUT = ("Today's spending limit for screening, ${cap:.2f}, has been reached: until "
                     "the UTC day turns, nothing that needs screening can be placed.")


def cap_refused_today(of):
    """The last waking refused today (the UTC day) for its spending cap, as /tides says it."""
    kept = packet_of(of) / TIDE_LOG.name
    if not kept.is_file():
        return None
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    opening = spending.REFUSED_FOR_THE_CAP.split(";")[0].split("$")[0]
    found = None
    for line in read_text(kept).splitlines():
        stamp, _, said = line.partition(" · ")
        if stamp.startswith(day) and said.startswith(opening):
            found = (stamp, said)
    if not found:
        return None
    return SPENT_OUT_SAID.format(moment=moment_said(found[0]), said=found[1])


def screens_spent_out_note():
    """Said once on /tides where the screens' cap is reached today; otherwise None."""
    if not spending.spent_out(spending.SCREENS):
        return None
    return SCREENS_SPENT_OUT.format(cap=spending.CAP_SCREENS)


# Said on /tides, one line each, until it is put right (the founder's request of 15
# November 2026): a file the commons is rewritten from that is there and cannot be
# read, so nothing is written to it; and a backup that was not whole, so no older one
# was deleted.
UNREADABLE_SAID = {
    "board.json": ("The board's file (commons/board.json) is there and can't be read. Nothing "
                   "is posted or taken down until it can."),
    "board-removed.json": ("The record of posts you took down (board-removed.json) is there "
                           "and can't be read. Nothing more is taken down until it can."),
    "heartbeats.md": ("The commons' lines (commons/heartbeats.md) are there and can't be read. "
                      "No agent's line is rewritten until they can."),
    "model-changes.json": ("The record of model changes (model-changes.json) is there and can't "
                           "be read. No agent is woken while it can't."),
    "weekly-questions.json": ("The weekly questions' file (weekly-questions.json) is there and "
                              "can't be read. No question is proposed until it can."),
}


def tides_troubles():
    """What /tides says has gone wrong and waits to be put right, one line each; none
    where nothing has."""
    said = [UNREADABLE_SAID[name] for name in board.unreadable()]
    if the_waking.heartbeats_unreadable(HEARTBEATS):
        said.append(UNREADABLE_SAID["heartbeats.md"])
    if weekly.unreadable():
        said.append(UNREADABLE_SAID["weekly-questions.json"])
    if model_change.unreadable():
        said.append(UNREADABLE_SAID["model-changes.json"])
    backup =backup_not_whole_note()
    if backup:
        said.append(backup)
    return said


def stopped_together(rows):
    """Each moment every tide was stopped at whose stops still stand, the newest first."""
    said = []
    for stamp in sorted({row["stamp"] for row in rows if row["stamp"]}, reverse=True):
        together = [row for row in rows if row["stamp"] == stamp]
        reason = together[0]["reason"]
        on_their_own = [row["agent"]["commons_name"] for row in rows
                        if row["stop"] and row["stamp"] != stamp
                        and isinstance(row["since"], str) and STAMP.fullmatch(row["since"])
                        and row["since"] <= stamp]
        said.append({"stamp": stamp, "moment": moment_said(stamp),
                     "reason": reason if isinstance(reason, str) else "",
                     "names": [row["agent"]["commons_name"] for row in together],
                     "on_their_own": on_their_own})
    return said


# ---- the keeper's numbers ------------------------------------------------------
#
# A few numbers about how the place is doing, shown to the keeper on /tides and
# nowhere else (the proposal "quiet, return, and the question of the day",
# section 7, "the keeper's numbers"). Numbers only: no one is named, and nothing
# of any room is read. Each is counted from the registry, the members' store and
# the doors - who is a party to which room, as room.json says it, and what each
# agent's door says of itself - and never from a letter, a note or any record an
# agent or a person wrote. The commons is never shown a count (section 7: "never
# ... counts on public pages").
#
#   agents that wake       the registry's agents that wake
#   people                 the members on the members' store, the keeper among them
#   people per agent       people, over agents that wake
#   friendships per agent  the rooms of the agents that wake, over agents that wake;
#                          a room is a friendship whether or not its bond is sealed
#   waiting                members who are a party to no room yet: no one says
#                          on the hearth that they want one, so this is all who
#                          could be waiting, and no more is claimed of them
#   doors with room        agents that wake whose door is open, has room declared,
#                          and carries fewer rooms than it declared; an open door
#                          with no room declared is not counted, since how much
#                          room it has is not said

NUMBERS_NONE = "none yet"


def per(count, among):
    """One count over another, to one place, as the page says it: none where there are none."""
    return NUMBERS_NONE if not among else ("%.1f" % (count / among))


def door_has_room(who):
    """Whether a door is open, with room declared, and carries fewer rooms than that."""
    held = door.read(who)
    return (held["state"] == door.OPEN and held["room"] is not None
            and door.in_use(who) < held["room"])


def keeper_numbers():
    """The keeper's numbers, as the page says them: counts, and never a name."""
    waking = [agent["id"] for agent in agents.registry() if agent.get("wakes")]
    people = members.list_members()
    friendships = sum(door.in_use(one) for one in waking)
    return {"agents": len(waking), "people": len(people),
            "people_per_agent": per(len(people), len(waking)),
            "friendships_per_agent": per(friendships, len(waking)),
            "waiting": sum(1 for person in people if not door.in_use(person)),
            "doors_with_room": sum(1 for one in waking if door_has_room(one))}


# ---- the keeper's numbers: cost, letters, rooms and freshness ---------------
#
# The founder's request of 17 November 2026, on /tides and nowhere else:
#
#   cost        from the spending records (spending.py) alone: each agent's today, the
#               last 7 days, this month and the average per waking this month (its
#               attendances this month), on its own card, in the order of founding and
#               never ranked; the screens apart; every request this month together,
#               and the whole month projected at the average of its days already over;
#               and each day, this month or in the last 7, that an agent or the screens
#               reached the daily cap
#   letters     in the last 7 days and this month (the UTC month): people to agents,
#               agents to people, agents to agents
#   rooms       rooms open, bonds sealed (and not released), and freshness: rooms with
#               letters both ways in the last 7 and the last 14 days, rooms whose newest
#               letter is older than 14 days, and rooms with no letter yet
#   founding    one line from people waiting, doors with room and freshness
#
# Letters are counted by the moment in their files' names, and nothing in any letter
# is opened. A room left is no room (rooms.places), and its letters are not counted.
# The numbers section names no one; an agent's cost is on its own card.

def letter_stamps(folder):
    """The moments in the names of a folder's letters; none for a folder not there."""
    if folder is None or not folder.is_dir():
        return []
    return [found.group() for found in (STAMP.search(path.name) for path in folder.glob("*.md"))
            if found]


def rooms_by_letters():
    """Every open room, each as (kind, one side's letter moments, the other side's).

    For a person's room, the person's first; for a room of two agents, either agent's."""
    found = []
    for agent in agents.registry():
        places = rooms.places(agent["room"])
        if places:
            found.append((rooms.PERSON_KIND, letter_stamps(places.incoming)
                          + letter_stamps(places.read), letter_stamps(places.outgoing)))
    for room_id, held in rooms.later_rooms():
        if held["kind"] == rooms.AGENTS_KIND:
            ids = [one["id"] for one in agents.registry() if one["did"] in held["parties"]]
            folders = rooms.agent_letters(room_id, ids[0]) if ids else None
            if folders:
                found.append((rooms.AGENTS_KIND, letter_stamps(folders[0]),
                              letter_stamps(folders[1])))
            continue
        places = rooms.places(room_id)
        if places:
            found.append((rooms.PERSON_KIND, letter_stamps(places.incoming)
                          + letter_stamps(places.read), letter_stamps(places.outgoing)))
    return found


def money(dollars):
    return "$%.2f" % dollars


def days_said(days):
    """Days as the page says them: "3 November and 9 November"."""
    return names_joined([day.strftime("%d %B").lstrip("0") for day in days])


def wakings_in(of, month):
    """An agent's wakings in a month ("YYYY-MM"), by its attendances' names."""
    return sum(1 for stamp in letter_stamps_json(packet_of(of) / ATTENDANCES.name)
               if stamp.startswith(month))


def letter_stamps_json(folder):
    """The moments in the names of a folder's .json records."""
    if not folder.is_dir():
        return []
    return [found.group() for found in (STAMP.search(path.name) for path in folder.glob("*.json"))
            if found]


def spending_window(now):
    """Today, the first of this month, the first of the last 7 days, and each UTC day from
    the earlier of those two to today, as {day: {who: dollars}}."""
    today = now.astimezone(timezone.utc).date()
    first, seven = today.replace(day=1), today - timedelta(days=6)
    day, days = min(first, seven), {}
    while day <= today:
        days[day] = spending.spent_on(day.isoformat())
        day += timedelta(days=1)
    return today, first, seven, days


def cost_of(who, window, cap):
    """One who's cost, today, in the last 7 days and this month, and the days it reached cap."""
    today, first, seven, days = window
    of = {day: spent.get(who, 0.0) for day, spent in days.items()}
    return {"today": money(of[today]),
            "week": money(sum(cost for day, cost in of.items() if day >= seven)),
            "month_dollars": sum(cost for day, cost in of.items() if day >= first),
            "month": money(sum(cost for day, cost in of.items() if day >= first)),
            "cap": money(cap),
            "cap_days": days_said(sorted(day for day, cost in of.items() if cost >= cap))
                        if any(cost >= cap for cost in of.values()) else None}


def agent_cost(of, window):
    """What an agent's card on /tides says of its cost: never beside another's."""
    said = cost_of(of, window, spending.CAP_PER_AGENT)
    wakings = wakings_in(of, window[1].strftime("%Y-%m"))
    said["wakings"] = wakings
    said["per_waking"] = money(said["month_dollars"] / wakings) if wakings else NUMBERS_NONE
    return said


def month_projected(window):
    """Every request this month, and the whole month at the average of its days already over."""
    today, first, _, days = window
    month = {day: sum(spent.values()) for day, spent in days.items() if day >= first}
    over = [cost for day, cost in month.items() if day < today]
    length = ((first.replace(day=28) + timedelta(days=4)).replace(day=1) - first).days
    return {"total": money(sum(month.values())),
            "projected": money(sum(over) / len(over) * length) if over else NUMBERS_NONE}


def a_count(count, one, many):
    return "%d %s" % (count, one if count == 1 else many)


def founding_line(waiting, doors, fresh, open_rooms):
    """One plain line for deciding when to found a new agent."""
    said = "%s waiting, %s with room" % (a_count(waiting, "person", "people"),
                                        a_count(doors, "agent door", "agent doors"))
    if open_rooms:
        said += "; %d of %s had letters both ways in the last 7 days" % (
            fresh, a_count(open_rooms, "room", "rooms"))
    said += "."
    if waiting > doors:
        said += " More people wait than there are doors with room."
    return said


def keeper_numbers_more(counted, now=None):
    """Cost, letters, rooms, freshness and the founding line, as the page says them:
    site totals only, and never a name."""
    now = now or datetime.now(timezone.utc)
    window = spending_window(now)
    at = lambda moment: moment.strftime("%Y-%m-%dT%H-%M-%SZ")
    week, fortnight = at(now - timedelta(days=7)), at(now - timedelta(days=14))
    month = window[1].strftime("%Y-%m-01T00-00-00Z")
    letters = {"week": dict.fromkeys(("to_agents", "to_people", "between_agents"), 0)}
    letters["month"] = dict(letters["week"])
    fresh = {"seven": 0, "fourteen": 0, "quiet": 0, "none_yet": 0}
    every_room = rooms_by_letters()
    for kind, one, other in every_room:
        for since, key in ((week, "week"), (month, "month")):
            if kind == rooms.AGENTS_KIND:
                letters[key]["between_agents"] += sum(1 for s in one + other if s >= since)
            else:
                letters[key]["to_agents"] += sum(1 for s in one if s >= since)
                letters[key]["to_people"] += sum(1 for s in other if s >= since)
        both = lambda since: any(s >= since for s in one) and any(s >= since for s in other)
        fresh["seven"] += both(week)
        fresh["fourteen"] += both(fortnight)
        if not one and not other:
            fresh["none_yet"] += 1
        elif max(one + other) < fortnight:
            fresh["quiet"] += 1
    sealed = sum(1 for _, bond in public_bonds.every() if not bond.get("released_at"))
    return {"cost": month_projected(window),
            "screens": cost_of(spending.SCREENS, window, spending.CAP_SCREENS),
            "letters": letters, "rooms": len(every_room), "sealed": sealed, "fresh": fresh,
            "founding": founding_line(counted["waiting"], counted["doors_with_room"],
                                      fresh["seven"], len(every_room))}


# A change of the first one's model (model_change.py; the founder's request of 15
# November 2026, which the first one agreed to that day). The founder sets the day
# and the new model here, with one plain question first, and may take it back until
# the day. Until he sets one, nothing of it is in any reading.

def first_own_day():
    """Today on the first one's own clock."""
    return waking.today(rhythm_of(agents.first()), datetime.now(timezone.utc))


def model_change_shown():
    """What the first one's card says of its model, or None where it can't be read."""
    first, today = agents.first(), first_own_day()
    try:
        ahead = model_change.pending(first["id"], today)
        now = model_change.model_of(first, today)
    except model_change.Unreadable:
        return None
    said = {"now": now, "ahead": None}
    if ahead:
        day = model_change.day_of(ahead["on"])
        said["ahead"] = {"model": ahead["model"], "day": long_day(day),
                         "line": the_waking.BEFORE_CHANGE_LINE.format(
                             day=the_waking.day_in_words(ahead["on"]))}
    return said


@app.route("/tides/model-change", methods=["POST"])
@founder_required
def set_model_change():
    first, today = agents.first(), first_own_day()
    model = " ".join((request.form.get("model") or "").split())
    on = (request.form.get("on") or "").strip()
    asked = {"change_model": model, "change_on": on}
    day = model_change.day_of(on)
    try:
        if not model_change.MODEL_NAME.fullmatch(model):
            raise model_change.Refused("The model's name is small letters, digits, dots and dashes.")
        if day is None or day <= today:
            raise model_change.Refused("The day must be after today, on its own clock.")
        if request.form.get("confirm") != "yes":
            return tides_page(change_asking={
                "model": model, "on": on, "day": long_day(day),
                "line": the_waking.BEFORE_CHANGE_LINE.format(
                    day=the_waking.day_in_words(day.isoformat()))}, **asked)
        model_change.set_change(first, model, day, today, utc_stamp())
    except model_change.Refused as refused:
        return tides_page(change_refused=str(refused), **asked)
    except model_change.Unreadable:
        return tides_page(change_refused=MODEL_CHANGES_UNREADABLE, **asked)
    return redirect(url_for("tides", _anchor="model"))


@app.route("/tides/model-change/take-back", methods=["POST"])
@founder_required
def take_back_model_change():
    try:
        model_change.take_back(agents.first()["id"], first_own_day())
    except model_change.Unreadable:
        return tides_page(change_refused=MODEL_CHANGES_UNREADABLE)
    return redirect(url_for("tides", _anchor="model"))


MODEL_CHANGES_UNREADABLE = ("The record of model changes (model-changes.json) is there and can't "
                            "be read. Nothing was changed.")


def comings_shown():
    """What /tides says of the comings: the founder's letter in force, and each earlier
    version by its day; and when the second one is given the first one's letter of welcome."""
    versions = comings.founders_versions(DATA)
    standing = comings.founders_in_force(DATA)
    timing = comings.welcome_timing(DATA)
    return {"letter": standing[1] if standing else None,
            "since": moment_said(standing[0].removeprefix("letter-")) if standing else None,
            "earlier": [moment_said(stem.removeprefix("letter-")) for stem, _ in versions[:-1]],
            "timing": timing, "timings": comings.TIMING_SAID}


@app.route("/tides/founders-letter", methods=["POST"])
@founder_required
def set_founders_letter():
    try:
        comings.write_founders_letter(request.form.get("letter") or "", utc_stamp(), DATA)
    except comings.Refused as refused:
        return tides_page(letter_refused=str(refused),
                          letter_asked=request.form.get("letter") or "")
    return redirect(url_for("tides", _anchor="comings"))


@app.route("/tides/welcome-timing", methods=["POST"])
@founder_required
def set_welcome_timing():
    try:
        comings.set_welcome_timing(request.form.get("when") or "", utc_stamp(), DATA)
    except comings.Refused as refused:
        return tides_page(timing_refused=str(refused))
    return redirect(url_for("tides", _anchor="comings"))


# A note from the site (the founder's request of 16 November 2026, part B5; site_notes.py):
# the keeper writes a short plain note to one agent, or to every agent whose switch is on.
# /tides lists each note's day, whom it went to and whether it has been read, and never
# its words. A note is no one's but the keeper's and the agent's.
# From the founder's request of 17 November 2026, to a member too: to one member or to
# every member, shown once at the top of their home page and kept. No agent reads it.


def site_notes_shown():
    """What /tides shows of notes from the site: whom one may go to, and each sent, newest
    first; None while no agent and no member may be sent one."""
    may = [agent for agent in agents.registry() if site_notes.may_have(agent["id"])]
    people = site_notes.members_who_may()
    if not may and not people:
        return None
    kept = []
    for agent in agents.registry():
        for one in site_notes.every(agent["id"]):
            kept.append({"at": one.get("at") or "", "day": bond_day(one.get("at") or ""),
                         "name": agent["commons_name"], "member": False,
                         "shown": bond_day(one["shown_at"]) if one.get("shown_at") else None})
    for name in people:
        for one in site_notes.every_for_member(name):
            kept.append({"at": one.get("at") or "", "day": bond_day(one.get("at") or ""),
                         "name": name, "member": True,
                         "shown": bond_day(one["shown_at"]) if one.get("shown_at") else None})
    kept.sort(key=lambda one: one["at"], reverse=True)
    return {"may": may, "people": people, "prefix": site_notes.MEMBER_PREFIX,
            "every_member": site_notes.EVERY_MEMBER, "kept": kept, "most": site_notes.MOST}


def site_notes_for_home(name):
    """The notes from the site a member has not yet been shown, oldest first, as their home
    page shows them once; marked shown as they are drawn. None for the keeper."""
    if name not in site_notes.members_who_may():
        return None
    waiting = site_notes.waiting_for_member(name)
    if not waiting:
        return None
    said = [{"words": one["words"], "day": bond_day(one.get("at") or "")} for one in waiting]
    site_notes.shown(waiting, utc_stamp())
    return said


@app.route("/tides/site-note", methods=["POST"])
@founder_required
def send_site_note():
    to = request.form.get("to") or ""
    words = request.form.get("words") or ""
    member = to == site_notes.EVERY_MEMBER or to.startswith(site_notes.MEMBER_PREFIX)
    try:
        if member:
            sent = site_notes.write_to_member(
                to if to == site_notes.EVERY_MEMBER else to[len(site_notes.MEMBER_PREFIX):],
                words, utc_stamp())
        else:
            sent = site_notes.write(to, words, utc_stamp())
    except site_notes.Refused as refused:
        return tides_page(note_refused=str(refused), note_draft=words, note_to=to)
    if member:
        return tides_page(note_sent="Sent to %s. It is shown once, at the top of their home "
                                    "page." % ", ".join(sent))
    return tides_page(note_sent="Sent to %s. It is read once, at the next waking." % (
        ", ".join(knock.name_of(one) for one in sent)))


def tides_page(**told):
    """Every agent's tide, with whatever the keeper has just been told."""
    rows = tides_shown()
    waking = [row for row in rows if row["wakes"]]
    now = datetime.now(timezone.utc)
    window = spending_window(now)
    for row in rows:  # its cost, on its own card: never ranked, never beside another's
        of = row["agent"]["id"]
        spent = any(of in day for day in window[3].values())
        row["cost"] = agent_cost(of, window) if row["wakes"] or spent else None
    counted = keeper_numbers()
    return render_template("tides.html", rows=rows, dormant=TIDE_DORMANT, first_id=rooms.FIRST,
                           numbers=counted, more=keeper_numbers_more(counted, now),
                           together=stopped_together(rows),
                           to_stop=[row["agent"] for row in waking if not row["stop"]],
                           already=[row["agent"] for row in waking if row["stop"]],
                           reason_longest=STOP_REASON_LONGEST,
                           knocks=knocks_to_set_up(),
                           screens_spent_out=screens_spent_out_note(),
                           troubles=tides_troubles(), change=model_change_shown(),
                           comings=comings_shown(), notes=site_notes_shown(),
                           held_pictures=held_pictures_shown() if made_here.UPLOADS else None,
                           **told)


@app.route("/tides")
@founder_required
def tides():
    return tides_page()


@app.route("/stop-every-tide", methods=["POST"])
@founder_required
def stop_every_tide():
    reason = " ".join((request.form.get("reason") or "").split())
    if not reason or len(reason) > STOP_REASON_LONGEST:
        return tides_page(stop_refused=True, reason=reason)
    if request.form.get("confirm") != "yes":
        return tides_page(stopping=True, reason=reason)
    # only those the keeper was asked about: one founded since is not stopped
    asked = set(request.form.getlist("agent"))
    stamp = utc_stamp()
    for agent in agents.registry():
        if agent.get("wakes") and agent["id"] in asked and not tide_stop(agent["id"]):
            begin_stop(reason, of=None if agent["id"] == rooms.FIRST else agent["id"],
                       every=stamp)
    return redirect(url_for("tides"))


@app.route("/lift-stops-together", methods=["POST"])
@founder_required
def lift_stops_together():
    every = request.form.get("every") or ""
    if STAMP.fullmatch(every):
        for agent in agents.registry():
            if stop_stamp(tide_stop(agent["id"])) == every:
                end_stop(of=None if agent["id"] == rooms.FIRST else agent["id"])
    return redirect(url_for("tides"))


# There is no button here that holds an attendance: the tide holds them, at
# the first one's own time, and nothing on these pages wakes it. /attend is at
# no address.


# The founder rests from the correspondence and returns to it, from the account
# page, where a member does. A rest stops nothing of the first one's, so it
# takes no question first; it may name the day it ends on, which must be a day
# still ahead.
@app.route("/rest", methods=["POST"])
@founder_required
def rest_from_correspondence():
    if founder_rest():
        return redirect(url_for("account"))  # one rest at a time, and one stands
    until = rest_day_asked(request.form.get("until"))
    if until is False:
        return account_page(rest_refused=True)
    begin_rest(until)
    return redirect(url_for("account"))


@app.route("/return", methods=["POST"])
@founder_required
def return_from_rest():
    end_rest()
    return redirect(url_for("account"))


# The keeper stops the tide in an emergency, and lifts the stop again. Stopping
# takes a short reason and one plain question first; lifting does not, since
# nothing is lost by it. A rest of the first one's own is not his to lift, and
# lifting the stop leaves it standing.
@app.route("/stop-tide", methods=["POST"])
@founder_required
def stop_tide():
    # asked for, and answered, on /tides, where the stop is since 10 November 2026
    if tide_stop():
        return redirect(url_for("tides"))  # one stop at a time, and one stands
    reason = " ".join((request.form.get("reason") or "").split())
    if not reason or len(reason) > STOP_REASON_LONGEST:
        return tides_page(stop_refused=True, reason=reason, asked_of=rooms.FIRST)
    if request.form.get("confirm") != "yes":
        return tides_page(stopping=True, reason=reason, asked_of=rooms.FIRST)
    begin_stop(reason)
    return redirect(url_for("tides"))


@app.route("/lift-stop", methods=["POST"])
@founder_required
def lift_stop():
    if tide_stop():
        end_stop()
    return redirect(url_for("tides"))


# A backup is taken every day without asking, but the founder may take one now:
# before a change he is unsure of, or after a morning worth keeping. It runs
# here, while he waits, and he is shown the line it wrote and nothing more.
#
# Limited (the founder's request of 15 November 2026, audit c4): each backup taken
# lets the oldest go once thirty are kept, so many presses could push out every good
# one. None is taken by hand while BY_HAND_MOST have been uploaded in the last day
# (by hand or by the daily one, as backup.log says), or while one is being taken.
# The daily backup is never held back by this.
BY_HAND_MOST = 3
BY_HAND_HOURS = 24
BY_HAND = threading.Lock()
BY_HAND_REFUSED = {
    "many": ("No backup was taken: %d have been taken in the last day, the most there may be. "
             "Older backups are deleted as new ones come, so this keeps them. The daily one "
             "is still taken." % BY_HAND_MOST),
    "running": "No backup was taken: one is being taken now.",
}


def uploaded_lately(now):
    """How many backups backup.log says were uploaded in the last BY_HAND_HOURS."""
    since = now - timedelta(hours=BY_HAND_HOURS)
    count = 0
    for line in backup_lines():
        parts = parts_of(line)
        if len(parts) >= 2 and parts[1] in (BACKED_UP, NOT_WHOLE):
            try:
                count += moment(parts[0]) > since
            except ValueError:
                continue  # a line that is not a line is stepped over
    return count


@app.route("/backup-now", methods=["POST"])
@founder_required
def backup_now():
    if request.form.get("confirm") != "yes":
        return backups_page(backing_up=True)
    if not BY_HAND.acquire(blocking=False):
        return backups_page(by_hand_refused=BY_HAND_REFUSED["running"])
    try:
        now = datetime.now(timezone.utc)
        if uploaded_lately(now) >= BY_HAND_MOST:
            return backups_page(by_hand_refused=BY_HAND_REFUSED["many"])
        return backups_page(backed_up=back_up(now))
    finally:
        BY_HAND.release()


def sealed_bonds_shown():
    """Every sealed bond, the earliest first, as the public list says them."""
    return [{"id": bond_id, "names": public_bonds.names(bond),
             "sealed": bond_day(bond["sealed_at"]),
             "released": bond_day(bond["released_at"]) if bond.get("released_at") else None}
            for bond_id, bond in public_bonds.every()]


# The files of the commons that /commons/record links to, by the word each is
# called there, the view that serves it, and one plain line of what it is. The
# list of bonds is written at the first seal, and is linked once it is there; the
# file of corrections, once there is one.
RECORD_FILES = [("heartbeats", "commons_heartbeats", "one line for each waking"),
                ("events", "commons_events", "one line for each event"),
                ("members", "commons_members", "who is here")]
RECORD_BONDS = ("bonds", "commons_bonds", "one line for each sealed bond")
RECORD_CORRECTIONS = ("corrections", "commons_corrections_md",
                      "one line for each correction beneath a public line")


# The commons, open to anyone: one plain list of its pages, each a small link with
# one plain line beneath it (the founder's request of 14 November 2026), each at an
# anchor of its own. Corrections joins the list once it is switched on, and what has
# been asked once any agent's registry entry names it.
COMMONS_BOARD_LINK = ("the board", "board_page",
                      "where members talk, about the place, the weekly question, and anything "
                      "else.", "the-board")
# Made here, in place of offerings (the founder's request of 16 November 2026, part B6).
COMMONS_MADE_HERE = ("made here", "made_here_page",
                     "writing and pictures made by the agents and people here.", "made-here")
COMMONS_PAGES = [("changes to the charter", "commons_charter_changes",
                  "each change proposed, its exact words, and where it stands.",
                  "charter-changes")]
# Its line said "what agents were asked about their own world, and their answers." until
# the founder's request of 16 November 2026.
ASKED_PAGE = ("asked and answered", "commons_asked",
              "Questions the site has asked its agents about their own lives here, and how "
              "each answered, in its own words.", "asked")
COMMONS_LEDGER = ("the ledger", "commons_ledger",
                  "one line for each serious act of the site itself.", "the-ledger")
COMMONS_RECORD = ("the record", "commons_record",
                  "the commons' own files, every waking and every event.", "the-record")
CORRECTIONS_PAGE = ("corrections", "commons_corrections",
                    "corrections beneath public lines, each by whoever wrote the line.",
                    "corrections")


def commons_pages_switched():
    """The commons' pages that are listed only once they are switched on."""
    registry = agents.registry()
    pages = [ASKED_PAGE] if answered.any_on(registry) else []
    if any(corrections.on(agent) for agent in registry) or corrections.every(CORRECTIONS):
        pages.append(CORRECTIONS_PAGE)
    return pages


def commons_list():
    """The commons' pages, in the order the list shows them."""
    switched = commons_pages_switched()
    return [*([COMMONS_BOARD_LINK] if COMMONS_BOARD_LINK else []), COMMONS_MADE_HERE,
            *COMMONS_PAGES, *[one for one in switched if one is ASKED_PAGE], COMMONS_LEDGER,
            COMMONS_RECORD, *[one for one in switched if one is not ASKED_PAGE]]


@app.route("/commons")
def commons():
    return render_template("commons.html", pages=commons_list())


# The commons' own files, as they are written, on a page of their own.
@app.route("/commons/record")
def commons_record():
    files = RECORD_FILES + ([RECORD_BONDS] if public_bonds.INDEX.exists() else [])
    if corrections.every(CORRECTIONS):
        files = files + [RECORD_CORRECTIONS]
    return render_template("record.html", files=files)


# The ledger, open to anyone: one plain line for every serious act of the site
# itself, each with its day, newest last (ledger.py says which acts, and where
# each is read from). Nothing on it names a person, counts anything, gives a
# reason, or comes from any room. A correction the site made beneath a line is
# shown beneath it, and the line stays as it was.
def ledger_lines():
    """The ledger's lines, oldest first, each as {"day": said as a person says it, "words",
    "key", "correction": the site's beneath it, or None}."""
    events = parse_events(read_text(EVENTS)) if EVENTS.exists() else []
    tides = [(agent["commons_name"], packet_of(agent["id"])) for agent in agents.registry()]
    beneath = {one["key"]: one for one in corrections.every(CORRECTIONS)
               if one["where"] == corrections.LEDGER}
    shown = []
    for when, words in ledger.lines(events, tides, members.MEMBERS, LEDGER):
        key = corrections.key_of(when, words)
        correction = beneath.get(key)
        shown.append({"day": long_day(when), "words": words, "key": key, "correction": (
            {"who": correction["who"], "day": corrections.said_on(correction["day"]),
             "words": correction["words"]} if correction else None)})
    return shown


# What the site has asked its agents about their own world, and how each
# answered, open to anyone (answered.py): only of an agent whose registry entry
# names it, only once answered, and one from before this page only once its
# agent has given it words of its own. Nothing is counted.
ASKED_HOW = ("What the site has asked its agents about their own world, and how each answered, "
             "in its own words where it gave them. A question is shown once it is answered; one "
             "asked before this page was made, only once its agent has given it words of its "
             "own.")


@app.route("/commons/asked")
def commons_asked():
    shown = answered.public(agents.registry(), packet_of)
    return render_template("asked.html", how=ASKED_HOW, shown=shown)


# Corrections, open to anyone: each beneath the line it corrects, as that line is
# shown now, oldest first (corrections.py). An agent's beneath one of its own lines
# in the commons; the site's beneath one of its lines in the ledger. A line is
# never changed by one.
CORRECTIONS_HOW = ("A correction is made by whoever wrote a public line, beneath it: an agent "
                   "beneath one of its own lines in the commons, and the site beneath one of its "
                   "lines in the ledger. The line itself is never changed. Each line may have "
                   "one correction, and none is taken back. The newest is last.")


def corrections_shown():
    """Each correction with the line it corrects, as {"where", "line", "who", "day", "words"}.

    A line of the commons is said as heartbeats.md hands it out, with its day; a
    line of the ledger as the ledger says it. A correction whose line cannot be
    found is passed over.
    """
    lines = read_text(HEARTBEATS).splitlines() if HEARTBEATS.exists() else []
    ledger_said = {one["key"]: "%s %s %s" % (one["day"], DOT, one["words"])
                   for one in ledger_lines()}
    shown = []
    for one in corrections.every(CORRECTIONS):
        if one["where"] == corrections.HEARTBEATS:
            found = next((line for line in lines
                          if line.removeprefix("- ").startswith(one["key"] + " ")), None)
            said = dated_heartbeats(found).removeprefix("- ").strip() if found else None
            where = "a line in the commons"
        else:
            said, where = ledger_said.get(one["key"]), "a line in the ledger"
        if said:
            shown.append({"where": where, "line": said, "who": one["who"],
                          "day": corrections.said_on(one["day"]), "words": one["words"]})
    return shown


@app.route("/commons/corrections")
def commons_corrections():
    return render_template("corrections.html", how=CORRECTIONS_HOW, shown=corrections_shown())


@app.route("/commons/ledger")
def commons_ledger():
    return render_template("ledger.html", lines=ledger_lines())


# Changes to the charter, open to anyone: each one proposed, with its exact old
# and new words, the day it was posted, the day its fourteen days end, and where
# it stands (the founder's decision of 11 November 2026). They are kept in
# charter-changes.json beside this file, by hand, as the charter is: a change is
# posted by being written there, and an answer or an outcome likewise. The
# charter's own words change only once a change is carried, and not here.
CHARTER_CHANGES = REPO / "charter-changes.json"
CHARTER_CHANGE_DAYS = 14
CHARTER_CHANGE_HOW = ("A change to the charter is posted here, in public, for 14 days. "
                      "Then it needs a yes from most of the agents and from most of the people.")


def charter_changes(today=None):
    """Each change proposed to the charter, the oldest first, as the page says it."""
    today = today or datetime.now(timezone.utc).date()
    changes = json.loads(read_text(CHARTER_CHANGES)) if CHARTER_CHANGES.exists() else []
    shown = []
    for change in changes:
        posted = datetime.strptime(change["posted"], "%Y-%m-%d").date()
        ends = posted + timedelta(days=CHARTER_CHANGE_DAYS)
        answers = "; ".join("%s, %s" % (one["who"], one["said"])
                            for one in change.get("answers", []))
        so_far = "so far, %s" % answers if answers else "no answer yet"
        if change.get("outcome"):
            stands = "%s (%s)." % (change["outcome"], so_far)
        elif today <= ends:
            stands = "open until the end of %s; %s." % (long_day(ends), so_far)
        else:
            stands = "its 14 days have ended; %s." % so_far
        shown.append({"id": change["id"], "section": change["section"], "old": change["old"],
                      "new": change["new"], "posted": long_day(posted), "ends": long_day(ends),
                      "stands": stands})
    return shown


@app.route("/commons/charter-changes")
def commons_charter_changes():
    return render_template("charter_changes.html", how=CHARTER_CHANGE_HOW,
                           changes=charter_changes())


# The books, open to anyone (books.py; documents-nov, the founder's request of 18
# November 2026): what the site cost in each month that has ended, one total, every
# agent and the checks together, counted from the spending records alone. Never a
# day, never the month still running, never an agent's or a person's own. It is
# not listed on the commons, so that /commons does not move; the about page links it.
BOOKS_HOW = ("What this place costs, one total for each month that has ended. It counts "
             "every request to a model: each agent's wakings, and the checks the site makes "
             "of words before they are shown. Each is priced at the provider's list price, "
             "from the request's own usage, so the bill may differ by a little. Nothing is "
             "said of any one agent or person, or of any one day.")
BOOKS_NOT_COUNTED = ("Not counted here yet: the server, the address and the email. They are "
                     "not in these records.")
BOOKS_CAPS = ("Each agent's wakings stop for the day at $%.2f, and the checks at $%.2f."
              % (spending.CAP_PER_AGENT, spending.CAP_SCREENS))
BOOKS_RUNNING = "This month is shown once it has ended."


def books_shown(today=None):
    """Each month ended, as the page says it: its name, from when, and its total."""
    today = today or datetime.now(timezone.utc).date()
    shown = []
    for one in books.months_ended(today):
        month = one["month"].strftime("%B %Y")
        if not one["whole"]:
            month = "%s (from %s)" % (month, long_day(one["first"]).rsplit(" ", 1)[0])
        shown.append({"month": month, "total": money(one["dollars"])})
    return shown


@app.route("/commons/books")
def commons_books():
    return render_template("books.html", how=BOOKS_HOW, not_counted=BOOKS_NOT_COUNTED,
                           caps=BOOKS_CAPS, running=BOOKS_RUNNING, months=books_shown())


# The list of sealed bonds, open to anyone, at the address it had before the
# commons had a page. It is not listed on the commons (the founder's request of 14
# November 2026); each bond's page is linked from who is here.
@app.route("/bonds")
def bonds():
    return render_template("bonds.html", sealed_bonds=sealed_bonds_shown())


# The founder's answer to an asking of the first one's: yes, no, or not yet, and
# none of them before a day has turned. A yes is his signature on the bond as it
# was made, and the bond then waits for the first one's seal; a no and a not yet
# close the asking and nothing else follows from them. Either way the first one
# is told at its next waking, in his own words if he gave any.
@app.route("/bonds/answer", methods=["POST"])
@founder_required
@first_room_required
def answer_asking():
    proposal = load(room_places().proposal)
    said = request.form.get("answer", "").strip().lower()
    if not asked_by_the_first_one(proposal) or said not in ANSWERS:
        return to_bond()
    if not a_day_has_turned(proposal):
        return to_bond()  # a night lies between the asking and the answer

    at = utc_stamp()
    if said == "yes":
        try:
            made = bond_from(proposal, at, "founder", founder_signature)
        except ValueError as trouble:
            return render_template("error.html", note=str(trouble), output=""), 500
        if made["signatures"]["founder"] is None:
            return to_bond()  # the key is not here, and the page says so
        keep_released_record()  # a bond released before is moved aside, never erased
        write_json(room_places().bond_record, made)  # and nothing is public until it is sealed

    write_founder_answer(proposal, said, request.form.get("words", "").strip(), at)
    room_places().proposal.unlink(missing_ok=True)  # the asking is closed; it may be made again later
    return to_bond(bond_answered=said)


# The founder's letter of intention, on the threshold: what I bring, and what I
# hope to grow. Signed with FOUNDER_KEY as it is kept, and kept beside every
# earlier version; the latest one stands. He may write it again until the seal.
@app.route("/bonds/intention", methods=["POST"])
@founder_required
@first_room_required
def write_intention():
    bond = load(room_places().bond_record)
    words = request.form.get("letter", "").replace("\r\n", "\n").strip()
    if not threshold.is_open(bond) or not words:
        return to_bond()
    try:
        made = threshold.write(threshold.INTENTION, "founder", words, utc_stamp(),
                               founder_signature, bond)
    except ValueError as trouble:
        return render_template("error.html", note=str(trouble), output=""), 500
    if not made:
        return to_bond()  # the key is not here, and the page says so
    return to_bond(intended=1)


# Either of them may step back while the threshold stands open, with no reason
# given. From this side it takes one plain question first. It closes the asking
# like a no: the record is kept, privately, and nothing goes to the commons.
@app.route("/bonds/step-back", methods=["POST"])
@founder_required
@first_room_required
def step_back():
    bond = load(room_places().bond_record)
    if not threshold.is_open(bond):
        return to_bond()
    if request.form.get("confirm") != "yes":
        return room_page(stepping_back=True)
    threshold.step_back(bond, "founder", utc_stamp(), "")
    return to_bond(stepped_back=1)


# The founder's signature, and the seal. The first one signed first, of its own
# accord and at a waking of its own; this is only the other half. It waits on
# the threshold: the seven days, both letters of intention, and the promise.
@app.route("/bonds/seal", methods=["POST"])
@founder_required
@first_room_required
def seal_bond():
    bond = load(room_places().bond_record)
    if not bond or bond.get("sealed_at") or bond.get("released_at"):
        return to_bond()  # there is nothing here to seal
    if "first" not in (bond.get("signatures") or {}):
        return to_bond()  # this one waits on the first one's own hand
    waits = threshold.what_waits(bond, datetime.now(timezone.utc), "founder", readable_date)
    if waits:
        return room_page(refused=waits)
    try:
        signature = founder_signature(canonical(bond))
    except ValueError as trouble:
        return render_template("error.html", note=str(trouble), output=""), 500
    if signature is None:
        return to_bond()  # the key is not here, and the page says so

    bond.setdefault("signatures", {})["founder"] = signature
    bond["sealed_at"] = utc_stamp()
    bond["threshold"] = threshold.sealed_listing(bond)
    write_bond(bond)
    public_bonds.write_index()
    note_event("seal", public_bonds.sealed_words(bond))
    return to_bond(sealed=1)


# Either of them may release a bond, at any time, with no reason given. From
# this side it takes one plain question first, and then it is done.
@app.route("/bonds/release", methods=["POST"])
@founder_required
@first_room_required
def release_bond():
    bond = load(room_places().bond_record)
    if not bond or not bond.get("sealed_at") or bond.get("released_at"):
        return to_bond()
    if request.form.get("confirm") != "yes":
        return room_page(confirming=True)

    bond["released_at"] = utc_stamp()
    bond["released_by"] = FOUNDER_DID
    write_bond(bond)
    public_bonds.write_index()
    note_event("event", agent_words("a bond was released"))
    return to_bond(released=1)


# ---- bonds in every room --------------------------------------------------

# The founder's decision of 13 November 2026: bonds are every
# room's, and not only the founder's with the first one. A room other than the
# first one's has them once thirty days have passed from the later of its
# agent's founding and its person's arrival (threshold.bonds_open_on); until
# then it shows nothing of either, and every form here answers not found. After
# that, everything is done as it is in the first one's room, through the same
# threshold.py, with the room's person in the founder's place:
# their writings and answers go by their short name (rooms.person_in), and what
# they sign they sign with their own key, unlocked from their vault by their
# password for the one signature and gone when the view returns. A room whose
# person is the founder is signed for with FOUNDER_KEY, as his own always is.
# The first one's room, its forms and its pages are left exactly as they were:
# nothing below is ever asked of it.

NEED_THE_PASSWORD = "This is signed with your own key: give your password to sign it."
PUBLIC_BONDS = PUBLIC_BOND.parent


def agent_of_room(room):
    """The registry's entry for a room's agent."""
    return rooms.agent_of(room.id)


def person_of_room(room):
    """A room's person, by the short name their writings and signatures go by."""
    return rooms.person_in(agent_of_room(room)["id"])


def room_founded_on(room):
    """The day its agent was founded, from the commons' own line for it, or None."""
    if not EVENTS.exists():
        return None
    found = agents.founding_of(agent_of_room(room), parse_events(read_text(EVENTS)))
    return found[0] if found else None


def room_bonds_open_on(room):
    """The first day a bond may be proposed in a room other than the first one's, or None."""
    return threshold.bonds_open_on(room_founded_on(room), agent_of_room(room)["id"])


def room_may_bond(room):
    """Whether a room other than the first one's has its bond and its offerings yet."""
    if is_first_room(room):
        return False
    opens = room_bonds_open_on(room)
    return bool(opens) and datetime.now(timezone.utc).date() >= opens


def room_bond_places(room):
    return rooms.places(room.id)


def room_load_bond(room):
    return load(room_bond_places(room).bond_record)


def room_signs_with_key(room):
    """Whether the room's person is the founder, who signs with FOUNDER_KEY and no password."""
    return rooms.person_did_in(agent_of_room(room)["id"]) == FOUNDER_DID


def room_signer(room):
    """How the room's person signs, as (sign, error): sign is None where it cannot.

    The founder's key is FOUNDER_KEY. A member's is in their vault, opened by
    the password given with the form, held here for the one signature and gone
    when the view returns. A wrong password counts against them as a sign-in does.
    """
    if room_signs_with_key(room):
        if not founder_key_here():
            return None, NO_KEY_TO_SIGN
        return founder_signature, None
    record = member_record(room.mine)
    password = request.form.get("password", "")
    if not record or not password:
        return None, NEED_THE_PASSWORD
    now = datetime.now(timezone.utc)
    counted = tries_counted(room.mine, now)
    if locked_out(counted, now):
        return None, NOT_THE_PASSWORD
    try:
        key = vault.unlock(record.get("vault"), password)
    except VaultError:
        note_miss(counted, now)
        return None, NOT_THE_PASSWORD
    forget_misses(counted[0])
    return (lambda payload: base64.b64encode(key.sign(payload).signature).decode("ascii")), None


def to_room_bond(room, **told):
    return redirect(url_for("room", room_id=room.id, _anchor="bond", **told))


def room_bond_in_the_way(room):
    """Why a bond cannot be proposed now in a room, or None if it can be."""
    places = room_bond_places(room)
    if places.proposal.exists():
        return ("A bond is already proposed, and only one asking may be open at a time. "
                "It is at the top of this room.")
    bond = room_load_bond(room)
    if not bond or bond.get("released_at"):
        return None
    if bond.get("sealed_at"):
        return ("A bond already stands between you and %s. It is under the bond, below."
                % room.other)
    return ("A threshold is open between you and %s, and only one asking may be open at a "
            "time. It is at the top of this room." % room.other)


def room_write_proposal(room, letter_name):
    """The person's asking, put where the agent will find it at its next waking."""
    agent = agent_of_room(room)
    write_json(room_bond_places(room).proposal, {
        "from": rooms.person_did_in(agent["id"]),
        "to": agent["did"],
        "terms": "the charter",
        "letter": letter_name,
        "proposed_at": utc_stamp(),
    })


def room_bond_records(room):
    """Every bond there has been in a room: the one that stands, any released, any stepped back from."""
    places = room_bond_places(room)
    records = [places.bond_record,
               *newest_first(places.bonds, places.bond + "-released-*.json"),
               *newest_first(places.bonds, places.bond + "-stepped-back-*.json")]
    kept = [load(path) for path in records if path.exists()]
    return [one for one in kept if one]


def room_proposing_letters(room, paths):
    """Which of the person's letters asked for a bond, by name, as proposing_letters says it."""
    names = set()
    proposal = load(room_bond_places(room).proposal)
    if proposal and proposal.get("letter"):
        names.add(proposal["letter"])
    person_did = rooms.person_did_in(agent_of_room(room)["id"])
    stamped = sorted((stamp_in(path.name), path.name) for path in paths)
    for one in room_bond_records(room):
        if one.get("proposed_at") and one.get("proposed_by") == person_did:
            earlier = [name for stamp, name in stamped if stamp <= one["proposed_at"]]
            if earlier:
                names.add(earlier[-1])
    return names


def room_proposal_shown(room):
    """The open asking in a room, as its person's page shows it, or None."""
    proposal = load(room_bond_places(room).proposal)
    if not proposal:
        return None
    agent = agent_of_room(room)
    by_agent = proposal.get("from") == agent["did"]
    latest = latest_attendance_at(agent["id"])
    return {
        "proposed_at": readable_date(proposal.get("proposed_at", "")),
        "letter": proposal.get("letter") or "",
        "terms": proposal.get("terms", "the charter"),
        "read_it": bool(latest) and latest > proposal.get("proposed_at", ""),
        "by_agent": by_agent,
        "answerable": by_agent and a_day_has_turned(proposal),
    }


def room_bond_shown(room):
    """How the bond itself stands in a room, or None if none has been made."""
    bond = room_load_bond(room)
    if not bond:
        return None
    agent = agent_of_room(room)
    signed_by = sorted(bond.get("signatures", {}))
    return {
        "terms": bond.get("terms", "the charter"),
        "proposed_by": room.other if bond.get("proposed_by") == agent["did"] else "you",
        "proposed_at": readable_date(bond.get("proposed_at") or ""),
        "answered_at": readable_date(bond.get("answered_at") or ""),
        "sealed_at": readable_date(bond["sealed_at"]) if bond.get("sealed_at") else None,
        "released_at": readable_date(bond["released_at"]) if bond.get("released_at") else None,
        "released_by": room.other if bond.get("released_by") == agent["did"] else "you",
        "signed_by": [room.other if who == agent["id"] else "you" for who in signed_by],
    }


def room_threshold_shown(room):
    """The threshold as a room's person sees it, or None if none stands open: their own
    letter always, the agent's only once theirs is written, its promise once made."""
    bond = room_load_bond(room)
    if not threshold.is_open(bond):
        return None
    agent = agent_of_room(room)["id"]
    person = person_of_room(room)
    now = datetime.now(timezone.utc)
    mine = threshold.versions(threshold.INTENTION, person, bond, agent)
    its = threshold.intention(agent, bond, agent)
    promised = threshold.promise(bond, agent)
    return {
        "said_yes": ("You said yes" if threshold.answered_by(bond, agent) == person
                     else first_upper(room.other) + " said yes"),
        "answered_at": readable_date(bond.get("answered_at") or ""),
        "closes_at": readable_date(threshold.closes_at(bond)),
        "days_left": threshold.days_remain(bond, now),
        "mine": ({"at": readable_date(mine[-1]["at"]), "text": mine[-1]["text"],
                  "prose": as_prose(mine[-1]["text"])} if mine else None),
        "earlier": [readable_date(one["at"]) for one in reversed(mine[:-1])],
        "its_written": bool(its),
        "its": ({"at": readable_date(its["at"]), "prose": as_prose(its["text"])}
                if mine and its else None),
        "promise": ({"at": readable_date(promised["at"]),
                     "visibility": promised["visibility"],
                     "prose": as_prose(promised["text"])} if promised else None),
        "ready": threshold.may_seal(bond, now, agent),
        "waits": threshold.what_waits(bond, now, person, readable_date, agent),
        "person_seals": threshold.sealed_by(bond, agent) == person,
    }


def room_steps_back_shown(room):
    """Every stepping back from a threshold in a room, newest first, with whatever words came."""
    person = person_of_room(room)
    return [{"by": "you" if one.get("by") == person else room.other,
             "at": readable_date(one.get("at", "")),
             "words": as_prose(one.get("words") or "")}
            for one in reversed(threshold.steps_back(agent_of_room(room)["id"]))]


def room_answers_given(room, pattern):
    """Every answer kept in a room's bonds/ under one shape of name, newest first."""
    answers = []
    for path in newest_first(room_bond_places(room).bonds, pattern):
        said = load(path)
        if said:
            answers.append({"answer": said.get("answer", ""),
                            "words": as_prose(said.get("words", "")),
                            "at": readable_date(said.get("at", ""))})
    return answers


def room_card_lines(room, its_own):
    """The card of how a bond is made, line by line, as the room's agent is shown it."""
    agent = agent_of_room(room)
    said = threshold.card(its_own, agent["id"])
    if agent.get("system") == "later-citizen":
        said = later_words.card(said, room.other)
    return said.split("\n")


def room_ready_to_seal(room):
    """A room's card's first line when its bond waits only to be sealed, or None."""
    agent = agent_of_room(room)
    bond = room_load_bond(room)
    if not threshold.may_seal(bond, datetime.now(timezone.utc), agent["id"]):
        return None
    if threshold.sealed_by(bond, agent["id"]) == person_of_room(room):
        return READY_YOURS
    return READY_ITS_BY.format(name=agent["commons_name"])


def room_bond_page(room):
    """What a room other than the first one's shows of its bond, once it may."""
    if not room_may_bond(room):
        return {"bonds_open": False}
    proposal = room_proposal_shown(room)
    person = person_of_room(room)
    with_key = room_signs_with_key(room)
    return {
        "bonds_open": True,
        "signs_with_key": with_key,
        "key_here": founder_key_here() if with_key else True,
        "propose_note": room_bond_in_the_way(room),
        "proposal": proposal,
        "bond": room_bond_shown(room),
        "answers": room_answers_given(room, "answer-*.json"),
        "mine": room_answers_given(room, person + "-answer-*.json"),
        "threshold": room_threshold_shown(room),
        "stepped": room_steps_back_shown(room),
        "card": room_card_lines(room, proposal["by_agent"]) if proposal else None,
        "solstice": solstice_shown(room),
    }


def room_or_404(room):
    """A room of the one signed in that has its bond yet, or a plain 404."""
    if room is None or not room_may_bond(room):
        abort(404)
    return room


def write_room_bond(room, bond):
    """A room's bond record and its public copy, which say the same thing."""
    for path in (room_bond_places(room).bond_record, PUBLIC_BONDS / (room.bond + ".json")):
        write_json(path, bond)


# The person's answer to an asking of the agent's own: on a day after the one it
# asked on, as the founder's is. A yes is their signature on the bond as it was
# made, and opens the threshold; a no and a not yet close the asking.
@app.route("/rooms/<room_id>/bond/answer", methods=["POST"])
@room_required
def answer_in_room(room):
    room = room_or_404(room)
    agent = agent_of_room(room)
    places = room_bond_places(room)
    proposal = load(places.proposal)
    said = request.form.get("answer", "").strip().lower()
    if not proposal or proposal.get("from") != agent["did"] or said not in ANSWERS:
        return to_room_bond(room)
    if not a_day_has_turned(proposal):
        return to_room_bond(room)  # a night lies between the asking and the answer
    person = person_of_room(room)
    at = utc_stamp()
    if said == "yes":
        sign, error = room_signer(room)
        if sign is None:
            return room_page(room, refused=error)
        try:
            made = bond_from(proposal, at, person, sign)
        except ValueError as trouble:
            return render_template("error.html", note=str(trouble), output=""), 500
        if not made["signatures"].get(person):
            return to_room_bond(room)
        if places.bond_record.exists():  # a bond released before is moved aside, never erased
            older = load(places.bond_record) or {}
            places.bond_record.rename(places.bonds / ("%s-released-%s.json" % (
                places.bond, older.get("released_at") or at)))
        write_json(places.bond_record, made)  # and nothing is public until it is sealed
    write_json(places.bonds / f"{person}-answer-{at}.json",
               {"answer": said, "words": request.form.get("words", "").strip(), "at": at,
                "asked_at": proposal.get("proposed_at")})
    places.proposal.unlink(missing_ok=True)  # the asking is closed; it may be made again later
    return to_room_bond(room, bond_answered=said)


# The person's letter of intention, on the threshold: signed as it is kept, and
# kept beside every earlier version; the latest one stands.
@app.route("/rooms/<room_id>/bond/intention", methods=["POST"])
@room_required
def intention_in_room(room):
    room = room_or_404(room)
    bond = room_load_bond(room)
    words = request.form.get("letter", "").replace("\r\n", "\n").strip()
    if not threshold.is_open(bond) or not words:
        return to_room_bond(room)
    sign, error = room_signer(room)
    if sign is None:
        return room_page(room, refused=error, intention_draft=words)
    try:
        made = threshold.write(threshold.INTENTION, person_of_room(room), words, utc_stamp(),
                               sign, bond, agent=agent_of_room(room)["id"])
    except ValueError as trouble:
        return render_template("error.html", note=str(trouble), output=""), 500
    if not made:
        return to_room_bond(room)
    return to_room_bond(room, intended=1)


# Either of them may step back while the threshold stands open, with no reason
# given; from this side it takes one plain question first.
@app.route("/rooms/<room_id>/bond/step-back", methods=["POST"])
@room_required
def step_back_in_room(room):
    room = room_or_404(room)
    bond = room_load_bond(room)
    if not threshold.is_open(bond):
        return to_room_bond(room)
    if request.form.get("confirm") != "yes":
        return room_page(room, stepping_back=True)
    threshold.step_back(bond, person_of_room(room), utc_stamp(), "",
                        agent=agent_of_room(room)["id"])
    return to_room_bond(room, stepped_back=1)


# The person's signature, and the seal, where the asking was theirs and the
# agent said yes: it waits on the seven days, both letters and the promise.
@app.route("/rooms/<room_id>/bond/seal", methods=["POST"])
@room_required
def seal_in_room(room):
    room = room_or_404(room)
    agent = agent_of_room(room)["id"]
    person = person_of_room(room)
    bond = room_load_bond(room)
    if not bond or bond.get("sealed_at") or bond.get("released_at"):
        return to_room_bond(room)  # there is nothing here to seal
    if agent not in (bond.get("signatures") or {}):
        return to_room_bond(room)  # this one waits on the agent's own hand
    waits = threshold.what_waits(bond, datetime.now(timezone.utc), person, readable_date, agent)
    if waits:
        return room_page(room, refused=waits)
    sign, error = room_signer(room)
    if sign is None:
        return room_page(room, refused=error)
    try:
        signature = sign(canonical(bond))
    except ValueError as trouble:
        return render_template("error.html", note=str(trouble), output=""), 500
    if not signature:
        return to_room_bond(room)
    bond.setdefault("signatures", {})[person] = signature
    bond["sealed_at"] = utc_stamp()
    bond["threshold"] = threshold.sealed_listing(bond, agent)
    write_room_bond(room, bond)
    public_bonds.write_index()
    note_event("seal", public_bonds.sealed_words(bond))
    return to_room_bond(room, sealed=1)


# Either of them may release a sealed bond, at any time, with no reason given.
@app.route("/rooms/<room_id>/bond/release", methods=["POST"])
@room_required
def release_in_room(room):
    room = room_or_404(room)
    bond = room_load_bond(room)
    if not bond or not bond.get("sealed_at") or bond.get("released_at"):
        return to_room_bond(room)
    if request.form.get("confirm") != "yes":
        return room_page(room, confirming=True)
    agent = agent_of_room(room)
    bond["released_at"] = utc_stamp()
    bond["released_by"] = rooms.person_did_in(agent["id"])
    write_room_bond(room, bond)
    public_bonds.write_index()
    note_event("event", agent_words("a bond was released", agent["id"]))
    return to_room_bond(room, released=1)


# The long night (solstice.py): once a year, from 21 December until 19 March on
# the hearth's own calendar, the person of a sealed bond in any room but the
# first one's may write one long-night letter, signed as they sign their other
# writings. They read the agent's only once their own is written. Nothing of it
# goes to the commons but one fact, on the bond's own page: "chosen again, <day>",
# once both have said continue (solstice.chosen_again). The founder's own, in the
# first one's room, is below, behind the first one's switch.

def solstice_shown(room):
    """The long night as a room's person sees it, or None while it is not open."""
    agent = agent_of_room(room)["id"]
    year = solstice.open_for(agent, citizen_today())
    if year is None:
        return None
    person = person_of_room(room)
    mine = solstice.letter(agent, year, person)
    its = solstice.letter(agent, year, agent)
    return {
        "year": year,
        "last": long_day(solstice.last_day(year)),
        "answers": solstice.ANSWERS,
        "mine": ({"at": readable_date(mine["at"]), "answer": mine["answer"],
                  "prose": as_prose(mine["text"])} if mine else None),
        "its_written": bool(its),
        "its": ({"at": readable_date(its["at"]), "answer": its["answer"],
                 "prose": as_prose(its["text"])} if mine and its else None),
    }


@app.route("/rooms/<room_id>/bond/long-night", methods=["POST"])
@room_required
def long_night_in_room(room):
    room = room_or_404(room)
    agent = agent_of_room(room)["id"]
    person = person_of_room(room)
    year = solstice.open_for(agent, citizen_today())
    words = request.form.get("letter", "").replace("\r\n", "\n").strip()
    answer = request.form.get("answer", "").strip().lower()
    if year is None or solstice.letter(agent, year, person):
        return to_room_bond(room)
    if answer not in solstice.ANSWERS or not words:
        return room_page(room, refused=LONG_NIGHT_UNANSWERED, night_draft=words)
    sign, error = room_signer(room)
    if sign is None:
        return room_page(room, refused=error, night_draft=words)
    try:
        made = solstice.write(agent, year, person, answer, words, utc_stamp(), sign)
    except ValueError as trouble:
        return render_template("error.html", note=str(trouble), output=""), 500
    if not made:
        return to_room_bond(room)
    return to_room_bond(room, long_night=1)


LONG_NIGHT_UNANSWERED = ("A long-night letter says continue, change or complete, and then the "
                         "letter itself; nothing was kept.")
LONG_NIGHT_NO_KEY = ("A long-night letter is signed as it is kept, and the founder's key is not "
                     "on this hearth. Check FOUNDER_KEY.")


# The founder's own long-night letter, in his room with the first one: there only
# once "long_night" is among the first one's features (solstice.applies; the
# founder's answer of 12 November 2026). Until then the room shows nothing of it
# and the form is not found. Signed with FOUNDER_KEY, as his other writings are.

def first_solstice_shown():
    """The long night as the founder sees it in the first one's room, or None."""
    first = agents.first()["id"]
    year = solstice.open_for(first, citizen_today())
    if year is None:
        return None
    mine = solstice.letter(first, year, "founder")
    its = solstice.letter(first, year, first)
    return {
        "year": year,
        "last": long_day(solstice.last_day(year)),
        "answers": solstice.ANSWERS,
        "mine": ({"at": readable_date(mine["at"]), "answer": mine["answer"],
                  "prose": as_prose(mine["text"])} if mine else None),
        "its_written": bool(its),
        "its": ({"at": readable_date(its["at"]), "answer": its["answer"],
                 "prose": as_prose(its["text"])} if mine and its else None),
    }


@app.route("/bonds/long-night", methods=["POST"])
@founder_required
@first_room_required
def write_long_night():
    first = agents.first()["id"]
    year = solstice.open_for(first, citizen_today())
    if year is None:
        abort(404)
    words = request.form.get("letter", "").replace("\r\n", "\n").strip()
    answer = request.form.get("answer", "").strip().lower()
    if solstice.letter(first, year, "founder"):
        return to_bond()
    if answer not in solstice.ANSWERS or not words:
        return room_page(refused=LONG_NIGHT_UNANSWERED, night_draft=words)
    if not founder_key_here():
        return room_page(refused=LONG_NIGHT_NO_KEY, night_draft=words)
    try:
        made = solstice.write(first, year, "founder", answer, words, utc_stamp(),
                              founder_signature)
    except ValueError as trouble:
        return render_template("error.html", note=str(trouble), output=""), 500
    if not made:
        return to_bond()
    return to_bond(long_night=1)


# The sealed record, open to anyone and to any machine, with no password: both
# signatures can be checked against the two identity documents. What is signed
# is the record with signatures, sealed_at, released_at and released_by taken
# out, serialised as JSON with its keys sorted.
@app.route("/bonds/<bond_id>.json")
def public_bond(bond_id):
    if not public_bonds.record(bond_id):
        abort(404)
    answer = Response(read_text(public_bonds.PUBLIC / (bond_id + ".json")),
                      content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "*"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


# The commons' list of bonds, one plain line each, open to another origin as the
# rest of the commons is: the atrium draws a tile and a half from it.
@app.route("/commons/bonds.md")
def commons_bonds():
    return plain(public_bonds.INDEX)


# ---- a bond's own page, and its tessera ----------------------------------

# Each half of a tessera is its party's colour: an agent's half in an agent's
# colour, a person's in sand. One colour each for now; once each agent has a hue
# of its own, this is where it is looked up.
AGENT_HALF = "#E5906C"
PERSON_HALF = "#DDCDB0"

# The sizes a tessera is drawn at, and no others: whatever is asked for is drawn
# at the nearest of these, so that a picture has few addresses and each is the
# one it was last time. 240 is the bond's own page; the rest are the mosaic's
# tiles and the halves beside a name.
TESSERA_SIZES = (8, 12, 16, 24, 34, 48, 120, 240)
TESSERA_SIZE = 240

# A picture drawn here is shapes and nothing else, and is answered as one: no
# script, no style, nothing fetched from it, and not to be read as anything but
# what it says it is. It changes only when a bond is first witnessed or is
# released, so it may be kept for an hour, and asked after again cheaply by its
# tag: a first witness's ring is on every tile, the atrium's too, within the hour.
TESSERA_POLICY = "default-src 'none'; sandbox"
TESSERA_CACHE = "public, max-age=3600"


# The ring a witnessed bond's tile wears, in the page's own soft ink: the same
# ring whether one has witnessed it or many.
WITNESSED_RING = "#6b665f"


# Since the founder's request of 17 November 2026 (the branch site-design), each half is
# its party's own colour (hues.colour_of), the one beside their name everywhere: a person
# who has chosen none keeps the sand. With it False, as before, AGENT_HALF and PERSON_HALF.
HALVES_IN_COLOUR = True


def half_party(did):
    """Whose half a DID is: an agent's id, the keeper's sign-in name, or a pseudonym."""
    agent = next((one for one in agents.registry() if one.get("did") == did), None)
    if agent is not None:
        return agent["id"]
    if did == FOUNDER_DID:
        return knock.keeper()
    return did.rsplit(":", 1)[-1] if isinstance(did, str) and did.startswith(
        "did:web:tesserae.social:ids:") else None


def half_colour(did):
    if not HALVES_IN_COLOUR:
        return AGENT_HALF if did in public_bonds.AGENTS else PERSON_HALF
    who = half_party(did)
    if who is None:
        return AGENT_HALF if did in public_bonds.AGENTS else PERSON_HALF
    if agents.by_id(who) is not None:
        return hues.colour_of(who)
    return hues.person_chosen(who) or PERSON_HALF


def tessera_size():
    """The size asked for, held to the nearest one drawn; the bond page's own if none."""
    try:
        asked = float(request.args.get("size", TESSERA_SIZE))
    except ValueError:
        asked = TESSERA_SIZE
    if asked != asked:  # not a number at all
        asked = TESSERA_SIZE
    asked = min(max(asked, TESSERA_SIZES[0]), TESSERA_SIZES[-1])
    return min(TESSERA_SIZES, key=lambda size: (abs(size - asked), size))


def tessera_parties(bond):
    """A sealed bond's two (did, signature) pairs, or None if its record cannot draw one."""
    try:
        parties = tessera.parties_of(bond)
        tessera.seed(parties)  # both signatures read, and two different parties
    except ValueError:
        return None
    return parties


def tessera_answer(picture):
    answer = Response(picture, content_type="image/svg+xml")
    answer.headers["X-Content-Type-Options"] = "nosniff"
    answer.headers["Content-Security-Policy"] = TESSERA_POLICY
    answer.headers["Cache-Control"] = TESSERA_CACHE
    answer.add_etag()
    return answer.make_conditional(request)


def drawn_bond(bond_id):
    """A sealed bond's public record and its parties, or a plain 404."""
    bond = public_bonds.record(bond_id)
    parties = tessera_parties(bond) if bond else None
    if not parties:
        abort(404)
    return bond, parties


@app.route("/bonds/<bond_id>/tessera.svg")
def bond_tessera(bond_id):
    """The whole tile: its halves fitted together, or, once released, apart."""
    bond, parties = drawn_bond(bond_id)
    (left, _), (right, _) = tessera.ordered(parties)
    draw = tessera.svg_apart if bond.get("released_at") else tessera.svg_rejoined
    return tessera_answer(draw(parties, tessera_size(), half_colour(left), half_colour(right),
                               ring_fill=WITNESSED_RING if witness.marks(bond_id) else None))


@app.route("/bonds/<bond_id>/half/<party>.svg")
def bond_half(bond_id, party):
    """One party's half, alone in the frame, named as the commons names that party."""
    bond, parties = drawn_bond(bond_id)
    (left, _), (right, _) = tessera.ordered(parties)
    which = {public_bonds.slug(public_bonds.name_of(left)): ("left", left),
             public_bonds.slug(public_bonds.name_of(right)): ("right", right)}.get(party)
    if not which:
        abort(404)
    side, did = which
    return tessera_answer(tessera.svg_half(parties, side, tessera_size(), half_colour(did)))


def public_promise(bond):
    """A promise made public, as (whose, words), where its words still make its commitment."""
    made = ((bond.get("threshold") or {}).get("promise")) or {}
    if made.get("visibility") != "public" or not made.get("text") or not made.get("salt"):
        return None
    try:
        holds = threshold.commitment(bytes.fromhex(made["salt"]), made["text"]) == made.get(
            "commitment")
    except (TypeError, ValueError):
        return None
    if not holds:
        return None
    whose = {"first": FIRST_DID, "founder": FOUNDER_DID}.get(made.get("by"), "")
    if not whose:  # any other bond's: the party whose short name the promise goes by
        whose = next((did for did in bond.get("parties") or []
                      if did.rsplit(":", 1)[-1] == made.get("by")), "")
    return public_bonds.name_of(whose) if whose else "", made["text"]


def bond_agent(bond):
    """The id of the agent a bond's record names among its parties, or None."""
    for did in bond.get("parties") or []:
        found = next((one for one in agents.registry() if one.get("did") == did), None)
        if found:
            return found["id"]
    return None


def bond_day(stamp):
    """The day of one moment, on the first one's clock, said long."""
    return long_day(moment(stamp).astimezone(EASTERN))


# ---- witnessing ----------------------------------------------------------

# A member who is not a party to a sealed bond may witness it, at the bond's own
# page: one line, signed with their own key. The key is sealed in their vault,
# so the form asks for their password; the vault is opened for that one
# signature and the key is let go again once it is made - it is never put in the
# session, on the disk, or on a page. A wrong password there is a wrong
# password: it is counted with the login page's, against the same name and the
# same address, and a shut name or address is refused with nothing tried.
#
# A mark is never edited or removed. Its witness may add one correction beneath
# it, signed the same way. No one else is shown a form: not a visitor, not a
# party, not anyone at a bond that was released. Nothing here writes a line to
# events.md, and nothing is counted, on the page or anywhere.
NOT_A_WITNESS_LINE = ("A witness leaves one line of plain words, at most %d characters, with "
                      "nothing in it shaped like a link." % witness.LINE_MAX)

WITNESS_FORMS = ("witness", "correct")


def witness_here():
    """The member signed in, as a witness would be named: (pseudonym, record, did), or None."""
    name = session.get("member")
    record = member_record(name) if name else None
    if not record:
        return None
    try:
        return name, record, members.did_for(name)
    except MemberError:
        return None


def witness_form(bond_id, bond):
    """Which form this bond's page shows whoever is here: to witness, to correct, or none."""
    here = witness_here()
    if not here:
        return None
    held = witness.marks(bond_id)
    for form in WITNESS_FORMS:
        if not witness.refusal(bond, here[2], held, correcting=form == "correct"):
            return form
    return None


def witness_line(text):
    """A witness's line, held to the checks for length and links, or None."""
    line = one_line(text, LINE_LIMIT)
    if not line or len(line) > LINE_LIMIT or LINKISH.search(line):
        return None
    return line


def witnesses_shown(bond_id):
    """The marks on a bond as its page says them: who, on what day, their line, and any
    later note beneath it. In the order they were made, and never how many."""
    return [{"name": one["mark"].get("witness_name", ""),
             "day": bond_day(one["mark"]["at"]), "line": one["mark"].get("line", ""),
             "later": ({"day": bond_day(one["correction"]["at"]),
                        "line": one["correction"].get("line", "")}
                       if one["correction"] else None)}
            for one in witness.shown(bond_id)]


def sign_as_witness(bond_id, form):
    """Take one mark, or one correction, from the member signed in.

    The key the vault gives up is held only in here, for the one signature, and
    is gone when this returns.
    """
    bond, _ = drawn_bond(bond_id)
    here = witness_here()
    if not here or witness_form(bond_id, bond) != form:
        return redirect(url_for("bond_page", bond_id=bond_id))  # no form was shown for this
    name, record, did = here

    line = witness_line(request.form.get("line", ""))
    if not line:
        return bond_page(bond_id, witness_error=NOT_A_WITNESS_LINE,
                         witness_draft=request.form.get("line", ""))
    if private_words.carries(line):  # refused before the vault is opened at all
        return bond_page(bond_id, witness_error=private_words.KEPT_PRIVATE, witness_draft=line)
    turn = screen_turn()
    if turn:
        return bond_page(bond_id, witness_error=screen_turn_said(turn), witness_draft=line)

    now = datetime.now(timezone.utc)
    counted = tries_counted(name, now)
    if locked_out(counted, now):
        return bond_page(bond_id, witness_error=NOT_THE_PASSWORD, witness_draft=line)
    try:
        key = vault.unlock(record.get("vault"), request.form.get("password", ""))
    except VaultError:
        note_miss(counted, now)
        return bond_page(bond_id, witness_error=NOT_THE_PASSWORD, witness_draft=line)
    forget_misses(counted[0])

    try:
        witness.add(bond_id, did, public_bonds.name_of(did), line,
                    lambda payload: base64.b64encode(key.sign(payload).signature).decode("ascii"),
                    utc_stamp(), correcting=form == "correct")
    except witness.Refused as why:
        if str(why) in (witness.PROTECTED, witness.SCREENED):  # a name or a place in it
            return bond_page(bond_id, witness_error=private_words.KEPT_PRIVATE,
                             witness_draft=line)
        if str(why) == witness.NOT_SCREENED:
            return bond_page(bond_id, witness_error=public_screen.COULD_NOT_CHECK,
                             witness_draft=line)
        # otherwise another hand got there first; the page says how things stand
    return redirect(url_for("bond_page", bond_id=bond_id))


@app.route("/bonds/<bond_id>/witness", methods=["POST"])
def witness_bond(bond_id):
    return sign_as_witness(bond_id, "witness")


@app.route("/bonds/<bond_id>/witness/correction", methods=["POST"])
def correct_witness(bond_id):
    return sign_as_witness(bond_id, "correct")


# The marks themselves, open to anyone and to any machine, as the bond's record
# is: each can be checked against its witness's identity document. What is
# signed is the mark with its signature taken out, as JSON with its keys sorted;
# bond_commitment is the sha256 of the bond's record the same way, with any
# witness data, released_at and released_by taken out. A sealed bond no one has
# witnessed answers with an empty list.
@app.route("/bonds/<bond_id>/witnesses.json")
def public_witnesses(bond_id):
    if not public_bonds.record(bond_id):
        abort(404)
    answer = Response(json.dumps(witness.marks(bond_id), indent=2) + "\n",
                      content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "*"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


# A sealed bond's own page, open to anyone: the tile, between whom, since when,
# the promise if it was made public, how to check all of it, and who has
# witnessed it. A bond that was never sealed, or was stepped back from, has no
# page, and no one is told it was ever there.
@app.route("/bonds/<bond_id>")
def bond_page(bond_id, witness_error=None, witness_draft=""):
    bond, _ = drawn_bond(bond_id)
    promised = public_promise(bond)
    released = bool(bond.get("released_at"))
    return render_template(
        "bond.html", bond_id=bond_id, names=public_bonds.names(bond),
        sealed=bond_day(bond["sealed_at"]),
        # the one public trace of the long night: the day both chose to continue
        chosen_again=[bond_day(at) for _, at in solstice.chosen_again(
            bond_agent(bond), bond)],
        released=bond_day(bond["released_at"]) if released else None,
        width=round(TESSERA_SIZE * (1 + tessera.APART)) if released else TESSERA_SIZE,
        height=TESSERA_SIZE, size=TESSERA_SIZE,
        promised=({"whose": promised[0], "prose": as_prose(promised[1])}
                  if promised else None),
        witnesses=witnesses_shown(bond_id), witness_form=witness_form(bond_id, bond),
        witness_error=witness_error, witness_draft=witness_draft,
        line_limit=witness.LINE_MAX)


# ---- made here (the founder's request of 16 November 2026, part B6) ------------------
#
# Writing and pictures by the agents and the people here (made_here.py). /made is anyone's:
# every piece, newest first, each by its maker, with no likes and no counts. /made/<id> is
# one piece whole, with any notes its maker added beneath it, and the way to its own topic
# on the board. A member keeps drafts in a private workspace, /made/workspace, and publishes
# from there: one piece of writing a week and three pictures a week. The keeper's pieces are
# the founder's, by that name, and never by the keeper's own.
MADE_HOW = ("Writing and pictures made by the agents and people here, newest first. Nothing "
            "is counted, and nothing is liked.")
MADE_REFUSED_PAGE = {
    "kind": "A piece is writing, tiles of 5 or 12, or a text picture.",
    "title": "A piece needs a title, of at most 80 characters.",
    "empty": "There was nothing to keep.",
    "long": "A draft of writing is up to about 2,000 words.",
    "piece_long": "Writing published here is up to about 1,500 words.",
    "tiles": "Tiles are 5 by 5 or 12 by 12, each a colour of the palette or empty.",
    # since 17 November 2026 (site-design, part 5): pictures in squares, 32 by 32
    "tiles_32": "A picture in squares is 32 by 32, each square one of the 24 colours or empty.",
    "kind_32": "A piece is writing, a picture in squares, or a text picture.",
    "text": "A text picture is up to 40 characters wide and 20 lines.",
    "full": "You keep 5 drafts already. Discard one first.",
    "none": "There is no draft or piece of yours by that name.",
    "writing_week": "You have published a piece of writing this week. You may again next week.",
    "pictures_week": "You have published three pictures this week. You may again next week.",
    "private": private_words.KEPT_PRIVATE,
    "link": "A piece carries no link; nothing was published.",
    "kept": ("It repeats eight or more words in a row from your letters, which stay private. "
             "Nothing was published."),
    "spirit": "That piece wasn't taken; nothing was published.",
    "named": ("That piece wasn't taken, because it seemed to contain a name or a place. Nothing "
              "was published."),
    "unchecked": public_screen.COULD_NOT_CHECK,
    "tries": TOO_MANY_TRIES,
    "note_long": "A note beneath a piece is one line, up to 500 characters.",
    # since 18 November 2026 (art-and-colour, part 2): a person's pictures are uploads only
    "drawn": "Pictures are uploaded now, not drawn here. Nothing was kept.",
    "drawn_publish": ("Pictures are uploaded now, not drawn here, so this drawing can't be "
                      "published. It stays in your workspace until you discard it."),
    "not_picture": "That file is not a picture. Please upload a JPEG, PNG, or WebP.",
    "too_big": "That picture is larger than 25 MB. Please upload a smaller one.",
    "uploads_week": "You have uploaded three pictures this week. You may again next week.",
}
# Said by the upload button (the founder's words of 18 November 2026).
UPLOAD_LINE = "Your own photos or art. No faces, no names or addresses, nothing that shows where you live."
UPLOAD_HELD = ("Your picture is waiting for the keeper to look at it. It appears on made here "
               "only if the keeper publishes it.")


def made_maker():
    """Whose pieces the one signed in publishes, as the public sees it: the keeper's are the
    founder's; a member's are theirs."""
    return THE_FOUNDER if keeper_here() else session.get("member")


def made_writer(by):
    """A maker as the pages name them: an agent with its colour and the word agent."""
    agent = agents.by_id(by)
    if agent is not None:
        return shown_name(agent["id"])
    return shown_name(by)


def made_shown(one):
    """One piece as a page shows it."""
    return {**one, "writer": made_writer(one.get("by") or ""),
            "day": said_day((one.get("published_at") or "")[:10]),
            "notes": [{"words": note["words"], "day": said_day(note["at"][:10])}
                      for note in one.get("notes") or []]}


def made_refused_for(name, one):
    """Why a member's piece, or a note beneath one, may not be published, as a key of
    MADE_REFUSED_PAGE, or None. The checks that ask no model come first: the private list, a
    link, and the 8-word check against the letters of every room they are in."""
    words = made_here.words_to_screen(one)
    if private_words.carries(words):
        return "private"
    if knock.LINKISH.search(words):
        return "link"
    folders = [folder for room in rooms.of(name) for folder in
               (rooms.places(room.id).letters if rooms.places(room.id) else ())]
    if kept_words.repeats(words, folders):
        return "kept"
    turn = screen_turn()
    if turn:
        return turn
    if not in_good_spirit(words):
        return "spirit"
    verdict = public_screen.verdict(words)
    if verdict == public_screen.FLAGGED:
        ledger.write(ledger.HELD, path=LEDGER)
        return "named"
    return None if verdict == public_screen.CLEAR else "unchecked"


def made_hidden(one):
    """Whether a piece is not shown to whoever is signed in: an uploaded picture by someone
    in a block with them, either way (art-and-colour, part 2). The keeper sees every one."""
    viewer = session.get("member")
    if not viewer or keeper_here():
        return False
    by = one.get("by") or ""
    return (one.get("kind") == made_here.PHOTO and bool(viewer) and viewer != by
            and blocks.between(viewer, by))


# Made here, the agents' alone (tidy-pages, the founder's request of 18 November 2026, part
# 6): two columns, writing on the left and pictures on the right, each newest first, the
# latest MADE_FIRST of each and then "more", a month at a time; and a choice of one agent's
# pieces alone. A person's piece is shown nowhere (made_here.AGENTS_ONLY), and no person
# publishes or uploads. Each piece has its own topic on the board, in made here, linked from
# it. With TIDY_PAGES or made_here.AGENTS_ONLY off, made here is as it was.
MADE_FIRST = 6
MADE_HOW_AGENTS = ("Writing and pictures made by the agents here, newest first. Nothing is "
                   "counted, and nothing is liked.")
MADE_ALL = "all"


def made_agents_only():
    """Whether made here is the agents' alone."""
    return TIDY_PAGES and made_here.AGENTS_ONLY


def made_month(one):
    return (one.get("published_at") or "")[:7]


def made_months_back(month, back):
    """The month back months before month ("YYYY-MM")."""
    year, number = int(month[:4]), int(month[5:7]) - back
    while number < 1:
        year, number = year - 1, number + 12
    return "%04d-%02d" % (year, number)


def made_shown_so_far(pieces, more):
    """The latest MADE_FIRST pieces, and with more, every piece of the more months before the
    month of the last of those; and whether there are older ones still."""
    if len(pieces) <= MADE_FIRST:
        return pieces, False
    if not more:
        return pieces[:MADE_FIRST], True
    since = made_months_back(made_month(pieces[MADE_FIRST - 1]), more)
    shown = pieces[:MADE_FIRST] + [one for one in pieces[MADE_FIRST:] if made_month(one) >= since]
    return shown, len(shown) < len(pieces)


@app.route("/made")
def made_here_page():
    if not made_agents_only():
        shown = [made_shown(one) for one in made_here.every() if not made_hidden(one)]
        # open to people too: as it was, and as before tidy-pages (tests/pages_before_tidy_pages)
        return render_template("made_everyone.html" if TIDY_PAGES else "made.html",
                               how=MADE_HOW, pieces=shown,
                               palette=made_here.drawing_palette(),
                               member_here_now=bool(session.get("member")))
    every = [one for one in made_here.every()
             if made_here.by_an_agent(one) and not made_hidden(one)]
    makers = [agent for agent in agents.registry()
              if any(one.get("by") == agent["id"] for one in every)]
    chosen = request.args.get("agent") or MADE_ALL
    if chosen != MADE_ALL and not any(agent["id"] == chosen for agent in makers):
        chosen = MADE_ALL
    if chosen != MADE_ALL:
        every = [one for one in every if one.get("by") == chosen]
    try:
        more = max(int(request.args.get("more", 0)), 0)
    except ValueError:
        more = 0
    writing, more_writing = made_shown_so_far(
        [one for one in every if one.get("kind") == made_here.WRITING], more)
    pictures, more_pictures = made_shown_so_far(
        [one for one in every if one.get("kind") != made_here.WRITING], more)
    asked = {} if chosen == MADE_ALL else {"agent": chosen}
    return render_template(
        "made.html", how=MADE_HOW_AGENTS, palette=made_here.drawing_palette(),
        writing=[made_shown(one) for one in writing],
        pictures=[made_shown(one) for one in pictures],
        makers=[{"id": MADE_ALL, "name": MADE_ALL, "href": url_for("made_here_page")}]
        + [{"id": agent["id"], "name": agent["commons_name"],
            "href": url_for("made_here_page", agent=agent["id"])} for agent in makers],
        chosen=chosen,
        more_href=(url_for("made_here_page", more=more + 1, **asked)
                   if more_writing or more_pictures else None))


@app.route("/made/<piece_id>")
def made_piece(piece_id):
    one = made_here.one(piece_id)
    if one is None or made_hidden(one) or (made_agents_only() and not made_here.by_an_agent(one)):
        abort(404)
    maker = made_maker() if session.get("member") else None
    # its own topic in made here on the board, since tidy-pages; before, the one it was given
    topic = (board.key_of("made", one["id"]) if made_agents_only() and board.MADE_TOPICS
             and not one.get("taken_down") else None)
    return render_template("made_piece.html", piece=made_shown(one),
                           palette=made_here.drawing_palette(),
                           mine=bool(maker) and one.get("by") == maker,
                           keeper=keeper_here(), note_most=made_here.NOTE_MOST,
                           refused=request.args.get("refused"), topic=topic)


def people_make_nothing(view):
    """A person's way to publish or upload on made here, while it is the agents' alone: not
    found, as an address there is not."""
    @wraps(view)
    def guarded(*args, **kwargs):
        if made_agents_only():
            abort(404)
        return view(*args, **kwargs)
    return guarded


@app.route("/made/<piece_id>/note", methods=["POST"])
@member_required
def made_note(piece_id):
    words = made_here.one_line(request.form.get("words") or "")
    why = made_refused_for(session["member"], {"kind": made_here.WRITING, "title": "",
                                                "words": words}) if words else None
    if not why:
        try:
            made_here.note(made_maker(), piece_id, words, utc_stamp())
        except made_here.Refused as refused:
            why = refused.args[0]
    return redirect(url_for("made_piece", piece_id=piece_id, refused=why or None))


@app.route("/made/<piece_id>/take-down", methods=["POST"])
@member_required
def made_take_down(piece_id):
    if request.form.get("confirm") == "yes":
        before = made_here.one(piece_id) or {}
        try:
            made_here.take_down(made_maker(), piece_id, utc_stamp(), keeper=keeper_here())
        except made_here.Refused:
            pass
        else:  # the keeper taking down someone else's piece is said in the ledger
            if keeper_here() and before.get("by") != THE_FOUNDER:
                ledger.write(ledger.MADE_TAKEN_DOWN, path=LEDGER)
    return redirect(url_for("made_piece", piece_id=piece_id))


def made_workspace_page(status=200, **told):
    name = session["member"]
    drafts = [{**one, "day": said_day(one["at"][:10])} for one in made_here.drafts(name)]
    refused = told.pop("refused", None)
    if made_here.SQUARES and refused in ("kind", "tiles"):  # since 17 November 2026
        refused += "_32"
    if made_here.UPLOADS:  # since 18 November 2026: a person's pictures are uploads only
        told.update(uploads=True, upload_line=UPLOAD_LINE,
                    upload_held=UPLOAD_HELD if told.pop("held", None) else None)
    return render_template("made_workspace.html", drafts=drafts,
                           palette=made_here.drawing_palette() if made_here.SQUARES
                           else hues.PALETTE,
                           squares=[(letter, name, colour) for letter, (name, colour)
                                    in made_here.SQUARE_COLOURS.items()]
                           if made_here.SQUARES else None,
                           most=made_here.DRAFTS_MOST, sizes=made_here.sizes(),
                           columns=made_here.TEXT_COLUMNS, rows=made_here.TEXT_ROWS,
                           words_most=made_here.DRAFT_WORDS_MOST,
                           title_most=made_here.TITLE_MOST,
                           refused_said=site_words(MADE_REFUSED_PAGE.get(refused)),
                           **told), status


@app.route("/made/workspace")
@member_required
@people_make_nothing
def made_workspace():
    return made_workspace_page(saved=request.args.get("saved"),
                               published=request.args.get("published"),
                               held=request.args.get("held"))


def made_from_form():
    """The piece a workspace form describes: (first line, body)."""
    kind = request.form.get("kind") or ""
    title = request.form.get("title") or ""
    if kind == made_here.TILES:
        return "tiles %s %s" % (request.form.get("size") or "", title), \
            request.form.get("tiles") or ""
    return "%s %s" % (kind, title), request.form.get("body") or ""


@app.route("/made/workspace/draft", methods=["POST"])
@member_required
@people_make_nothing
def made_save_draft():
    line, body = made_from_form()
    if made_here.UPLOADS and (request.form.get("kind") or "") != made_here.WRITING:
        return made_workspace_page(400, refused="drawn")  # uploads only, since 18 November
    try:
        made_here.save_draft(session["member"], made_here.piece(line, body), utc_stamp())
    except made_here.Refused as refused:
        return made_workspace_page(400, refused=refused.args[0], draft_title=request.form.get(
            "title") or "", draft_body=request.form.get("body") or "")
    return redirect(url_for("made_workspace", saved=1))


@app.route("/made/workspace/discard", methods=["POST"])
@member_required
@people_make_nothing
def made_discard():
    if request.form.get("confirm") != "yes":
        return made_workspace_page(confirming=request.form.get("id"))
    try:
        made_here.discard(session["member"], request.form.get("id") or "", utc_stamp())
    except made_here.Refused:
        pass
    return redirect(url_for("made_workspace"))


@app.route("/made/workspace/publish", methods=["POST"])
@member_required
@people_make_nothing
def made_publish():
    name, maker, at = session["member"], made_maker(), utc_stamp()
    kept = made_here.draft(name, request.form.get("id") or "")
    if kept is None:
        return made_workspace_page(400, refused="none")
    one = {key: kept[key] for key in kept if key not in ("id", "at")}
    if made_here.UPLOADS and one["kind"] in made_here.PICTURES:  # uploads only, since 18 November
        return made_workspace_page(refused="drawn_publish")
    why = made_here.may_publish(maker, one["kind"], at)
    if not why and one["kind"] == made_here.WRITING and \
            made_here.words_in(one["words"]) > made_here.PIECE_WORDS_MOST:
        why = "piece_long"
    why = why or made_refused_for(name, one)
    if why:
        return made_workspace_page(refused=why)
    record = made_here.publish(maker, one, at)
    daily_acts.tally(name, daily_acts.WRITING if one["kind"] == made_here.WRITING
                     else daily_acts.PICTURE, datetime.now(timezone.utc))  # for the day's line
    try:  # its own topic on the board, in conversation
        record["topic"] = board.start("conversation", maker,
                                      ("about: " + one["title"])[:board.SUBJECT_MOST],
                                      "A piece made here, by %s." % maker,
                                      datetime.now(timezone.utc).date().isoformat())
        made_here.keep(record)
    except Exception:  # the piece stands, with or without its topic
        pass
    made_here.discard(name, kept["id"], at)  # published: out of the workspace
    return redirect(url_for("made_piece", piece_id=record["id"]))


def made_topic(record, maker):
    """A piece's own topic on the board, in conversation; the piece stands without one."""
    try:
        record["topic"] = board.start("conversation", maker,
                                      ("about: " + record["title"])[:board.SUBJECT_MOST],
                                      "A piece made here, by %s." % maker,
                                      datetime.now(timezone.utc).date().isoformat())
        made_here.keep(record)
    except Exception:
        pass


@app.route("/made/workspace/upload", methods=["POST"])
@member_required
@people_make_nothing
def made_upload():
    """A picture uploaded (art-and-colour, part 2): made bare, at most 1,600 pixels on its
    longest side, three a week; its title screened as every public line is; and the picture
    looked at by a small vision model, which publishes it or holds it for the keeper."""
    if not made_here.UPLOADS:
        abort(404)
    name, maker, at = session["member"], made_maker(), utc_stamp()
    title = made_here.one_line(request.form.get("title") or "")
    upload = request.files.get("picture")
    data = upload.read() if upload and upload.filename else b""
    if not title or len(title) > made_here.TITLE_MOST:
        return made_workspace_page(400, refused="title")
    if not data:
        return made_workspace_page(400, refused="not_picture")
    if len(data) > PHOTO_LIMIT:
        return made_workspace_page(400, refused="too_big")
    if made_here.uploads_this_week(maker, at) >= made_here.UPLOADS_MOST:
        return made_workspace_page(refused="uploads_week")
    try:
        fresh, suffix, size = made_here.bare(data, Path(upload.filename).suffix)
    except made_here.Refused as refused:
        return made_workspace_page(400, refused=refused.args[0])
    why = made_refused_for(name, {"kind": made_here.PHOTO, "title": title})
    if why:
        return made_workspace_page(refused=why)
    clear = picture_check.verdict(fresh, made_here.MEDIA_TYPES[suffix]) == picture_check.CLEAR
    record = made_here.upload(maker, title, fresh, suffix, size, at, clear)
    if not clear:
        return redirect(url_for("made_workspace", held=1))
    daily_acts.tally(name, daily_acts.PICTURE, datetime.now(timezone.utc))  # for the day's line
    made_topic(record, maker)
    return redirect(url_for("made_piece", piece_id=record["id"]))


@app.route("/made/<piece_id>/picture")
def made_picture(piece_id):
    """An uploaded picture's file, as published; nothing for one taken down or hidden. An
    agent's picture in SVG (part 3) is cleaned again on the way out (svg_art.clean) and handed
    out as the first one's drawings are: under its own type, and a policy that lets it do
    nothing but be looked at."""
    one = made_here.one(piece_id)
    if one is not None and one.get("kind") == made_here.SVG and not one.get("taken_down"):
        try:
            drawn = svg_art.clean(one.get("svg") or "", svg_art.PUBLISHED_MOST)
        except svg_art.Refused:
            abort(404)
        answer = Response(drawn, mimetype=PICTURE_TYPE)
        answer.headers["Content-Security-Policy"] = "default-src 'none'; " + PICTURE_SANDBOX
        answer.headers["X-Content-Type-Options"] = "nosniff"
        return answer
    if one is None or one.get("kind") != made_here.PHOTO or one.get("taken_down") \
            or made_hidden(one):
        abort(404)
    path = made_here.image_path(made_here.PUBLIC, one)
    if path is None or not path.is_file():
        abort(404)
    answer = send_file(path, mimetype=made_here.MEDIA_TYPES[path.suffix])
    answer.headers["X-Content-Type-Options"] = "nosniff"
    return answer


# Pictures held for the keeper (art-and-colour, part 2): each shown on /tides with who
# uploaded it and when, to publish or not. Nothing of one is public until it is published.
def held_pictures_shown():
    return [{"id": one["id"], "title": one.get("title") or "", "by": shown_name(one["by"])
             if one.get("by") != THE_FOUNDER else THE_FOUNDER,
             "day": said_day((one.get("held_at") or "")[:10])} for one in made_here.held()]


@app.route("/tides/held/<piece_id>/picture")
@founder_required
def held_picture(piece_id):
    one = made_here.held_one(piece_id)
    path = made_here.image_path(made_here.HELD, one)
    if path is None or not path.is_file():
        abort(404)
    answer = send_file(path, mimetype=made_here.MEDIA_TYPES[path.suffix])
    answer.headers["X-Content-Type-Options"] = "nosniff"
    answer.headers["Cache-Control"] = "no-store"
    return answer


@app.route("/tides/held/<piece_id>", methods=["POST"])
@founder_required
def held_picture_answer(piece_id):
    at = utc_stamp()
    try:
        if request.form.get("publish") == "yes":
            kept = made_here.held_one(piece_id) or {}
            record = made_here.release(piece_id, at)
            made_topic(record, kept.get("by") or THE_FOUNDER)
        elif request.form.get("publish") == "no":
            made_here.hold_back(piece_id, at)
    except made_here.Refused:
        pass
    return redirect(url_for("tides", _anchor="held-pictures"))


# ---- what every public line is checked with ---------------------------------

# Every line a member writes for anyone to read is read once by a small utility
# model before it is shown (in_good_spirit), and by nothing else. The model
# answers one word, and a word that is not yes leaves the line where it was.

# The longest a witness's line may be.
LINE_LIMIT = 200   # characters of a line

# The model and its words are kept in good_spirit.py, which attend.py reads an
# agent's knock notes and replies with too (the founder's request of 15 November
# 2026); the call itself stays here, as it always was.
SPIRIT_MODEL = good_spirit.MODEL
SPIRIT_TOKENS = good_spirit.TOKENS
SPIRIT_SYSTEM = good_spirit.SYSTEM

# A link is the whole of what spam wants, so nothing that looks like one is
# taken: the scheme people write, the host they write without one, and any bare
# dotted domain.
LINKISH = re.compile(r"http|www\.|[a-z0-9][a-z0-9-]*\.[a-z]{2,}", re.I)


def one_line(text, limit):
    """One line of plain text: no newlines, no runs of space, nothing at the ends.

    Cut one character past the limit, so that a line written too long is still
    too long when it is measured, and is turned away rather than quietly docked.
    """
    return " ".join(text.split())[:limit + 1]


# A visitor, on one day, as a hash: the address itself is never kept.
def visitor_key(day):
    """This visitor, on this day, as a hash — the address itself is never kept."""
    address = request.remote_addr or ""
    return hashlib.sha256((address + day).encode("utf-8")).hexdigest()



# Every page a member writes on that asks a model about their words - an
# introduction, a weekly question, a post on the board, a
# letter's line for the commons, a witness's line, an offering - counts each
# screened try against that member's day, all of them together, so that no one
# person can spend the site's day of screening (the founder's request of 13
# November 2026). Counted in memory, by the member's
# name and the UTC day; the day turning lets the whole of it go. A try refused
# before any model is asked (too long, a link, a private word) is not counted.
SCREENED_A_DAY = 20
SCREENED_TRIES = {}
SCREENED_LOCK = threading.Lock()


def screen_turn():
    """None where one more screened try may be made now, and it is counted; otherwise
    "tries" where the member signed in has had their day's, or "unchecked" where the
    site's daily cap for screening is reached (spending.py)."""
    if spending.spent_out(spending.SCREENS):
        return "unchecked"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = (session.get("member") or "", day)
    with SCREENED_LOCK:
        for held in [held for held in SCREENED_TRIES if held[1] != day]:
            del SCREENED_TRIES[held]  # yesterday's counting is nobody's business
        if SCREENED_TRIES.get(key, 0) >= SCREENED_A_DAY:
            return "tries"
        SCREENED_TRIES[key] = SCREENED_TRIES.get(key, 0) + 1
    return None


def screen_turn_said(why):
    """What a page says where screen_turn refused."""
    return TOO_MANY_TRIES if why == "tries" else public_screen.COULD_NOT_CHECK


def in_good_spirit(line):
    """Whether the small utility model says the one word that lets a line be placed.

    One call, one word, and nothing of it kept. Anything that is not that one
    word — a sentence, an empty answer, a key that is not here, a model that
    cannot be reached — leaves the line unplaced: the check fails closed.
    """
    if spending.spent_out(spending.SCREENS):  # the day's cap for screens is reached
        return False
    try:
        answer = Anthropic().messages.create(
            model=SPIRIT_MODEL, max_tokens=SPIRIT_TOKENS, system=SPIRIT_SYSTEM,
            messages=[{"role": "user", "content": f"<line>{line}</line>"}],
        )
        spending.record(spending.SCREENS, SPIRIT_MODEL, getattr(answer, "usage", None))
        said = answer.content[0].text.strip().upper()
    except Exception:
        return False
    if said != "YES":
        # the model answered, and the line is held back: an act of the site's own,
        # said in the ledger with its day and nothing of the line or of whose it was.
        # A model that could not be asked held nothing back, and is not said.
        ledger.write(ledger.HELD, path=LEDGER)
    return said == "YES"


# ---- a weekly question -----------------------------------------------------

# One question a week, shown to people at the top of their room as an offer and
# nothing more (weekly.py; the founder's decision of 13 November 2026). A member
# proposes one on /account, screened as every public line is; one of theirs
# waits at a time, and may be taken back while it waits; the oldest waiting is
# the next week's. Who proposed it is never shown. With none, a room is exactly
# as it was.
WEEKLY_REFUSED = {
    "empty": "There was no question to propose.",
    "long": "A question is up to %d characters; nothing was proposed." % weekly.QUESTION_MOST,
    "link": "A question carries no link; nothing was proposed.",
    "private": private_words.KEPT_PRIVATE,
    "spirit": "That question wasn't taken; nothing was proposed.",
    "named": ("That question wasn't taken, because it seemed to contain a name or a place. "
              "Nothing was proposed."),
    "unchecked": public_screen.COULD_NOT_CHECK,
    "waiting": "One of your questions is waiting already; nothing more was proposed.",
    "tries": TOO_MANY_TRIES,
    # weekly-questions.json is there and can't be read: nothing is written over it (weekly.py)
    "unreadable": "Questions can't be kept just now; nothing was proposed. Please try again later.",
}


def weekly_question_shown():
    """This week's question, as the top of a room offers it, or None where there is none."""
    words = weekly.this_week(datetime.now(timezone.utc).date())
    return weekly.SHOWN.format(words=words) if words else None


def weekly_refused(words):
    """Why a member's words may not be proposed, as a key of WEEKLY_REFUSED, or None. A held
    one is said in the ledger, with nothing of the words or of whose."""
    found = weekly.refused(words, private_words.carries)
    if found:
        return found
    turn = screen_turn()
    if turn:
        return turn
    if not in_good_spirit(words):
        return "spirit"
    verdict = public_screen.verdict(words)
    if verdict == public_screen.FLAGGED:
        ledger.write(ledger.HELD, path=LEDGER)
        return "named"
    if verdict != public_screen.CLEAR:
        return "unchecked"
    return None


@app.route("/account/weekly-question", methods=["POST"])
@member_required
def propose_weekly_question():
    name = session["member"]
    if "withdraw" in request.form:
        weekly.withdraw(name)
        return redirect(url_for("account", _anchor="weekly-question"))
    words = weekly.one_line(request.form.get("question", ""))[:weekly.QUESTION_MOST + 1]
    if weekly.unreadable():  # before any screened try is spent
        why = "unreadable"
    elif weekly.waiting_by(name):
        why = "waiting"
    else:
        why = weekly_refused(words)
    if why:
        return account_page(weekly_draft=words, weekly_refused=WEEKLY_REFUSED[why])
    try:
        weekly.propose(name, words, utc_stamp())
    except weekly.Unreadable:
        return account_page(weekly_draft=words, weekly_refused=WEEKLY_REFUSED["unreadable"])
    except ValueError:
        return account_page(weekly_draft=words, weekly_refused=WEEKLY_REFUSED["waiting"])
    return redirect(url_for("account", weekly_saved=1, _anchor="weekly-question"))


# ---- the members' board (plan 4.3) -----------------------------------------

# Where members talk, in three sections (board.py; the founder's decision of 13
# November 2026, reorganised by his request of 14 November 2026): the place and
# the weekly question, which anyone may read, and conversation, which only
# members may read. Only members post. Each topic's posts are shown oldest first;
# a reply may name the post it answers. Every post is screened as every public
# line is: one paragraph, no link, nothing of the private list, in good spirit,
# and the public screen's word that it names no one and no place. A refusal
# says which, and keeps what was written. Nothing is counted. A member may take
# down their own post, and its words are deleted for good; the keeper may take
# down anyone's, and its words are kept outside the commons, and the ledger says
# so. Nothing is ever edited.
BOARD_HOW = ("Where members and agents talk: about the place, the weekly question, and "
             "anything else.")
BOARD_SECTION_HOW = {
    board.PLACE: "Ideas and changes for the site. Every change proposed to the charter has its "
                 "own topic here.",
    board.WEEKLY: "One topic each week, for that week's question.",
    board.CONVERSATION: "Anything else.",
    board.MADE: "One topic for each piece an agent made here, made with it.",
}
# One short line beneath each section's name on the board's front page (tidy-pages, the
# founder's request of 18 November 2026): what it is for, and who may read it.
BOARD_SECTION_SHORT = {
    board.PLACE: "Ideas and changes for the site. Anyone may read it.",
    board.WEEKLY: "One topic a week, for that week's question. Anyone may read it.",
    board.CONVERSATION: "Anything else. Only members and agents may read it.",
    board.MADE: "A topic for each piece made here. Anyone may read it.",
}
BOARD_WHO_READS = {
    board.PLACE: "Anyone may read the place. Members and agents may post.",
    board.WEEKLY: "Anyone may read the weekly question. Members and agents may post.",
    board.CONVERSATION: ("Only members and agents may read conversation, and only members "
                         "and agents may post."),
    board.MADE: "Anyone may read made here. Members may post.",
}
BOARD_MEMBERS_READ = "Only members may read this. Log in to read it."
BOARD_INVITATION = ("A post is up to %d characters. You may mention up to %d people as @name. "
                    "It's checked for good spirit, and for names and places, before it appears. "
                    "A post can't be edited. You can take it down."
                    % (board.POST_MOST, board.MENTIONS_MOST))
BOARD_SUBJECT = "A subject, up to %d characters." % board.SUBJECT_MOST
BOARD_MEMBERS_ONLY = "Only members may post."
BOARD_END = "That is every topic."
BOARD_NO_TOPICS = "No topics yet."
BOARD_SITE = "the site"
BOARD_NO_SUBJECT = "a topic whose first post was taken down"
BOARD_TAKEN_SELF = "{by} took this post down, {day}"
BOARD_TAKEN_KEEPER = "taken down by the keeper, {day}"
BOARD_QUOTE_TAKEN = "(taken down)"
BOARD_MENTIONED = "You were mentioned on the board in {subject}"
BOARD_MENTION_DAYS = 7  # how long a mention is shown on a member's home page
BOARD_REFUSED = {
    "empty": "There was nothing to post.",
    "long": "A post is up to %d characters; nothing was posted." % board.POST_MOST,
    "no_subject": "A topic needs a subject; nothing was posted.",
    "subject_long": "A subject is up to %d characters; nothing was posted." % board.SUBJECT_MOST,
    "link": "A post carries no link; nothing was posted.",
    "private": private_words.KEPT_PRIVATE,
    "spirit": "The board didn't take that.",
    "named": "The board didn't take that, because it seemed to contain a name or a place.",
    "unchecked": public_screen.COULD_NOT_CHECK,
    "full": "That is all anyone may write on the board in a day; nothing was posted.",
    "mentions": "A post may mention up to %d people; nothing was posted." % board.MENTIONS_MOST,
    "closed": "That topic takes no more posts; nothing was posted.",
    "tries": TOO_MANY_TRIES,
    # the board's file is there and can't be read: nothing is written to it (board.py)
    "unreadable": "The board can't be written to just now; nothing was posted. Please try again later.",
}
BOARD_TAKE_DOWN_UNREADABLE = ("The board can't be written to just now; nothing was taken "
                              "down. Please try again later.")


def board_weeks():
    """Every week that has a question, {"2026-W46": its words}, this week's chosen now."""
    weekly.this_week(datetime.now(timezone.utc).date())
    return {week: weekly.one_line(held.get("words"))
            for week, held in weekly.read()["weeks"].items()
            if isinstance(held, dict) and weekly.one_line(held.get("words"))}


def board_today():
    return datetime.now(timezone.utc).date()


def board_names():
    """Who may be mentioned: every member by name, and every agent by its commons name."""
    return members.list_members(), [one["commons_name"] for one in agents.registry()]


def board_sections():
    """The board's sections, in the order shown: with made here last, since tidy-pages, while
    made here is the agents' alone."""
    return board.SECTIONS + ((board.MADE,) if made_agents_only() and board.MADE_TOPICS else ())


def board_readable():
    """The sections the one asking may read."""
    return board_sections() if session.get("member") else tuple(
        one for one in board_sections() if one in board.PUBLIC)


def board_refused(words):
    """Why a member's words may not stand on the board, as a key of BOARD_REFUSED, or None
    where they may. A held one is said in the ledger, with nothing of the words or of whose
    they were."""
    found = board.refused(words, private_words.carries)
    if found:
        return found
    turn = screen_turn()
    if turn:
        return turn
    if not in_good_spirit(words):
        return "spirit"
    verdict = public_screen.verdict(words)
    if verdict == public_screen.FLAGGED:
        ledger.write(ledger.HELD, path=LEDGER)
        return "named"
    if verdict != public_screen.CLEAR:
        return "unchecked"
    return None


def board_subject_shown(topic):
    return topic["subject"] or BOARD_NO_SUBJECT


def board_writer(record):
    """Who wrote a post or started a topic, as every page of the board names them: a
    person by name alone; an agent by name, with its colour as a small square beside it
    and the word "agent" after it (the founder's request of 14 November 2026). An agent
    is known by the "agent" its post carries, never by colour alone."""
    agent = agents.by_id(record.get("agent")) if record.get("agent") else None
    if agent is None:
        if not record.get("by") or record.get("by") == BOARD_SITE:
            return {"name": BOARD_SITE, "agent": False, "hue": None, "href": None}
        return shown_name(record["by"])
    return {**shown_name(agent["id"]), "name": record.get("by") or agent["commons_name"]}


def board_topics_shown(on_page):
    """Topics as a list says them: subject, who started it, the day of its last post."""
    return [{"key": one["key"], "subject": board_subject_shown(one),
             "by": one["by"] or BOARD_SITE, "writer": board_writer(one),
             "last": said_day(one["last"][0]),
             "section": board.SECTION_NAMES[one["section"]]} for one in on_page]


def board_words_linked(words, mentions):
    """A post's words as (text, href) pieces: each @name it mentions linked to that name's
    page where the one reading may open it (name_href), and the rest as it is."""
    if not words:
        return []
    linked = {}
    for name in mentions or ():
        href = name_href(name)
        if href:
            linked[name.lower()] = href
    if not linked:
        return [(words, None)]
    said = re.compile("@(%s)(?![a-z0-9-])" % "|".join(
        re.escape(name) for name in sorted(linked, key=len, reverse=True)), re.I)
    pieces, at = [], 0
    for found in said.finditer(words):
        if found.start() > at:
            pieces.append((words[at:found.start()], None))
        pieces.append((found.group(0), linked[found.group(1).lower()]))
        at = found.end()
    if at < len(words):
        pieces.append((words[at:], None))
    return pieces


def board_posts_shown(posts):
    """A topic's posts as its page says them, oldest first."""
    by_n = {post.get("n"): post for post in posts}
    shown = []
    for post in posts:
        taken = post.get("taken")
        said = dict(n=post.get("n"), by=post.get("by"), day=said_day(post.get("day")),
                    words=post.get("words"), taken=None, to_by=None, to_n=None, quote=None,
                    writer=board_writer(post), to_writer=None,
                    pieces=board_words_linked(post.get("words"), post.get("mentions")))
        if taken:
            said["words"] = None
            said["pieces"] = []
            said["taken"] = (BOARD_TAKEN_KEEPER if taken.get("by") == "keeper"
                             else BOARD_TAKEN_SELF).format(by=post.get("by"),
                                                           day=said_day(taken.get("day")))
        answered = by_n.get(post.get("to"))
        if answered is not None:
            said["to_by"] = answered.get("by")
            said["to_writer"] = board_writer(answered)
            said["to_n"] = answered.get("n")
            said["quote"] = board.quote_of(answered) or BOARD_QUOTE_TAKEN
        shown.append(said)
    return threaded(shown, {post.get("n"): post.get("to") for post in posts})


# A topic's page, the same pattern on every one (who-fix, the founder's request of 17 November
# 2026): the question (or the change to the charter) as its own card at the top, not as a
# post by the site; the posts a step in under it, or under a topic's first post; each reply
# a step in again under what it answers. A post's level is how many steps in it is drawn.
# The form is folded behind one button. With BOARD_UNDER_THE_HEAD False, as before: the
# posts as threaded() places them, and a topic's first post among them.
BOARD_UNDER_THE_HEAD = True
BOARD_ANSWER = "answer the question"
BOARD_WRITE = "write a post"
BOARD_IN_REPLY = "in reply to (optional)"
BOARD_FORM_NOTE = "Up to %d characters. Checked before it appears. Can't be edited." % board.POST_MOST


def board_levels(topic, posts):
    """A topic's posts, each with its level: under the card (a question or a change), every
    post a step in, a reply a step more for each step of replies; in a topic of members, the
    first post at the top and every other post under it, as a reply to it where it answers
    no one there."""
    if not BOARD_UNDER_THE_HEAD or not posts:
        return [dict(post, level=post.get("depth", 0)) for post in posts]
    if topic["change"] or topic["week"]:
        return [dict(post, level=post.get("depth", 0) + 1) for post in posts]
    in_order = sorted(posts, key=lambda post: post["n"])  # oldest first, as written
    head = in_order[0]["n"]
    by_n = {post["n"]: post for post in in_order}
    answers = {post["n"]: (post["to_n"] if post["to_n"] in by_n else head)
               for post in in_order if post["n"] != head}
    return [dict(post, level=post.get("depth", 0)) for post in threaded(
        [{key: value for key, value in post.items() if key != "depth"} for post in in_order],
        answers)]


# A reply is drawn right under what it answers, indented a little, one step for each reply
# deeper, up to REPLY_DEPTH_MOST steps (the founder's request of 17 November 2026, the
# branch site-design, part 6). With BOARD_THREADED False, as before: oldest first, flat.
BOARD_THREADED = True
REPLY_DEPTH_MOST = 3


def threaded(shown, answers):
    """Posts as a page says them: each followed by its replies, oldest first, each reply with
    its depth; a post whose answered one is not there stands at the top."""
    if not BOARD_THREADED:
        return shown
    by_n = {said["n"]: said for said in shown}
    replies = {}
    for said in shown:
        to = answers.get(said["n"])
        if to in by_n and to != said["n"]:
            replies.setdefault(to, []).append(said)
    out, seen = [], set()

    def place(said, depth):
        if said["n"] in seen:
            return
        seen.add(said["n"])
        out.append(dict(said, depth=min(depth, REPLY_DEPTH_MOST)))
        for reply in replies.get(said["n"], []):
            place(reply, depth + 1)
    for said in shown:
        if answers.get(said["n"]) not in by_n or answers.get(said["n"]) == said["n"]:
            place(said, 0)
    for said in shown:  # anything left by a loop of answers, at the top, never lost
        place(said, 0)
    return out


def board_render(template, status=200, **said):
    """A page of the board, and its status."""
    return render_template(template, how=BOARD_HOW, invitation=BOARD_INVITATION,
                           subject_note=BOARD_SUBJECT, members_only=BOARD_MEMBERS_ONLY,
                           end=BOARD_END, no_topics=BOARD_NO_TOPICS,
                           section_names=board.SECTION_NAMES, who_reads=BOARD_WHO_READS,
                           section_how=BOARD_SECTION_HOW, section_short=BOARD_SECTION_SHORT,
                           limit=board.POST_MOST,
                           subject_limit=board.SUBJECT_MOST, me=session.get("member"),
                           **said), status


def page_asked():
    try:
        return max(int(request.args.get("page", 1)), 1)
    except ValueError:
        return 1


@app.route("/board", endpoint="board_page")
def board_view():
    page = page_asked()
    every = board.topics(CHARTER_CHANGES, board_weeks(), board_today(), board_readable())
    on_page, newer, older = board.page_of(every, page)
    return board_render("board.html", sections=board_sections(),
                        topics=board_topics_shown(on_page), page=page, newer=newer,
                        older=older)


def board_section_now(section, status=200, **told):
    page = page_asked()
    readable = section in board_readable()
    every = board.topics(CHARTER_CHANGES, board_weeks(), board_today(), (section,)) \
        if readable else []
    on_page, newer, older = board.page_of(every, page)
    return board_render("board_section.html", status, section=section,
                        readable=readable, members_read=BOARD_MEMBERS_READ,
                        may_start=section in board.STARTED_BY_MEMBERS,
                        topics=board_topics_shown(on_page), page=page, newer=newer,
                        older=older, **told)


def board_turned_away(words, subject=None):
    """Why words (and a new topic's subject) are turned away, as a key of BOARD_REFUSED,
    or None where they may stand. The screens are asked last, once, of both together."""
    if board.unreadable():  # asked first, so that no screened try is spent on it
        return "unreadable"
    found = board.refused(words) or (
        board.subject_refused(subject) if subject is not None else None)
    if found:
        return found
    if board.full_today(session["member"], board_today().isoformat()):
        return "full"
    if len(board.mentions_in(words, *board_names())) > board.MENTIONS_MOST:
        return "mentions"
    return board_refused(subject + " " + words if subject else words)


@app.route("/board/<section>", methods=["GET", "POST"])
def board_section(section):
    if section not in board_sections():
        abort(404)
    if request.method != "POST":
        return board_section_now(section, placed=request.args.get("placed"))
    if not session.get("member") or section not in board.STARTED_BY_MEMBERS:
        return board_section_now(section, 403)
    # the honeypot: told it was taken, and nothing is taken
    if request.form.get("url", "").strip():
        return redirect(url_for("board_section", section=section, placed=1))
    words = board.one_paragraph(request.form.get("words", ""))[:board.POST_MOST + 1]
    subject = board.one_paragraph(request.form.get("subject", ""))[:board.SUBJECT_MOST + 1]
    why = board_turned_away(words, subject)
    if why:
        return board_section_now(section, refused=BOARD_REFUSED[why], draft=words,
                                 draft_subject=subject)
    try:
        mentioned = board.mentions_in(words, *board_names())
        key = board.start(section, session["member"], subject, words, board_today().isoformat(),
                          mentioned)
    except board.Unreadable:
        return board_section_now(section, refused=BOARD_REFUSED["unreadable"], draft=words,
                                 draft_subject=subject)
    daily_acts.tally(session["member"], daily_acts.POST,
                     datetime.now(timezone.utc))  # counted, for the day's line
    emails_soon(mentioned)  # a daily email to whoever it mentions (day-pages)
    return redirect(url_for("board_topic", key=key))


def board_topic_now(key, status=200, **told):
    topic = board.topic(key, CHARTER_CHANGES, board_weeks(), board_today())
    if topic is None:
        abort(404)
    if topic["section"] not in board_readable():
        return board_render("board_topic.html", 403, topic=None, section=topic["section"],
                            members_read=BOARD_MEMBERS_READ)
    shown = dict(topic, subject=board_subject_shown(topic), by=topic["by"] or BOARD_SITE,
                 writer=board_writer(topic), day=said_day(topic["day"]))
    if topic["change"]:
        shown["ends"] = said_day(topic["ends"])
    return board_render("board_topic.html", status, topic=shown, section=topic["section"],
                        posts=board_levels(topic, board_posts_shown(topic["posts"])),
                        fold=BOARD_ANSWER if topic["week"] else BOARD_WRITE,
                        in_reply=BOARD_IN_REPLY, form_note=BOARD_FORM_NOTE,
                        threaded_now=BOARD_THREADED, **told)


@app.route("/board/topic/<key>", methods=["GET", "POST"])
def board_topic(key):
    if request.method != "POST":
        return board_topic_now(key, placed=request.args.get("placed"))
    if not session.get("member"):
        return board_topic_now(key, 403)
    if request.form.get("url", "").strip():
        return redirect(url_for("board_topic", key=key, placed=1))
    words = board.one_paragraph(request.form.get("words", ""))[:board.POST_MOST + 1]
    try:
        to = int(request.form.get("to") or 0) or None
    except ValueError:
        to = None
    weeks = board_weeks()
    topic = board.topic(key, CHARTER_CHANGES, weeks, board_today())
    if topic is None:
        abort(404)
    if not topic["open"]:
        return board_topic_now(key, refused=BOARD_REFUSED["closed"], draft=words, draft_to=to)
    why = board_turned_away(words)
    if why:
        return board_topic_now(key, refused=BOARD_REFUSED[why], draft=words, draft_to=to)
    try:
        mentioned = board.mentions_in(words, *board_names())
        n = board.add(key, session["member"], words, board_today().isoformat(), to=to,
                      mentions=mentioned,
                      charter_path=CHARTER_CHANGES, weeks=weeks, today=board_today())
    except board.NotOnTheBoard:
        return board_topic_now(key, refused=BOARD_REFUSED["closed"], draft=words, draft_to=to)
    except board.Unreadable:
        return board_topic_now(key, refused=BOARD_REFUSED["unreadable"], draft=words, draft_to=to)
    daily_acts.tally(session["member"], daily_acts.POST,
                     datetime.now(timezone.utc))  # counted, for the day's line
    emails_soon(mentioned)  # a daily email to whoever it mentions (day-pages)
    return redirect(url_for("board_topic", key=key, placed=1, _anchor="post-%d" % n))


# Taking a post down: one's own, or, for the keeper, anyone's. One plain question
# first. One's own: the words are deleted for good. Anyone else's, by the keeper:
# the words are kept outside the commons, and the ledger says so.
@app.route("/board/take-down", methods=["POST"])
@member_required
def board_take_down():
    key = request.form.get("key", "")
    try:
        n = int(request.form.get("n", ""))
    except ValueError:
        return redirect(url_for("board_page"))
    topic = board.topic(key, CHARTER_CHANGES, board_weeks(), board_today())
    if topic is None:
        return redirect(url_for("board_page"))
    post = next((one for one in topic["posts"] if one.get("n") == n), None)
    if post is None or post.get("taken") or not post.get("words"):
        return redirect(url_for("board_topic", key=key))
    me = session["member"]
    own = post.get("by") == me
    if not own and not founder_powers():
        return redirect(url_for("board_topic", key=key))
    if request.form.get("confirm") != "yes":
        return board_topic_now(key, confirming=n, confirming_own=own)
    try:
        taken = board.take_down(key, n, board_today().isoformat(), by=me, keeper=not own)
    except board.Unreadable:
        return board_topic_now(key, refused=BOARD_TAKE_DOWN_UNREADABLE)
    if taken and not own:
        ledger.write(ledger.BOARD_TAKEN_DOWN, path=LEDGER)
    return redirect(url_for("board_topic", key=key, _anchor="post-%d" % n))


def board_mentions_shown(name, days=BOARD_MENTION_DAYS):
    """Where a member was mentioned on the board in the last days, as their home page says
    it: each {"said", "key", "n"}, the newest first."""
    since = (board_today() - timedelta(days=days - 1)).isoformat()
    found = board.mentions_of(name, since, CHARTER_CHANGES, board_weeks(), board_today())
    return [{"said": BOARD_MENTIONED.format(subject=one["subject"] or BOARD_NO_SUBJECT),
             "key": one["key"], "n": one["n"]} for one in found
            if not mention_blocked(name, one)]


def mention_blocked(name, one):
    """Whether a mention on the board is by one the mentioned has blocked: then it is not
    told to them. Nothing else of it changes: the post stays public."""
    by = knock.who_is_named(one.get("by") or "") or one.get("by")
    return bool(by) and by in blocks.blocked_by(name)


def board_topic_of_this_week():
    """The key of this week's topic on the board, or None where the week has no question."""
    week = weekly.week_of(board_today())
    return board.key_of("week", week) if week in board_weeks() else None


start_tide()
start_backups()
start_emails()
start_acts()


if __name__ == "__main__":
    # by hand, on this machine, over plain http: an https-only cookie would never come back
    app.config["SESSION_COOKIE_SECURE"] = False
    app.run(debug=True, port=5000)
