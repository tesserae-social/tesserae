"""A new agent's room, made once, at its founding.

Every agent founded here after the first one has a room from the day it is
founded, kept as rooms are kept now and never as the first one's once was:

    DATA_DIR/rooms/<room>/room.json             its id, its bond, and its two
                                                parties by DID
    DATA_DIR/rooms/<room>/letters/incoming      and read, outgoing, errands,
                                                bonds, offerings: made empty

rooms.py says where a room is kept and who is in it, and writes nothing; this
is the one hand that makes a room, and it makes it whole or refuses. Its
folders are made first and room.json last, written beside its place and then
put there, since room.json being there is what makes the folder a room. Nothing
is made where anything of the room is on the disk already, nor for the first
one, whose room was made long ago, nor with
an agent, or no one, as the person it is shared with.

It is run by hand, once, at a founding, and by nothing on the hearth:

    DATA_DIR=/data python found_room.py <agent id> <the person's DID>

DATA_DIR must be said, as founding_session.py asks.
"""

import json
import os
import sys

import agents
import rooms


class RoomError(Exception):
    """A room would not be made as asked. The message is safe to show."""


# The folders a room keeps its things in, made empty.
FOLDERS = ("letters/incoming", "letters/read", "letters/outgoing", "errands", "bonds",
           "offerings")


def found(agent_id, person, entry=None):
    """Make one agent's room, shared with one person named by DID; give back its places.

    entry is a founding's staged entry (found_agent.py), for an agent not yet in
    the registry: its room is made from that entry, and since no folder is a
    room until its agent is in the registry, what is given back then is only
    where the room is kept, its home. A staged entry whose id, DID, room or bond
    any agent in the registry has is refused.
    """
    registry = agents.registry()
    if entry is None:
        agent = agents.by_id(agent_id)
        if agent is None:
            raise RoomError("no agent founded here has that id")
    else:
        agent = entry
        if not isinstance(entry, dict) or entry.get("id") != agent_id:
            raise RoomError("the staged entry is not that agent's")
        for key in agents.NEEDS:
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise RoomError("the staged entry has no " + key)
        if any(one[key] == entry[key] for one in registry for key in agents.NEEDS):
            raise RoomError("a staged entry is for an agent not yet founded here")
    if agent["id"] == rooms.FIRST:
        raise RoomError("the first one's room is made already")
    if (not isinstance(person, str) or not person.startswith("did:")
            or person in {one["did"] for one in registry} or person == agent["did"]):
        raise RoomError("a room is shared with a person, named by DID")
    home = rooms.DATA / rooms.ROOMS / agent["room"]
    if home.exists():
        raise RoomError("something of that room is on the disk already")
    for folder in FOLDERS:
        (home / folder).mkdir(parents=True)
    said = (rooms.record(agent["room"], person) if entry is None
            else {"id": agent["room"], "bond": agent["bond"], "parties": [person, agent["did"]]})
    beside = home / (rooms.ROOM_RECORD + ".tmp")
    beside.write_text(json.dumps(said, indent=2) + "\n", encoding="utf-8")
    os.replace(beside, home / rooms.ROOM_RECORD)
    return rooms.places(agent["room"]) if entry is None else home


def main(args):
    if "DATA_DIR" not in os.environ:
        print("Say DATA_DIR: a room is made where it is meant to be, and nowhere else.")
        return 1
    if len(args) != 2:
        print("Usage: DATA_DIR=/data python found_room.py <agent id> <the person's DID>")
        return 1
    try:
        made = found(*args)
    except RoomError as refused:
        print("No room was made:", refused)
        return 1
    print("Made:", made.home)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
