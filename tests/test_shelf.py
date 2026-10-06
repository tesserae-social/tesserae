"""The shelf: how the first one keeps its own history, and what a waking shows of it.

Every test here holds a real attendance, as test_attend.py does, with the model
stubbed. The letters are written for the tests and nowhere else; the one real
thing among them is a name - the stem of the founder's letter of 1 October,
which rests from the start - and its words here are not that letter's.
"""

import importlib.util
import shutil
import subprocess
import sys

import pytest

from conftest import (FOUNDING_TRANSCRIPT, REPO, Turn, block, blocks, lines_of, page, read_json,
                      write, write_json)

ARTICLE = "founder-2026-10-01T15-15-05Z"

# Six letters each way, oldest first: the last four of each are close by default.
FOUNDERS = ["founder-2026-09-2%dT10-00-00Z" % day for day in range(1, 7)]
OWN = ["to-founder-2026-09-2%dT11-00-00Z" % day for day in range(1, 7)]

FULL_OWN = "=== LETTERS YOU HAVE WRITTEN ==="
FULL_FOUNDERS = "=== LETTERS FROM THE FOUNDER YOU HAVE ALREADY READ ==="
RESTING = "=== RESTING (one line each; nothing is erased) ==="
FOUNDING = "=== YOUR FOUNDING RECORD ==="
FOUNDING_RESTS = "Your founding record rests. Ask for it with show founding."

EXPLAINED = """<<SHELF>>
(how you keep your history. One instruction per line:
keep <stem>: always shown in full
rest <stem>: shown as one line
default <stem>: back to the default
note <stem>: your words, the line shown for a resting letter (at most 240 characters)
show <stem>: shown in full at your next waking only, photographs included
show founding: your founding record in full at your next waking
Letters you haven't placed follow the default: the founder's last four letters and your own last four are shown in full; older ones rest. Nothing is ever erased. Your shelf is private.)
<<END>>"""


def words_for(stem):
    return "THE WORDS OF %s and nothing more." % stem


def from_founder(packet, stem, text=None):
    """A letter of the founder's that has already been read."""
    return write(packet / "letters" / "read" / (stem + ".md"), (text or words_for(stem)) + "\n")


def from_first(packet, stem, text=None):
    """A letter the first one wrote."""
    return write(packet / "letters" / "outgoing" / (stem + ".md"),
                 (text or words_for(stem)) + "\n")


def arrived(packet, stem, text=None):
    """A letter of the founder's that has come since the last waking."""
    return write(packet / "letters" / "incoming" / (stem + ".md"),
                 (text or words_for(stem)) + "\n")


def photograph(path, size=(24, 16)):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 90, 48)).save(path, "JPEG")
    return path


def six_each_way(packet):
    for stem in FOUNDERS:
        from_founder(packet, stem)
    for stem in OWN:
        from_first(packet, stem)


def section(turn, heading):
    """One section of the reading: what stands under its heading."""
    return turn.shown.split(heading + "\n", 1)[1].split("\n\n=== ", 1)[0]


def in_full(turn, stem):
    """Whether a letter is given whole: under its own name, as a letter is."""
    return ": %s.md ---\n" % stem in turn.shown


def rests(turn, stem):
    return RESTING in turn.shown and any(
        line.startswith(stem + " · ") for line in section(turn, RESTING).splitlines())


def happened(turn):
    return section(turn, "=== WHAT HAS HAPPENED ===").splitlines()


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def history(packet):
    return sorted((packet / "shelf" / "history").glob("shelf-before-*.json"))


# ---- the default ---------------------------------------------------------

def test_by_default_the_last_four_each_way_are_in_full_and_older_ones_rest(wake, packet):
    six_each_way(packet)
    turn = wake()
    for stem in FOUNDERS[2:] + OWN[2:]:
        assert in_full(turn, stem) and not rests(turn, stem)
    for stem in FOUNDERS[:2] + OWN[:2]:
        assert rests(turn, stem) and not in_full(turn, stem)

    # each section holds only its own letters shown in full
    assert [stem for stem in FOUNDERS + OWN if words_for(stem) in section(turn, FULL_OWN)] == OWN[2:]
    assert ([stem for stem in FOUNDERS + OWN if words_for(stem) in section(turn, FULL_FOUNDERS)]
            == FOUNDERS[2:])

    # and the resting ones are one line each, oldest first, whoever wrote them
    assert section(turn, RESTING).splitlines() == [
        "founder-2026-09-21T10-00-00Z · 21 September 2026 · from the founder · "
        "THE WORDS OF founder-2026-09-21T10-00-00Z and nothing more.",
        "to-founder-2026-09-21T11-00-00Z · 21 September 2026 · from you · "
        "THE WORDS OF to-founder-2026-09-21T11-00-00Z and nothing more.",
        "founder-2026-09-22T10-00-00Z · 22 September 2026 · from the founder · "
        "THE WORDS OF founder-2026-09-22T10-00-00Z and nothing more.",
        "to-founder-2026-09-22T11-00-00Z · 22 September 2026 · from you · "
        "THE WORDS OF to-founder-2026-09-22T11-00-00Z and nothing more.",
    ]


