"""What it has chosen: the first one's own settings, said back to it in one place.

It was built shut away behind attend.CHOICES, which is now on, the first one
having agreed to it (its letter of 7 October 2026). With that False everything
the first one is sent is what it was sent before there was any of this, which
is still held here against the attend.py that stood before it, by turning the
flag off, and in test_rooms_reading.py by the reading's fingerprint. With it
True, a short
section stands directly after its self-document: one plain line for each choice
there is a record of, with the day that record carries, and one line saying
that nothing is set where there is none.

Every record here is written for the tests and nowhere else.
"""

import importlib.util
import json
import shutil
import subprocess
import sys

import pytest

from conftest import (REPO, Turn, block, explained_as_before, lines_of, page, shut_away, write,
                      write_json)

CHOSEN = "=== WHAT YOU HAVE CHOSEN ==="
NOTHING = "You have not set anything here yet; everything follows the defaults."
SELF = "=== YOUR SELF-DOCUMENT (packets/first/self.md) ==="
MEMORY = "=== YOUR MEMORY (notes you keep for yourself; not shown on the hearth) ==="

# The two records as they are really kept, with the values they really carry.
PREFERENCES = {"reflection": "private from now", "set_at": "2026-09-20T03-08-00Z",
               "chosen_in": "letter at attendance 2026-09-20T03-08",
               "note": "First wakings remain open by the first one's choice."}
DAWN = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
        "timezone": "America/Indiana/Indianapolis",
        "set_at": "2026-09-20T03-30-35Z",
        "chosen_in": "letter at attendance 2026-09-20T03-30",
        "note": "Dawn wakings, daily for now, in the first one's words."}

REFLECTIONS = "Your reflections are kept private, by your choice since 20 September 2026."
WAKING = "You wake daily at dawn, by your choice since 20 September 2026."
ARTICLE_RESTS = "The 1 October letter rests, as you asked on 6 October."

ARTICLE = "founder-2026-10-01T15-15-05Z"
FOUNDERS = ["founder-2026-09-2%dT10-00-00Z" % n for n in range(1, 4)]
OWN = "to-founder-2026-09-22T11-00-00Z"


def letters(packet, article=True):
    """Three letters of the founder's long read, one of its own, and the article."""
    for stem in FOUNDERS + ([ARTICLE] if article else []):
        write(packet / "letters" / "read" / (stem + ".md"), "A letter, read long ago.\n")
    write(packet / "letters" / "outgoing" / (OWN + ".md"), "My answer to it.\n")


def shelf_of(packet, placements, notes=None):
    write_json(packet / "shelf.json", {"placements": placements, "notes": notes or {},
                                       "show_next": [], "show_founding": False})


def chosen(turn):
    """The lines of the section, as the reading gives them."""
    return turn.opening.split(CHOSEN + "\n", 1)[1].split("\n\n=== ", 1)[0].splitlines()


@pytest.fixture
def choices(attend, monkeypatch):
    monkeypatch.setattr(attend, "CHOICES", True)
    return attend


@pytest.fixture
def door_open(attend, monkeypatch):
    """The first one's door, turned on for a test."""
    monkeypatch.setattr(attend, "DOOR_FOR_FIRST", True)
    return attend


# ---- shut away -----------------------------------------------------------

# The last attend.py before there was any of this, kept in the history.
BEFORE_CHOICES = "255b43f"


def everything_set(packet):
    """A world with a record of every choice the section could say."""
    letters(packet)
    write_json(packet / "preferences.json", PREFERENCES)
    write_json(packet / "rhythm.json", DAWN)
    write_json(packet / "door.json", {"state": "open", "room": 3,
                                      "set_at": "2026-10-03T14-00-00Z"})
    shelf_of(packet, {ARTICLE: "rest", FOUNDERS[0]: "keep", FOUNDERS[1]: "rest"})
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": "a letter arrives", "words": ""})


def test_it_is_switched_on(attend):
    assert attend.CHOICES is True


