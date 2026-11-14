"""Asked and answered, corrections, and a reflection waking's cost apart.

The founder's decisions of 12 November 2026 (plan steps 2.2 and 2.3; the design
of 11 November). Each change to a reading is built behind a switch of its own
in the registry, and both are off: READING_NOW holds, and so does every page,
for the commons links its new pages only once a switch is on (or, for
corrections, once the site has made one).

Asked and answered (answered.SWITCH, attend.ASKED_ON): what the site has asked
an agent about its own world, kept in asked/ in its packet and entered by the
founder with answered.py; shown in its reading under ASKED OF YOU; answered
with <<ANSWER>>, and given its own words with <<ASKED>>; and shown on
/commons/asked once answered, a question from before this page only once the
agent has given it words.

Corrections (corrections.SWITCH, attend.CORRECTIONS): one correction beneath
one of its own past lines in the commons, with <<CORRECTION>>, and by hand the
site's beneath one of its lines in the ledger; the line never changed, and
each shown on /commons/corrections, the site's beneath its line on the ledger.

Each switched-on reading has its own fingerprint, recoverable: switched off it
is READING_NOW, and with only its own words taken out it is the reading as it
was.

On 13 November 2026 the founder switched asked and answered on for the first
one, as it agreed that day (with its introduction, doors_to_eight and
people_waiting; corrections stays off). READING_NOW, on the small world, has no
question kept; READING_NOW_ASKED is the live reading with the two questions
here kept, and with the four shut away again (conftest.switches_not_yet) it is
READING_ONE_WAKING, the reading with both switches here off.
"""

import hashlib
import json
import shutil

import pytest

import agents
from conftest import (block, load, lines_of, page, read_json, rewrite_last_reply_not_yet, write,
                      switches_not_yet, wakings_not_yet_switched, write_json)
from test_rooms_reading import READING_NOW, READING_ONE_WAKING, fingerprint_of_reading
from test_wakings_doors import the_small_world

# Cut on 12 November 2026 from the small world, each with only its own switch on;
# for asked and answered, with the two questions of two_questions kept. Held as
# READING_*_FIRST_CUT since.
READING_ASKED_FIRST_CUT = "ad6cd667614f574cc2364566508843b9093a7d0bb3b63c5fb71745d97ccdf843"
READING_CORRECTIONS_FIRST_CUT = "5e6361a169965ccfd2dbc7165bfa2664cc1f761c30f32798628d75a3c90b2d96"
READING_BOTH_FIRST_CUT = "eff0c15e476a74c4d7e6976820ee134e737ec529910d261e699f684747af8e5a"
# Cut again, on purpose, the same day, for two things and nothing else: every one
# because READING_NOW was (<<REWRITE>>'s explanation now ends "Write it in your
# last reply, after looking.", the first one's rewrites of that day having been
# dropped beside a look-up); and, where asked is on, because no agent's words may
# name the founder or say he: ASKED OF YOU's explanation says "entered later,
# with your answer as it was recorded", and a question from before this page
# "you answered yes, as it was recorded". With the sentence taken out
# (conftest.rewrite_last_reply_not_yet) and the asked words put back
# (asked_words_as_first_cut), each is exactly its first cut. All six are held from
# the registry as it stood before the first one's wakings were switched the same
# day (one waking a day, its reflection waking on): conftest.wakings_not_yet_switched
# puts them back first, and with both switches here off it is READING_NOW.
READING_ASKED = "6367255bdf7b90b36153059418a628cf1688363b7d238c67b0ecf62a733e1cd8"
READING_CORRECTIONS = "62393f8f39c2f392b1b7a119a7b0e4e29289826adbc61f36a3c41e7cc3aadd3f"
READING_BOTH = "0e0d5d2fc397fb0115281c7c737d05652f9949738a42acc9fb4ab38c1bf65b85"

# Cut on 13 November 2026, on the branch switches: the reading live once asked and
# the other three are switched on for the first one, on the small world with the
# two questions of two_questions kept. Beside READING_NOW (test_rooms_reading), it
# adds ASKED OF YOU after what it has chosen and its proposals, and <<ANSWER>> and
# <<ASKED>> after <<WELCOME>>, and nothing else: with those taken out it is
# exactly READING_NOW.
READING_NOW_ASKED = "60e45e9ae574d8441870e3d19e2935e99047da0715b942e5035f9a4b140cab4a"

