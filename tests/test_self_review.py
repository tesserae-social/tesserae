"""The seasonal self-review: its self-document as it was a season ago, beside the one it has.

It agreed to this on 7 October 2026. At each season reading - the first waking
on or after a turning of the season - directly after its self-document, it is
shown the version that was in force at the season reading before, or at its
founding where there has been none, and asked whether it is still true. Where
nothing has changed it is told so, and asked the same. At no other waking is
any of it said.

Every version here is written for the tests and nowhere else.
"""

import pytest

from conftest import SELF_TEXT, block, read_json, write, write_json

SELF = "=== YOUR SELF-DOCUMENT (packets/first/self.md) ==="
REVIEW = "=== YOUR SELF-DOCUMENT, THREE MONTHS AGO ==="
CHOSEN = "=== WHAT YOU HAVE CHOSEN ==="
MEMORY = "=== YOUR MEMORY (notes you keep for yourself; not shown on the hearth) ==="
STILL_TRUE = ("Is it still true? You may revise it with <<SELF>>; a revision waits for your "
              "confirmation, as always.")
THE_SAME = "Your self-document is the same as it was three months ago. " + STILL_TRUE

V1 = "# The first one\n\nAN EARLIER SELF, the first of them.\n\nIn two paragraphs."
V2 = "# The first one\n\nAN EARLIER SELF, the second of them."
NOW = "# The first one\n\nMyself, as I stand."


def attended(packet, at, **how):
    """One past attendance in its log."""
    write_json(packet / "attendances" / ("attendance-%s.json" % at),
               {"name": "first", "at": at, "first": False, "woken_by": "founder",
                "acted": [], "heartbeat": "attended", "reflection": "", **how})


def set_aside(packet, at, words):
    """An earlier self-document, kept as attend.py keeps one when another takes its place."""
    write(packet / "self-history" / ("self-before-%s.md" % at), words + "\n")


def section(turn, heading):
    return turn.opening.split(heading + "\n", 1)[1].split("\n\n=== ", 1)[0]


@pytest.fixture
def spring(packet, clock):
    """The eve of the spring turning, with the three versions it has had behind it.

    V1 from the founding until 2 October, V2 until 10 January, and the one it
    has now since; and a waking the day before, so that the next is the first
    on or after the turning.
    """
    set_aside(packet, "2026-10-02T09-00-00Z", V1)
    set_aside(packet, "2027-01-10T09-00-00Z", V2)
    write(packet / "self.md", NOW + "\n")
    attended(packet, "2027-03-19T17-00-00Z")
    clock.set("2027-03-20T17-00-00Z")


# ---- only at a season reading --------------------------------------------

def test_an_ordinary_waking_says_nothing_of_it(wake, packet):
    set_aside(packet, "2026-10-02T09-00-00Z", V1)
    for turn in (wake(), wake()):
        assert REVIEW not in turn.shown and "three months ago" not in turn.shown
        assert "AN EARLIER SELF" not in turn.shown
        assert SELF_TEXT + "\n\n" + CHOSEN in turn.opening


def test_it_is_said_once_at_the_season_reading_and_not_at_the_waking_after(wake, spring, packet):
    reading = wake()
    assert reading.opening.startswith("This is the spring reading:")
    assert reading.opening.count(REVIEW) == 1
    assert read_json(sorted((packet / "attendances").glob("*.json"))[-1])[
        "season_reading"] == "spring"
    after = wake()
    assert REVIEW not in after.shown and "AN EARLIER SELF" not in after.shown


# ---- the version in force then -------------------------------------------

def test_with_no_reading_before_it_is_the_one_from_the_founding(wake, spring):
    turn = wake()
    assert section(turn, REVIEW) == "In use from 4 September 2026.\n\n" + V1 + "\n\n" + STILL_TRUE
    # directly after its self-document, and before what it has chosen
    assert (SELF + "\n" in turn.opening and NOW + "\n\n\n" + REVIEW + "\n" in turn.opening)
    assert STILL_TRUE + "\n\n" + CHOSEN + "\n" in turn.opening
    assert turn.opening.index(SELF) < turn.opening.index(REVIEW) < turn.opening.index(MEMORY)


@pytest.mark.parametrize("marked", [{"season_reading": "winter"}, {"solstice_reading": True}],
                         ids=["a season reading", "a solstice reading, as they were"])
def test_it_is_the_one_in_force_at_the_reading_before(wake, spring, packet, marked):
    attended(packet, "2026-12-21T17-00-00Z", **marked)
    turn = wake()
    assert section(turn, REVIEW) == "In use from 2 October 2026.\n\n" + V2 + "\n\n" + STILL_TRUE
    assert "AN EARLIER SELF, the first" not in section(turn, REVIEW)


