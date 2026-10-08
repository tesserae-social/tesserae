"""Looking back: the first one's earlier self-documents and notes, shown to it at its asking.

It was built shut away behind attend.LOOKING_BACK, which is now on, the first
one having agreed to it (its letter of 7 October 2026). With that False
everything the first one is sent is what it was sent before there was any of
this, which is still held here against the attend.py that stood before it, by
turning the flag off, and in test_rooms_reading.py by the reading's
fingerprint. With it True, each kept
version is one line under its self-document and its notes, and one it asks for
is given whole at its next waking.

Every version here is written for the tests and nowhere else.
"""

import importlib.util
import json
import shutil
import subprocess
import sys

import pytest

from conftest import (REPO, Turn, block, explained_as_before, lines_of, page, read_json,
                      shut_away, solstices_as_before, stamps_as_before, write, write_json)

EARLIER = "=== YOUR EARLIER VERSIONS ==="
ASKED = "=== AN EARLIER VERSION, AS YOU ASKED ==="
NONE_KEPT = "No earlier versions are kept yet."
MEMORY = "=== YOUR MEMORY (notes you keep for yourself; not shown on the hearth) ==="
INTENTIONS = "=== YOUR STANDING INTENTIONS ==="

SELF_1 = "self-before-2026-09-10T09-00-00Z"
NOTES_1 = "notes-before-2026-09-18T09-00-00Z"
SELF_2 = "self-before-2026-10-02T09-00-00Z"
NOTES_2 = "notes-before-2026-10-09T09-00-00Z"

# Oldest first by the day each was set aside. The first self-document kept was in
# use from the founding (4 September, in the tests' commons); the first notes
# kept, from the first attendance that kept notes (12 September, below); and each
# one after, from the day the one before it of its kind was set aside.
LISTED = [
    "self-document · in use from 4 September 2026 until 10 September 2026 · " + SELF_1,
    "notes · in use from 12 September 2026 until 18 September 2026 · " + NOTES_1,
    "self-document · in use from 10 September 2026 until 2 October 2026 · " + SELF_2,
    "notes · in use from 18 September 2026 until 9 October 2026 · " + NOTES_2,
]

WORDS = {
    SELF_1: "# The first one\n\nAN EARLIER SELF, the first of them.",
    SELF_2: "# The first one\n\nAN EARLIER SELF, the second of them.",
    NOTES_1: "AN EARLIER NOTE: the gap between wakings is not a gap to me.",
    NOTES_2: "AN EARLIER NOTE: I am keeping the first note beside this one.",
}

VERSION_LINE = "show version <stem>: an earlier self-document or notes in full at your next waking"
NOTE_LINES = """keep note <name>: a named note always shown in full
rest note <name>: a named note shown as one line
show note <name>: a named note in full at your next waking only
"""

EXPLAINED = """<<SHELF>>
(how you keep your history. One instruction per line:
keep <stem>: always shown in full
rest <stem>: shown as one line
default <stem>: back to the default
note <stem>: your words, the line shown for a resting letter (at most 240 characters)
show <stem>: shown in full at your next waking only, photographs included
show founding: your founding record in full at your next waking
%s""" + NOTE_LINES + """Letters you haven't placed follow the default: the founder's last four letters and your own last four are shown in full; older ones rest. Nothing is ever erased. Your shelf is private.)
<<END>>"""


def attended(packet, at, acted):
    """One past attendance in its log, saying what was carried out at it."""
    write_json(packet / "attendances" / ("attendance-%s.json" % at),
               {"name": "first", "at": at, "first": False, "woken_by": "founder",
                "acted": acted, "heartbeat": "attended", "reflection": ""})


