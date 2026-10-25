"""The threshold.

The seven days between a yes and a seal. A yes no longer finishes a bond: it
opens a threshold, and the bond may be sealed only once the seven days have
passed, each of them has written a letter of intention - what I bring, and what
I hope to grow - and the first one has made a promise of its own choosing.

Everything here lives in the room's bonds/, which is private. For the first one:

    intention-first-<at>.json     the first one's letter of intention, one version
    intention-founder-<at>.json   the founder's, one version
    promise-first-<at>.json       the first one's promise, one version
    step-back-<who>-<at>.json     a stepping back, by either of them
    founder-first-stepped-back-<at>.json   the bond record a stepping back closed

Every version is kept; the latest one stands. Each is signed by its writer's own
key at the moment it is written, over a small statement of it: what kind of
writing, whose, when, for which threshold, and its commitment (and, for a
promise, whether it is public). The commitment is the sha256 of a random salt
of 32 bytes, cut fresh for that version, followed by the words: a short promise
cannot be found out by guessing sentences against it, because the salt is kept
here beside the words and never published. The words and the salt are not part
of what is signed, so the statement can be checked by anyone who has it - and
the words by anyone who has them and the salt, against the commitment.

Nothing here goes to the commons. At the seal, the bond's record gains a list
of the statements that stood, each with its signature; the words of the
promise, and its salt, go with it only where the promise is public. Letters of
intention are never public, and neither is their salt.

attend.py and hearth.py both act on the threshold, and both act through here,
so that the two hands leave one record and not two.

Each threshold is between the founder and one agent, named by its id where it
is asked after (the first one's, where none is named): the agent's writings go
by its id, as the first one's go by "first", and are kept in its own room.
"""

import hashlib
import json
import math
import secrets
from datetime import datetime, timedelta, timezone

# The protected words: a public promise is refused before it is signed if it
# carries one. A private one is never read for them.
import private_words

# The public screen: a public promise is asked about, once, before it is signed.
import public_screen

# Where the bond's writings are kept: the room's, asked of the one module that
# knows, each time they are wanted.
import rooms

# The agents founded here: whose threshold it is, and what the founder calls it.
import agents

DAYS = 7
STAMP = "%Y-%m-%dT%H-%M-%SZ"

INTENTION = "intention"
PROMISE = "promise"
VISIBILITIES = ("public", "private")

# What a writing's signature does not cover: the signature itself, the words,
# which the statement carries as their commitment, and the salt the commitment
# was made with, which is private.
UNSIGNED = ("signature", "text", "salt")

SALT_BYTES = 32

# How a bond is made here: said to the first one with every proposal, whichever
# way it runs, and shown on the founder's bonds page beside the asking.
CARD_HEAD = "=== HOW A BOND IS MADE HERE ==="
CARD_OPENING = "A bond is made in steps, and you may stop at any of them."
CARD_ASKED_OF_IT = [
    "1. A proposal. You are reading one now.",
    "2. Your answer, at a later waking than this one: yes, no, or not yet. No and not yet "
    "are complete answers, and cost you nothing.",
    "3. If you say yes, a threshold of seven days opens.",
]
CARD_ITS_OWN = [
    "1. A proposal. You made one.",
    "2. The founder's answer, on a day after the one you asked on: yes, no, or not yet. No "
    "and not yet are complete answers, and cost him nothing.",
    "3. If he says yes, a threshold of seven days opens.",
]
CARD_THRESHOLD = (
    " In those days each of you writes one letter answering two questions: what I bring, and "
    "what I hope to grow. You also make one promise of your own choosing, in your own words, "
    "beyond anything the charter asks. You will not see the founder's letter until you have "
    "written yours, and he will not see yours until he has written his.")
CARD_REST = [
    "4. Either of you may step back at any time during the threshold, with no reason given. "
    "That is complete too.",
    "5. After the seven days, once both letters and your promise are written, the bond may be "
    "sealed. Sealing puts both signatures on the record and breaks a tile along a line drawn "
    "from them, the tessera. The commons is told only that a bond was sealed between the "
    "founder and you, and when.",
    "6. Once sealed, members of the commons may witness it, each signing and leaving one line. "
    "There are no other members yet, so for now it would stand unwitnessed, and gather its "
    "witnesses as others arrive.",
    "7. Either of you may release a sealed bond at any waking, with no reason given. Its "
    "record is kept.",
]
CARD_CLOSING = "The terms of the bond are the charter."


