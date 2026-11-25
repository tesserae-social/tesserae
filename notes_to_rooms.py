#!/usr/bin/env python3
"""Make the notes between two people the first letters of a room of their own (person-rooms,
the founder's request of 25 November 2026).

Since person-rooms a yes between two people opens a room of letters (rooms.PEOPLE_KIND) in
place of notes (notes.py). Each yes between two people that stood before then has no room. This
makes one for each, at the address rooms.address_for_people gives, and writes each note into it
as a letter, by its writer, at the moment it was written, oldest first. A yes with no notes gets
its room too, empty but for the knock and its answer at its top. The notes files are left as
they are: nothing in DATA_DIR/notes/ is changed or removed.

    python notes_to_rooms.py              a dry run: lists every room and letter, changes nothing
    python notes_to_rooms.py --apply      makes them, and keeps a record of each
    python notes_to_rooms.py --undo       takes away every room the record holds

Run it with DATA_DIR set, after the deploy that turns person-rooms on. --apply refuses unless an
encrypted backup was taken in the last FRESH_HOURS (backup.log, as move_to_ids.py reads it), and
while a record of an earlier run stands. Each knock is marked with its room, as any yes's room
is; the knock as it was is kept in the record. Both of the two are marked as having seen the
letters made, so no email tells them of old notes. Where one of the two has left the commons,
the room is made closed, as leaving closes a room, and neither is told of it again.

--undo refuses for a room with anything in it the run did not write (a letter written since):
it takes away only what it made, puts each knock back as it was, and unmarks what was seen.

The record is DATA_DIR/rooms/notes-to-rooms.json. It names the two of each room by the names
the stores keep them by, never by a sign-in name: the keeper is "founder".
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RECORD = "notes-to-rooms.json"
STAMP = "%Y-%m-%dT%H-%M-%SZ"


class Refused(Exception):
    """Nothing was changed."""


def data():
    return Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent))


def modules():
    """The project's modules, read now that DATA_DIR is set."""
    import knock
    import members
    import notes
    import rooms
    import found_room
    import leaving
    return knock, members, notes, rooms, found_room, leaving


def store(rooms, who):
    """One as the stores name them: "founder" for the keeper."""
    return "founder" if who == "founder" or rooms.is_keeper(who) else who


def plan():
    """Every yes between two people with no room yet: (knock, room address, letters, who left),
    each letter (writer as the stores name them, stamp, words), oldest first."""
    knock, members, notes, rooms, _, _ = modules()
    found, taken = [], set()
    for held in knock.every():
        if held.get("answer") != knock.YES or not knock.between_people(held):
            continue
        if held.get("room") or held.get("set_up_at"):
            continue
        one, other = held["from"], held["to"]
        address = rooms.address_for_people(one, other)
        while address in taken:  # two in one run with the same two names: the next number
            base, _, n = address.rpartition("-")
            address = "%s-%d" % (base, int(n) + 1) if n.isdigit() else address + "-2"
        taken.add(address)
        letters = [(store(rooms, note["from"]), note["at"], note["words"])
                   for note in notes.read(one, other)]
        gone = [who for who in (one, other) if members.has_left(who)]
        found.append({"knock": held, "room": address, "letters": letters, "left": gone})
    return found


def listed(found):
    lines = ["Each yes between two people gets a room; its notes become its first letters."]
    for one in found:
        held = one["knock"]
        lines.append("room     rooms/%s  (knock %s--%s, answered %s)%s" % (
            one["room"], held["from"], held["to"], held.get("answered_at"),
            "  closed: %s has left" % ", ".join(one["left"]) if one["left"] else ""))
        for by, at, words in one["letters"]:
            lines.append("letter   from-%s/%s-%s.md  (%d characters)" % (by, by, at, len(words)))
    if not found:
        lines.append("There is no yes between two people without a room.")
    lines.append("left     DATA_DIR/notes/ as it is: no notes file is changed or removed")
    return lines


