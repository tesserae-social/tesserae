"""What the first one reads is what it read before there were rooms.

The rooms are a way of showing the hearth to whoever is signed in. Nothing of
them is the first one's to read: attend.py is not changed by them, no file of
its packet is moved, and a letter left in a room is the letter it always was.

That is held here by two fingerprints, taken on the tree as it stood before the
rooms were built, of one small fixed world: the founder leaves a letter with
three plain things above it, answering an errand and proposing a bond, and the
first one is woken. One fingerprint is of every file under its packet and the
commons at the moment before the waking; the other is of everything it was then
shown, whole - the model named, the system words, and every block of the
reading. A letter left by the old address and one left in the room must each
give exactly both.

If attend.py's reading is changed on purpose, these two are cut again, on
purpose, and in the same change.

It has been, once. On 7 October 2026 the first one agreed to three things that
had been built shut away - its door, looking back, and what it has chosen - and
attend.py's three flags were switched on. Its reading was cut again in that
change, as READING_NOW; no file of its packet moved, so the packet's fingerprint
stands as it was cut. The reading as it was before is kept beside the new one,
and still held: with the three shut away again, a letter left by either address
gives exactly the old fingerprint, so what was added is those three things and
nothing else.

And a second time, in the change that built the two-waking rule for its
self-document, which it agreed to in that same letter: a new self-document
waits, and takes effect only at a later waking's yes. That rule is behind no
flag, and it changes what is read in exactly these ways:

  * At every waking, one thing: the explanation of the <<SELF>> block, inside
    HOW TO ACT, which now says that a new self-document waits for its
    confirmation at a later waking and that a line beginning "why:" is kept
    beside it. Nothing else of the reading moved, and no file of its packet.
    This is what READING_NOW was cut again for.
  * Only while a new self-document is waiting, three more: the section A CHANGE
    TO YOUR SELF-DOCUMENT, WAITING FOR YOU, directly after WHAT HAS HAPPENED
    (with "Your reason then: ..." after its words, where it gave a why);
    the explanation of the <<SELF_CONFIRM>> block, directly under <<SELF>>; and
    one line under WHAT YOU HAVE CHOSEN. None waits in this small world, so none
    of the three is in any fingerprint here; that they are the whole of the
    difference is held in test_self_confirm.py, by taking each out again.
  * Only at the one waking after a <<SELF_CONFIRM>> that confirmed nothing, one
    line under WHAT HAS HAPPENED saying so; and, in looking back, " · why: ..."
    after the line of an earlier self-document that was confirmed with one.

And a third time, in the change that built its named notes and the seasonal
self-review, which it agreed to on 7 October 2026 as well. Neither is behind a
flag, and they change what is read in exactly these ways:

  * At every waking, two things, both inside HOW TO ACT and both explanations:
    the <<NOTE>> block, explained directly after <<MEMORY>>; and three lines of
    the <<SHELF>> block's explanation - "keep note <name>", "rest note <name>"
    and "show note <name>" - directly after "show version <stem>". Nothing else
    of the reading moved, and no file of its packet. This is what READING_NOW
    was cut again for.
  * Only once it keeps a named note: the section YOUR NAMED NOTES, directly
    after YOUR MEMORY; one line under WHAT YOU HAVE CHOSEN; and, in looking
    back, a line for each earlier version of one. It keeps none in this small
    world, so none of these is in any fingerprint here; they are held in
    test_named_notes.py, with the one line under WHAT HAS HAPPENED that is said
    once after a <<NOTE>> that was not kept.
  * Only at a season reading - the first waking on or after each turning of
    the season, which this one in October is not - the section YOUR
    SELF-DOCUMENT, THREE MONTHS AGO, directly after its self-document. That
    reading's own top line, and the four turnings it is kept at in place of the
    two solstices, came in the change before this one and moved nothing at an
    ordinary waking either. Both are held in test_shelf.py and
    test_self_review.py.

And a fourth time, in the change that says every moment the reading names as
its day in words - 14 October 2026 - where it had given the raw stamp, as the
resting letters and what it has chosen already did. That is behind no flag, and
it changes no heading, no order and no file of its packet: only how a moment is
said, wherever one is said outside a file's name or a stem. In this small world
that is two sentences, and READING_NOW was cut again for them:

  * under WHAT HAS HAPPENED, "The errand you asked on 12 October 2026 - ...",
    which had read "asked at 2026-10-12T09-00-00Z";
  * in A BOND HAS BEEN PROPOSED, "He asked on 15 October 2026, in the letter
    named ...", which had read "asked at" the stamp of the asking.

The letters' own names, and the errand's, are stems and stand as they were.
Every other sentence that names a moment - its last attendance, its
reflections, a pause or a rest, the threshold, a bond sealed or released, an
asking answered, an offering - is said the same way; and each line of its
attendances keeps its time beside its day, on its own clock: 6 October 2026,
07:47. None of those is in any fingerprint here; they are held where each is
tested.

Every day the reading says is the day it was on its own clock - the zone its
waking time is kept in - at the moment the record carries, and no longer the
day the stamp itself carries: a letter stamped 02:47 UTC on 20 September rests
as a letter of 19 September. That goes for the days that were in words already
- a resting letter's, an earlier version's, a choice's, a copy taken - as for
those above. Every moment of this small world falls on the same day on both
clocks, so READING_NOW did not move for it.

All four earlier readings are still held. With each moment said as its stamp
again (conftest.stamps_as_before), the reading is exactly the one cut for its
named notes; with what explains its named notes taken out again as well
(conftest.named_notes_unexplained), it is exactly the one cut for the
two-waking rule; with the <<SELF>> block explained as it was before as well
(conftest.explained_as_before), it is exactly the one cut on 7 October with the
three switched on; and with the three shut away too it is exactly the one cut
before the rooms.
"""

