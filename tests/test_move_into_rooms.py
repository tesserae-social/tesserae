"""Moving the room out of the first one's packet and into a folder of its own.

move_into_rooms.py moves the four folders the room keeps - letters, errands,
bonds, offerings - whole, from DATA_DIR/packets/first/ to DATA_DIR/rooms/first/,
and writes room.json beside them; or moves them back. Held here:

  * what it refuses, and that a refusal writes nothing; that a dry run writes
    nothing at all;
  * that it moves everything and nothing more, byte for byte, with every
    signature saying after what it said before; that it stops, and leaves the
    room where it was, when something is written while it works;
  * that apply and then undo gives back the tree exactly, and an undo keeps
    what was written in the room since;
  * that the first one's private notebook is never moved, copied, opened,
    listed or printed by it;
  * that, on a world with everything in it, the hearth shows the same pages and
    hands out the same copy before and after the move, and that what is written
    after the move lands in the room; and that a rehearsal on such a world finds
    the first one shown the same thing, byte for byte, on both sides of it;
  * that a room with no errands/ and no offerings/, or with them empty, is no
    reason to refuse: what is missing is made empty in the room, said and
    recorded, and an undo takes it away again; and that a rehearsal holds on a
    restored backup, which keeps no empty folder.

A move always begins from the packet, so every world here starts in the old
layout, whichever layout the suite was run in.
"""

import ast
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import (FOUNDER_NAME, NOTEBOOK_WORDS, PASSWORD, Turn, a_private_notebook, block,
                      load, page, post, read_json, write, write_json)
from test_backup import KEY as BACKUP_KEY, Bucket, set_variables
from test_hearth_bonds import sealed
from test_offerings import offer, photo_bytes
from test_proposals import proposed

import move_into_rooms as mir

MOVE_SCRIPT = Path(mir.__file__).resolve()

# A moment when a move may be made: the first one wakes at 06:00 its time, which
# is 10:00 UTC in October, and the backup is at 13:00 UTC.
QUIET = datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)
RHYTHM = {"rhythm": "daily", "at": "06:00", "place": "Indianapolis",
          "timezone": "America/Indiana/Indianapolis", "set_at": "2026-10-01T09-00-00Z",
          "effective_from": "2026-10-02", "until_then": "dawn"}
# the next of those wakings after QUIET
NEXT_WAKING = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
MOVED_AT = QUIET.strftime("%Y-%m-%dT%H-%M-%SZ")

ROOM_FOLDERS = ("letters", "errands", "bonds", "offerings")

OPEN_ERRAND = "errand-2026-10-06T09-00-00Z"
PHOTO_JPG = "founder-2026-10-01T09-00-00Z"
PHOTO_JFIF = "founder-2026-10-03T09-00-00Z"
PICTURE = "to-founder-2026-10-02T09-00-00Z"
DRAWN = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
         '<rect width="10" height="10" fill="#c85a30"/></svg>\n')


@pytest.fixture
def layout():
    """A move begins where the room has always been kept: in the packet."""
    return "legacy"


@pytest.fixture
def proc(tmp_path):
    """A /proc of its own, with a hearth running in it and no waking."""
    held = tmp_path / "proc"
    write(held / "41" / "cmdline", "")
    (held / "41" / "cmdline").write_bytes(b"/usr/local/bin/gunicorn\0hearth:app\0")
    (held / "self").mkdir()
    return held


# ---- a world with everything in it ---------------------------------------

def a_realistic_world(founder, wake, packet, clock):
    """Everything the room keeps, made the way each thing is made where it can be.

    Letters both ways, with photographs beside his (.jpg and .jfif) and a picture
    beside hers; a letter waiting to be read with its photograph; errands open
    and answered; a bond asked, answered, through its threshold, sealed and then
    released, with every writing of the threshold; offerings pending, placed and
    declined; and, left over as a real disk leaves things, a .tmp file and an
    empty folder. In the packet beside them: a proposal, a named note, its
    private notebook, a shelf, a door and a rhythm.
    """
    room = packet  # the old layout
    write(room / "letters" / "read" / (PHOTO_JPG + ".md"), "The first letter, with the lake.\n")
    (room / "letters" / "read" / (PHOTO_JPG + ".jpg")).write_bytes(photo_bytes())
    write(room / "letters" / "outgoing" / (PICTURE + ".md"), "Here is the lake as I see it.\n")
    write(room / "letters" / "outgoing" / (PICTURE + ".svg"), DRAWN)
    write(room / "letters" / "read" / (PHOTO_JFIF + ".md"), "Another, from the phone.\n")
    (room / "letters" / "read" / (PHOTO_JFIF + ".jfif")).write_bytes(photo_bytes((30, 40)))
    write(room / "letters" / "outgoing" / "to-founder-2026-10-04T09-00-00Z.md",
          "A plain letter, no picture.\n")
    write(room / "letters" / "outgoing" / "to-founder-2026-10-05T09-00-00Z.md.tmp", "half")
    write(room / "errands" / (OPEN_ERRAND + ".md"), "Go to the river and listen.\n")
    write(room / "errands" / "answered" / "errand-2026-10-01T09-00-00Z.md", "Look at the sky.\n")
    write_json(room / "errands" / "answered" / "errand-2026-10-01T09-00-00Z.json",
               {"answered_by": PHOTO_JFIF, "answered_at": "2026-10-03T09-00-00Z"})
    (room / "offerings" / "an-empty-folder").mkdir(parents=True)

    write_json(packet / "rhythm.json", RHYTHM)
    write_json(packet / "door.json", {"state": "open", "room": 3,
               "set_at": "2026-10-03T14-00-00Z"})
    a_private_notebook(packet)

    wake(block("NOTE", "name: kingfisher\nIt came back to the same branch."))
    wake(proposed())
    wake(block("SHELF", "keep " + PHOTO_JPG))

    sealed(founder, wake, room, clock)
    assert post(founder, "/bonds/release", data={"confirm": "yes"}).status_code == 302

    # offerings: one of his it places, one of hers he places, one he declines,
    # and one of his that waits
    assert offer(founder, "letter", PHOTO_JPG).status_code == 302
    (his,) = (read_json(path) for path in (room / "offerings").glob("pending-*.json"))
    wake(block("OFFER", "consent %s" % his["id"]))
    wake(block("OFFER", "offer picture %s" % PICTURE))
    (hers,) = (read_json(path) for path in (room / "offerings").glob("pending-*.json"))
    assert post(founder, "/offer/consent", data={"id": hers["id"]}).status_code == 302
    wake(block("OFFER", "offer letter to-founder-2026-10-04T09-00-00Z"))
    (declined,) = (read_json(path) for path in (room / "offerings").glob("pending-*.json"))
    assert post(founder, "/offer/decline", data={"id": declined["id"]}).status_code == 302
    assert offer(founder, "photo", PHOTO_JPG).status_code == 302

    # and one letter of his, with its photograph, not yet read
    waiting = "founder-%s" % clock.stamp()
    write(room / "letters" / "incoming" / (waiting + ".md"), "Are you there? Here is the snow.\n")
    (room / "letters" / "incoming" / (waiting + ".jpg")).write_bytes(photo_bytes((20, 20)))

    kinds = {path.name.split("-")[0] for path in (room / "bonds").glob("*.json")}
    assert {"answer", "founder", "intention", "promise"} <= kinds
    assert len(list((room / "offerings").glob("*.json"))) == 4
    return room