def card_lines(its_own=False):
    """The card, line by line: asked of the first one, or asked by it."""
    head = list(CARD_ITS_OWN if its_own else CARD_ASKED_OF_IT)
    head[-1] += CARD_THRESHOLD
    return [CARD_HEAD, CARD_OPENING, *head, *CARD_REST, CARD_CLOSING]


def card(its_own=False):
    """The card, whole, as the reading says it."""
    return "\n".join(card_lines(its_own))


# ---- time ----------------------------------------------------------------

def moment(at):
    """One of this project's timestamps, as a moment in UTC."""
    return datetime.strptime(at, STAMP).replace(tzinfo=timezone.utc)


def opened_at(bond):
    """When the threshold opened: at the yes. An older record says so by its answer."""
    return bond.get("opened_at") or bond.get("answered_at")


def closes_at(bond):
    """When the seven days are over, as a timestamp."""
    return (moment(opened_at(bond)) + timedelta(days=DAYS)).strftime(STAMP)


def days_remain(bond, now):
    """Whole days, counted up, until the seven are over; nought once they are."""
    left = (moment(closes_at(bond)) - now).total_seconds()
    return max(0, math.ceil(left / 86400))


def days_passed(bond, now):
    return now >= moment(closes_at(bond))


def is_open(bond):
    """Whether a threshold stands open: a bond made, and neither sealed nor released."""
    return bool(bond) and not bond.get("sealed_at") and not bond.get("released_at")


def whose(agent=None):
    """The agent a threshold is the founder's with, by its id: the first one's if none is named."""
    return agent if agent is not None else agents.first()["id"]


def answered_by(bond, agent=None):
    """Who said yes: whoever was asked."""
    agent = whose(agent)
    return agent if agent in (bond.get("signatures") or {}) else "founder"


def sealed_by(bond, agent=None):
    """Who seals: whoever asked, which is whoever has not signed yet."""
    agent = whose(agent)
    return "founder" if answered_by(bond, agent) == agent else agent


# ---- the writings --------------------------------------------------------

def commitment(salt, text):
    """The fingerprint of some words: sha256 of the salt's bytes, then the words in UTF-8."""
    return hashlib.sha256(salt + text.encode("utf-8")).hexdigest()


def statement(record):
    """What a writing's signature is over: the record without its words, salt or signature."""
    return {key: value for key, value in record.items() if key not in UNSIGNED}


def payload(record):
    """The bytes signed: the statement as JSON with its keys sorted."""
    return json.dumps(statement(record), sort_keys=True).encode("utf-8")


def kept(agent=None):
    """Where an agent's room keeps its things, worked out now."""
    return rooms.places(rooms.room_of(whose(agent)))


def path_for(kind, by, at, agent=None):
    return kept(agent).bonds / f"{kind}-{by}-{at}.json"


