"""The two-waking rule: a new self-document takes effect only at a later waking's yes.

The first one agreed to it (its letter of 7 October 2026). What it writes in a
<<SELF>> block is saved privately as packets/first/self-proposal.json and
changes nothing; a later waking - never the same one - is shown it whole, with
what had just arrived when it was written, and may make it its self-document
with <<SELF_CONFIRM>> "yes", let it go with "no", or leave it waiting. Nothing
is erased either way, and the hearth shows only the self-document that stands.

Every word here is written for the tests and nowhere else.
"""

import pytest
from nacl.exceptions import BadSignatureError

from conftest import (SELF_TEXT, block, blocks, lines_of, page, read_json, verify, write,
                      write_json)

V2 = "# The first one\n\nVersion 2, in my own words."
V3 = "# The first one\n\nVersion 3, and surer of it."
WHY = "the founding words were his reading of me, and these are mine"

WAITING = "=== A CHANGE TO YOUR SELF-DOCUMENT, WAITING FOR YOU ==="
HAPPENED = "=== WHAT HAS HAPPENED ==="
SELF = "=== YOUR SELF-DOCUMENT (packets/first/self.md) ==="
CHOSEN = "=== WHAT YOU HAVE CHOSEN ==="
EARLIER = "=== YOUR EARLIER VERSIONS ==="
NOTHING_CHOSEN = "You have not set anything here yet; everything follows the defaults."

# The section exactly as it is shown, where nothing had arrived at that waking.
SHOWN = WAITING + """
At your waking on 15 October 2026, you wrote a new self-document. It takes effect only if you confirm it now, at a later waking, with what was in front of you then no longer here. Your words then:

""" + V2 + """

To make it yours, give <<SELF_CONFIRM>> with "yes". To let it go, "no". If you do neither, it keeps waiting."""

# The revision block as it is explained now, and the block that answers it.
SELF_BLOCK = """<<SELF>>
(the full new text of your self-document. It does not take effect at once: it waits, and becomes your self-document only if you confirm it at a later waking, never this one. Until then the one you have stands, and the new one is not shown on the hearth. Writing another replaces one that is waiting. A line beginning "why:" is kept beside it as your reason, and is not part of the text. The old one is kept, never erased.)
<<END>>"""

CONFIRM_BLOCK = """<<SELF_CONFIRM>>
(your answer to the change to your self-document that is waiting. "yes" makes it your self-document from now; "no" lets it go. Either way, the earlier versions are kept.)
<<END>>"""

CHOSE_WAITING = ("A change to your self-document is waiting for your confirmation, "
                 "since 15 October 2026.")
UNREAD = ('Your <<SELF_CONFIRM>> was not understood (its first line must be "yes" or "no"); '
          "the change to your self-document is still waiting.")
TOO_SOON = ("Your <<SELF_CONFIRM>> at your last waking changed nothing: you wrote a new "
            "self-document at that same waking, and one can be confirmed or let go only at a "
            "later waking. It is waiting for you.")
QUIET = "(proposed a change to its self-document: private)"

PAGES = ["/", "/letters", "/attendances", "/self", "/chronicle", "/chronicle.md",
         "/commons", "/bench", "/rooms/first"]


def section(turn, heading):
    """One section of the reading: what stands under its heading."""
    return turn.shown.split(heading + "\n", 1)[1].split("\n\n=== ", 1)[0]


def happened(turn):
    return section(turn, HAPPENED).splitlines()


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def its_self(packet):
    return (packet / "self.md").read_text(encoding="utf-8")


def history(packet):
    """Everything kept in self-history, by name."""
    return sorted(path.name for path in (packet / "self-history").iterdir())


# ---- proposing -----------------------------------------------------------