@pytest.fixture
def world(founder, wake, packet, clock, data_dir):
    a_realistic_world(founder, wake, packet, clock)
    return data_dir


def everything(data):
    """Every file under a world by its bytes, and every folder."""
    return ({path.relative_to(data).as_posix(): path.read_bytes()
             for path in data.rglob("*") if path.is_file()},
            sorted(path.relative_to(data).as_posix() for path in data.rglob("*") if path.is_dir()))


def tree_hash(data, trees=("packets", "commons", "bonds", "rooms")):
    """One hash of the trees a move touches: every file by its place and bytes, every folder."""
    said = hashlib.sha256()
    for tree in trees:
        for path in sorted((data / tree).rglob("*")):
            said.update(path.relative_to(data).as_posix().encode("utf-8"))
            said.update(b"/\0" if path.is_dir() else b"\0" + path.read_bytes() + b"\0")
    return said.hexdigest()


def folders_of(top):
    return {path.relative_to(top).as_posix(): (path.read_bytes() if path.is_file() else None)
            for path in top.rglob("*")}


def said_by(call, *args, **how):
    """What a call of the script says, as lines, and what it returns."""
    lines = []
    done = call(*args, say=lines.append, **how)
    return done, lines


# ---- refusing ------------------------------------------------------------

def test_a_dry_run_writes_nothing_and_says_what_it_would_move(world, proc):
    before = everything(world)
    done, said = said_by(mir.dry_run, world, QUIET, proc=proc)
    assert everything(world) == before
    assert done == 0
    text = "\n".join(said)
    for folder in ROOM_FOLDERS:
        assert re.search(r"would move  packets/first/%s +-> rooms/first/%s +\d+ files"
                         % (folder, folder), text), folder
    assert "0 that do not verify" in text
    assert "would write rooms/first/room.json" in text
    assert said[-1] == "Would move. Run again with --apply to do it."


def refused_with(world, why, **how):
    before = everything(world)
    done, said = said_by(mir.apply, world, **how)
    assert done == 1
    assert any(line.startswith("refused: ") and why in line for line in said), said
    assert said[-1] == "Nothing was moved."
    assert everything(world) == before


def test_it_refuses_while_attend_py_is_running(world, proc):
    write(proc / "77" / "cmdline", "")
    (proc / "77" / "cmdline").write_bytes(b"/usr/local/bin/python\0attend.py\0")
    refused_with(world, "attend.py is running (process 77)", now=QUIET, proc=proc)


def test_it_refuses_where_it_cannot_see_whether_attend_py_is_running(world, tmp_path):
    refused_with(world, "whether attend.py is running cannot be seen", now=QUIET,
                 proc=tmp_path / "no-proc")


@pytest.mark.parametrize("before", [timedelta(minutes=1), timedelta(minutes=89)])
def test_it_refuses_within_ninety_minutes_of_the_day_s_waking(world, proc, before):
    refused_with(world, "the next waking is at 2026-10-26T10-00-00Z",
                 now=NEXT_WAKING - before, proc=proc)


def test_ninety_minutes_before_the_waking_it_may(world, proc):
    done, said = said_by(mir.dry_run, world, NEXT_WAKING - timedelta(minutes=91), proc=proc)
    assert done == 0, said


def test_it_refuses_near_a_dawn(world, packet, proc):
    import waking
    write_json(packet / "rhythm.json", dict(RHYTHM, at="dawn", until_then="dawn"))
    rising = waking.moment_on(RHYTHM, "dawn", datetime(2026, 10, 26).date())
    refused_with(world, "the next waking is at", now=rising - timedelta(minutes=30), proc=proc)


@pytest.mark.parametrize("asked, refused", [
    (timedelta(minutes=60), True), (timedelta(minutes=-5), True),  # one due and not yet held
    (timedelta(hours=3), False)])