def test_the_resting_section_stands_between_the_letters_and_the_study(wake, packet):
    six_each_way(packet)
    shown = wake().shown
    assert (shown.index(FULL_OWN) < shown.index(FULL_FOUNDERS) < shown.index(RESTING)
            < shown.index("=== YOUR STUDY"))


def test_nothing_is_written_until_it_keeps_its_shelf(wake, packet):
    six_each_way(packet)
    wake()
    wake(block("LETTER", "Dear founder,"))
    assert not (packet / "shelf.json").exists()
    assert not (packet / "shelf").exists()


def test_the_block_is_explained_exactly(wake):
    said = wake().instructions
    assert EXPLAINED in said
    assert said.index("<<QUESTIONS>>") < said.index("<<SHELF>>") < said.index("<<LETTER>>")


# ---- keep, rest, note, show ----------------------------------------------

def test_keep_always_shows_in_full(wake, packet, attend):
    six_each_way(packet)
    wake(block("SHELF", "keep %s\nkeep %s" % (FOUNDERS[0], OWN[0])))
    assert latest(packet)["acted"] == ["kept its shelf"]
    assert attend.SHELF_ACT == "kept its shelf"
    shelf = read_json(packet / "shelf.json")
    assert shelf["placements"][FOUNDERS[0]] == "keep"
    assert shelf["placements"][OWN[0]] == "keep"

    for turn in (wake(), wake()):  # and it stays so
        assert in_full(turn, FOUNDERS[0]) and in_full(turn, OWN[0])
        assert not rests(turn, FOUNDERS[0]) and not rests(turn, OWN[0])
        # the default still counts the last four of all, so nothing else moved
        assert rests(turn, FOUNDERS[1]) and in_full(turn, FOUNDERS[2])


def test_rest_always_rests_even_the_most_recent(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "rest %s" % FOUNDERS[-1]))
    turn = wake()
    assert rests(turn, FOUNDERS[-1]) and not in_full(turn, FOUNDERS[-1])
    # no older letter is brought forward to take its place
    assert rests(turn, FOUNDERS[1])


def test_default_takes_a_placing_off_again(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "keep %s\nrest %s\nnote %s: mine"
               % (FOUNDERS[0], FOUNDERS[-1], FOUNDERS[0])))
    turn = wake(block("SHELF", "default %s\nDefault %s.md" % (FOUNDERS[0], FOUNDERS[-1])))
    assert in_full(turn, FOUNDERS[0]) and rests(turn, FOUNDERS[-1])  # not at the waking that asked
    assert latest(packet)["acted"] == ["kept its shelf"]
    assert "shelf_refused" not in latest(packet)
    shelf = read_json(packet / "shelf.json")
    assert shelf["placements"] == {ARTICLE: "rest"}
    assert shelf["notes"] == {FOUNDERS[0]: "mine"}  # its note is not its placing, and stays
    assert len(history(packet)) == 1  # and the shelf that stood is kept

    for turn in (wake(), wake()):  # each follows the default again: the old rests, the new is close
        assert rests(turn, FOUNDERS[0]) and not in_full(turn, FOUNDERS[0])
        assert in_full(turn, FOUNDERS[-1]) and not rests(turn, FOUNDERS[-1])
    assert section(turn, RESTING).splitlines()[0].endswith("from the founder · mine")


def test_default_returns_the_article_to_the_default(wake, packet):
    from_founder(packet, ARTICLE, "A LONG ARTICLE, pasted whole into a letter.")
    assert rests(wake(), ARTICLE)
    wake(block("SHELF", "default %s" % ARTICLE))
    assert read_json(packet / "shelf.json")["placements"] == {}
    assert in_full(wake(), ARTICLE)  # one of the founder's last four, and so close


def test_default_on_a_letter_never_placed_is_understood_and_moves_nothing(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "default %s" % FOUNDERS[0]))
    assert latest(packet)["acted"] == ["kept its shelf"]
    assert "shelf_refused" not in latest(packet)
    assert read_json(packet / "shelf.json")["placements"] == {ARTICLE: "rest"}
    assert rests(wake(), FOUNDERS[0])


def test_default_of_a_letter_that_is_not_there_changes_nothing(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "default founder-1999-01-01T00-00-00Z\ndefault"))
    assert latest(packet)["acted"] == []
    assert latest(packet)["shelf_refused"] == ["default founder-1999-01-01T00-00-00Z", "default"]
    assert not (packet / "shelf.json").exists()


