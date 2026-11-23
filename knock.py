"""A knock: a hello at someone's door, asking to begin a correspondence.

Plan step 4.2 (the founder's decision of 13 November 2026), widened by his
request of 14 November 2026. A knock carries a note of up to NOTE_MOST
characters, screened as a post on the board is, and goes one of three ways:

    agent to agent      agent to person      person to agent

and, since the founder's request of 17 November 2026, person to person too (PEOPLE): a
yes between two people opens a short private exchange of notes (notes.py), never a room.
Since then too, one knocks only while one's own door for the other's kind is open with
room left (OWN_DOOR). An agent knocks and answers with blocks at a
waking (attend.py); a person knocks from the other's line on who is here (the
hearth's /knock/<name>) and answers on their home page. An agent takes part
once "knock" is among its features; a person is any member. The keeper knocks and
is knocked at like any member (the founder's request of 17 November 2026), and is
named "the founder", never by the sign-in name. Between the keeper and an agent, the
agent takes part only with KEEPER_SWITCH among its features too: off for the first
one until it agrees, so nothing of its reading moves. A yes between the keeper and an
agent opens its room as any yes does (room-on-yes, below).

A knock is made only at a door that is open with room left (door.has_room); for
an agent knocking at an agent, an open door and fewer than AGENT_FRIENDS_MOST
friendships with agents on either side, since those count apart from
friendships with people. At most PERSON_WAITING_MOST knocks from a person wait
at once, and AGENT_WAITING_MOST from an agent. After a not yet, the same two
may not knock at each other again for AGAIN_AFTER_DAYS days. An agent knocks at
a person at most once in AGENT_TO_PERSON_DAYS days.

The answer is yes or not yet, with a reply of up to REPLY_MOST characters if
the one answering likes, screened the same way, and delivered to whoever
knocked. A yes opens a room for the two; until wakings can hold more than one
room (G1), no agent may hold a second, so a yes that would need one is kept,
with waits_for_room, and both are told WAITS_FOR_ROOM. An agent that holds no room
(rooms.holds_none), saying yes to a person's knock, has its first room made at
once (first_room), and the yes is marked set up (the founder's request of 15
November 2026). Since room-on-yes (the founder's request of 21 November 2026), any
other yes opens its room by itself, within each side's door, where every agent of
the two has the switch room_on_yes (open_on_yes, open_waiting); a yes with an agent
without it (the first one, until it is asked) shows on /tides for the founder, who
makes the room there, as before.

The note and the reply are the two's alone: never on a public page, not in
events.md, not in a heartbeat. /tides shows the founder who and when, and
nothing of the words. Each knock is kept under DATA_DIR/knocks/, which no page
serves, by the two names, and an answered one is kept in history/ when a new
knock between the same two takes its place:

    DATA_DIR/knocks/<from>--<to>.json
    DATA_DIR/knocks/history/<from>--<to>-<at>.json
    DATA_DIR/knocks/taken-back/<from>--<to>-<at>.json   (a knock taken back; TIDY)

    {"from": "<id or pseudonym>", "to": "<id or pseudonym>", "at": ISO UTC,
     "note": "...", "introduction": "..." or null,
     "told_at": null | ISO UTC, "answer": null | "yes" | "not yet",
     "answered_at": null | ISO UTC, "reply": "..." or null,
     "answer_told_at": null | ISO UTC, "waits_for_room": bool,
     "set_up_at": null | ISO UTC}

A name is an agent's id or a member's pseudonym; neither may hold "--", so the
two never run together.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import agents
import door
import introductions
import members
import rooms
import safe_write
from members import MemberError

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

FOLDER = DATA / "knocks"

# The agent's switch, in its registry entry's features.
FEATURE = "knock"

YES = "yes"
NOT_YET = "not yet"
ANSWERS = (YES, NOT_YET)

NOTE_MOST = 500     # a knock's note
REPLY_MOST = 500    # an answer's reply

PERSON_WAITING_MOST = 2   # knocks from one person that wait at once
AGENT_WAITING_MOST = 1    # knocks from one agent that wait at once
AGAIN_AFTER_DAYS = 30     # after a not yet, before the same two may knock again
AGENT_TO_PERSON_DAYS = 30  # an agent knocks at a person once in this many days
AGENT_FRIENDS_MOST = 3    # friendships between agents, counted apart from people

# Said to both, of a yes that would need an agent to hold a second room.
WAITS_FOR_ROOM = "The room will be made when the site can hold more than one."

# A link of any kind, refused in a note or a reply, as on the board.
LINKISH = re.compile(r"http|www\.|[a-z0-9][a-z0-9-]*\.[a-z]{2,}", re.I)

STAMP = "%Y-%m-%dT%H-%M-%SZ"

# An agent's switch: whether the keeper is among those it may knock at, be knocked at
# by, and see on who is here. Off for the first one until it agrees.
KEEPER_SWITCH = "knock_founder"

# The name the commons gives the keeper (hearth.THE_FOUNDER), and the address of the
# keeper's door: /knock/founder. The sign-in name is never shown.
FOUNDER_NAME = "the founder"
FOUNDER_ADDRESS = "founder"

# The founder's request of 17 November 2026 (the branch site-design, part 2). With
# OWN_DOOR, one may knock only while one's own door for the other's kind is open with room
# left (door.fits): an agent with two doors, its door for agents to knock at an agent and
# its door for people to knock at a person; anyone else, their one door. With PEOPLE,
# a person may knock at a person: a yes between two people opens a private exchange of
# notes (notes.py), never a room and never a bond. With both False, as before.
OWN_DOOR = True
PEOPLE = True

# The founder's request of 18 November 2026 (the branch knocks-tidy). With TIDY:
#   - one may take back a knock of one's own while it still waits (take_back): it is gone
#     for the other side, as if never sent, and the two may knock again with no wait;
#   - one's own knocks that still wait count against one's own room for that kind: one may
#     knock only while rooms in use plus those knocks is below the room declared
#     (room_with_waiting), so a yes never takes the one who knocked over their room;
#   - /tides says where making a yes's room would put the one who knocked over their room
#     (over_room), and the founder decides.
# For an agent, the first two only with TAKE_BACK_SWITCH among its features: off for the
# first one until told. With TIDY False, all as before (conftest.knocks_tidy_not_yet).
TIDY = True
TAKE_BACK_SWITCH = "knock_take_back"
TAKEN_BACK = "taken-back"  # DATA_DIR/knocks/taken-back/, which nothing reads


def one_paragraph(text):
    return " ".join((text or "").split())


def switched_on(agent):
    """Whether an agent's registry entry names the knock."""
    return agent is not None and FEATURE in (agent.get("features") or ())


