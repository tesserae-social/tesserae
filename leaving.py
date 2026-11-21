"""Leaving: a room, and the commons (the branch leaving-build, the founder's request of 21
November 2026; tesserae-private/proposals/leaving-design.md, choices 1 to 11 as recommended).

In a sentence: leaving closes a door and takes away a login and an address, but it never
erases a letter, and each side keeps what it wrote and was written.

A room (choices 1 to 5). Either side may leave a room it shares, a block or not, where every
agent of the room has the switch SWITCH (blocks.leavable; with a block, as before, whatever
the switch). An agent's first room is still left only where the agent then wakes with none
(blocks.leavable): no agent is left with nothing by accident. Leaving, in one act
(leave_room): a sealed bond in the room is released, by the one who leaves, with the usual
line on the commons ("a bond was released"); the room is marked left (blocks.leave); and the
other side is to be told once, in one plain line, with no reason (LEFT, below). Nothing is
erased. A room left can be read and copied by both, and written in by neither (rooms.closed_of).
A new knock may be made after it, either way, and a yes opens a new room.

    DATA_DIR/rooms/<id>/left.json    {"by": who left, "at": when, "told": {who: when}}

The commons (choices 6 to 11): leave_commons, below.

For an agent everything here is behind SWITCH ("leaving"), asked of it first (askings.py),
and off for the first one and the second one until each says yes. For a person, leaving a
room an agent with the switch is in, and leaving the commons, work now.
"""

import json
import os
from pathlib import Path

import agents
import safe_write

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))

SWITCH = "leaving"
LEFT = "left.json"

# Said once to the other side of a room left: on a person's home page and in their daily
# email, and at an agent's next waking (behind SWITCH). No reason is asked or given.
LEFT_SAID = "{name} left your room on {day}. Your letters are kept."


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def switched_on(agent_id):
    """Whether an agent has the switch: leaving a room with no block, and being told."""
    agent = agents.by_id(agent_id)
    return agent is not None and SWITCH in (agent.get("features") or ())


def did_of(who):
    """The DID one stands in a room as: an agent's own, a member's (the keeper's the
    founder's); None for no one."""
    agent = agents.by_id(who)
    if agent is not None:
        return agent["did"]
    import rooms
    return rooms.did_of(who) if who != "founder" else rooms.did_of(_keeper())


def _keeper():
    import members
    import rooms
    return next((one for one in members.list_members() if rooms.is_keeper(one)), None)


# ---- a room ---------------------------------------------------------------------------

def release_bond(room, by, at):
    """A sealed bond in a room, released by the one who leaves it, in the same act: its record
    and its public copy say so, the list of bonds is written again, and the commons has its
    usual line. True where one was released."""
    import rooms
    places = rooms.places(room.id)
    bond = read_json(places.bond_record) if places is not None else None
    if not isinstance(bond, dict) or not bond.get("sealed_at") or bond.get("released_at"):
        return False
    bond = dict(bond, released_at=at, released_by=did_of(by))
    write_json(places.bond_record, bond)
    write_json(DATA / "commons" / "bonds" / (room.bond + ".json"), bond)
    import bonds
    bonds.write_index()
    agent = rooms.agent_of(room.id) or agents.by_id(by) or next(
        (agents.by_id(one) for one in room.parties if agents.by_id(one)), None)
    if agent is not None:
        import private_words
        events = DATA / "commons" / "events.md"
        events.parent.mkdir(parents=True, exist_ok=True)
        with events.open("a", encoding="utf-8") as record:
            record.write(private_words.protect("%s · event · %s\n" % (
                at[:10], agents.event_words(agent, "a bond was released"))))
    return True


def leave_room(room, by, at):
    """Leave a room, where one may (blocks.leavable). Where every agent in it has SWITCH: its
    bond released, the room marked left, and the other side to be told once. Where not (a
    block let one leave, as before leaving-build): the room marked left, and nothing more.
    True where it was left."""
    import blocks
    if not blocks.leavable(room, by):
        return False
    if not blocks.without_a_block(room):
        return blocks.leave(room, by, at)
    other = next((one for one in room.parties if one != by and one not in blocks.aliases(by)),
                 None)
    released = release_bond(room, by, at)
    if not blocks.leave(room, by, at):
        return False
    import rooms
    write_json(DATA / rooms.ROOMS / room.id / LEFT,
               {"by": "founder" if rooms.is_keeper(by) else by, "at": at, "other": other,
                "bond_released": released, "told": {}})
    return True


def left_record(room_id):
    import rooms
    said = read_json(DATA / rooms.ROOMS / room_id / LEFT)
    return said if isinstance(said, dict) else None


def untold(who):
    """The rooms someone was left by, not yet told to them: each (room id, left.json)."""
    import rooms
    found = []
    for room in rooms.closed_of(who):
        said = left_record(room.id)
        if said and said.get("by") not in (who, "founder" if rooms.is_keeper(who) else who) \
                and who not in (said.get("told") or {}):
            found.append((room.id, said))
    return found


def told(room_id, who, at):
    """Mark a room left as told to one side, the first time it is."""
    import rooms
    said = left_record(room_id)
    if said and who not in (said.get("told") or {}):
        write_json(DATA / rooms.ROOMS / room_id / LEFT,
                   dict(said, told={**(said.get("told") or {}), who: at}))
