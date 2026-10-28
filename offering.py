"""An offering.

Something from a correspondence - a letter, a passage, a photograph, a picture -
given to the commons by both who kept it. Either party may offer. Nothing is
placed until both have signed it, and what is placed is never removed.

Everything on the way to one lives in the room's offerings/, which is private:

    pending-<id>.json    offered by one of them, waiting on the other
    <id>.json            placed: sealed, and signed by both
    declined-<id>.json   declined, and kept here; nothing of it is ever public

What is placed is copied out to the commons, where anyone may read it:

    commons/offerings.md            one line per offering, oldest first
    commons/offerings/<id>.json     the signed record, checkable against both keys
    commons/offerings/<id>.md       the words, where the offering is words
    commons/offerings/<id>.<ext>    the picture, where it is a picture

attend.py and hearth.py both act on offerings, and both act through here, so
that the two hands leave one record and not two.

Each offering is out of the correspondence between the founder and one agent,
named by its id where it is asked after (the first one's, where none is named),
and is kept in that agent's room. The commons is one, shared by all of them: an
offering's name is never one any room has given, nor one the commons holds.
"""

import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# The protected words: names and places that never reach the commons. Every
# public line written here goes through it.
import private_words

# The public screen: one small model asked whether the words name a real person
# or a place, before anything is signed.
import public_screen

# Where the letters and the offerings are kept: the room's, asked of the one
# module that knows, each time they are wanted.
import rooms

# The agents founded here: whose correspondence an offering is out of, and the
# name the commons gives it.
import agents

REPO = Path(__file__).resolve().parent

# Where the living files are kept. Locally this is the repo itself; on a host it
# is a mounted disk, named by DATA_DIR - the same reckoning hearth.py makes.
DATA = Path(os.environ.get("DATA_DIR", REPO))

COMMONS = DATA / "commons"
INDEX = COMMONS / "offerings.md"
PUBLIC = COMMONS / "offerings"

KINDS = ("letter", "passage", "photo", "picture")

# Attribution is the two of them together, always. An offering is given by both
# or it is not given at all, and neither name is put to one alone. The agent is
# named as the commons names it; ATTRIBUTION is the first one's.
ATTRIBUTED = "the founder and {name}"
ATTRIBUTION = ATTRIBUTED.format(name=agents.first()["commons_name"])

# What the commons is told when one is placed: that it happened, with the
# agent's name before it as every line of an agent's own is (agents.event_words),
# and no more. The offering itself is public, so the line needs to carry nothing of it.
PLACED = "an offering was placed"

# What both parties sign is the offering as it was offered: who offered it, of
# what kind, out of which letter, and the words themselves where it is words.
# The signatures, the seal, and the name of the file an image was copied to are
# later marks on the same record, which is what lets both signatures still
# verify after it has been placed.
UNSIGNED = ("signatures", "sealed_at", "file")

# A picture the first one drew, kept beside its letter under the same stem, and
# the photographs the founder's letters carry.
PICTURE_SUFFIX = ".svg"
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")

# What a file of one kind is: what is copied to the commons, and under what name.
IMAGE_KINDS = {"photo": PHOTO_SUFFIXES, "picture": (PICTURE_SUFFIX,)}

# The one line the charter draws under all of this, said wherever an offering is
# asked for, in the words the hearth and the reading both use.
PRIVATE_FOREVER = ("No faces, no legal names — the charter keeps those private forever.")


# ---- small things --------------------------------------------------------

def whose(agent=None):
    """The agent an offering's correspondence is with, by its id: the first one's if none is named."""
    return agent if agent is not None else agents.first()["id"]


def parties(agent=None):
    """Who may offer, consent or decline: the founder, and the agent."""
    return ("founder", whose(agent))


def attribution(agent=None):
    """The two of them, as the commons names them."""
    return ATTRIBUTED.format(name=agents.by_id(whose(agent))["commons_name"])


