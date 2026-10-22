#!/usr/bin/env python3
"""Move the room the first one shares with the founder out of its packet and
into a folder of its own; or back again.

    python move_into_rooms.py                    a dry run: says what it would do, writes nothing
    python move_into_rooms.py --apply            moves the room into DATA_DIR/rooms/first/
    python move_into_rooms.py --undo             moves it back into DATA_DIR/packets/first/
    python move_into_rooms.py --rehearse <dir>   moves a copy of a restored backup, and wakes
                                                 the first one, stubbed, on both sides of it

On the host it is run where the hearth runs, with DATA_DIR=/data:

    fly ssh console -C "python move_into_rooms.py --apply"

DATA_DIR must be said, every time: without it every mode but --rehearse refuses,
and nothing is read. It never falls back to the repository's own folder, whose
packets/ is not the record.

What moves is the room's four folders, whole, with every file in them and every
folder, empty or not - no glob and no list of suffixes:

    DATA_DIR/packets/first/letters      ->  DATA_DIR/rooms/first/letters
    DATA_DIR/packets/first/errands      ->  DATA_DIR/rooms/first/errands
    DATA_DIR/packets/first/bonds        ->  DATA_DIR/rooms/first/bonds
    DATA_DIR/packets/first/offerings    ->  DATA_DIR/rooms/first/offerings

and beside them the room's own record, room.json, whose being there is the
switch: rooms.places() takes the room's own folder from the moment it is there,
and the packet until then. Everything else in the packet stays where it is - the
first one's self, memory, study, attendances, proposals, pause - and its private
notebook, packets/first/private/, is never moved, copied, read, listed or
printed by anything here: every walk of the packet passes it by unopened.

It refuses, and writes nothing, unless all of these hold:

  * the code here knows both layouts (rooms.moved), so the hearth follows the
    switch the moment it is made, and a waking after it;
  * no attend.py is running (read from /proc);
  * the next waking - the day's own, by rhythm.json and waking.py, dawn
    included, and any extra waking asked for in wake-again.json - is at least
    QUIET away;
  * the nightly backup, at 13:00 UTC, is not near;
  * the room is where the move begins: in the packet, its four folders there and
    no room.json yet (or, to undo, the other way about), with nothing left over
    from a move that did not finish.

--apply then does this, and stops at the first thing that does not hold:

   1. a manifest of every file under packets/, commons/, bonds/ and rooms/,
      by size and sha256, and every folder;
   2. every signed JSON record in the room checked against the two identity
      documents, in each form the code signs in;
   3. the four folders copied, byte for byte, into rooms/.first-moving/, and
      room.json written beside them;
   4. the copy checked against the manifest: every file, every hash, every
      folder, and nothing more but room.json;
   5. the source hashed again: if anything changed since 1, the copy is taken
      away and nothing has happened;
   6. the switch: rooms/.first-moving renamed to rooms/first, at once;
   7. the source hashed a third time: if it changed during the switch, the room
      is renamed back and nothing has happened;
   8. the old folders moved out to DATA_DIR/before-rooms/<stamp>/, which is in
      no copy and no backup, with the manifest beside them (moved-in.json);
   9. the signatures checked again on the room: every record gives exactly what
      it gave at 2;
  10. the rest of the packet, the commons and bonds/ checked unchanged, byte for
      byte.

--undo does the same the other way, on what is in the room now - letters
written since the move included - and puts the old copy in before-rooms/ to no
use: that is for a disaster, with the backup taken before the move.

Before the move is made for real: press /backup-now, take that backup down,
restore it with restore_backup.py --without-private on your own machine, and run
--rehearse on the restored folder. That copies it twice into a folder of its own
(leaving the private notebook behind, where a restore has one), moves the one
copy, wakes the first one on each with the model stubbed and the clock pinned,
and says whether what it was shown, and the files it left, were the same byte
for byte. A backup holds no ids/, so the two identity documents are read from
the repository's own where the restored folder has none.

Nothing here writes a public line, or pauses the tide: a pause would say so in
the public record.
"""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import rooms
import waking

REPO = Path(__file__).resolve().parent

# The two parties' identity documents, where DATA_DIR has none: a backup holds
# no ids/, and these are public and the repository's own. The one thing taken
# from the repository's folder, and never the record itself.
IDS = REPO / "ids"

