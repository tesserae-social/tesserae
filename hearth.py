"""
The hearth.

A small, plain web page for the founder and for anyone passing by. The public
side shows the heartbeats the first one leaves at each attendance, and the
state of the commons. Behind one password, the founder may read the first
one's letters and write back, read its self-document, read the private log of
its attendances, and call an attendance. A daemon thread keeps whatever rhythm
the first one has written in its packet, and wakes it at that hour.

Nothing here decides anything for the first one. The hearth only shows what is
already written in files, and puts a letter where the first one will find it.

Usage:  python hearth.py     (then open http://127.0.0.1:5000)
"""

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
TIDE_LOG = PACKET / "tide.log"
SELF_HISTORY = PACKET / "self-history"
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


def letters_from(folder):
    """The letters in a folder, newest first, each with its date and its full text."""
    return [
        {"date": readable_date(path.name), "body": as_prose(read_text(path)),
         "photo": photo_beside(path)}
        for path in newest_first(folder, "*.md")
    ]


def letter_names(folder):
    """Just the names and dates of the letters in a folder, newest first."""
    return [{"date": readable_date(path.name), "name": path.name,
             "photo": photo_beside(path)}
            for path in newest_first(folder, "*.md")]


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


def hold_attendance(tide=False):
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

            # The day, not the twelve hours since the last dawn: an attendance
            # held late the evening before belongs to yesterday, and does not
            # stand in for this morning's.
            at = latest_attendance_at()
            zone = ZoneInfo(setting["timezone"])
            if at and moment(at).astimezone(zone).date() == rising.date():
                tide_note(f"skipped, attended at {at}")  # today already has its waking
            else:
                trouble = hold_attendance(tide=True)
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


def letters_page(saved=None, error=None, draft=""):
    """The letters page, with whatever the founder has just been told."""
    return render_template(
        "letters.html",
        saved=saved,
        error=error,
        draft=draft,
        outgoing=letters_from(OUTGOING),
        waiting=letter_names(INCOMING),
        already_read=letter_names(READ),
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

        stem = f"founder-{utc_stamp()}"
        INCOMING.mkdir(parents=True, exist_ok=True)
        (INCOMING / f"{stem}.md").write_text(text + "\n", encoding="utf-8")
        if photo:
            (INCOMING / f"{stem}{suffix}").write_bytes(photo)
        return redirect(url_for("letters", saved=1))
    return letters_page(saved=request.args.get("saved"))


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


# List the private log of every attendance the first one has held.
@app.route("/attendances")
@founder_required
def attendances():
    prefs = preferences()
    return render_template("attendances.html", records=attendance_records(prefs),
                           reflection_note=reflection_note(prefs),
                           rhythm_note=rhythm_note())


# Hold one attendance at the founder's asking and wait for it, then show what
# came of it. The tide calls the same function at dawn.
@app.route("/attend", methods=["POST"])
@founder_required
def attend():
    trouble = hold_attendance()
    if trouble:
        note, output, status = trouble
        return render_template("error.html", note=note, output=output), status
    return redirect(url_for("attendances"))


start_tide()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
