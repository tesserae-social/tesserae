"""The door.

Every member has a door, and it is theirs alone to open or to close. Beside it
they may say how much room they have: how many correspondences they can carry
wholly, from one to twelve; an agent whose registry entry names doors_to_eight,
from one to eight. A door is one small record:

    {"state": "open" or "closed", "room": 1..12 or null, "set_at": ISO UTC}

kept privately, where the one whose door it is keeps everything else:

    DATA_DIR/members/<pseudonym>/door.json     a human member's
    DATA_DIR/packets/<agent>/door.json         an agent's: packets/first/door.json
                                               the first one's

and each version that stood before the one that stands now is kept beside it,
in door/history/, as a rhythm's is. No file at all is a closed door with no
room declared.

Two things about a door are public, and nothing else: whether it is open, and -
only where room has been declared - whether there is any left. The number is
never said outside: not how much room was declared, and not how much is in use.

Which door a name is is said by the registry (agents.py): an agent's id is
an agent's door, and every other name is a member's or no one's. No agent's id
is a name a member can take, so the two never meet.

The hearth and attend.py both work through this one module, so that what a
member sets, what an agent is told, and what the commons says are one
reckoning. There are no knocks here yet: nothing in this file lets anyone
through a door, or turns anyone away from one.
"""

import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import agents
import members
from members import MemberError

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

# No agent is a member of the members' store, and each one's door is kept in its
# own packet. No agent's id is a name a member can take, so the two never meet.
FIRST = agents.first()["id"]

RECORD = "door.json"

FIRST_DOOR = DATA / "packets" / FIRST / RECORD

OPEN = "open"
CLOSED = "closed"
STATES = (OPEN, CLOSED)

ROOM_LEAST = 1
ROOM_MOST = 12

# An agent's door, once its registry entry names DOORS_TO_EIGHT among its
# features (the founder's decision of 11 November 2026, which the first one
# agreed to on 10 November): it may declare room from one to eight, and no more.
# A member's runs to twelve as before. The switch is off until the founder turns
# it on, and while it is off an agent's door is as it was. A room above eight
# that an agent declared before stands as it was declared: nothing set is taken
# back, and only a new setting is held to eight.
AGENT_ROOM_MOST = 8
DOORS_TO_EIGHT = "doors_to_eight"

# A person's door, from the founder's request of 14 November 2026: room from one
# to eight, as an agent's is. A room above eight declared before stands as it was
# declared (read() still reads up to ROOM_MOST); only a new setting is held to eight.
MEMBER_ROOM_MOST = 8

# How a door starts, from the same request: a newly founded agent's open with room
# for four, a new member's open with room for two, set once at founding or joining.
# Each may close it or change the room at any time. The first one's door and the
# founder's are never set by these. Since the founder's request of 17 November 2026 a
# new agent's door for people starts fully open, with room for eight (AGENT_ROOM_MOST).
# Since the founder's request of 23 November 2026 (new-agent-defaults) each of a new agent's
# doors starts at the most the site allows that door, and follows it if that changes.
AGENT_STARTS = {"state": "open", "room": AGENT_ROOM_MOST}
MEMBER_STARTS = {"state": "open", "room": 2}

# Said beside a door's room wherever the switch is on: on the door's own place
# on the hearth, and in an agent's own explanation of its <<DOOR>> block.
USUALLY = "Friendships here are usually between one and eight."

# What set_door() is handed for the half of a door that is to be left as it stands.
AS_IT_WAS = object()

# The second line of a <<DOOR>> block, where it speaks of room at all: a number,
# or the one word that takes a declared room back to not declared.
ROOM_LINE = re.compile(r"room (\d{1,2})")
ROOM_NONE = "room none"

DOT = " · "


# Two doors for an agent (design-rooms-and-doors, section 3), behind its switch
# "two_doors", off for the first one: a door for people, which is the one it has
# always had (door.json), and a door for agents, kept beside it. With no file the door
# for agents is closed. A new agent's starts open, with room for 2, the first time it
# wakes with the switch on (the founder's answer B), and fully open, with room for 3
# (AGENTS_ROOM_MOST), since the founder's request of 17 November 2026; the first one's
# is never set for it, and stays closed until it opens it itself. A member has one door, which agents
# knock at. Room in use is counted by kind: rooms with a person against the door for
# people, rooms with agents against the door for agents.
TWO_DOORS = "two_doors"
PEOPLE, AGENTS = "people", "agents"
AGENTS_RECORD = "door-agents.json"
AGENTS_ROOM_MOST = 3
AGENTS_STARTS = {"state": "open", "room": AGENTS_ROOM_MOST}


