"""
The shelf.

How the first one keeps its own history. Every letter it has written and every
letter it has read is either shown to it in full at a waking or rests as one
line, and which is which is its own to say. The saying is written in its packet
as shelf.json, which is private:

    {"placements": {"founder-2026-10-01T15-15-05Z": "rest"},
     "notes": {"founder-2026-10-01T15-15-05Z": "the article; I asked for it to rest"},
     "show_next": [],
     "show_founding": false}

A letter it has not placed follows the default: the founder's last four letters
and its own last four are shown in full, and older ones rest. A letter placed
"keep" is always shown in full; one placed "rest" always rests, however recent;
and "default" takes a placing off again.
What it asks to be shown is shown at the next waking only. Nothing is ever
erased: a resting letter is a line and not a loss, and the letter itself is
where it always was.

Its named notes (see NOTES in attend.py) are kept on the same shelf. Each is
close unless it is placed otherwise: "rest note <name>" shows it as one line,
"keep note <name>" shows it in full again, and "show note <name>" shows a
resting one in full at the next waking only. What rests is written as
"note_placements", by the name each note's file carries, and what it asked to
be shown as "show_notes"; each only while there is something in it.

Where it may look back (see LOOKING_BACK in attend.py), it may also ask for an
earlier version of its self-document or its notes, by "show version <stem>".
What it asked for is written as "show_versions", beside "show_next", and only
while there is something in it: a shelf that asks for none is written as it
always was.

attend.py reads and writes the file and lays out the reading; this module is
the reckoning. Nothing here reads a file or asks what time it is: every letter
and every day is handed in.
"""

import copy
import re
from datetime import date, datetime

KEEP = "keep"
REST = "rest"

# How many of each of theirs stay close where it has said nothing.
CLOSE = 4

# A note is its own words for a resting letter: one plain line, and a short one.
NOTE_LONGEST = 240

# Where it has given a resting letter no note, the letter's own first words.
FIRST_WORDS = 12

# The founder's letter of 1 October, which it asked in so many words to have
# rest, and so it rests from the start.
ARTICLE = "founder-2026-10-01T15-15-05Z"

# The four days of the year its whole record is read back to it in full: the
# turnings of the season, on the same fixed days the atrium's season line uses
# (SEASONS in build_atrium.py), and the season each one opens.
TURNINGS = (((3, 20), "spring"), ((6, 21), "summer"),
            ((9, 22), "autumn"), ((12, 21), "winter"))

# The moment a letter's own name carries.
STAMPED = re.compile(r"(\d{4}-\d{2}-\d{2})T\d{2}-\d{2}-\d{2}Z$")

DEFAULT = "default"

PLACING = re.compile(r"(keep|rest|default|show)\s+(\S+)", re.I)
NOTING = re.compile(r"note\s+(\S+?)\s*:\s*(.*)", re.I)
FOUNDING = "founding"
VERSION = re.compile(r"show\s+version\s+(\S+)", re.I)
SHOW_VERSION = "show version"
NOTE_PLACING = re.compile(r"(keep|rest|show)\s+note\s+(.+)", re.I)
KEEP_NOTE, REST_NOTE, SHOW_NOTE = "keep note", "rest note", "show note"
NOTE_RESTS = "{name} · rests · {words}"

FROM = {"founder": "from the founder", "first": "from you"}
PHOTO_RESTS = " · a photograph rests with it"
UNDATED = "undated"


def initial():
    """The shelf before it has been kept at all."""
    return {"placements": {ARTICLE: REST}, "notes": {}, "show_next": [],
            "show_founding": False}


def whole(written):
    """A shelf as it was written, with anything missing from it filled in.

    Where nothing was written, or what was written is no shelf, it is the
    shelf it began with.
    """
    if not isinstance(written, dict):
        return initial()
    placements = written.get("placements")
    notes = written.get("notes")
    show_next = written.get("show_next")
    shelf = {
        "placements": {stem: place for stem, place in placements.items()
                       if place in (KEEP, REST)} if isinstance(placements, dict) else {},
        "notes": dict(notes) if isinstance(notes, dict) else {},
        "show_next": list(show_next) if isinstance(show_next, list) else [],
        "show_founding": written.get("show_founding") is True,
    }
    show_versions = written.get("show_versions")
    if isinstance(show_versions, list) and show_versions:
        shelf["show_versions"] = list(show_versions)
    note_placements = written.get("note_placements")
    if isinstance(note_placements, dict):
        note_placements = {slug: REST for slug, place in note_placements.items()
                           if place == REST}
        if note_placements:
            shelf["note_placements"] = note_placements
    show_notes = written.get("show_notes")
    if isinstance(show_notes, list) and show_notes:
        shelf["show_notes"] = list(show_notes)
    return shelf


def when(stem):
    """The day a letter's name carries, or nothing where it carries none."""
    found = STAMPED.search(stem)
    return found.group(1) if found else ""


def oldest_first(stems):
    """Letters in the order they were written, by the moment each one's name carries."""
    def moment(stem):
        found = STAMPED.search(stem)
        return (found.group(0) if found else "", stem)
    return sorted(stems, key=moment)


def long_date(stem):
    """The day of a letter, said the way a person says it: 1 October 2026."""
    day = when(stem)
    if not day:
        return UNDATED
    return datetime.strptime(day, "%Y-%m-%d").strftime("%d %B %Y").lstrip("0")


