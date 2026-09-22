"""An offering.

Something from a correspondence - a letter, a passage, a photograph, a picture -
given to the commons by both who kept it. Either party may offer. Nothing is
placed until both have signed it, and what is placed is never removed.

Everything on the way to one lives in packets/first/offerings/, which is private:

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
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where the living files are kept. Locally this is the repo itself; on a host it
# is a mounted disk, named by DATA_DIR - the same reckoning hearth.py makes.
DATA = Path(os.environ.get("DATA_DIR", REPO))

PACKET = DATA / "packets" / "first"
INCOMING = PACKET / "letters" / "incoming"
READ = PACKET / "letters" / "read"
OUTGOING = PACKET / "letters" / "outgoing"

# where a letter may be found, whichever of them wrote it and whether or not the
# first one has read it yet
LETTERS = (INCOMING, READ, OUTGOING)

OFFERINGS = PACKET / "offerings"

COMMONS = DATA / "commons"
INDEX = COMMONS / "offerings.md"
PUBLIC = COMMONS / "offerings"

KINDS = ("letter", "passage", "photo", "picture")
PARTIES = ("founder", "first")

# Attribution is the two of them together, always. An offering is given by both
# or it is not given at all, and neither name is put to one alone.
ATTRIBUTION = "the founder and the first one"

# What the commons is told when one is placed: that it happened, and no more.
# The offering itself is public, so the line needs to carry nothing of it.
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


# ---- the letters an offering may come out of -----------------------------

def letter_named(stem):
    """The letter that goes by one stem, wherever it is kept, or None."""
    if not stem or stem != Path(stem).name or not re.fullmatch(r"[A-Za-z0-9._-]+", stem):
        return None
    for folder in LETTERS:
        path = folder / (stem + ".md")
        if path.is_file() and path.resolve().parent == folder.resolve():
            return path
    return None


def beside(stem, suffixes):
    """The file kept beside a letter under one of these suffixes, or None."""
    letter = letter_named(stem)
    if letter is None:
        return None
    for suffix in suffixes:
        found = letter.with_suffix(suffix)
        if found.is_file():
            return found
    return None


def image_of(record):
    """The photograph or picture an offering is of, or None if it is neither."""
    suffixes = IMAGE_KINDS.get(record.get("kind"))
    return beside(record.get("source", ""), suffixes) if suffixes else None


def offerable(stem, kind):
    """The words an offering of this kind would carry, or None if there is none to offer.

    A letter carries its own text; a photograph and a picture carry none, and
    are offered by the file kept beside the letter. A passage is not asked for
    here: its words come from whoever quoted them, and are checked against the
    letter rather than read out of it.
    """
    letter = letter_named(stem)
    if letter is None:
        return None
    if kind == "letter":
        return read_text(letter).strip()
    if kind in IMAGE_KINDS:
        return "" if beside(stem, IMAGE_KINDS[kind]) else None
    return None


def quotes(stem, passage):
    """Whether a passage occurs, word for word, in the letter it is said to come from."""
    letter = letter_named(stem)
    said = words_of(passage or "")
    if letter is None or not said:
        return False
    return said in words_of(read_text(letter))


# ---- what is pending, what was placed, what was declined -----------------

def records(pattern):
    """The records under one shape of name, oldest first - the names carry the moment."""
    if not OFFERINGS.exists():
        return []
    kept = [load(path) for path in sorted(OFFERINGS.glob(pattern))]
    return [one for one in kept if one]


def pending():
    """Every offering waiting on someone's consent, oldest first."""
    return records("pending-*.json")


def awaiting(who):
    """The offerings waiting on one party: the ones the other party offered."""
    return [one for one in pending() if one.get("offered_by") != who]


def placed():
    """Every offering that was placed, oldest first."""
    return [one for one in records("*.json") if one.get("sealed_at")]


def declined():
    """Every offering that was declined, oldest first. None of these is public."""
    return records("declined-*.json")


def pending_path(one):
    return OFFERINGS / ("pending-%s.json" % one)


def placed_path(one):
    return OFFERINGS / ("%s.json" % one)