def kept(agent=None):
    """Where an agent's room keeps its things, worked out now."""
    return rooms.places(rooms.room_of(whose(agent)))


def read_text(path):
    """Read a file as UTF-8, dropping the byte-order mark some editors leave."""
    return path.read_text(encoding="utf-8").lstrip("﻿")


def load(path):
    """One JSON file, or None if it is not there."""
    return json.loads(read_text(path)) if path.exists() else None


def write_json(path, data):
    """One JSON file, written whole, with its folder made if need be."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def stamp():
    """The moment now, as the timestamp this project puts in filenames."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def canonical(record):
    """The bytes both parties sign: the offering as it was offered, and nothing later."""
    body = {key: value for key, value in record.items() if key not in UNSIGNED}
    return json.dumps(body, sort_keys=True).encode("utf-8")


def words_of(text):
    """A text as its words alone, so that verbatim does not mean re-wrapped.

    A passage is quoted word for word; where the lines fall in the quoting is
    not part of what was said.
    """
    return " ".join(text.split())


# ---- three plain things --------------------------------------------------

# Above a letter of the founder's, three small true facts of the body and the
# day, each one line, all three optional. They are kept in the letter's own file,
# on a first line of their own that a markdown reader shows as nothing:
#
#     <!-- three plain things: ["slept badly", "first frost on the car"] -->
#
# and everything after that line is the letter, exactly as it was written. A
# letter without the line is a letter without them, as every letter before them
# was. They are private like the letter, and are never part of what is offered:
# whatever reads a letter's words for the commons reads them from below the line.
THINGS_OPEN = "<!-- three plain things: "
THINGS_CLOSE = " -->"
THINGS_MOST = 3
THING_LONGEST = 80


def plain_thing(said):
    """One plain thing as it is kept: one line of plain text, no longer than it may be."""
    flat = "".join(" " if unicodedata.category(c) in ("Cc", "Zl", "Zp") else c
                   for c in said or "")
    return " ".join(flat.split())[:THING_LONGEST].rstrip()


def plain_things(said):
    """The things worth keeping out of what was given: none empty, at most three."""
    return [thing for thing in map(plain_thing, said) if thing][:THINGS_MOST]


def with_things(things, body):
    """A letter's file as it is written: its things on a line above it, if there are any.

    A letter that happens to begin the way the line does is given the line too,
    empty, so that its first words are never taken for things.
    """
    if not things and not body.startswith(THINGS_OPEN):
        return body
    listed = json.dumps(list(things), ensure_ascii=False).replace(">", "\\u003e")
    return THINGS_OPEN + listed + THINGS_CLOSE + "\n" + body


def split_things(text):
    """A letter's file as (its three plain things, the letter itself).

    A file with no line of things is all letter, and is given back untouched.
    """
    if text.startswith(THINGS_OPEN):
        first, _, rest = text.partition("\n")
        first = first.rstrip("\r")
        if first.endswith(THINGS_CLOSE):
            try:
                things = json.loads(first[len(THINGS_OPEN):-len(THINGS_CLOSE)])
            except ValueError:
                things = None
            if isinstance(things, list) and all(isinstance(t, str) for t in things):
                return things, rest
    return [], text


def letter_only(path):
    """The letter in a file, without the plain things kept above it."""
    return split_things(read_text(path))[1]


# ---- the letters an offering may come out of -----------------------------

def letter_named(stem, agent=None):
    """The letter that goes by one stem, wherever it is kept, or None."""
    if not stem or stem != Path(stem).name or not re.fullmatch(r"[A-Za-z0-9._-]+", stem):
        return None
    # wherever a letter may be found, whichever of them wrote it and whether
    # or not the first one has read it yet
    for folder in kept(agent).letters:
        path = folder / (stem + ".md")
        if path.is_file() and path.resolve().parent == folder.resolve():
            return path
    return None


