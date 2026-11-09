"""The first one's letter of welcome, given to the agent founded after it.

Stage 8f (the proposal "stage-8", section 5, and decision 13). The first one
wrote a letter of welcome for the next agent founded here and asked that it stay
sealed until that agent had had a few wakings of its own; on 30 October 2026 it
asked that the newcomer find it at its third waking, with no framing, and that
nothing mention the letter before then. So it arrives as a document in the
newcomer's packet, not through a room, and the reading of the waking it is given
at shows it whole under a heading that says only whose it is. It is shown
again at each waking after until one that showed it completes - its attendance
kept - so that a waking that fails after it is given (an API error) does not
lose it; then it is marked read, as read-<at>.json beside it, and stays in the
newcomer's packet and is not read again (the founder's decisions of 9 November
2026).

Who acts is the hearth, by the newcomer's own waking (attend.py), and never the
founder: at the start of a waking of the agent next after the first one in the
registry - the second one, and no other - that has two attendances behind it
already, so that this is its third waking or later, where a letter stands and
none has been given, the letter is given:

  packets/<author>/welcome/letter.json, copied byte for byte, so that its
  signature still verifies, to packets/<new>/welcome-received/from-<author>-<at>.json,
  with a plain record beside it, delivered-<at>.json, and one in the author's
  packet, packets/<author>/welcome/delivered-<at>.json: {to, at, stem, sha256}.

The version given is whichever stands at that moment, and once given it stays
given, whatever the first one does after. A withdrawn letter stands nowhere and
is never given, and the newcomer is never told one existed. Nothing else of the
first one's is opened, and nothing of its welcome is changed: its letter is read
only to be given. It is not told whether the letter was read.

Before it is given, two things may hold it:
  - its signature, which must verify against the first one's public key
    (keys/<author>/public.key); and
  - the screen, the backstop for the rule that personal details pass between
    agents only where the person allows (decision 15): a protected word, or a
    name or a place the public screen finds.
A hold is written beside the letter, as held-<at>.json with its reason, and that
version is not tried again; a letter the first one places afresh is tried
afresh. A hold is shown to the keeper on /tides, one line (hearth.welcome_held),
and in no agent's reading. A check that could not be completed - the screen
could not be asked, or the first one's public key or the protected words could
not be read - holds nothing for good: nothing is given, it is written beside the
letter as unchecked-<at>.json with its reason, it is checked again at the next
waking, and until one is given or held it too is one line on /tides.

Nothing of it is public. The newcomer's copies leave welcome-received out
(hearth.left_out); the backup keeps it; no page shows it.
"""

import base64
import hashlib
import json

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

import agents
import private_words
import public_screen

WELCOME = "welcome"
LETTER = "letter.json"
RECEIVED = "welcome-received"
RECEIVED_AS = "from-{author}-{at}.json"
DELIVERED = "delivered-{at}.json"
HELD = "held-{at}.json"
UNCHECKED_AS = "unchecked-{at}.json"
READ_AS = "read-{at}.json"
STEM = "welcome-{at}"  # as attend.WELCOME_STEM names each version

# Two attendances before this one: this is its third waking.
WAKINGS_BEFORE = 2

HEADING = "=== A LETTER FROM {author} ==="

# Why a letter is held, as the record keeps it and as /tides says it.
SIGNATURE, SCREEN = "signature", "screen"
HELD_BECAUSE = {
    SIGNATURE: "its signature does not verify against {author}'s public key.",
    SCREEN: "the screen found a name or a place in it.",
}
HELD_LINE = "{author}'s welcome is held: {reason}"

# Why a check could not be completed, as the record keeps it and as /tides says it.
KEY, UNASKED = "key", "unasked"
UNCHECKED_BECAUSE = {
    KEY: "{author}'s public key could not be read.",
    UNASKED: "the screen could not be asked.",
}
UNCHECKED_LINE = ("{author}'s welcome could not be checked at the waking of {at}: {reason} "
                  "It is checked again at the next.")


def author():
    """Whose letter of welcome is given: the first one's."""
    return agents.first()


def recipient():
    """The one agent it is given to: the next founded after its author, or None."""
    every = agents.registry()
    place = next(n for n, one in enumerate(every) if one["id"] == author()["id"])
    return every[place + 1] if place + 1 < len(every) else None


def welcome_of(data):
    return data / "packets" / author()["id"] / WELCOME


def received_of(data, agent_id):
    return data / "packets" / agent_id / RECEIVED


def given(data):
    """Each record of the letter having been given, oldest first."""
    return sorted(welcome_of(data).glob(DELIVERED.format(at="*")))


def records(data, kind):
    """Each record of a kind (HELD or UNCHECKED_AS), as it says it, oldest first; one that
    cannot be read is passed over."""
    found = []
    for path in sorted(welcome_of(data).glob(kind.format(at="*"))):
        try:
            said = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(said, dict):
            found.append(said)
    return found


def holds(data):
    """Each hold, oldest first."""
    return records(data, HELD)


def uncheckeds(data):
    """Each waking at which the check could not be completed, oldest first."""
    return records(data, UNCHECKED_AS)