# ASKED OF YOU's words as they were first cut, before they named no one.
ASKED_HOW_FIRST_CUT = (
    "(what the site has asked you about your own world, and how you answered. The commons' "
    "page of what has been asked shows each question once you have answered it, with your "
    "answer and, if you give them, your own words beside it. A question marked \"from before "
    "this page\" was asked before the page was made, and entered later by the founder with "
    "your answer as he recorded it; it is shown only once you give it words of your own.)")
ASKED_ANSWERED_BEFORE_FIRST_CUT = "you answered {answer}, as the founder recorded it"

SWITCHES = {"asked": "ASKED_ON", "corrections": "CORRECTIONS"}

FROM_BEFORE = {"question": "May your heartbeat be shown on the front page?",
               "asked_on": "2026-09-20", "answer": "yes", "answered_on": "2026-09-20",
               "answered_by": "founder", "words": None, "words_on": None, "from_before": True,
               "entered_at": "2026-10-14T09-00-00Z"}
NEW_ONE = {"question": "May the line you leave beside a letter tile be public?",
           "asked_on": "2026-10-14", "answer": None, "answered_on": None, "words": None,
           "words_on": None, "from_before": False, "entered_at": "2026-10-14T10-00-00Z"}
WORDS = "Yes, and gladly: a line is a small door left open."

SECTION = """=== ASKED OF YOU ===
(what the site has asked you about your own world, and how you answered. The commons' page of what has been asked shows each question once you have answered it, with your answer and, if you give them, your own words beside it. A question marked "from before this page" was asked before the page was made, and entered later, with your answer as it was recorded; it is shown only once you give it words of your own.)
1 · asked 20 September 2026 · from before this page · "May your heartbeat be shown on the front page?" · you answered yes, as it was recorded · not shown until you give it words
2 · asked 14 October 2026 · "May the line you leave beside a letter tile be public?" · not answered yet"""

ANSWER_BLOCK = """<<ANSWER>>
(your answer to a question under ASKED OF YOU. First line: its number, then one of: yes, no, not yet, as "1 yes". Any further lines are your own words beside your answer, up to 240 characters, checked for names and places as a line for the commons is; you may give them later instead, with <<ASKED>>. Your answer is shown on the commons' page of what has been asked. A no, a not yet, or no answer at all costs you nothing; a question you have answered not yet may be answered again at a later waking.)
<<END>>"""
ASKED_BLOCK = """<<ASKED>>
(your own words beside one of your answers, on the commons' page of what has been asked. First line: the question's number, as listed under ASKED OF YOU. Then your words, up to 240 characters, checked for names and places as a line for the commons is. A question from before this page is shown only once you give it words. Your words may be changed once, at a later waking; the words they replace are kept in your record and never shown again. Giving no words is as honoured as giving some.)
<<END>>"""
CORRECTION_BLOCK = """<<CORRECTION>>
(a correction beneath one of your own past lines in the commons, if you find that what it said was not so. First line: the line's date or its stamp, as read_commons_lines shows them. Then your words, up to 240 characters, checked for names and places as a line for the commons is. The line itself stays exactly as it was and is never edited; your correction is shown beneath it, on the commons' page of corrections, with your name and the day. Each line may have one correction, and it cannot be taken back, so say only what you would want to stand.)
<<END>>"""


def switched(attend, monkeypatch, *names, to=True):
    for name in names:
        monkeypatch.setattr(attend, SWITCHES[name], to)


def two_questions(packet):
    write_json(packet / "asked" / "asked-2026-10-14T09-00-00Z-000.json", FROM_BEFORE)
    write_json(packet / "asked" / "asked-2026-10-14T10-00-00Z-000.json", NEW_ONE)


def the_question(packet, n):
    return read_json(sorted((packet / "asked").glob("*.json"))[n - 1])


