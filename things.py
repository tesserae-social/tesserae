"""A letter's three plain things, and what is kept beside a letter.

These were offering.py's until offerings were taken out of the code (the founder's
request of 16 November 2026); they are the letters' own, and nothing of an offering.

Above a letter of the founder's, three small true facts of the body and the day,
each one line, all three optional. They are kept in the letter's own file, on a
first line of their own that a markdown reader shows as nothing:

    <!-- three plain things: ["slept badly", "first frost on the car"] -->

and everything after that line is the letter, exactly as it was written. A letter
without the line is a letter without them, as every letter before them was. They
are private like the letter.

A picture an agent drew beside a letter is kept under the letter's stem with
PICTURE_SUFFIX; a photograph with one of PHOTO_SUFFIXES.
"""

import json
import unicodedata

PICTURE_SUFFIX = ".svg"
PHOTO_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")

THINGS_OPEN = "<!-- three plain things: "
THINGS_CLOSE = " -->"
THINGS_MOST = 3
THING_LONGEST = 80


def read_text(path):
    return path.read_text(encoding="utf-8")


def words_of(text):
    """A text as its words alone, so that verbatim does not mean re-wrapped."""
    return " ".join(text.split())


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