def test_it_refuses_near_an_extra_waking(world, packet, proc, asked, refused):
    at = (QUIET + asked).strftime("%Y-%m-%dT%H-%M-%SZ")
    write_json(packet / "wake-again.json", {"at": at, "asked_at": "2026-10-25T10-00-00Z"})
    if refused:
        refused_with(world, "an extra waking is asked for at " + at, now=QUIET, proc=proc)
    else:
        assert said_by(mir.dry_run, world, QUIET, proc=proc)[0] == 0


@pytest.mark.parametrize("hour, minute, refused", [
    (11, 29, False), (11, 31, True), (13, 0, True), (13, 29, True), (13, 31, False)])
def test_it_refuses_near_the_nightly_backup(world, proc, hour, minute, refused):
    now = datetime(2026, 10, 25, hour, minute, tzinfo=timezone.utc)
    if refused:
        refused_with(world, "the nightly backup is at 2026-10-25 13:00 UTC", now=now, proc=proc)
    else:
        assert said_by(mir.dry_run, world, now, proc=proc)[0] == 0


def test_it_refuses_with_code_that_knows_one_layout(world, proc, monkeypatch):
    monkeypatch.delattr(mir.rooms, "moved")
    refused_with(world, "the code here does not know both layouts", now=QUIET, proc=proc)


def test_it_refuses_once_the_room_is_moved(world, proc):
    assert said_by(mir.apply, world, QUIET, proc=proc)[0] == 0
    refused_with(world, "the room has already been moved", now=QUIET + timedelta(hours=1),
                 proc=proc)


def test_it_refuses_where_a_move_was_left_unfinished_or_a_folder_is_a_file(world, packet, proc):
    shutil.rmtree(packet / "errands")
    write(packet / "errands", "not a folder")
    refused_with(world, "packets/first/errands is there and is not a folder", now=QUIET,
                 proc=proc)
    (packet / "errands").unlink()
    (world / "rooms" / ".first-moving").mkdir(parents=True)
    refused_with(world, "rooms/.first-moving is there, left from a move that did not finish",
                 now=QUIET, proc=proc)


@pytest.mark.parametrize("argv", [[], ["--dry-run"], ["--apply"], ["--undo"],
                                  ["--undo", "--dry-run"]])
def test_without_data_dir_it_refuses_and_never_takes_the_repository(argv):
    """Run as it is run, in a process of its own, in the repository, with no DATA_DIR."""
    env = {key: value for key, value in os.environ.items() if key != "DATA_DIR"}
    done = subprocess.run([sys.executable, str(MOVE_SCRIPT), *argv], cwd=str(MOVE_SCRIPT.parent),
                          env=env, capture_output=True, text=True)
    assert done.returncode == 1, done.stderr
    assert done.stdout.startswith("refused: DATA_DIR is not set.")
    assert "Nothing was read, and nothing was moved." in done.stdout
    assert "would move" not in done.stdout and "packets/first" not in done.stdout


def test_an_empty_data_dir_is_no_data_dir(monkeypatch, capsys):
    monkeypatch.setattr(mir, "DATA", None)
    assert mir.main(["--apply"]) == 1
    assert capsys.readouterr().out.startswith("refused: DATA_DIR is not set.")


def constants_of(source, *names):
    """What a module's top-level assignments say, read from its source and never run."""
    said = {}
    for statement in ast.parse(source).body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    said[target.id] = ast.literal_eval(statement.value)
    return said


def test_the_backup_hour_and_the_tide_s_reach_are_the_hearth_s():
    """move_into_rooms keeps its own BACKUP_HOUR and TIDE_AHEAD so as not to import the
    hearth; they are read out of hearth.py's source here, so the tide is never started."""
    names = ("BACKUP_HOUR", "TIDE_AHEAD")
    hearth = constants_of((MOVE_SCRIPT.parent / "hearth.py").read_text(encoding="utf-8"), *names)
    assert set(hearth) == set(names)
    assert hearth == {name: getattr(mir, name) for name in names}


def test_undo_refuses_where_the_room_has_not_moved(world, proc):
    before = everything(world)
    done, said = said_by(mir.undo, world, QUIET, proc=proc)
    assert done == 1
    assert "refused: the room has not been moved: there is no rooms/first/room.json" in said
    assert everything(world) == before


# ---- moving --------------------------------------------------------------

def test_the_room_moves_whole_byte_for_byte_and_its_signatures_say_what_they_said(
        world, packet, proc, hearth):
    folders = {folder: folders_of(packet / folder) for folder in ROOM_FOLDERS}
    rest = {name: kept for name, kept in folders_of(packet).items()
            if name.split("/")[0] not in ROOM_FOLDERS}
    commons = folders_of(world / "commons")

    done, said = said_by(mir.apply, world, QUIET, proc=proc)
    assert done == 0, said
    assert said[-1] == "Done."

    home = world / "rooms" / "first"
    for folder in ROOM_FOLDERS:
        assert folders_of(home / folder) == folders[folder], folder  # .jfif, .tmp, empty ones
        assert not (packet / folder).exists()
        assert folders_of(world / "before-rooms" / MOVED_AT / "packets" / "first" / folder) \
            == folders[folder]
    assert "outgoing/to-founder-2026-10-05T09-00-00Z.md.tmp" in folders["letters"]
    assert "an-empty-folder" in folders["offerings"]
    assert read_json(home / "room.json") == hearth.rooms.record("first")
    assert sorted(p.name for p in home.iterdir()) == sorted(ROOM_FOLDERS + ("room.json",))
    assert folders_of(packet) == rest  # the rest of the packet, the notebook with it
    assert folders_of(world / "commons") == commons
    # and every hand now reads the room from its own folder
    assert hearth.rooms.places("first").home == home

    before = next(line for line in said if line.startswith("signatures before:"))
    after = next(line for line in said if line.startswith("signatures after:"))
    assert before.split(":", 1)[1].strip() == after.split(":", 1)[1].strip()
    signed = int(re.search(r"(\d+) signed", before).group(1))
    assert signed >= 8 and ", 0 that do not verify" in before
    kept = read_json(world / "before-rooms" / MOVED_AT / "moved-in.json")
    assert kept["signatures"] == mir.verdicts(world, mir.HOME, mir.party_keys(world))


