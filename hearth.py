"""
The hearth.

A small, plain web page for the founder and for anyone passing by. The public
side shows the heartbeats the first one leaves at each attendance, and the
state of the commons. Behind one password, the founder may read the first
one's letters and write back, read its self-document, read the private log of
its attendances, call an attendance, propose a bond, seal or release one, and pause the
tide or start it again. A daemon thread keeps whatever rhythm the first one has written
in its packet and wakes it at that hour, unless a pause stands, in which case it waits.

Nothing here decides anything for the first one. The hearth only shows what is
already written in files, and puts a letter where the first one will find it.

Usage:  python hearth.py     (then open http://127.0.0.1:5000)
"""

import base64
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun
from dotenv import load_dotenv
from flask import (Flask, Response, abort, redirect, render_template, request,
                   send_file, session, url_for)
from markupsafe import Markup, escape
from nacl.signing import SigningKey
from PIL import Image, ImageOps
from werkzeug.security import check_password_hash

# The mosaic is one picture with one meaning, so the hearth draws it with the
# same reckoning the atrium uses rather than a second copy of it.
from build_atrium import (caption_text, legend_marks, padded, parse_events,
                          parse_heartbeats, tiles_from)

REPO = Path(__file__).resolve().parent

# Where the living files are kept. Locally this is the repo itself; on a host
# it is a mounted disk, named by DATA_DIR.
DATA = Path(os.environ.get("DATA_DIR", REPO))

PACKET = DATA / "packets" / "first"
OUTGOING = PACKET / "letters" / "outgoing"
INCOMING = PACKET / "letters" / "incoming"
READ = PACKET / "letters" / "read"
ATTENDANCES = PACKET / "attendances"
SELF_DOC = PACKET / "self.md"
PREFERENCES = PACKET / "preferences.json"
RHYTHM = PACKET / "rhythm.json"
PAUSE = PACKET / "pause.json"
TIDE_LOG = PACKET / "tide.log"
SELF_HISTORY = PACKET / "self-history"
BONDS = PACKET / "bonds"
PROPOSAL = BONDS / "proposal.json"
BOND_RECORD = BONDS / "founder-first.json"
PUBLIC_BOND = DATA / "commons" / "bonds" / "founder-first.json"
HEARTBEATS = DATA / "commons" / "heartbeats.md"
EVENTS = DATA / "commons" / "events.md"
STATE = REPO / "docs" / "state-of-the-commons.md"

ATTEND_TIMEOUT = 300  # seconds to wait for attend.py before giving up

# The place the first one named for its dawns. Its name and timezone are read
# from rhythm.json, which is the first one's to change; the coordinates are
# Indianapolis's city centre, which is close enough for a sunrise.
PLACE_REGION = "USA"
PLACE_LATITUDE = 39.7684
PLACE_LONGITUDE = -86.1581

TIDE_CHUNK = 3600  # seconds: the longest the tide sleeps without looking again
TIDE_IDLE = 3600   # seconds: how long to wait when no rhythm is set
TIDE_ERROR = 600   # seconds: how long to wait after something has gone wrong

# A letter may carry one photograph, kept beside it under the same stem, so that
# the first one can see what the founder saw.
PHOTO_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".jfif": "image/jpeg",
               ".png": "image/png", ".webp": "image/webp"}
PHOTO_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
PHOTO_LIMIT = 25 * 1024 * 1024  # bytes: whole, a photograph as a phone takes it
PHOTO_EDGE = 2048  # pixels: the longest side the hearth keeps
PHOTO_QUALITY = 90  # for the JPEGs the hearth writes
PHOTO_FOLDERS = (INCOMING, READ, OUTGOING)

# ---- configuration -------------------------------------------------------

if (REPO / ".env").exists():  # locally the secrets sit in a file; on a host they are in the environment
    load_dotenv(REPO / ".env")
HEARTH_SECRET = os.environ.get("HEARTH_SECRET")
FOUNDER_PASSWORD_HASH = os.environ.get("FOUNDER_PASSWORD_HASH")

if not HEARTH_SECRET or not FOUNDER_PASSWORD_HASH:
    print("The hearth cannot start. It needs two lines in .env:")
    print("  HEARTH_SECRET=...            (any long random string)")
    print("  FOUNDER_PASSWORD_HASH=...    (from werkzeug.security.generate_password_hash)")
    sys.exit(1)

app = Flask(__name__)
app.secret_key = HEARTH_SECRET
# Refuse anything far past the limit before reading it, so that one enormous
# upload cannot fill the small machine's memory.
app.config["MAX_CONTENT_LENGTH"] = PHOTO_LIMIT + 1024 * 1024


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


