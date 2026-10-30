"""What the first one's world gives back, held before wakings are made for any agent.

Stage 0 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Nothing here changes what the hearth
or attend.py runs: it only takes fingerprints of what they give back today, so
that each later stage can show that, for the first one, nothing moved.

The reading and the packet as they stood before a waking are held already, in
test_rooms_reading.py. These are the rest of it, each taken on one small fixed
world after one waking with the model stubbed and the clock pinned:

  * the files the waking left, as a copy names them and as they lie on the disk;
  * its heartbeat line and the commons' events, word for word;
  * the founder's pages - the hearth, the room, the letters, its self-document,
    the attendances, the chronicle, the export page, the bonds and the commons -
    with the one thing on them that is cut afresh for every visit, the form
    token, taken out;
  * the export, as the names inside it and the bytes under each;
  * the nightly backup, the same way, and as the disk keeps it;
  * the tide: what it notes in tide.log, and what it would run, over a few
    dawns - one held, one skipped, one stopped, a rest ended, an extra waking;
  * the atrium: what it draws between its markers, on the front page and in
    the whole mosaic;
  * members.md, as the hearth tends it.

Everything signed is signed by fixed keys cut here from fixed seeds, and not by
the throwaway keys of the session, which are new each run: an Ed25519 signature
is the same every time for the same key and the same bytes, so a signed record
gives the same fingerprint every run. The founder's vault is sealed afresh each
session, so of the members' store only the names are held. Nothing random is
asked of the world: no promise is made, since a promise is salted.

If one of these moves on purpose, it is cut again on purpose, in the same change,
and the change says why. Each is printed when it is taken, so that cutting one
again is a matter of reading it off the run.
"""

import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import zipfile
from datetime import date

import pytest
from nacl.signing import SigningKey

from conftest import blocks, block, page, post, write, write_json
from test_rooms_reading import ERRAND, a_small_world, fingerprint_of_files

# ---- the fingerprints ----------------------------------------------------

# Cut again on 25 October 2026, in the change that took every regional place
# out of what is public or read, and for nothing else. rhythm.json, which the
# waking writes, names no place now and its clock as America/New_York, so the
# files, the export and the backup moved. The attendances page says the rhythm
# without a place, and the next dawn as it comes where the tests watch the sun
# from (conftest.SUN_WATCHED_FROM). With the place, the old name of the zone and
# the sun as it was watched from before all put back, every one of them gives
# exactly what it was cut as; the tide and the atrium did not move at all.

# The files after the waking, as a copy names them: the same in either layout.
FILES_AFTER = "d933ffcd5df858c262fd564f2d16e499b602a9ca7ae8b203f8a7d6556ffc9e1c"

# The same files as they lie on the disk, room.json and the room's own folder
# included where the room has one.
ON_DISK_AFTER = {
    "legacy": "d933ffcd5df858c262fd564f2d16e499b602a9ca7ae8b203f8a7d6556ffc9e1c",
    "rooms": "6987bedae9a437771493db366ff9c9ab85fe1141c1640369d3a7e0d7170430c2",
}