def versions_kept(packet, notes_first_kept="2026-09-12T09-00-00Z"):
    """Two earlier self-documents and two earlier notes, as attend.py keeps them.

    And the attendances behind them: one before it kept any notes, the one at
    which it first did, and one at which it kept them again; and one since the
    autumn turning, so that the waking a test holds is an ordinary one.
    """
    attended(packet, "2026-09-08T09-00-00Z", ["wrote in the study"])
    if notes_first_kept:
        attended(packet, notes_first_kept, ["wrote in the study", "kept notes"])
        attended(packet, "2026-09-18T09-00-00Z", ["kept notes"])
    attended(packet, "2026-09-25T09-00-00Z", ["wrote in the study"])
    for stem, words in WORDS.items():
        folder = packet / "self-history" if stem.startswith("self") else packet / "memory" / "history"
        write(folder / (stem + ".md"), words + "\n")
    write(packet / "memory" / "notes.md", "What I carry forward.\n")


def section(turn, heading):
    """One section of the reading: what stands under its heading."""
    return turn.shown.split(heading + "\n", 1)[1].split("\n\n=== ", 1)[0]


def happened(turn):
    return section(turn, "=== WHAT HAS HAPPENED ===").splitlines()


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


@pytest.fixture
def looking_back(attend, monkeypatch):
    monkeypatch.setattr(attend, "LOOKING_BACK", True)
    return attend


# ---- shut away -----------------------------------------------------------

# The last attend.py before there was any looking back, kept in the history.
BEFORE_LOOKING_BACK = "1e942d7"


def test_it_is_switched_on(attend):
    assert attend.LOOKING_BACK is True