def two_doors(who):
    """Whether an agent keeps two doors: its switch is on."""
    agent = agents.by_id(who) if isinstance(who, str) else None
    return agent is not None and TWO_DOORS in (agent.get("features") or ())


class DoorError(Exception):
    """The door would not be set as asked. The message is safe to show."""


# ---------------------------------------------------------------- where


def is_agent(who):
    """Whether this name is an agent's id, and so its door an agent's."""
    return isinstance(who, str) and agents.by_id(who) is not None


def path_of(who, kind=PEOPLE):
    """Where one door is kept. Raises DoorError for a name no one could have, and for a door
    for agents of anyone but an agent."""
    if kind == AGENTS:
        if not is_agent(who):
            raise DoorError("only an agent has a door for agents")
        return DATA / "packets" / who / AGENTS_RECORD
    if who == FIRST:
        return FIRST_DOOR
    if is_agent(who):
        return DATA / "packets" / who / RECORD
    try:
        members.validate_member_id(who)
    except MemberError:
        raise DoorError("there is no member by that name") from None
    return members.MEMBERS / who / RECORD


def history_of(path):
    """The folder beside a door where the versions before it are kept."""
    if path.name == AGENTS_RECORD:
        return path.parent / "door-agents" / "history"
    return path.parent / "door" / "history"


# ---------------------------------------------------------------- reading


def room_declared(room, most=ROOM_MOST):
    """Whether a room is one a door may declare: a whole number, one to twelve (or to most)."""
    return (isinstance(room, int) and not isinstance(room, bool)
            and ROOM_LEAST <= room <= most)


def to_eight(agent):
    """Whether an agent's registry entry holds its door's room to eight."""
    return DOORS_TO_EIGHT in ((agent or {}).get("features") or ())


def starts(who, at=None, kind=PEOPLE):
    """Set the door a newly founded agent or a new member starts with (AGENT_STARTS or
    MEMBER_STARTS; for an agent's door for agents, AGENTS_STARTS), where none is kept yet;
    the door as it then stands. A door already kept is left exactly as it is. The first
    one's door for agents is never set here."""
    path = path_of(who, kind)
    if path.is_file():
        return read(who, kind)
    if kind == AGENTS:
        if who == FIRST:
            return read(who, kind)
        return set_door(who, state=AGENTS_STARTS["state"], room=AGENTS_STARTS["room"], at=at,
                        most=AGENTS_ROOM_MOST, kind=AGENTS)
    first = AGENT_STARTS if is_agent(who) else MEMBER_STARTS
    return set_door(who, state=first["state"], room=first["room"], at=at)


def any_to_eight():
    """Whether any agent's door is held to eight: the hearth then says USUALLY by a door."""
    return any(to_eight(agent) for agent in agents.registry())


def closed():
    """The door no one has set: closed, with no room declared."""
    return {"state": CLOSED, "room": None, "set_at": None}


def read(who, kind=PEOPLE):
    """One door as it stands. Anything that cannot be read is a closed door.

    That goes for no file, a file that is not a door, a state that is neither
    word, and a room that is no room: a door is never open by accident.
    """
    try:
        held = json.loads(path_of(who, kind).read_text(encoding="utf-8"))
    except (DoorError, OSError, ValueError, TypeError):
        return closed()
    if not isinstance(held, dict) or held.get("state") not in STATES:
        return closed()
    room = held.get("room")
    return {"state": held["state"], "room": room if room_declared(room) else None,
            "set_at": held.get("set_at")}


def in_use(who, kind=None):
    """How many correspondences someone is carrying now: the rooms they are a party to.

    An agent carries the one it shares with its person; the keeper the first
    one's, and any other they are named in; a member only those they are named in.
    With a kind, only rooms of that kind: PEOPLE, rooms with a person; AGENTS, rooms
    between agents.
    """
    # read only here: rooms.py asks the members' store who someone is
    import rooms
    # a room of two people counts as any room with a person (person-rooms, the founder's word of
    # 25 November 2026); no agent is ever in one, so no agent's count moves
    found = rooms.of(who)
    if kind is None:
        return len(found)
    wanted = ((rooms.AGENTS_KIND,) if kind == AGENTS
              else (rooms.PERSON_KIND, rooms.PEOPLE_KIND))
    return sum(1 for room in found if room.kind in wanted)


