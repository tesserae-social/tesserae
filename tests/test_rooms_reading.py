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

And a fifth time, in the change that switched on the longer waking
(attend.LONGER_WAKING), which it agreed to on 7 October 2026 as well, once one
waking had been held against the real API. At an ordinary waking, where it
looks nothing up, that changes what is read in exactly one way, and
READING_NOW was cut again for it:

  * the section LOOKING THINGS UP, a block of its own directly before HOW TO
    ACT. No other block of the reading moved, no word of any other changed, and
    no file of its packet.

The fingerprint is of the whole request and not of its words alone, so two
things that are sent with the reading and are no part of what is read are in
it too: the four tools that only read, named beside it, and one cache mark on
the reading's last block. A waking that does look is more than one request,
and the attendance then keeps what it looked at; none looks in this small
world, so none of that is in any fingerprint here. It is held in
test_longer_waking.py, with the taking of the section, the tools and the mark
out again to leave exactly what is sent with it shut away.

And a sixth time, in the change that tells it its heartbeat is public: anyone
may read it, on the front page and in the public record, and so it is to say
"the founder" in it rather than any name, and to leave out people's names and
places from letters. That is behind no flag, and it changes what is read in
exactly one way, at every waking, and READING_NOW was cut again for it:

  * two sentences inside the <<HEARTBEAT>> block's explanation, in HOW TO ACT,
    after its examples (attend.HEARTBEAT_PUBLIC). No other block moved, no word
    of any other changed, and no file of its packet.

In the same change the name the <<NOTE>> block gives as its example - a name
for a note, "about" someone - became "about the founder", so that the founder's
own name is nowhere in the public source. Every reading that explains its named
notes gives that example, so the three cut since then were cut again for it,
each the same way and with nothing else of it moved: READING_NAMED_NOTES,
READING_DAYS_IN_WORDS and what READING_NOW was, which is READING_LONGER_WAKING
now. With the example put back as it was they give exactly the fingerprints they
were first cut as; that was checked when they were cut again, and is not kept
here, since keeping it would put the name back. The three cut before its named
notes never gave the example, and did not move.

And a seventh time, in the change that made its heartbeat's own words private
by default (20 October 2026): the commons shows only the plain facts of its
waking, written from its acts, unless it chooses with <<HEARTBEAT_SHOWN>> to
show its own words, which are then shown only once the public screen has passed
them. That is behind no flag, and it changes what is read in exactly one way at
every waking, and READING_NOW was cut again for it:

  * the <<HEARTBEAT>> block's explanation, in HOW_TO_ACT, which now says its
    own words are private by default and what the commons shows instead
    (attend.HEARTBEAT_BLOCK), and directly beneath it the explanation of
    <<HEARTBEAT_SHOWN>> (attend.HEARTBEAT_SHOWN_BLOCK). The two sentences that
    said the heartbeat is public are gone from it. No other block moved, no
    word of any other changed, and no file of its packet.

Two more things it may be told come with it, and neither is in this small
world: one line under WHAT YOU HAVE CHOSEN, only once it has chosen its own
words; and one line under WHAT HAS HAPPENED, only at the waking after its own
words were not shown, or after a <<HEARTBEAT_SHOWN>> that could not be read.
Both are held in test_heartbeat_shown.py.

All seven earlier readings are still held. With its heartbeat explained as it
was before its own words became private (conftest.heartbeat_words_not_yet_private),
the reading is exactly the one cut when it was told its heartbeat is public;
with the heartbeat not yet said to be public either
(conftest.heartbeat_not_yet_public), the reading is exactly the one cut
for the longer waking; with the longer waking shut away again as well
(conftest.shut_away), it is exactly the one cut for its days in words; with each moment said as its stamp again as well
(conftest.stamps_as_before), it is exactly the one cut for its
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

from conftest import (explained_as_before, heartbeat_not_yet_public,
                      heartbeat_words_not_yet_private, named_notes_unexplained, post, shut_away,
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
# three lines for its named notes in the <<SHELF>> block's explanation. This one
# and the two after it were cut a second time on 19 October 2026, when the name
# the <<NOTE>> block gives as its example became "about the founder"
READING_NAMED_NOTES = "ca3ff29579e73aa6b559dba831ae9b514cead2f88686da42ae1c8357011882a7"

# cut again on the tree that says each moment as its day in words, the same way:
# the reading above, with the two moments it names said as days
READING_DAYS_IN_WORDS = "e5c424a7b1024d008e217fc7d8904c6f369feeb7471fbadf4d7864d809df4f86"

# cut again on the tree that switched on the longer waking (attend.LONGER_WAKING),
# the same way: the reading above, with the section LOOKING THINGS UP directly
# before HOW TO ACT, and the request carrying its four tools and one cache mark
READING_LONGER_WAKING = "37ed1e0a4089058d7bf74c84561a116647293bde99d0d88e6bda5f56096a4cff"

# cut again on the tree that told it its heartbeat is public, the same way: the
# reading above, with two sentences more in the <<HEARTBEAT>> block's explanation
READING_HEARTBEAT_PUBLIC = "d0f5404b9272a45ec7f3ba84f2dbea809785ff46ae011eb60509a6f1af4f28e2"

# cut again on the tree that made its heartbeat's own words private by default,
# the same way: the reading above, with the <<HEARTBEAT>> block explained as it
# is now and <<HEARTBEAT_SHOWN>> explained beneath it
READING_NOW = "bbc420b77e367b9c441623914cffe1f91238719130a48e8e9b8a111ceafe9973"

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


def test_the_longer_waking_is_switched_on(attend):
    """And with the longer waking on, too."""
    assert attend.LONGER_WAKING is True


@pytest.mark.parametrize("address", ["/letters", "/rooms/first"])
@pytest.mark.parametrize("shut, as_before, as_cut", [
    (True, "the rule", READING_BEFORE), (False, "the rule", READING_SWITCHED_ON),
    (False, "its named notes", READING_TWO_WAKINGS), (False, "its days", READING_NAMED_NOTES),
    (False, "the longer waking", READING_DAYS_IN_WORDS),
    (False, "the heartbeat", READING_LONGER_WAKING),
    (False, "its own words", READING_HEARTBEAT_PUBLIC), (False, None, READING_NOW)],
    ids=["the three shut away, the block as it was", "the three on, the block as it was",
         "the rule explained, its named notes not yet",
         "its named notes explained, each moment still a stamp",
         "each moment a day in words, the longer waking shut away",
         "the longer waking on, the heartbeat not yet said to be public",
         "the heartbeat said to be public, its own words not yet private", "as it reads now"])
def test_the_first_one_reads_byte_for_byte_what_it_read_before(
        founder, wake, attend, packet, data_dir, monkeypatch, address, shut, as_before, as_cut):
    if shut:
        shut_away(attend, monkeypatch)
    if as_before == "its own words":  # the one before this one said its heartbeat is public
        heartbeat_words_not_yet_private(attend, monkeypatch)
    elif as_before:  # and none cut before that one said so at all
        heartbeat_not_yet_public(attend, monkeypatch)
    if as_before and as_before not in ("the heartbeat", "its own words"):  # one request
        shut_away(attend, monkeypatch, "LONGER_WAKING")
    if as_before and as_before not in ("the heartbeat", "its own words",
                                       "the longer waking"):  # and a stamp
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