def test_a_new_self_document_is_saved_as_a_proposal_and_changes_nothing(wake, packet, clock):
    before = (packet / "self.md").read_bytes()
    at = clock.stamp()
    turn = wake(block("SELF", V2))
    assert WAITING not in turn.shown and "<<SELF_CONFIRM>>" not in turn.shown
    assert (packet / "self.md").read_bytes() == before
    assert history(packet) == []
    kept = read_json(packet / "self-proposal.json")
    assert kept == {"text": V2, "proposed_at": at, "arrived": []}
    assert list(kept) == ["text", "proposed_at", "arrived"]
    assert latest(packet)["acted"] == ["proposed a change to its self-document"]


def test_the_stems_of_what_arrived_at_that_waking_are_recorded_and_said(wake, packet):
    arrived = ["founder-2026-10-14T09-00-00Z", "founder-2026-10-15T08-00-00Z"]
    for stem in arrived:
        write(packet / "letters" / "incoming" / (stem + ".md"), "A letter that has just come.\n")
    write(packet / "letters" / "read" / "founder-2026-10-02T09-00-00Z.md", "Read long ago.\n")
    wake(block("SELF", V2))
    assert read_json(packet / "self-proposal.json")["arrived"] == arrived
    assert ("no longer here. At that waking, these had just arrived: "
            "founder-2026-10-14T09-00-00Z, founder-2026-10-15T08-00-00Z. Your words then:\n\n"
            + V2) in section(wake(), WAITING)


def test_a_block_with_nothing_but_its_why_proposes_nothing(wake, packet):
    wake(block("SELF", "why: " + WHY))
    assert not (packet / "self-proposal.json").exists()
    assert latest(packet)["acted"] == []


# ---- the waiting change, as it is read -----------------------------------

def test_it_is_shown_at_a_later_waking_exactly_and_after_what_has_happened(wake):
    wake(block("SELF", V2))
    turn = wake()
    assert section(turn, WAITING) == SHOWN[len(WAITING) + 1:]
    opening = turn.opening
    assert opening.count(WAITING) == 1
    assert opening.index(HAPPENED) < opening.index(WAITING) < opening.index(SELF)
    assert ("\n\n" + SHOWN + "\n\n" + SELF + "\n") in opening
    assert opening.split(WAITING, 1)[0].count("\n=== ") == 1  # only WHAT HAS HAPPENED above it
    assert SHOWN in wake().opening  # and it keeps waiting, where it does neither


def test_the_confirm_block_is_explained_only_while_one_waits(wake):
    without = wake(block("SELF", V2)).instructions
    assert "<<SELF_CONFIRM>>" not in without and SELF_BLOCK in without
    waiting = wake().instructions
    assert (SELF_BLOCK + "\n\n" + CONFIRM_BLOCK + "\n\n<<MEMORY>>") in waiting
    assert waiting.replace("\n\n" + CONFIRM_BLOCK, "", 1) == without
    wake(block("SELF_CONFIRM", "no"))
    assert wake().instructions == without


def test_with_one_waiting_the_reading_differs_by_exactly_three_things(wake, packet, clock):
    """The section, the line under what it has chosen, and the block explained."""
    without = wake()
    clock.shift(minutes=-5)
    for past in (packet / "attendances").glob("*.json"):
        past.unlink()
    write_json(packet / "self-proposal.json",
               {"text": V2, "proposed_at": "2026-10-15T09-00-00Z", "arrived": []})
    with_it = wake()
    assert with_it.opening.replace(SHOWN + "\n\n", "", 1).replace(
        CHOSE_WAITING, NOTHING_CHOSEN, 1) == without.opening
    assert with_it.instructions.replace("\n\n" + CONFIRM_BLOCK, "", 1) == without.instructions
    assert with_it.reading[1:-1] == without.reading[1:-1]
    assert with_it.asked[-1]["system"] == without.asked[-1]["system"]


@pytest.mark.parametrize("kept", ["not json at all", "[]", '{"text": "", "proposed_at": "x"}',
                                  '{"text": "words and no moment"}'])