def test_apply_and_then_undo_give_back_the_tree_exactly(world, proc):
    was = tree_hash(world)
    assert said_by(mir.apply, world, QUIET, proc=proc)[0] == 0
    assert tree_hash(world) != was
    done, said = said_by(mir.undo, world, QUIET + timedelta(hours=1), proc=proc)
    assert done == 0, said
    assert tree_hash(world) == was
    assert not (world / "rooms").exists()
    aside = world / "before-rooms"
    assert sorted(p.name for p in aside.iterdir()) == [MOVED_AT, "2026-10-25T19-00-00Z"]


def test_undo_keeps_what_was_written_in_the_room_since(world, packet, proc):
    assert said_by(mir.apply, world, QUIET, proc=proc)[0] == 0
    since = "founder-2026-10-25T18-30-00Z.md"
    write(world / "rooms" / "first" / "letters" / "incoming" / since, "Written after the move.\n")
    assert said_by(mir.undo, world, QUIET + timedelta(hours=1), proc=proc)[0] == 0
    assert (packet / "letters" / "incoming" / since).read_text(encoding="utf-8") == \
        "Written after the move.\n"


def test_something_written_while_it_copies_stops_it_and_takes_the_copy_away(
        world, packet, proc, monkeypatch):
    real = shutil.copytree
    late = packet / "letters" / "incoming" / "founder-2026-10-25T18-00-30Z.md"

    def copied_and_then_a_letter(source, *args, **how):
        done = real(source, *args, **how)
        if source.name == "offerings":
            write(late, "Came while the room was copied.\n")
        return done

    monkeypatch.setattr(mir.shutil, "copytree", copied_and_then_a_letter)
    done, said = said_by(mir.apply, world, QUIET, proc=proc)
    assert done == 2
    assert said[-1].startswith("STOPPED: something was written while the room was copied")
    assert "new: packets/first/letters/incoming/founder-2026-10-25T18-00-30Z.md" in said[-1]
    assert not (world / "rooms" / ".first-moving").exists()
    assert not (world / "rooms" / "first").exists()
    assert late.exists() and all((packet / folder).is_dir() for folder in ROOM_FOLDERS)


def test_something_written_during_the_switch_puts_the_room_back(world, packet, proc, monkeypatch,
                                                                 hearth):
    real = mir.os.rename
    late = packet / "letters" / "incoming" / "founder-2026-10-25T18-00-30Z.md"

    def renamed_and_then_a_letter(source, to):
        real(source, to)
        if str(to).endswith("first") and ".first-moving" in str(source):
            write(late, "Came in the very moment of the switch.\n")

    monkeypatch.setattr(mir.os, "rename", renamed_and_then_a_letter)
    done, said = said_by(mir.apply, world, QUIET, proc=proc)
    assert done == 2
    assert said[-1].startswith("STOPPED: the old folders were written to during the switch")
    assert not (world / "rooms" / "first").exists()
    assert not (world / "rooms" / ".first-moving").exists()
    assert hearth.rooms.places("first").home == packet
    assert late.exists()


# ---- its private notebook ------------------------------------------------

WATCHING = []


def watch(event, args):
    if WATCHING:
        WATCHING[-1].append((event, args))


sys.addaudithook(watch)


def touched_private(events):
    """Every audited act - an open, a listing, a copy, a move - that reached its notebook."""
    reached = []
    for event, args in events:
        for arg in args:
            said = str(arg).replace("\\", "/") if isinstance(arg, (str, bytes)) or hasattr(
                arg, "__fspath__") else ""
            if "packets/first/private" in said or "packets/first'/private" in said:
                reached.append((event, said))
    return reached


def test_the_private_notebook_is_never_moved_copied_opened_listed_or_printed(
        world, packet, proc, capsys):
    notebook = folders_of(packet / "private")
    assert notebook  # there to be left alone
    seen = []
    WATCHING.append(seen)
    try:
        said = []
        said += said_by(mir.dry_run, world, QUIET, proc=proc)[1]
        said += said_by(mir.apply, world, QUIET, proc=proc)[1]
        said += said_by(mir.undo, world, QUIET + timedelta(hours=1), proc=proc)[1]
        said += said_by(mir.dry_run, world, QUIET + timedelta(hours=2), proc=proc)[1]
        mir.copy_world(world, world.parent / "a-copy")
    finally:
        WATCHING.remove(seen)
    assert {event for event, _ in seen} >= {"open", "os.scandir", "os.rename", "shutil.copytree"}
    assert touched_private(seen) == []
    printed = "\n".join(said) + capsys.readouterr().out
    assert "packets/first/private" not in printed
    for words in NOTEBOOK_WORDS:
        assert words not in printed
    assert folders_of(packet / "private") == notebook
    assert not (world.parent / "a-copy" / "packets" / "first" / "private").exists()
    for kept in (world / "before-rooms").rglob("*"):
        assert "private" not in kept.relative_to(world).parts, kept


