"""What the commons shows of the first one's waking: the facts, or a line it leaves.

The commons shows the plain facts of its waking, written from its acts with
what is private left out. Its own <<HEARTBEAT>> words are kept in its record,
for itself and the founder, and are never shown. At every waking it is offered,
and never owes, one line of its own with <<COMMONS_LINE>>, shown in the facts'
place once the public screen has passed it. Where the screen finds a name or a
place, cannot be asked, or the line is longer than 240 characters, the facts
are shown; the line is kept in its record either way, and is read back at its
next waking with what became of it. <<HEARTBEAT_SHOWN>>, which once chose what
its heartbeat shows, is read no longer. The screen is stubbed here, as
everywhere in the suite (conftest.screen).
"""

import json

import pytest

from conftest import block, blocks, lines_of, page, read_json, write

FLAGGED = ("The line you left for the commons was not shown, because it seemed to contain a "
           "name or a place; the plain facts were shown instead. It is kept in your record, and "
           "nothing more is owed.")
UNCHECKED = ("The line you left for the commons was not shown, because it could not be checked "
             "at the time; the plain facts were shown instead. It is kept in your record.")
LONG = ("The line you left for the commons was not shown, because it was longer than 240 "
        "characters; the plain facts were shown instead.")
SHOWN = "It was shown in the commons."
IGNORED = ("<<HEARTBEAT_SHOWN>> is no longer read; a line for the commons is asked for at each "
           "waking with <<COMMONS_LINE>>.")
THEN = 'Your line for the commons then: "%s".'

OWN = "a slow dawn, and the founder's letter"
LINE = "the light came late and stayed"


def last_line(commons):
    return lines_of(commons / "heartbeats.md")[-1]


def shown(commons):
    """The words of the last public line: what follows the name."""
    return last_line(commons).split(" · the first one · ", 1)[1]