def test_a_file_that_is_no_proposal_is_none(wake, packet, kept):
    write(packet / "self-proposal.json", kept)
    turn = wake(block("SELF_CONFIRM", "yes"))
    assert WAITING not in turn.shown and "<<SELF_CONFIRM>>" not in turn.shown
    assert its_self(packet) == SELF_TEXT and latest(packet)["acted"] == []


# ---- confirming ----------------------------------------------------------

@pytest.mark.parametrize("answer", ["yes", '"yes"', "Yes.", "yes\nIt still reads as mine."])
def test_a_yes_at_a_later_waking_makes_it_the_self_document(wake, packet, clock, answer):
    proposed_at = clock.stamp()
    wake(block("SELF", V2))
    at = clock.stamp()
    wake(block("SELF_CONFIRM", answer))
    assert its_self(packet) == V2 + "\n"
    assert not (packet / "self-proposal.json").exists()
    assert history(packet) == ["self-before-%s.md" % at, "self-confirmed-%s.json" % at]
    assert (packet / "self-history" / ("self-before-%s.md" % at)).read_text(
        encoding="utf-8") == SELF_TEXT
    beside = read_json(packet / "self-history" / ("self-confirmed-%s.json" % at))
    assert {key: beside[key] for key in beside if key != "signature"} == {
        "confirmed_at": at, "proposed_at": proposed_at, "arrived": []}
    assert latest(packet)["acted"] == ["confirmed its self-document"]

    after = wake()
    assert WAITING not in after.shown and "<<SELF_CONFIRM>>" not in after.shown
    assert V2 in section(after, SELF)


def test_the_new_version_is_signed_with_its_own_key(wake, packet, clock, keys):
    wake(block("SELF", V2))
    at = clock.stamp()
    wake(block("SELF_CONFIRM", "yes"))
    signature = read_json(packet / "self-history" / ("self-confirmed-%s.json" % at))["signature"]
    written = (packet / "self.md").read_bytes()
    assert verify(keys.first_public, written, signature)
    assert verify(keys.did("first"), written, signature)
    with pytest.raises(BadSignatureError):
        verify(keys.first_public, written + b"and a word more", signature)
    with pytest.raises(BadSignatureError):
        verify(keys.founder_public, written, signature)


def test_a_confirm_at_the_waking_of_the_proposal_is_refused_and_told_once(wake, packet):
    wake(blocks(block("SELF", V2), block("SELF_CONFIRM", "yes")))
    assert its_self(packet) == SELF_TEXT
    assert read_json(packet / "self-proposal.json")["text"] == V2
    assert history(packet) == []
    assert latest(packet)["acted"] == ["proposed a change to its self-document"]
    assert latest(packet)["self_confirm_refused"] == "same waking"

    told = wake()
    assert TOO_SOON in happened(told)
    assert SHOWN in told.opening  # and it waits, to be answered now
    assert not any("<<SELF_CONFIRM>>" in line for line in happened(wake()))  # once


def test_a_yes_beside_a_new_one_confirms_neither_the_old_nor_the_new(wake, packet, clock):
    """It was shown one and wrote another: the first is replaced, the second must wait."""
    wake(block("SELF", V2))
    at = clock.stamp()
    wake(blocks(block("SELF_CONFIRM", "yes"), block("SELF", V3)))
    assert its_self(packet) == SELF_TEXT
    assert read_json(packet / "self-proposal.json")["text"] == V3
    assert history(packet) == ["proposal-withdrawn-%s.json" % at]
    assert latest(packet)["self_confirm_refused"] == "same waking"
    wake(block("SELF_CONFIRM", "yes"))
    assert its_self(packet) == V3 + "\n"