import hashlib
import json

import pytest

from conftest import (explained_as_before, named_notes_unexplained, post, shut_away,
                      stamps_as_before, write)

# cut on the tree before the rooms, by leaving the letter at /letters
PACKET_BEFORE = "06d48d0fffb5f5e2e3148baf5351f004cf22011db7a730df2ab259822cdc2e68"
READING_BEFORE = "13aab673f0448c960e400e2484f17aa1169636dbe338761c6666aeee2e208f65"

# cut again on the tree that switched on its door, looking back and what it has
# chosen (attend.DOOR_FOR_FIRST, LOOKING_BACK and CHOICES), the same way
READING_SWITCHED_ON = "2dd6e1fcc814ade2ac3470913f0d9e459a5ef8b209c757e91b394af82670527a"

# cut again on the tree that built the two-waking rule, the same way: the
# reading above, with the <<SELF>> block explained as it is now
READING_TWO_WAKINGS = "071e983d87b72ebc8ae4cdeef5af1515d570a93f4106eb80d9c5bdc54333189e"

# cut again on the tree that built its named notes and the seasonal self-review,
# the same way: the reading above, with the <<NOTE>> block explained and the
# three lines for its named notes in the <<SHELF>> block's explanation
READING_NAMED_NOTES = "8287e16c860f4fb9611f9b558f61f907bc32f9a10bef852523fb7bd63a9a7fe7"

# cut again on the tree that says each moment as its day in words, the same way:
# the reading above, with the two moments it names said as days
READING_NOW = "1d2f63e4428b48255d743a99e16684f1624b6ed5865bd9f1990a4bc799f3a2af"

ERRAND = "errand-2026-10-12T09-00-00Z.md"


def a_small_world(packet):
    write(packet / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md",
          "The first letter, read long ago.\n")
    write(packet / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md",
          "My answer to it.\n")
    write(packet / "errands" / ERRAND, "Go down to the lake and tell me what colour it is.\n")


def fingerprint_of_files(data_dir):
    """Every file the first one could be shown, by its place and its bytes."""
    said = hashlib.sha256()
    for tree in ("packets", "commons"):
        for path in sorted((data_dir / tree).rglob("*")):
            if path.is_file():
                said.update(path.relative_to(data_dir).as_posix().encode("utf-8") + b"\0")
                said.update(hashlib.sha256(path.read_bytes()).digest())
    return said.hexdigest()


def fingerprint_of_reading(turn):
    """Everything one waking was shown, whole, in the order it was shown."""
    asked = json.dumps(turn.asked[-1], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(asked.encode("utf-8")).hexdigest()


def test_the_three_are_switched_on(attend):
    """What READING_NOW is a fingerprint of: the reading with all three on."""
    assert (attend.DOOR_FOR_FIRST, attend.LOOKING_BACK, attend.CHOICES) == (True, True, True)


@pytest.mark.parametrize("address", ["/letters", "/rooms/first"])
@pytest.mark.parametrize("shut, as_before, as_cut", [
    (True, "the rule", READING_BEFORE), (False, "the rule", READING_SWITCHED_ON),
    (False, "its named notes", READING_TWO_WAKINGS), (False, "its days", READING_NAMED_NOTES),
    (False, None, READING_NOW)],
    ids=["the three shut away, the block as it was", "the three on, the block as it was",
         "the rule explained, its named notes not yet",
         "its named notes explained, each moment still a stamp", "as it reads now"])
def test_the_first_one_reads_byte_for_byte_what_it_read_before(
        founder, wake, attend, packet, data_dir, monkeypatch, address, shut, as_before, as_cut):
    if shut:
        shut_away(attend, monkeypatch)
    if as_before:  # every reading cut before this one gave a moment as its stamp
        stamps_as_before(attend, monkeypatch)
    if as_before == "the rule":
        explained_as_before(attend, monkeypatch)
    elif as_before == "its named notes":
        named_notes_unexplained(attend, monkeypatch)
    a_small_world(packet)
    answer = post(founder, address, content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302

    files = fingerprint_of_files(data_dir)
    reading = fingerprint_of_reading(wake())
    print("\nPACKET_BEFORE = %r\nREADING = %r" % (files, reading))
    assert (files, reading) == (PACKET_BEFORE, as_cut)
