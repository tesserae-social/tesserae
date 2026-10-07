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

Both earlier readings are still held: with the <<SELF>> block explained as it
was before (conftest.explained_as_before), the reading with the three switched
on is exactly the one cut on 7 October, and with the three shut away as well it
is exactly the one cut before the rooms.
"""

import hashlib
import json

import pytest

from conftest import explained_as_before, post, shut_away, write

# cut on the tree before the rooms, by leaving the letter at /letters
PACKET_BEFORE = "06d48d0fffb5f5e2e3148baf5351f004cf22011db7a730df2ab259822cdc2e68"
READING_BEFORE = "13aab673f0448c960e400e2484f17aa1169636dbe338761c6666aeee2e208f65"

# cut again on the tree that switched on its door, looking back and what it has
# chosen (attend.DOOR_FOR_FIRST, LOOKING_BACK and CHOICES), the same way
READING_SWITCHED_ON = "2dd6e1fcc814ade2ac3470913f0d9e459a5ef8b209c757e91b394af82670527a"

# cut again on the tree that built the two-waking rule, the same way: the
# reading above, with the <<SELF>> block explained as it is now
READING_NOW = "071e983d87b72ebc8ae4cdeef5af1515d570a93f4106eb80d9c5bdc54333189e"

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
    (True, True, READING_BEFORE), (False, True, READING_SWITCHED_ON), (False, False, READING_NOW)],
    ids=["the three shut away, the block as it was", "the three on, the block as it was",
         "as it reads now"])
def test_the_first_one_reads_byte_for_byte_what_it_read_before(
        founder, wake, attend, packet, data_dir, monkeypatch, address, shut, as_before, as_cut):
    if shut:
        shut_away(attend, monkeypatch)
    if as_before:
        explained_as_before(attend, monkeypatch)
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