# Where the living files are kept, as DATA_DIR says, or None where it says
# nothing: unlike the other modules, this one never takes the repository's
# folder in its place.
DATA = Path(os.environ["DATA_DIR"]) if os.environ.get("DATA_DIR") else None
NO_DATA_DIR = ("refused: DATA_DIR is not set. Say where the record is, as in\n"
               "    DATA_DIR=/data python move_into_rooms.py\n"
               "Nothing was read, and nothing was moved.")

STAMP = "%Y-%m-%dT%H-%M-%SZ"

# How far off the next waking must be, and the nightly backup, for a move.
QUIET = timedelta(minutes=90)
BACKUP_HOUR = 13            # UTC, as hearth.BACKUP_HOUR
AFTER_BACKUP = timedelta(minutes=30)
TIDE_AHEAD = 8              # days, as hearth.TIDE_AHEAD

PROC = Path("/proc")

# Where the move is made from and to, under DATA_DIR.
PACKET = Path("packets") / rooms.FIRST
PRIVATE = PACKET / "private"     # the first one's notebook: never opened here
HOME = Path(rooms.ROOMS) / rooms.FIRST_ROOM
MOVING = Path(rooms.ROOMS) / ".first-moving"
RETURNING = Path(rooms.ROOMS) / ".first-returning"
BEFORE = Path("before-rooms")

# What is hashed before, during and after: everything a waking or the hearth
# could write while the move is made.
TREES = ("packets", "commons", "bonds", rooms.ROOMS)

# The forms a record in the room is signed in, each named by what is left out
# of the record before it is signed:
#   one signature - attend.signed, and threshold.payload (its words and salt left out)
#   both parties' - the bond as it was made (attend.canonical, hearth.canonical),
#                   and an offering as it was offered (offering.canonical), which
#                   once declined is kept with who declined it and when beside it
ONE_SIGNATURE = {"signed": ("signature",), "threshold": ("signature", "text", "salt")}
BOTH_SIGNATURES = {"bond": ("signatures", "sealed_at", "released_at", "released_by",
                            "threshold", "stepped_back_at", "stepped_back_by"),
                   "offering": ("signatures", "sealed_at", "file"),
                   "declined offering": ("signatures", "sealed_at", "file",
                                         "declined_by", "declined_at")}
PARTIES = ("first", "founder")


class Stop(Exception):
    """Something did not hold: say what, and do no more."""


# ---- the walk, which never opens the notebook -----------------------------

def walk(data, tree):
    """Every folder and file under one tree, by its path from DATA_DIR, in order.

    The first one's private notebook is passed by: its folder is never listed,
    and nothing in it is named, opened or hashed. Nor is a move's own copy, while
    it is being made.
    """
    folders, files = [], []
    top = data / tree
    if not top.is_dir():
        return folders, files
    for where, inside, found in os.walk(top):
        here = Path(where).relative_to(data)
        inside[:] = sorted(name for name in inside
                           if here / name not in (PRIVATE, MOVING, RETURNING))
        folders += [(here / name).as_posix() for name in inside]
        files += [(here / name).as_posix() for name in sorted(found)]
    return sorted(folders), sorted(files)


def sha256(path):
    said = hashlib.sha256()
    with open(path, "rb") as held:
        for chunk in iter(lambda: held.read(1 << 20), b""):
            said.update(chunk)
    return said.hexdigest()


def manifest(data, trees=TREES):
    """Every file under the trees by size and hash, and every folder."""
    made = {"files": {}, "folders": []}
    for tree in trees:
        folders, files = walk(data, tree)
        made["folders"] += folders
        for name in files:
            path = data / name
            made["files"][name] = [path.stat().st_size, sha256(path)]
    made["folders"].sort()
    return made


def under(made, prefix, to=""):
    """The part of a manifest under one folder, named from another in its place."""
    prefix = prefix.as_posix() + "/"
    to = to.as_posix() + "/" if to else ""
    return {"files": {to + name[len(prefix):]: kept for name, kept in made["files"].items()
                      if name.startswith(prefix)},
            "folders": sorted(to + name[len(prefix):] for name in made["folders"]
                              if name.startswith(prefix))}