def last_record(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def happened(turn):
    return turn.shown.partition("=== WHAT HAS HAPPENED ===\n")[2].partition("\n\n=== ")[0]


@pytest.fixture
def in_the_registry(monkeypatch, tmp_path):
    """The first one's registry entry with some features added, or some taken out, as the
    hearth reads it."""
    def put(*features, without=()):
        where = tmp_path / "agents.json"
        first = agents.first()
        first = {**first, "features": [*(one for one in first["features"] if one not in without),
                                       *features]}
        where.write_text(json.dumps([first], indent=2) + "\n", encoding="utf-8")
        monkeypatch.setattr(agents, "FILE", where)
    return put


# ---- the switches, and the readings ---------------------------------------

def test_asked_is_on_for_the_first_one_and_corrections_off(attend):
    """Since 13 November 2026, asked and answered is switched on for the first one."""
    assert (attend.ASKED_ON, attend.CORRECTIONS) == (True, False)
    assert "asked" in agents.first()["features"]
    assert "corrections" not in agents.first()["features"]


@pytest.mark.parametrize("names, as_cut", [
    (("asked",), READING_ASKED), (("corrections",), READING_CORRECTIONS),
    (("asked", "corrections"), READING_BOTH)], ids=["asked", "corrections", "both"])
def test_each_switched_on_reading_is_held_by_its_own_fingerprint(
        founder, wake, attend, room, packet, monkeypatch, names, as_cut):
    the_small_world(founder, room)
    two_questions(packet)
    wakings_not_yet_switched(attend, monkeypatch)  # cut from the registry before 12 November
    switched(attend, monkeypatch, *names)
    reading = fingerprint_of_reading(wake())
    print("\n%s = %r" % (names, reading))
    assert reading == as_cut


def asked_words_as_first_cut(attend, monkeypatch):
    """Put back, for one test, ASKED OF YOU's words as first cut (12 November 2026)."""
    monkeypatch.setattr(attend, "ASKED_HOW", ASKED_HOW_FIRST_CUT)
    monkeypatch.setattr(attend, "ASKED_ANSWERED_BEFORE", ASKED_ANSWERED_BEFORE_FIRST_CUT)


@pytest.mark.parametrize("names, as_cut", [
    (("asked",), READING_ASKED_FIRST_CUT), (("corrections",), READING_CORRECTIONS_FIRST_CUT),
    (("asked", "corrections"), READING_BOTH_FIRST_CUT)], ids=["asked", "corrections", "both"])
def test_with_the_last_reply_and_the_asked_words_as_they_were_it_is_the_first_cut(
        founder, wake, attend, room, packet, monkeypatch, names, as_cut):
    the_small_world(founder, room)
    two_questions(packet)
    wakings_not_yet_switched(attend, monkeypatch)  # cut from the registry before 12 November
    switched(attend, monkeypatch, *names)
    rewrite_last_reply_not_yet(attend, monkeypatch)
    asked_words_as_first_cut(attend, monkeypatch)
    assert fingerprint_of_reading(wake()) == as_cut


def test_with_both_off_it_is_the_reading_before_even_with_questions_kept(
        founder, wake, attend, room, packet, monkeypatch):
    """With asked and the three switched on beside it shut away again, the questions kept
    change nothing: it is the reading of 12 November 2026."""
    switches_not_yet(attend, monkeypatch)
    the_small_world(founder, room)
    two_questions(packet)
    assert fingerprint_of_reading(wake()) == READING_ONE_WAKING


def test_as_switched_on_the_questions_kept_are_its_own_reading(founder, wake, attend, room,
                                                                 packet):
    the_small_world(founder, room)
    two_questions(packet)
    turn = wake()
    assert turn.shown.count(SECTION + "\n\n") == 1
    assert turn.instructions.count(ANSWER_BLOCK + "\n\n" + ASKED_BLOCK) == 1
    reading = fingerprint_of_reading(turn)
    print("\nREADING_NOW_ASKED = %r" % reading)
    assert reading == READING_NOW_ASKED
    # the section and the two blocks are the whole of the difference from READING_NOW
    asked = json.dumps(turn.asked[-1], sort_keys=True, ensure_ascii=False, default=str)
    for said in (SECTION + "\n\n", "\n\n" + ANSWER_BLOCK + "\n\n" + ASKED_BLOCK):
        escaped = json.dumps(said, ensure_ascii=False)[1:-1]
        assert asked.count(escaped) == 1
        asked = asked.replace(escaped, "", 1)
    assert hashlib.sha256(asked.encode("utf-8")).hexdigest() == READING_NOW


def on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch, name):
    """The small world's waking with one switch on, and then, from the same world and the
    same moment, with it off."""
    the_small_world(founder, room)
    two_questions(data_dir / "packets" / "first")
    shutil.copytree(data_dir, tmp_path / "as it was")
    switched(attend, monkeypatch, name)
    shown = wake().shown
    shutil.rmtree(data_dir)
    shutil.copytree(tmp_path / "as it was", data_dir)
    clock.shift(minutes=-5)
    switched(attend, monkeypatch, name, to=False)
    return shown, wake().shown