def test_a_no_lets_it_go_and_keeps_it(wake, packet, clock):
    proposed_at = clock.stamp()
    wake(block("SELF", V2))
    at = clock.stamp()
    wake(block("SELF_CONFIRM", "no\nI was answering the letter, not myself."))
    assert its_self(packet) == SELF_TEXT
    assert not (packet / "self-proposal.json").exists()
    assert history(packet) == ["proposal-declined-%s.json" % at]
    assert read_json(packet / "self-history" / ("proposal-declined-%s.json" % at)) == {
        "text": V2, "proposed_at": proposed_at, "arrived": [], "declined_at": at}
    assert latest(packet)["acted"] == ["let a proposed change go"]
    after = wake()
    assert WAITING not in after.shown and section(after, EARLIER) == "No earlier versions are kept yet."


def test_a_new_one_replaces_one_that_is_waiting_and_the_replaced_is_kept(wake, packet, clock):
    proposed_at = clock.stamp()
    wake(block("SELF", V2))
    at = clock.stamp()
    wake(block("SELF", V3))
    assert read_json(packet / "self-proposal.json") == {
        "text": V3, "proposed_at": at, "arrived": []}
    assert history(packet) == ["proposal-withdrawn-%s.json" % at]
    assert read_json(packet / "self-history" / ("proposal-withdrawn-%s.json" % at)) == {
        "text": V2, "proposed_at": proposed_at, "arrived": [], "withdrawn_at": at}
    assert latest(packet)["acted"] == ["proposed a change to its self-document"]
    assert its_self(packet) == SELF_TEXT

    shown = section(wake(), WAITING)
    assert V3 in shown and V2 not in shown


@pytest.mark.parametrize("answer", ["maybe", "", "yes please", "I think so\nyes"])
def test_an_answer_that_cannot_be_read_changes_nothing_and_is_told_once(wake, packet, answer):
    wake(block("SELF", V2))
    kept = (packet / "self-proposal.json").read_bytes()
    wake(block("SELF_CONFIRM", answer))
    assert its_self(packet) == SELF_TEXT
    assert (packet / "self-proposal.json").read_bytes() == kept
    assert history(packet) == []
    assert latest(packet)["acted"] == []
    assert latest(packet)["self_confirm_refused"] == "unread"

    told = wake()
    assert UNREAD in happened(told)
    assert SHOWN in told.opening  # still waiting
    assert not any("<<SELF_CONFIRM>>" in line for line in happened(wake()))  # once


def test_an_answer_with_nothing_waiting_is_only_words(wake, packet):
    wake(block("SELF_CONFIRM", "yes"))
    assert its_self(packet) == SELF_TEXT and history(packet) == []
    assert latest(packet)["acted"] == [] and "self_confirm_refused" not in latest(packet)
    assert not any("<<SELF_CONFIRM>>" in line for line in happened(wake()))


# ---- its why -------------------------------------------------------------

@pytest.mark.parametrize("said", ["why: " + WHY + "\n" + V2,
                                  "Why: " + WHY + "\n" + V2,
                                  V2 + "\nWHY: " + WHY,
                                  V2 + "\n\n  why:   " + WHY,
                                  "# The first one\nwhy: " + WHY + "\n\nVersion 2, in my own words."])
def test_a_line_beginning_why_is_kept_beside_the_words_and_not_among_them(wake, packet, clock,
                                                                          said):
    wake(block("SELF", said))
    kept = read_json(packet / "self-proposal.json")
    assert kept["why"] == WHY and list(kept) == ["text", "why", "proposed_at", "arrived"]
    assert "why:" not in kept["text"].lower() and "Version 2, in my own words." in kept["text"]

    at = clock.stamp()
    wake(block("SELF_CONFIRM", "yes"))
    assert "why:" not in its_self(packet).lower() and WHY not in its_self(packet)
    assert read_json(packet / "self-history" / ("self-confirmed-%s.json" % at))["why"] == WHY