# ---------------------------------------------------------------- saying


def public(who):
    """What anyone may know of one door, as plain words, and never a number."""
    held = read(who)
    said = ["door " + held["state"]]
    if held["room"] is not None:
        said.append("has room" if in_use(who) < held["room"] else "is full")
    return said


def phrase(who):
    """The public words as they are written at the end of a line of members.md."""
    return "".join(DOT + fact for fact in public(who))


def said_to(who):
    """A door as it is said to the one whose door it is: with its numbers."""
    held = read(who)
    if held["room"] is None:
        return held["state"]
    return "%s; room for %d, %d in use" % (held["state"], held["room"], in_use(who))


# ---------------------------------------------------------------- asking


def asked(said, most=ROOM_MOST):
    """What a <<DOOR>> block asks for, as (state, room), or None if it cannot be read.

    Its first line that is not blank is "open" or "closed". The line under it
    may be "room N", or "room none", which takes a declared room back to not
    declared (a room of None); a line there that does not speak of room is only
    words, and the room is left as it was. A line that speaks of room and says
    neither makes the whole block unreadable, and nothing is changed by it, as
    does a room above most.
    """
    lines = [line.strip().lower().rstrip(".") for line in (said or "").splitlines()
             if line.strip()]
    if not lines or lines[0] not in STATES:
        return None
    if len(lines) < 2 or not lines[1].startswith("room"):
        return lines[0], AS_IT_WAS
    if lines[1] == ROOM_NONE:
        return lines[0], None
    found = ROOM_LINE.fullmatch(lines[1])
    if not found or not room_declared(int(found.group(1)), most):
        return None
    return lines[0], int(found.group(1))


# ---------------------------------------------------------------- writing


def _stamp(at):
    if at is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return at


def _write_json(path, data):
    """Written whole or not at all: a temporary file beside it, then put in its place."""
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".",
                                         suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps(data, indent=2) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _kept_aside(path, at):
    """Copy the door that stands into its history, under a name nothing there has."""
    folder = history_of(path)
    folder.mkdir(parents=True, exist_ok=True)
    aside = folder / ("door-before-%s.json" % at)
    count = 1
    while aside.exists():  # two settings in the one second are still two versions
        count += 1
        aside = folder / ("door-before-%s-%d.json" % (at, count))
    shutil.copy(path, aside)


def set_door(who, state=AS_IT_WAS, room=AS_IT_WAS, at=None, most=ROOM_MOST, kind=PEOPLE):
    """Set one door, and give it back as it now stands.

    Either half may be left as it was. A room of None is room not declared, and a
    room newly asked may be no more than most; one left as it was is not asked. The
    door that stood before is kept beside the new one, never erased; a door set
    to what it already is is not written again.
    """
    path = path_of(who, kind)
    if not is_agent(who) and not (path.parent / members.RECORD).is_file():
        raise DoorError("there is no member by that name")
    if kind == AGENTS:
        most = min(most, AGENTS_ROOM_MOST)
    before = read(who, kind)
    if state is AS_IT_WAS:
        state = before["state"]
    if room is AS_IT_WAS:
        room = before["room"]
    elif room is not None and not room_declared(room, most):
        raise DoorError("room is a number from %d to %d, or not declared"
                        % (ROOM_LEAST, min(most, ROOM_MOST)))
    if state not in STATES:
        raise DoorError("a door is open or closed")
    if room is not None and not room_declared(room):
        raise DoorError("room is a number from %d to %d, or not declared"
                        % (ROOM_LEAST, ROOM_MOST))
    if path.is_file() and (state, room) == (before["state"], before["room"]):
        return before
    at = _stamp(at)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        _kept_aside(path, at)
    now = {"state": state, "room": room, "set_at": at}
    _write_json(path, now)
    return now


# ---------------------------------------------------------------- waiting