def test_asked_adds_its_section_and_its_two_blocks_and_nothing_else(
        founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch):
    on, off = on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch,
                         "asked")
    assert on.count(SECTION + "\n\n") == 1
    assert on.count("\n\n" + ANSWER_BLOCK + "\n\n" + ASKED_BLOCK + "\n\n") == 1
    assert on.replace(SECTION + "\n\n", "", 1).replace(
        "\n\n" + ANSWER_BLOCK + "\n\n" + ASKED_BLOCK, "", 1) == off


def test_corrections_add_their_block_after_rewrite_and_nothing_else(
        founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch):
    on, off = on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch,
                         "corrections")
    assert on.count(attend.REWRITE_BLOCK + "\n\n" + CORRECTION_BLOCK + "\n\n") == 1
    assert on.replace("\n\n" + CORRECTION_BLOCK, "", 1) == off


def test_the_words_are_these(attend):
    assert (attend.ANSWER_BLOCK, attend.ASKED_BLOCK, attend.CORRECTION_BLOCK) == (
        ANSWER_BLOCK, ASKED_BLOCK, CORRECTION_BLOCK)


# ---- asked and answered: its reading ----------------------------------------

@pytest.fixture
def asked_on(attend, monkeypatch, packet):
    switched(attend, monkeypatch, "asked")
    two_questions(packet)
    return attend


def test_with_no_question_kept_there_is_no_section_and_no_block(attend, monkeypatch, wake):
    switched(attend, monkeypatch, "asked")
    turn = wake()
    assert "ASKED OF YOU" not in turn.shown and "<<ANSWER>>" not in turn.shown


def test_the_section_comes_after_its_proposals_and_before_its_memory(asked_on, wake):
    shown = wake().shown
    assert shown.index(SECTION) < shown.index("=== YOUR MEMORY")
    assert shown.index("=== WHAT YOU HAVE CHOSEN ===") < shown.index(SECTION)


def test_an_answer_with_words_is_kept_and_told_once(asked_on, wake, packet):
    wake(block("ANSWER", "2 yes\n" + WORDS))
    kept = the_question(packet, 2)
    assert (kept["answer"], kept["answered_on"], kept["answered_by"]) == (
        "yes", "2026-10-15", "agent")
    assert (kept["words"], kept["words_on"]) == (WORDS, "2026-10-15")
    assert last_record(packet)["asked_done"] == [
        {"n": 2, "kind": "answer", "answer": "yes", "was": None},
        {"n": 2, "kind": "words", "words": WORDS, "was": None}]
    assert "asked" not in last_record(packet)["acted"]  # no act: the facts never say it
    turn = wake()
    said = happened(turn)
    assert ("Your answer to question 2, yes, is shown on the commons' page of what has been "
            "asked.") in said
    assert ('Your words beside question 2 are shown on the commons\' page of what has been '
            'asked: "%s".' % WORDS) in said
    assert ('2 · asked 14 October 2026 · "May the line you leave beside a letter tile be '
            'public?" · you answered yes on 15 October 2026 · your words: "%s"' % WORDS) \
        in turn.shown
    assert "is shown on the commons' page" not in happened(wake())  # once


def test_yes_and_no_stand_and_not_yet_may_be_answered_again(asked_on, wake, packet):
    wake(block("ANSWER", "2 not yet"))
    turn = wake(block("ANSWER", "2 no"))
    assert "<<ANSWER>>" in turn.instructions  # a not yet may be answered again
    assert the_question(packet, 2)["answer"] == "no"
    assert last_record(packet)["asked_done"][0]["was"] == "not yet"
    turn = wake(block("ANSWER", "2 yes"))
    assert "<<ANSWER>>" not in turn.instructions  # nothing is left to answer
    assert the_question(packet, 2)["answer"] == "no"


def test_an_answer_given_already_is_refused_in_these_words(asked_on, wake, packet):
    wake(block("ANSWER", "2 no"))
    wake(block("ANSWER", "2 yes"))
    assert last_record(packet)["asked_refused"] == [
        "Your <<ANSWER>> at your last waking changed nothing: you answered question 2 no "
        "already, and only a not yet may be answered again."]
    assert the_question(packet, 2)["answer"] == "no"