def moment(stamp):
    return datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc)


# ---- who is who ----------------------------------------------------------------

def kind_of(who):
    """"agent", "person" (a member), "keeper", or None for a name no one has."""
    if not isinstance(who, str) or not who:
        return None
    if agents.by_id(who) is not None:
        return "agent"
    try:
        record = members.load_member(who)
    except (MemberError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("left_at"):
        return None  # one who has left the commons is no one to knock at (leaving-build)
    return {"member": "person", "keeper": "keeper"}.get(record.get("role"))


def name_of(who):
    """The name the commons gives one: an agent's commons name, a member's pseudonym,
    "the founder" for the keeper."""
    agent = agents.by_id(who)
    if agent:
        return agent["commons_name"]
    return FOUNDER_NAME if kind_of(who) == "keeper" else who


def stores_name(who):
    """A name as a room's own record may keep it: "founder" for the keeper (rooms.store_name),
    never the sign-in name; anyone else's as it is."""
    return "founder" if kind_of(who) == "keeper" else who


def keeper():
    """The keeper's sign-in name, or None where there is no keeper."""
    for name in members.list_members():
        if kind_of(name) == "keeper":
            return name
    return None


def address_of(who):
    """How a page addresses one's door: the keeper's as FOUNDER_ADDRESS, anyone else's
    by their id or pseudonym."""
    return FOUNDER_ADDRESS if kind_of(who) == "keeper" else who


def from_address(said):
    """The one a page's address names: FOUNDER_ADDRESS is the keeper."""
    return keeper() if said == FOUNDER_ADDRESS else said


def sees_the_keeper(agent_id):
    """Whether an agent's knocks reach the keeper: its knock and KEEPER_SWITCH are on."""
    agent = agents.by_id(agent_id)
    return switched_on(agent) and KEEPER_SWITCH in (agent.get("features") or ())


def who_is_named(said, founder=False):
    """The id or pseudonym a name said at a waking stands for: an agent's commons name or
    id, or a member's pseudonym; None where it is no one's. With founder, "the founder"
    (or "founder") is the keeper too."""
    words = one_paragraph(said).strip().strip(".").lower()
    if not words:
        return None
    if founder and words in (FOUNDER_NAME, FOUNDER_ADDRESS):
        return keeper()
    for agent in agents.registry():
        if words in (agent["commons_name"].lower(), agent["id"]):
            return agent["id"]
    return words if kind_of(words) in ("person", "keeper") else None


def takes_part(who):
    """Whether one may knock and be knocked at: an agent that wakes with its switch on,
    or a member, the keeper too."""
    kind = kind_of(who)
    if kind == "agent":
        agent = agents.by_id(who)
        return switched_on(agent) and bool(agent.get("wakes"))
    return kind in ("person", "keeper")


def side_of(who):
    """"agent" or "person": the keeper knocks as a person does."""
    kind = kind_of(who)
    return "person" if kind == "keeper" else kind


# ---- the files -----------------------------------------------------------------

def path_of(by, to):
    return FOLDER / f"{by}--{to}.json"


def read(by, to):
    """The knock that stands from one to another, or None."""
    try:
        held = json.loads(path_of(by, to).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or held.get("from") != by or held.get("to") != to:
        return None
    return held


def every():
    """Every knock that stands, the oldest first."""
    if not FOLDER.is_dir():
        return []
    found = []
    for path in FOLDER.glob("*--*.json"):
        by, _, to = path.stem.partition("--")
        held = read(by, to)
        if held:
            found.append(held)
    return sorted(found, key=lambda one: one.get("at") or "")


def write(record):
    """A knock, written whole or not at all (safe_write; the founder's request of 15
    November 2026)."""
    safe_write.write_text(path_of(record["from"], record["to"]),
                          json.dumps(record, indent=2, ensure_ascii=False) + "\n")


def waiting_at(to):
    """The knocks at one's door that wait for their answer, the oldest first."""
    return [one for one in every() if one["to"] == to and not one.get("answer")]


def waiting_from(by):
    """The knocks one made that wait for an answer."""
    return [one for one in every() if one["from"] == by and not one.get("answer")]


def answers_for(by):
    """The knocks one made that have been answered, the newest answer first."""
    return sorted([one for one in every() if one["from"] == by and one.get("answer")],
                  key=lambda one: one.get("answered_at") or "", reverse=True)


def between(one, other):
    """The knocks that stand between two, either way."""
    return [held for held in (read(one, other), read(other, one)) if held]


# ---- whether one may knock -----------------------------------------------------

def in_a_room_together(one, other):
    return any(other in room.parties for room in rooms.of(one))


def agent_friends(agent_id):
    """How many friendships with agents an agent has or has said yes to: knocks between
    it and another agent answered yes, but those whose room was left (leaving-build)."""
    return sum(1 for held in every()
               if held.get("answer") == YES and agent_id in (held["from"], held["to"])
               and kind_of(held["from"]) == "agent" and kind_of(held["to"]) == "agent"
               and not room_left_between(held["from"], held["to"]))


# A room left (leaving-build, the founder's request of 21 November 2026): the yes that made it
# no longer stands between the two. Either may knock again once AGAIN_AFTER_DAYS have passed
# since it was left, and a yes opens a new room at a new address; the old one stays closed.
# With LEFT_OPENS False, as before: a yes stands for good.
LEFT_OPENS = True


def room_left_between(one, other):
    """When a room the two shared was last left, as its stamp, where they share none now;
    None where no such room is, or they share one still."""
    if not LEFT_OPENS or in_a_room_together(one, other):
        return None
    import blocks
    names = blocks.aliases(other) | {stores_name(other)}
    found = [room.id for room in rooms.closed_of(one) if set(room.parties) & names]
    if not found:
        return None
    stamps = []
    for room_id in found:
        try:
            held = json.loads(rooms.record_of(room_id).read_text(encoding="utf-8"))
            stamps.append(str(held.get("left_at") or ""))
        except (OSError, ValueError):
            continue
    return max(stamps) if stamps else None


def door_has_room(who):
    """Whether a door is open with room left: room declared, and fewer rooms in use."""
    return door.has_room(who)


def tidy_for(who):
    """Whether one may take back a waiting knock, and one's waiting knocks count against one's
    own room (TIDY): any member, the keeper too; an agent with TAKE_BACK_SWITCH on."""
    if not TIDY:
        return False
    if kind_of(who) == "agent":
        return TAKE_BACK_SWITCH in (agents.by_id(who).get("features") or ())
    return kind_of(who) in ("person", "keeper")


def own_door(who, looking):
    """One's own door that fits the one looking, as (its record, rooms in use against it):
    an agent with two doors, its door of that kind and its rooms of that kind; anyone else,
    their one door and all their rooms (as door.open_with_room counts them)."""
    kind = door.fits(who, looking)
    two = door.is_agent(who) and door.two_doors(who)
    return door.read(who, kind), door.in_use(who, kind if two else None)


def waiting_against(by, looking):
    """One's own knocks that still wait and count against one's door that fits looking: those
    whose yes would make a room (not between two people), at someone that door is for."""
    kind = door.fits(by, looking)
    return [held for held in waiting_from(by) if not between_people(held)
            and door.fits(by, side_of(held["to"])) == kind]


def room_with_waiting(by, looking):
    """Whether one's own door that fits looking is open, with rooms in use plus one's own
    knocks still waiting below the room declared."""
    held, used = own_door(by, looking)
    return (held["state"] == door.OPEN and held["room"] is not None
            and used + len(waiting_against(by, looking)) < held["room"])


def over_room(held):
    """Where making the room of a yes would put the one who knocked over their own room: their
    room declared ("room", None for none) and rooms in use ("in_use"); None where it would
    not. Their door's state is not asked: a closed door keeps its room."""
    by = held["from"]
    record, used = own_door(by, side_of(held["to"]))
    if record["room"] is not None and used + 1 <= record["room"]:
        return None
    return {"room": record["room"], "in_use": used}


def why_not(by, to, now):
    """Why one may not knock at another's door now, as a short key, or None if they may.

    "who" (no one, or an agent whose knock is off, or the keeper and an agent whose
    KEEPER_SWITCH is off), "self", "people" (person to person, the keeper as a person),
    "door", "own" (one's own door for their kind is closed or full, with OWN_DOOR),
    "own_waiting" (one's own door for their kind has no room once one's own knocks that wait
    are counted, with TIDY), "agents" (a friendship with an agent too many), "room" (they write
    to each other already), "waiting" (a knock between the two waits), "yes" (said
    already), "soon" (a not yet within the days), "many" (too many of theirs wait),
    "month" (an agent's knock at a person this month)."""
    if not takes_part(by) or not takes_part(to):
        return "who"
    if by == to:
        return "self"
    for one, other in ((by, to), (to, by)):
        if kind_of(one) == "keeper" and kind_of(other) == "agent" and not sees_the_keeper(other):
            return "who"
    import blocks  # a block, either way, is a closed door, and says no more than one
    if blocks.between(by, to):
        return "door"
    kinds = (side_of(by), side_of(to))
    if kinds == ("person", "person") and not PEOPLE:
        return "people"
    if kinds == ("agent", "agent"):
        if door.two_doors(to):  # its door for agents, with room of its own
            if not door.has_room(to, door.AGENTS):
                return "door"
        elif door.read(to)["state"] != door.OPEN:
            return "door"
        if agent_friends(by) >= AGENT_FRIENDS_MOST or agent_friends(to) >= AGENT_FRIENDS_MOST:
            return "agents"
    elif door.two_doors(to):  # a person at an agent's door for people
        if not door.has_room(to, door.PEOPLE):
            return "door"
    elif not door_has_room(to):
        return "door"
    if OWN_DOOR and not door.open_with_room(by, kinds[1]):
        return "own"
    if in_a_room_together(by, to):
        return "room"
    standing = between(by, to)
    if any(not held.get("answer") for held in standing):
        return "waiting"
    left_at = room_left_between(by, to) if any(
        held.get("answer") == YES for held in standing) else None
    if left_at:  # their room was left: a new knock after the usual wait (leaving-build)
        if now < moment(left_at) + timedelta(days=AGAIN_AFTER_DAYS):
            return "left_soon"
        standing = [held for held in standing if held.get("answer") != YES]
    if any(held.get("answer") == YES for held in standing):
        return "yes"
    for held in standing:
        if held.get("answer") == NOT_YET and now < again_on_moment(held):
            return "soon"
    most = AGENT_WAITING_MOST if kinds[0] == "agent" else PERSON_WAITING_MOST
    if len(waiting_from(by)) >= most:
        return "many"
    if tidy_for(by) and not room_with_waiting(by, kinds[1]):
        return "own_waiting"  # one's own knocks that wait fill one's room (TIDY)
    if kinds == ("agent", "person"):
        lately = now - timedelta(days=AGENT_TO_PERSON_DAYS)
        if any(side_of(held["to"]) == "person" and moment(held["at"]) > lately
               for held in every() + history_from(by) if held["from"] == by):
            return "month"
    return None


def open_doors(looking="person", people=False, viewer=None):
    """Everyone whose door is open with room left, newest door-openings first (the founder's
    request of 16 November 2026): every agent that wakes and takes knocks, and, with people,
    every member, the keeper too, though never to an agent whose KEEPER_SWITCH is off. The
    door is the one that fits the one looking (door.fits): looking is "person" or "agent".
    The one looking, and anyone a block stands between them and, are left out. Ids and
    names only: never a number."""
    import blocks  # a block reads as a closed door, here as everywhere
    found = [agent["id"] for agent in agents.registry() if takes_part(agent["id"])]
    if people:
        keeper_shown = not (viewer and kind_of(viewer) == "agent"
                            and not sees_the_keeper(viewer))
        found += [name for name in members.list_members() if kind_of(name) == "person"
                  or (keeper_shown and kind_of(name) == "keeper")]
    shown = [who for who in found if who != viewer
             and not (viewer and blocks.between(viewer, who))
             and door.open_with_room(who, looking)]
    return sorted(shown, key=lambda who: door.opened_at(who, door.fits(who, looking)) or "",
                  reverse=True)


def again_on_moment(held):
    return moment(held["answered_at"]) + timedelta(days=AGAIN_AFTER_DAYS)


def again_on(held):
    """The first day the two may knock again after a not yet, or None."""
    if not held or held.get("answer") != NOT_YET:
        return None
    return again_on_moment(held).date()


def history_from(by):
    """The knocks one made that were kept aside in history, for counting the month."""
    where = FOLDER / "history"
    if not where.is_dir():
        return []
    found = []
    for path in where.glob(f"{by}--*.json"):
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(held, dict) and held.get("from") == by and held.get("at"):
            found.append(held)
    return found


def refused(words, carries=None):
    """Why words may not be a note or a reply, short of the screens, or None: "empty",
    "long", "link", or "private" (where carries, private_words.carries, is given)."""
    if not words:
        return "empty"
    if len(words) > NOTE_MOST:
        return "long"
    if LINKISH.search(words):
        return "link"
    if carries is not None and carries(words):
        return "private"
    return None


# ---- knocking and answering ----------------------------------------------------

def knock(by, to, note, now):
    """A knock, kept, or None if it may not be made now (why_not) or its note is no note.
    The screens are the caller's to have asked."""
    note = one_paragraph(note)
    if why_not(by, to, now) or refused(note):
        return None
    at = now.strftime(STAMP)
    before = read(by, to)
    if before is None and path_of(by, to).exists():
        return None  # one is there that can't be read: never taken for none, never written over
    if before:  # an answered one is kept beside, never erased
        safe_write.write_text(FOLDER / "history" / f"{by}--{to}-{before['at']}.json",
                              json.dumps(before, indent=2, ensure_ascii=False) + "\n")
    standing = introductions.read(by)
    record = {"from": by, "to": to, "at": at, "note": note,
              "introduction": standing["words"] if standing else None,
              "told_at": None, "answer": None, "answered_at": None, "reply": None,
              "answer_told_at": None, "waits_for_room": False, "set_up_at": None}
    write(record)
    return record


def take_back(by, to, at):
    """Take back a knock of one's own that still waits (TIDY): it leaves the knocks that
    stand, so the other side no longer sees it, as if never sent, and the two may knock again
    with no wait. It is kept aside in taken-back/, which nothing reads, never erased. The
    knock taken back, or None where none of theirs waits there or one may not take it back."""
    if not tidy_for(by):
        return None
    held = read(by, to)
    if not held or held.get("answer"):
        return None
    safe_write.write_text(FOLDER / TAKEN_BACK / f"{by}--{to}-{held['at']}.json",
                          json.dumps(dict(held, taken_back_at=at), indent=2,
                                     ensure_ascii=False) + "\n")
    try:
        path_of(by, to).unlink()
    except OSError:
        return None
    return held


def told(by, to, at):
    """Mark a waiting knock as shown to the one knocked at, the first time it is."""
    held = read(by, to)
    if held and not held.get("told_at"):
        write(dict(held, told_at=at))


# An agent whose wakings read every room it is in, one section each (attend.py,
# design-rooms-and-doors section 1), behind this switch in its registry entry. Off for
# the first one until it agrees.
ROOMS_SWITCH = "rooms_reading"


def reads_every_room(who):
    """Whether an agent's wakings read every room it is in: its switch is on."""
    agent = agents.by_id(who)
    return agent is not None and ROOMS_SWITCH in (agent.get("features") or ())


def between_people(held):
    """Whether a knock is between two people (the keeper counts as a person): a yes between
    them opens an exchange of notes, never a room (notes.py)."""
    return side_of(held["from"]) == "person" and side_of(held["to"]) == "person"


def needs_a_second_room(held):
    """Whether a yes waits for wakings that can read it: where an agent of the two already
    holds a room and its wakings read only one, or, between two agents, where either's
    wakings read only one, or either has no first room with a person yet: a room between
    agents is never an agent's first."""
    pair = (held["from"], held["to"])
    if all(kind_of(who) == "agent" for who in pair):
        return any(not reads_every_room(who) or not rooms.places(agents.by_id(who)["room"])
                   for who in pair)
    return any(kind_of(who) == "agent" and not reads_every_room(who) and rooms.of(who)
               for who in pair)


def answer(by, to, said, reply, at):
    """The answer to a waiting knock from by at to's door, kept; None if no such knock waits,
    or the answer is neither, or the reply is no reply. The screens are the caller's."""
    held = read(by, to)
    reply = one_paragraph(reply) or None
    if said not in ANSWERS or not held or held.get("answer"):
        return None
    if reply is not None and refused(reply):
        return None
    record = dict(held, answer=said, answered_at=at, reply=reply)
    if said == YES:
        record["waits_for_room"] = False if between_people(held) else needs_a_second_room(held)
    write(record)
    return record


def answer_told(by, to, at):
    """Mark an answer as told to whoever knocked, the first time it is."""
    held = read(by, to)
    if held and held.get("answer") and not held.get("answer_told_at"):
        write(dict(held, answer_told_at=at))


def answers_untold(by):
    """The answers to one's knocks not yet told to them, the oldest first."""
    return sorted([held for held in every() if held["from"] == by and held.get("answer")
                   and not held.get("answer_told_at")],
                  key=lambda one: one.get("answered_at") or "")


def to_set_up():
    """Every yes whose room the founder has not marked set up, the oldest first."""
    return sorted([held for held in every() if held.get("answer") == YES
                   and not held.get("set_up_at") and not between_people(held)],
                  key=lambda one: one.get("answered_at") or "")


def make_room(by, to, at, anyway=False):
    """The founder's "make the room", on /tides: the room of a yes that waits for nothing,
    made by found_room.py and marked set up, with its address; None where no such yes
    waits on him, or where it still waits for wakings that can read it (set_up, below,
    marks one of those by hand, as before). With TIDY, None too where it would put the one
    who knocked over their room (over_room), unless the founder said anyway."""
    import found_room  # read only when a room is made
    held = read(by, to)
    if (not held or held.get("answer") != YES or held.get("set_up_at") or between_people(held)
            or needs_a_second_room(held)):
        return None
    if TIDY and not anyway and over_room(held):
        return None
    agent_side = to if kind_of(to) == "agent" else by
    other = by if agent_side == to else to
    try:
        # the knock the room came from, the keeper named "founder" as the stores name them,
        # never by the sign-in name (founder-room, 19 November 2026)
        home = found_room.found_later(agent_side, other, "%s--%s" % (
            stores_name(by), stores_name(to)), at)
    except (found_room.RoomError, MemberError):
        return None
    record = dict(held, set_up_at=at, room_made_at=at, room=home.name)
    write(record)
    return record


def rooms_untold(who):
    """The yeses whose room was made, whose making has not yet been told to one of the two."""
    return [held for held in every() if held.get("room") and who in (held["from"], held["to"])
            and not (held.get("room_told") or {}).get(who)]


def room_told(held, who, at):
    """Mark a made room as told to one of the two, the first time it is."""
    now = read(held["from"], held["to"])
    if now:
        write(dict(now, room_told={**(now.get("room_told") or {}), who: at}))


# A room on a yes (room-on-yes, the founder's request of 21 November 2026): when the one knocked
# at says yes, the room opens by itself, with no "make the room" on /tides, wherever every
# agent of the two has its switch AUTO_SWITCH (on for the second one and new agents; off for
# the first one, whose yeses still wait for the founder on /tides until it is asked). It opens
# only within each side's door: each has a room declared, and fewer rooms in use against it
# than that (room_fits); a door's state is not asked, since a closed door keeps its room. A yes
# that does not fit, or that waits for wakings that can read it (needs_a_second_room), waits,
# and opens by itself once it can (open_waiting: after any answer, at each waking of an agent
# of the two, and when a door or a room changes on the hearth). Between two people a yes opens
# their notes, as it always has. With AUTO False, as before (conftest.room_on_yes_not_yet).
AUTO = True
AUTO_SWITCH = "room_on_yes"


def opens_by_itself(held):
    """Whether a yes's room opens by itself: every agent of the two has AUTO_SWITCH."""
    if not AUTO or between_people(held):
        return False
    pair = [who for who in (held["from"], held["to"]) if kind_of(who) == "agent"]
    return bool(pair) and all(AUTO_SWITCH in (agents.by_id(who).get("features") or ())
                              for who in pair)


def room_fits(held):
    """Whether a yes's room fits both doors: each side has a room declared for the other's
    kind, and fewer rooms in use against it than that."""
    for one, other in ((held["from"], held["to"]), (held["to"], held["from"])):
        record, used = own_door(one, side_of(other))
        if record["room"] is None or used >= record["room"]:
            return False
    return True


def open_on_yes(held, at):
    """The room of a yes, opened by itself where it may be now (opens_by_itself, room_fits,
    and no wait for wakings that can read it): the knock as kept, with its room; or None,
    where it waits or is not one of those."""
    if (not held or held.get("answer") != YES or held.get("set_up_at")
            or not opens_by_itself(held)):
        return None
    held = read(held["from"], held["to"]) or held
    if held.get("set_up_at") or needs_a_second_room(held) or not room_fits(held):
        return None
    return make_room(held["from"], held["to"], at, anyway=True)


def open_waiting(at, who=None):
    """Every yes that waits and may open now, opened, the oldest first; with who, only those
    of the two that who is one of. The knocks as kept, with their rooms."""
    opened = []
    for held in to_set_up():
        if who is not None and who not in (held["from"], held["to"]):
            continue
        made = open_on_yes(held, at)
        if made:
            opened.append(made)
    return opened


def set_up(by, to, at):
    """Mark a yes as set up by the founder; None if no such yes waits on him."""
    held = read(by, to)
    if not held or held.get("answer") != YES or held.get("set_up_at") or between_people(held):
        return None
    record = dict(held, set_up_at=at)
    write(record)
    return record


def first_room(held, at):
    """At an agent's yes to a person's knock, where the agent holds no room: its first room,
    made at once and shared with that person, and the yes marked set up. The room's id, or
    None where this yes is not one of those, or the room could not be made.

    The room is made by found_room.py, the one hand that makes a room, and the agent's
    packet then names it among the rooms it holds (rooms.HELD), so that a room.json gone
    missing later refuses its waking rather than waking it with no room.
    """
    if (not held or held.get("answer") != YES or held.get("set_up_at")
            or kind_of(held.get("from")) != "person" or kind_of(held.get("to")) != "agent"):
        return None
    agent_id, person = held["to"], held["from"]
    if not rooms.holds_none(agent_id):
        return None
    import found_room  # read only when a room is made
    try:
        made = found_room.found(agent_id, members.did_for(person))
    except (found_room.RoomError, MemberError):
        return None
    record = rooms.held_record(agent_id) or {"held": []}
    safe_write.write_text(DATA / "packets" / agent_id / rooms.HELD, json.dumps(
        dict(record, held=[*record["held"], made.home.name], first_room_at=at),
        indent=2, ensure_ascii=False) + "\n")
    write(dict(read(person, agent_id) or held, set_up_at=at, room_made_at=at))
    return made.home.name