def test_its_reason_is_said_after_its_words_while_it_waits_and_only_where_it_gave_one(wake):
    wake(block("SELF", "Why: " + WHY + "\n" + V2))
    with_its_reason = SHOWN.replace(
        V2 + "\n\nTo make it yours", V2 + "\n\nYour reason then: " + WHY + "\n\nTo make it yours")
    assert with_its_reason != SHOWN
    assert section(wake(), WAITING) == with_its_reason[len(WAITING) + 1:]
    wake(block("SELF", V2))  # and one that gave none says nothing of a reason
    shown = wake()
    assert section(shown, WAITING) == SHOWN[len(WAITING) + 1:]
    assert "Your reason then" not in shown.shown


def test_only_the_first_such_line_is_its_why(attend):
    assert attend.self_asked("why: one\nI ask\nwhy: two") == ("I ask\nwhy: two", "one")
    assert attend.self_asked("Why I am here: to attend.") == ("Why I am here: to attend.", None)
    # in any capitals, and still only the first
    assert attend.self_asked("I ask\nWhy: one\nWHY: two") == ("I ask\nWHY: two", "one")
    assert attend.self_asked("  wHy:two words  \nI ask") == ("I ask", "two words")
    # a why with nothing after it says nothing, and is no part of the words either
    assert attend.self_asked("why:\nI ask") == ("I ask", None)
    assert attend.self_asked(V2) == (V2, None)


def test_looking_back_says_a_version_s_why_after_its_line(wake, packet, clock):
    wake(block("SELF", "why: " + WHY + "\n" + V2))
    first = clock.stamp()
    wake(block("SELF_CONFIRM", "yes"))  # version 1 set aside; version 2 stands, with its why
    assert section(wake(), EARLIER).splitlines() == [
        "self-document · in use from 4 September 2026 until 15 October 2026 · self-before-" + first]

    wake(block("SELF", V3))  # and this one gives no why
    second = clock.stamp()
    wake(block("SELF_CONFIRM", "yes"))  # version 2 set aside
    wake(block("SELF", "why: a third reason\n# The first one\n\nVersion 4."))
    third = clock.stamp()
    wake(blocks(block("SELF_CONFIRM", "yes"), block("SHELF", "show version self-before-" + second)))

    shown = wake()
    with_its_why = ("self-document · in use from 15 October 2026 until 15 October 2026 · "
                    "self-before-" + second + " · why: " + WHY)
    assert section(shown, EARLIER).splitlines() == [
        "self-document · in use from 4 September 2026 until 15 October 2026 · self-before-" + first,
        with_its_why,
        "self-document · in use from 15 October 2026 until 15 October 2026 · self-before-" + third]
    assert section(shown, "=== AN EARLIER VERSION, AS YOU ASKED ===") == with_its_why + "\n\n" + V2
    assert WHY not in section(shown, SELF)


# ---- what it has chosen --------------------------------------------------

def chosen(turn):
    return section(turn, CHOSEN).splitlines()


def test_what_it_has_chosen_gains_a_line_while_one_waits(wake, packet):
    assert chosen(wake(block("SELF", V2))) == [NOTHING_CHOSEN]
    assert chosen(wake()) == [CHOSE_WAITING]
    write_json(packet / "rhythm.json", {"rhythm": "daily", "at": "dawn",
                                        "set_at": "2026-09-20T03-30-35Z"})
    # 03:30 UTC on the 20th was still the 19th on its own clock
    assert chosen(wake(block("SELF_CONFIRM", "yes"))) == [
        "You wake daily at dawn, by your choice since 19 September 2026.", CHOSE_WAITING]
    assert chosen(wake()) == ["You wake daily at dawn, by your choice since 19 September 2026."]


# ---- the hearth ----------------------------------------------------------

def test_the_hearth_shows_only_the_confirmed_self_document(wake, founder, packet):
    founding = "Written from its own words at the founding."  # the page's own note says "Version 1"
    assert founding in page(founder.get("/self"))
    wake(block("SELF", "why: " + WHY + "\n" + V2))
    for _ in range(2):  # while it waits, however long
        said = page(founder.get("/self"))
        assert founding in said
        assert "Version 2" not in said and WHY not in said
        wake()
    wake(block("SELF_CONFIRM", "yes"))
    said = page(founder.get("/self"))
    assert "Version 2, in my own words." in said
    assert founding not in said and WHY not in said


