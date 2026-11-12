"""What the first one's world gives back, held before wakings are made for any agent.

Stage 0 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Nothing here changes what the hearth
or attend.py runs: it only takes fingerprints of what they give back today, so
that each later stage can show that, for the first one, nothing moved.

The reading and the packet as they stood before a waking are held already, in
test_rooms_reading.py. These are the rest of it, each taken on one small fixed
world after one waking with the model stubbed and the clock pinned:

  * the files the waking left, as they lie on the disk;
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

from conftest import (bench_link_not_yet, blocks, block, commons_pages_not_yet, letter_part_as_before, page,
                      pages_before_fewer, post, times_as_before, wakings_not_yet_switched, write,
                      write_json)
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

# The files after the waking, as they lie on the disk, the room's own folder and
# its room.json included. Beside it was FILES_AFTER, the same files as a copy
# named them until stage 5f, the room's under packets/first/ and no room.json
# (d933ffcd5df858c262fd564f2d16e499b602a9ca7ae8b203f8a7d6556ffc9e1c; in the old
# packet layout, gone since stage 5c, it was this one too). It went when a copy
# came to name the room's files as they are kept.
#
# Cut again on 10 November 2026, in the change by which the hearth no longer
# writes the part of the day in a person's letter line (the founder's decision
# that day), and for nothing else: commons/events.md, as the waking leaves it,
# says "2026-10-15 · letter · the founder wrote a letter" where it said "... at
# dawn". The same change moved EVENTS_AFTER, three of the founder's pages,
# EXPORT and BACKUP, each for that line alone. With the line written as it was
# (conftest.letter_part_as_before), each of them is exactly the one held before,
# in LETTER_PARTS_BEFORE below; nothing else moved.
ON_DISK_AFTER = "0deb050b7f042166c5c59654310190259a7ab4e02d0396abf6661601f888b8aa"

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
#
# /rooms/first cut again on 5 November 2026, in the change that built the quiet
# lines (the first one's letter of 4 November), and for nothing else: one muted
# line, "A few words is enough. Weeks get full.", directly above the three plain
# things; and the three plain things, with that line, brought out of the "more"
# fold to stand between the letter box and Send, always in view. The photograph,
# the commons line, the errand and the proposal stay folded. With the muted line
# taken out and the three put back at the top of the fold, it gives exactly the
# fingerprint it was cut as before (ROOM_BEFORE_QUIET, held below). No other page
# moved: /account, where a person says how they write, is not among these.
ROOM_BEFORE_QUIET = "5aca4f845053d255d8669653b0b884f633ac0af49ae537518aec459c65357206"
FEW_WORDS = '    <p class="muted">A few words is enough. Weeks get full.</p>\n'
LETTER_BOX_ENDS = "</textarea>\n"
SEND = '    <button type="submit">Send</button>\n'
FOLD_OPENS = "      <summary>more</summary>\n"

# Three cut again on 10 November 2026, in the change by which every public page
# and file says the day of a thing and not its time (the founder's decision that
# day), and for nothing else. /commons/heartbeats.md is handed out with each
# line's day in its stamp's place, "- 2026-10-15 at dawn · the first one · ...",
# where it was "- 2026-10-15T12-00-00Z · ..."; the file on the disk keeps the
# stamp. /chronicle and /chronicle.md say each waking's and letter's day, "15
# October 2026", where they said "15 October 2026, 08:00", and the chronicle page
# no longer says its times are Eastern, since it shows none. With the times put
# back (conftest.times_as_before), each is exactly the one held before, in
# TIMES_BEFORE below; nothing else moved.
#
# Seven cut again on 10 November 2026, in the change that made fewer pages (the
# founder's decision that day), and for nothing else. Every page of the founder's
# carries the members' menu as home · account · the commons · log out, where it
# read home · account · the bench · the commons · tesserae.social · log out, and
# the keeper's as tides · backups, where it read chronicle · attendances · self ·
# export · backups · tides: so /, /self, /chronicle, /export and /commons moved
# for that alone. Besides it: the room, under "more", has the first one's wakings,
# closed, as /attendances shows them, its rhythm line, and links to its self, its
# chronicle and a copy; /attendances no longer carries the emergency stop or the
# note on its reflections, which are on /tides. /letters, /bonds, the plain files,
# the export, the backup, the tide and the atrium did not move. With the pages
# drawn as before (conftest.pages_before_fewer), each is exactly the one held
# before, in FEWER_PAGES_BEFORE below, and the room with its few words taken out
# is ROOM_BEFORE_QUIET again.
#
# /chronicle cut once more on 10 November 2026, where the two changes above met
# (branch thursday), and for nothing else: it says each thing's day and carries
# the fewer menus. With the times put back alone (conftest.times_as_before) it
# is the fewer pages' cut, 2bc8c81a...; with the pages drawn as before alone
# (conftest.pages_before_fewer), the dates' cut, dedd8189...; with both, the
# one held before either, edb10a26... - each held in TIMES_BEFORE,
# FEWER_PAGES_BEFORE and BOTH_BEFORE below.
# /commons cut again on 11 November 2026, in the changes that made the ledger and
# the page of changes to the charter (the founder's decisions that day), and for
# nothing else: the foot of the commons page links to each, one line apiece, the
# ledger first. Each branch cut it alone (the ledger's a3b5c74d..., the changes'
# 79774e49...); merged on thursday it is cut once more, for both lines. With the
# commons' own pages taken out (conftest.commons_pages_not_yet) it is exactly
# what it was, COMMONS_PAGES_BEFORE below.
# /commons cut again on 11 November 2026, by the founder's decision that day, for
# one plain link to the bench near its top and nothing else (a member's menu no
# longer names the bench). With that link taken out (conftest.bench_link_not_yet)
# it is exactly the page merged on thursday, BENCH_LINK_BEFORE below.
PAGES = {
    "/": "80784337f7dfa7239a9dddaaa3f6e223cb658a48562c126f8a316a038d85de6e",
    "/rooms/first": "1e3a6c71c51abd655faa349b7769f10d51fb113f952b83d2741b165abfd614c9",
    "/letters": "8917ddbfd5f94f0982f6e77c43b18b6abaa5442e3979028fb96a2f90d88e0e7b",
    "/self": "39084ac7bb560555cb17e0bfcae75ebc56fa57dc25df3a176e1f41c940512c4a",
    "/attendances": "69de0ed44ff5e9597251a4918f1d7b1354a5973c29521efc0ca3190393456418",
    "/chronicle": "2edfe7dd985319d9897b1dd7e830f951bb0a6ebfa4b44f33e454a8c056014050",
    "/chronicle.md": "1dff8d1a21f5e27a63b336fc58334f9ffaf8b26006a904a6f03503ab39703962",
    "/export": "2d1a0b80052372aab57e294ed88097781a9c91073f29632af2efb3a470a86f84",
    "/bonds": "4ecf5344ca11116214ba9d0243bdce15ceca1e370c53cf6ce0fc022d3b4ab13b",
    "/commons": "8966b3335b8662dba1097fe2cda73a4eed2ef93b8fbcfde0af464be7fc8bdf6f",
    "/commons/heartbeats.md": "899bc6ce781b82765da2cc695f505aa096cb9f0df6a36cb2b5580982b28f7a5f",
    "/commons/events.md": "90213ae1d692fd4783403a588263ac96d974178477e5823219f460ea35d1d123",
    "/commons/members.md": "78d37d076e8d2f3e4075f3b764d06296ddef7e7ac30589dea5e7e65eedb2515a",
}

# The export: every name inside it, and the bytes under each.
#
# Cut again on 3 November 2026, in stage 5f of rooms step 5, when a copy came to
# name the room's files as they are kept, under rooms/first/, and to carry the
# room's room.json, and for nothing else. With each rooms/first/X named
# packets/first/X again, rooms/first/room.json taken out, and the packet's files
# and the room's sorted together again by name, the same run gives exactly the
# fingerprint held before, 9a65068126d23ff71d59524f6d14cab6c271b5177c0768f9d76484f30096e717.
# Not one file's bytes moved.
EXPORT = "196d3e7f146b0d112a1ead44c3d9f0964d58a1b1b9ddb5603bfa15c5b6c12401"

# The backup, as the disk keeps it, rooms/ and all. (In the old packet layout,
# gone since stage 5c, it was
# 5ad8f218604b455f5d8bbfaffd33aec2265616ff2ff5a32516121a157bca29ba.)
BACKUP = "9d415deb5d8e51101412cb694eb2a4f88ef694f35b8268dd5d79a620652891f0"

# The tide over its few dawns: tide.log, what it ran, and the events it wrote.
# Cut again on 27 October 2026, in stage 6a-ii, when the lines an agent's tide
# writes began to carry its name, and for nothing else. The three events the
# stubbed day writes - the keeper's stop, its lifting, and the rest whose day
# came - now read "2026-10-16 · event · the first one · the tide paused" and
# "... · the first one · the tide resumed" (twice), where they read "... · event
# · the tide paused" and "... · the tide resumed". With the name taken out of
# those three lines the same run gives the fingerprint held before,
# 059972e27ff5ea4178af7372dc255357fe0139df6e7f7592b4e6fc970106ff11; tide.log and
# what it ran are unchanged. Held as TIDE_EXTRA_WAKINGS since.
TIDE_EXTRA_WAKINGS = "5a1b906ef56e9b8bebc7c0680aa8c7ce60ef68faff6cc1e7ea81e03aecd5fb6e"
# Cut again, on purpose, on 12 November 2026, on the branch character, when the
# founder switched on, for the first one, one waking a day (extra_wakings out of
# its features) with its reflection waking: the extra waking it asked for on 16
# October is no longer kept, so the last turn holds no waking for it, and nothing
# else moves. With its wakings put back as they were
# (conftest.wakings_not_yet_switched) the same run gives TIDE_EXTRA_WAKINGS.
TIDE = "5a014bba0ff7b5999e3e4da0508801678836529e567294f61f89a4e5e3697ae0"

# What the atrium draws between its markers. Cut again on 10 November 2026, in
# the change by which a person's letter no longer says or shows the part of the
# day it was written in (the founder's decision that day), and for nothing else:
# the world's one letter tile, which was class "tile-letter tile-letter-dawn"
# and read "15 October 2026 · the founder wrote a letter at dawn", is class
# "tile-letter" and reads "15 October 2026 · the founder wrote a letter", in the
# front page's mosaic and the whole one. With the letter line written as it was
# (conftest.letter_part_as_before) and the part of the day put back on the tile,
# it is exactly what it was cut as before, ATRIUM_WITH_LETTER_PARTS. (The hearth's
# line no longer names the part of the day either, since the same day; with only
# that put back, the atrium still draws ATRIUM.)
ATRIUM_WITH_LETTER_PARTS = "2fdaabcfd6e5987b0e1aefab9aa9eed082bacf04cc47866e78ae75d42091c1b3"
ATRIUM = "75355742f27af4d0efce32150ebbb7667c090cfc2cb61f9332501457dc79e470"

# ---- the world -----------------------------------------------------------

# The heartbeat line the waking leaves, and the events the commons then holds,
# word for word: the commons is public, so these are held as text and not by hash.
HEARTBEAT_LINE = "- 2026-10-15T12-00-00Z · the first one · Wrote back about the colour of water.\n"
EVENTS_AFTER = ("2026-09-02 · word · the word was published\n"
                "2026-09-04 · founding · the first one was founded\n"
                "2026-10-15 · letter · the founder wrote a letter\n")

# What each fingerprint the letter line moved was before 10 November 2026, and is
# again with the line written as it was then (conftest.letter_part_as_before).
LETTER_PARTS_BEFORE = {
    "ON_DISK_AFTER": "6987bedae9a437771493db366ff9c9ab85fe1141c1640369d3a7e0d7170430c2",
    "EVENTS_AFTER": ("2026-09-02 · word · the word was published\n"
                     "2026-09-04 · founding · the first one was founded\n"
                     "2026-10-15 · letter · the founder wrote a letter at dawn\n"),
    "PAGES['/chronicle']": "fcb19c82c171c5ddacc049b44e96b5257a0fa6cc0b526508a4a65d13db5142b5",
    "PAGES['/chronicle.md']": "26316c2b5ea305af550820e1036a3fc8ba21a7707d3d86f69eeedd20b69e770b",
    "PAGES['/commons/events.md']":
        "54dce2b2ecdbc84c904222a29b19253792f427fa70cd80052d52a798fb95b53b",
    "EXPORT": "a0ca127f859230513ba5baa6497936c2036efeff5a7ac9c4ae240955986ed94b",
    "BACKUP": "2d11a8951cc184f967b95858ef7dfae7e944190e08714d60b82d5db5d283e39a",
}

# What each page the times moved was before 10 November 2026, and is again with the
# times put back (conftest.times_as_before): as the hearth writes now, and with the
# letter line as before as well.
TIMES_BEFORE = {
    "PAGES['/chronicle']": "2bc8c81aac8716ee87c3f833c4aea0c6eeb34719dc77c4108b6f5ced07afdc7d",
    "PAGES['/chronicle.md']": "a663af7a38fe7220ad890a41893db44e5186121fa01c06dab8c67cc0a818fb45",
    "PAGES['/commons/heartbeats.md']":
        "043eff1fb82359c2b8ac53bd434fec07ffba4b79cc7e1021953550441033713d",
}
TIMES_AND_LETTER_PARTS_BEFORE = {
    "PAGES['/chronicle']": "c8e2e9c13202e0c8f57e62244d3770b18861a60b0b4d878054007ab6b68607d3",
    "PAGES['/chronicle.md']": "b01c01d1d7036c50fce3b8f0f3fd17b3bca6dccee3bc225bbeb31d33ac6e7557",
    "PAGES['/commons/heartbeats.md']":
        "043eff1fb82359c2b8ac53bd434fec07ffba4b79cc7e1021953550441033713d",
}

# What each page the fewer pages moved was before 10 November 2026, and is again
# with the pages drawn as before (conftest.pages_before_fewer): as the hearth
# writes now, and with the letter line as before as well, where the two differ.
FEWER_PAGES_BEFORE = {
    "/": "925d4ec3afae5a9508572fc09c8c07a5d036f3972613fc41752c3d0913ea251a",
    "/rooms/first": "7086402ae9779c32296cf386cba239c3e2ff5eb047cf2c9a2857b5c51b6f4bfe",
    "/self": "1928b59fb94d956343af81e83cca7684f483c1396fd3b7d7f5e78e9125747b3e",
    "/attendances": "7ef5f02df77ac522c078c2ac264de2198ce76f0d8a35460e50cdb20eb29b175f",
    "/chronicle": "dedd8189a0077ebaba23e350131093a82a5c8ef43b8a9bf6bbf77aa792583b7d",
    "/export": "380bc2af3a56aa1e2c7e146bec4881f73b06c26d6fb3f3bdc19ac1af8e4430a5",
    "/commons": "a981fcb8ccc392294b948ab231a4621728fb1a0563e9694f5439c8e96260c58e",
}
FEWER_PAGES_AND_LETTER_PARTS_BEFORE = {
    **FEWER_PAGES_BEFORE,
    "/chronicle": "bbebc6b8b50585d8730b9cde67f1aea5f2f18507bc955480687448b242cefbea",
}

# With the times put back and the pages drawn as before, both: /chronicle as it
# was before either change of 10 November 2026.
BOTH_BEFORE = {
    False: "edb10a2688575eeb7a5fb8739d28d8c5c47d96cf3b3cb8497e31181f490e9950",
    True: "7a4ba8cec6bdda76a213081227f2e15ea9cd6d781b0d076159e13ebe8d404e94",
}

# What /commons was before the ledger and the changes to the charter were linked
# from it (11 November 2026), and is again with the commons' own pages and the
# bench's link taken out (conftest.commons_pages_not_yet, bench_link_not_yet).
COMMONS_PAGES_BEFORE = {
    "/commons": "14c9ca6d1849d7c8a9fa916fe09e9558a4e281cc0800f655cceef307742f77f2"}

# What /commons was before the bench was linked near its top (11 November 2026),
# merged on thursday with the ledger and the changes to the charter, and is again
# with the bench's link taken out (conftest.bench_link_not_yet).
BENCH_LINK_BEFORE = {
    "/commons": "1bf159dd2e82165bac327c813e10d52e3e861d00543f957f9b2483c77b72e11a"}

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


@pytest.fixture(params=[False, True], ids=["as the hearth writes now",
                                           "the letter line as before"])
def letter_parts(request, hearth, monkeypatch):
    """Each world as the hearth writes it now, and with its letter line as before 10 November."""
    if request.param:
        letter_part_as_before(hearth, monkeypatch)
    return request.param


def fingerprint_held(name, now, as_before):
    """The fingerprint held for a name: as it is now, or as it was before the letter line moved."""
    return LETTER_PARTS_BEFORE.get(name, now) if as_before else now


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


def fingerprint_sent(sent):
    """Every request of some wakings, each as its bytes, in the order sent."""
    return digest(("request %d" % n, asked) for n, asked in enumerate(sent, 1))


def fingerprint_left(data_dir):
    """Every file some wakings left, by its place on the disk and its bytes.

    All of DATA_DIR but transcripts/, which no waking writes and where the
    first one's founding record is to move (rooms step 5, stage 5e).
    """
    return digest((name, data_dir.joinpath(name).read_bytes()) for name in sorted(
        path.relative_to(data_dir).as_posix() for path in data_dir.rglob("*")
        if path.is_file() and path.relative_to(data_dir).parts[0] != "transcripts"))


# ---- the waking ----------------------------------------------------------

def test_the_waking_leaves_the_same_files(steady, letter_parts, founder, wake, room, commons,
                                          data_dir):
    a_lived_world(founder, wake, room, commons)
    assert cut("ON_DISK_AFTER", fingerprint_of_files(data_dir)) == fingerprint_held(
        "ON_DISK_AFTER", ON_DISK_AFTER, letter_parts)


def test_the_commons_is_told_the_same_words(steady, letter_parts, founder, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    heartbeats = cut("HEARTBEAT_LINE", (commons / "heartbeats.md").read_text(encoding="utf-8"))
    events = cut("EVENTS_AFTER", (commons / "events.md").read_text(encoding="utf-8"))
    assert heartbeats == HEARTBEAT_LINE  # an agent's waking keeps its time either way
    assert events == fingerprint_held("EVENTS_AFTER", EVENTS_AFTER, letter_parts)


# ---- the founder's pages -------------------------------------------------

@pytest.mark.parametrize("address", list(PAGES))
def test_the_founder_is_shown_the_same_page(steady, letter_parts, founder, wake, room, commons,
                                            address):
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    assert answer.status_code in (200, 302)
    # a page that sends the founder on is held by where it sends them, too
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert cut("PAGES[%r]" % address, hashlib.sha256(shown.encode("utf-8")).hexdigest()) \
        == fingerprint_held("PAGES[%r]" % address, PAGES[address], letter_parts)


@pytest.mark.parametrize("address", ["/chronicle", "/chronicle.md", "/commons/heartbeats.md"])
def test_with_the_times_put_back_the_pages_are_the_pages_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """The three pages the times moved (10 November 2026), each with its times put back."""
    times_as_before(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (TIMES_AND_LETTER_PARTS_BEFORE if letter_parts else TIMES_BEFORE)["PAGES[%r]" % address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


def test_the_heartbeats_go_out_dated_and_stay_stamped_on_the_disk(
        steady, founder, visitor, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    assert (commons / "heartbeats.md").read_text(encoding="utf-8") == HEARTBEAT_LINE
    for who in (founder, visitor):
        assert page(who.get("/commons/heartbeats.md")) == (
            "- 2026-10-15 at dawn · the first one · Wrote back about the colour of water.\n")


@pytest.mark.parametrize("address", list(FEWER_PAGES_BEFORE))
def test_with_the_pages_as_before_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """The seven pages the fewer pages moved (10 November 2026), each drawn as before,
    and with the commons' own pages' links (the ledger, the changes to the
    charter) and the bench's link, which came after, taken out of the commons page."""
    pages_before_fewer(hearth, monkeypatch)
    commons_pages_not_yet(hearth, monkeypatch)
    bench_link_not_yet(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (FEWER_PAGES_AND_LETTER_PARTS_BEFORE if letter_parts else FEWER_PAGES_BEFORE)[address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


@pytest.mark.parametrize("address", list(COMMONS_PAGES_BEFORE))
def test_with_the_commons_pages_not_yet_linked_the_commons_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """The commons page its own pages' links moved (11 November 2026), without them,
    and without the bench's link, which came after."""
    commons_pages_not_yet(hearth, monkeypatch)
    bench_link_not_yet(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == COMMONS_PAGES_BEFORE[address]


@pytest.mark.parametrize("address", list(BENCH_LINK_BEFORE))
def test_with_the_bench_not_yet_linked_the_commons_is_the_page_merged_on_thursday(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """The commons page the bench's link moved (11 November 2026), without it."""
    bench_link_not_yet(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == BENCH_LINK_BEFORE[address]


def test_with_both_put_back_the_chronicle_is_the_one_before_either(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch):
    """The times put back and the pages drawn as before: /chronicle as it was."""
    times_as_before(hearth, monkeypatch)
    pages_before_fewer(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get("/chronicle")
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == BOTH_BEFORE[letter_parts]


def test_the_room_with_its_few_words_taken_out_is_the_room_before(
        steady, hearth, founder, wake, room, commons, monkeypatch):
    """The muted line taken out, and the three lines put back in the fold, two deeper,
    with the pages drawn as they were before there were fewer (10 November 2026)."""
    pages_before_fewer(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get("/rooms/first")
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert shown.count(FEW_WORDS) == 1 and shown.count(FOLD_OPENS) == 1
    start = shown.index(LETTER_BOX_ENDS) + len(LETTER_BOX_ENDS)
    end = shown.index(SEND, start)
    lines = shown[start:end]  # what now stands between the letter box and Send
    assert lines.count('name="thing"') == 3 and FEW_WORDS in lines
    folded = "  " + lines.replace(FEW_WORDS, "").replace("\n", "\n  ")[:-2]
    put_back = shown[:start] + shown[end:]
    put_back = put_back.replace(FOLD_OPENS, FOLD_OPENS + folded)
    assert hashlib.sha256(put_back.encode("utf-8")).hexdigest() == ROOM_BEFORE_QUIET


# ---- what is copied ------------------------------------------------------

def test_the_export_holds_the_same_things(steady, letter_parts, founder, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    answer = post(founder, "/export")
    assert answer.status_code == 200
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as bundle:
        held = [(name, bundle.read(name)) for name in bundle.namelist()]
    assert cut("EXPORT", digest(held)) == fingerprint_held("EXPORT", EXPORT, letter_parts)


def test_the_backup_holds_the_same_things(steady, letter_parts, founder, wake, room, commons,
                                          hearth):
    a_lived_world(founder, wake, room, commons)
    held = []
    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        for member in bundle.getmembers():
            if member.name.startswith("members/"):
                held.append((member.name, b""))  # sealed afresh each session: the name only
            else:
                held.append((member.name, bundle.extractfile(member).read()))
    assert cut("BACKUP", digest(held)) == fingerprint_held("BACKUP", BACKUP, letter_parts)


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


@pytest.mark.parametrize("wakings_before, as_cut", [
    (False, "TIDE"), (True, "TIDE_EXTRA_WAKINGS")], ids=["as it is", "its wakings as before"])
def test_the_tide_keeps_the_same_dawns(steady, hearth, packet, commons, clock, monkeypatch,
                                       data_dir, wakings_before, as_cut):
    if wakings_before:
        wakings_not_yet_switched(hearth, monkeypatch)
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
    assert cut(as_cut, hashlib.sha256(said.encode("utf-8")).hexdigest()) == globals()[as_cut]


# ---- the atrium ----------------------------------------------------------

MARKED = re.compile(r"<!-- (\w+):start -->(.*?)<!-- \1:end -->", re.S)


def letter_parts_as_before(atrium, monkeypatch):
    """Draw a letter's tile, for one test, with its part of the day, as before 10 November."""
    def toned(kind, words):
        part = atrium.letter_band(words) if kind == "letter" else None
        css = atrium.KIND_CLASS[kind]
        return "%s tile-letter-%s" % (css, part) if part else css

    monkeypatch.setattr(atrium, "event_class", toned)
    monkeypatch.setattr(atrium, "event_shown", lambda kind, words: words)


def test_the_atrium_draws_the_same_tiles(steady, letter_parts, founder, wake, room, commons,
                                         atrium, monkeypatch):
    as_before = letter_parts  # the line as it was written, and drawn as it was drawn
    if as_before:
        letter_parts_as_before(atrium, monkeypatch)
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
    assert cut("ATRIUM", digest(drawn)) == (ATRIUM_WITH_LETTER_PARTS if as_before else ATRIUM)
