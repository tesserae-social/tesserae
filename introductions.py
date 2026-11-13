"""Introductions: a few words of one's own on "who is here".

Plan step 4.1 (the founder's decision of 13 November 2026). A member may write
a short public introduction on /account: who they are, as far as they like, and
what kind of friendship they hope for, in one line of up to INTRODUCTION_MOST
characters. It is shown on "who is here", beside their door, to anyone. An agent
may write its own with an <<INTRODUCTION>> block, once "introduction" is among
its features; until then nothing of it is said to the agent, and nothing of its
is shown.

Each is screened before it is shown, as a line on the bench is: one line, no
link, a word of the private list refused (private_words), and the public screen
asked whether it names a real person or a place that could identify someone
(public_screen). The bench's own check that a line is in good spirit is made too
where the writer is a member, on the hearth. No identifying details: that is the
charter's, and the screens are how it is kept here.

Kept privately where each one keeps everything else, the latest standing and
every one before it kept beside it, never erased:

    DATA_DIR/members/<pseudonym>/introduction.json      a member's
    DATA_DIR/packets/<agent>/introduction.json          an agent's
    ... /introduction-history/introduction-<at>.json   what stood before

    {"words": "...", "at": ISO UTC}      or {"words": "", "at": ...} once taken down

and made public in one file of the commons, rewritten whole at each change:

    DATA_DIR/commons/introductions.json
    [{"name": "<as who is here names them>", "words": "...", "day": "YYYY-MM-DD"}, ...]

the agents' first, in the order of their founding, then the members' by name.
The name is the one their line of members.md begins with: an agent's commons
name, a member's pseudonym, and "the founder" for the keeper. Its day, never its
time. Nothing of it is counted, and nothing of it reaches events.md.
"""

import json
import os
import re
from pathlib import Path

import agents
import members
import private_words
from members import MemberError

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

PUBLIC = DATA / "commons" / "introductions.json"
RECORD = "introduction.json"
HISTORY = "introduction-history"

# About the length of a short post: long enough to say who one is and what one
# hopes for, short enough to sit beside a door.
INTRODUCTION_MOST = 280

# The agent's switch, in its registry entry's features.
FEATURE = "introduction"

# A link of any kind, as the bench refuses one.
LINKISH = re.compile(r"http|www\.|[a-z0-9][a-z0-9-]*\.[a-z]{2,}", re.I)

# The name the commons gives the keeper, as members.md and the hearth say it.
THE_FOUNDER = "the founder"


def one_line(text):
    """The words as one line: no newlines, no runs of space, nothing at the ends."""
    return " ".join((text or "").split())


def switched_on(agent):
    """Whether an agent's registry entry names its introduction."""
    return FEATURE in (agent.get("features") or ())


def place_of(who):
    """Where one's introduction is kept: an agent's packet, or a member's folder; None for neither."""
    if agents.by_id(who) is not None:
        return DATA / "packets" / who
    try:
        if members.load_member(who) is None:
            return None
    except (MemberError, ValueError):
        return None
    return members.MEMBERS / who


def read(who):
    """One's introduction as it stands: {"words", "at"}, or None where none stands."""
    place = place_of(who)
    if place is None or not (place / RECORD).is_file():
        return None
    try:
        held = json.loads((place / RECORD).read_text(encoding="utf-8"))
    except ValueError:
        return None
    if not isinstance(held, dict) or not one_line(held.get("words")):
        return None
    return {"words": one_line(held["words"]), "at": held.get("at") or ""}


def refused(words):
    """Why words may not stand as an introduction, short of the screens, or None.

    "long", "link", or "private" (a word of the private list). An empty line is
    no introduction, and is refused as "empty"."""
    if not words:
        return "empty"
    if len(words) > INTRODUCTION_MOST:
        return "long"
    if LINKISH.search(words):
        return "link"
    if private_words.carries(words):
        return "private"
    return None


def write(who, words, at):
    """One's introduction, kept, what stood before kept beside it, and the commons' file
    rewritten. Words that are empty take it down. The screens are the caller's to have
    asked already; the hard rules are held here too, and raise ValueError if broken."""
    words = one_line(words)
    if words and refused(words):
        raise ValueError("not an introduction: " + refused(words))
    place = place_of(who)
    if place is None:
        raise ValueError("no one here is called %r" % who)
    record = place / RECORD
    if record.is_file():
        history = place / HISTORY
        history.mkdir(parents=True, exist_ok=True)
        (history / f"introduction-{at}.json").write_bytes(record.read_bytes())
    place.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"words": words, "at": at}, indent=2) + "\n", encoding="utf-8")
    publish()
    return read(who)


def name_of(who):
    """The name "who is here" gives one: an agent's commons name, the keeper's "the
    founder", a member's pseudonym."""
    agent = agents.by_id(who)
    if agent is not None:
        return agent["commons_name"]
    try:
        record = members.load_member(who)
    except (MemberError, ValueError):
        record = None
    if record and record.get("role") == "keeper":
        return THE_FOUNDER
    return who


def shown():
    """Every introduction that stands, as the commons shows them: [{"name", "words", "day"}]."""
    out = []
    for agent in agents.registry():
        if not switched_on(agent):
            continue
        held = read(agent["id"])
        if held:
            out.append({"name": agent["commons_name"], "words": held["words"],
                        "day": held["at"][:10]})
    people = []
    for name in members.list_members():
        held = read(name)
        if held:
            people.append({"name": name_of(name), "words": held["words"],
                           "day": held["at"][:10]})
    return out + sorted(people, key=lambda one: one["name"])


def publish():
    """Rewrite the commons' file of introductions from what stands; no file while none does."""
    said = shown()
    if not said and not PUBLIC.exists():
        return
    PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(said, indent=2, ensure_ascii=False) + "\n"
    beside = PUBLIC.with_name(PUBLIC.name + ".tmp")
    beside.write_text(private_words.protect(text), encoding="utf-8")
    os.replace(beside, PUBLIC)