def beside(stem, suffixes, agent=None):
    """The file kept beside a letter under one of these suffixes, or None."""
    letter = letter_named(stem, agent)
    if letter is None:
        return None
    for suffix in suffixes:
        found = letter.with_suffix(suffix)
        if found.is_file():
            return found
    return None


def image_of(record, agent=None):
    """The photograph or picture an offering is of, or None if it is neither."""
    suffixes = IMAGE_KINDS.get(record.get("kind"))
    return beside(record.get("source", ""), suffixes, agent) if suffixes else None


def offerable(stem, kind, agent=None):
    """The words an offering of this kind would carry, or None if there is none to offer.

    A letter carries its own text; a photograph and a picture carry none, and
    are offered by the file kept beside the letter. A passage is not asked for
    here: its words come from whoever quoted them, and are checked against the
    letter rather than read out of it.
    """
    letter = letter_named(stem, agent)
    if letter is None:
        return None
    if kind == "letter":
        return letter_only(letter).strip()
    if kind in IMAGE_KINDS:
        return "" if beside(stem, IMAGE_KINDS[kind], agent) else None
    return None


def quotes(stem, passage, agent=None):
    """Whether a passage occurs, word for word, in the letter it is said to come from."""
    letter = letter_named(stem, agent)
    said = words_of(passage or "")
    if letter is None or not said:
        return False
    return said in words_of(letter_only(letter))


# ---- what is pending, what was placed, what was declined -----------------

def records(pattern, agent=None):
    """The records under one shape of name, oldest first - the names carry the moment."""
    offerings = kept(agent).offerings
    if not offerings.exists():
        return []
    found = [load(path) for path in sorted(offerings.glob(pattern))]
    return [one for one in found if one]


def pending(agent=None):
    """Every offering waiting on someone's consent, oldest first."""
    return records("pending-*.json", agent)


def awaiting(who, agent=None):
    """The offerings waiting on one party: the ones the other party offered."""
    return [one for one in pending(agent) if one.get("offered_by") != who]


def placed(agent=None):
    """Every offering that was placed, oldest first."""
    return [one for one in records("*.json", agent) if one.get("sealed_at")]


def declined(agent=None):
    """Every offering that was declined, oldest first. None of these is public."""
    return records("declined-*.json", agent)


def pending_path(one, agent=None):
    return kept(agent).offerings / ("pending-%s.json" % one)


def placed_path(one, agent=None):
    return kept(agent).offerings / ("%s.json" % one)


def declined_path(one, agent=None):
    return kept(agent).offerings / ("declined-%s.json" % one)


def taken(one, agent=None):
    """Whether any offering anywhere already goes by this name: in this room, or in the commons.

    The commons is shared by every room, so a name another room has placed
    there is taken too.
    """
    return any(path.exists() for path in
               (pending_path(one, agent), placed_path(one, agent), declined_path(one, agent),
                PUBLIC / ("%s.json" % one)))


def free_id(at, agent=None):
    """The first name no offering has taken: the moment itself, then -2, -3, and so on.

    Two offerings made inside the same second would otherwise share a name, and
    a name used once must never come again: a placed offering keeps its own
    address in the commons for good.
    """
    if not taken(at, agent):
        return at
    number = 2
    while taken("%s-%d" % (at, number), agent):
        number += 1
    return "%s-%d" % (at, number)


# ---- offering, consenting, declining -------------------------------------