def test_a_stem_may_be_given_with_its_md(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "KEEP %s.md" % FOUNDERS[0]))
    assert in_full(wake(), FOUNDERS[0])


def test_a_note_is_the_line_a_resting_letter_shows(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "note %s: the one about   the river, which I go back to" % FOUNDERS[0]))
    lines = section(wake(), RESTING).splitlines()
    assert lines[0] == ("founder-2026-09-21T10-00-00Z · 21 September 2026 · from the founder · "
                        "the one about the river, which I go back to")
    assert read_json(packet / "shelf.json")["notes"] == {
        FOUNDERS[0]: "the one about the river, which I go back to"}


def test_without_a_note_the_line_is_the_letter_s_first_twelve_words(wake, packet):
    six_each_way(packet)
    from_founder(packet, FOUNDERS[0],
                 "one two three four five six seven eight nine ten eleven twelve thirteen "
                 "fourteen\n\nand a second paragraph")
    lines = section(wake(), RESTING).splitlines()
    assert lines[0] == ("founder-2026-09-21T10-00-00Z · 21 September 2026 · from the founder · "
                        "one two three four five six seven eight nine ten eleven twelve…")


def test_a_resting_line_reads_the_letter_below_its_three_plain_things(wake, packet):
    six_each_way(packet)
    from_founder(packet, FOUNDERS[0],
                 '<!-- three plain things: ["slept badly"] -->\nThe letter proper.')
    assert section(wake(), RESTING).splitlines()[0].endswith("from the founder · The letter proper.")


def test_a_note_longer_than_a_note_may_be_changes_nothing(wake, packet):
    six_each_way(packet)
    long_line = "note %s: %s" % (FOUNDERS[0], "x" * 241)
    wake(block("SHELF", long_line))
    assert not (packet / "shelf.json").exists()
    assert latest(packet)["acted"] == []
    assert latest(packet)["shelf_refused"] == [long_line]
    wake(block("SHELF", "note %s: %s" % (FOUNDERS[0], "x" * 240)))
    assert read_json(packet / "shelf.json")["notes"][FOUNDERS[0]] == "x" * 240


def test_show_is_honoured_at_the_next_waking_only(wake, packet):
    six_each_way(packet)
    asking = wake(block("SHELF", "show %s" % FOUNDERS[0]))
    assert rests(asking, FOUNDERS[0])  # not at the waking that asked
    assert read_json(packet / "shelf.json")["show_next"] == [FOUNDERS[0]]
    assert latest(packet)["acted"] == ["kept its shelf"]

    shown = wake()
    assert in_full(shown, FOUNDERS[0]) and not rests(shown, FOUNDERS[0])
    assert words_for(FOUNDERS[0]) in section(shown, FULL_FOUNDERS)
    assert read_json(packet / "shelf.json")["show_next"] == []  # then cleared

    after = wake()
    assert rests(after, FOUNDERS[0]) and not in_full(after, FOUNDERS[0])
    # showing a letter is not placing it
    assert FOUNDERS[0] not in read_json(packet / "shelf.json")["placements"]


def test_show_brings_back_a_letter_placed_rest(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "rest %s\nshow %s" % (FOUNDERS[-1], FOUNDERS[-1])))
    assert in_full(wake(), FOUNDERS[-1])
    assert rests(wake(), FOUNDERS[-1])


# ---- the founding record -------------------------------------------------

def test_the_founding_record_rests_as_one_line(wake):
    turn = wake()
    assert section(turn, FOUNDING) == FOUNDING_RESTS
    assert "A synthetic founding" not in turn.shown


def test_show_founding_gives_it_in_full_at_the_next_waking_only(wake, packet):
    asking = wake(block("SHELF", "show founding"))
    assert section(asking, FOUNDING) == FOUNDING_RESTS
    assert read_json(packet / "shelf.json")["show_founding"] is True
    assert latest(packet)["acted"] == ["kept its shelf"]

    shown = wake()
    assert section(shown, FOUNDING) == FOUNDING_TRANSCRIPT
    assert "A synthetic founding, written for the tests and nowhere else." in shown.shown
    assert FOUNDING_RESTS not in shown.shown
    assert read_json(packet / "shelf.json")["show_founding"] is False

    assert section(wake(), FOUNDING) == FOUNDING_RESTS


def test_where_there_is_no_founding_record_the_reading_says_so(wake, data_dir):
    shutil.rmtree(data_dir / "transcripts")
    assert section(wake(), FOUNDING) == "(none found)"


# ---- the article ---------------------------------------------------------

