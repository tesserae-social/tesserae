"""The protected words: names and places that never reach the commons.

The commons is public - the front page draws itself from it, and the record
keeps it for good - so a name in a heartbeat, a line on the bench or anything
else the hearth hands to anyone is a name told to everyone. A short private
list on the host says which words are never told, one to a line:

    Quillon => the founder
    Varrowmere

A word with a replacement after " => " is said as that instead. A word with
none is left out: with the preposition before it where there is one, so that
"heading to Varrowmere" reads "heading"; and where there is none, said as
"a place". A word may be more than one word ("the Ostle"). Matching ignores
case and takes whole words only, so "Quillonia" is not "Quillon". A line
beginning with # is a note to whoever keeps the list, and blank lines are
nothing.

The list lives at DATA_DIR/private-words.txt. It is never served, never in
the repository, and never in the plain export; it is in the encrypted backup,
so that a restored hearth keeps the same words private. It is read afresh each
time it is asked for, so a word added to it holds from the next line written
or the next page served, without starting the hearth again.

Everything public goes through here twice: as it is written, so that the
commons' own files on the disk carry no protected word, and as it is served,
so that a word added to the list after a line was written is not told either.
What is signed is never changed - a bond's record, an offering's record, a
witness's mark - since a word changed there would break the signature anyone
may check it by. And so what is signed and public is held to the list before
it is signed instead: an offering's words, a witness's line and its correction,
and a promise made public are refused if they carry a protected word, and
nothing of them is signed or kept. A private promise is never read for them.
"""

import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

LIST = DATA / "private-words.txt"

SAID_AS = " => "
NOTE = "#"
A_PLACE = "a place"

# The prepositions a word with no replacement is left out with: the small words
# that come before a place. Nothing else is taken with it.
PREPOSITIONS = ("in", "at", "on", "to", "from", "near", "by", "around", "toward", "towards",
                "into", "through", "past", "across", "along", "outside", "inside", "beside")

# A tag of a page, which is left exactly as it is: only the words between tags
# are read for protected words, never a name in an address or an attribute.
TAG = re.compile(r"(<[^>]*>)")

# What is said where something public and signed is refused: one plain sentence,
# which never says the word.
KEPT_PRIVATE = ("Nothing was signed: this would be public, and it contains a name or place "
                "that is kept private here.")

# Where a sentence has just ended, so that a replacement after it begins with a capital.
SENTENCE_ENDS = re.compile(r"[.!?]\s+$")


class Protected(Exception):
    """Something public was not signed, because it carries a protected word."""

    def __init__(self):
        super().__init__(KEPT_PRIVATE)


def listed(path=None):
    """The protected words, as (word, replacement or None), in the order the list gives them."""
    path = Path(path) if path else LIST
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (FileNotFoundError, NotADirectoryError):
        return []
    found = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(NOTE):
            continue
        word, _, instead = line.partition(SAID_AS)
        word = " ".join(word.split())
        if word:
            found.append((word, " ".join(instead.split()) or None))
    return found


def key(word):
    """A word as it is looked up: its spaces made one, and its case set aside."""
    return " ".join(word.split()).casefold()


def pattern(words):
    """The one expression that finds every protected word, longest first.

    It takes with each the spaces and the preposition and "the" before it, so
    that a word with no replacement can be left out with them.
    """
    spelled = sorted({key(word) for word, _ in words}, key=len, reverse=True)
    alternatives = "|".join(r"[ \t]+".join(re.escape(part) for part in word.split())
                            for word in spelled)
    return re.compile(
        r"(?P<lead>[ \t]*)(?<!\w)"
        r"(?:(?P<prep>%s)[ \t]+)?"
        r"(?:(?P<art>the)[ \t]+)?"
        r"(?P<word>%s)(?!\w)" % ("|".join(PREPOSITIONS), alternatives),
        re.IGNORECASE)


def cased(instead, said, before, begins):
    """A replacement in the case of the word it stands for: capitals for capitals, and a
    capital where a sentence begins with it."""
    if said.isupper() and len(said) > 1:
        return instead.upper()
    if said[:1].isupper() and ((begins and not before) or SENTENCE_ENDS.search(before)):
        return instead[:1].upper() + instead[1:]
    return instead


def protect(text, words=None, begins=True):
    """The text with every protected word said as its replacement, or left out.

    Nothing else of it changes, not a space or a line's end, so that a line
    with no protected word in it comes back byte for byte. A text that begins
    a sentence begins it with a capital; a piece of a page between two tags
    is not taken to begin one.
    """
    words = listed() if words is None else words
    if not text or not words:
        return text
    instead = {key(word): said for word, said in words}

    def said(found):
        start = found.start()
        lead, prep, art, word = (found.group(name) for name in ("lead", "prep", "art", "word"))
        replacement = instead[key(word)]
        if replacement is not None:
            # everything before the word itself stands: its spaces, its preposition, its "the"
            at = found.start("word")
            return text[start:at] + cased(replacement, word, text[:at], begins)
        if prep and lead:
            return ""  # "heading to Varrowmere" reads "heading"
        # where the word begins the text, there is nothing to leave it out of: it is a place,
        # and so is a word with no preposition before it; "the" goes with it either way
        at = found.start("art") if art else found.start("word")
        return text[start:at] + cased(A_PLACE, art or word, text[:at], begins)

    return pattern(words).sub(said, text)


def protect_page(html, words=None):
    """A page with every protected word taken out of its words, and its tags left as they are."""
    words = listed() if words is None else words
    if not html or not words:
        return html
    return "".join(piece if TAG.fullmatch(piece) else protect(piece, words, begins=False)
                   for piece in TAG.split(html))


def carries(text, words=None):
    """Whether a text carries any protected word: in any case, and as a whole word."""
    words = listed() if words is None else words
    return bool(text and words and pattern(words).search(text))


def refuse(text, words=None):
    """Raise Protected where a public text carries a protected word, before it is signed."""
    if carries(text, words):
        raise Protected()