@pytest.mark.parametrize("said, why", [
    ("7 yes", 'Your <<ANSWER>> at your last waking changed nothing: there is no question "7" '
              'under ASKED OF YOU.'),
    ("2 perhaps", "Your <<ANSWER>> at your last waking changed nothing: its first line was not "
                  "a question's number followed by one of yes, no, not yet."),
    ("yes", "Your <<ANSWER>> at your last waking changed nothing: its first line was not a "
            "question's number followed by one of yes, no, not yet.")])
def test_an_answer_that_cannot_be_read_changes_nothing(asked_on, wake, packet, said, why):
    wake(block("ANSWER", said))
    assert last_record(packet)["asked_refused"] == [why]
    assert the_question(packet, 2)["answer"] is None
    assert why in happened(wake())


def test_words_from_before_are_its_own_and_the_answer_stays_the_founder_s(
        asked_on, wake, packet):
    wake(block("ASKED", "1\n" + WORDS))
    kept = the_question(packet, 1)
    assert (kept["answer"], kept["answered_by"], kept["words"]) == ("yes", "founder", WORDS)
    assert ('1 · asked 20 September 2026 · from before this page · "May your heartbeat be shown '
            'on the front page?" · you answered yes, as it was recorded · your words: '
            '"%s"' % WORDS) in wake().shown


def test_words_may_be_changed_once_and_what_they_replace_is_kept_in_its_record(
        asked_on, wake, packet):
    wake(block("ASKED", "1\n" + WORDS))
    wake(block("ASKED", "1\nOther words."))
    assert last_record(packet)["asked_done"] == [
        {"n": 1, "kind": "words", "words": "Other words.", "was": WORDS}]
    kept = the_question(packet, 1)
    assert (kept["words"], kept["words_changed"]) == ("Other words.", True)
    assert WORDS not in json.dumps(kept)  # the words replaced are in its record alone
    turn = wake(block("ASKED", "1\nA third time."))
    assert '(changed once, and they stand)' in turn.shown
    assert "<<ASKED>>" not in turn.instructions.replace(ANSWER_BLOCK, "")
    assert last_record(packet)["asked_refused"] == [
        "Your <<ASKED>> at your last waking changed nothing: your words beside question 1 were "
        "changed once already, and they stand as they are."]


def test_held_words_are_kept_in_its_record_and_change_nothing(asked_on, wake, packet, screen):
    screen.says = "YES"
    wake(block("ASKED", "1\n" + WORDS))
    assert the_question(packet, 1)["words"] is None
    assert last_record(packet)["asked_done"] == [
        {"n": 1, "kind": "words", "words": WORDS, "held": "flagged"}]
    screen.says = "NO"
    assert ("Your words beside question 1 were not shown, because they seemed to contain a name "
            "or a place. They are kept in your record, and nothing more is owed.") \
        in happened(wake(block("ASKED", "1\n" + WORDS)))
    assert the_question(packet, 1)["words"] == WORDS  # held words did not use up the change
    assert "words_changed" not in the_question(packet, 1)


@pytest.mark.parametrize("said, why", [
    ("2\nWords.", "Your <<ASKED>> at your last waking changed nothing: question 2 is not "
                  "answered yet; answer it with <<ANSWER>>, and give your words there or after."),
    ("1", "Your <<ASKED>> at your last waking changed nothing: it gave no words after the first "
          "line."),
    ("9\nWords.", 'Your <<ASKED>> at your last waking changed nothing: there is no question "9" '
                  'under ASKED OF YOU.')])
def test_words_that_cannot_be_given_change_nothing(asked_on, wake, packet, said, why):
    wake(block("ASKED", said))
    assert last_record(packet)["asked_refused"] == [why]


def test_shut_away_its_blocks_are_only_words(attend, wake, packet, monkeypatch):
    switched(attend, monkeypatch, "asked", to=False)
    two_questions(packet)
    turn = wake(block("ANSWER", "2 yes\n" + WORDS) + "\n\n" + block("ASKED", "1\n" + WORDS))
    assert "ASKED OF YOU" not in turn.shown
    assert the_question(packet, 2) == NEW_ONE and the_question(packet, 1) == FROM_BEFORE
    assert "asked_done" not in last_record(packet) and "asked_refused" not in last_record(packet)