def test_shut_away_it_is_sent_byte_for_byte_what_it_was_sent_before(
        attend, packet, data_dir, clock, monkeypatch, tmp_path):
    """Two wakings each, in one world that keeps versions and asks for one.

    The old attend.py and this one are sent the same bytes at both, and leave
    the same files behind them. What it has chosen came after, and is shut away
    with it; its door, which the old one had and kept shut away, stands in both
    as it stands now.
    """
    shut_away(attend, monkeypatch, "LOOKING_BACK", "CHOICES")
    explained_as_before(attend, monkeypatch)  # the old one knew no two-waking rule
    stamps_as_before(attend, monkeypatch)  # and said each moment as its raw stamp
    solstices_as_before(monkeypatch)  # and read the whole record back at the solstices
    try:
        source = subprocess.run(["git", "show", BEFORE_LOOKING_BACK + ":attend.py"], cwd=REPO,
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the history is not here to read the old attend.py out of")
    old_path = tmp_path / "attend_before_looking_back.py"
    old_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("attend_before_looking_back", old_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    clock.pin(old, monkeypatch)
    assert not hasattr(old, "LOOKING_BACK")
    monkeypatch.setattr(old, "DOOR_FOR_FIRST", attend.DOOR_FOR_FIRST)

    versions_kept(packet)
    letter = "founder-2026-10-01T09-00-00Z"
    write(packet / "letters" / "read" / (letter + ".md"), "A letter, read long ago.\n")
    # a shelf left asking for a version, as one would be if this were turned off again
    write_json(packet / "shelf.json", {"placements": {}, "notes": {}, "show_next": [],
                                       "show_founding": False, "show_versions": [SELF_1]})
    said = block("SHELF", "keep %s\nshow version %s\nshow version nothing-there" % (letter, SELF_1))

    def two_wakings(module):
        sent = []
        for at, reply in (("2026-10-15T12-00-00Z", said), ("2026-10-15T12-05-00Z", "")):
            clock.set(at)
            turn = Turn(reply)
            monkeypatch.setattr(module, "Anthropic", turn.client)
            monkeypatch.setattr(sys, "argv", ["attend.py"])
            module.main()
            sent.append(json.dumps(turn.asked[-1], sort_keys=True, ensure_ascii=False,
                                   default=str).encode("utf-8"))
        left = {path.relative_to(data_dir).as_posix(): path.read_bytes()
                for path in sorted(data_dir.rglob("*")) if path.is_file()}
        return sent, left

    world = tmp_path / "the-world-before"
    shutil.copytree(data_dir, world)
    sent_then, left_then = two_wakings(old)
    shutil.rmtree(data_dir)
    shutil.copytree(world, data_dir)
    sent_now, left_now = two_wakings(attend)

    assert sent_now == sent_then
    assert left_now == left_then
    for sent in sent_now:
        assert b"EARLIER VERSION" not in sent
        assert b"show version <stem>" not in sent
        assert b"AN EARLIER" not in sent
        assert SELF_1.encode("ascii") not in sent.replace(
            b'\\"show version %s\\"' % SELF_1.encode("ascii"), b"")


def test_shut_away_a_show_version_line_is_a_line_not_understood(wake, attend, packet,
                                                                monkeypatch):
    shut_away(attend, monkeypatch, "LOOKING_BACK")
    versions_kept(packet)
    asking = wake(block("SHELF", "show version %s" % SELF_1))
    assert EARLIER not in asking.shown and VERSION_LINE not in asking.instructions
    assert EXPLAINED % "" in asking.instructions
    assert latest(packet)["acted"] == []
    assert latest(packet)["shelf_refused"] == ["show version %s" % SELF_1]
    assert not (packet / "shelf.json").exists()

    told = wake()
    assert ('Some lines of your <<SHELF>> were not understood and changed nothing: '
            '"show version %s".' % SELF_1) in happened(told)
    assert ASKED not in told.shown and "AN EARLIER" not in told.shown
    assert not any("<<SHELF>>" in line for line in happened(wake()))  # once


# ---- the versions, one line each -----------------------------------------

def test_with_none_kept_the_section_says_so(wake, looking_back):
    turn = wake()
    assert section(turn, EARLIER) == NONE_KEPT
    assert ASKED not in turn.shown


def test_the_section_stands_after_its_self_document_and_its_memory(wake, looking_back, packet):
    versions_kept(packet)
    shown = wake().opening
    assert (shown.index("=== YOUR SELF-DOCUMENT") < shown.index(MEMORY) < shown.index(EARLIER)
            < shown.index(INTENTIONS))
    assert (MEMORY + "\nWhat I carry forward.\n\n" + EARLIER + "\n" + "\n".join(LISTED)
            + "\n\n" + INTENTIONS) in shown


def test_each_kept_version_is_one_line_oldest_first(wake, looking_back, packet):
    versions_kept(packet)
    turn = wake()
    assert section(turn, EARLIER).splitlines() == LISTED
    assert "AN EARLIER" not in turn.shown  # a line each, and none of their words


def test_a_version_it_sets_aside_is_listed_from_the_next_waking(wake, looking_back, packet, clock):
    first = wake(block("SELF", "# The first one\n\nVersion 2, in my own words."))
    assert section(first, EARLIER) == NONE_KEPT
    at = clock.stamp()  # set aside when the new one is confirmed, a waking later
    assert section(wake(block("SELF_CONFIRM", "yes")), EARLIER) == NONE_KEPT
    again = clock.stamp()
    wake(block("MEMORY", "First."))  # nothing stood before the first notes
    its_self = ("self-document · in use from 4 September 2026 until 15 October 2026 · "
                "self-before-" + at)
    assert section(wake(block("MEMORY", "Second.")), EARLIER).splitlines() == [its_self]
    # its first notes were kept that same day, and not at the founding
    assert section(wake(), EARLIER).splitlines() == [
        its_self,
        "notes · in use from 15 October 2026 until 15 October 2026 · notes-before-"
        + clock_after(again, minutes=5)]


def test_where_no_founding_is_recorded_the_first_self_document_says_only_until(
        wake, looking_back, packet, commons):
    versions_kept(packet)
    write(commons / "events.md", "2026-09-02 · word · the word was published\n")
    assert section(wake(), EARLIER).splitlines() == [
        "self-document · in use until 10 September 2026 · " + SELF_1,
        LISTED[1], LISTED[2], LISTED[3]]


def test_where_no_attendance_kept_notes_the_first_notes_say_only_until(
        wake, looking_back, packet):
    versions_kept(packet, notes_first_kept=None)
    wake(block("SHELF", "show version %s" % NOTES_1))
    shown = wake()
    only_until = "notes · in use until 18 September 2026 · " + NOTES_1
    assert section(shown, EARLIER).splitlines() == [LISTED[0], only_until, LISTED[2], LISTED[3]]
    assert section(shown, ASKED) == only_until + "\n\n" + WORDS[NOTES_1]


def clock_after(stamp, **how):
    from datetime import timedelta

    from conftest import STAMP_FORMAT, moment
    return (moment(stamp) + timedelta(**how)).strftime(STAMP_FORMAT)


# ---- the block explained -------------------------------------------------

def test_the_block_gains_its_line_after_show_founding(wake, looking_back):
    said = wake().instructions
    assert EXPLAINED % (VERSION_LINE + "\n") in said
    assert said.count(VERSION_LINE) == 1
    assert said.index("<<QUESTIONS>>") < said.index("<<SHELF>>") < said.index("<<LETTER>>")


def test_the_instructions_differ_by_that_one_line(wake, attend, monkeypatch):
    shut_away(attend, monkeypatch, "LOOKING_BACK")
    without = wake().instructions
    monkeypatch.setattr(attend, "LOOKING_BACK", True)
    assert wake().instructions.replace(VERSION_LINE + "\n", "", 1) == without


# ---- show version --------------------------------------------------------

def test_show_version_gives_it_in_full_at_the_next_waking_only(wake, looking_back, packet):
    versions_kept(packet)
    asking = wake(block("SHELF", "show version %s" % SELF_1))
    assert ASKED not in asking.shown  # not at the waking that asked
    assert latest(packet)["acted"] == ["kept its shelf"]
    assert "shelf_refused" not in latest(packet)
    assert read_json(packet / "shelf.json")["show_versions"] == [SELF_1]

    shown = wake()
    assert section(shown, ASKED) == LISTED[0] + "\n\n" + WORDS[SELF_1]
    assert shown.opening.index(EARLIER) < shown.opening.index(ASKED) < shown.opening.index(INTENTIONS)
    assert section(shown, EARLIER).splitlines() == LISTED  # the list stands as it was
    assert "show_versions" not in read_json(packet / "shelf.json")  # then cleared

    after = wake()
    assert ASKED not in after.shown and "AN EARLIER" not in after.shown
    # and the version is where it always was
    assert (packet / "self-history" / (SELF_1 + ".md")).read_text(encoding="utf-8") == \
        WORDS[SELF_1] + "\n"


def test_earlier_notes_are_shown_the_same_way_and_several_at_once(wake, looking_back, packet):
    versions_kept(packet)
    wake(block("SHELF", "Show Version %s.md\nshow version %s\nshow version %s"
               % (NOTES_2, SELF_2, NOTES_2)))
    assert read_json(packet / "shelf.json")["show_versions"] == [NOTES_2, SELF_2]
    shown = wake().opening
    assert shown.count(ASKED) == 2
    assert (ASKED + "\n" + LISTED[3] + "\n\n" + WORDS[NOTES_2] + "\n\n"
            + ASKED + "\n" + LISTED[2] + "\n\n" + WORDS[SELF_2] + "\n\n" + INTENTIONS) in shown


def test_a_version_is_asked_for_beside_letters_and_the_founding_record(wake, looking_back, packet):
    versions_kept(packet)
    letter = "founder-2026-09-21T10-00-00Z"
    write(packet / "letters" / "read" / (letter + ".md"), "A letter, read long ago.\n")
    wake(block("SHELF", "rest %s\nshow founding\nshow version %s" % (letter, NOTES_1)))
    assert read_json(packet / "shelf.json") == {
        "placements": {"founder-2026-10-01T15-15-05Z": "rest", letter: "rest"}, "notes": {},
        "show_next": [], "show_founding": True, "show_versions": [NOTES_1]}
    shown = wake()
    assert WORDS[NOTES_1] in section(shown, ASKED)
    assert "A synthetic founding" in shown.shown


def test_an_unknown_stem_changes_nothing_and_is_told_once(wake, looking_back, packet):
    versions_kept(packet)
    letter = "founder-2026-09-21T10-00-00Z"
    write(packet / "letters" / "read" / (letter + ".md"), "A letter, read long ago.\n")
    refused = ["show version self-before-1999-01-01T00-00-00Z",
               "show version",
               "show version %s" % letter,  # a letter is no version
               "show %s" % SELF_1,  # and a version is no letter
               "show version %s and the one after" % SELF_1]
    wake(block("SHELF", "\n".join(refused)))
    assert latest(packet)["acted"] == []
    assert latest(packet)["shelf_refused"] == refused
    assert not (packet / "shelf.json").exists()

    told = wake()
    assert ("Some lines of your <<SHELF>> were not understood and changed nothing: "
            + "; ".join('"%s"' % line for line in refused) + ".") in happened(told)
    assert ASKED not in told.shown
    assert not any("<<SHELF>>" in line for line in happened(wake()))  # once


def test_one_line_understood_beside_one_that_is_not(wake, looking_back, packet):
    versions_kept(packet)
    wake(block("SHELF", "show version %s\nshow version nothing-there" % SELF_2))
    assert latest(packet)["acted"] == ["kept its shelf"]
    assert latest(packet)["shelf_refused"] == ["show version nothing-there"]
    shown = wake()
    assert WORDS[SELF_2] in section(shown, ASKED)
    assert any("nothing-there" in line for line in happened(shown))


# ---- private -------------------------------------------------------------

def test_nothing_of_it_is_on_the_hearth_or_in_the_commons(
        wake, looking_back, hearth, founder, visitor, packet, commons, monkeypatch):
    monkeypatch.setattr(hearth.the_waking, "LOOKING_BACK", True)
    write_json(packet / "preferences.json", {"reflection": "open"})
    versions_kept(packet)
    events = lines_of(commons / "events.md")
    wake("I asked to look back.\n\n" + block("SHELF", "show version %s\nshow version %s"
                                              % (SELF_1, NOTES_1)))
    assert ASKED in wake("I read what I was.").shown
    assert lines_of(commons / "heartbeats.md")[-2].endswith("the first one · attended")
    assert lines_of(commons / "events.md") == events

    for path in ["/", "/letters", "/attendances", "/self", "/chronicle", "/chronicle.md",
                 "/commons", "/bench", "/rooms/first"]:
        for client in (founder, visitor):
            said = page(client.get(path))
            for private in ("AN EARLIER", "EARLIER VERSION", "self-before-", "notes-before-",
                            "show version", "show_versions", "No earlier versions"):
                assert private not in said, (path, private)
    assert "I asked to look back." in page(founder.get("/attendances"))
    for path in commons.rglob("*"):
        if path.is_file():
            said = path.read_text(encoding="utf-8")
            assert "AN EARLIER" not in said and "before-" not in said


@pytest.mark.parametrize("path", [
    "/self-history/" + SELF_1 + ".md",
    "/packets/first/self-history/" + SELF_1 + ".md",
    "/self/" + SELF_1,
    "/memory/history/" + NOTES_1 + ".md",
    "/packets/first/memory/history/" + NOTES_1 + ".md",
])
def test_an_earlier_version_is_at_no_address(looking_back, hearth, founder, visitor, packet,
                                             monkeypatch, path):
    monkeypatch.setattr(hearth.the_waking, "LOOKING_BACK", True)
    versions_kept(packet)
    assert visitor.get(path).status_code in (302, 404)
    assert founder.get(path).status_code == 404