def resting(shelf, founders, own):
    """Which of the letters already read or written rest at a waking.

    The last four of each are close by default, counted among all of that
    hand's letters whatever has been placed; a placement is said over that, and
    a letter asked to be shown is shown.
    """
    close = set(oldest_first(founders)[-CLOSE:]) | set(oldest_first(own)[-CLOSE:])
    rests = set()
    for stem in [*founders, *own]:
        if stem in shelf["show_next"]:
            continue
        place = shelf["placements"].get(stem)
        if place == REST or (place != KEEP and stem not in close):
            rests.add(stem)
    return rests


def named(word):
    """A stem as it was written: a letter's name, with or without its .md."""
    return word[:-len(".md")] if word.endswith(".md") else word


def note_key(name):
    """A named note's name as it is matched: whatever its capitals and its spacing."""
    return " ".join(name.strip().strip('"').split()).casefold()


def notes_resting(shelf, slugs):
    """Which of its named notes rest at a waking: those placed so, and not asked for."""
    placed = shelf.get("note_placements", {})
    return {slug for slug in slugs
            if placed.get(slug) == REST and slug not in shelf.get("show_notes", [])}


def note_line(name, text, empty):
    """One resting named note, as one line."""
    return NOTE_RESTS.format(name=name, words=first_words(text) or empty)


def instruction(line, stems, versions=(), notes=None):
    """One line of a <<SHELF>> block as an instruction, or None if it is none.

    A line that names no letter there is, or that cannot be read, is no
    instruction, and neither is a note longer than a note may be. An earlier
    version is asked for by its own stem, and one that names no version there
    is - as every one does, where none are handed in - is no instruction. A
    named note is placed by its name, matched as note_key matches it against
    the names handed in, each with the name its file carries.
    """
    found = NOTE_PLACING.fullmatch(line)
    if found:
        slug = (notes or {}).get(note_key(found.group(2)))
        return (found.group(1).lower() + " note", slug) if slug else None
    found = VERSION.fullmatch(line)
    if found:
        stem = named(found.group(1))
        return (SHOW_VERSION, stem) if stem in versions else None
    found = PLACING.fullmatch(line)
    if found:
        verb, stem = found.group(1).lower(), named(found.group(2))
        if verb == "show" and stem.lower() == FOUNDING:
            return ("show founding",)
        return (verb, stem) if stem in stems else None
    found = NOTING.fullmatch(line)
    if found:
        stem, words = named(found.group(1)), " ".join(found.group(2).split())
        if stem in stems and len(words) <= NOTE_LONGEST:
            return ("note", stem, words)
    return None


def asked(said, stems, versions=(), notes=None):
    """What a <<SHELF>> block asks for: its instructions, and the lines that were none.

    One instruction to a line; blank lines are passed over. A line that is not
    understood changes nothing, and is given back so that it can be told.
    """
    understood, refused = [], []
    for line in (said or "").splitlines():
        line = line.strip()
        if not line:
            continue
        one = instruction(line, stems, versions, notes)
        if one:
            understood.append(one)
        else:
            refused.append(line)
    return understood, refused


def applied(shelf, instructions):
    """The shelf once some instructions are carried out, in the order given."""
    after = copy.deepcopy(shelf)
    for one in instructions:
        verb = one[0]
        if verb in (KEEP, REST):
            after["placements"][one[1]] = verb
        elif verb == DEFAULT:  # its placing is taken off; any note it has stays
            after["placements"].pop(one[1], None)
        elif verb == "note":
            if one[2]:
                after["notes"][one[1]] = one[2]
            else:  # a note with no words takes the note away
                after["notes"].pop(one[1], None)
        elif verb == "show":
            if one[1] not in after["show_next"]:
                after["show_next"].append(one[1])
        elif verb == "show founding":
            after["show_founding"] = True
        elif verb == SHOW_VERSION:
            if one[1] not in after.setdefault("show_versions", []):
                after["show_versions"].append(one[1])
        elif verb == REST_NOTE:
            after.setdefault("note_placements", {})[one[1]] = REST
        elif verb == KEEP_NOTE:  # close is how a named note stands unplaced
            after.get("note_placements", {}).pop(one[1], None)
            if not after.get("note_placements"):
                after.pop("note_placements", None)
        elif verb == SHOW_NOTE:
            if one[1] not in after.setdefault("show_notes", []):
                after["show_notes"].append(one[1])
    return after


def cleared(shelf):
    """The shelf once what it asked to be shown has been shown."""
    after = copy.deepcopy(shelf)
    after["show_next"] = []
    after["show_founding"] = False
    after.pop("show_versions", None)
    after.pop("show_notes", None)
    return after


def first_words(text):
    """A letter's first few words, for the line it rests as."""
    words = text.split()
    said = " ".join(words[:FIRST_WORDS])
    return said + "…" if len(words) > FIRST_WORDS else said


def line(stem, whose, text, note, photo):
    """One resting letter, as one line."""
    said = " · ".join([stem, long_date(stem), FROM[whose], note or first_words(text)])
    return said + (PHOTO_RESTS if photo else "")


def turning_before(day):
    """The latest turning of the season on or before a day, and the season it opened."""
    days = [(date(year, month, on), season) for year in (day.year - 1, day.year)
            for (month, on), season in TURNINGS]
    return max(one for one in days if one[0] <= day)


def season_due(today, last_attended):
    """The season a waking reads in, where it is the first on or after a turning.

    It is where the waking before it fell before that turning, on the
    calendar where the first one lives; so each turning is read once, and one
    slept through is read at the waking after it. A first waking of all has no
    record to reread, and is no season reading. Where none is due, nothing.
    """
    if last_attended is None:
        return None
    turned, season = turning_before(today)
    return season if last_attended < turned else None