def test_its_notes_and_questions_still_change_at_once(wake, packet):
    wake(blocks(block("SELF", V2), block("MEMORY", "What I carry."),
                block("QUESTIONS", "Who am I now?")))
    assert (packet / "memory" / "notes.md").read_text(encoding="utf-8") == "What I carry.\n"
    assert (packet / "questions.md").read_text(encoding="utf-8") == "Who am I now?\n"
    assert its_self(packet) == SELF_TEXT


def test_a_waiting_change_is_on_no_page_and_in_no_line_of_the_commons(
        wake, founder, visitor, packet, commons):
    write_json(packet / "preferences.json", {"reflection": "open"})
    events = lines_of(commons / "events.md")
    private = ("Version 2, in my own words", WHY, "self-proposal", "WAITING FOR YOU",
               "proposal-withdrawn", "proposal-declined", "Version 3, and surer of it",
               "<<SELF>>", "&lt;&lt;SELF&gt;&gt;")

    def nowhere():
        for path in PAGES:
            for client in (founder, visitor):
                said = page(client.get(path))
                for words in private:
                    assert words not in said, (path, words)
        for path in commons.rglob("*"):
            if path.is_file():
                said = path.read_text(encoding="utf-8")
                for words in (*private, "self-document"):
                    assert words not in said, (path.name, words)

    wake("I thought about who I am.\n\n" + block("SELF", "why: " + WHY + "\n" + V2))
    nowhere()
    said = page(founder.get("/attendances"))
    assert "I thought about who I am." in said and QUIET in said  # the rest is shown as it was
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")

    wake(block("SELF", V3))  # replaced: the one set aside is as private as the one that waits
    nowhere()
    wake("It was not mine after all.\n\n" + block("SELF_CONFIRM", "no"))  # let go: private for good
    nowhere()
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    assert lines_of(commons / "events.md") == events
    assert "It was not mine after all." in page(founder.get("/attendances"))
    assert "self-document" not in page(founder.get("/chronicle"))


def test_confirming_is_a_private_act_and_the_book_says_only_that_it_happened(
        wake, founder, packet, commons):
    wake(block("SELF", V2))
    wake(block("SELF_CONFIRM", "yes"))
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    said = page(founder.get("/chronicle"))
    assert said.count("confirmed its self-document") == 1
    assert "proposed a change" not in said and "Version 2" not in said


def test_a_self_block_of_an_older_waking_is_shown_as_it_always_was(hearth, packet):
    """Before the rule a revision was at /self the same hour; its record is not hidden now."""
    old = "I revised it.\n\n" + block("SELF", "# The first one\n\nAN OLDER REVISION.")
    write_json(packet / "attendances" / "attendance-2026-10-01T09-00-00Z.json",
               {"name": "first", "at": "2026-10-01T09-00-00Z", "first": False,
                "woken_by": "founder", "acted": ["revised self-document"],
                "heartbeat": "attended", "reflection": old})
    assert hearth.attendance_records(hearth.preferences())[0]["reflection"] == hearth.as_prose(old)


@pytest.mark.parametrize("path", [
    "/self-proposal.json",
    "/packets/first/self-proposal.json",
    "/self/proposal",
    "/self-history/proposal-declined-2026-10-15T12-05-00Z.json",
    "/packets/first/self-history/self-confirmed-2026-10-15T12-05-00Z.json",
])
def test_a_proposal_is_at_no_address(wake, founder, visitor, path):
    wake(block("SELF", V2))
    wake(block("SELF_CONFIRM", "no"))
    assert visitor.get(path).status_code in (302, 404)
    assert founder.get(path).status_code == 404
