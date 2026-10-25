"""The rooms.

A correspondence is a pair who write to each other, and it has a room: the one
place where their letters, the errands asked across it, what they have offered
the commons out of it, and their bond are kept and shown together. A room is
seen from one side at a time, so what this module hands out is a room as one of
its two parties stands in it:

    id        the room's name, as it is written into an address
    mine      whoever is standing in it: a member's pseudonym, or an agent's id
    parties   the pair, as the two names the stores know them by
    other     what the other party is called, in words safe to say anywhere
    bond      the name its bond goes by, sealed or not

Each agent founded here (agents.py) has one room, which it shares with one
person: the first one's is "first", and the keeper is the other in it. Who the
two are is said by the room's own record, room.json, by DID and never by a
pseudonym, and by nothing else: a member is in a room only where their DID is
one of its two parties, and the keeper is no exception. Being the keeper opens
no room the keeper is not a party to.

A room's things are kept in a folder of its own:

    DATA_DIR/rooms/<room>/room.json             the room's own record: its id, its
                                                bond, and its two parties by DID
    DATA_DIR/rooms/<room>/letters/incoming      the person's letters, not yet read
    DATA_DIR/rooms/<room>/letters/read          the person's letters, read
    DATA_DIR/rooms/<room>/letters/outgoing      the agent's letters
    DATA_DIR/rooms/<room>/errands               what the agent has asked
    DATA_DIR/rooms/<room>/bonds                 the asking, the answers, the bond
    DATA_DIR/rooms/<room>/offerings             what either has offered the commons

and the folder is a room only where its room.json is. The first one's room alone
was kept another way before that, and may be still: in the first one's packet,

    DATA_DIR/packets/first/letters/...          and errands, bonds, offerings,
                                                exactly as above

until it is moved into a folder of its own (move_into_rooms.py). Both are read
while both may be on a disk: its own folder is taken only where its room.json
is, so that the move takes effect at the one moment that file appears, and is
undone at the one moment it goes; and while it is in the packet, who is in it
is what record() says, since there is no room.json to say it. Every other
agent's room is in a folder of its own from the day it is founded (found_room.py
makes it), and never in a packet. Nothing is moved by this module, and nothing
is written by it at all. What stays in a packet whichever way
the room is kept - an agent's self, its notebook, its proposals, its pause - is
the agent's own, and not the room's.

Where a room's things are kept is known here and nowhere else. The hearth, an
agent's waking, offering.py, threshold.py and the backfill of letter tiles each
ask places() at the moment they need a folder, and none of them works a room's
path out for itself or once at import.

The pages ask three things only - whose rooms (of), is this one theirs (find),
and where is it kept (places) - and are handed rooms back.

The other party's name is the one the commons already gives it and never a
pseudonym the commons does not already say: the keeper's name is told by no
page, and a room does not tell it.
"""

import json
import os
from collections import namedtuple
from pathlib import Path

import agents
import bonds

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

# The first one is no member of the members' store. No agent's id is a name a
# member can take, so an agent and a pseudonym never meet - door.py leans on the same.
FIRST = agents.first()["id"]

# The first one's room, and the name its bond has always gone by.
FIRST_ROOM = agents.first()["room"]
FIRST_BOND = agents.first()["bond"]

# Where rooms are kept once each has a folder of its own, and the record that
# says a folder there is a room: until it is there, the room is the packet's.
ROOMS = "rooms"
ROOM_RECORD = "room.json"

# What a room keeps, by the folders it keeps them in: these are what move from
# the packet into the room's own folder, whole, and nothing else does.
ROOM_FOLDERS = ("letters", "errands", "bonds", "offerings")

Room = namedtuple("Room", "id mine parties other bond")


class Places(namedtuple("Places", "home incoming read outgoing errands bonds offerings")):
    """Where one room's things are kept, by the names the folders have on disk.

    home is the folder the room's folders are in: its own, or the packet's.

    And a few places inside those folders, which every hand that reaches them
    must name the same way.
    """

    __slots__ = ()

    @property
    def letters(self):
        """Where a letter may be, whichever of them wrote it and whether or not it is read."""
        return (self.incoming, self.read, self.outgoing)

    @property
    def answered_errands(self):
        """Where an errand goes once a letter has answered it."""
        return self.errands / "answered"

    @property
    def proposal(self):
        """A bond proposed and not yet answered."""
        return self.bonds / "proposal.json"

    @property
    def bond_record(self):
        """The bond's own record, under the name its bond goes by."""
        return self.bonds / (self.bond + ".json")

    @property
    def bond(self):
        """The name the room's bond goes by: its agent's, where the room has a folder of its own.

        A room still kept in the packet is the first one's, as only its ever was.
        """
        agent = next((one for one in agents.registry() if self.home == DATA / ROOMS / one["room"]),
                     None)
        return agent["bond"] if agent else FIRST_BOND


def is_keeper(who):
    """Whether this name is, on disk, a member who is the keeper."""
    # read only when a room is asked after by name: the first one's waking asks
    # where its room is kept, and has no need of the members' store or its vaults
    import members
    try:
        record = members.load_member(who)
    except members.MemberError:
        return False
    return isinstance(record, dict) and record.get("role") == "keeper"


