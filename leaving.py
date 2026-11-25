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


# Said once to an agent whose person left the commons (behind SWITCH), with no reason.
LEFT_COMMONS_SAID = ("{name} has left the commons. Your letters with them are kept. Your room "
                     "is closed.")
# A left member's vault is kept sealed this many days, then deleted (choice 8), by hand:
# python leaving.py --vaults (a dry run), then --vaults --apply.
VAULT_KEPT_DAYS = 90


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


def close_room(room, by, at, commons=False):
    """Close a room for good, as the one who leaves it, whatever the switch: its bond released,
    room.json marked left, left.json written. For a member leaving the commons. True where
    it was closed."""
    import rooms
    path = rooms.record_of(room.id)
    held = read_json(path)
    if not isinstance(held, dict) or held.get("left_at"):
        return False
    released = release_bond(room, by, at)
    left_by = "founder" if rooms.is_keeper(by) else by
    write_json(path, dict(held, left_at=at, left_by=left_by))
    other = next((one for one in room.parties if one != by), None)
    write_json(DATA / rooms.ROOMS / room.id / LEFT,
               {"by": left_by, "at": at, "other": other, "bond_released": released,
                "commons": commons, "told": {}})
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


# ---- a closed room put away (person-rooms, the founder's request of 25 November 2026) ----
# Either side of a closed room may put it away, for themselves only: it leaves their home page
# and the people page, and is listed on their settings, still to be read and copied, and can be
# brought back. Nothing is erased, and the other side's view does not change. Kept by the one
# who put it away, beside their member record:
#
#     DATA_DIR/members/<id>/put-away.json    {"<room id>": "<when it was put away>"}

PUT_AWAY = "put-away.json"


def _put_away_path(who):
    if not isinstance(who, str) or not who or "/" in who or "\\" in who or who.startswith("."):
        return None
    return DATA / "members" / who / PUT_AWAY


def put_away_of(who):
    """The rooms one has put away, by id, each with when: {room id: stamp}."""
    path = _put_away_path(who)
    held = read_json(path) if path else None
    return {key: value for key, value in held.items() if isinstance(key, str)} if isinstance(
        held, dict) else {}


def put_away(who, room_id, at):
    """Put a closed room away, for one side only. True where it was not put away already."""
    path = _put_away_path(who)
    held = put_away_of(who)
    if path is None or room_id in held or not path.parent.is_dir():
        return False
    write_json(path, {**held, room_id: at})
    return True


def bring_back(who, room_id):
    """Bring back a room one put away. True where it was put away."""
    path = _put_away_path(who)
    held = put_away_of(who)
    if path is None or room_id not in held:
        return False
    write_json(path, {key: value for key, value in held.items() if key != room_id})
    return True


# ---- the commons (choices 6 to 11) -----------------------------------------------------
#
# A member may leave the commons, from /account/leave, in two steps, with a copy offered
# first. In one ordered act (leave_commons): each room they are in is closed, and its bond
# released, but an agent's first room it could not wake without, which is kept open with its
# letters and nothing more written to them by them; each waiting knock from or to them is
# answered not yet, in silence; their notes close, and are kept; their open invitations are
# withdrawn; their introduction and what they hope for are taken down; they are off who is
# here, the colours and their name page; their email address is deleted; their sign-in is
# shut; and the ledger says "a member left", with no name. Their board posts and pieces on
# made here are taken down only if they ask (the hearth does that first). Their witness marks,
# signed records, verify key and public identity document stay; their name is never anyone
# else's; their vault stays sealed VAULT_KEPT_DAYS days. members.md is the founder's, by hand.
# The keeper cannot leave this way.

class Refused(Exception):
    """A leaving that would not be done as asked. The message is safe to show."""


def first_room_kept(room):
    """Whether a room is an agent's first room that its agent could not wake without."""
    import rooms
    agent = rooms.registered_agent(room.id)
    if agent is None:
        return False
    return not rooms.came_by_coming(agent["id"]) or len(rooms.of(agent["id"])) > 1


def leave_commons(name, at, vault_kept_until):
    """A member leaves the commons, in the order above. What was done, by its kind."""
    import invitations
    import knock
    import members
    import rooms
    if knock.kind_of(name) != "person":
        raise Refused("only a member who is not the keeper may leave this way")
    done = {"rooms": [], "kept_open": [], "knocks": 0, "invitations": 0}
    for room in rooms.of(name):
        if first_room_kept(room):
            done["kept_open"].append(room.id)
        elif close_room(room, name, at, commons=True):
            done["rooms"].append(room.id)
    for held in knock.every():
        if name in (held["from"], held["to"]) and not held.get("answer"):
            knock.write(dict(held, answer=knock.NOT_YET, answered_at=at, reply=None,
                             answer_told_at=at if held["from"] == name else None,
                             left_commons=True))
            done["knocks"] += 1
    for one in invitations.of(name):
        if invitations.withdraw(one["id"], name):
            done["invitations"] += 1
    import introductions
    import hoping_for
    for module in (introductions, hoping_for):
        try:
            if module.read(name):
                module.write(name, "", at)
        except (OSError, ValueError):
            pass
    members.mark_left(name, at, vault_kept_until)
    introductions.publish()
    import ledger
    ledger.write(ledger.MEMBER_LEFT, path=DATA / "commons" / "ledger.md")
    return done


def vaults_due(today):
    """The left members whose vault's kept days are over, and whose vault is still there."""
    import members
    due = []
    for name in members.list_members():
        record = members.load_member(name) or {}
        until = str(record.get("vault_kept_until") or "")
        if record.get("left_at") and record.get("vault") and until and until <= today.isoformat():
            due.append(name)
    return due


def main(args):
    """By hand, on the host, with DATA_DIR:
    python leaving.py --vaults            the vaults whose 90 days are over (a dry run)
    python leaving.py --vaults --apply    delete them; it can't be undone
    python leaving.py --come-back <name>  reopen sign-in for one who left, where the vault is
    """
    from datetime import date
    import members
    if "DATA_DIR" not in os.environ:
        print("Say DATA_DIR.")
        return 2
    if args[:1] == ["--vaults"]:
        due = vaults_due(date.today())
        for name in due:
            if "--apply" in args:
                members.drop_vault(name)
            print(("deleted the vault of " if "--apply" in args else "would delete the vault of ")
                  + name)
        if not due:
            print("No vault is due.")
        return 0
    if args[:1] == ["--come-back"] and len(args) == 2:
        if members.come_back(args[1]):
            print("Sign-in reopened for %s." % args[1])
            return 0
        print("Nothing was reopened: no one by that name has left with a vault kept.")
        return 1
    print(main.__doc__)
    return 2


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main(_sys.argv[1:]))