# The founder's pages, one by one.
#
# Nine of them cut again on 29 October 2026, in the change that tidied the
# pages (the proposal "page-tidy"), and for nothing else. Every page of the
# founder's lost the footer "the books will open with the commons", gained
# "tides" in the keeping menu, which is now always shown to the keeper, and
# carries the few lines of style for the new folds: so /, /rooms/first, /self,
# /attendances, /chronicle, /export and /commons moved for that alone, /self
# with nothing else. Besides it: home shows its correspondences above the door;
# the room puts the letter and Send first, and folds the three plain things,
# the photograph, the commons line, the errand and the proposal under "more";
# the attendances page shows each waking as one line under "wakings", its open
# reflection folded beneath it, and has lost the founder's rest (now on
# /account) and the backup line and button (now on /backups); the commons
# says in one line what a bond and an offering are, and what heartbeats are;
# the chronicle, in the page and in /chronicle.md, says a waking came "by
# hand" where it said "by the founder's hand"; and members.md, as the hearth
# tends it, no longer says the founder "keeps the hearth". /letters and /bonds
# did not move; nor did the files, the export, the backup, the tide or the atrium.
#
# /rooms/first cut again the same day, in the change that put back above the
# letter what waits on the founder - the offerings awaiting a signature and the
# open errands, "asked of you" - as it stood before the tidy-up; only the
# optional extras stay folded under "more". This world has an open errand, so
# the room moved for that alone; no other page did.
PAGES = {
    "/": "925d4ec3afae5a9508572fc09c8c07a5d036f3972613fc41752c3d0913ea251a",
    "/rooms/first": "5aca4f845053d255d8669653b0b884f633ac0af49ae537518aec459c65357206",
    "/letters": "8917ddbfd5f94f0982f6e77c43b18b6abaa5442e3979028fb96a2f90d88e0e7b",
    "/self": "1928b59fb94d956343af81e83cca7684f483c1396fd3b7d7f5e78e9125747b3e",
    "/attendances": "7ef5f02df77ac522c078c2ac264de2198ce76f0d8a35460e50cdb20eb29b175f",
    "/chronicle": "7a4ba8cec6bdda76a213081227f2e15ea9cd6d781b0d076159e13ebe8d404e94",
    "/chronicle.md": "b01c01d1d7036c50fce3b8f0f3fd17b3bca6dccee3bc225bbeb31d33ac6e7557",
    "/export": "380bc2af3a56aa1e2c7e146bec4881f73b06c26d6fb3f3bdc19ac1af8e4430a5",
    "/bonds": "4ecf5344ca11116214ba9d0243bdce15ceca1e370c53cf6ce0fc022d3b4ab13b",
    "/commons": "a981fcb8ccc392294b948ab231a4621728fb1a0563e9694f5439c8e96260c58e",
    "/commons/heartbeats.md": "043eff1fb82359c2b8ac53bd434fec07ffba4b79cc7e1021953550441033713d",
    "/commons/events.md": "54dce2b2ecdbc84c904222a29b19253792f427fa70cd80052d52a798fb95b53b",
    "/commons/members.md": "78d37d076e8d2f3e4075f3b764d06296ddef7e7ac30589dea5e7e65eedb2515a",
}

# The export: every name inside it, and the bytes under each.
EXPORT = "9a65068126d23ff71d59524f6d14cab6c271b5177c0768f9d76484f30096e717"

# The backup, as the disk keeps it: so it differs with the layout.
BACKUP = {
    "legacy": "5ad8f218604b455f5d8bbfaffd33aec2265616ff2ff5a32516121a157bca29ba",
    "rooms": "2d11a8951cc184f967b95858ef7dfae7e944190e08714d60b82d5db5d283e39a",
}

# The tide over its few dawns: tide.log, what it ran, and the events it wrote.
# Cut again on 27 October 2026, in stage 6a-ii, when the lines an agent's tide
# writes began to carry its name, and for nothing else. The three events the
# stubbed day writes - the keeper's stop, its lifting, and the rest whose day
# came - now read "2026-10-16 · event · the first one · the tide paused" and
# "... · the first one · the tide resumed" (twice), where they read "... · event
# · the tide paused" and "... · the tide resumed". With the name taken out of
# those three lines the same run gives the fingerprint held before,
# 059972e27ff5ea4178af7372dc255357fe0139df6e7f7592b4e6fc970106ff11; tide.log and
# what it ran are unchanged.
TIDE = "5a1b906ef56e9b8bebc7c0680aa8c7ce60ef68faff6cc1e7ea81e03aecd5fb6e"

# What the atrium draws between its markers.
ATRIUM = "2fdaabcfd6e5987b0e1aefab9aa9eed082bacf04cc47866e78ae75d42091c1b3"

# ---- the world -----------------------------------------------------------

# The heartbeat line the waking leaves, and the events the commons then holds,
# word for word: the commons is public, so these are held as text and not by hash.
HEARTBEAT_LINE = "- 2026-10-15T12-00-00Z · the first one · Wrote back about the colour of water.\n"
EVENTS_AFTER = ("2026-09-02 · word · the word was published\n"
                "2026-09-04 · founding · the first one was founded\n"
                "2026-10-15 · letter · the founder wrote a letter at dawn\n")