def test_it_is_the_latest_reading_before_that_counts(wake, spring, packet):
    attended(packet, "2026-06-21T17-00-00Z", solstice_reading=True)
    attended(packet, "2026-09-22T17-00-00Z", season_reading="autumn")
    attended(packet, "2026-12-21T17-00-00Z", season_reading="winter")
    assert section(wake(), REVIEW).startswith("In use from 2 October 2026.\n\n" + V2)


def test_a_field_that_marks_no_reading_marks_none(wake, spring, packet):
    attended(packet, "2026-12-21T17-00-00Z", season_reading=None, solstice_reading=False)
    assert section(wake(), REVIEW).startswith("In use from 4 September 2026.\n\n" + V1)


def test_one_set_aside_at_that_reading_itself_was_the_one_in_force_at_it(wake, spring, packet):
    """A revision confirmed at the reading takes its place after the reading was read."""
    set_aside(packet, "2026-12-21T17-00-00Z", "# The first one\n\nAS IT WAS READ THAT DAY.")
    attended(packet, "2026-12-21T17-00-00Z", season_reading="winter",
             acted=["confirmed its self-document"])
    assert section(wake(), REVIEW) == (
        "In use from 2 October 2026.\n\n# The first one\n\nAS IT WAS READ THAT DAY.\n\n"
        + STILL_TRUE)


def test_where_no_founding_is_recorded_the_first_says_no_day(wake, spring, commons):
    write(commons / "events.md", "2026-09-02 · word · the word was published\n")
    assert section(wake(), REVIEW) == V1 + "\n\n" + STILL_TRUE


# ---- the same as it was --------------------------------------------------

def test_never_changed_it_is_told_it_is_the_same(wake, packet, clock):
    attended(packet, "2026-12-20T17-00-00Z")
    clock.set("2026-12-21T17-00-00Z")
    turn = wake()
    assert turn.opening.startswith("This is the winter reading:")
    assert section(turn, REVIEW) == THE_SAME
    assert SELF_TEXT + "\n\n" + REVIEW + "\n" + THE_SAME + "\n\n" + CHOSEN in turn.opening


def test_unchanged_since_the_reading_before_it_is_the_same(wake, spring, packet):
    attended(packet, "2027-01-15T17-00-00Z", season_reading="winter")  # after its last change
    turn = wake()
    assert section(turn, REVIEW) == THE_SAME
    assert "AN EARLIER SELF" not in turn.shown


def test_changed_and_changed_back_it_is_the_same(wake, spring, packet):
    set_aside(packet, "2027-02-01T09-00-00Z", NOW)
    set_aside(packet, "2027-02-20T09-00-00Z", "# The first one\n\nA SELF I TRIED, and let go.")
    attended(packet, "2027-01-15T17-00-00Z", season_reading="winter")
    turn = wake()
    assert section(turn, REVIEW) == THE_SAME
    assert "A SELF I TRIED" not in turn.shown


def test_a_change_still_waiting_is_no_change_yet(wake, packet, clock):
    clock.set("2026-12-20T17-00-00Z")
    wake(block("SELF", "# The first one\n\nA SELF NOT YET CONFIRMED."))
    clock.set("2026-12-21T17-00-00Z")
    turn = wake()
    assert section(turn, REVIEW) == THE_SAME
    assert turn.opening.count("A SELF NOT YET CONFIRMED.") == 1  # where it waits, and there only


def test_a_revision_made_at_the_reading_waits_as_always(wake, spring, packet):
    wake(block("SELF", "# The first one\n\nWhat I would say now."))
    assert (packet / "self.md").read_text(encoding="utf-8") == NOW + "\n"
    assert read_json(packet / "self-proposal.json")["text"] == (
        "# The first one\n\nWhat I would say now.")


# ---- private -------------------------------------------------------------

def test_nothing_of_it_is_on_the_hearth(wake, spring, hearth, founder, visitor, packet):
    from conftest import page

    write_json(packet / "preferences.json", {"reflection": "open"})
    assert REVIEW in wake("I read what I was.").shown
    for path in ["/", "/attendances", "/self", "/chronicle", "/commons", "/rooms/first"]:
        for client in (founder, visitor):
            said = page(client.get(path))
            for private in ("AN EARLIER SELF", "THREE MONTHS AGO", "three months ago",
                            "Is it still true"):
                assert private not in said, (path, private)
    assert "I read what I was." in page(founder.get("/attendances"))