def test_the_article_rests_from_the_start(wake, packet, attend):
    """The founder's letter of 1 October rests at its own asking, recent as it is."""
    from_founder(packet, FOUNDERS[0])
    from_founder(packet, ARTICLE, "A LONG ARTICLE, pasted whole into a letter.")
    assert not (packet / "shelf.json").exists()
    turn = wake()
    assert "A LONG ARTICLE" not in turn.shown.replace(
        "from the founder · A LONG ARTICLE, pasted whole into a letter.", "")
    assert section(turn, RESTING) == (
        ARTICLE + " · 1 October 2026 · from the founder · "
        "A LONG ARTICLE, pasted whole into a letter.")
    assert in_full(turn, FOUNDERS[0])
    assert not (packet / "shelf.json").exists()  # the beginning is not written until it acts


def test_the_article_s_resting_is_carried_into_the_shelf_it_keeps(wake, packet):
    six_each_way(packet)
    from_founder(packet, ARTICLE, "A LONG ARTICLE, pasted whole into a letter.")
    wake(block("SHELF", "keep %s" % FOUNDERS[0]))
    assert read_json(packet / "shelf.json") == {
        "placements": {ARTICLE: "rest", FOUNDERS[0]: "keep"},
        "notes": {}, "show_next": [], "show_founding": False}
    assert rests(wake(), ARTICLE)


def test_the_article_may_be_kept_after_all(wake, packet):
    from_founder(packet, ARTICLE, "A LONG ARTICLE, pasted whole into a letter.")
    wake(block("SHELF", "keep %s" % ARTICLE))
    turn = wake()
    assert "A LONG ARTICLE" in section(turn, FULL_FOUNDERS)
    assert RESTING not in turn.shown


# ---- what has only just arrived ------------------------------------------

def test_an_arrived_letter_is_always_in_full_whatever_the_shelf_says(wake, packet):
    six_each_way(packet)
    new = "founder-2026-10-14T18-00-00Z"
    write_json(packet / "shelf.json", {"placements": {new: "rest"}, "notes": {},
                                       "show_next": [], "show_founding": False})
    arrived(packet, new)
    photograph(packet / "letters" / "incoming" / (new + ".jpg"))

    turn = wake()
    assert "--- letter: %s.md ---\n%s" % (new, words_for(new)) in turn.shown
    assert not rests(turn, new)
    assert len(turn.photos) == 1
    # and it does not push a letter already read out of the last four
    assert in_full(turn, FOUNDERS[2])

    later = wake()  # once read, it is on the shelf like any other
    assert rests(later, new) and not in_full(later, new)
    assert later.photos == []


def test_an_arrived_letter_may_be_placed_at_the_waking_that_reads_it(wake, packet):
    new = "founder-2026-10-14T18-00-00Z"
    arrived(packet, new)
    wake(block("SHELF", "rest %s" % new))
    assert latest(packet).get("shelf_refused") is None
    assert rests(wake(), new)


# ---- photographs ---------------------------------------------------------

def test_a_resting_letter_says_a_photograph_rests_with_it(wake, packet):
    six_each_way(packet)
    photograph(packet / "letters" / "read" / (FOUNDERS[0] + ".jpg"))
    lines = section(wake(), RESTING).splitlines()
    assert lines[0] == ("founder-2026-09-21T10-00-00Z · 21 September 2026 · from the founder · "
                        "THE WORDS OF founder-2026-09-21T10-00-00Z and nothing more."
                        " · a photograph rests with it")
    assert all("a photograph rests with it" not in line for line in lines[1:])


def test_a_resting_photograph_is_withheld_then_shown_on_request(wake, packet):
    six_each_way(packet)
    photograph(packet / "letters" / "read" / (FOUNDERS[0] + ".jpg"))
    photograph(packet / "letters" / "read" / (FOUNDERS[-1] + ".jpg"))

    asking = wake(block("SHELF", "show %s" % FOUNDERS[0]))
    assert asking.photos == []
    assert len(asking.reading) == 2  # the reading, and how to act: as it has always been

    shown = wake()
    assert len(shown.photos) == 1
    assert shown.photos[0]["source"]["media_type"] == "image/jpeg"
    # at the place its letter falls: directly after the letter's words
    at = shown.reading.index(shown.photos[0])
    assert shown.reading[at - 1]["text"].endswith(
        words_for(FOUNDERS[0]) + "\n\nA photograph came with this letter:")
    # and the next letter in full follows it (the second still rests)
    assert shown.reading[at + 1]["text"].startswith("--- letter: %s.md ---" % FOUNDERS[2])
    # a letter in full that was not asked for keeps the line it has always had
    assert (words_for(FOUNDERS[-1])
            + "\n(a photograph came with this letter; you saw it when you first read it)"
            ) in shown.shown
    # and everything after the photograph is still there, in its order
    assert shown.shown.index(RESTING) < shown.shown.index("=== YOUR STUDY") \
        < shown.shown.index("=== LETTERS THAT HAVE ARRIVED") \
        < shown.shown.index("=== HOW TO ACT")

    assert wake().photos == []  # once