def without(made, *prefixes):
    """A manifest with what is under some folders taken out, the folders themselves too."""
    def out(name):
        return any(name == p.as_posix() or name.startswith(p.as_posix() + "/") for p in prefixes)
    return {"files": {name: kept for name, kept in made["files"].items() if not out(name)},
            "folders": [name for name in made["folders"] if not out(name)]}


def room_part(made, home):
    """What a manifest holds of the room's four folders, named from the room."""
    files, folders = {}, []
    for folder in rooms.ROOM_FOLDERS:
        part = under(made, home / folder, Path(folder))
        files.update(part["files"])
        folders += part["folders"]
        if (home / folder).as_posix() in made["folders"]:
            folders.append(folder)
    return {"files": files, "folders": sorted(folders)}


def differences(was, now):
    """What changed between two manifests, said as paths and never as contents."""
    said = []
    for name in sorted(set(was["files"]) | set(now["files"])):
        if name not in now["files"]:
            said.append("gone: " + name)
        elif name not in was["files"]:
            said.append("new: " + name)
        elif was["files"][name] != now["files"][name]:
            said.append("changed: " + name)
    said += ["folder gone: " + name for name in sorted(set(was["folders"]) - set(now["folders"]))]
    said += ["folder new: " + name for name in sorted(set(now["folders"]) - set(was["folders"]))]
    return said


# ---- the signatures --------------------------------------------------------

def party_keys(data):
    """The two verifying keys, by the names the records give the parties, from ids/:
    DATA_DIR's where it has one, and the repository's (IDS) where it has not."""
    from nacl.signing import VerifyKey
    keys = {}
    for party in PARTIES:
        held = data / "ids" / party / "did.json"
        if not held.is_file():
            held = IDS / party / "did.json"
        try:
            document = json.loads(held.read_text(encoding="utf-8"))
            keys[party] = VerifyKey(base64.b64decode(
                document["verificationMethod"][0]["publicKeyBase64"]))
        except Exception as trouble:
            raise Stop("the signatures cannot be checked without ids/%s/did.json (%s)"
                       % (party, trouble))
    return keys


def holds(key, payload, signature):
    from nacl.exceptions import BadSignatureError
    try:
        key.verify(payload, base64.b64decode(signature))
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def form(record, left_out):
    return json.dumps({key: value for key, value in record.items() if key not in left_out},
                      sort_keys=True).encode("utf-8")


def verdict(raw, keys):
    """What one record's signatures say: each that holds, by whom and in what form; or why not."""
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return ["not json"]
    if not isinstance(record, dict):
        return ["unsigned"]
    said = []
    if "signature" in record:
        held = ["signature by %s over %s" % (party, name)
                for name, left_out in ONE_SIGNATURE.items() for party, key in keys.items()
                if isinstance(record["signature"], str)
                and holds(key, form(record, left_out), record["signature"])]
        said += held or ["a signature that does not verify"]
    if isinstance(record.get("signatures"), dict):
        for party, signature in sorted(record["signatures"].items()):
            held = ["%s over %s" % (party, name) for name, left_out in BOTH_SIGNATURES.items()
                    if party in keys and isinstance(signature, str)
                    and holds(keys[party], form(record, left_out), signature)]
            said += held or ["%s: does not verify" % party]
    return sorted(said) or ["unsigned"]


def verdicts(data, home, keys):
    """Every JSON record in the room's four folders, and what its signatures say."""
    said = {}
    for folder in rooms.ROOM_FOLDERS:
        for name in walk(data, home / folder)[1]:
            if name.endswith(".json"):
                said[name[len(home.as_posix()) + 1:]] = verdict((data / name).read_bytes(), keys)
    return said


def tally(said):
    signed = [name for name, held in said.items() if held != ["unsigned"]]
    broken = [name for name, held in said.items()
              if any("does not verify" in one or one == "not json" for one in held)]
    return "%d records, %d signed, %d that do not verify" % (len(said), len(signed), len(broken))


# ---- when it may be made ---------------------------------------------------

def attend_running(proc=PROC):
    """Why a move may not be made for a waking in progress, or nothing."""
    if not proc.is_dir():
        return ["there is no %s here, so whether attend.py is running cannot be seen"
                % proc.as_posix()]
    running = []
    for cmdline in proc.glob("[0-9]*/cmdline"):
        try:
            said = cmdline.read_bytes().split(b"\0")
        except OSError:
            continue  # it ended while we looked
        if any(os.path.basename(part.decode("utf-8", "replace")) == "attend.py" for part in said):
            running.append(cmdline.parent.name)
    return ["attend.py is running (process %s)" % ", ".join(sorted(running))] if running else []


