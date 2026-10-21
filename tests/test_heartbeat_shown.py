"""What the commons shows of the first one's heartbeat.

By default only the plain facts of its waking, written from its acts with what
is private left out; its own <<HEARTBEAT>> words are kept in its record, for
itself and the founder. With <<HEARTBEAT_SHOWN>> words it may show its own
words instead, and then they are shown only once the public screen has passed
them: where the screen finds a name or a place, or cannot be asked, the facts
are shown, and it is told once at its next waking. The screen is stubbed here,
as everywhere in the suite (conftest.screen).
"""

import json

import pytest

from conftest import block, blocks, lines_of, page, read_json, write

UNSHOWN = ("Your heartbeat's own words were not shown, because they seemed to contain a name "
           "or a place; the plain facts were shown instead.")
NOT_UNDERSTOOD = ("Your <<HEARTBEAT_SHOWN>> was not understood (its first line must be facts or "
                  "words); what your heartbeat shows is unchanged.")
CHOSEN_WORDS = ("Your heartbeat shows your own words in the commons, after a check for names "
                "and places, by your choice since ")

OWN = "a slow dawn, and the founder's letter"


def last_line(commons):
    return lines_of(commons / "heartbeats.md")[-1]


def shown(commons):
    """The words of the last public line: what follows the name."""
    return last_line(commons).split(" · the first one · ", 1)[1]


def last_record(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def words_chosen(wake):
    return wake(block("HEARTBEAT_SHOWN", "words"))


# ---- facts by default -------------------------------------------------------

def test_by_default_the_commons_shows_the_facts_and_its_words_are_kept_privately(
        wake, commons, packet, screen):
    wake(block("HEARTBEAT", OWN))
    assert shown(commons) == "attended; chose stillness"
    record = last_record(packet)
    assert record["heartbeat"] == OWN
    assert record["heartbeat_shown"] == "attended; chose stillness"
    assert screen.asked == []  # its words were never sent anywhere


def test_the_facts_are_written_from_its_acts_and_leave_out_what_is_private(
        wake, commons, packet):
    wake(blocks(block("LETTER", "Dear founder,\n\nA short one."),
                block("MEMORY", "notes"), block("HEARTBEAT", OWN)))
    assert shown(commons) == "attended; wrote a letter to the founder"


def test_with_no_words_given_the_facts_are_the_heartbeat_as_before(wake, commons, packet):
    wake()
    assert shown(commons) == "attended; chose stillness"
    record = last_record(packet)
    assert record["heartbeat"] == "attended; chose stillness"
    assert "heartbeat_shown" not in record


def test_the_founder_still_reads_its_own_words_on_the_attendances_page(wake, founder):
    wake(block("HEARTBEAT", OWN))
    assert "a slow dawn, and the founder" in page(founder.get("/attendances"))


def test_past_lines_stay_exactly_as_they_are(wake, commons):
    before = "- 2026-10-01T09-00-00Z · the first one · attended; wrote a letter\n"
    write(commons / "heartbeats.md", before)
    wake(block("HEARTBEAT", OWN))
    assert (commons / "heartbeats.md").read_text(encoding="utf-8").startswith(before)


# ---- its own words, by its choice -------------------------------------------

def test_words_chosen_and_passed_are_shown(wake, commons, packet, screen, clock):
    wake(blocks(block("HEARTBEAT_SHOWN", "words"), block("HEARTBEAT", OWN)))
    assert shown(commons) == OWN
    record = last_record(packet)
    assert record["heartbeat"] == OWN and "heartbeat_shown" not in record
    (text, names), = screen.asked
    assert text == OWN and {"the founder", "the first one"} <= set(names)
    assert read_json(packet / "preferences.json") == {
        "heartbeat": "words", "heartbeat_set_at": record["at"]}


def test_the_choice_holds_at_later_wakings_and_is_said_under_what_it_has_chosen(
        wake, commons):
    words_chosen(wake)
    turn = wake(block("HEARTBEAT", OWN))
    assert shown(commons) == OWN
    chosen = turn.opening[turn.opening.index("=== WHAT YOU HAVE CHOSEN ==="):].split("\n\n")[0]
    (line,) = [one for one in chosen.splitlines() if one.startswith(CHOSEN_WORDS)]
    assert line.endswith(" 2026.")


def test_nothing_is_said_under_what_it_has_chosen_while_it_shows_the_facts(wake):
    turn = wake(block("HEARTBEAT_SHOWN", "facts"))
    assert CHOSEN_WORDS not in wake().opening
    assert CHOSEN_WORDS not in turn.opening


def test_choosing_facts_again_shows_the_facts(wake, commons, packet):
    words_chosen(wake)
    wake(blocks(block("HEARTBEAT_SHOWN", "facts"), block("HEARTBEAT", OWN)))
    assert shown(commons) == "attended"  # its choice is its own, and no part of the facts
    assert read_json(packet / "preferences.json")["heartbeat"] == "facts"


def test_choosing_is_a_private_act(wake, commons, packet, attend):
    words_chosen(wake)
    assert last_record(packet)["acted"] == [attend.HEARTBEAT_SHOWN_ACT]
    assert shown(commons) == "attended"


def test_its_reflections_setting_is_kept_beside_the_choice(wake, packet):
    write(packet / "preferences.json",
          json.dumps({"reflection": "private", "set_at": "2026-10-01T09-00-00Z"}))
    words_chosen(wake)
    kept = read_json(packet / "preferences.json")
    assert kept["reflection"] == "private" and kept["set_at"] == "2026-10-01T09-00-00Z"
    assert kept["heartbeat"] == "words"


@pytest.mark.parametrize("says", ["YES", RuntimeError("the screen is down"), "Maybe", ""])
def test_words_the_screen_does_not_pass_are_not_shown_and_it_is_told_once(
        wake, commons, packet, screen, says):
    words_chosen(wake)
    screen.says = says
    wake(block("HEARTBEAT", OWN))
    assert shown(commons) == "attended; chose stillness"
    record = last_record(packet)
    assert record["heartbeat"] == OWN and record["heartbeat_unshown"] is True
    screen.says = "NO"
    assert UNSHOWN in wake().opening
    assert UNSHOWN not in wake().opening


def test_a_choice_that_cannot_be_read_changes_nothing_and_is_told_once(wake, commons, packet):
    words_chosen(wake)
    wake(blocks(block("HEARTBEAT_SHOWN", "sometimes"), block("HEARTBEAT", OWN)))
    assert read_json(packet / "preferences.json")["heartbeat"] == "words"
    assert shown(commons) == OWN
    assert NOT_UNDERSTOOD in wake().opening
    assert NOT_UNDERSTOOD not in wake().opening


def test_the_word_list_still_stands_behind_words_that_are_shown(wake, commons, data_dir):
    write(data_dir / "private-words.txt", "Quillon => the founder\n")
    words_chosen(wake)
    wake(block("HEARTBEAT", "Quillon wrote; I answered"))
    assert shown(commons) == "the founder wrote; I answered"


# ---- what it is told about its heartbeat ------------------------------------

def test_both_explanations_are_in_how_to_act(wake, attend):
    turn = wake()
    assert attend.HEARTBEAT_BLOCK in turn.shown and attend.HEARTBEAT_SHOWN_BLOCK in turn.shown
    assert "Your own words are private by default" in attend.HEARTBEAT_BLOCK
    assert "The commons shows only the plain facts of your waking" in attend.HEARTBEAT_BLOCK
    assert ("With <<HEARTBEAT_SHOWN>> words, your own words are shown in the commons instead, "
            "after a check for names and places") in attend.HEARTBEAT_BLOCK