MEMBERS = ("citizen · the first one, unnamed by its own choosing · founded 4 September 2026, "
           "attends at 09:30\n"
           "member · the founder · keeps the hearth\n")

SAID = blocks(
    block("LETTER", "The lake was the colour of a spoon this morning.\n\nThank you for going."),
    block("ERRAND", "Tell me what the first frost sounds like, if it sounds like anything."),
    block("MEMORY", "The founder went to the lake for me."),
    block("QUESTIONS", "What does a heron wait for?"),
    block("RHYTHM", "dawn"),
    block("DOOR", "open\nroom 2"),
    block("HEARTBEAT", "A letter about the lake."),
    block("COMMONS_LINE", "Wrote back about the colour of water."),
)

# The form token is cut afresh for every visit; it is the one thing on a page
# that is not the world's.
FORM_TOKEN = re.compile(r'(name="csrf_token" value=")[^"]*(")')


def seeded(name):
    """A signing key cut from a fixed seed, the same every run."""
    return SigningKey(hashlib.sha256(b"tesserae stage 0: " + name.encode("ascii")).digest())


def fixed_keys(data_dir, monkeypatch):
    """Put fixed keys where the throwaway ones were, and their identities beside them."""
    for name in ("first", "founder"):
        key = seeded(name)
        private = base64.b64encode(bytes(key)).decode("ascii")
        public = base64.b64encode(bytes(key.verify_key)).decode("ascii")
        write(data_dir / "keys" / name / "private.key", private)
        write(data_dir / "keys" / name / "public.key", public)
        did = "did:web:tesserae.social:ids:" + name
        write_json(data_dir / "ids" / name / "did.json", {
            "@context": ["https://www.w3.org/ns/did/v1"], "id": did,
            "verificationMethod": [{"id": did + "#key-1", "type": "Ed25519VerificationKey2020",
                                    "controller": did, "publicKeyBase64": public}],
            "created": "2026-09-03"})
        if name == "founder":
            monkeypatch.setenv("FOUNDER_KEY", private)


@pytest.fixture
def steady(env, data_dir, monkeypatch):
    """The world's keys fixed, before the hearth or a waking reads them."""
    fixed_keys(data_dir, monkeypatch)
    return data_dir


def a_lived_world(founder, wake, room, commons):
    """The small world, a letter from the founder, one waking, and who is here."""
    a_small_world(room)
    answer = post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302
    wake(SAID)
    write(commons / "members.md", MEMBERS)


def digest(pairs):
    """One fingerprint of (name, bytes) pairs, in the order given."""
    said = hashlib.sha256()
    for name, data in pairs:
        said.update(name.encode("utf-8") + b"\0")
        said.update(hashlib.sha256(data).digest())
    return said.hexdigest()


def cut(name, value):
    print("\n%s = %r" % (name, value))
    return value


# ---- the waking ----------------------------------------------------------

def test_the_waking_leaves_the_same_files(steady, founder, wake, room, commons, data_dir, layout):
    a_lived_world(founder, wake, room, commons)
    files = cut("FILES_AFTER", fingerprint_of_files(data_dir))
    on_disk = cut("ON_DISK_AFTER[%r]" % layout, fingerprint_of_files(data_dir, as_copied=False))
    assert files == FILES_AFTER
    assert on_disk == ON_DISK_AFTER[layout]