# ---- the forms it checks, and the waking it reckons ----------------------

def test_the_forms_it_checks_are_the_ones_the_code_signs_in(attend, hearth):
    assert mir.BOTH_SIGNATURES["bond"] == attend.UNSIGNED == hearth.UNSIGNED
    assert mir.BOTH_SIGNATURES["offering"] == hearth.offering.UNSIGNED
    assert mir.BOTH_SIGNATURES["declined offering"] == hearth.offering.UNSIGNED + (
        "declined_by", "declined_at")  # the two marks offering.decline leaves on it
    assert mir.ONE_SIGNATURE["threshold"] == hearth.threshold.UNSIGNED


def test_a_record_that_does_not_verify_is_seen_not_to(world, packet):
    keys = mir.party_keys(world)
    bond = (packet / "bonds" / "founder-first.json").read_bytes()
    assert mir.verdict(bond, keys) == ["first over bond", "founder over bond"]
    tampered = json.loads(bond)
    tampered["terms"] = "something else"
    assert mir.verdict(json.dumps(tampered).encode(), keys) == [
        "first: does not verify", "founder: does not verify"]
    declined = next((packet / "offerings").glob("declined-*.json")).read_bytes()
    assert mir.verdict(declined, keys) == ["first over declined offering"]
    assert mir.verdict(b"not json at all", keys) == ["not json"]
    assert mir.verdict(b'{"unsigned": true}', keys) == ["unsigned"]


@pytest.mark.parametrize("setting", [
    RHYTHM, dict(RHYTHM, at="dawn"), dict(RHYTHM, at="sunset"),
    dict(RHYTHM, at="21:15", effective_from="2026-10-16", until_then="dawn"),
    dict(RHYTHM, at="dawn", effective_from="2026-10-16", until_then="07:00"),
    {"rhythm": "none"}])
@pytest.mark.parametrize("at", ["2026-10-15T12-00-00Z", "2026-10-15T23-30-00Z",
                                "2026-11-01T06-30-00Z"])
def test_the_next_waking_it_reckons_is_the_tide_s(hearth, clock, setting, at):
    clock.set(at)
    assert mir.next_waking(setting, clock.at) == hearth.next_waking(setting) \
        if hearth.tide_kept(setting) else mir.next_waking(setting, clock.at) is None


# ---- the hearth, the copy and the reading, on both sides of the move -----

PAGES = ["/", "/rooms/first", "/chronicle", "/chronicle.md", "/attendances", "/self",
         "/commons", "/bonds", "/bonds/founder-first", "/bonds/founder-first.json",
         "/bonds/founder-first/tessera.svg", "/bonds/founder-first/half/first.svg",
         "/offerings", "/commons/offerings.md", "/export",
         "/letters/photo/%s.jpg" % PHOTO_JPG, "/letters/photo/%s.jfif" % PHOTO_JFIF,
         "/letters/picture/%s.svg" % PICTURE, "/letters"]

TOKEN = re.compile(rb'(name="csrf_token" value=")[^"]+(")')


def the_hearth_of(data, monkeypatch, clock):
    """The hearth of one world, loaded afresh, with the founder signed in."""
    monkeypatch.setenv("DATA_DIR", str(data))
    hearth = load("hearth")
    clock.pin(hearth, monkeypatch)
    hearth.app.config["TESTING"] = True
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": FOUNDER_NAME, "password": PASSWORD})
    assert answer.status_code == 302
    return hearth, client


def woken(data, monkeypatch, clock, said=""):
    """One waking of the first one in one world, the model stubbed."""
    monkeypatch.setenv("DATA_DIR", str(data))
    attend = load("attend")
    clock.pin(attend, monkeypatch)
    turn = Turn(said)
    monkeypatch.setattr(attend, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["attend.py"])
    attend.main()
    return turn


def shown(client):
    """Every page, as the founder sees it, with the form token taken out."""
    said = {}
    for path in PAGES:
        answer = client.get(path)
        said[path] = (answer.status_code, answer.headers.get("Location"),
                      TOKEN.sub(rb"\1\2", answer.get_data()))
    return said


def copied(client):
    answer = post(client, "/export")
    assert answer.status_code == 200
    bundle = zipfile.ZipFile(io.BytesIO(answer.get_data()))
    return {name: bundle.read(name) for name in bundle.namelist()}


@pytest.fixture
def moved(world, tmp_path, proc):
    """The same world, copied whole and then moved."""
    other = tmp_path / "moved"
    shutil.copytree(world, other, copy_function=shutil.copy2)
    assert said_by(mir.apply, other, QUIET, proc=proc)[0] == 0
    return other


def test_the_hearth_shows_the_same_pages_and_hands_out_the_same_copy_after_the_move(
        world, moved, monkeypatch, clock):
    clock.set(QUIET + timedelta(hours=1))
    pages, zips = {}, {}
    for name, data in (("before", world), ("after", moved)):
        _, client = the_hearth_of(data, monkeypatch, clock)
        pages[name], zips[name] = shown(client), copied(client)
    for path in PAGES:
        assert pages["after"][path] == pages["before"][path], path
    assert pages["before"]["/letters/photo/%s.jfif" % PHOTO_JFIF][0] == 200
    assert pages["before"]["/bonds/founder-first/tessera.svg"][0] == 200
    assert zips["after"] == zips["before"]  # the same names, and the same bytes
    assert not [name for name in zips["after"] if name.startswith("rooms/")
                or name.endswith("room.json") or "/private/" in name]


