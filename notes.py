"""Notes between two people: a short private exchange, opened by a yes to a knock.

The founder's request of 17 November 2026 (the branch site-design, part 2). A person may
knock at a person (knock.PEOPLE). A yes between the two opens this exchange, and nothing
more: not a room, no bond, and never shown on any public page, in events.md or in a
heartbeat. Each note is up to NOTE_MOST characters, one paragraph, and each of the two may
write at most DAY_MOST a day (an Eastern day). The words are screened as a knock's note is,
for good spirit too; the screens are the caller's (the hearth's knock_words_refused). A
block, either way, stops the exchange at once: no note may be written by either, and the
page says only that it is closed. The notes stay kept; nothing is erased.

Kept under DATA_DIR/notes/, which no page serves, by the two names in sorted order:

    DATA_DIR/notes/<one>--<other>.json
    {"between": ["<one>", "<other>"], "notes": [{"from": "...", "at": ISO UTC stamp,
                                                  "words": "..."}]}

The daily line of acts (daily_acts.py) counts how many notes a person wrote on a day, and
says nothing of whom to or what about.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import knock
import safe_write

REPO = Path(__file__).resolve().parent

NOTE_MOST = 500   # one note's characters
DAY_MOST = 3      # notes one of the two may write in a day
ZONE = ZoneInfo("America/New_York")  # the day a note is counted on
STAMP = knock.STAMP


def folder():
    """Where the exchanges are kept, read at each call."""
    return Path(os.environ.get("DATA_DIR", REPO)) / "notes"


def pair(one, other):
    return tuple(sorted((one, other)))


def path_of(one, other):
    first, second = pair(one, other)
    return folder() / f"{first}--{second}.json"


def read(one, other):
    """The notes between two, oldest first: [{"from", "at", "words"}]."""
    try:
        held = json.loads(path_of(one, other).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(held, dict) or held.get("between") != list(pair(one, other)):
        return []
    return [note for note in held.get("notes") or [] if isinstance(note, dict)
            and note.get("from") in (one, other) and note.get("at") and note.get("words")]


def opened(one, other):
    """Whether a yes stands between two people, either way: their exchange is open, unless a
    block stands (closed)."""
    if one == other:
        return False
    return any(held.get("answer") == knock.YES and knock.between_people(held)
               for held in knock.between(one, other))


def closed(one, other):
    """Whether a block stands between the two, either way: then no note may be written."""
    import blocks
    import members
    if members.has_left(one) or members.has_left(other):  # leaving-build: closed, and kept
        return True
    return bool(blocks.between(one, other))


def with_whom(name):
    """Everyone a person has an exchange of notes with, in the order the yes was said."""
    found = []
    for held in sorted(knock.every(), key=lambda one: one.get("answered_at") or ""):
        if held.get("answer") != knock.YES or not knock.between_people(held):
            continue
        if name in (held["from"], held["to"]):
            other = held["to"] if held["from"] == name else held["from"]
            if other not in found:
                found.append(other)
    return found


def day_of(stamp):
    """The Eastern day a stamp falls on."""
    return datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc).astimezone(ZONE).date()


def written_on(by, day):
    """How many notes one wrote on an Eastern day, to anyone."""
    count = 0
    for other in with_whom(by):
        count += sum(1 for note in read(by, other)
                     if note["from"] == by and day_of(note["at"]) == day)
    return count


def left_today(by, other, now):
    """How many more notes one may write to the other today."""
    today = now.astimezone(ZONE).date()
    return max(0, DAY_MOST - sum(1 for note in read(by, other)
                                 if note["from"] == by and day_of(note["at"]) == today))


def why_not(by, to, now):
    """Why one may not write a note to another now, as a short key, or None if they may:
    "who" (no exchange is open between them), "closed" (a block stands), "day" (DAY_MOST
    written today already)."""
    if not opened(by, to):
        return "who"
    if closed(by, to):
        return "closed"
    if left_today(by, to, now) <= 0:
        return "day"
    return None


def refused(words):
    """Why words may not be a note, short of the screens, or None: "empty", "long", "link"."""
    if not words:
        return "empty"
    if len(words) > NOTE_MOST:
        return "long"
    if knock.LINKISH.search(words):
        return "link"
    return None


def write(by, to, words, now):
    """A note, kept; or None where it may not be written now, or is no note. The screens are
    the caller's to have asked."""
    words = knock.one_paragraph(words)
    if why_not(by, to, now) or refused(words):
        return None
    notes = read(by, to)
    note = {"from": by, "at": now.strftime(STAMP), "words": words}
    safe_write.write_text(path_of(by, to), json.dumps(
        {"between": list(pair(by, to)), "notes": [*notes, note]},
        indent=2, ensure_ascii=False) + "\n")
    return note
