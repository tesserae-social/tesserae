"""The door.

Every member has a door, and it is theirs alone to open or to close. Beside it
they may say how much room they have: how many correspondences they can carry
wholly, from one to twelve. A door is one small record:

    {"state": "open" or "closed", "room": 1..12 or null, "set_at": ISO UTC}

kept privately, where the one whose door it is keeps everything else:

    DATA_DIR/members/<pseudonym>/door.json     a human member's
    DATA_DIR/packets/first/door.json           the first one's

and each version that stood before the one that stands now is kept beside it,
in door/history/, as a rhythm's is. No file at all is a closed door with no
room declared.

Two things about a door are public, and nothing else: whether it is open, and -
only where room has been declared - whether there is any left. The number is
never said outside: not how much room was declared, and not how much is in use.

The hearth and attend.py both work through this one module, so that what a
member sets, what the first one is told, and what the commons says are one
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

import members
from members import MemberError

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

# The first one is no member of the members' store, and its door is kept in its
# own packet. "first" is a name no member can take, so the two never meet.
FIRST = "first"
FIRST_DOOR = DATA / "packets" / FIRST / "door.json"

RECORD = "door.json"

OPEN = "open"
CLOSED = "closed"
STATES = (OPEN, CLOSED)

ROOM_LEAST = 1
ROOM_MOST = 12

# What set_door() is handed for the half of a door that is to be left as it stands.
AS_IT_WAS = object()

# The second line of a <<DOOR>> block, where it speaks of room at all: a number,
# or the one word that takes a declared room back to not declared.
ROOM_LINE = re.compile(r"room (\d{1,2})")
ROOM_NONE = "room none"

DOT = " · "


class DoorError(Exception):
    """The door would not be set as asked. The message is safe to show."""


# ---------------------------------------------------------------- where


def path_of(who):
    """Where one door is kept. Raises DoorError for a name no one could have."""
    if who == FIRST:
        return FIRST_DOOR
    try:
        members.validate_pseudonym(who)
    except MemberError:
        raise DoorError("there is no member by that name") from None
    return members.MEMBERS / who / RECORD


def history_of(path):
    """The folder beside a door where the versions before it are kept."""
    return path.parent / "door" / "history"


# ---------------------------------------------------------------- reading


def room_declared(room):
    """Whether a room is one a door may declare: a whole number, one to twelve."""
    return (isinstance(room, int) and not isinstance(room, bool)
            and ROOM_LEAST <= room <= ROOM_MOST)


def closed():
    """The door no one has set: closed, with no room declared."""
    return {"state": CLOSED, "room": None, "set_at": None}


def read(who):
    """One door as it stands. Anything that cannot be read is a closed door.

    That goes for no file, a file that is not a door, a state that is neither
    word, and a room that is no room: a door is never open by accident.
    """
    try:
        held = json.loads(path_of(who).read_text(encoding="utf-8"))
    except (DoorError, OSError, ValueError, TypeError):
        return closed()
    if not isinstance(held, dict) or held.get("state") not in STATES:
        return closed()
    room = held.get("room")
    return {"state": held["state"], "room": room if room_declared(room) else None,
            "set_at": held.get("set_at")}


def in_use(who):
    """How many correspondences someone is carrying now.

    Today there is one correspondence here, between the founder and the first
    one, so each of them carries one and no one else carries any.
    """
    if who == FIRST:
        return 1
    try:
        record = members.load_member(who)
    except MemberError:
        return 0
    return 1 if isinstance(record, dict) and record.get("role") == "keeper" else 0


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


def asked(said):
    """What a <<DOOR>> block asks for, as (state, room), or None if it cannot be read.

    Its first line that is not blank is "open" or "closed". The line under it
    may be "room N", or "room none", which takes a declared room back to not
    declared (a room of None); a line there that does not speak of room is only
    words, and the room is left as it was. A line that speaks of room and says
    neither makes the whole block unreadable, and nothing is changed by it.
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
    if not found or not room_declared(int(found.group(1))):
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


def set_door(who, state=AS_IT_WAS, room=AS_IT_WAS, at=None):
    """Set one door, and give it back as it now stands.

    Either half may be left as it was. A room of None is room not declared. The
    door that stood before is kept beside the new one, never erased; a door set
    to what it already is is not written again.
    """
    path = path_of(who)
    if who != FIRST and not (path.parent / members.RECORD).is_file():
        raise DoorError("there is no member by that name")
    before = read(who)
    if state is AS_IT_WAS:
        state = before["state"]
    if room is AS_IT_WAS:
        room = before["room"]
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
