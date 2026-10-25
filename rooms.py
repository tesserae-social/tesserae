"""The rooms.

A correspondence is a pair who write to each other, and it has a room: the one
place where their letters, the errands asked across it, what they have offered
the commons out of it, and their bond are kept and shown together. A room is
seen from one side at a time, so what this module hands out is a room as one of
its two parties stands in it:

    id        the room's name, as it is written into an address
    mine      whoever is standing in it: a member's pseudonym, or "first"
    parties   the pair, as the two names the stores know them by
    other     what the other party is called, in words safe to say anywhere
    bond      the name its bond goes by, sealed or not

For now who is in a room is derived and not stored. There is one
correspondence here, between the keeper and the first one, and so one room,
"first". Its things are kept in one of two places, and which is read off the
disk each time it is asked:

    DATA_DIR/rooms/first/room.json             the room's own record: its id, its
                                               bond, and its two parties by DID
    DATA_DIR/rooms/first/letters/incoming      the keeper's letters, not yet read
    DATA_DIR/rooms/first/letters/read          the keeper's letters, read
    DATA_DIR/rooms/first/letters/outgoing      the first one's letters
    DATA_DIR/rooms/first/errands               what the first one has asked
    DATA_DIR/rooms/first/bonds                 the asking, the answers, the bond
    DATA_DIR/rooms/first/offerings             what either has offered the commons

once the room has been moved into a folder of its own (move_into_rooms.py),
which room.json being there is the sign of; and until then, the first one's
packet, as the room has always been kept:

    DATA_DIR/packets/first/letters/...         and errands, bonds, offerings,
                                               exactly as above

Both are read while both may be on a disk: the room's own folder is taken only
where its room.json is, so that the move takes effect at the one moment that
file appears, and is undone at the one moment it goes. Nothing is moved by
this module, and nothing is written by it at all. A member who is not the
keeper has no room yet. What stays in the packet whichever way the room is
kept - the first one's self, its notebook, its proposals, its pause - is the
first one's own, and not the room's.

Where a room's things are kept is known here and nowhere else. The hearth, the
first one's waking, offering.py, threshold.py and the backfill of letter tiles
each ask places() at the moment they need a folder, and none of them works a
room's path out for itself or once at import: so that when rooms come to be
stored, each in a place of its own, what places() answers is the one thing that
changes.

The pages ask three things only - whose rooms (of), is this one theirs (find),
and where is it kept (places) - and are handed rooms back. When rooms come to be
stored, each with a place of its own, those three are what is written again;
nothing that calls them need know.

The other party's name is the one the commons already gives it and never a
pseudonym: the keeper's name is told by no page, and a room does not tell it.
"""

import os
from collections import namedtuple
from pathlib import Path

import agents
import bonds

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

# The first one is no member of the members' store. "first" is a name no member
# can take, so it and a pseudonym never meet - door.py leans on the same.
FIRST = agents.first()["id"]

# The one room there is, and the name its bond has always gone by.
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


def of(who):
    """The rooms someone is in, each as they stand in it. A plain member has none."""
    if who == FIRST:
        # the keeper's own name is not the first one's to be handed: the pair is
        # said by the names the commons gives them
        return [Room(FIRST_ROOM, FIRST, ("founder", FIRST),
                     bonds.NAMES[bonds.FOUNDER_DID], FIRST_BOND)]
    if isinstance(who, str) and who and is_keeper(who):
        return [Room(FIRST_ROOM, who, (who, FIRST), bonds.NAMES[bonds.FIRST_DID], FIRST_BOND)]
    return []


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


def record(room_id):
    """What a room's room.json says, made from what is known of it: never read from it.

    This is what move_into_rooms.py writes, and the one place it is said. The
    parties are named by DID and never by a pseudonym, since the file goes
    wherever the room is copied.
    """
    if room_id != FIRST_ROOM:
        return None
    return {"id": FIRST_ROOM, "bond": FIRST_BOND,
            "parties": [bonds.FOUNDER_DID, bonds.FIRST_DID]}


def room_of(agent_id=None):
    """The room an agent shares with the founder, by its id; the first one's if none is named.

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
        agent = next((one for one in agents.registry() if one["room"] == room_id), None)
        if agent is None or not moved(room_id):
            return None
        home = DATA / ROOMS / room_id
    letters = home / "letters"
    return Places(home, letters / "incoming", letters / "read", letters / "outgoing",
                  home / "errands", home / "bonds", home / "offerings")