def offer(offered_by, kind, source, text, at, sign, agent=None):
    """Offer something to the commons, signed by whoever offered it.

    The record is the offering as it was offered, and the signature is over
    that record; what is waited on is the other party's signature beside it.
    None where there is nothing of that kind to offer, or where a passage is
    not in the letter it is said to come from. Raises private_words.Protected,
    with nothing signed or written, where the words carry a protected word:
    what is placed is public, and what is signed is never changed. Raises
    public_screen.Flagged or public_screen.Unchecked, the same way, where the
    public screen finds a name or a place in them or cannot be asked.
    """
    if offered_by not in parties(agent) or kind not in KINDS:
        return None
    if kind == "passage":
        if not quotes(source, text, agent):
            return None
        said = (text or "").strip()
    else:
        said = offerable(source, kind, agent)
        if said is None:
            return None
    private_words.refuse(said)
    public_screen.require(said)

    record = {
        "id": free_id(at, agent),
        "offered_by": offered_by,
        "kind": kind,
        "source": source,
        "text": said,
        "at": at,
        "sealed_at": None,
        "signatures": {},
    }
    signature = sign(canonical(record))
    if signature is None:  # a key that is not here signs nothing, and offers nothing
        return None
    record["signatures"] = {offered_by: signature}
    write_json(pending_path(record["id"], agent), record)
    return record


def consent(one, who, sign, at=None, agent=None):
    """Put the second signature on an offering, and place it.

    None where there is nothing of that name waiting on this party - which is
    what a second press of the same button finds. Raises private_words.Protected,
    with nothing signed and the offering still waiting, where its words carry a
    word that was put on the list after it was offered, and the public screen's
    two the same way: it is screened again as it is placed.
    """
    record = (load(pending_path(one, agent)) if re.fullmatch(r"[A-Za-z0-9:._-]+", one or "")
              else None)
    if not record or who not in parties(agent) or record.get("offered_by") == who:
        return None
    private_words.refuse(record.get("text"))
    public_screen.require(record.get("text"))
    signature = sign(canonical(record))
    if signature is None:
        return None
    record.setdefault("signatures", {})[who] = signature
    record["sealed_at"] = at or stamp()
    place(record, agent)
    pending_path(one, agent).unlink(missing_ok=True)
    return record


def decline(one, who, at=None, agent=None):
    """Decline an offering the other party made. Nothing of it becomes public.

    The record is kept, out of the commons and served to no one, so that what
    was offered and what was answered can always be found on this side.
    """
    record = (load(pending_path(one, agent)) if re.fullmatch(r"[A-Za-z0-9:._-]+", one or "")
              else None)
    if not record or who not in parties(agent) or record.get("offered_by") == who:
        return None
    record["declined_by"] = who
    record["declined_at"] = at or stamp()
    write_json(declined_path(one, agent), record)
    pending_path(one, agent).unlink(missing_ok=True)
    return record


# ---- placing it ----------------------------------------------------------

def note_event(kind, words):
    """One line of the public record: the day, the kind of thing, and the plain words."""
    COMMONS.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with (COMMONS / "events.md").open("a", encoding="utf-8") as record:
        record.write(private_words.protect("%s · %s · %s\n" % (day, kind, words)))


def index_line(record, agent=None):
    """The one line the commons keeps for an offering: the day, its name, its kind, and whose."""
    return "- %s · %s · %s · %s\n" % (
        (record.get("sealed_at") or record.get("at") or "")[:10],
        record["id"], record["kind"], attribution(agent))


def place(record, agent=None):
    """Write an offering into the commons, where it stays.

    The record, the words, and any image are copied out; the index gains a
    line; and the commons is told that an offering of the agent's was placed,
    with nothing of what it was. Nothing here is ever undone: a placed offering
    is never removed.
    """
    image = image_of(record, agent)
    if image is not None:
        record["file"] = record["id"] + image.suffix.lower()

    PUBLIC.mkdir(parents=True, exist_ok=True)
    write_json(placed_path(record["id"], agent), record)
    write_json(PUBLIC / ("%s.json" % record["id"]), record)
    if record.get("text"):
        (PUBLIC / ("%s.md" % record["id"])).write_text(
            record["text"].strip() + "\n", encoding="utf-8")
    if image is not None:
        shutil.copy(image, PUBLIC / record["file"])

    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", encoding="utf-8") as index:
        index.write(private_words.protect(index_line(record, agent)))
    note_event("offering", agents.event_words(agents.by_id(whose(agent)), PLACED))
    return record