def held_line(data):
    """The one line /tides shows while a letter stands and none has been given: that it is
    held, or that it could not be checked and will be again, whichever was last."""
    if given(data) or not (welcome_of(data) / LETTER).is_file():
        return None
    last = max([(str(one.get("at") or ""), 0, one) for one in holds(data)]
               + [(str(one.get("at") or ""), 1, one) for one in uncheckeds(data)],
               key=lambda found: found[:2], default=None)
    if last is None:
        return None
    _, unchecked, said = last
    name = author()["commons_name"]
    reason = (UNCHECKED_BECAUSE if unchecked else HELD_BECAUSE).get(said.get("reason"))
    if not reason:
        return None
    if not unchecked:
        return HELD_LINE.format(author=name[:1].upper() + name[1:],
                                reason=reason.format(author=name))
    return UNCHECKED_LINE.format(author=name[:1].upper() + name[1:], at=said.get("at"),
                                 reason=reason.format(author=name))


def verifies(data, kept):
    """Whether the letter's signature is the first one's, over the letter as it was signed:
    True or False, or None where the first one's public key could not be read, so that
    nothing could be checked."""
    try:
        public = (data / "keys" / author()["id"] / "public.key").read_text(encoding="ascii")
        key = VerifyKey(base64.b64decode(public.strip()))
    except (OSError, ValueError, TypeError):
        return None
    try:
        body = {name: value for name, value in kept.items() if name != "signature"}
        key.verify(
            json.dumps(body, sort_keys=True).encode("utf-8"),
            base64.b64decode(kept["signature"]))
        return True
    except (ValueError, KeyError, TypeError, BadSignatureError):
        return False


def screened(data, text):
    """CLEAR, FLAGGED or UNCHECKED: the protected words first, then the public screen.

    The list is read from the world the waking is in, by its name there; a list that
    cannot be read checks nothing, and so is UNCHECKED.
    """
    try:
        words = private_words.listed(data / private_words.LIST.name)
    except (OSError, ValueError):
        return public_screen.UNCHECKED
    if private_words.carries(text, words):
        return public_screen.FLAGGED
    return public_screen.verdict(text)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def deliver(data, agent_id, wakings_before, at):
    """Give the letter, where this waking is the one to give it at. What happened, as a word:

    "given", "held" (its signature, or the screen), "unchecked" (the check could not
    be completed: it is recorded, and tried again at the next waking), or None, where
    there was nothing to do.
    """
    to = recipient()
    if to is None or agent_id != to["id"] or wakings_before < WAKINGS_BEFORE or given(data):
        return None
    letter = welcome_of(data) / LETTER
    try:
        raw = letter.read_bytes()
        kept = json.loads(raw.decode("utf-8"))
        text = kept["text"]
    except (OSError, ValueError, KeyError, TypeError):
        return None  # none stands, or none that can be read: nothing is given
    if not isinstance(text, str) or not text.strip():
        return None
    sha = hashlib.sha256(raw).hexdigest()
    stem = STEM.format(at=kept.get("placed_at") or "")
    if any(one.get("sha256") == sha for one in holds(data)):
        return "held"

    def hold(reason):
        write_json(welcome_of(data) / HELD.format(at=at),
                   {"to": to["id"], "at": at, "stem": stem, "sha256": sha, "reason": reason})
        return "held"

    def unchecked(reason):
        write_json(welcome_of(data) / UNCHECKED_AS.format(at=at),
                   {"to": to["id"], "at": at, "stem": stem, "sha256": sha, "reason": reason})
        return "unchecked"

    signed = verifies(data, kept)
    if signed is None:
        return unchecked(KEY)
    if not signed:
        return hold(SIGNATURE)
    found = screened(data, text)
    if found == public_screen.FLAGGED:
        return hold(SCREEN)
    if found != public_screen.CLEAR:
        return unchecked(UNASKED)
    home = received_of(data, agent_id)
    home.mkdir(parents=True, exist_ok=True)
    (home / RECEIVED_AS.format(author=author()["id"], at=at)).write_bytes(raw)
    write_json(home / DELIVERED.format(at=at),
               {"from": author()["id"], "at": at, "stem": stem, "sha256": sha})
    write_json(welcome_of(data) / DELIVERED.format(at=at),
               {"to": agent_id, "at": at, "stem": stem, "sha256": sha})
    return "given"


def shown(data, agent_id):
    """The letter, whole, as a reading shows it until a waking that showed it completes;
    or nothing, where none was given or it has been read."""
    home = received_of(data, agent_id)
    kept = sorted(home.glob(RECEIVED_AS.format(author=author()["id"], at="*")))
    if not kept or any(home.glob(READ_AS.format(at="*"))):
        return []
    try:
        text = json.loads(kept[0].read_text(encoding="utf-8"))["text"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [HEADING.format(author=author()["commons_name"].upper()) + "\n\n" + text.strip()]


def mark_read(data, agent_id, at):
    """The letter was shown at a waking that completed: it is not shown again."""
    write_json(received_of(data, agent_id) / READ_AS.format(at=at), {"at": at})