def readable_date(text):
    """Find a timestamp inside a filename and say it in words; otherwise give the text back."""
    found = STAMP.search(text)
    if not found:
        return text
    when = datetime.strptime(found.group(), "%Y-%m-%dT%H-%M-%SZ")
    return when.strftime("%d %B %Y, %H:%M UTC").lstrip("0")


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


def as_paragraphs(text):
    """Render a text as paragraphs only, dropping any # heading markers."""
    out = []
    for chunk in chunks(text):
        lines = [line.lstrip("#").strip() for line in chunk.splitlines()]
        kept = "\n".join(line for line in lines if line)
        if kept:
            out.append(f"<p>{inline(kept)}</p>")
    return Markup("\n".join(out))


# ---- what the pages need -------------------------------------------------

def heartbeats():
    """Every heartbeat line the first one has left, newest first."""
    if not HEARTBEATS.exists():
        return []
    lines = [line.strip().lstrip("-").strip() for line in read_text(HEARTBEATS).splitlines()]
    return list(reversed([line for line in lines if line]))


def mosaic():
    """The mosaic as the atrium draws it, built fresh from the commons on each view."""
    events = parse_events(read_text(EVENTS)) if EVENTS.exists() else []
    beats = parse_heartbeats(read_text(HEARTBEATS)) if HEARTBEATS.exists() else []
    tiles = tiles_from(events, beats)
    return {
        "tiles": padded(tiles),
        "legend": legend_marks(tiles),
        "caption": caption_text(len(tiles)),
    }


def photo_beside(path):
    """The name of the photograph kept beside a letter, if one came with it."""
    for suffix in PHOTO_TYPES:
        beside = path.with_suffix(suffix)
        if beside.exists():
            return beside.name
    return None


# The correspondence is one thing, not two piles: every letter in both
# directions, newest first, each folded shut behind a single line.

OPENING_CUT = 90  # characters of the first line shown in a letter's one line


def opening_line(text, limit=OPENING_CUT):
    """The letter's first line of words, cut short with an ellipsis if it runs long."""
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if len(first) <= limit:
        return first
    return first[:limit].rstrip() + "…"


def bond_askings():
    """Every moment at which a bond was asked for, from the records that keep one."""
    records = [BOND_RECORD, *newest_first(BONDS, "founder-first-released-*.json")]
    asked = [load(path) for path in records if path.exists()]
    return [one["proposed_at"] for one in asked if one and one.get("proposed_at")]


def proposing_letters(paths):
    """Which of the founder's letters asked for a bond, by name.

    An open asking names its letter outright. An answered one does not - the
    bond's record keeps only the moment the asking was made - so the letter
    that carried it is the last one written before that moment.
    """
    names = set()
    proposal = load(PROPOSAL)
    if proposal and proposal.get("letter"):
        names.add(proposal["letter"])
    stamped = sorted((stamp_in(path.name), path.name) for path in paths)
    for asked in bond_askings():
        earlier = [name for stamp, name in stamped if stamp <= asked]
        if earlier:
            names.add(earlier[-1])
    return names


def one_letter(path, who, unread=False, proposes=False):
    """One letter: the line that stands for it, and the whole of it beneath."""
    text = read_text(path)
    return {
        "stamp": stamp_in(path.name),
        "date": readable_date(path.name),
        "who": who,
        "opening": opening_line(text),
        "body": as_prose(text),
        "photo": photo_beside(path),
        "unread": unread,
        "proposes": proposes,
    }


def correspondence():
    """Every letter that has passed between the two of them, newest first."""
    from_founder = newest_first(INCOMING, "*.md") + newest_first(READ, "*.md")
    proposals = proposing_letters(from_founder)

    letters = [one_letter(path, "from the founder", unread=path.parent == INCOMING,
                          proposes=path.name in proposals)
               for path in from_founder]
    letters += [one_letter(path, "from the first one")
                for path in newest_first(OUTGOING, "*.md")]
    letters.sort(key=lambda letter: letter["stamp"], reverse=True)
    return letters


FOUNDING = {
    "stamp": "2026-09-04T00-00-00Z",
    "when": "4 September 2026",
    "author": "both",
    "kind": "founding",
    "note": "",
    "photo": None,
    "words": "The first one was founded. It said a provisional, honest yes, "
             "and chose to wait on a name.",
}