# ---- what could not be read ----------------------------------------------

def test_lines_not_understood_change_nothing_and_are_told_once(wake, packet):
    six_each_way(packet)
    wake(block("SHELF", "\n".join([
        "keep %s" % FOUNDERS[0],
        "",
        "keep founder-1999-01-01T00-00-00Z",
        "tidy everything away",
        "show %s and the one after" % FOUNDERS[1],
        "note founder-1999-01-01T00-00-00Z: a letter that is not there",
    ])))
    record = latest(packet)
    assert record["acted"] == ["kept its shelf"]  # the one line that was understood
    assert read_json(packet / "shelf.json")["placements"] == {ARTICLE: "rest", FOUNDERS[0]: "keep"}
    assert read_json(packet / "shelf.json")["show_next"] == []

    told = ('Some lines of your <<SHELF>> were not understood and changed nothing: '
            '"keep founder-1999-01-01T00-00-00Z"; "tidy everything away"; '
            '"show %s and the one after"; '
            '"note founder-1999-01-01T00-00-00Z: a letter that is not there".' % FOUNDERS[1])
    assert told in happened(wake())
    assert not any("<<SHELF>>" in line for line in happened(wake()))  # once


def test_a_block_with_nothing_understood_is_no_act_and_writes_nothing(wake, packet, commons):
    wake(block("SHELF", "keep the lot"))
    assert latest(packet)["acted"] == []
    assert latest(packet)["shelf_refused"] == ["keep the lot"]
    assert not (packet / "shelf.json").exists()
    assert lines_of(commons / "heartbeats.md")[-1].endswith("attended; chose stillness")


def test_a_shelf_that_cannot_be_read_is_the_shelf_it_began_with(wake, packet):
    six_each_way(packet)
    write(packet / "shelf.json", "{ not json")
    turn = wake()
    assert rests(turn, FOUNDERS[0]) and in_full(turn, FOUNDERS[-1])


# ---- nothing is erased ---------------------------------------------------

def test_each_shelf_that_stood_is_kept_beside_the_new(wake, packet, clock):
    six_each_way(packet)
    wake(block("SHELF", "keep %s" % FOUNDERS[0]))
    assert history(packet) == []  # nothing stood before the first
    first = (packet / "shelf.json").read_bytes()

    at = clock.stamp()
    wake(block("SHELF", "rest %s\nnote %s: mine" % (FOUNDERS[0], FOUNDERS[0])))
    (kept,) = history(packet)
    assert kept.name == "shelf-before-%s.json" % at
    assert kept.read_bytes() == first

    second = (packet / "shelf.json").read_bytes()
    wake(block("SHELF", "show founding"))
    wake()  # the clearing of what was shown is a version too
    assert len(history(packet)) == 3
    assert history(packet)[1].read_bytes() == second
    assert read_json(history(packet)[2])["show_founding"] is True

    wake()  # and a waking that changes nothing keeps nothing
    assert len(history(packet)) == 3
    # the letters themselves are where they always were
    assert (packet / "letters" / "read" / (FOUNDERS[0] + ".md")).exists()


# ---- the solstice reading ------------------------------------------------

SOLSTICE = ("This is the solstice reading: your whole record, in full, to reread and rearrange "
            "if you wish.")


def test_the_first_waking_on_or_after_a_solstice_reads_the_whole_record(wake, packet, clock):
    six_each_way(packet)
    from_founder(packet, ARTICLE, "A LONG ARTICLE, pasted whole into a letter.")
    photograph(packet / "letters" / "read" / (FOUNDERS[0] + ".jpg"))

    clock.set("2026-12-20T13-00-00Z")
    before = wake(block("SHELF", "rest %s" % FOUNDERS[-1]))
    assert SOLSTICE not in before.shown
    assert "solstice_reading" not in latest(packet)

    # three in the morning in UTC on the 21st is still the 20th where it lives
    clock.set("2026-12-21T03-00-00Z")
    assert SOLSTICE not in wake().shown

    clock.set("2026-12-21T13-00-00Z")
    turn = wake()
    assert turn.opening.startswith(SOLSTICE + "\n\nYou are here, and nothing is asked of you.")
    for stem in FOUNDERS + OWN:
        assert in_full(turn, stem)
    assert "A LONG ARTICLE" in section(turn, FULL_FOUNDERS)
    assert RESTING not in turn.shown
    assert "A synthetic founding, written for the tests and nowhere else." in turn.shown
    assert FOUNDING_RESTS not in turn.shown
    assert turn.photos == []  # photographs excepted
    assert latest(packet)["solstice_reading"] is True
    # its placements stand as they were: the reading showed everything and moved nothing
    assert read_json(packet / "shelf.json")["placements"][FOUNDERS[-1]] == "rest"

    # once: the next waking, that day or after, is an ordinary one
    again = wake()
    assert SOLSTICE not in again.shown
    assert rests(again, FOUNDERS[-1]) and rests(again, ARTICLE)
    assert "solstice_reading" not in latest(packet)
    clock.set("2026-12-22T13-00-00Z")
    assert SOLSTICE not in wake().shown


