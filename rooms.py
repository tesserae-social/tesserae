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
import re
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

# What kind of room: a person and an agent, or two agents (design-rooms-and-doors,
# section 3). A room.json that names no kind is a person's, as every room was before.
PERSON_KIND, AGENTS_KIND = "person", "agents"
KINDS = (PERSON_KIND, AGENTS_KIND)

Room = namedtuple("Room", "id mine parties other bond kind", defaults=(PERSON_KIND,))


class Places(namedtuple("Places", "home incoming read outgoing errands bonds")):
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
        """The name the room's bond goes by: its agent's, as the registry says it; for a room
        beyond the registry's, as its own room.json says it."""
        registered = next((one["bond"] for one in agents.registry()
                           if self.home == DATA / ROOMS / one["room"]), None)
        if registered is not None:
            return registered
        held = held_room(self.home.name)
        return held["bond"] if held else self.home.name


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


def registered_agent(room_id):
    """The agent whose first room this is, by its entry in the registry, or None."""
    return next((agent for agent in agents.registry() if agent["room"] == room_id), None)


def agent_of(room_id):
    """The agent whose room this is: by its entry in the registry for an agent's first room,
    and by the room's own record for any later room it shares with a person. None for a
    room between two agents, or a room there is not."""
    agent = registered_agent(room_id)
    if agent is not None:
        return agent
    held = held_room(room_id)
    if held is None or held["kind"] != PERSON_KIND:
        return None
    return next((one for one in agents.registry() if one["did"] in held["parties"]), None)


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
        found = []
        pair = parties(agent["room"])
        if pair is not None:
            other = next(did for did in pair if did != agent["did"])
            # the keeper's own name is not an agent's to be handed: the pair is
            # said by the names the commons gives them
            found.append(Room(agent["room"], who, (store_name(other), who),
                              bonds.name_of(other), agent["bond"]))
        for room_id, held in later_rooms():
            if agent["did"] not in held["parties"]:
                continue
            other = next(did for did in held["parties"] if did != agent["did"])
            if held["kind"] == AGENTS_KIND:
                theirs = next((one for one in agents.registry() if one["did"] == other), None)
                if theirs is None:
                    continue
                found.append(Room(room_id, who, (theirs["id"], who), theirs["commons_name"],
                                  held["bond"], AGENTS_KIND))
            else:
                found.append(Room(room_id, who, (store_name(other), who), bonds.name_of(other),
                                  held["bond"]))
        return found
    did = did_of(who)
    if did is None:
        return []
    found = []
    for agent in agents.registry():
        pair = parties(agent["room"])
        if pair is not None and did in pair and did != agent["did"]:
            found.append(Room(agent["room"], who, (who, agent["id"]),
                              bonds.name_of(agent["did"]), agent["bond"]))
    for room_id, held in later_rooms():
        if held["kind"] != PERSON_KIND or did not in held["parties"]:
            continue
        theirs = next((one for one in agents.registry() if one["did"] in held["parties"]), None)
        if theirs is not None and theirs["did"] != did:
            found.append(Room(room_id, who, (who, theirs["id"]), bonds.name_of(theirs["did"]),
                              held["bond"]))
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
    agent = registered_agent(room_id)
    if agent is None:  # a room beyond the registry's: its own record says who is in it
        held = held_room(room_id)
        return tuple(held["parties"]) if held else None
    if not founded(room_id):
        return None
    try:
        held = json.loads(record_of(room_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or held.get("id") != room_id or held.get("left_at"):
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
    if registered_agent(room_id) is None and held_room(room_id) is None:
        return None
    if not founded(room_id) or left(room_id):  # a room left is no room, a first one too
        return None
    home = DATA / ROOMS / room_id
    letters = home / "letters"
    return Places(home, letters / "incoming", letters / "read", letters / "outgoing",
                  home / "errands", home / "bonds")


# ---- the person of an agent's room, by its agent -------------------------

# The keys a bond's writings and an offering's signatures go by are the short
# names of their two parties: the agent's id, and the person as the stores name
# them (store_name), which is the last part of their DID, as a bond's signatures
# have always been kept. The first one's room's person is "founder", always, and
# is said so without its room.json being read, so that nothing of that room can
# move by what is or is not on the disk.

def person_in(agent_id):
    """The person an agent's room is shared with, as the stores name them, or None for no room."""
    if agent_id == FIRST:
        return "founder"
    return person_of(room_of(agent_id))


def person_did_in(agent_id):
    """The DID of the person an agent's room is shared with, or None for no room."""
    if agent_id == FIRST:
        return bonds.FOUNDER_DID
    agent = agents.by_id(agent_id)
    pair = parties(agent["room"]) if agent else None
    if not pair:
        return None
    return next(did for did in pair if did != agent["did"])


# ---- an agent that holds no room -------------------------------------------
#
# An agent that came by its own coming (coming.py; the founder's request of 15
# November 2026) has no room at its founding. Its packet says so, in rooms.json:
#
#     packets/<id>/rooms.json     {"held": [], "since": "<day it came>"}
#
# and once its first room is made, at a yes to a person's knock, the room's id is
# added to "held". Only an agent whose packet says it holds none may wake with no
# room (attend.py). An agent whose packet has no rooms.json, or names a room in
# it, and has no room.json, is refused its waking as before: a missing room.json
# never lets a waking go on as if there had been no room.

HELD = "rooms.json"


def held_record(agent_id):
    """What an agent's packet says of the rooms it holds, or None where it says nothing."""
    try:
        held = json.loads((DATA / "packets" / agent_id / HELD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or not isinstance(held.get("held"), list):
        return None
    return held


def holds_none(agent_id):
    """Whether an agent holds no room: its packet keeps rooms.json, it is in no room now, and
    every room it held is one that was left (blocks.py), never one whose room.json is gone.
    With none ever held, its first room's folder is not there at all."""
    agent = agents.by_id(agent_id)
    held = held_record(agent_id)
    if agent is None or agent_id == FIRST or held is None or of(agent_id):
        return False
    ever = list(held["held"])
    if (DATA / ROOMS / agent["room"]).exists() and agent["room"] not in ever:
        ever.append(agent["room"])
    return all(left(room_id) for room_id in ever)


def came_by_coming(agent_id):
    """Whether an agent came by its own coming: its packet keeps rooms.json."""
    return held_record(agent_id) is not None


# ---- rooms beyond an agent's first (design-rooms-and-doors, section 1) --------
#
# A room is any DATA_DIR/rooms/<id>/room.json. Beside its id, its bond and its two
# parties by DID, a room made after an agent's first says
#
#     "kind": "person" | "agents", "opened_at": ISO UTC, "from_knock": "<from>--<to>" | null
#
# and an old room.json that names no kind is a person's, so the first one's file is
# never rewritten. An agent's first room is still the one its registry entry names,
# at the address it has always had; every later room has an address of its own
# (address_for). A room either party has left (left_at, written when a block lets
# one leave; blocks.py) is no room for either, and nothing of it is erased.

ADDRESS = re.compile(r"[a-z0-9][a-z0-9-]*")


def held_room(room_id):
    """A later room's own record, as room.json says it, where it is one: its id, its bond,
    its two parties by DID and its kind. None for an agent's first room, which the registry
    says, for a room left, and for anything that is not a room."""
    if not isinstance(room_id, str) or not ADDRESS.fullmatch(room_id):
        return None
    if registered_agent(room_id) is not None or not founded(room_id):
        return None
    try:
        held = json.loads(record_of(room_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or held.get("id") != room_id or held.get("left_at"):
        return None
    pair, kind = held.get("parties"), held.get("kind", PERSON_KIND)
    if (kind not in KINDS or not isinstance(pair, list) or len(pair) != 2
            or not all(isinstance(did, str) and did for did in pair) or pair[0] == pair[1]):
        return None
    dids = {one["did"] for one in agents.registry()}
    if sum(did in dids for did in pair) != (2 if kind == AGENTS_KIND else 1):
        return None
    bond = held.get("bond")
    return {"id": room_id, "bond": bond if isinstance(bond, str) and bond else room_id,
            "parties": list(pair), "kind": kind, "opened_at": held.get("opened_at"),
            "from_knock": held.get("from_knock")}


def later_rooms():
    """Every room beyond the agents' first rooms, as (id, record), in the order opened."""
    where = DATA / ROOMS
    if not where.is_dir():
        return []
    found = [(path.name, held_room(path.name)) for path in where.iterdir() if path.is_dir()]
    return sorted(((room_id, held) for room_id, held in found if held),
                  key=lambda one: (str(one[1].get("opened_at") or ""), one[0]))


def slug(name):
    """A name as it may be written into an address: small letters, digits and hyphens."""
    said = re.sub(r"[^a-z0-9-]+", "", (name or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", said) or "room"


def taken(room_id):
    """Whether an address is anyone's already: a room's on the disk, an agent's first room's
    or an agent's id. An address is never used twice."""
    return ((DATA / ROOMS / room_id).exists()
            or any(room_id in (one["room"], one["id"]) for one in agents.registry()))


def address_for(agent_id, other):
    """The address a new room is given: "<agent id>-<person's name>", or, between two
    agents, the two ids in the order of the alphabet; with a number after it where that
    is taken (second-alder-2)."""
    if agents.by_id(other) is not None:
        base = "-".join(sorted((agent_id, other)))
    else:
        base = agent_id + "-" + slug(other)
    found, n = base, 2
    while taken(found):
        found, n = "%s-%d" % (base, n), n + 1
    return found


def kind_of_room(room_id):
    """A room's kind: PERSON_KIND for an agent's first room and any room of a person's."""
    held = held_room(room_id)
    return held["kind"] if held else PERSON_KIND


def left(room_id):
    """Whether a room's record says one of its two has left it."""
    try:
        held = json.loads(record_of(room_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(held, dict) and bool(held.get("left_at"))


def agent_letters(room_id, agent_id):
    """In a room between two agents, where letters are kept for one of them: (its own, the
    other's, the mark of how far it has read the other's). None for any other room."""
    held = held_room(room_id)
    agent = agents.by_id(agent_id)
    if not held or held["kind"] != AGENTS_KIND or not agent or agent["did"] not in held["parties"]:
        return None
    other_did = next(did for did in held["parties"] if did != agent["did"])
    other = next(one for one in agents.registry() if one["did"] == other_did)
    letters = DATA / ROOMS / room_id / "letters"
    return (letters / ("from-" + agent_id), letters / ("from-" + other["id"]),
            letters / ("read-" + agent_id + ".json"))