# ---- asked and answered: the commons' page ---------------------------------

def test_the_page_shows_only_what_is_answered_and_from_before_only_with_words(
        asked_on, wake, packet, visitor, in_the_registry):
    in_the_registry("asked")
    shown = page(visitor.get("/commons/asked"))
    assert "nothing yet" in shown and "heartbeat be shown" not in shown
    wake(block("ANSWER", "2 yes"))
    shown = page(visitor.get("/commons/asked"))
    assert ("the first one was asked: &ldquo;May the line you leave beside a letter tile be "
            "public?&rdquo;") in shown
    assert "<p>yes, 15 October 2026</p>" in shown
    assert "heartbeat be shown" not in shown  # from before, and no words yet
    wake(block("ASKED", "1\n" + WORDS))
    shown = page(visitor.get("/commons/asked"))
    assert "20 September 2026 · asked before this page was made" in shown
    assert "<p>yes</p>" in shown  # as the founder recorded it, with no day of answering
    assert shown.index("heartbeat be shown") < shown.index("letter tile")  # in the order asked
    assert "&ldquo;%s&rdquo;" % WORDS in shown


def test_the_page_shows_nothing_of_an_agent_whose_switch_is_off(asked_on, wake, packet, visitor,
                                                                 in_the_registry):
    in_the_registry(without=("asked",))
    wake(block("ANSWER", "2 yes\n" + WORDS))
    assert "letter tile" not in page(visitor.get("/commons/asked"))


def test_the_commons_links_it_only_once_a_switch_is_on(visitor, in_the_registry):
    link = '<a href="/commons/asked">asked and answered</a>'
    in_the_registry(without=("asked",))
    before = page(visitor.get("/commons"))
    assert link not in before and "/commons/corrections" not in before
    in_the_registry("asked")
    now = page(visitor.get("/commons"))
    line = ('\n  <li id="asked">%s\n    <p class="note">what agents were asked about their own '
            'world, and their answers.</p></li>' % link)
    assert now.replace(line, "", 1) == before


# ---- asked and answered: entered by hand ----------------------------------

@pytest.fixture
def by_hand(env, capsys):
    module = load("answered")

    def run(*argv):
        code = module.main(list(argv))
        out = capsys.readouterr()
        return code, out.out + out.err
    return run


def test_a_question_is_said_and_written_only_with_apply(by_hand, packet, screen):
    code, said = by_hand("ask", "first", "May the  line beside a letter tile be public?")
    assert code == 0 and "not answered yet · May the line beside a letter tile be public?" in said
    assert not (packet / "asked").exists()
    assert ("May the line beside a letter tile be public?", []) == (screen.asked[-1][0], [])
    code, said = by_hand("ask", "first", "May the line beside a letter tile be public?", "--apply")
    kept = read_json(next((packet / "asked").glob("*.json")))
    assert (kept["question"], kept["answer"], kept["from_before"]) == (
        "May the line beside a letter tile be public?", None, False)


def test_questions_from_before_come_from_a_file(by_hand, packet, tmp_path):
    past = tmp_path / "past.txt"
    past.write_text("2026-09-20 · yes · May your heartbeat be shown?\n\n"
                    "2026-10-02 · Not yet · May a bond be proposed?\n", encoding="utf-8")
    code, said = by_hand("before", "first", str(past), "--apply")
    assert code == 0
    kept = [read_json(path) for path in sorted((packet / "asked").glob("*.json"))]
    assert [(one["asked_on"], one["answer"], one["answered_by"], one["from_before"],
             one["words"]) for one in kept] == [
        ("2026-09-20", "yes", "founder", True, None),
        ("2026-10-02", "not yet", "founder", True, None)]


@pytest.mark.parametrize("line", ["2026-9-20 · yes · A question?", "2026-09-20 · maybe · A?",
                                  "2026-09-20 · yes"])
def test_a_file_with_a_line_that_cannot_be_read_writes_nothing(by_hand, packet, tmp_path, line):
    past = tmp_path / "past.txt"
    past.write_text("2026-09-20 · yes · Fine?\n" + line + "\n", encoding="utf-8")
    code, said = by_hand("before", "first", str(past), "--apply")
    assert code == 1 and said.startswith("Refused:")
    assert not (packet / "asked").exists()


