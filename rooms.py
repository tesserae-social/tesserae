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

and the folder is a room only where its room.json is: with no room.json there
is no room, the first one's no less than any other's, and nothing stands in for
it. Every agent's room is in a folder of its own from the day it is founded
(found_room.py makes a later one's), and never in a packet. Nothing is written
by this module at all. What stays in a packet - an agent's self, its notebook,
its proposals, its pause - is the agent's own, and not the room's.

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

# The first one's room.
FIRST_ROOM = agents.first()["room"]

# Where rooms are kept, each in a folder of its own, and the record that says a
# folder there is a room: until it is there, there is no room.
ROOMS = "rooms"
ROOM_RECORD = "room.json"

Room = namedtuple("Room", "id mine parties other bond")


class Places(namedtuple("Places", "home incoming read outgoing errands bonds offerings")):
    """Where one room's things are kept, by the names the folders have on disk.

    home is the folder the room's folders are in: its own, under rooms/.

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
        """The name the room's bond goes by: its agent's, as the registry says it."""
        return next(one["bond"] for one in agents.registry()
                    if self.home == DATA / ROOMS / one["room"])


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


def person_of(room_id):
    """The person a room is shared with, as the stores name them, or None for no room.

    Their letters in it are named by it, and the agent's to them: "founder-<stamp>"
    and "to-founder-<stamp>" in a room the keeper is in, as the first one's always
    were, and "<pseudonym>-<stamp>" and "to-<pseudonym>-<stamp>" in any other, so
    that no letter in a later agent's room is named for someone who did not write
    it or is not its reader (gate G10, stage 8).
    """
    agent = agent_of(room_id)
    pair = parties(room_id)
    if agent is None or pair is None:
        return None
    return store_name(next(did for did in pair if did != agent["did"]))


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
    """Where a room's own record is, or would be once it is founded."""
    return DATA / ROOMS / room_id / ROOM_RECORD


def founded(room_id):
    """Whether a room is there at all: whether its room.json is."""
    return record_of(room_id).is_file()


def record(room_id, person=None):
    """What a room's room.json says, or None for a room no agent founded here has.

    It is made from the person the room is shared with, by DID, where one is
    handed in - that is what found_room.py writes - and is otherwise what its
    room.json says. The parties are named by DID and never by a pseudonym, since
    the file goes wherever the room is copied.
    """
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

    A room with no room.json, or whose room.json cannot be read, is another
    room's, or does not name its agent and one other beside it, is no room at
    all: a room is never opened by accident, the first one's no more than any.
    """
    agent = agent_of(room_id)
    if agent is None or not founded(room_id):
        return None
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
    own folder where its room.json is, and nowhere where it is not. Every
    agent's room is in a folder of its own from the day it is founded, and is
    not there until then.
    """
    if agent_of(room_id) is None or not founded(room_id):
        return None
    home = DATA / ROOMS / room_id
    letters = home / "letters"
    return Places(home, letters / "incoming", letters / "read", letters / "outgoing",
                  home / "errands", home / "bonds", home / "offerings")