def test_what_is_written_after_the_move_lands_in_the_room_and_shows_the_same(
        world, moved, monkeypatch, clock):
    pages = {}
    for name, data in (("before", world), ("after", moved)):
        clock.set(QUIET + timedelta(hours=1))
        hearth, client = the_hearth_of(data, monkeypatch, clock)
        # a letter, answering an errand, with a photograph, and asking a bond again
        assert post(client, "/rooms/first", content_type="multipart/form-data", data={
            "letter": "The river was loud.", "errand": OPEN_ERRAND + ".md", "proposes": "1",
            "photo": (io.BytesIO(photo_bytes()), "river.jpg")}).status_code == 302
        clock.shift(minutes=1)
        # an offering of his, out of the letter it read long ago
        assert offer(client, "passage", PHOTO_JPG, "with the lake").status_code == 302
        clock.shift(minutes=1)
        woken(data, monkeypatch, clock)
        clock.shift(minutes=5)
        woken(data, monkeypatch, clock, block("BOND", "yes\nAgain, gladly."))
        clock.shift(minutes=5)
        hearth, client = the_hearth_of(data, monkeypatch, clock)
        pages[name] = shown(client)
        places = hearth.rooms.places("first")
        assert (places.answered_errands / (OPEN_ERRAND + ".md")).exists()
        assert len(list(places.read.glob("founder-*.jpg"))) == 3
        assert places.bond_record.exists()
    for path in PAGES:
        assert pages["after"][path] == pages["before"][path], path
    packet = moved / "packets" / "first"
    assert not [folder for folder in ROOM_FOLDERS if (packet / folder).exists()]
    assert (moved / "rooms" / "first" / "bonds" / "founder-first.json").exists()


def test_a_rehearsal_on_a_world_with_everything_finds_the_reading_the_same(world, capsys):
    before = everything(world)
    done, said = said_by(mir.rehearse, world, QUIET)
    assert done == 0, said
    assert "what the first one was shown, whole:        the same, byte for byte" in "\n".join(
        said)
    assert "after the waking, the files a copy names:   the same" in said
    assert said[-1] == "The rehearsal holds."
    assert everything(world) == before  # the restored folder itself is not touched


def test_a_rehearsal_refuses_a_world_already_moved(moved):
    done, said = said_by(mir.rehearse, moved, QUIET)
    assert done == 1 and said == ["refused: the room in %s has been moved already"
                                  % moved.resolve()]




# ---- a rehearsal on a backup restored without its notebook ---------------