def write_json(path, value):
    import safe_write
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def apply(now=None):
    import move_to_ids
    knock, members, _, rooms, found_room, _ = modules()
    root = data()
    now = now or datetime.now(timezone.utc)
    record_path = root / rooms.ROOMS / RECORD
    if record_path.exists():
        raise Refused("a run is recorded already (rooms/%s): undo it first" % RECORD)
    try:
        move_to_ids.fresh_backup(root, now)
    except move_to_ids.Refused as refused:
        raise Refused(str(refused))
    at = now.strftime(STAMP)
    done = {"at": at, "rooms": []}
    for one in plan():
        held = one["knock"]
        home = found_room.found_people(held["from"], held["to"], "%s--%s" % (
            knock.stores_name(held["from"]), knock.stores_name(held["to"])), at)
        if home.name != one["room"]:
            raise Refused("rooms/%s was made as %s; nothing more was made" % (one["room"],
                                                                              home.name))
        made = {"room": home.name, "knock": held, "files": [], "seen": []}
        done["rooms"].append(made)
        write_json(record_path, done)
        for by, stamp, words in one["letters"]:
            folder = home / "letters" / ("from-" + by)
            stem, n = "%s-%s" % (by, stamp), 2
            while (folder / (stem + ".md")).exists():
                stem, n = "%s-%s-%d" % (by, stamp, n), n + 1
            (folder / (stem + ".md")).write_text(words + "\n", encoding="utf-8")
            made["files"].append((folder / (stem + ".md")).relative_to(home).as_posix())
        newest = max((stamp for _, stamp, _ in one["letters"]), default=None)
        if newest:
            for who in (held["from"], held["to"]):
                members.mark_seen(who, home.name, newest)
                made["seen"].append(who)
        if one["left"]:  # closed, as leaving closes a room, and told to no one again
            gone = one["left"][0]
            record = read_json(home / rooms.ROOM_RECORD)
            write_json(home / rooms.ROOM_RECORD, dict(record, left_at=at,
                                                      left_by=store(rooms, gone)))
            write_json(home / "left.json", {
                "by": store(rooms, gone), "at": at, "other": None, "bond_released": False,
                "commons": True, "told": {who: at for who in (held["from"], held["to"])}})
            made["files"].append("left.json")
        knock.write(dict(held, set_up_at=at, room_made_at=at, room=home.name,
                         from_notes=True))
        write_json(record_path, done)
    write_json(record_path, done)
    return done


def undo():
    knock, members, _, rooms, _, _ = modules()
    root = data()
    record_path = root / rooms.ROOMS / RECORD
    done = read_json(record_path)
    if not isinstance(done, dict):
        raise Refused("there is no run recorded to undo")
    for made in done.get("rooms") or []:
        home = root / rooms.ROOMS / made["room"]
        if not home.is_dir():
            continue
        ours = set(made["files"]) | {rooms.ROOM_RECORD}
        extra = [path.relative_to(home).as_posix() for path in home.rglob("*")
                 if path.is_file() and path.relative_to(home).as_posix() not in ours]
        if extra:
            raise Refused("rooms/%s holds what this run did not write (%s); nothing was undone"
                          % (made["room"], ", ".join(sorted(extra))))
    for made in reversed(done.get("rooms") or []):
        held = made["knock"]
        now = knock.read(held["from"], held["to"])
        if now is not None and now.get("room") == made["room"]:
            knock.write(held)
        for who in made.get("seen") or []:
            path = root / "members" / who / members.SEEN
            seen = read_json(path)
            if isinstance(seen, dict) and made["room"] in seen:
                write_json(path, {key: value for key, value in seen.items()
                                  if key != made["room"]})
        home = root / rooms.ROOMS / made["room"]
        if home.is_dir():
            shutil.rmtree(home)
    record_path.unlink()
    return done


def main(argv=None):
    parser = argparse.ArgumentParser(description="Make notes between people into rooms.")
    parser.add_argument("--apply", action="store_true", help="make the rooms")
    parser.add_argument("--undo", action="store_true", help="take away the rooms recorded")
    args = parser.parse_args(argv)
    if "DATA_DIR" not in os.environ:
        print("Say DATA_DIR.")
        return 2
    try:
        if args.undo:
            done = undo()
            print("Undone: %d rooms taken away, and their knocks put back as they were."
                  % len(done.get("rooms") or []))
            return 0
        print("\n".join(listed(plan())))
        if not args.apply:
            print("A dry run: nothing was changed. Run again with --apply to make the rooms.")
            return 0
        done = apply()
        print("Done: %d rooms made. The record is rooms/%s. The notes files are as they were."
              % (len(done["rooms"]), RECORD))
        return 0
    except Refused as refused:
        print("Refused:", refused)
        return 1


if __name__ == "__main__":
    sys.exit(main())