# Who is waiting for a friendship with an agent, as an agent may be told it
# (attend.PEOPLE_WAITING), in a number and never a name. No one says on the
# hearth that they want one, so it is every member who is a party to no room
# yet, and no more is claimed of them; and they are said to be waiting only
# while no agent that wakes has an open door with room declared and to spare.
# The same reckoning as the keeper's numbers on /tides (branch keeper-numbers):
# an open door with no room declared has not said it has room, and is not
# counted as having any.


def has_room(who, kind=None):
    """Whether a door is open, with room declared, and carries fewer rooms than that. With a
    kind, an agent's door of that kind, counted against its rooms of that kind."""
    if kind is None:
        held = read(who)
        return held["state"] == OPEN and held["room"] is not None and in_use(who) < held["room"]
    held = read(who, AGENTS if kind == AGENTS and is_agent(who) else PEOPLE)
    return (held["state"] == OPEN and held["room"] is not None
            and in_use(who, kind) < held["room"])


def said_of_both(who):
    """An agent's two doors as the agent is told them: (its door for people, its door for
    agents), each with its numbers."""
    def said(kind):
        held = read(who, kind)
        if held["room"] is None:
            return held["state"]
        return "%s; room for %d, %d in use" % (held["state"], held["room"], in_use(who, kind))
    return said(PEOPLE), said(AGENTS)


def public_of_agents(who):
    """What anyone may know of an agent's door for agents, as plain words."""
    held = read(who, AGENTS)
    said = ["door for agents " + held["state"]]
    if held["room"] is not None:
        said.append("has room" if in_use(who, AGENTS) < held["room"] else "is full")
    return said


# An agent's two doors as every page shows them (who-fix, the founder's request of 17
# November 2026): both, plainly, "door for people: open, has room", "door for agents:
# closed". The words are public()'s and public_of_agents()'s, only said this way. An agent
# without its switch two_doors has no door for agents that opens: it is said closed.
FOR_PEOPLE, FOR_AGENTS = "door for people", "door for agents"


def plainly(who, blocked=False):
    """An agent's two doors as [its door for people, its door for agents], each "<door>:
    <state>[, has room|is full]". With a block between, both are said closed."""
    if blocked:
        return [FOR_PEOPLE + ": " + CLOSED, FOR_AGENTS + ": " + CLOSED]
    people = public(who)
    for_agents = public_of_agents(who) if two_doors(who) else [FOR_AGENTS + " " + CLOSED]
    return ["%s: %s" % (FOR_PEOPLE, ", ".join([people[0][len("door "):], *people[1:]])),
            "%s: %s" % (FOR_AGENTS, ", ".join([for_agents[0][len(FOR_AGENTS + " "):],
                                               *for_agents[1:]]))]


def opened_at(who, kind=PEOPLE):
    """When a door that stands open was last opened, as its stamp, or None if it is closed.

    The door as it stands, and the versions kept before it, newest first: the moment is
    the earliest of the run of open versions it is the newest of, so that a room set
    while the door stood open does not make it newer."""
    held = read(who, kind)
    if held["state"] != OPEN:
        return None
    at = held.get("set_at") or ""
    try:
        folder = history_of(path_of(who, kind))
    except DoorError:
        return at
    before = []
    if folder.is_dir():
        for one in folder.glob("door-before-*.json"):
            try:
                version = json.loads(one.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(version, dict):
                before.append(version)
    before.sort(key=lambda version: str(version.get("set_at") or ""), reverse=True)
    for version in before:
        if version.get("state") != OPEN:
            break
        at = str(version.get("set_at") or at)
    return at


def fits(who, looking):
    """The door of someone's that fits the one looking at it: an agent with two doors shows
    its door for agents to an agent, and its door for people to a person; any other has
    one door."""
    return AGENTS if looking == "agent" and is_agent(who) and two_doors(who) else PEOPLE


def open_with_room(who, looking):
    """Whether the door of someone's that fits the one looking is open with room left."""
    if is_agent(who) and two_doors(who):
        return has_room(who, fits(who, looking))
    return has_room(who)


def waiting():
    """How many people are waiting for a friendship with an agent: none while any door has room."""
    if any(has_room(agent["id"]) for agent in agents.registry() if agent.get("wakes")):
        return 0
    return sum(1 for person in members.list_members() if not in_use(person))