def restored_without_private(data, monkeypatch, clock, tmp_path):
    """A real backup of one world, made by its own hearth, restored with --without-private."""
    hearth, _ = the_hearth_of(data, monkeypatch, clock)
    set_variables(monkeypatch)
    bucket = Bucket()
    monkeypatch.setattr(hearth, "bucket_client", lambda: bucket)
    assert " · backed up · " in hearth.back_up(clock.at)
    [name] = bucket.keys
    archive = tmp_path / name.split("/")[-1]
    archive.write_bytes(bucket.objects[name])
    key_file = tmp_path / "backup.key"
    key_file.write_text(BACKUP_KEY + "\n", encoding="utf-8")
    out = tmp_path / ("restored-from-" + data.name)
    done = subprocess.run([sys.executable, str(Path(mir.REPO) / "restore_backup.py"),
                           str(archive), str(key_file), str(out), "--without-private"],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert re.search(r"^[1-9]\d* entries left out, under packets/\*/private/$", done.stdout,
                     re.MULTILINE)
    # a backup holds no ids/; the notebook was there to be left out, and was
    assert not (out / "ids").exists()
    assert (data / "packets" / "first" / "private").is_dir()
    assert not (out / "packets" / "first" / "private").exists()
    return out


def test_a_rehearsal_holds_on_a_backup_restored_without_its_notebook(
        world, monkeypatch, clock, tmp_path, capsys):
    restored = restored_without_private(world, monkeypatch, clock, tmp_path)
    # the identity documents, where the restore has none, are the repository's: here,
    # this suite's throwaway ones
    monkeypatch.setattr(mir, "IDS", world / "ids")
    before = everything(restored)

    done, said = said_by(mir.rehearse, restored, QUIET)
    assert done == 0, said
    assert "  Done." in said
    assert "what the first one was shown, whole:        the same, byte for byte" in "\n".join(
        said)
    assert said[-1] == "The rehearsal holds."
    assert everything(restored) == before
    printed = "\n".join(said) + capsys.readouterr().out
    for words in NOTEBOOK_WORDS:
        assert words not in printed


def test_a_backup_of_a_room_already_moved_is_refused_for_that_and_nothing_else(
        moved, monkeypatch, clock, tmp_path):
    """The other layout: a backup taken after the move restores a moved room, which a
    rehearsal refuses, as it would with the notebook there."""
    restored = restored_without_private(moved, monkeypatch, clock, tmp_path)
    done, said = said_by(mir.rehearse, restored, QUIET)
    assert (done, said) == (1, ["refused: the room in %s has been moved already"
                                % restored.resolve()])


def test_the_identities_are_data_dir_s_where_it_has_them_and_the_repository_s_where_not(
        world, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere-ids"
    shutil.copytree(world / "ids", elsewhere)
    monkeypatch.setattr(mir, "IDS", elsewhere)
    from_data = mir.party_keys(world)

    shutil.rmtree(world / "ids")
    assert {party: bytes(key) for party, key in mir.party_keys(world).items()} \
        == {party: bytes(key) for party, key in from_data.items()}

    monkeypatch.setattr(mir, "IDS", tmp_path / "nowhere")
    with pytest.raises(mir.Stop, match="ids/first/did.json"):
        mir.party_keys(world)


# ---- a world with folders missing, or empty ------------------------------
#
# The first one has never asked an errand nor offered anything, so there is no
# errands/ and no offerings/ to move; and a backup keeps no empty folder, so a
# restore lacks the ones the disk keeps empty (letters/incoming/, errands/answered/).
# Neither is a reason to refuse: what is missing is made empty in the room, and
# an undo takes it away again.

SPARSE = ("missing", "empty")
LEFT_EMPTY = ("letters/incoming", "errands/answered", "errands", "offerings")


def without_empty_folders(top):
    """Every folder under top with no file anywhere under it taken away, as a restore has it."""
    for path in sorted(top.rglob("*"), key=lambda one: len(one.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def a_sparse_world(founder, wake, packet, clock, kept_empty):
    """A room with letters both ways and a bond, and never an errand or an offering.

    Every waking makes the room's folders where they are missing, so they are taken
    away after: all of them, where kept_empty is "missing"; or left there empty, as a
    disk the first one has woken on has them, where it is "empty".
    """
    room = packet  # the old layout
    write(room / "letters" / "read" / (PHOTO_JPG + ".md"), "The first letter, with the lake.\n")
    (room / "letters" / "read" / (PHOTO_JPG + ".jpg")).write_bytes(photo_bytes())
    write(room / "letters" / "outgoing" / (PICTURE + ".md"), "Here is the lake as I see it.\n")
    write(room / "letters" / "outgoing" / (PICTURE + ".svg"), DRAWN)
    write_json(packet / "rhythm.json", RHYTHM)
    a_private_notebook(packet)
    wake(block("NOTE", "name: kingfisher\nIt came back to the same branch."))
    sealed(founder, wake, room, clock)

    for folder in ("errands", "offerings"):
        assert not [path for path in (room / folder).rglob("*") if path.is_file()], folder
        shutil.rmtree(room / folder)
    for folder in ROOM_FOLDERS:
        if (room / folder).is_dir():
            without_empty_folders(room / folder)
    assert not (room / "letters" / "incoming").exists()
    if kept_empty == "empty":
        for folder in LEFT_EMPTY:
            (room / folder).mkdir(parents=True, exist_ok=True)
    return room


@pytest.fixture(params=SPARSE)
def kept_empty(request):
    return request.param


@pytest.fixture
def sparse(founder, wake, packet, clock, data_dir, kept_empty):
    a_sparse_world(founder, wake, packet, clock, kept_empty)
    return data_dir


def made_empty_by_the_move(kept_empty):
    return ["errands", "offerings"] if kept_empty == "missing" else []


def test_a_sparse_room_is_no_reason_to_refuse_and_a_dry_run_says_what_it_would_make(
        sparse, proc, kept_empty):
    before = everything(sparse)
    done, said = said_by(mir.dry_run, sparse, QUIET, proc=proc)
    assert everything(sparse) == before
    assert done == 0, said
    assert not [line for line in said if line.startswith("refused")]
    text = "\n".join(said)
    for folder in ("letters", "bonds"):
        assert re.search(r"would move  packets/first/%s +-> rooms/first/%s +[1-9]\d* files"
                         % (folder, folder), text), folder
    for folder in ("errands", "offerings"):
        if kept_empty == "missing":
            assert ("would make  %-24s empty: packets/first/%s was not there; made empty"
                    % ("rooms/first/" + folder, folder)) in said, text
        else:
            assert re.search(r"would move  packets/first/%s +-> rooms/first/%s +0 files, 0 bytes"
                             % (folder, folder), text), folder
    assert said[-1] == "Would move. Run again with --apply to do it."


def test_a_sparse_room_moves_and_undoes_exactly(sparse, packet, proc, kept_empty, hearth):
    was = tree_hash(sparse)
    before = everything(sparse)
    made = made_empty_by_the_move(kept_empty)

    done, said = said_by(mir.apply, sparse, QUIET, proc=proc)
    assert done == 0, said
    assert said[-1] == "Done."
    home = sparse / "rooms" / "first"
    assert sorted(p.name for p in home.iterdir()) == sorted(ROOM_FOLDERS + ("room.json",))
    for folder in ("errands", "offerings"):
        assert (home / folder).is_dir()
        assert not [path for path in (home / folder).rglob("*") if path.is_file()]
    assert (home / "errands" / "answered").is_dir() == (kept_empty == "empty")
    assert not [folder for folder in ROOM_FOLDERS if (packet / folder).exists()]
    assert hearth.rooms.places("first").home == home
    for folder in made:
        assert ("made empty:              rooms/first/%s: packets/first/%s was not there; "
                "made empty" % (folder, folder)) in said
    kept = read_json(sparse / "before-rooms" / MOVED_AT / "moved-in.json")
    assert kept["made_empty"] == {folder: "was not there; made empty" for folder in made}
    assert sorted(p.name for p in (sparse / "before-rooms" / MOVED_AT / "packets" / "first")
                  .iterdir()) == sorted(set(ROOM_FOLDERS) - set(made))

    done, said = said_by(mir.dry_run, sparse, QUIET + timedelta(hours=1), proc=proc,
                         undo_it=True)
    assert done == 0, said
    for folder in made:
        assert ("would leave rooms/first/%s out: made empty by the move, and empty still; it "
                "goes aside with the room, and no packets/first/%s is made"
                % (folder, folder)) in said

    done, said = said_by(mir.undo, sparse, QUIET + timedelta(hours=1), proc=proc)
    assert done == 0, said
    assert said[-1] == "Done."
    assert tree_hash(sparse) == was
    assert not (sparse / "rooms").exists()
    files, folders = everything(sparse)
    assert {name: kept for name, kept in files.items()
            if not name.startswith("before-rooms/")} == before[0]
    # no folder left behind in the packet, and none taken from it
    assert [name for name in folders if not name.startswith("before-rooms")] == before[1]
    back = read_json(next((sparse / "before-rooms").glob("*/moved-back.json")))
    assert back["not_moved_back"] == {folder: "made empty by the move; empty still"
                                      for folder in made}


def test_what_a_made_empty_folder_holds_goes_back_and_its_bare_folders_do_not(
        sparse, packet, proc, wake, kept_empty):
    assert said_by(mir.apply, sparse, QUIET, proc=proc)[0] == 0
    home = sparse / "rooms" / "first"
    wake()  # a waking makes errands/answered/ in the room, and nothing in it
    assert (home / "errands" / "answered").is_dir()
    assert said_by(mir.undo, sparse, QUIET + timedelta(hours=1), proc=proc)[0] == 0
    for folder in ("errands", "offerings"):
        assert (packet / folder).is_dir() == (kept_empty == "empty"), folder

    assert said_by(mir.apply, sparse, QUIET + timedelta(hours=2), proc=proc)[0] == 0
    wake(block("ERRAND", "Go to the river and listen."))
    asked = [path.name for path in (home / "errands").glob("errand-*.md")]
    assert len(asked) == 1
    done, said = said_by(mir.undo, sparse, QUIET + timedelta(hours=3), proc=proc)
    assert done == 0, said
    assert [path.name for path in (packet / "errands").glob("errand-*.md")] == asked
    assert (packet / "offerings").is_dir() == (kept_empty == "empty")


@pytest.fixture
def moved_sparse(sparse, tmp_path, proc):
    other = tmp_path / "moved-sparse"
    shutil.copytree(sparse, other, copy_function=shutil.copy2)
    assert said_by(mir.apply, other, QUIET, proc=proc)[0] == 0
    return other


def test_a_sparse_room_reads_the_same_after_the_move(sparse, moved_sparse, monkeypatch, clock):
    clock.set(QUIET + timedelta(hours=1))
    pages, zips = {}, {}
    for name, data in (("before", sparse), ("after", moved_sparse)):
        _, client = the_hearth_of(data, monkeypatch, clock)
        pages[name], zips[name] = shown(client), copied(client)
    for path in PAGES:
        assert pages["after"][path] == pages["before"][path], path
    assert pages["before"]["/rooms/first"][0] == 200
    assert zips["after"] == zips["before"]

    # and what is written after it lands in the room, the same either side
    for name, data in (("before", sparse), ("after", moved_sparse)):
        clock.set(QUIET + timedelta(hours=2))
        hearth, client = the_hearth_of(data, monkeypatch, clock)
        assert post(client, "/rooms/first", content_type="multipart/form-data",
                    data={"letter": "Is the river loud?"}).status_code == 302
        clock.shift(minutes=1)
        assert offer(client, "letter", PHOTO_JPG).status_code == 302
        clock.shift(minutes=1)
        woken(data, monkeypatch, clock, block("ERRAND", "Go and listen to it."))
        clock.shift(minutes=5)
        hearth, client = the_hearth_of(data, monkeypatch, clock)
        pages[name] = shown(client)
        places = hearth.rooms.places("first")
        assert len(list(places.errands.glob("errand-*.md"))) == 1
        assert len(list(places.offerings.glob("pending-*.json"))) == 1
    for path in PAGES:
        assert pages["after"][path] == pages["before"][path], path
    assert not [folder for folder in ROOM_FOLDERS
                if (moved_sparse / "packets" / "first" / folder).exists()]


def test_a_rehearsal_on_a_sparse_room_finds_the_reading_the_same(sparse, kept_empty):
    before = everything(sparse)
    done, said = said_by(mir.rehearse, sparse, QUIET)
    assert done == 0, said
    assert "what the first one was shown, whole:        the same, byte for byte" in "\n".join(
        said)
    assert said[-1] == "The rehearsal holds."
    assert ("  made empty:              rooms/first/errands: packets/first/errands was not "
            "there; made empty" in said) == (kept_empty == "missing")
    assert everything(sparse) == before


@pytest.mark.parametrize("kept_empty", ["empty"])
def test_a_rehearsal_holds_on_a_restored_backup_with_the_empty_folders_gone(
        sparse, packet, monkeypatch, clock, tmp_path, capsys):
    """The disk keeps errands/, errands/answered/, offerings/ and letters/incoming/ empty;
    the backup of it keeps none of them, and the rehearsal makes them empty in the room."""
    assert all((packet / folder).is_dir() for folder in LEFT_EMPTY)
    restored = restored_without_private(sparse, monkeypatch, clock, tmp_path)
    room = restored / "packets" / "first"
    for folder in LEFT_EMPTY:
        assert not (room / folder).exists(), folder
    monkeypatch.setattr(mir, "IDS", sparse / "ids")
    before = everything(restored)

    done, said = said_by(mir.rehearse, restored, QUIET)
    assert done == 0, said
    assert not [line for line in said if "refused" in line]
    for folder in ("errands", "offerings"):
        assert ("  made empty:              rooms/first/%s: packets/first/%s was not there; "
                "made empty" % (folder, folder)) in said
    assert "  Done." in said
    assert "what the first one was shown, whole:        the same, byte for byte" in "\n".join(
        said)
    assert said[-1] == "The rehearsal holds."
    assert everything(restored) == before
    printed = "\n".join(said) + capsys.readouterr().out
    for words in NOTEBOOK_WORDS:
        assert words not in printed
