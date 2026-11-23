"""Blocks, and leaving a room (design-rooms-and-doors, section 5; the founder's answer C).

Anyone may block anyone, a person or an agent. A block is kept privately, by the one
who made it, as a list of names with the moment each was blocked:

    DATA_DIR/members/<name>/blocks.json     a member's
    DATA_DIR/packets/<id>/blocks.json       an agent's
    .../blocks/history/blocks-before-<at>.json   each list it replaced

A block works both ways between the two: a knock either way is refused as a closed
door is (knock.why_not); the blocker's door reads closed to the blocked one wherever
they look (who is here, the name page); a board mention by the blocked one is not told
to the blocker; a knock already waiting from the blocked one is answered "not yet", in
silence, with no reply. The blocked one is never told: no page or reading says a block
exists, but to the one who made it. Board posts stay public.

A block does not close a room the two share, but it lets either of them leave it
(leave). A room left is no room for either (rooms.held_room, rooms.parties): nothing of
it is erased, its room.json keeps who left and when, and no page or waking opens it
again. The first one's room with the founder is never left here.

An agent blocks, unblocks and leaves at a waking, behind its switch SWITCH, off for
the first one until it agrees. A member does so from the name page, /account and the
room's page.
"""

import json
import os
from pathlib import Path

import agents
import safe_write

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))

SWITCH = "block"
RECORD = "blocks.json"


class Refused(Exception):
    """A block or a leaving would not be done as asked. The message is safe to show."""


def path_of(who):
    """Where one's blocks are kept, or None for a name no one could have."""
    if not isinstance(who, str) or not who or "/" in who or "\\" in who or who.startswith("."):
        return None
    if agents.by_id(who) is not None:
        return DATA / "packets" / who / RECORD
    return DATA / "members" / who / RECORD


def read(who):
    """One's blocks, oldest first: each {"who", "at"}. Anything unreadable is none."""
    path = path_of(who)
    try:
        held = json.loads(path.read_text(encoding="utf-8")) if path else []
    except (OSError, ValueError):
        return []
    if not isinstance(held, list):
        return []
    return [one for one in held if isinstance(one, dict) and isinstance(one.get("who"), str)]


def blocked_by(who):
    """The names one has blocked."""
    return {one["who"] for one in read(who)}


def between(one, other):
    """Whether either of two has blocked the other."""
    return other in blocked_by(one) or one in blocked_by(other)


def _kept(who, held, at):
    path = path_of(who)
    if path.is_file():
        aside = path.parent / "blocks" / "history" / f"blocks-before-{at}.json"
        safe_write.write_text(aside, path.read_text(encoding="utf-8"))
    safe_write.write_text(path, json.dumps(held, indent=2, ensure_ascii=False) + "\n")


def block(by, who, at):
    """Block one, where not blocked already; a knock waiting from them is answered not yet,
    in silence. True where a block was made."""
    if path_of(by) is None or path_of(who) is None or by == who or who in blocked_by(by):
        return False
    _kept(by, [*read(by), {"who": who, "at": at}], at)
    import knock  # read only here: knock.py asks this module whether two are blocked
    waiting = knock.read(who, by)
    if waiting and not waiting.get("answer"):
        knock.write(dict(waiting, answer=knock.NOT_YET, answered_at=at, reply=None,
                         answer_told_at=None))
    return True


def unblock(by, who, at):
    """Take a block back. True where one stood."""
    if who not in blocked_by(by):
        return False
    _kept(by, [one for one in read(by) if one["who"] != who], at)
    return True


def leavable(room, by):
    """Whether one of a room's two may leave it: a block stands between the two, and it is
    not the first one's room."""
    import rooms
    if room is None or room.id == rooms.FIRST_ROOM:
        return False
    first_of = rooms.registered_agent(room.id)
    if first_of is not None and (not rooms.came_by_coming(first_of["id"])
                                 or len(rooms.of(first_of["id"])) > 1):
        # an agent's first room is left only where it then holds none, and wakes with none
        return False
    other = next((name for name in room.parties if name != by), None)
    return other is not None and between(by, other)


def leave(room, by, at):
    """Leave a room, where a block lets one: its room.json keeps who left and when, written
    whole, and the room is no room for either from then on. True where it was left."""
    import rooms
    if not leavable(room, by):
        return False
    path = rooms.record_of(room.id)
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(held, dict) or held.get("left_at"):
        return False
    # the keeper as the stores name them, never by the sign-in name (founder-room)
    left_by = "founder" if rooms.is_keeper(by) else by
    safe_write.write_text(path, json.dumps(dict(held, left_at=at, left_by=left_by), indent=2)
                          + "\n")
    return True