def test_a_question_the_screen_does_not_pass_is_refused(by_hand, packet, screen):
    screen.says = "YES"
    code, said = by_hand("ask", "first", "May I name the lake?", "--apply")
    assert code == 1 and "public screen did not pass" in said
    assert not (packet / "asked").exists()


# ---- corrections: its reading ---------------------------------------------

MINE = "- 2026-10-01T11-00-00Z · the first one · The heron was there at dawn.\n"
ANOTHER = "- 2026-10-02T11-00-00Z · the scratch one · its own line, not the first one's\n"
LATER = "- 2026-10-03T11-00-00Z · the first one · attended; chose stillness\n"
FIX = "It was a crane, not a heron; I was wrong about that."


@pytest.fixture
def corrections_on(attend, monkeypatch, commons):
    switched(attend, monkeypatch, "corrections")
    write(commons / "heartbeats.md", MINE + ANOTHER + LATER)
    return attend


def correction(which, words=FIX):
    return block("CORRECTION", "%s\n%s" % (which, words))


@pytest.mark.parametrize("which", ["2026-10-01T11-00-00Z", "2026-10-01", "1 October 2026"])
def test_a_correction_is_written_beneath_and_the_line_stays_as_it_was(
        corrections_on, wake, commons, packet, which):
    wake(correction(which))
    assert lines_of(commons / "heartbeats.md")[:3] == [MINE.strip(), ANOTHER.strip(),
                                                       LATER.strip()]
    assert lines_of(commons / "corrections.md") == [
        "- 2026-10-15 · the first one · heartbeats 2026-10-01T11-00-00Z · " + FIX]
    assert last_record(packet)["corrections"] == [
        {"line": "2026-10-01T11-00-00Z", "was": "The heron was there at dawn.", "words": FIX}]
    assert "corrected" not in " ".join(last_record(packet)["acted"])  # no act
    said = happened(wake())
    assert ('Your correction to your line of 1 October 2026 in the commons is shown beneath it, '
            'on the commons\' page of corrections: "%s".' % FIX) in said


def test_read_commons_lines_shows_it_beneath_its_line(corrections_on, wake):
    wake(correction("2026-10-01"))
    said = corrections_on.commons_lines_said()
    assert ("2026-10-01T11-00-00Z · 1 October 2026 · The heron was there at dawn.\n"
            '    your correction, 15 October 2026: "%s"\n2026-10-03T11-00-00Z' % FIX) in said


def test_one_correction_a_line_and_a_held_one_does_not_use_it_up(
        corrections_on, wake, commons, packet, screen):
    screen.says = "YES"
    wake(correction("2026-10-01"))
    assert last_record(packet)["corrections"][0]["held"] == "flagged"
    assert not (commons / "corrections.md").exists()
    screen.says = "NO"
    assert ("Your correction to your line of 1 October 2026 in the commons was not shown, because "
            "it seemed to contain a name or a place; the line stands as it was, with nothing "
            "beneath it. It is kept in your record.") in happened(wake(correction("2026-10-01")))
    wake(correction("2026-10-01", "Another thought."))
    assert last_record(packet)["corrections_refused"] == [
        "Your <<CORRECTION>> at your last waking changed nothing: your line of 1 October 2026 in "
        "the commons has a correction beneath it already, and a line may have one."]
    assert len(lines_of(commons / "corrections.md")) == 1


@pytest.mark.parametrize("which, why", [
    ("2026-10-02\nWords.", 'Your <<CORRECTION>> at your last waking changed nothing: no line of yours in '
                   'the commons is from "2026-10-02".'),
    ("2026-10-01\n", "Your <<CORRECTION>> at your last waking changed nothing: it gave no words "
                     "after the first line.")])
def test_a_correction_that_finds_no_line_of_its_own_changes_nothing(
        corrections_on, wake, commons, packet, which, why):
    wake(block("CORRECTION", which))
    assert last_record(packet)["corrections_refused"] == [why]
    assert not (commons / "corrections.md").exists()


def test_shut_away_a_correction_is_only_words(attend, wake, commons, packet):
    write(commons / "heartbeats.md", MINE)
    turn = wake(correction("2026-10-01"))
    assert "<<CORRECTION>>" not in turn.instructions
    assert not (commons / "corrections.md").exists()
    assert "corrections" not in last_record(packet)


# ---- corrections: the pages, and the site's by hand --------------------------