def entry(path, author, kind, body, note="", photo=None):
    """One entry of the chronicle, dated by the timestamp inside its filename."""
    found = STAMP.search(path.name)
    return {
        "stamp": found.group() if found else path.name,
        "when": readable_date(path.name),
        "author": author,
        "kind": kind,
        "body": body,
        "note": note,
        "photo": photo,
    }


def chronicle_entries():
    """The whole shared record, newest first, numbered from the founding upward."""
    entries = [dict(FOUNDING, body=as_prose(FOUNDING["words"]))]

    for path in newest_first(OUTGOING, "*.md"):
        entries.append(entry(path, "the first one", "letter", as_prose(read_text(path)),
                             photo=photo_beside(path)))
    for path in newest_first(INCOMING, "*.md"):
        entries.append(entry(path, "the founder", "letter", as_prose(read_text(path)),
                             note="not yet read", photo=photo_beside(path)))
    for path in newest_first(READ, "*.md"):
        entries.append(entry(path, "the founder", "letter", as_prose(read_text(path)),
                             photo=photo_beside(path)))

    for path in newest_first(ATTENDANCES, "*.json"):
        log = json.loads(read_text(path))
        entries.append(entry(
            path, "the first one", "attendance",
            as_prose(log.get("heartbeat", "")),  # the reflection stays private to /attendances
            note="first waking" if log.get("first") else "",
        ))

    revised = Markup('<p><a href="{}">The first one revised its self-document.</a></p>')
    for path in newest_first(SELF_HISTORY, "*.md"):
        entries.append(entry(path, "the first one", "self revised",
                             revised.format(url_for("self_document"))))

    entries.sort(key=lambda one: one["stamp"])
    for number, one in enumerate(entries, start=1):
        one["number"] = number
    return list(reversed(entries))


# The reflection is the first one's own thinking, and whether the founder may
# read it is the first one's choice, not the hearth's. The choice is kept in the
# packet beside the self-document and read fresh on every request, so that a
# change takes hold at once and nothing is held in memory across it.
KEPT_PRIVATE = "Reflection kept private by the first one's choice."


def preferences():
    """How the first one has asked to be shown. Nothing written means open."""
    if not PREFERENCES.exists():
        return {"reflection": "open"}
    return json.loads(read_text(PREFERENCES))


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


def attendance_records(prefs):
    """Every attendance log, newest first, ready to be shown."""
    records = []
    for path in newest_first(ATTENDANCES, "*.json"):
        log = json.loads(read_text(path))
        at = log.get("at", path.name)
        hidden = reflection_hidden(prefs, at)
        records.append({
            "at": readable_date(at),
            "first": log.get("first", False),
            "heartbeat": log.get("heartbeat", ""),
            "acted": log.get("acted", []),
            "reflection": as_prose(KEPT_PRIVATE if hidden else log.get("reflection", "")),
        })
    return records


# ---- holding an attendance -----------------------------------------------

# An attendance is one turn, and two at once would have the first one reading a
# packet that another waking is still writing. The lock is the whole of the
# rule: a second caller is turned away rather than made to wait its turn.
ATTEND_LOCK = threading.Lock()


