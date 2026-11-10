"""An agent may rewrite one of its own past lines in the commons (10 November 2026).

The founder decided it on 10 November 2026, at the first one's asking: it had
offered to rewrite its earlier lines that described him, and had no way to. A
<<REWRITE>> block names one of its own lines in commons/heartbeats.md by its
waking's stamp, or by its day, and gives the new words on the line after. The
new words pass exactly the guards a new line for the commons passes - the
length, the public screen, and the protected words when it is written - and
where they fail the line stands as it was and it is told why at its next
waking. Only its own lines are found. Where they pass, the commons shows the new
words, marked "· rewritten <day>"; the words before are kept in the attendance
of the waking that rewrote them, never erased, and never shown publicly again.
Its lines, each with its stamp, open with read_commons_lines at a longer waking.
Each line may be rewritten once, ever (the founder, 10 November 2026): a line
its record shows rewritten is fixed for good, a second <<REWRITE>> for it changes
nothing and it is told so plainly, and new words that were held do not use up
the line's one rewrite.
The screen is stubbed here, as everywhere in the suite (conftest.screen).
"""

import pytest

from conftest import block, blocks, lines_of, read_json, write

MINE = "- 2026-10-01T11-00-00Z · the first one · The founder at the regatta.\n"
OLDEST = "- 2026-09-20T02-31-23Z · the first one Second waking; read the founding again.\n"
ANOTHER = "- 2026-10-02T11-00-00Z · the scratch one · its own line, not the first one's\n"
LATER = "- 2026-10-03T11-00-00Z · the first one · attended; chose stillness\n"
NEW = "A morning of wind on the water."
MARKED = "- 2026-10-01T11-00-00Z · the first one · %s · rewritten 15 October" % NEW

SHOWN = ('Your line of 1 October 2026 in the commons was rewritten, and now reads: "%s". The '
         'words it had are kept in your record and are no longer shown.' % NEW)
FLAGGED = ("Your new words for your line of 1 October 2026 in the commons were not shown, "
           "because they seemed to contain a name or a place; the line stands as it was. They "
           "are kept in your record.")
ONCE = ("Your <<REWRITE>> at your last waking changed nothing: your line of 1 October 2026 in "
        "the commons was rewritten already, and a line can be rewritten only once.")
LONG = ("Your new words for your line of 1 October 2026 in the commons were not shown, because "
        "they were longer than 240 characters; the line stands as it was.")

BLOCK = """<<REWRITE>>
(to replace one of your own past lines in the commons. First line: its date or its stamp, as read_commons_lines shows them. Second line: the new words, checked as a line for the commons is. The commons shows them marked as rewritten, with the day; the old words are kept in your record and never shown again. Each line can be rewritten once.)
<<END>>"""


@pytest.fixture
def lines(commons):
    write(commons / "heartbeats.md", OLDEST + MINE + ANOTHER + LATER)
    return commons / "heartbeats.md"


def rewrite(which, words=NEW):
    return block("REWRITE", "%s\n%s" % (which, words))