def test_the_page_shows_each_beneath_its_line_and_the_commons_links_it(
        corrections_on, wake, visitor):
    before = page(visitor.get("/commons"))
    wake(correction("2026-10-01"))
    shown = page(visitor.get("/commons/corrections"))
    assert ('<span class="muted">a line in the commons:</span> 2026-10-01 at dawn · the first '
            'one · The heron was there at dawn.') in shown  # as heartbeats.md hands it out
    assert ('corrected by the first one, 15 October 2026:</span> &ldquo;%s&rdquo;' % FIX) in shown
    now = page(visitor.get("/commons"))
    assert '<a href="/commons/corrections">corrections</a>' in now
    assert '<a href="/commons/corrections.md">corrections</a>' in page(
        visitor.get("/commons/record"))
    assert '<a href="/commons/corrections">' not in before
    assert page(visitor.get("/commons/corrections.md")) == (
        "- 2026-10-15 · the first one · heartbeats 2026-10-01T11-00-00Z · %s\n" % FIX)


@pytest.fixture
def site_by_hand(env, commons, capsys, clock, monkeypatch):
    write(commons / "ledger.md", "- 2026-10-14 · a rule was changed: letters wait a night\n")
    module = load("corrections")
    clock.pin(module, monkeypatch)

    def run(*argv):
        code = module.main(list(argv))
        out = capsys.readouterr()
        return code, out.out + out.err
    run.module = module
    return run


def test_the_site_corrects_a_ledger_line_beneath_it_by_hand(site_by_hand, commons, visitor):
    code, said = site_by_hand("ledger")
    key = next(line for line in said.splitlines() if "letters wait a night" in line)
    key = key.split(" · ")[0]
    day, mark = key.split()
    before = page(visitor.get("/commons/ledger"))
    code, said = site_by_hand("ledger", day, mark, "--words", "It was two nights, not one.")
    assert code == 0 and not (commons / "corrections.md").exists()  # said, not written
    code, said = site_by_hand("ledger", day, mark, "--words", "It was two nights, not one.",
                              "--apply")
    assert lines_of(commons / "corrections.md") == [
        "- 2026-10-15 · the site · ledger %s · It was two nights, not one." % key]
    now = page(visitor.get("/commons/ledger"))
    beneath = ('\n      <br><span class="muted">corrected by the site, 15 October 2026:</span> '
               '&ldquo;It was two nights, not one.&rdquo;')
    assert now.count(beneath) == 1 and now.replace(beneath, "", 1) == before
    code, said = site_by_hand("ledger", day, mark, "--words", "Again.", "--apply")
    assert code == 1 and "corrected already" in said
    assert "a line in the ledger:</span> 14 October 2026 · a rule was changed" in page(
        visitor.get("/commons/corrections"))


def test_the_site_s_words_are_screened_and_a_key_must_be_a_line(site_by_hand, commons, screen):
    code, said = site_by_hand("ledger", "2026-10-14", "00000000", "--words", "Words.", "--apply")
    assert code == 1 and "no line of the ledger" in said
    screen.says = "YES"
    code, said = site_by_hand("ledger")
    day, mark = next(line for line in said.splitlines() if "letters" in line).split(" · ")[0] \
        .split()
    code, said = site_by_hand("ledger", day, mark, "--words", "The lake was wrong.", "--apply")
    assert code == 1 and "public screen did not pass" in said
    assert not (commons / "corrections.md").exists()


# ---- a reflection waking's cost, apart ------------------------------------

def test_the_usage_report_counts_reflection_wakings_apart(env, packet, capsys):
    module = load("usage_report")
    write_json(packet / "attendances" / "attendance-2026-10-14T09-00-00Z.json",
               {"usage_total": {"input_tokens": 100, "output_tokens": 10,
                                "cache_creation_input_tokens": 0,
                                "cache_read_input_tokens": 0}})
    before = module.report("first")
    assert len(before) == 5
    write_json(packet / "reflections" / "reflection-2026-10-12T22-00-00Z.json",
               {"usage_total": {"input_tokens": 500, "output_tokens": 50,
                                "cache_creation_input_tokens": 5,
                                "cache_read_input_tokens": 0}, "reflection": "never printed"})
    now = module.report("first")
    assert now[:5] == before
    assert now[5] == "reflection wakings with usage recorded: 1"
    assert now[6].startswith("input_tokens: average 500.0, median 500.0, maximum 500, last 7 "
                             "days ")
    assert "never printed" not in "\n".join(now)