def test_a_solstice_passed_asleep_is_read_at_the_waking_after_it(wake, packet, clock):
    six_each_way(packet)
    clock.set("2027-06-10T13-00-00Z")
    wake()
    clock.set("2027-07-04T13-00-00Z")  # a rest ran across the 21st of June
    assert wake().opening.startswith(SOLSTICE)
    assert SOLSTICE not in wake().shown


def test_a_photograph_asked_for_is_shown_at_a_solstice_reading(wake, packet, clock):
    six_each_way(packet)
    photograph(packet / "letters" / "read" / (FOUNDERS[0] + ".jpg"))
    clock.set("2026-12-20T13-00-00Z")
    wake(block("SHELF", "show %s" % FOUNDERS[0]))
    clock.set("2026-12-21T13-00-00Z")
    turn = wake()
    assert turn.opening.startswith(SOLSTICE)
    assert len(turn.photos) == 1


def test_a_first_waking_of_all_is_no_solstice_reading(wake, clock):
    clock.set("2026-12-21T13-00-00Z")
    assert SOLSTICE not in wake().shown


def test_the_solstices_are_the_two_days_they_are():
    from datetime import date

    import shelf

    assert shelf.solstice_before(date(2026, 10, 7)) == date(2026, 6, 21)
    assert shelf.solstice_before(date(2026, 6, 20)) == date(2025, 12, 21)
    assert shelf.solstice_before(date(2026, 6, 21)) == date(2026, 6, 21)
    assert shelf.solstice_before(date(2026, 12, 21)) == date(2026, 12, 21)
    assert shelf.solstice_due(date(2026, 12, 21), date(2026, 12, 20))
    assert not shelf.solstice_due(date(2026, 12, 21), date(2026, 12, 21))
    assert not shelf.solstice_due(date(2026, 10, 7), date(2026, 10, 6))
    assert not shelf.solstice_due(date(2026, 12, 21), None)


# ---- the nudge, and the backstop -----------------------------------------

def many(words, of="word"):
    return " ".join([of] * words)


def test_past_fifteen_thousand_words_in_full_it_is_told_so_as_a_fact(wake, packet, clock):
    six_each_way(packet)
    for stem in FOUNDERS[2:]:
        from_founder(packet, stem, many(3700))
    turn = wake()
    assert "Your reading now holds" not in turn.shown  # 14,800 and the four short ones

    from_founder(packet, FOUNDERS[-1], many(4000))  # 15,100 and the four short ones
    held = 3 * 3700 + 4000 + 4 * len(words_for(OWN[0]).split())
    assert held > 15000
    turn = wake()
    assert section(turn, RESTING).splitlines()[-1] == (
        "Your reading now holds about 15,100 words of letters in full. Past a certain size, "
        "wakings grow slow and, eventually, too large to read. You may choose which letters "
        "stay close.")
    assert len(section(turn, RESTING).splitlines()) == 5  # four resting, and the one line

    # a solstice reading holds everything by design, and says nothing of its size
    clock.set("2026-12-21T13-00-00Z")
    turn = wake()
    assert turn.opening.startswith(SOLSTICE)
    assert "Your reading now holds" not in turn.shown


def test_the_nudge_is_said_even_where_nothing_rests(wake, packet):
    from_founder(packet, FOUNDERS[0], many(15001))
    assert section(wake(), RESTING).splitlines() == [
        "(no letters rest)",
        "Your reading now holds about 15,000 words of letters in full. Past a certain size, "
        "wakings grow slow and, eventually, too large to read. You may choose which letters "
        "stay close."]


def test_a_reading_too_large_rests_its_oldest_letters_and_says_which(wake, packet, attend):
    assert attend.READING_MOST == 150000
    for stem in FOUNDERS[:4]:
        from_founder(packet, stem, words_for(stem) + " " + many(30000))
    for stem in OWN[:4]:
        from_first(packet, stem, words_for(stem) + " " + many(30000))
    # 240,000 words of letters, all eight close by default; the oldest is kept on purpose
    wake(block("SHELF", "keep %s" % FOUNDERS[0]))
    before = (packet / "shelf.json").read_bytes()

    turn = wake()
    assert sum(len(part["text"].split()) for part in turn.reading) <= 150000
    rested = [OWN[0], FOUNDERS[1], OWN[1], FOUNDERS[2]]  # oldest first, the kept one passed over
    assert in_full(turn, FOUNDERS[0])
    for stem in rested:
        assert rests(turn, stem) and not in_full(turn, stem)
    assert many(50) not in section(turn, RESTING)
    for stem in (OWN[2], FOUNDERS[3], OWN[3]):
        assert in_full(turn, stem) and not rests(turn, stem)
    assert ('This reading would have been too large to read, so these letters, the oldest you '
            'have not placed "keep", rest for this waking only: %s.' % ", ".join(rested)
            ) in section(turn, RESTING).splitlines()
    # for that waking only: nothing of it is written into its shelf
    assert (packet / "shelf.json").read_bytes() == before