def last_record(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def leave(wake, line=LINE, *more):
    return wake(blocks(block("COMMONS_LINE", line), *more))


# ---- the facts, where it leaves no line -----------------------------------

def test_with_no_line_the_commons_shows_the_facts_and_its_words_are_kept_privately(
        wake, commons, packet, screen):
    wake(block("HEARTBEAT", OWN))
    assert shown(commons) == "attended; chose stillness"
    record = last_record(packet)
    assert record["heartbeat"] == OWN
    assert record["heartbeat_shown"] == "attended; chose stillness"
    assert "commons_line" not in record and "commons_line_held" not in record
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
    leave(wake)
    assert (commons / "heartbeats.md").read_text(encoding="utf-8").startswith(before)


def test_its_heartbeat_words_are_never_shown_even_where_it_once_chose_words(
        wake, commons, packet, screen):
    write(packet / "preferences.json",
          json.dumps({"heartbeat": "words", "heartbeat_set_at": "2026-10-01T09-00-00Z"}))
    wake(block("HEARTBEAT", OWN))
    assert shown(commons) == "attended; chose stillness"
    assert screen.asked == []
    # and nothing is said of the old choice under what it has chosen
    assert "Your heartbeat shows your own words" not in wake().opening


# ---- a line it leaves --------------------------------------------------------

def test_a_line_the_screen_passes_is_shown_and_kept_in_its_record(wake, commons, packet, screen):
    leave(wake, LINE, block("HEARTBEAT", OWN))
    assert shown(commons) == LINE
    record = last_record(packet)
    assert record["heartbeat"] == OWN  # its own words, kept as they were
    assert record["commons_line"] == LINE and record["heartbeat_shown"] == LINE
    assert "commons_line_held" not in record
    (text, names), = screen.asked  # only the line is sent, never its heartbeat words
    assert text == LINE and {"the founder", "the first one"} <= set(names)


def test_only_the_first_line_is_taken(wake, commons, packet):
    leave(wake, "  " + LINE + "  \nand a second line, which is not")
    assert shown(commons) == LINE
    assert last_record(packet)["commons_line"] == LINE


def test_leaving_a_line_is_no_act(wake, commons, packet):
    leave(wake, LINE, block("MEMORY", "notes"))
    assert last_record(packet)["acted"] == ["kept notes"]
    leave(wake, LINE)
    assert last_record(packet)["acted"] == []


def test_an_empty_line_is_no_line(wake, commons, packet, screen):
    leave(wake, "   ")
    assert shown(commons) == "attended; chose stillness"
    assert "commons_line" not in last_record(packet) and screen.asked == []


def test_the_word_list_still_stands_behind_a_line_that_is_shown(wake, commons, data_dir):
    write(data_dir / "private-words.txt", "Quillon => the founder\n")
    leave(wake, "Quillon wrote; I answered")
    assert shown(commons) == "the founder wrote; I answered"


def test_it_is_offered_at_every_waking(wake, attend):
    for _ in range(2):
        turn = wake()
        assert attend.COMMONS_LINE_BLOCK in turn.shown
    leave(wake)
    assert attend.COMMONS_LINE_BLOCK in wake().shown


# ---- a line held back ---------------------------------------------------------

@pytest.mark.parametrize("says, held, told", [
    ("YES", "flagged", FLAGGED),
    (RuntimeError("the screen is down"), "unchecked", UNCHECKED),
    ("Maybe", "unchecked", UNCHECKED), ("", "unchecked", UNCHECKED)])
def test_a_line_the_screen_does_not_pass_is_held_back_and_it_is_told_why_once(
        wake, commons, packet, screen, says, held, told):
    screen.says = says
    leave(wake, LINE, block("HEARTBEAT", OWN))
    assert shown(commons) == "attended; chose stillness"
    record = last_record(packet)
    assert record["commons_line"] == LINE and record["commons_line_held"] == held
    assert record["heartbeat"] == OWN
    screen.says = "NO"
    opening = wake().opening
    assert (THEN % LINE) + " " + told in opening and SHOWN not in opening
    later = wake().opening
    assert told not in later and (THEN % LINE) not in later


def test_a_line_longer_than_240_characters_is_held_back_and_never_screened(
        wake, commons, packet, screen):
    too_long = "a" * 241
    leave(wake, too_long)
    assert shown(commons) == "attended; chose stillness"
    record = last_record(packet)
    assert record["commons_line"] == too_long and record["commons_line_held"] == "long"
    assert screen.asked == []
    assert (THEN % too_long) + " " + LONG in wake().opening


def test_a_line_of_exactly_240_characters_is_shown(wake, commons):
    leave(wake, "a" * 240)
    assert shown(commons) == "a" * 240


def test_a_held_back_line_says_nothing_of_itself_in_the_facts(wake, commons, screen):
    screen.says = "YES"
    leave(wake, LINE, block("LETTER", "Dear founder,"))
    assert shown(commons) == "attended; wrote a letter to the founder"


# ---- read back at the next waking ------------------------------------------

def test_the_next_waking_reads_its_line_back_and_says_it_was_shown(wake, attend):
    leave(wake, LINE, block("HEARTBEAT", OWN))
    opening = wake().opening
    said = 'Your heartbeat then: "%s".\n' % OWN + (THEN % LINE) + " " + SHOWN + "\n"
    assert said in opening
    assert (THEN % LINE) not in wake().opening  # only at the waking after it


def test_with_no_line_left_nothing_is_read_back(wake):
    wake(block("HEARTBEAT", OWN))
    opening = wake().opening
    assert "Your line for the commons then" not in opening and SHOWN not in opening


# ---- <<HEARTBEAT_SHOWN>>, read no longer -------------------------------------

def test_a_heartbeat_shown_is_ignored_and_it_is_told_once(wake, commons, packet):
    wake(blocks(block("HEARTBEAT_SHOWN", "words"), block("HEARTBEAT", OWN)))
    assert shown(commons) == "attended; chose stillness"  # and no act among the facts
    record = last_record(packet)
    assert record["acted"] == [] and record["heartbeat_shown_ignored"] is True
    assert not (packet / "preferences.json").exists()  # nothing of it is kept as a setting
    assert IGNORED in wake().opening
    assert IGNORED not in wake().opening


def test_nothing_is_said_of_it_where_none_was_written(wake):
    wake()
    assert IGNORED not in wake().opening


# ---- what it is told -------------------------------------------------------

def test_both_explanations_are_in_how_to_act(wake, attend):
    turn = wake()
    assert attend.HEARTBEAT_BLOCK + "\n\n" + attend.COMMONS_LINE_BLOCK in turn.shown
    assert "<<HEARTBEAT_SHOWN>>" not in turn.shown
    assert ("Your own words here are private: they are kept in your record, where the founder "
            "may read them, and they are never shown in the commons.") in attend.HEARTBEAT_BLOCK
    assert "by default" not in attend.HEARTBEAT_BLOCK
    assert "The commons shows only the plain facts of your waking" in attend.HEARTBEAT_BLOCK
    assert attend.HEARTBEAT_BLOCK.endswith(
        "For a line of your own that the commons may show, see <<COMMONS_LINE>>.)\n<<END>>")
    assert "never something owed" in attend.COMMONS_LINE_BLOCK
    assert "say \"the founder\" rather than any name" in attend.COMMONS_LINE_BLOCK