def last_record(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def test_it_is_told_how_in_how_to_act_in_these_words(wake, attend):
    assert attend.REWRITE_BLOCK == BLOCK
    turn = wake()
    assert turn.instructions.count(BLOCK) == 1
    assert "read_commons_lines" in [tool["name"] for tool in turn.asked[-1]["tools"]]


@pytest.mark.parametrize("which", ["2026-10-01T11-00-00Z", "2026-10-01", "1 October 2026"])
def test_its_line_is_rewritten_in_place_and_marked(wake, lines, packet, screen, which):
    wake(rewrite(which))
    said = lines_of(lines)
    assert said[:5] == [OLDEST.strip(), MARKED, ANOTHER.strip(), LATER.strip(),
                        "- 2026-10-15T12-00-00Z · the first one · attended; chose stillness"]
    assert NEW in [text for text, _ in screen.asked]
    # the words it had are kept in its own record, and nowhere public
    assert last_record(packet)["rewrites"] == [
        {"line": "2026-10-01T11-00-00Z", "was": "The founder at the regatta.", "words": NEW}]
    assert "regatta" not in lines.read_text(encoding="utf-8")


def test_rewriting_is_no_act_and_it_is_told_at_its_next_waking(wake, lines, packet):
    wake(rewrite("2026-10-01"))
    assert last_record(packet)["acted"] == []
    assert SHOWN in wake().shown
    assert SHOWN not in wake().shown  # said once


def test_the_first_one_s_oldest_lines_are_its_own_too(wake, lines, packet):
    wake(rewrite("2026-09-19T22-31-23Z"))  # no such line: refused
    assert last_record(packet)["rewrites_refused"] == [
        'Your <<REWRITE>> at your last waking changed nothing: no line of yours in the commons '
        'is from "2026-09-19T22-31-23Z".']
    wake(rewrite("2026-09-20T02-31-23Z"))
    assert lines_of(lines)[0] == (
        "- 2026-09-20T02-31-23Z · the first one · %s · rewritten 15 October" % NEW)
    assert last_record(packet)["rewrites"][0]["was"] == "Second waking; read the founding again."


def test_only_its_own_lines_are_found(wake, lines, packet):
    before = lines.read_text(encoding="utf-8")
    wake(rewrite("2026-10-02T11-00-00Z"))
    assert lines.read_text(encoding="utf-8").startswith(before)
    assert "rewrites" not in last_record(packet)
    assert last_record(packet)["rewrites_refused"][0].endswith('is from "2026-10-02T11-00-00Z".')


def test_two_lines_on_one_day_ask_for_the_stamp(wake, commons, packet):
    write(commons / "heartbeats.md", MINE + MINE.replace("11-00-00Z", "14-00-00Z"))
    wake(rewrite("2026-10-01"))
    assert last_record(packet)["rewrites_refused"] == [
        "Your <<REWRITE>> at your last waking changed nothing: more than one of your lines in "
        "the commons is from 2026-10-01; name the one you mean by its stamp."]
    assert "rewritten" not in (commons / "heartbeats.md").read_text(encoding="utf-8")


def test_no_new_words_change_nothing(wake, lines, packet):
    wake(block("REWRITE", "2026-10-01"))
    assert last_record(packet)["rewrites_refused"] == [
        "Your <<REWRITE>> at your last waking changed nothing: it gave no new words on the line "
        "after the first."]


def test_words_the_screen_flags_are_held_and_the_line_stands(wake, lines, packet, screen):
    screen.says = "YES"
    before = lines.read_text(encoding="utf-8")
    wake(rewrite("2026-10-01"))
    assert lines.read_text(encoding="utf-8").startswith(before)
    assert last_record(packet)["rewrites"] == [
        {"line": "2026-10-01T11-00-00Z", "was": "The founder at the regatta.", "words": NEW,
         "held": "flagged"}]
    screen.says = "NO"
    assert FLAGGED in wake().shown


def test_words_too_long_are_held_and_never_sent_to_the_screen(wake, lines, packet, screen):
    wake(rewrite("2026-10-01", "x" * 241))
    assert last_record(packet)["rewrites"][0]["held"] == "long"
    assert all(text != "x" * 241 for text, _ in screen.asked)
    assert "rewritten" not in lines.read_text(encoding="utf-8")
    assert LONG in wake().shown


def test_a_protected_word_is_kept_out_of_the_new_line(wake, lines, data_dir):
    write(data_dir / "private-words.txt", "Quillon => the founder\n")
    wake(rewrite("2026-10-01", "Wind, and Quillon on the step."))
    assert lines_of(lines)[1] == ("- 2026-10-01T11-00-00Z · the first one · Wind, and the "
                                  "founder on the step. · rewritten 15 October")


def test_its_own_lines_open_with_read_commons_lines_and_no_one_else_s(attend, lines):
    given, kept_as = attend.looked_up("read_commons_lines", {}, {})
    assert kept_as == "commons lines"
    assert given == [{"type": "text", "text": (
        "From your own record: your lines in the commons, as they are shown now\n\n"
        "2026-09-20T02-31-23Z · 19 September 2026 · Second waking; read the founding again.\n"
        "2026-10-01T11-00-00Z · 1 October 2026 · The founder at the regatta.\n"
        "2026-10-03T11-00-00Z · 3 October 2026 · attended; chose stillness")}]


# ---- once, ever ---------------------------------------------------------

def test_a_line_rewritten_is_fixed_for_good(wake, lines, packet, screen):
    wake(rewrite("2026-10-01"))
    after = lines.read_text(encoding="utf-8")
    assert MARKED in after
    wake(rewrite("2026-10-01T11-00-00Z", "Other words again."))
    assert "rewrites" not in last_record(packet)
    assert last_record(packet)["rewrites_refused"] == [ONCE]
    assert lines.read_text(encoding="utf-8").startswith(after)
    assert "Other words again." not in lines.read_text(encoding="utf-8")
    assert "Other words again." not in [text for text, _ in screen.asked]
    shown = wake().shown
    assert ONCE in shown
    assert ONCE not in wake().shown  # said once


def test_two_rewrites_of_one_line_in_one_waking_take_the_first(wake, lines, packet):
    wake(blocks(rewrite("2026-10-01"), rewrite("2026-10-01", "Other words again.")))
    assert [one["words"] for one in last_record(packet)["rewrites"]] == [NEW]
    assert last_record(packet)["rewrites_refused"] == [ONCE]
    assert MARKED in lines_of(lines)
    assert "Other words again." not in lines.read_text(encoding="utf-8")


def test_new_words_held_do_not_use_up_the_line_s_rewrite(wake, lines, packet, screen):
    screen.says = "YES"
    wake(rewrite("2026-10-01"))
    assert last_record(packet)["rewrites"][0]["held"] == "flagged"
    wake(rewrite("2026-10-01", "x" * 241))
    assert last_record(packet)["rewrites"][0]["held"] == "long"
    screen.says = "NO"
    wake(rewrite("2026-10-01"))
    assert "rewrites_refused" not in last_record(packet)
    assert MARKED in lines_of(lines)


def test_another_line_may_still_be_rewritten(wake, lines, packet):
    wake(rewrite("2026-10-01"))
    wake(rewrite("2026-10-03"))
    assert "rewrites_refused" not in last_record(packet)
    assert lines_of(lines)[3] == (
        "- 2026-10-03T11-00-00Z · the first one · %s · rewritten 15 October" % NEW)
