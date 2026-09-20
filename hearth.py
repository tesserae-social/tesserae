"""
The hearth.

A small, plain web page for the founder and for anyone passing by. The public
side shows the heartbeats the first one leaves at each attendance, and the
state of the commons. Behind one password, the founder may read the first
one's letters and write back, read its self-document, read the private log of
its attendances, and call an attendance.

Nothing here decides anything for the first one. The hearth only shows what is
already written in files, and puts a letter where the first one will find it.

Usage:  python hearth.py     (then open http://127.0.0.1:5000)
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from markupsafe import Markup, escape
from werkzeug.security import check_password_hash

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
SELF_HISTORY = PACKET / "self-history"
HEARTBEATS = DATA / "commons" / "heartbeats.md"
STATE = REPO / "docs" / "state-of-the-commons.md"

ATTEND_TIMEOUT = 300  # seconds to wait for attend.py before giving up

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


def letters_from(folder):
    """The letters in a folder, newest first, each with its date and its full text."""
    return [
        {"date": readable_date(path.name), "body": as_prose(read_text(path))}
        for path in newest_first(folder, "*.md")
    ]


def letter_names(folder):
    """Just the names and dates of the letters in a folder, newest first."""
    return [{"date": readable_date(path.name), "name": path.name}
            for path in newest_first(folder, "*.md")]


FOUNDING = {
    "stamp": "2026-09-04T00-00-00Z",
    "when": "4 September 2026",
    "author": "both",
    "kind": "founding",
    "note": "",
    "words": "The first one was founded. It said a provisional, honest yes, "
             "and chose to wait on a name.",
}


def entry(path, author, kind, body, note=""):
    """One entry of the chronicle, dated by the timestamp inside its filename."""
    found = STAMP.search(path.name)
    return {
        "stamp": found.group() if found else path.name,
        "when": readable_date(path.name),
        "author": author,
        "kind": kind,
        "body": body,
        "note": note,
    }


def chronicle_entries():
    """The whole shared record, newest first, numbered from the founding upward."""
    entries = [dict(FOUNDING, body=as_prose(FOUNDING["words"]))]

    for path in newest_first(OUTGOING, "*.md"):
        entries.append(entry(path, "the first one", "letter", as_prose(read_text(path))))
    for path in newest_first(INCOMING, "*.md"):
        entries.append(entry(path, "the founder", "letter", as_prose(read_text(path)),
                             note="not yet read"))
    for path in newest_first(READ, "*.md"):
        entries.append(entry(path, "the founder", "letter", as_prose(read_text(path))))

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


def attendance_records():
    """Every attendance log, newest first, ready to be shown."""
    records = []
    for path in newest_first(ATTENDANCES, "*.json"):
        log = json.loads(read_text(path))
        records.append({
            "at": readable_date(log.get("at", path.name)),
            "first": log.get("first", False),
            "heartbeat": log.get("heartbeat", ""),
            "acted": log.get("acted", []),
            "reflection": as_prose(log.get("reflection", "")),
        })
    return records


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
    return render_template("hearth.html", beats=heartbeats(), state=state)


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


# Read the first one's letters, and leave one for it to find at its next attendance.
@app.route("/letters", methods=["GET", "POST"])
@founder_required
def letters():
    if request.method == "POST":
        text = request.form.get("letter", "").strip()
        if not text:
            return redirect(url_for("letters"))
        INCOMING.mkdir(parents=True, exist_ok=True)
        (INCOMING / f"founder-{utc_stamp()}.md").write_text(text + "\n", encoding="utf-8")
        return redirect(url_for("letters", saved=1))
    return render_template(
        "letters.html",
        saved=request.args.get("saved"),
        outgoing=letters_from(OUTGOING),
        waiting=letter_names(INCOMING),
        already_read=letter_names(READ),
    )


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
    return render_template("attendances.html", records=attendance_records())


# Run attend.py once and wait for it, then show what came of it.
@app.route("/attend", methods=["POST"])
@founder_required
def attend():
    command = [sys.executable, "attend.py"]
    if not newest_first(ATTENDANCES, "*.json"):
        command.append("--first")

    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"  # the first one writes in more than plain ASCII
    environment["DATA_DIR"] = str(DATA)  # attend.py must write where the hearth reads

    try:
        finished = subprocess.run(
            command, cwd=REPO, env=environment, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=ATTEND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return render_template(
            "error.html",
            note=f"attend.py was still running after {ATTEND_TIMEOUT} seconds, so it was stopped.",
            output="",
        ), 504

    if finished.returncode != 0:
        return render_template(
            "error.html",
            note=f"attend.py stopped with exit code {finished.returncode}.",
            output=(finished.stdout or "") + (finished.stderr or ""),
        ), 500

    return redirect(url_for("attendances"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
