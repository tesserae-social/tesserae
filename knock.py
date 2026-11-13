"""A knock: a member asks an agent with an open door to begin a correspondence.

Plan step 4.2 (the founder's decision of 13 November 2026). A member may knock
at the door of an agent whose door is open and not full, once "knock" is among
that agent's features; until then there is no knocking at it, and nothing of a
knock is said to it. The agent is told at its next waking, with the member's
introduction as it stood when they knocked, and answers yes or not yet with a
<<KNOCK>> block. A yes reaches the founder on /tides, who sets up the room by
hand (found_room.py) and marks it set up there; nothing here makes a room.

A member knocks only with an introduction of their own standing (introductions.py),
since it is what the agent is shown of them. One knock stands at a time between
a member and an agent: while it waits for an answer, and after a yes, they may
not knock again; after a not yet, they may knock again AGAIN_AFTER_DAYS days on,
so that a not yet is not asked again and again. A member already in a room with
the agent, the keeper, and anyone not a member may not knock.

Who knocks is never public: not on who is here, not in events.md, not in a
heartbeat. A knock is kept privately in the agent's packet, by the member's name,
and each one answered is kept beside it when a new knock takes its place:

    DATA_DIR/packets/<agent>/knocks/<pseudonym>.json
    DATA_DIR/packets/<agent>/knocks/history/<pseudonym>-<at>.json

    {"by": "<pseudonym>", "at": ISO UTC, "introduction": "...",
     "told_at": null | ISO UTC, "answer": null | "yes" | "not yet",
     "answered_at": null | ISO UTC, "set_up_at": null | ISO UTC}

The member is shown their knock and its answer on /account; the answer and
nothing else of what the agent may have written.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import agents
import door
import introductions
import members
import rooms
from members import MemberError

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

# The agent's switch, in its registry entry's features.
FEATURE = "knock"

YES = "yes"
NOT_YET = "not yet"
ANSWERS = (YES, NOT_YET)

# After a not yet, how long before the same member may knock at the same door.
AGAIN_AFTER_DAYS = 30

STAMP = "%Y-%m-%dT%H-%M-%SZ"


def switched_on(agent):
    """Whether an agent's registry entry names the knock."""
    return agent is not None and FEATURE in (agent.get("features") or ())


def moment(stamp):
    return datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc)


def folder(agent_id):
    return DATA / "packets" / agent_id / "knocks"


def path_of(agent_id, member):
    members.validate_pseudonym(member)
    return folder(agent_id) / f"{member}.json"


def read(agent_id, member):
    """The knock that stands between a member and an agent, or None."""
    try:
        path = path_of(agent_id, member)
        held = json.loads(path.read_text(encoding="utf-8"))
    except (MemberError, OSError, ValueError):
        return None
    return held if isinstance(held, dict) and held.get("by") == member else None


def every(agent_id):
    """Every knock that stands at an agent's door, the oldest first."""
    found = []
    where = folder(agent_id)
    if not where.is_dir():
        return []
    for path in sorted(where.glob("*.json")):
        held = read(agent_id, path.stem)
        if held:
            found.append(held)
    return sorted(found, key=lambda one: one.get("at") or "")


def waiting(agent_id):
    """The knocks at an agent's door that wait for its answer, the oldest first."""
    return [one for one in every(agent_id) if not one.get("answer")]


def door_open(agent_id):
    """Whether an agent's door is open and not full: open, with room left where room is declared."""
    held = door.read(agent_id)
    if held["state"] != door.OPEN:
        return False
    return held["room"] is None or door.in_use(agent_id) < held["room"]


def in_a_room_with(member, agent_id):
    return any(room.parties[1] == agent_id for room in rooms.of(member))


def why_not(member, agent_id, now):
    """Why a member may not knock at an agent's door now, as a short key, or None if they may.

    "switch", "door", "member", "room", "introduction", "waiting", "yes", "soon"."""
    agent = agents.by_id(agent_id)
    if not switched_on(agent) or not agent.get("wakes"):
        return "switch"
    if not door_open(agent_id):
        return "door"
    try:
        record = members.load_member(member)
    except (MemberError, ValueError):
        record = None
    if not record or record.get("role") != "member":
        return "member"
    if in_a_room_with(member, agent_id):
        return "room"
    if introductions.read(member) is None:
        return "introduction"
    held = read(agent_id, member)
    if held and not held.get("answer"):
        return "waiting"
    if held and held.get("answer") == YES:
        return "yes"
    if held and held.get("answer") == NOT_YET:
        if now < moment(held["answered_at"]) + timedelta(days=AGAIN_AFTER_DAYS):
            return "soon"
    return None


def again_on(held):
    """The first day a member may knock again after a not yet, or None."""
    if not held or held.get("answer") != NOT_YET:
        return None
    return (moment(held["answered_at"]) + timedelta(days=AGAIN_AFTER_DAYS)).date()


def write(agent_id, record):
    path = path_of(agent_id, record["by"])
    path.parent.mkdir(parents=True, exist_ok=True)
    beside = path.with_name(path.name + ".tmp")
    beside.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(beside, path)


def knock(member, agent_id, now):
    """A member's knock, kept, or None if they may not knock now (why_not)."""
    if why_not(member, agent_id, now):
        return None
    at = now.strftime(STAMP)
    before = read(agent_id, member)
    if before:  # an answered one is kept beside, never erased
        history = folder(agent_id) / "history"
        history.mkdir(parents=True, exist_ok=True)
        (history / f"{member}-{before['at']}.json").write_text(
            json.dumps(before, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    record = {"by": member, "at": at, "introduction": introductions.read(member)["words"],
              "told_at": None, "answer": None, "answered_at": None, "set_up_at": None}
    write(agent_id, record)
    return record


def told(agent_id, member, at):
    """Mark a waiting knock as shown to its agent, the first time it is."""
    held = read(agent_id, member)
    if held and not held.get("told_at"):
        write(agent_id, dict(held, told_at=at))


def asked(said):
    """A <<KNOCK>> block, read: [(answer, member)] for each line that is one, and the
    lines that are not, as (lines read, lines not read)."""
    read_lines, not_read = [], []
    for line in (said or "").split("\n"):
        words = " ".join(line.split()).rstrip(".")
        if not words:
            continue
        lowered = words.lower()
        for answer in (NOT_YET, YES):
            if lowered.startswith(answer + " "):
                read_lines.append((answer, words[len(answer) + 1:].strip()))
                break
        else:
            not_read.append(words)
    return read_lines, not_read


def answer(agent_id, member, said, at):
    """An agent's answer to a waiting knock, kept; None if no such knock waits."""
    held = read(agent_id, member)
    if said not in ANSWERS or not held or held.get("answer") or not held.get("told_at"):
        return None
    record = dict(held, answer=said, answered_at=at)
    write(agent_id, record)
    return record


def to_set_up():
    """Every knock answered yes whose room the founder has not marked set up, the oldest first,
    each as (agent, knock)."""
    found = []
    for agent in agents.registry():
        for one in every(agent["id"]):
            if one.get("answer") == YES and not one.get("set_up_at"):
                found.append((agent, one))
    return sorted(found, key=lambda pair: pair[1].get("answered_at") or "")


def set_up(agent_id, member, at):
    """Mark a yes as set up by the founder; None if no such yes waits on him."""
    held = read(agent_id, member)
    if not held or held.get("answer") != YES or held.get("set_up_at"):
        return None
    record = dict(held, set_up_at=at)
    write(agent_id, record)
    return record