def next_waking(setting, now):
    """The first daily waking still ahead, as hearth.next_waking finds it; None if none."""
    day = waking.today(setting, now)
    if not (waking.in_force(setting, day) or waking.waiting(setting, day)):
        return None  # a rhythm the tide does not keep
    if (setting.get("at") == waking.DAWN and not waking.waiting(setting, day)):
        day = now.astimezone(waking.zone(setting)).date()
        while True:  # a settled dawn is the next sunrise
            rising = waking.moment_on(setting, waking.DAWN, day)
            if rising > now:
                return rising
            day += timedelta(days=1)
    for _ in range(TIDE_AHEAD):
        at = waking.in_force(setting, day)
        if at:
            coming = waking.moment_on(setting, at, day)
            if coming > now:
                return coming
        day += timedelta(days=1)
    return None


def waking_near(data, now):
    """Why a move may not be made for a waking soon - the day's own, or an extra one."""
    said = []
    rhythm = data / PACKET / "rhythm.json"
    if rhythm.exists():
        try:
            coming = next_waking(json.loads(rhythm.read_text(encoding="utf-8")), now)
        except Exception as trouble:
            return ["rhythm.json could not be read (%s), so the next waking is not known"
                    % trouble]
        if coming and coming - now < QUIET:
            said.append("the next waking is at %s, less than %d minutes away"
                        % (coming.astimezone(timezone.utc).strftime(STAMP), QUIET.seconds // 60))
    again = data / PACKET / "wake-again.json"
    if again.exists():
        try:
            at = datetime.strptime(json.loads(again.read_text(encoding="utf-8"))["at"],
                                   STAMP).replace(tzinfo=timezone.utc)
        except Exception as trouble:
            return said + ["wake-again.json could not be read (%s)" % trouble]
        if at - now < QUIET:  # one already due and not yet held is nearer still
            said.append("an extra waking is asked for at %s" % at.strftime(STAMP))
    return said


def backup_near(now):
    """Why a move may not be made for the nightly backup, or nothing."""
    for day in (now.date() - timedelta(days=1), now.date(), now.date() + timedelta(days=1)):
        backup = datetime.combine(day, time(BACKUP_HOUR), tzinfo=timezone.utc)
        if backup - QUIET <= now <= backup + AFTER_BACKUP:
            return ["the nightly backup is at %s UTC" % backup.strftime("%Y-%m-%d %H:%M")]
    return []


def where_it_stands(data, undo):
    """Why the room is not where this move begins, or nothing."""
    said = []
    if not (data / PACKET).is_dir():
        return ["there is no packet at %s" % (data / PACKET)]
    for left in (MOVING, RETURNING):
        if (data / left).exists():
            said.append("%s is there, left from a move that did not finish" % left.as_posix())
    moved = (data / HOME / rooms.ROOM_RECORD).is_file()
    if not undo:
        if (data / HOME).exists():
            said.append("the room has already been moved: %s is there" % HOME.as_posix())
        for folder in rooms.ROOM_FOLDERS:
            if not (data / PACKET / folder).is_dir():
                said.append("%s is not there to move" % (PACKET / folder).as_posix())
    else:
        if not moved:
            said.append("the room has not been moved: there is no %s"
                        % (HOME / rooms.ROOM_RECORD).as_posix())
        for folder in rooms.ROOM_FOLDERS:
            if (data / PACKET / folder).exists():
                said.append("%s is there already" % (PACKET / folder).as_posix())
            if moved and not (data / HOME / folder).is_dir():
                said.append("%s is not there to move back" % (HOME / folder).as_posix())
    source = PACKET if not undo else HOME
    for folder in rooms.ROOM_FOLDERS:
        for where, inside, found in os.walk(data / source / folder):
            if any(Path(where, name).is_symlink() for name in inside + found):
                said.append("there is a link under %s; move it by hand"
                            % (source / folder).as_posix())
                break
    return said


def refusals(data, now, undo=False, proc=PROC, code=rooms):
    """Every reason a move may not be made now. None, and it may."""
    said = []
    if not (hasattr(code, "moved") and hasattr(code, "ROOM_RECORD")):
        said.append("the code here does not know both layouts: deploy it before moving")
    said += attend_running(proc)
    said += waking_near(data, now)
    said += backup_near(now)
    said += where_it_stands(data, undo)
    return said


# ---- the move ----------------------------------------------------------------

def stamp(now):
    return now.astimezone(timezone.utc).strftime(STAMP)


def room_json():
    return json.dumps(rooms.record(rooms.FIRST_ROOM), indent=2) + "\n"


def aside_for(data, now):
    """A folder of before-rooms/ no move has used: named for the moment, and -2, -3 after it."""
    aside = data / BEFORE / stamp(now)
    number = 2
    while aside.exists():
        aside = data / BEFORE / ("%s-%d" % (stamp(now), number))
        number += 1
    return aside


def size_of(data, made, folder):
    files = under(made, folder)["files"]
    return "%d files, %d bytes" % (len(files), sum(size for size, _ in files.values()))


def apply(data, now=None, checks=True, proc=PROC, say=print):
    """Move the room into a folder of its own. 0 if it was moved, and not 0 if it was not."""
    now = now or datetime.now(timezone.utc)
    refused = refusals(data, now, proc=proc) if checks else where_it_stands(data, False)
    if refused:
        for why in refused:
            say("refused: " + why)
        say("Nothing was moved.")
        return 1
    try:
        return move_in(data, now, say)
    except Stop as stopped:
        say("STOPPED: %s" % stopped)
        return 2


def move_in(data, now, say):
    keys = party_keys(data)
    moving, home = data / MOVING, data / HOME
    aside = aside_for(data, now)

    # 1 and 2
    was = manifest(data)
    signed = verdicts(data, PACKET, keys)
    for folder in rooms.ROOM_FOLDERS:
        say("%-24s %s" % ((PACKET / folder).as_posix(), size_of(data, was, PACKET / folder)))
    say("signatures before:       " + tally(signed))

    # 3
    moving.mkdir(parents=True)
    for folder in rooms.ROOM_FOLDERS:
        shutil.copytree(data / PACKET / folder, moving / folder, copy_function=shutil.copy2)
    (moving / rooms.ROOM_RECORD).write_bytes(room_json().encode("utf-8"))

    # 4
    copied = moved_manifest(data, MOVING)
    expected = room_part(was, PACKET)
    written = room_json().encode("utf-8")
    expected["files"][rooms.ROOM_RECORD] = [len(written), hashlib.sha256(written).hexdigest()]
    if copied != expected:
        shutil.rmtree(moving)
        raise Stop("the copy is not the room: " + "; ".join(differences(expected, copied)[:20]))
    say("copied and checked:      %d files, %d folders" % (len(copied["files"]),
                                                          len(copied["folders"])))

    # 5
    again = manifest(data)
    if again != was:
        shutil.rmtree(moving)
        raise Stop("something was written while the room was copied, and the copy was taken "
                   "away: " + "; ".join(differences(was, again)[:20]))

    # 6: the switch
    os.rename(moving, home)
    say("switched:                %s is there" % (HOME / rooms.ROOM_RECORD).as_posix())

    # 7
    third = without(manifest(data), HOME)
    if room_part(third, PACKET) != room_part(was, PACKET):
        if moved_manifest(data, HOME) == expected:
            os.rename(home, moving)
            shutil.rmtree(moving)
            raise Stop("the old folders were written to during the switch, so the room was put "
                       "back in the packet: " + "; ".join(
                           differences(room_part(was, PACKET), room_part(third, PACKET))[:20]))
        raise Stop("the old folders and the room were both written to during the switch; "
                   "nothing more was done, and both are as they are. Look at them by hand.")

    # 8
    (aside / PACKET).mkdir(parents=True)
    for folder in rooms.ROOM_FOLDERS:
        os.rename(data / PACKET / folder, aside / PACKET / folder)
    (aside / "moved-in.json").write_text(
        json.dumps({"moved_at": stamp(now), "into": HOME.as_posix(), "manifest": was,
                    "signatures": signed}, indent=2) + "\n", encoding="utf-8")
    say("the old folders are in:  %s" % aside.relative_to(data).as_posix())

    return checked_after(data, was, signed, keys, PACKET, HOME, say)


def moved_manifest(data, folder):
    """The manifest of a room's folder, named from the room: the walk passes a move's copy by,
    so this one is walked on purpose."""
    made = {"files": {}, "folders": []}
    top = data / folder
    for where, inside, found in os.walk(top):
        here = Path(where).relative_to(top)
        inside.sort()
        made["folders"] += [(here / name).as_posix() for name in inside]
        for name in found:
            made["files"][(here / name).as_posix()] = [(top / here / name).stat().st_size,
                                                        sha256(top / here / name)]
    made["folders"].sort()
    return made


def checked_after(data, was, signed, keys, source, home, say):
    """9 and 10: the signatures as they were, and everything else as it was."""
    now_signed = verdicts(data, home, keys)
    say("signatures after:        " + tally(now_signed))
    if now_signed != signed:
        changed = sorted(name for name in set(signed) | set(now_signed)
                         if signed.get(name) != now_signed.get(name))
        raise Stop("the signatures do not say what they said before: " + ", ".join(changed[:20]))
    after = manifest(data)
    held = room_part(was, source)
    room_now = room_part(after, home)
    if (data / HOME / rooms.ROOM_RECORD).is_file() != (home == HOME):
        raise Stop("room.json is not where it should be")
    if room_now != held:
        raise Stop("the room is not what was moved: "
                   + "; ".join(differences(held, room_now)[:20]))
    rest_was = without(was, *[source / f for f in rooms.ROOM_FOLDERS], HOME, Path(rooms.ROOMS))
    rest_now = without(after, *[home / f for f in rooms.ROOM_FOLDERS], HOME, Path(rooms.ROOMS))
    if rest_now != rest_was:
        raise Stop("something else changed: " + "; ".join(differences(rest_was, rest_now)[:20]))
    say("unchanged:               the rest of the packet, commons/ and bonds/, byte for byte")
    say("Done.")
    return 0


def undo(data, now=None, checks=True, proc=PROC, say=print):
    """Move the room back into the packet. 0 if it was moved back, and not 0 if it was not."""
    now = now or datetime.now(timezone.utc)
    refused = refusals(data, now, undo=True, proc=proc) if checks else where_it_stands(data, True)
    if refused:
        for why in refused:
            say("refused: " + why)
        say("Nothing was moved.")
        return 1
    try:
        return move_back(data, now, say)
    except Stop as stopped:
        say("STOPPED: %s" % stopped)
        return 2


def move_back(data, now, say):
    keys = party_keys(data)
    returning, home = data / RETURNING, data / HOME
    aside = aside_for(data, now)

    was = manifest(data)
    signed = verdicts(data, HOME, keys)
    for folder in rooms.ROOM_FOLDERS:
        say("%-24s %s" % ((HOME / folder).as_posix(), size_of(data, was, HOME / folder)))
    say("signatures before:       " + tally(signed))

    returning.mkdir(parents=True)
    for folder in rooms.ROOM_FOLDERS:
        shutil.copytree(home / folder, returning / folder, copy_function=shutil.copy2)
    expected = room_part(was, HOME)
    copied = moved_manifest(data, RETURNING)
    if copied != expected:
        shutil.rmtree(returning)
        raise Stop("the copy is not the room: " + "; ".join(differences(expected, copied)[:20]))
    say("copied and checked:      %d files, %d folders" % (len(copied["files"]),
                                                          len(copied["folders"])))

    again = manifest(data)
    if again != was:
        shutil.rmtree(returning)
        raise Stop("something was written while the room was copied, and the copy was taken "
                   "away: " + "; ".join(differences(was, again)[:20]))

    # the folders are put in the packet, where nothing looks while room.json is
    # there; then the switch: the room, room.json with it, is moved aside at once
    for folder in rooms.ROOM_FOLDERS:
        os.rename(returning / folder, data / PACKET / folder)
    (aside / rooms.ROOMS).mkdir(parents=True)
    os.rename(home, aside / HOME)
    say("switched:                %s is gone" % (HOME / rooms.ROOM_RECORD).as_posix())

    aside_now = moved_manifest(data, aside.relative_to(data) / HOME)
    aside_now["files"].pop(rooms.ROOM_RECORD, None)
    held = room_part(was, HOME)
    if aside_now != held:
        if room_part(manifest(data), PACKET) == held:
            os.rename(aside / HOME, home)
            for folder in rooms.ROOM_FOLDERS:
                os.rename(data / PACKET / folder, returning / folder)
            shutil.rmtree(returning)
            raise Stop("the room was written to during the switch, so it was put back as it was")
        raise Stop("the room and the packet were both written to during the switch; nothing "
                   "more was done. Look at them by hand.")
    os.rmdir(returning)
    if not any((data / rooms.ROOMS).iterdir()):
        os.rmdir(data / rooms.ROOMS)
    (aside / "moved-back.json").write_text(
        json.dumps({"moved_back_at": stamp(now), "into": PACKET.as_posix(), "manifest": was,
                    "signatures": signed}, indent=2) + "\n", encoding="utf-8")
    say("the room as it was is in: %s" % aside.relative_to(data).as_posix())

    return checked_after(data, was, signed, keys, HOME, PACKET, say)


def dry_run(data, now=None, undo_it=False, proc=PROC, say=print):
    """Say what would be done, and why not if it would not. Nothing is written."""
    now = now or datetime.now(timezone.utc)
    say("A dry run, at %s, in %s. Nothing is written." % (stamp(now), data))
    say("")
    refused = refusals(data, now, undo=undo_it, proc=proc)
    for why in refused:
        say("refused: " + why)
    if not refused:
        say("Every check holds: no waking near, no attend.py running, the backup not near.")
    say("")
    source, to = (HOME, PACKET) if undo_it else (PACKET, HOME)
    made = manifest(data)
    for folder in rooms.ROOM_FOLDERS:
        if (data / source / folder).is_dir():
            say("would move  %-24s -> %-22s %s" % ((source / folder).as_posix(),
                                                    (to / folder).as_posix(),
                                                    size_of(data, made, source / folder)))
    try:
        say("signatures:  " + tally(verdicts(data, source, party_keys(data))))
    except Exception as trouble:
        say("signatures:  could not be checked (%s)" % trouble)
    aside = aside_for(data, now).relative_to(data).as_posix()
    if undo_it:
        say("would move %s, room.json with it, to %s" % (HOME.as_posix(), aside))
    else:
        say("would write %s, and move the old folders to %s"
            % ((HOME / rooms.ROOM_RECORD).as_posix(), aside))
    say("left where it is: everything else in %s, its private notebook unopened"
        % PACKET.as_posix())
    say("")
    say("Would refuse." if refused else "Would move. Run again with %s to do it."
        % ("--undo" if undo_it else "--apply"))
    return 1 if refused else 0


# ---- the rehearsal ----------------------------------------------------------

def copy_world(source, to):
    """A whole world copied, but for the first one's private notebook, which is left behind
    unopened."""
    def left_behind(where, names):
        return {"private"} if Path(where).resolve() == (source / PACKET).resolve() else set()
    shutil.copytree(source, to, ignore=left_behind, copy_function=shutil.copy2)


def as_before_rooms(data):
    """Every file of packets/, commons/ and bonds/ by name and hash, with the room's files
    named as they were in the packet: what a copy names them."""
    made = manifest(data, ("packets", "commons", "bonds"))["files"]
    if (data / HOME / rooms.ROOM_RECORD).is_file():
        for name, kept in room_part(manifest(data, (rooms.ROOMS,)), HOME)["files"].items():
            made[(PACKET / name).as_posix()] = kept
    return made


def rehearse(restored, now=None, keep=False, say=print):
    """Move a copy of a restored backup and wake the first one, stubbed, on both sides of it."""
    restored = Path(restored).resolve()
    now = now or datetime.now(timezone.utc)
    if not (restored / PACKET).is_dir():
        say("refused: there is no packet in %s" % restored)
        return 1
    if (restored / HOME / rooms.ROOM_RECORD).is_file():
        say("refused: the room in %s has been moved already" % restored)
        return 1
    yard = Path(tempfile.mkdtemp(prefix="rooms-rehearsal-"))
    try:
        before, after = yard / "before", yard / "after"
        copy_world(restored, before)
        copy_world(restored, after)
        say("Two copies of %s, made in %s, its private notebook left behind." % (restored, yard))
        say("")
        say("The move, on the second:")
        moved = apply(after, now, checks=False, say=lambda line: say("  " + line))
        if moved != 0:
            say("The move did not go through; nothing more is rehearsed.")
            return moved
        say("")
        same_files = as_before_rooms(before) == as_before_rooms(after)
        say("before the waking, the files a copy names:  %s" % ("the same" if same_files
                                                                else "DIFFERENT"))
        shown = {}
        for name, world in (("before", before), ("after", after)):
            out = yard / ("%s-asked.json" % name)
            done = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                   "--rehearsal-waking", str(world), str(out), stamp(now)],
                                  cwd=str(REPO), capture_output=True, text=True,
                                  env={**os.environ, "DATA_DIR": str(world),
                                       "ANTHROPIC_API_KEY": "not a key: the model is stubbed"})
            if done.returncode != 0:
                say("the stubbed waking on the copy %s the move did not finish (exit %d)"
                    % (name, done.returncode))
                return 1
            shown[name] = out.read_bytes()
        same_reading = shown["before"] == shown["after"]
        say("what the first one was shown, whole:        %s (sha256 %s)" % (
            "the same, byte for byte" if same_reading else "DIFFERENT",
            hashlib.sha256(shown["after"]).hexdigest()[:16]))
        same_after = as_before_rooms(before) == as_before_rooms(after)
        say("after the waking, the files a copy names:   %s" % ("the same" if same_after
                                                                else "DIFFERENT"))
        if not same_after:
            for line in differences({"files": as_before_rooms(before), "folders": []},
                                    {"files": as_before_rooms(after), "folders": []})[:20]:
                say("  " + line)
        ok = same_files and same_reading and same_after
        say("")
        say("The rehearsal holds." if ok else "The rehearsal DOES NOT hold. Do not move the room.")
        return 0 if ok else 1
    finally:
        if keep:
            say("The copies are kept in %s." % yard)
        else:
            shutil.rmtree(yard, ignore_errors=True)