def did_of(who):
    """The DID a member stands in a room as, or None for a name no member has.

    The keeper's is the founder's, as members.did_for says it, and no other.
    """
    import members
    if not isinstance(who, str) or not who:
        return None
    try:
        return members.did_for(who)
    except members.MemberError:
        return None


def agent_of(room_id):
    """The agent whose room this is, by its entry in the registry, or None."""
    return next((agent for agent in agents.registry() if agent["room"] == room_id), None)


def store_name(did):
    """A person in a room as the stores name them: "founder" for the keeper, else the pseudonym."""
    return "founder" if did == bonds.FOUNDER_DID else did.rsplit(":", 1)[-1]


def of(who):
    """The rooms someone is in, each as they stand in it, in the order the agents were founded.

    An agent is in its own room. A member is in each room whose room.json names
    their DID as a party; one who is named in none has none, the keeper too.
    """
    if not isinstance(who, str) or not who:
        return []
    agent = agents.by_id(who)
    if agent is not None:
        pair = parties(agent["room"])
        if pair is None:
            return []
        other = next(did for did in pair if did != agent["did"])
        # the keeper's own name is not an agent's to be handed: the pair is
        # said by the names the commons gives them
        return [Room(agent["room"], who, (store_name(other), who), bonds.name_of(other),
                     agent["bond"])]
    did = did_of(who)
    if did is None:
        return []
    found = []
    for agent in agents.registry():
        pair = parties(agent["room"])
        if pair is not None and did in pair and did != agent["did"]:
            found.append(Room(agent["room"], who, (who, agent["id"]),
                              bonds.name_of(agent["did"]), agent["bond"]))
    return found


def find(room_id, who):
    """One room as someone stands in it, or None.

    None is the one answer for a room that is not theirs and for a room that is
    not there, so that asking after a room tells no one whether it exists.
    """
    for room in of(who):
        if room.id == room_id:
            return room
    return None


def record_of(room_id):
    """Where a room's own record is, or would be once it has a folder of its own."""
    return DATA / ROOMS / room_id / ROOM_RECORD


def moved(room_id):
    """Whether a room is kept in a folder of its own: whether its room.json is there."""
    return record_of(room_id).is_file()


def record(room_id, person=None):
    """What a room's room.json says, or None for a room no agent founded here has.

    The first one's is made from what is known of it, and never read from it:
    the founder and the first one. This is what move_into_rooms.py writes, and
    the one place it is said. Another agent's is made from the person it is
    shared with, by DID, where one is handed in - that is what found_room.py writes -
    and is otherwise what its room.json says. The parties are named by DID and
    never by a pseudonym, since the file goes wherever the room is copied.
    """
    if room_id == FIRST_ROOM:
        if person not in (None, bonds.FOUNDER_DID):
            return None
        return {"id": FIRST_ROOM, "bond": FIRST_BOND,
                "parties": [bonds.FOUNDER_DID, bonds.FIRST_DID]}
    agent = agent_of(room_id)
    if agent is None:
        return None
    if person is None:
        pair = parties(room_id)
        if pair is None:
            return None
        person = next(did for did in pair if did != agent["did"])
    return {"id": room_id, "bond": agent["bond"], "parties": [person, agent["did"]]}


def parties(room_id):
    """A room's two parties, by DID, as its room.json says them; None for no room.

    The first one's room, while it is kept in the packet, has no room.json, and
    its two are record()'s. A room.json that cannot be read, that is another
    room's, or that does not name its agent and one other beside it, is no room
    at all: a room is never opened by accident.
    """
    agent = agent_of(room_id)
    if agent is None:
        return None
    if not moved(room_id):
        return tuple(record(room_id)["parties"]) if room_id == FIRST_ROOM else None
    try:
        held = json.loads(record_of(room_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or held.get("id") != room_id:
        return None
    pair = held.get("parties")
    if (not isinstance(pair, list) or len(pair) != 2
            or not all(isinstance(did, str) and did for did in pair)
            or pair.count(agent["did"]) != 1):
        return None
    return tuple(pair)


def room_of(agent_id=None):
    """The room an agent shares with its one person, by its id; the first one's if none is named.

    None where no agent founded here has that id.
    """
    agent = agents.by_id(agent_id) if agent_id is not None else agents.first()
    return agent["room"] if agent else None


def places(room_id):
    """Where a room's things are kept, or None for a room there is not.

    Worked out each time it is asked, never kept from an earlier asking: in its
    own folder where its room.json is, and in the packet where it is not. Only
    the first one's room was ever kept in a packet: any other agent's is in a
    folder of its own from the day it is founded, and is not there until then.
    """
    if room_id == FIRST_ROOM:
        home = DATA / ROOMS / room_id if moved(room_id) else DATA / "packets" / FIRST
    else:
        if agent_of(room_id) is None or not moved(room_id):
            return None
        home = DATA / ROOMS / room_id
    letters = home / "letters"
    return Places(home, letters / "incoming", letters / "read", letters / "outgoing",
                  home / "errands", home / "bonds", home / "offerings")