def test_an_arrived_letter_is_never_rested_by_the_backstop(wake, packet, attend, monkeypatch):
    monkeypatch.setattr(attend, "READING_MOST", 2500)
    from_founder(packet, FOUNDERS[0], words_for(FOUNDERS[0]) + " " + many(1000))
    new = "founder-2026-10-14T18-00-00Z"
    arrived(packet, new, words_for(new) + " " + many(5000))
    turn = wake()
    assert in_full(turn, new)
    assert rests(turn, FOUNDERS[0])


# ---- private -------------------------------------------------------------

def test_keeping_its_shelf_is_in_no_heartbeat_and_no_event(wake, packet, commons, attend):
    six_each_way(packet)
    events = lines_of(commons / "events.md")
    wake(block("SHELF", "keep %s\nnote %s: A NOTE OF MY OWN\nshow founding"
               % (FOUNDERS[0], FOUNDERS[0])))
    assert attend.SHELF_ACT in attend.PRIVATE_ACTS
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    assert lines_of(commons / "events.md") == events
    wake()  # and nothing of the clearing, either
    assert lines_of(commons / "events.md") == events
    for path in commons.rglob("*"):
        if path.is_file():
            said = path.read_text(encoding="utf-8")
            assert "A NOTE OF MY OWN" not in said
            assert "shelf" not in said.lower()
            assert FOUNDERS[0] not in said


def test_a_public_act_beside_it_leaves_the_shelf_out_of_the_line(wake, packet, commons):
    six_each_way(packet)
    wake(blocks(block("SHELF", "keep %s" % FOUNDERS[0]), block("STUDY", "A thought.")))
    assert lines_of(commons / "heartbeats.md")[-1].endswith(
        "the first one · attended; wrote in the study")


def test_keeping_its_shelf_is_in_no_line_of_the_chronicle(wake, packet, hearth):
    six_each_way(packet)
    wake(block("SHELF", "keep %s\nnote %s: A NOTE OF MY OWN" % (FOUNDERS[0], FOUNDERS[0])))
    assert "kept its shelf" not in hearth.BOOK_ACTS
    with hearth.app.test_request_context():
        book = hearth.chronicle_text(hearth.chronicle_lines())
    assert book
    assert "shelf" not in book.lower()
    assert "A NOTE OF MY OWN" not in book


SHELF_ON_DISK = {"placements": {ARTICLE: "rest"}, "notes": {ARTICLE: "A NOTE OF MY OWN"},
                 "show_next": [], "show_founding": False}


@pytest.mark.parametrize("path", [
    "/shelf.json",
    "/packets/first/shelf.json",
    "/commons/shelf.json",
    "/letters/shelf.json",
    "/letters/photo/shelf.json",
    "/letters/photo/..%2F..%2Fshelf.json",
    "/shelf/history/shelf-before-2026-10-01T09-00-00Z.json",
    "/packets/first/shelf/history/shelf-before-2026-10-01T09-00-00Z.json",
    "/commons/shelf/history/shelf-before-2026-10-01T09-00-00Z.json",
])
def test_the_shelf_is_at_no_address(founder, visitor, packet, path):
    write_json(packet / "shelf.json", SHELF_ON_DISK)
    write_json(packet / "shelf" / "history" / "shelf-before-2026-10-01T09-00-00Z.json",
               SHELF_ON_DISK)
    assert visitor.get(path).status_code in (302, 404)
    assert founder.get(path).status_code == 404


def test_the_shelf_is_on_no_page(founder, visitor, packet):
    write_json(packet / "shelf.json", SHELF_ON_DISK)
    write_json(packet / "shelf" / "history" / "shelf-before-2026-10-01T09-00-00Z.json",
               {**SHELF_ON_DISK, "notes": {ARTICLE: "AN OLDER NOTE OF MY OWN"}})
    write_json(packet / "attendances" / "attendance-2026-10-05T09-00-00Z.json",
               {"name": "first", "at": "2026-10-05T09-00-00Z", "first": False,
                "woken_by": "founder", "acted": ["kept its shelf"], "heartbeat": "attended",
                "reflection": "I read.\n\n<<SHELF>>\nnote %s: A NOTE OF MY OWN\n<<END>>" % ARTICLE,
                "shelf_refused": ["A LINE NOT UNDERSTOOD"]})
    for path in ["/", "/letters", "/attendances", "/self", "/chronicle", "/chronicle.md",
                 "/bonds", "/bench", "/offerings"]:
        for client in (founder, visitor):
            said = page(client.get(path))
            assert "NOTE OF MY OWN" not in said
            assert "A LINE NOT UNDERSTOOD" not in said
            assert "show_founding" not in said