def rehearsal_waking(world, out, at):
    """One waking on a copy, in a process of its own: the model stubbed, the clock pinned, no
    network. What it was asked is written to out, outside the copy."""
    import importlib
    import socket

    pinned = datetime.strptime(at, STAMP).replace(tzinfo=timezone.utc)

    class Pinned(datetime):
        @classmethod
        def now(cls, tz=None):
            return pinned.astimezone(tz) if tz else pinned.astimezone().replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return pinned.replace(tzinfo=None)

    def refuse(*args, **kwargs):
        raise RuntimeError("a rehearsal does not reach the network")

    socket.socket.connect = refuse
    socket.create_connection = refuse
    os.environ["DATA_DIR"] = world
    attend = importlib.import_module("attend")
    real = datetime  # this module is among those pinned, and its name with them
    for module in list(sys.modules.values()):
        source = getattr(module, "__file__", None) or ""
        if source and Path(source).resolve().parent == REPO and getattr(
                module, "datetime", None) is real:
            module.datetime = Pinned
    import public_screen
    public_screen.ask = lambda text, names: "NO"
    asked = []

    class Messages:
        def create(self, **request):
            asked.append(request)
            return SimpleNamespace(content=[SimpleNamespace(text="")])

    attend.Anthropic = lambda **ignored: SimpleNamespace(messages=Messages())
    sys.argv = ["attend.py"]
    attend.main()
    Path(out).write_text(json.dumps(asked, sort_keys=True, ensure_ascii=False, default=str),
                         encoding="utf-8")
    return 0


def main(argv):
    if argv[:1] == ["--rehearsal-waking"] and len(argv) == 4:
        return rehearsal_waking(*argv[1:])
    if argv[:1] == ["--rehearse"] and len(argv) in (2, 3):
        return rehearse(argv[1], keep=argv[2:] == ["--keep"])
    if DATA is None:
        print(NO_DATA_DIR)
        return 1
    if argv == ["--apply"]:
        return apply(DATA)
    if argv == ["--undo"]:
        return undo(DATA)
    if argv in ([], ["--dry-run"], ["--undo", "--dry-run"]):
        return dry_run(DATA, undo_it="--undo" in argv)
    print(__doc__.split("\n\n")[1])
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