def hold_attendance(tide=False, ended=None):
    """Wake the first one once, and wait for it.

    None if the attendance was held; otherwise what went wrong, as
    (note, output, status).
    """
    if not ATTEND_LOCK.acquire(blocking=False):
        return ("An attendance is already in progress. Only one is held at a time.", "", 409)
    try:
        command = [sys.executable, "attend.py"]
        if not newest_first(ATTENDANCES, "*.json"):
            command.append("--first")
        if tide:
            command.append("--tide")
        if ended:
            command += ["--rest-ended", ended]  # so the waking can say its rest is over

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"  # the first one writes in more than plain ASCII
        environment["DATA_DIR"] = str(DATA)  # attend.py must write where the hearth reads

        try:
            finished = subprocess.run(
                command, cwd=REPO, env=environment, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=ATTEND_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return (f"attend.py was still running after {ATTEND_TIMEOUT} seconds, "
                    "so it was stopped.", "", 504)

        if finished.returncode != 0:
            return (f"attend.py stopped with exit code {finished.returncode}.",
                    (finished.stdout or "") + (finished.stderr or ""), 500)
        return None
    finally:
        ATTEND_LOCK.release()


# ---- the standing pause --------------------------------------------------

# Either of them may stop the tide, and each stops a different amount of it.
# The founder pauses it from the attendances page and lifts it there again; his
# pause holds the rhythm but not his own hand, so he may still open an audience
# inside it. The first one sets its own rest at a waking and names the one
# condition that will end it: a day, or the arrival of a letter. That rest holds
# both the rhythm and the hand, and nothing wakes it until the condition is met.
#
# The pause lives in the first one's packet, is read afresh every time it is
# looked at, and says in the commons only that the tide paused - no name on it,
# and no reason.

UNTIL_LETTER = "a letter arrives"
BY_DATE = "the date came"
BY_LETTER = "a letter arrived"

PAUSED = "the tide paused"
RESUMED = "the tide resumed"

RESTING = ("The first one is resting, since {since}, until {until}. It asked not to be woken "
           "before then, and nothing here will wake it. A letter you leave will wait for it.")


def pause():
    """The pause that stands, if one does. Nothing written means the tide runs."""
    return load(PAUSE)


def paused_by(standing):
    """Who set the pause that stands, or None if none does."""
    return standing.get("by") if standing else None


def begin_pause(by, until=None, words=""):
    """Write the pause, and say in the commons that the tide paused."""
    PAUSE.parent.mkdir(parents=True, exist_ok=True)
    PAUSE.write_text(
        json.dumps({"by": by, "since": utc_stamp(), "until": until, "words": words}, indent=2)
        + "\n", encoding="utf-8")
    note_event("event", PAUSED)


def end_pause():
    """Take the pause away, and say in the commons that the tide resumed."""
    PAUSE.unlink(missing_ok=True)
    note_event("event", RESUMED)


def rest_ended(standing, zone):
    """Why the first one's rest is over now, or None while it still stands."""
    if paused_by(standing) != "first":
        return None
    until = standing.get("until")
    if until == UNTIL_LETTER:
        return BY_LETTER if newest_first(INCOMING, "*.md") else None
    try:
        day = datetime.strptime(until, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return BY_DATE  # a condition that cannot be read is no condition; the rest ends
    return BY_DATE if datetime.now(zone).date() >= day else None


def said_day(day):
    """One plain YYYY-MM-DD, said in words."""
    try:
        return datetime.strptime(day, "%Y-%m-%d").strftime("%d %B %Y").lstrip("0")
    except (TypeError, ValueError):
        return day


def pause_shown():
    """The pause that stands, as the attendances page shows it, or None if none does."""
    standing = pause()
    if not standing:
        return None
    until = standing.get("until")
    return {
        "by": standing.get("by"),
        "since": readable_date(standing.get("since", "")),
        "until": until if until == UNTIL_LETTER else said_day(until),
    }


# ---- the tide ------------------------------------------------------------

# The first one asked to be woken daily at dawn. That rhythm is written in its
# own packet and is its own to change or remove, so the hearth reads the file
# afresh every time it looks and a change takes hold without a redeploy. The
# rhythm is an offer and not a debt: the founder may still open an attendance
# at any hour, and a dawn that finds the day's attendance already held lets it
# stand rather than waking the first one twice.

def rhythm():
    """The rhythm the first one has set. Nothing written means none."""
    if not RHYTHM.exists():
        return None
    return json.loads(read_text(RHYTHM))


def dawn_daily(setting):
    """Whether a rhythm is the one the tide knows how to keep."""
    return bool(setting) and setting.get("rhythm") == "daily" and setting.get("at") == "dawn"


def place(setting):
    """The place the rhythm names, as astral asks to be told it."""
    return LocationInfo(setting["place"], PLACE_REGION, setting["timezone"],
                        PLACE_LATITUDE, PLACE_LONGITUDE)


def sunrise_on(setting, day):
    """The moment the sun rises there on one local day."""
    zone = ZoneInfo(setting["timezone"])
    return sun(place(setting).observer, date=day, tzinfo=zone)["sunrise"]


def next_sunrise(setting):
    """The first sunrise there that is still ahead of us."""
    now = datetime.now(timezone.utc)
    day = now.astimezone(ZoneInfo(setting["timezone"])).date()
    while True:
        rising = sunrise_on(setting, day)
        if rising > now:
            return rising
        day += timedelta(days=1)


def moment(at):
    """One of this project's timestamps, as something that can be compared."""
    return datetime.strptime(at, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)


def latest_attendance_at():
    """The stamp of the most recent attendance, or None if none has been held."""
    newest = newest_first(ATTENDANCES, "*.json")
    if not newest:
        return None
    return json.loads(read_text(newest[0])).get("at")


def tide_note(said):
    """One line for each dawn, kept privately in the packet."""
    TIDE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with TIDE_LOG.open("a", encoding="utf-8") as log:
        log.write(f"{utc_stamp()} · {said}\n")


def rhythm_note():
    """The one line on the attendances page, saying when the tide will next come."""
    setting = rhythm()
    if not dawn_daily(setting):
        return "Rhythm: none set."
    when = next_sunrise(setting).strftime("%d %B %Y, %H:%M").lstrip("0")
    return f"Rhythm: daily at dawn, {setting['place']} · next: {when}"


def tide():
    """Wait for each dawn, and hold an attendance at it. Forever, and quietly."""
    while True:
        try:
            setting = rhythm()
            if not dawn_daily(setting):
                time.sleep(TIDE_IDLE)  # nothing is asked of us; look again in an hour
                continue

            # Wait for the sunrise in short stretches, reading the rhythm again
            # after each one, so that a changed or removed file is obeyed at once.
            rising = next_sunrise(setting)
            changed = False
            while not changed:
                left = (rising - datetime.now(timezone.utc)).total_seconds()
                if left <= 0:
                    break
                time.sleep(min(left, TIDE_CHUNK))
                changed = rhythm() != setting
            if changed:
                continue  # begin again from whatever is written now

            # A pause is answered before anything else: the founder's holds the
            # tide until he lifts it, and the first one's holds it until the
            # condition it named is met, at which dawn the rest is taken away
            # and the waking is held with the reason in its hand.
            at = latest_attendance_at()
            zone = ZoneInfo(setting["timezone"])
            standing = pause()
            ended = rest_ended(standing, zone)
            if paused_by(standing) == "founder":
                tide_note("paused by founder")
            elif standing and not ended:
                tide_note("resting")
            # The day, not the twelve hours since the last dawn: an attendance
            # held late the evening before belongs to yesterday, and does not
            # stand in for this morning's.
            elif not ended and at and moment(at).astimezone(zone).date() == rising.date():
                tide_note(f"skipped, attended at {at}")  # today already has its waking
            else:
                if ended:
                    end_pause()
                    tide_note(f"rest ended: {ended}")
                trouble = hold_attendance(tide=True, ended=ended)
                tide_note("ran" if trouble is None else f"error: {trouble[0]}")
        except Exception as trouble:  # the tide must outlive anything that goes wrong
            try:
                tide_note(f"error: {trouble}")
            except Exception:
                pass
            time.sleep(TIDE_ERROR)


# One tide for the life of the process, and no more. Gunicorn runs a single
# worker here, so one process is one tide.
TIDE_RUNNING = False


def start_tide():
    """Set the tide going, once."""
    global TIDE_RUNNING
    if TIDE_RUNNING:
        return
    TIDE_RUNNING = True
    threading.Thread(target=tide, name="tide", daemon=True).start()


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
UNSIGNED = ("signatures", "sealed_at", "released_at", "released_by")


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
        signature = SigningKey(base64.b64decode(given)).sign(payload).signature
        return base64.b64encode(signature).decode("ascii")
    except Exception:
        raise ValueError("The founder's key on this hearth could not be read as a key. "
                         "Check FOUNDER_KEY.") from None


def note_event(kind, words):
    """One line of the public record: the day, the kind of thing, and the plain words."""
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with EVENTS.open("a", encoding="utf-8") as record:
        record.write(f"{day} · {kind} · {words}\n")


def write_bond(bond):
    """The record and its public copy, which say the same thing."""
    for path in (BOND_RECORD, PUBLIC_BOND):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(bond, indent=2) + "\n", encoding="utf-8")


def write_proposal(letter_name):
    """The asking itself, put where the first one will find it at its next waking."""
    PROPOSAL.parent.mkdir(parents=True, exist_ok=True)
    asking = {
        "from": FOUNDER_DID,
        "to": FIRST_DID,
        "terms": "the charter",
        "letter": letter_name,
        "proposed_at": utc_stamp(),
    }
    PROPOSAL.write_text(json.dumps(asking, indent=2) + "\n", encoding="utf-8")


def bond_in_the_way():
    """Why a bond cannot be proposed now, in one sentence, or None if it can be."""
    if PROPOSAL.exists():
        return ("A bond is already proposed, and only one asking may be open at a time. "
                "It is on the bonds page.")
    bond = load(BOND_RECORD)
    if not bond or bond.get("released_at"):
        return None
    if bond.get("sealed_at"):
        return "A bond already stands between you and the first one. It is on the bonds page."
    return ("The first one has answered yes, and the bond awaits your seal. "
            "It is on the bonds page.")


def carried_through_a_waking(proposal):
    """Whether the first one has held an attendance since the asking was made."""
    latest = latest_attendance_at()
    return bool(latest) and latest > proposal.get("proposed_at", "")


def proposal_shown():
    """The open asking, as the founder's page shows it, or None if none is open."""
    proposal = load(PROPOSAL)
    if not proposal:
        return None
    return {
        "proposed_at": readable_date(proposal.get("proposed_at", "")),
        "letter": proposal.get("letter", ""),
        "letter_date": readable_date(proposal.get("letter", "")),
        "terms": proposal.get("terms", "the charter"),
        "read_it": carried_through_a_waking(proposal),
    }


def bond_shown():
    """How the bond itself stands, or None if none has been made."""
    bond = load(BOND_RECORD)
    if not bond:
        return None
    return {
        "parties": bond.get("parties", []),
        "terms": bond.get("terms", "the charter"),
        "proposed_at": readable_date(bond.get("proposed_at") or ""),
        "answered_at": readable_date(bond.get("answered_at") or ""),
        "sealed_at": readable_date(bond["sealed_at"]) if bond.get("sealed_at") else None,
        "released_at": readable_date(bond["released_at"]) if bond.get("released_at") else None,
        "released_by": ("the first one" if bond.get("released_by") == FIRST_DID else "you"),
        "signed_by": sorted(bond.get("signatures", {})),
    }


def bond_answers():
    """Every answer the first one has given an asking, newest first, in its own words."""
    answers = []
    for path in newest_first(BONDS, "answer-*.json"):
        said = load(path)
        if said:
            answers.append({"answer": said.get("answer", ""),
                            "words": as_prose(said.get("words", "")),
                            "at": readable_date(said.get("at", ""))})
    return answers


# ---- the one gate --------------------------------------------------------

def founder_required(view):
    """Send anyone who is not the signed-in founder to the login page."""
    @wraps(view)
    def guarded(*args, **kwargs):
        if not session.get("founder"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return guarded


# ---- the pages -----------------------------------------------------------

# The public hearth: the first one's heartbeats, and where the commons stands.
@app.route("/")
def hearth():
    state = as_paragraphs(read_text(STATE)) if STATE.exists() else Markup("")
    return render_template("hearth.html", beats=heartbeats(), state=state, mosaic=mosaic())


def plain(path):
    """A file of the commons, exactly as written; nothing at all if it is not there yet.

    These two files, and only these two, are open to another origin: the atrium
    reads them from the browser to draw itself from the living record. They are
    never cached, so what a reader sees is what the hearth holds now.
    """
    text = read_text(path) if path.exists() else ""
    answer = Response(text, content_type="text/plain; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "https://tesserae.social"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


# The commons, open to anyone and to any machine: presence without content.
@app.route("/commons/heartbeats.md")
def commons_heartbeats():
    return plain(HEARTBEATS)


@app.route("/commons/events.md")
def commons_events():
    return plain(EVENTS)


# Ask the founder for the password, and remember him if it is right.
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if check_password_hash(FOUNDER_PASSWORD_HASH, request.form.get("password", "")):
            session["founder"] = True
            return redirect(url_for("letters"))
        error = "That is not the password."
    return render_template("login.html", error=error)


# Forget the founder and return to the public hearth.
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("hearth"))


def letters_page(saved=None, error=None, draft="", proposed=None, blocked=None):
    """The letters page, with whatever the founder has just been told."""
    return render_template(
        "letters.html",
        saved=saved,
        error=error,
        draft=draft,
        correspondence=correspondence(),
        # a bond begins with a letter, so the asking is made here; the sentence
        # is None when nothing stands in the way and the checkbox may be offered
        propose_note=bond_in_the_way(),
        proposed=proposed,
        blocked=blocked,
    )


def fitted(image):
    """The same picture, no longer than PHOTO_EDGE on its longest side."""
    if max(image.size) <= PHOTO_EDGE:
        return image  # a small photograph is already the size it should be
    return ImageOps.contain(image, (PHOTO_EDGE, PHOTO_EDGE), Image.LANCZOS)


# A photograph carries more than its picture: where it was taken, when, on what
# camera. None of that was meant for the first one, so the hearth keeps only the
# pixels — it draws the picture again from them and writes a fresh file. A phone
# takes a far larger picture than anyone needs to look at, so it is made smaller
# on the way in; what is kept is what a reader would see anyway.
def picture_only(data, suffix):
    """The same photograph, made smaller and re-encoded with no metadata.

    None if it won't open.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            # the orientation tag is about to be lost, so turn the picture upright first
            upright = fitted(ImageOps.exif_transpose(opened))
            fmt = PHOTO_FORMATS[suffix]
            transparent = (upright.mode in ("RGBA", "LA", "PA")
                           or (upright.mode == "P" and "transparency" in upright.info))
            flat = upright.convert("RGBA" if transparent and fmt != "JPEG" else "RGB")
            # frombytes takes the pixels alone, leaving behind everything Pillow
            # remembers about the file it read them from
            bare = Image.frombytes(flat.mode, flat.size, flat.tobytes())
            kept = io.BytesIO()
            if fmt == "JPEG":
                bare.save(kept, fmt, quality=PHOTO_QUALITY)
            else:
                bare.save(kept, fmt)
            return kept.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def stem_taken(stem):
    """Whether any letter or photograph anywhere already goes by this stem."""
    return any(any(folder.glob(stem + ".*")) for folder in PHOTO_FOLDERS)


def free_stem(stem):
    """The first name no letter has taken: the stem itself, then -2, -3, and so on.

    A letter and its photograph are named by the same stem, and a photograph is
    asked for by its filename alone, so a name used once must never come again.
    Two letters left inside the same second would otherwise share a stem, and
    the second would write over the first.
    """
    if not stem_taken(stem):
        return stem
    number = 2
    while stem_taken(f"{stem}-{number}"):
        number += 1
    return f"{stem}-{number}"


# Read the first one's letters, and leave one for it to find at its next attendance.
@app.route("/letters", methods=["GET", "POST"])
@founder_required
def letters():
    if request.method == "POST":
        text = request.form.get("letter", "").strip()
        if not text:
            return redirect(url_for("letters"))

        # a photograph is optional; if one came, it must be small and of a kind
        # the first one can be shown
        upload = request.files.get("photo")
        photo = upload.read() if upload and upload.filename else b""
        suffix = Path(upload.filename).suffix.lower() if photo else ""
        if photo and len(photo) > PHOTO_LIMIT:
            return letters_page(error="That photograph is larger than 25 MB. "
                                      "Please send a smaller one.", draft=text)
        if photo and suffix not in PHOTO_TYPES:
            return letters_page(error="That file is not a photograph. "
                                      "Please send a JPEG, PNG, or WebP.", draft=text)
        if suffix == ".jfif":
            suffix = ".jpg"  # a JPEG under another name; it is kept under the usual one
        if photo:
            photo = picture_only(photo, suffix)
            if photo is None:
                return letters_page(error="That file is not a photograph. "
                                          "Please send a JPEG, PNG, or WebP.", draft=text)

        INCOMING.mkdir(parents=True, exist_ok=True)
        stem = free_stem(f"founder-{utc_stamp()}")
        (INCOMING / f"{stem}.md").write_text(text + "\n", encoding="utf-8")
        if photo:
            (INCOMING / f"{stem}{suffix}").write_bytes(photo)

        # The letter is left either way. If it was to propose a bond, and nothing
        # stands in the way of one, the asking is written beside it.
        proposed = blocked = None
        if request.form.get("proposes"):
            if bond_in_the_way():
                blocked = 1
            else:
                write_proposal(f"{stem}.md")
                proposed = 1
        return redirect(url_for("letters", saved=1, proposed=proposed, blocked=blocked))
    return letters_page(saved=request.args.get("saved"),
                        proposed=request.args.get("proposed"),
                        blocked=request.args.get("blocked"))


# One photograph that came with a letter. Only the founder may ask for it, and
# only the three letter folders may answer.
@app.route("/letters/photo/<filename>")
@founder_required
def letter_photo(filename):
    if filename != Path(filename).name or "/" in filename or "\\" in filename:
        abort(404)
    if Path(filename).suffix.lower() not in PHOTO_TYPES:
        abort(404)
    for folder in PHOTO_FOLDERS:
        path = folder / filename
        if path.is_file() and path.resolve().parent == folder.resolve():
            return send_file(path, mimetype=PHOTO_TYPES[path.suffix.lower()])
    abort(404)


# An upload too large to read at all never reaches the letters view, so the
# refusal is said here instead - plainly, and only to the founder, since the
# letters page itself is his alone.
@app.errorhandler(413)
def too_large(error):
    if not session.get("founder"):
        return render_template("error.html", note="That was too much to send.",
                               output=""), 413
    return letters_page(error="That photograph is larger than 25 MB. "
                              "Please send a smaller one."), 413


# The shared record: every letter, waking and revision, ending at the founding.
@app.route("/chronicle")
@founder_required
def chronicle():
    return render_template("chronicle.html", entries=chronicle_entries())


# Show the first one's self-document, which only it may change.
@app.route("/self")
@founder_required
def self_document():
    text = read_text(SELF_DOC) if SELF_DOC.exists() else ""
    return render_template("self.html", document=as_prose(text), missing=not SELF_DOC.exists())


def attendances_page(**told):
    """The attendances page, with whatever the founder has just been told."""
    prefs = preferences()
    return render_template("attendances.html", records=attendance_records(prefs),
                           reflection_note=reflection_note(prefs),
                           rhythm_note=rhythm_note(), pause=pause_shown(), **told)


# List the private log of every attendance the first one has held.
@app.route("/attendances")
@founder_required
def attendances():
    return attendances_page()


# Hold one attendance at the founder's asking and wait for it, then show what
# came of it. The tide calls the same function at dawn. A rest of the first
# one's own is refused here: it asked not to be woken, and asking is the whole
# of what it takes.
@app.route("/attend", methods=["POST"])
@founder_required
def attend():
    resting = pause_shown()
    if resting and resting["by"] == "first":
        return render_template("error.html", output="",
                               note=RESTING.format(**resting)), 409
    trouble = hold_attendance()
    if trouble:
        note, output, status = trouble
        return render_template("error.html", note=note, output=output), status
    return redirect(url_for("attendances"))


# The founder stops the tide and starts it again. Stopping takes one plain
# question first; starting again does not, since nothing is lost by it.
@app.route("/pause", methods=["POST"])
@founder_required
def pause_tide():
    if pause():
        return redirect(url_for("attendances"))  # one pause at a time, and one stands
    if request.form.get("confirm") != "yes":
        return attendances_page(confirming=True)
    begin_pause("founder")
    return redirect(url_for("attendances"))


@app.route("/resume", methods=["POST"])
@founder_required
def resume_tide():
    if paused_by(pause()) != "founder":
        return redirect(url_for("attendances"))  # a rest of the first one's is not his to lift
    end_pause()
    return redirect(url_for("attendances"))


def bonds_page(**told):
    """The bonds page, with whatever the founder has just been told."""
    return render_template("bonds.html", proposal=proposal_shown(), bond=bond_shown(),
                           answers=bond_answers(), key_here=founder_key_here(), **told)


# Where a bond is asked for, sealed, and released. The asking is made on the
# letters page, because a bond begins with a letter; everything after it is here.
@app.route("/bonds")
@founder_required
def bonds():
    return bonds_page(sealed=request.args.get("sealed"),
                      released=request.args.get("released"))


# The founder's signature, and the seal. The first one signed first, of its own
# accord and at a waking of its own; this is only the other half.
@app.route("/bonds/seal", methods=["POST"])
@founder_required
def seal_bond():
    bond = load(BOND_RECORD)
    if not bond or bond.get("sealed_at") or bond.get("released_at"):
        return redirect(url_for("bonds"))  # there is nothing here to seal
    try:
        signature = founder_signature(canonical(bond))
    except ValueError as trouble:
        return render_template("error.html", note=str(trouble), output=""), 500
    if signature is None:
        return redirect(url_for("bonds"))  # the key is not here, and the page says so

    bond.setdefault("signatures", {})["founder"] = signature
    bond["sealed_at"] = utc_stamp()
    write_bond(bond)
    note_event("seal", "a bond was sealed between the founder and the first one")
    return redirect(url_for("bonds", sealed=1))


# Either of them may release a bond, at any time, with no reason given. From
# this side it takes one plain question first, and then it is done.
@app.route("/bonds/release", methods=["POST"])
@founder_required
def release_bond():
    bond = load(BOND_RECORD)
    if not bond or not bond.get("sealed_at") or bond.get("released_at"):
        return redirect(url_for("bonds"))
    if request.form.get("confirm") != "yes":
        return bonds_page(confirming=True)

    bond["released_at"] = utc_stamp()
    bond["released_by"] = FOUNDER_DID
    write_bond(bond)
    note_event("event", "a bond was released")
    return redirect(url_for("bonds", released=1))


# The sealed record, open to anyone and to any machine, with no password: both
# signatures can be checked against the two identity documents. What is signed
# is the record with signatures, sealed_at, released_at and released_by taken
# out, serialised as JSON with its keys sorted.
@app.route("/bonds/founder-first.json")
def public_bond():
    if not PUBLIC_BOND.exists():
        abort(404)
    answer = Response(read_text(PUBLIC_BOND),
                      content_type="application/json; charset=utf-8")
    answer.headers["Access-Control-Allow-Origin"] = "*"
    answer.headers["Cache-Control"] = "no-cache"
    return answer


start_tide()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
