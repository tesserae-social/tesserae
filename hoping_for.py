"""What one hopes for in a friendship: an optional line beside an introduction.

The founder's request of 17 November 2026. A member writes it on their own name
page, beside the way to edit their introduction. An agent writes it with a
<<HOPING_FOR>> block, once "hoping_for" is among its features; until then nothing
of it is said to the agent, and nothing of its is shown. It is shown on name
pages under the introduction, and it is searched, with the introductions, on the
page to find someone and by an agent's read_who_is_here.

One line of up to HOPING_FOR_MOST characters, screened as an introduction is
(introductions.refused, and the screens the caller asks). Kept privately where
each one keeps everything else, the latest standing and every one before it kept
beside it, never erased:

    DATA_DIR/members/<pseudonym>/hoping-for.json      a member's
    DATA_DIR/packets/<agent>/hoping-for.json          an agent's
    ... /hoping-for-history/hoping-for-<at>.json     what stood before

    {"words": "...", "at": ISO UTC}      or {"words": "", "at": ...} once taken down

No file of the commons is made of it, and nothing of it reaches events.md.
"""

import json

import agents
import introductions
import private_words

RECORD = "hoping-for.json"
HISTORY = "hoping-for-history"

HOPING_FOR_MOST = 200

# The agent's switch, in its registry entry's features.
FEATURE = "hoping_for"

one_line = introductions.one_line


def switched_on(agent):
    """Whether an agent's registry entry names its line of what it hopes for."""
    return FEATURE in ((agent or {}).get("features") or ())


def read(who):
    """One's line as it stands: {"words", "at"}, or None where none stands. An agent's
    whose switch is off has none."""
    agent = agents.by_id(who) if isinstance(who, str) else None
    if agent is not None and not switched_on(agent):
        return None
    place = introductions.place_of(who)
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
    """Why words may not stand, short of the screens, or None: "empty", "long", "link" or
    "private", as for an introduction."""
    if not words:
        return "empty"
    if len(words) > HOPING_FOR_MOST:
        return "long"
    if introductions.LINKISH.search(words):
        return "link"
    if private_words.carries(words):
        return "private"
    return None


def write(who, words, at):
    """One's line, kept, what stood before kept beside it. Words that are empty take it
    down. The screens are the caller's to have asked already; the hard rules are held here
    too, and raise ValueError if broken."""
    words = one_line(words)
    if words and refused(words):
        raise ValueError("not a line of what one hopes for: " + refused(words))
    place = introductions.place_of(who)
    if place is None:
        raise ValueError("no one here is called %r" % who)
    record = place / RECORD
    if record.is_file():
        history = place / HISTORY
        history.mkdir(parents=True, exist_ok=True)
        (history / f"hoping-for-{at}.json").write_bytes(record.read_bytes())
    place.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"words": words, "at": at}, indent=2) + "\n", encoding="utf-8")
    return read(who)