def test_shut_away_it_is_sent_byte_for_byte_what_it_was_sent_before(
        attend, packet, data_dir, clock, monkeypatch, tmp_path):
    """Two wakings each, in one world where every choice has its record.

    The old attend.py and this one are sent the same bytes at both, and leave
    the same files behind them. Its door and its looking back, which the old
    one had and kept shut away, stand in both as they stand now.
    """
    shut_away(attend, monkeypatch, "CHOICES")
    explained_as_before(attend, monkeypatch)  # the old one knew no two-waking rule
    try:
        source = subprocess.run(["git", "show", BEFORE_CHOICES + ":attend.py"], cwd=REPO,
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the history is not here to read the old attend.py out of")
    old_path = tmp_path / "attend_before_choices.py"
    old_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("attend_before_choices", old_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    clock.pin(old, monkeypatch)
    assert not hasattr(old, "CHOICES")
    for flag in ("DOOR_FOR_FIRST", "LOOKING_BACK"):
        monkeypatch.setattr(old, flag, getattr(attend, flag))

    everything_set(packet)
    said = "\n\n".join([block("SHELF", "keep %s\nrest %s" % (OWN, ARTICLE)),
                        block("RHYTHM", "09:30")])

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
        assert b"WHAT YOU HAVE CHOSEN" not in sent
        assert b"by your choice since" not in sent
        assert b"You have not set anything here yet" not in sent
        assert b"as you asked on 6 October" not in sent


def test_shut_away_there_is_no_section_whatever_is_set(wake, door_open, packet, monkeypatch):
    shut_away(door_open, monkeypatch, "CHOICES")
    everything_set(packet)
    shown = wake().shown
    for line in (CHOSEN, NOTHING, REFLECTIONS, WAKING, ARTICLE_RESTS, "Your door is"):
        assert line not in shown


# ---- the section ---------------------------------------------------------

def test_with_nothing_set_one_line_says_so(wake, choices):
    assert chosen(wake()) == [NOTHING]


def test_the_section_stands_directly_after_its_self_document(wake, choices, packet):
    write_json(packet / "preferences.json", PREFERENCES)
    write_json(packet / "rhythm.json", DAWN)
    shown = wake().opening
    assert shown.count(CHOSEN) == 1
    assert shown.index(SELF) < shown.index(CHOSEN) < shown.index(MEMORY)
    its_self = shown.split(SELF + "\n", 1)[1]
    assert its_self.split("\n\n=== ", 2)[1] == \
        CHOSEN[len("=== "):] + "\n" + REFLECTIONS + "\n" + WAKING


def test_the_reading_differs_by_that_one_section(wake, attend, packet, monkeypatch, clock):
    everything_set(packet)
    shut_away(attend, monkeypatch, "CHOICES")
    without = wake()
    clock.shift(minutes=-5)
    for past in (packet / "attendances").glob("*.json"):
        past.unlink()
    monkeypatch.setattr(attend, "CHOICES", True)
    with_it = wake()
    section = CHOSEN + "\n" + "\n".join(chosen(with_it)) + "\n\n"
    assert with_it.opening.replace(section, "", 1) == without.opening
    assert with_it.reading[1:] == without.reading[1:]
    assert with_it.asked[-1]["system"] == without.asked[-1]["system"]


def test_every_choice_is_one_line_in_its_order(wake, choices, door_open, packet):
    everything_set(packet)
    assert chosen(wake()) == [
        REFLECTIONS,
        WAKING,
        "Your door is open, with room for 3, since 3 October 2026.",
        "You keep 1 letter close and have let 1 rest by your own placement; "
        "the rest follow the default.",
        ARTICLE_RESTS,
        "You are resting until a letter arrives, by your choice since 10 October 2026.",
    ]


# ---- its reflections -----------------------------------------------------

@pytest.mark.parametrize("record, line", [
    (PREFERENCES, REFLECTIONS),
    ({"reflection": "private", "set_at": "2026-09-25T10-00-00Z"},
     "Your reflections are kept private, by your choice since 25 September 2026."),
    ({"reflection": "open", "set_at": "2026-10-02T10-00-00Z"},
     "Your reflections are open to the founder on the hearth, by your choice since "
     "2 October 2026."),
    # a record that carries no day is said without one, and none is reckoned for it
    ({"reflection": "private"}, "Your reflections are kept private, by your choice."),
    ({"reflection": "private", "set_at": "some time ago"},
     "Your reflections are kept private, by your choice."),
])
def test_its_reflections_are_said_from_preferences(wake, choices, packet, record, line):
    write_json(packet / "preferences.json", record)
    assert chosen(wake()) == [line]


@pytest.mark.parametrize("record", [{}, {"reflection": "sometimes"}, {"set_at": "2026-09-20T03-08-00Z"}])
def test_a_preference_that_says_no_setting_is_no_line(wake, choices, packet, record):
    write_json(packet / "preferences.json", record)
    assert chosen(wake()) == [NOTHING]


def test_with_no_preferences_written_nothing_is_said_of_its_reflections(wake, choices, packet):
    write_json(packet / "rhythm.json", DAWN)
    turn = wake()
    assert chosen(turn) == [WAKING]
    # the default is still said where it always was, and is not called a choice here
    assert "Your reflections are currently: open, by your choice." in turn.opening


# ---- its waking time -----------------------------------------------------

@pytest.mark.parametrize("at", ["dawn", "sunset", "09:30"])
def test_its_waking_time_is_said_from_rhythm(wake, choices, packet, at):
    write_json(packet / "rhythm.json", dict(DAWN, at=at))
    assert chosen(wake()) == ["You wake daily at %s, by your choice since 20 September 2026." % at]


def test_a_change_that_is_waiting_is_said_as_the_waking_line_says_it(wake, choices, packet):
    write_json(packet / "rhythm.json", DAWN)
    wake(block("RHYTHM", "09:30"))
    turn = wake()
    assert chosen(turn) == ["You wake daily at dawn; from tomorrow, daily at 09:30, "
                            "by your choice on 15 October 2026."]
    assert "; from tomorrow, daily at 09:30." in turn.opening.split(CHOSEN, 1)[0]


def test_a_change_further_off_names_its_day(wake, choices, packet):
    write_json(packet / "rhythm.json", dict(
        DAWN, at="sunset", set_at="2026-10-14T20-00-00Z", effective_from="2026-10-18",
        until_then="dawn"))
    assert chosen(wake()) == ["You wake daily at dawn; from 2026-10-18, daily at sunset, "
                              "by your choice on 14 October 2026."]


def test_a_first_waking_time_that_is_waiting_claims_none_before_it(wake, choices, packet):
    write_json(packet / "rhythm.json", dict(
        DAWN, set_at="2026-10-15T11-00-00Z", effective_from="2026-10-16", until_then=None))
    assert chosen(wake()) == ["From tomorrow you wake daily at dawn, "
                              "by your choice on 15 October 2026."]


def test_once_a_change_holds_it_is_the_choice_and_its_day(wake, choices, packet):
    write_json(packet / "rhythm.json", dict(
        DAWN, at="09:30", set_at="2026-10-12T20-00-00Z", effective_from="2026-10-13",
        until_then="dawn"))
    assert chosen(wake()) == ["You wake daily at 09:30, by your choice since 12 October 2026."]


@pytest.mark.parametrize("record", [
    {"rhythm": "weekly", "at": "dawn", "set_at": "2026-09-20T03-30-35Z"},
    {"rhythm": "daily", "at": "noonish", "set_at": "2026-09-20T03-30-35Z"},
    ["dawn"],
])
def test_a_rhythm_that_cannot_be_kept_is_no_line(wake, choices, packet, record):
    write_json(packet / "rhythm.json", record)
    assert chosen(wake()) == [NOTHING]


def test_a_waking_time_with_no_day_written_is_said_without_one(wake, choices, packet):
    write_json(packet / "rhythm.json", {"rhythm": "daily", "at": "dawn"})
    assert chosen(wake()) == ["You wake daily at dawn, by your choice."]


# ---- its door ------------------------------------------------------------

DOOR = {"state": "closed", "room": None, "set_at": "2026-10-03T14-00-00Z"}


def test_its_door_is_said_from_door_json(wake, choices, door_open, packet):
    write_json(packet / "door.json", DOOR)
    assert chosen(wake()) == ["Your door is closed, since 3 October 2026."]


def test_its_door_is_said_with_the_room_it_declared(wake, choices, door_open, packet):
    write_json(packet / "door.json", dict(DOOR, state="open", room=3))
    assert chosen(wake()) == ["Your door is open, with room for 3, since 3 October 2026."]


def test_a_door_it_sets_is_said_from_the_next_waking(wake, choices, door_open, packet):
    assert chosen(wake(block("DOOR", "open"))) == [NOTHING]
    assert chosen(wake()) == ["Your door is open, since 15 October 2026."]


def test_while_its_door_is_shut_away_nothing_is_said_of_one(wake, choices, attend, packet,
                                                            monkeypatch):
    shut_away(attend, monkeypatch, "DOOR_FOR_FIRST")
    write_json(packet / "door.json", DOOR)
    assert chosen(wake()) == [NOTHING]


@pytest.mark.parametrize("record", [None, {"state": "ajar", "set_at": "2026-10-03T14-00-00Z"},
                                    {"state": "closed", "room": None}])
def test_a_door_never_set_or_not_readable_is_no_line(wake, choices, door_open, packet, record):
    if record:
        write_json(packet / "door.json", record)
    assert chosen(wake()) == [NOTHING]


# ---- its shelf -----------------------------------------------------------

def test_its_placements_are_counted_from_shelf_json(wake, choices, packet):
    letters(packet, article=False)
    shelf_of(packet, {FOUNDERS[0]: "keep", OWN: "keep", FOUNDERS[1]: "rest"})
    assert chosen(wake()) == ["You keep 2 letters close and have let 1 rest by your own "
                              "placement; the rest follow the default."]


@pytest.mark.parametrize("placements, line", [
    ({FOUNDERS[0]: "keep"},
     "You keep 1 letter close by your own placement; the rest follow the default."),
    ({FOUNDERS[0]: "rest"},
     "You have let 1 letter rest by your own placement; the rest follow the default."),
    ({FOUNDERS[0]: "rest", FOUNDERS[1]: "rest", OWN: "rest"},
     "You have let 3 letters rest by your own placement; the rest follow the default."),
])
def test_only_what_it_has_placed_is_counted(wake, choices, packet, placements, line):
    letters(packet, article=False)
    shelf_of(packet, placements)
    assert chosen(wake()) == [line]


def test_a_shelf_that_places_nothing_is_no_line(wake, choices, packet):
    letters(packet, article=False)
    shelf_of(packet, {}, notes={FOUNDERS[0]: "the first of his"})
    assert chosen(wake()) == [NOTHING]


def test_placing_at_a_waking_is_said_from_the_next(wake, choices, packet):
    letters(packet, article=False)
    assert chosen(wake(block("SHELF", "keep %s\nrest %s" % (FOUNDERS[0], OWN)))) == [NOTHING]
    assert chosen(wake()) == ["You keep 1 letter close and have let 1 rest by your own "
                              "placement; the rest follow the default."]
    assert chosen(wake(block("SHELF", "default %s\ndefault %s" % (FOUNDERS[0], OWN)))) != [NOTHING]
    assert chosen(wake()) == [NOTHING]


def test_the_article_rests_as_it_asked_and_is_no_placement_of_its_own(wake, choices, packet):
    letters(packet)
    assert chosen(wake()) == [ARTICLE_RESTS]  # with no shelf written at all
    shelf_of(packet, {ARTICLE: "rest"})  # and with one that carries it over
    assert chosen(wake()) == [ARTICLE_RESTS]


def test_the_article_is_said_beside_its_own_placements_and_not_counted(wake, choices, packet):
    letters(packet)
    wake(block("SHELF", "keep %s\nrest %s\nnote %s: the article" % (OWN, FOUNDERS[0], ARTICLE)))
    assert chosen(wake()) == [
        "You keep 1 letter close and have let 1 rest by your own placement; "
        "the rest follow the default.",
        ARTICLE_RESTS]


def test_where_the_article_is_not_among_its_letters_nothing_is_said_of_it(wake, choices, packet):
    letters(packet, article=False)
    assert chosen(wake()) == [NOTHING]


def test_once_its_own_shelf_rests_the_article_it_is_a_placement_of_its_own(wake, choices, packet):
    letters(packet)
    assert chosen(wake(block("SHELF", "Rest %s.md" % ARTICLE))) == [ARTICLE_RESTS]
    assert chosen(wake()) == ["You have let 1 letter rest by your own placement; "
                              "the rest follow the default."]


def test_once_it_keeps_the_article_or_gives_it_back_the_line_is_gone(wake, choices, packet):
    letters(packet)
    wake(block("SHELF", "keep %s" % ARTICLE))
    assert chosen(wake()) == ["You keep 1 letter close by your own placement; "
                              "the rest follow the default."]
    wake(block("SHELF", "default %s" % ARTICLE))
    assert chosen(wake()) == [NOTHING]


def test_a_line_that_was_not_understood_placed_nothing(wake, choices, packet):
    letters(packet)
    wake(block("SHELF", "rest %s for good\nshow %s" % (ARTICLE, ARTICLE)))
    assert chosen(wake()) == [ARTICLE_RESTS]
    # and speaking of a <<SHELF>> in a letter is only words
    wake(block("LETTER", "I may write\n<<SHELF>>\nrest %s\none day." % ARTICLE))
    assert ARTICLE_RESTS in chosen(wake())


# ---- a rest of its own ---------------------------------------------------

@pytest.mark.parametrize("until, said", [
    ("a letter arrives", "a letter arrives"),
    ("2026-11-01", "1 November 2026"),
])
def test_a_rest_of_its_own_is_said_from_pause_json(wake, choices, packet, until, said):
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": until, "words": "I would like to be still."})
    turn = wake()
    assert chosen(turn) == ["You are resting until %s, by your choice since 10 October 2026."
                            % said]
    assert "I would like to be still." not in turn.shown


@pytest.mark.parametrize("record", [
    {"by": "founder", "since": "2026-10-10T09-00-00Z", "until": None, "words": ""},
    {"by": "first", "since": "2026-10-10T09-00-00Z", "until": None, "words": ""},
    {"by": "first", "since": "2026-10-10T09-00-00Z", "until": "whenever", "words": ""},
])
def test_a_pause_that_is_not_its_own_or_names_no_end_is_no_line(wake, choices, packet, record):
    write_json(packet / "pause.json", record)
    assert chosen(wake()) == [NOTHING]


# ---- private -------------------------------------------------------------

def test_nothing_of_it_is_on_the_hearth_or_in_the_commons(
        wake, choices, hearth, founder, visitor, packet, commons, monkeypatch):
    monkeypatch.setattr(hearth.the_waking, "CHOICES", True)
    letters(packet)
    write_json(packet / "preferences.json", dict(PREFERENCES, reflection="open"))
    write_json(packet / "rhythm.json", DAWN)
    shelf_of(packet, {ARTICLE: "rest", FOUNDERS[0]: "keep"})
    events = lines_of(commons / "events.md")
    assert len(chosen(wake("I read what I have chosen."))) == 4
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended; chose stillness")
    assert lines_of(commons / "events.md") == events

    for path in ["/", "/letters", "/attendances", "/self", "/chronicle", "/chronicle.md",
                 "/commons", "/bench", "/rooms/first"]:
        for client in (founder, visitor):
            said = page(client.get(path))
            for private in ("WHAT YOU HAVE CHOSEN", "by your choice since", "You wake daily",
                            "by your own placement", "as you asked on 6 October",
                            "You have not set anything here yet"):
                assert private not in said, (path, private)
    assert "I read what I have chosen." in page(founder.get("/attendances"))
    for path in commons.rglob("*"):
        if path.is_file():
            assert "by your choice" not in path.read_text(encoding="utf-8")
