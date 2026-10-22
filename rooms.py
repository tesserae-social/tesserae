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

For now a room is derived and not stored. There is one correspondence here,
between the keeper and the first one, and so one room, "first", which is the
first one's packet exactly as it has always been kept:

    DATA_DIR/packets/first/letters/incoming    the keeper's letters, not yet read
    DATA_DIR/packets/first/letters/read        the keeper's letters, read
    DATA_DIR/packets/first/letters/outgoing    the first one's letters
    DATA_DIR/packets/first/errands             what the first one has asked
    DATA_DIR/packets/first/bonds               the asking, the answers, the bond
    DATA_DIR/packets/first/offerings           what either has offered the commons

Nothing is moved to make a room, and nothing is written by this module at all.
A member who is not the keeper has no room yet.

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

import bonds

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

# The first one is no member of the members' store. "first" is a name no member
# can take, so it and a pseudonym never meet - door.py leans on the same.
FIRST = "first"

# The one room there is, and the name its bond has always gone by.
FIRST_ROOM = "first"
FIRST_BOND = "founder-first"

Room = namedtuple("Room", "id mine parties other bond")


class Places(namedtuple("Places", "packet incoming read outgoing errands bonds offerings")):
    """Where one room's things are kept, by the names the folders have on disk.

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
        return self.bonds / (FIRST_BOND + ".json")


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


def places(room_id):
    """Where a room's things are kept, or None for a room there is not.

    Worked out each time it is asked, never kept from an earlier asking.
    """
    if room_id != FIRST_ROOM:
        return None
    packet = DATA / "packets" / FIRST
    letters = packet / "letters"
    return Places(packet, letters / "incoming", letters / "read", letters / "outgoing",
                  packet / "errands", packet / "bonds", packet / "offerings")