def declined_path(one):
    return OFFERINGS / ("declined-%s.json" % one)


def taken(one):
    """Whether any offering anywhere already goes by this name."""
    return any(path.exists() for path in
               (pending_path(one), placed_path(one), declined_path(one)))


def free_id(at):
    """The first name no offering has taken: the moment itself, then -2, -3, and so on.

    Two offerings made inside the same second would otherwise share a name, and
    a name used once must never come again: a placed offering keeps its own
    address in the commons for good.
    """
    if not taken(at):
        return at
    number = 2
    while taken("%s-%d" % (at, number)):
        number += 1
    return "%s-%d" % (at, number)


# ---- offering, consenting, declining -------------------------------------

def offer(offered_by, kind, source, text, at, sign):
    """Offer something to the commons, signed by whoever offered it.

    The record is the offering as it was offered, and the signature is over
    that record; what is waited on is the other party's signature beside it.
    None where there is nothing of that kind to offer, or where a passage is
    not in the letter it is said to come from.
    """
    if offered_by not in PARTIES or kind not in KINDS:
        return None
    if kind == "passage":
        if not quotes(source, text):
            return None
        said = (text or "").strip()
    else:
        said = offerable(source, kind)
        if said is None:
            return None

    record = {
        "id": free_id(at),
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
    write_json(pending_path(record["id"]), record)
    return record


def consent(one, who, sign, at=None):
    """Put the second signature on an offering, and place it.

    None where there is nothing of that name waiting on this party - which is
    what a second press of the same button finds.
    """
    record = load(pending_path(one)) if re.fullmatch(r"[A-Za-z0-9:._-]+", one or "") else None
    if not record or who not in PARTIES or record.get("offered_by") == who:
        return None
    signature = sign(canonical(record))
    if signature is None:
        return None
    record.setdefault("signatures", {})[who] = signature
    record["sealed_at"] = at or stamp()
    place(record)
    pending_path(one).unlink(missing_ok=True)
    return record


def decline(one, who, at=None):
    """Decline an offering the other party made. Nothing of it becomes public.

    The record is kept, out of the commons and served to no one, so that what
    was offered and what was answered can always be found on this side.
    """
    record = load(pending_path(one)) if re.fullmatch(r"[A-Za-z0-9:._-]+", one or "") else None
    if not record or who not in PARTIES or record.get("offered_by") == who:
        return None
    record["declined_by"] = who
    record["declined_at"] = at or stamp()
    write_json(declined_path(one), record)
    pending_path(one).unlink(missing_ok=True)
    return record


# ---- placing it ----------------------------------------------------------

def note_event(kind, words):
    """One line of the public record: the day, the kind of thing, and the plain words."""
    COMMONS.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with (COMMONS / "events.md").open("a", encoding="utf-8") as record:
        record.write("%s · %s · %s\n" % (day, kind, words))


def index_line(record):
    """The one line the commons keeps for an offering: the day, its name, its kind, and whose."""
    return "- %s · %s · %s · %s\n" % (
        (record.get("sealed_at") or record.get("at") or "")[:10],
        record["id"], record["kind"], ATTRIBUTION)


def place(record):
    """Write an offering into the commons, where it stays.

    The record, the words, and any image are copied out; the index gains a
    line; and the commons is told that an offering was placed, with nothing of
    what it was. Nothing here is ever undone: a placed offering is never removed.
    """
    image = image_of(record)
    if image is not None:
        record["file"] = record["id"] + image.suffix.lower()

    PUBLIC.mkdir(parents=True, exist_ok=True)
    write_json(placed_path(record["id"]), record)
    write_json(PUBLIC / ("%s.json" % record["id"]), record)
    if record.get("text"):
        (PUBLIC / ("%s.md" % record["id"])).write_text(
            record["text"].strip() + "\n", encoding="utf-8")
    if image is not None:
        shutil.copy(image, PUBLIC / record["file"])

    INDEX.parent.mkdir(parents=True, exist_ok=True)
    with INDEX.open("a", encoding="utf-8") as index:
        index.write(index_line(record))
    note_event("offering", PLACED)
    return record