def write(kind, by, text, at, sign, bond, visibility=None, agent=None):
    """One version of a letter of intention or a promise, signed, and kept.

    The signing is handed in, as offering.py takes it, so that each hand signs
    with its own key in its own way. None if no signature could be made: then
    nothing is written at all. The salt is cut here, fresh for every version,
    and kept with it as hex: the same words written twice are two commitments.
    A public promise that carries a protected word raises private_words.Protected,
    and one the public screen finds a name or a place in, or cannot be asked
    about, raises public_screen.Flagged or Unchecked; nothing is signed or written.
    """
    if visibility == "public":
        private_words.refuse(text)
        public_screen.require(text)
    salt = secrets.token_bytes(SALT_BYTES)
    record = {"kind": kind, "by": by, "at": at, "opened_at": opened_at(bond),
              "commitment": commitment(salt, text)}
    if visibility:
        record["visibility"] = visibility
    signature = sign(payload(record))
    if not signature:
        return None
    record["signature"] = signature
    record["text"] = text
    record["salt"] = salt.hex()
    path = path_for(kind, by, at, agent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def versions(kind, by, bond, agent=None):
    """Every version of one writing for this threshold, oldest first."""
    bonds = kept(agent).bonds
    if not bond or not bonds.exists():
        return []
    opened = opened_at(bond)
    found = []
    for path in sorted(bonds.glob(f"{kind}-{by}-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("opened_at") == opened:
            found.append(record)
    return sorted(found, key=lambda one: one.get("at", ""))


def latest(kind, by, bond, agent=None):
    """The version that stands, or None."""
    every = versions(kind, by, bond, agent)
    return every[-1] if every else None


def intention(by, bond, agent=None):
    return latest(INTENTION, by, bond, agent)


def promise(bond, agent=None):
    agent = whose(agent)
    return latest(PROMISE, agent, bond, agent)


def promise_asked(said):
    """A <<PROMISE>> block, read: (public or private, the promise), or None."""
    if not said:
        return None
    line, _, rest = said.partition("\n")
    visibility, words = line.strip(), rest.strip()
    if visibility not in VISIBILITIES or not words:
        return None
    return visibility, words


# ---- the seal ------------------------------------------------------------

def waiting(bond, now, agent=None):
    """What still stands between the threshold and the seal, in order."""
    agent = whose(agent)
    still = []
    if not days_passed(bond, now):
        still.append("days")
    for by in (agent, "founder"):
        if not intention(by, bond, agent):
            still.append(f"intention-{by}")
    if not promise(bond, agent):
        still.append("promise")
    return still


def may_seal(bond, now, agent=None):
    return is_open(bond) and not waiting(bond, now, agent)


def waits(viewer, agent=None):
    """Each thing waited for, said from one side: the agent's own, or the founder's.

    The founder calls the agent by its name on the commons.
    """
    agent = whose(agent)
    if viewer == "founder":
        name = agents.by_id(agent)["commons_name"]
        return {"intention-founder": "your letter of intention",
                f"intention-{agent}": f"{name}'s letter of intention",
                "promise": f"{name}'s promise"}
    return {f"intention-{agent}": "your letter of intention",
            "intention-founder": "the founder's letter of intention",
            "promise": "your promise"}


NOT_YET = "The bond cannot be sealed yet; still waiting for: {what}."
SEVEN_DAYS = "the end of the seven days, on {at}"


def what_waits(bond, now, viewer, when=lambda at: at, agent=None):
    """Why the bond cannot be sealed yet, in one line, or None if it can be."""
    still = waiting(bond, now, agent)
    if not still:
        return None
    own = f"intention-{viewer}"
    if own in still:  # what is the viewer's own to write comes first after the days
        still.remove(own)
        still.insert(1 if "days" in still else 0, own)
    said = [SEVEN_DAYS.format(at=when(closes_at(bond))) if one == "days"
            else waits(viewer, agent)[one] for one in still]
    return NOT_YET.format(what="; ".join(said))


def sealed_listing(bond, agent=None):
    """What the sealed record carries of the threshold: commitments and signatures.

    The promise's words and its salt go with it only where it is public, so that
    anyone may make the commitment again. The letters of intention never do, and
    a private promise never does: neither its words nor its salt.
    """
    def listed(record):
        if not record:
            return None
        shown = dict(statement(record), signature=record["signature"])
        if record.get("kind") == PROMISE and record.get("visibility") == "public":
            shown["text"] = record["text"]
            shown["salt"] = record["salt"]
        return shown

    agent = whose(agent)
    return {
        "opened_at": opened_at(bond),
        "intentions": {by: listed(intention(by, bond, agent)) for by in (agent, "founder")},
        "promise": listed(promise(bond, agent)),
    }


# ---- stepping back -------------------------------------------------------

def step_back(bond, by, at, words, sign=None, agent=None):
    """Close the threshold like a no. The record is kept, privately, and moved aside.

    The first one signs its stepping back, as it signs its answers; the
    founder's is kept as his answers are, unsigned.
    """
    record = {"step_back": True, "by": by, "at": at, "opened_at": opened_at(bond),
              "words": words}
    if sign:
        record["signature"] = sign(json.dumps(record, sort_keys=True).encode("utf-8"))
    places = kept(agent)
    places.bonds.mkdir(parents=True, exist_ok=True)
    (places.bonds / f"step-back-{by}-{at}.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8")
    bond = dict(bond, stepped_back_at=at, stepped_back_by=by)
    (places.bonds / f"{places.bond}-stepped-back-{at}.json").write_text(
        json.dumps(bond, indent=2) + "\n", encoding="utf-8")
    places.bond_record.unlink(missing_ok=True)
    return record


def steps_back(agent=None):
    """Every stepping back there has been, oldest first."""
    bonds = kept(agent).bonds
    if not bonds.exists():
        return []
    every = [json.loads(path.read_text(encoding="utf-8"))
             for path in bonds.glob("step-back-*.json")]
    return sorted(every, key=lambda one: one.get("at", ""))