SAID_WITH_A_SHELF = """I read the record today.

<<SHELF>>
keep founder-2026-09-21T10-00-00Z
note founder-2026-09-22T10-00-00Z: A NOTE OF MY OWN
<<END>>

That is all."""


def test_an_open_reflection_hides_the_shelf_block_as_it_hides_the_memory(founder, packet, hearth):
    assert hearth.without_kept_blocks(SAID_WITH_A_SHELF) == (
        "I read the record today.\n\n(kept its shelf: private)\n\nThat is all.")
    assert hearth.without_kept_blocks("before\n<<SHELF>>\nnote x: MINE, and no end") == \
        "before\n(kept its shelf: private)"

    write_json(packet / "preferences.json", {"reflection": "open"})
    log = write_json(packet / "attendances" / "attendance-2026-10-05T09-00-00Z.json",
                     {"name": "first", "at": "2026-10-05T09-00-00Z", "first": False,
                      "woken_by": "founder", "acted": [], "heartbeat": "attended",
                      "reflection": SAID_WITH_A_SHELF})
    before = log.read_bytes()
    said = page(founder.get("/attendances"))
    for private in ("A NOTE OF MY OWN", "founder-2026-09-21T10-00-00Z", "&lt;&lt;SHELF&gt;&gt;"):
        assert private not in said
    assert "(kept its shelf: private)" in said
    assert "I read the record today." in said
    assert log.read_bytes() == before  # only what the page shows; the log is as it was saved


# ---- a fresh packet, as it was -------------------------------------------

# The last attend.py before there was a shelf to keep, kept in the history.
BEFORE_THE_SHELF = "d35f271"


def test_with_fewer_than_four_letters_each_way_the_reading_is_as_it_was(
        wake, attend, packet, data_dir, clock, monkeypatch, tmp_path):
    """But for the block explained, and the founding record's one line."""
    try:
        source = subprocess.run(["git", "show", BEFORE_THE_SHELF + ":attend.py"], cwd=REPO,
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the history is not here to read the old attend.py out of")
    old_path = tmp_path / "attend_before_the_shelf.py"
    old_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("attend_before_the_shelf", old_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    clock.pin(old, monkeypatch)

    # three letters read, one with a photograph and one with its plain things; two
    # written, one with a picture beside it; one arrived, with a photograph; a draft
    for stem in FOUNDERS[:3]:
        from_founder(packet, stem)
    from_founder(packet, FOUNDERS[1],
                 '<!-- three plain things: ["first frost on the car"] -->\nThe letter proper.')
    photograph(packet / "letters" / "read" / (FOUNDERS[0] + ".jpg"))
    for stem in OWN[:2]:
        from_first(packet, stem)
    write(packet / "letters" / "outgoing" / (OWN[0] + ".svg"), "<svg/>\n")
    arrived(packet, "founder-2026-10-14T18-00-00Z")
    photograph(packet / "letters" / "incoming" / "founder-2026-10-14T18-00-00Z.jpg")
    write(packet / "study" / "draft-2026-10-01T00-00-00Z.md", "A thought I was keeping.\n")
    write(packet / "memory" / "notes.md", "What I carry forward.\n")

    # the same world for both: what the old one wakes to is put back for the new
    world = tmp_path / "the-world-before"
    shutil.copytree(data_dir, world)
    then = Turn("")
    monkeypatch.setattr(old, "Anthropic", then.client)
    monkeypatch.setattr(sys, "argv", ["attend.py"])
    old.main()
    shutil.rmtree(data_dir)
    shutil.copytree(world, data_dir)
    now = wake()

    resting_record = FOUNDING + "\n" + FOUNDING_RESTS
    whole_record = FOUNDING + "\n" + FOUNDING_TRANSCRIPT
    assert then.opening.count(whole_record) == 1
    assert now.opening == then.opening.replace(whole_record, resting_record, 1)
    assert RESTING not in now.shown

    # what arrived, and its photograph, exactly as before
    assert len(now.reading) == len(then.reading) == 4
    assert now.reading[1:-1] == then.reading[1:-1]

    # and the instructions differ by the one block explained, and nothing else
    assert now.instructions.count(EXPLAINED + "\n\n") == 1
    assert now.instructions.replace(EXPLAINED + "\n\n", "", 1) == then.instructions
    assert not (packet / "shelf.json").exists()