def test_the_commons_is_told_the_same_words(steady, founder, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    heartbeats = cut("HEARTBEAT_LINE", (commons / "heartbeats.md").read_text(encoding="utf-8"))
    events = cut("EVENTS_AFTER", (commons / "events.md").read_text(encoding="utf-8"))
    assert heartbeats == HEARTBEAT_LINE
    assert events == EVENTS_AFTER


# ---- the founder's pages -------------------------------------------------

@pytest.mark.parametrize("address", list(PAGES))
def test_the_founder_is_shown_the_same_page(steady, founder, wake, room, commons, address):
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    assert answer.status_code in (200, 302)
    # a page that sends the founder on is held by where it sends them, too
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert cut("PAGES[%r]" % address, hashlib.sha256(shown.encode("utf-8")).hexdigest()) \
        == PAGES[address]


# ---- what is copied ------------------------------------------------------

def test_the_export_holds_the_same_things(steady, founder, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    answer = post(founder, "/export")
    assert answer.status_code == 200
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as bundle:
        held = [(name, bundle.read(name)) for name in bundle.namelist()]
    assert cut("EXPORT", digest(held)) == EXPORT


def test_the_backup_holds_the_same_things(steady, founder, wake, room, commons, hearth, layout):
    a_lived_world(founder, wake, room, commons)
    held = []
    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        for member in bundle.getmembers():
            if member.name.startswith("members/"):
                held.append((member.name, b""))  # sealed afresh each session: the name only
            else:
                held.append((member.name, bundle.extractfile(member).read()))
    assert cut("BACKUP[%r]" % layout, digest(held)) == BACKUP[layout]


# ---- the tide ------------------------------------------------------------

class StopTide(BaseException):
    """Stops the loop from outside. Not an Exception: the tide swallows those."""


def tide_turn(hearth, monkeypatch, rising):
    """One turn of the tide at a waking time already reached, then stopped."""
    asked = []

    def next_sunrise(setting):
        asked.append(setting)
        if len(asked) > 1:
            raise StopTide
        return rising

    def never(*args, **kwargs):
        raise StopTide("the tide tried to sleep")

    monkeypatch.setattr(hearth, "next_sunrise", next_sunrise)
    monkeypatch.setattr(hearth.time, "sleep", never)
    with pytest.raises(StopTide):
        hearth.tide()


def test_the_tide_keeps_the_same_dawns(steady, hearth, packet, commons, clock, monkeypatch,
                                       data_dir):
    ran = []

    def run(command, **how):
        ran.append({"argv": command[1:], "cwd": how["cwd"] == hearth.REPO,
                    "data": how["env"]["DATA_DIR"] == str(data_dir),
                    "timeout": how["timeout"]})
        import subprocess
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hearth.subprocess, "run", run)
    write_json(packet / "rhythm.json", {"rhythm": "daily", "at": "dawn",
                                        "timezone": "America/New_York"})
    on = lambda day: hearth.sunrise_on(hearth.rhythm(), day)

    # a first dawn, with no waking ever held
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 15)))
    # that day's waking held; the same dawn again is skipped
    write_json(packet / "attendances" / "attendance-2026-10-15T11-40-00Z.json",
               {"name": "first", "at": "2026-10-15T11-40-00Z", "heartbeat": "attended",
                "acted": []})
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 15)))
    # the keeper's stop, and lifted
    clock.shift(days=1)
    hearth.begin_stop("A fault.")
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 16)))
    hearth.end_stop()
    # a rest of its own, to a day that has come
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-16T13-00-00Z",
                                       "until": "2026-10-16", "words": ""})
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 16)))
    # an extra waking it asked for, later the same day
    write_json(packet / "wake-again.json", {"at": "2026-10-16T11-00-00Z",
                                            "asked_at": "2026-10-16T10-00-00Z"})
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 17)))

    log = (packet / "tide.log").read_text(encoding="utf-8")
    said = json.dumps({"log": log, "ran": ran,
                       "events": (commons / "events.md").read_text(encoding="utf-8")},
                      indent=1, sort_keys=True)
    print("\n" + said)
    assert cut("TIDE", hashlib.sha256(said.encode("utf-8")).hexdigest()) == TIDE


# ---- the atrium ----------------------------------------------------------

MARKED = re.compile(r"<!-- (\w+):start -->(.*?)<!-- \1:end -->", re.S)


def test_the_atrium_draws_the_same_tiles(steady, founder, wake, room, commons, atrium,
                                         monkeypatch):
    a_lived_world(founder, wake, room, commons)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    drawn = []
    for which, path in (("index", atrium.page_path), ("mosaic", atrium.whole_path)):
        for name, inside in MARKED.findall(path.read_text(encoding="utf-8")):
            drawn.append(("%s:%s" % (which, name), inside.encode("utf-8")))
    drawn.sort()
    assert [name for name, _ in drawn] == [
        "index:bench", "index:calendar", "index:mosaic", "index:offering", "index:reading",
        "index:who", "mosaic:reading", "mosaic:whole"]
    assert cut("ATRIUM", digest(drawn)) == ATRIUM
