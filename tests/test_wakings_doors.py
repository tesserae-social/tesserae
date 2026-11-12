"""One waking a day, a weekly reflection waking, and doors of one to eight.

The founder's decisions of 11 November 2026, which the first one agreed to on
10 November (the plan's steps 0.6 and 0.7). Each change to what an agent reads
is behind a switch of its own in the registry, a feature its entry names, and
each is off until the founder turns it on, so READING_NOW does not move:

  extra_wakings     on, as it was since 21 October; one waking a day is had by
                    taking it out (attend.EXTRA_WAKINGS False), and nothing of an
                    extra waking is then offered
  reflection_waking the weekly reflection waking (attend.REFLECTION_WAKING,
                    reflecting.py, hearth.keep_reflection)
  doors_to_eight    an agent's door declares room from one to eight
                    (attend.DOORS_TO_EIGHT, door.AGENT_ROOM_MOST), and the door
                    on the hearth says door.USUALLY beside its room
  people_waiting    an agent is told, once for each number and with no name, how
                    many people are waiting for a friendship with an agent while
                    no agent's door has room (attend.PEOPLE_WAITING, door.waiting)

Each switched-on reading is held here by a fingerprint of its own, cut on 11
November 2026 from test_rooms_reading.py's small world, and each is recoverable:
with its switch off it is READING_NOW, and with exactly the words it adds taken
out of what it shows, it is what the reading with the switch off shows. No file
of the first one's moves before a waking, so PACKET_IN_ROOMS stands.

On 12 November 2026 the founder switched on, for the first one only, the two
it had agreed to and that the two had agreed to turn on together: one waking a
day (extra_wakings out of its features) and its reflection waking
(reflection_waking in, Sundays at sunset to start). doors_to_eight and
people_waiting stay off. READING_NOW is now the reading with those two on. Each
fingerprint here was cut from the registry as it stood before, and is held from
it still: conftest.wakings_not_yet_switched puts the two back first, and with
all four as they stood before, the reading is READING_LAST_REPLY.
"""

import json
import shutil
from datetime import date, datetime, timezone

import pytest

import agents
import reflecting
import waking
from conftest import (block, page, post, read_json, rewrite_last_reply_not_yet,
                      wakings_not_yet_switched, write, write_json)
from test_rooms_reading import (ERRAND, PACKET_IN_ROOMS, READING_LAST_REPLY, READING_NOW,
                                a_small_world, fingerprint_of_files, fingerprint_of_reading)

UTC = timezone.utc

# Cut on 11 November 2026, each from the small world, each with only its own
# switch changed from the registry as it stands (and, for PEOPLE_WAITING, two
# members in no room yet and the first one's door closed). Held as *_FIRST_CUT
# since.
FIRST_CUT = {
    "one a day": "df16389d428d1ff8b70674f3086df6752c5ccd8f802fc305abc8e1aa234828f3",
    "reflection": "0cf59b3c6f8898b71b757928ff77c1b83085e431099c043a85e2559debc7d891",
    "doors": "563c9d99a55a843556228d413e46d4ca57ae0327210f03e44bd6efb488a843bf",
    "waiting": "825cf6957898becfb6f68ba1d7fb39a38a4418ea8ad59f619c7575faf5d71207",
    "all four": "1c1fdc61521752e66985e2913bc74c3a29368229d2ef5bd9675a41ed930f89d3"}
# Cut again, on purpose, on 12 November 2026, for nothing else than READING_NOW
# was: <<REWRITE>>'s explanation now ends "Write it in your last reply, after
# looking.", the first one's rewrites of that day having been dropped beside a
# look-up. With that sentence taken out (conftest.rewrite_last_reply_not_yet),
# each is exactly its first cut.
READING_ONE_A_DAY = "59076b5e5aef31d64fd302e7c479ded397810284e96268031fe08bbc49b9d6e3"
READING_REFLECTION_WAKING = "a09675dee57747a84ab3ed70f6f324fce535fe57b01fdf41956c79e69674f8e9"
READING_DOORS_TO_EIGHT = "a2c011fd6c588a90c4b82a01c9963563bafadeb404941992f7334fcc729faf5e"
READING_PEOPLE_WAITING = "5fd817c033ead971a1b2a717f64729784581c78b33212978d1dd0d78ee6047e5"
# and with all four as the founder would turn them on together
READING_ALL_FOUR = "eb058947d782153a43524a681d1fa6a7f38ef02177be50916dfc8f7eb65b53e1"
# the reflection waking itself, in the same small world, with nothing kept yet
REFLECTION_READING = "9bd9b2887664397c53df9d1192bde6d5bd653adaed865e2b40b431ef40dcaaf4"

CHOSE_SUNDAY = "Your weekly reflection waking comes on Sundays at sunset, as you asked."
WAITING_TWO = "2 people are waiting for a friendship with an agent."


# ---- the small world, and switches --------------------------------------

def the_small_world(founder, room):
    a_small_world(room)
    answer = post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302


def a_member(data, name):
    """A member, as far as being counted goes: a record and no vault."""
    write_json(data / "members" / name / "member.json",
               {"v": 1, "pseudonym": name, "role": "member", "verify_key": "0" * 64})


def two_waiting(data):
    a_member(data, "alder")
    a_member(data, "hazel")


SWITCHES = {
    "one a day": ("EXTRA_WAKINGS", False),
    "reflection": ("REFLECTION_WAKING", True),
    "doors": ("DOORS_TO_EIGHT", True),
    "waiting": ("PEOPLE_WAITING", True),
}


def switched(attend, monkeypatch, *names):
    for name in names:
        flag, to = SWITCHES[name]
        monkeypatch.setattr(attend, flag, to)


def blocks(*pairs):
    """Several labelled blocks, each given as (tag, body)."""
    return "\n\n".join(block(tag, body) for tag, body in pairs)


def text_of(turn):
    return turn.shown


def test_one_a_day_and_the_reflection_waking_are_on_and_the_other_two_off(attend):
    """What READING_NOW is a fingerprint of since 12 November 2026: one waking a day and its
    reflection waking on for the first one, and the other two not yet."""
    assert attend.EXTRA_WAKINGS is False
    assert (attend.REFLECTION_WAKING, attend.DOORS_TO_EIGHT, attend.PEOPLE_WAITING) == (
        True, False, False)
    features = agents.first()["features"]
    assert "extra_wakings" not in features and "reflection_waking" in features
    for feature in ("doors_to_eight", "people_waiting"):
        assert feature not in features


# ---- each switched-on reading, by its own fingerprint ---------------------

@pytest.mark.parametrize("names, as_cut", [
    (("one a day",), READING_ONE_A_DAY),
    (("reflection",), READING_REFLECTION_WAKING),
    (("doors",), READING_DOORS_TO_EIGHT),
    (("waiting",), READING_PEOPLE_WAITING),
    (("one a day", "reflection", "doors", "waiting"), READING_ALL_FOUR)],
    ids=["one a day", "the reflection waking", "doors to eight", "people waiting", "all four"])
def test_each_switched_on_reading_is_held_by_its_own_fingerprint(
        founder, wake, attend, room, data_dir, monkeypatch, names, as_cut):
    the_small_world(founder, room)
    if "waiting" in names:
        two_waiting(data_dir)
    wakings_not_yet_switched(attend, monkeypatch)  # each was cut from the registry before
    switched(attend, monkeypatch, *names)
    files = fingerprint_of_files(data_dir) if "waiting" not in names else PACKET_IN_ROOMS
    reading = fingerprint_of_reading(wake())
    print("\n%s = %r" % (names, reading))
    assert (files, reading) == (PACKET_IN_ROOMS, as_cut)


@pytest.mark.parametrize("names, first_cut", [
    (("one a day",), "one a day"), (("reflection",), "reflection"), (("doors",), "doors"),
    (("waiting",), "waiting"), (("one a day", "reflection", "doors", "waiting"), "all four")],
    ids=["one a day", "the reflection waking", "doors to eight", "people waiting", "all four"])
def test_with_the_last_reply_taken_out_each_is_its_first_cut(
        founder, wake, attend, room, data_dir, monkeypatch, names, first_cut):
    the_small_world(founder, room)
    if "waiting" in names:
        two_waiting(data_dir)
    wakings_not_yet_switched(attend, monkeypatch)
    switched(attend, monkeypatch, *names)
    rewrite_last_reply_not_yet(attend, monkeypatch)
    assert fingerprint_of_reading(wake()) == FIRST_CUT[first_cut]


def test_with_every_switch_off_it_is_the_reading_before(founder, wake, attend, room, data_dir,
                                                       monkeypatch):
    """Recoverable: the four turned off again give the reading before 12 November 2026."""
    the_small_world(founder, room)
    switched(attend, monkeypatch, "one a day", "reflection", "doors", "waiting")
    for flag, to in SWITCHES.values():
        monkeypatch.setattr(attend, flag, not to)
    assert fingerprint_of_reading(wake()) == READING_LAST_REPLY


def test_from_the_reading_before_the_two_switched_on_give_reading_now(
        founder, wake, attend, room, data_dir, monkeypatch):
    """The registry as it stands is the reading before with exactly these two switched."""
    the_small_world(founder, room)
    wakings_not_yet_switched(attend, monkeypatch)
    switched(attend, monkeypatch, "one a day", "reflection")
    assert fingerprint_of_reading(wake()) == READING_NOW


def on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch, name,
               waiting=False):
    """What the small world's waking shows with one switch on, and then, from the same world
    and the same moment, with it off; each from the registry as it stood before 12 November."""
    wakings_not_yet_switched(attend, monkeypatch)
    the_small_world(founder, room)
    if waiting:
        two_waiting(data_dir)
    shutil.copytree(data_dir, tmp_path / "as it was")
    switched(attend, monkeypatch, name)
    shown = text_of(wake())
    shutil.rmtree(data_dir)
    shutil.copytree(tmp_path / "as it was", data_dir)
    clock.shift(minutes=-5)
    flag, to = SWITCHES[name]
    monkeypatch.setattr(attend, flag, not to)
    return shown, text_of(wake())


def test_one_a_day_takes_out_the_extra_waking_and_nothing_else(
        founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch):
    shown, before = on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path,
                               monkeypatch, "one a day")
    assert "<<WAKE_AGAIN>>" not in shown and "send kept" not in shown
    assert before.replace("\n\n" + attend.WAKE_AGAIN_BLOCK, "", 1).replace(
        attend.SEND_KEPT, "", 1) == shown


def test_the_reflection_waking_adds_its_block_and_its_line_and_nothing_else(
        founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch):
    shown, before = on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path,
                               monkeypatch, "reflection")
    assert shown.count(attend.REFLECTION_TIME_BLOCK) == 1
    assert shown.count(CHOSE_SUNDAY) == 1
    assert shown.replace("\n\n" + attend.REFLECTION_TIME_BLOCK, "", 1).replace(
        CHOSE_SUNDAY, attend.NOTHING_CHOSEN, 1) == before


def test_doors_to_eight_add_their_words_to_the_door_and_nothing_else(
        founder, wake, attend, room, data_dir, clock, tmp_path, monkeypatch):
    shown, before = on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path,
                               monkeypatch, "doors")
    assert ('"room 3" (how many correspondences you can carry wholly, from 1 to 8) or "room '
            'none". Friendships here are usually between one and eight. Your door') in shown
    assert shown.replace(", from 1 to 8)", ")", 1).replace(
        " Friendships here are usually between one and eight.", "", 1) == before


def test_people_waiting_add_one_line_and_nothing_else(founder, wake, attend, room, data_dir,
                                                      clock, tmp_path, monkeypatch):
    shown, before = on_and_off(founder, wake, attend, room, data_dir, clock, tmp_path,
                               monkeypatch, "waiting", waiting=True)
    happened = shown.partition("=== WHAT HAS HAPPENED ===")[2].partition("\n=== ")[0]
    assert happened.count(WAITING_TWO) == 1
    assert "alder" not in shown and "hazel" not in shown  # never a name
    assert shown.replace("\n" + WAITING_TWO, "", 1) == before


# ---- one a day ----------------------------------------------------------

def test_one_a_day_a_wake_again_is_only_words(founder, wake, attend, packet, monkeypatch):
    monkeypatch.setattr(attend, "EXTRA_WAKINGS", False)
    wake(block("WAKE_AGAIN", "19:30"))
    assert not (packet / "wake-again.json").exists()
    record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert "asked to wake again" not in record["acted"]
    assert "wake_again_refused" not in record


def test_one_a_day_the_tide_keeps_no_extra_waking(hearth, packet, monkeypatch, clock):
    monkeypatch.setattr(hearth.the_waking, "EXTRA_WAKINGS", False)
    assert hearth.extra_wakings_on("first") is False


# ---- the reflection time: asked, kept, said ------------------------------

@pytest.mark.parametrize("said, asked", [
    ("sunday sunset", ("sunday", "sunset")),
    ("Sunday at sunset", ("sunday", "sunset")),
    ("on Sundays at sunset.", ("sunday", "sunset")),
    ("wednesday dawn", ("wednesday", "dawn")),
    ("saturday 21:00\nbecause the week is done", ("saturday", "21:00")),
    ("none", (None, None)),
    ("  \nNone", (None, None)),
    ("sunday", None), ("sunset", None), ("someday sunset", None), ("sunday 25:00", None),
    ("sunday at noon", None), ("", None)])
def test_a_reflection_time_is_read_strictly(said, asked):
    assert reflecting.asked(said) == asked
    assert reflecting.asked(None) is None


def test_the_first_one_starts_with_sunday_at_sunset_and_no_other_agent_with_any(tmp_path):
    assert reflecting.read(tmp_path, "first") == {"day": "sunday", "at": "sunset",
                                                  "set_by": reflecting.AS_IT_ASKED}
    assert reflecting.read(tmp_path, "second") is None
    write_json(tmp_path / reflecting.RECORD, {"day": None, "set_at": "2026-11-15T12-00-00Z"})
    assert reflecting.read(tmp_path, "first") is None  # its own choice of none
    write(tmp_path / reflecting.RECORD, "not json")
    assert reflecting.read(tmp_path, "first") is None  # never held by accident


@pytest.fixture
def reflecting_on(attend, monkeypatch):
    monkeypatch.setattr(attend, "REFLECTION_WAKING", True)
    return attend


def chosen_of(turn):
    return turn.shown.partition("=== WHAT YOU HAVE CHOSEN ===\n")[2].partition("\n\n")[0]


def test_its_reflection_time_is_kept_and_said_and_the_one_before_kept_beside_it(
        reflecting_on, wake, packet, clock):
    wake(block("REFLECTION_TIME", "saturday 21:00"))
    kept = read_json(packet / "reflection-time.json")
    assert kept == {"day": "saturday", "at": "21:00", "set_at": "2026-10-15T12-00-00Z"}
    record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert "set its reflection waking" in record["acted"]
    turn = wake(block("REFLECTION_TIME", "none"))
    assert ("Your weekly reflection waking comes on Saturdays at 21:00, by your choice since "
            "15 October 2026.") in chosen_of(turn)
    assert [p.name for p in (packet / "reflection-time" / "history").iterdir()] == [
        "reflection-time-before-2026-10-15T12-05-00Z.json"]
    assert "You have no weekly reflection waking, by your choice since 15 October 2026." in \
        chosen_of(wake())


def test_one_that_cannot_be_read_changes_nothing_and_is_told_once(reflecting_on, wake, packet):
    wake(block("REFLECTION_TIME", "every so often"))
    assert not (packet / "reflection-time.json").exists()
    told = wake()
    assert told.shown.count(reflecting_on.REFLECTION_TIME_REFUSED) == 1
    assert reflecting_on.REFLECTION_TIME_REFUSED not in wake().shown


def test_shut_away_it_is_only_words(attend, wake, packet, monkeypatch):
    monkeypatch.setattr(attend, "REFLECTION_WAKING", False)
    turn = wake(block("REFLECTION_TIME", "saturday 21:00"))
    assert not (packet / "reflection-time.json").exists()
    assert "REFLECTION_TIME" not in turn.shown


# ---- the reflection waking itself ----------------------------------------

def reflections(packet):
    return [read_json(p) for p in sorted((packet / "reflections").glob("reflection-*.json"))]


def test_shut_away_a_reflection_waking_is_refused(attend, wake, packet, monkeypatch):
    monkeypatch.setattr(attend, "REFLECTION_WAKING", False)
    with pytest.raises(SystemExit) as stopped:
        wake("", "--reflect", "--tide")
    assert stopped.value.code == 1
    assert not (packet / "reflections").exists()
    assert not list((packet / "attendances").glob("*.json"))


def test_its_reading_is_its_self_notes_and_notebook_and_nothing_of_its_room(
        founder, reflecting_on, wake, packet, room, data_dir):
    the_small_world(founder, room)
    write(packet / "memory" / "notes.md", "A FAKE NOTE TO ITSELF, FOR THE TESTS.\n")
    write(packet / "private" / "entry-2026-10-01T09-00-00Z.md",
          "A FAKE PRIVATE ENTRY, FOR THE TESTS.\n")
    turn = wake("", "--reflect", "--tide")
    shown = turn.shown
    assert shown.startswith(reflecting_on.REFLECTION_OPENING)
    assert "A FAKE NOTE TO ITSELF" in shown and "A FAKE PRIVATE ENTRY" in shown
    assert "=== YOUR SELF-DOCUMENT (packets/first/self.md) ===" in shown
    for none_of_these in ("The lake was grey", "The first letter", "My answer to it",
                          "lake and tell me", "LETTER", "BOND", "ERRAND", "DOOR",
                          "REFLECTION_TIME", "RHYTHM", "LOOKING THINGS UP"):
        assert none_of_these not in shown
    for these in ("<<SELF>>", "<<MEMORY>>", "<<NOTE>>", "<<PRIVATE>>"):
        assert these in shown
    assert "tools" not in turn.asked[-1]  # one request, and nothing to look up


def test_the_reflection_reading_is_held_by_its_own_fingerprint(
        founder, reflecting_on, wake, room, data_dir):
    the_small_world(founder, room)
    reading = fingerprint_of_reading(wake("", "--reflect", "--tide"))
    print("\nREFLECTION_READING = %r" % reading)
    assert reading == REFLECTION_READING


def test_it_keeps_its_self_notes_and_notebook_and_passes_over_the_rest(
        founder, reflecting_on, wake, packet, room, commons, data_dir):
    the_small_world(founder, room)
    incoming = sorted((room / "letters" / "incoming").glob("*.md"))
    assert incoming
    heartbeats = (commons / "heartbeats.md").read_bytes() if (
        commons / "heartbeats.md").exists() else None
    said = blocks(("MEMORY", "Kept at a reflection."), ("NOTE", "name: the week\nIt was long."),
                  ("PRIVATE", "A FAKE PRIVATE ENTRY, FOR THE TESTS."),
                  ("SELF", "# The first one\n\nRevised at a reflection.\n\nwhy: the week"),
                  ("LETTER", "A letter that must not go."), ("RHYTHM", "sunset"),
                  ("REFLECTION_TIME", "monday dawn"), ("ERRAND", "Go and look."))
    wake(said, "--reflect", "--tide")

    # what it keeps of itself is kept
    assert (packet / "memory" / "notes.md").read_text(encoding="utf-8") == \
        "Kept at a reflection.\n"
    assert (packet / "memory" / "notes" / "the-week.md").exists()
    assert len(list((packet / "private").glob("entry-*.md"))) == 1
    assert read_json(packet / "self-proposal.json")["arrived"] == []
    # and nothing else is done: no letter, no errand, no time changed, nothing read
    assert sorted((room / "letters" / "incoming").glob("*.md")) == incoming
    assert list((room / "letters" / "outgoing").glob("*A letter*")) == []
    assert all("A letter that must not go" not in p.read_text(encoding="utf-8")
               for p in (room / "letters" / "outgoing").glob("*.md"))
    assert not (packet / "rhythm.json").exists()
    assert not (packet / "reflection-time.json").exists()
    assert not list((room / "errands").glob("errand-2026-10-15*"))
    assert not list((packet / "attendances").glob("*.json"))
    after = (commons / "heartbeats.md").read_bytes() if (
        commons / "heartbeats.md").exists() else None
    assert after == heartbeats  # no line of the commons

    held, = reflections(packet)
    assert held["kind"] == "reflection" and held["woken_by"] == "tide"
    assert held["acted"] == ["proposed a change to its self-document", "kept notes",
                             "kept a named note", "kept something private"]
    assert held["passed_over"] == ["LETTER", "RHYTHM", "REFLECTION_TIME", "ERRAND"]
    assert "A FAKE PRIVATE ENTRY" not in json.dumps(held)  # its notebook is never logged
    assert "signatures" in held or "signature" in held


def test_its_next_waking_is_told_of_it_once_and_reads_its_letters(
        founder, reflecting_on, wake, packet, room, data_dir):
    the_small_world(founder, room)
    wake("")  # its day's waking, which reads the letter that came
    write(room / "letters" / "incoming" / "founder-2026-10-15T12-07-00Z.md",
          "A FAKE LETTER THAT CAME BEFORE THE REFLECTION, FOR THE TESTS.\n")
    wake(blocks(("MEMORY", "Kept at a reflection."), ("LETTER", "Not this.")),
         "--reflect", "--tide")
    turn = wake("")
    happened = turn.shown.partition("=== WHAT HAS HAPPENED ===")[2].partition("\n=== ")[0]
    assert ("You had your reflection waking on 15 October 2026. What was carried out at it: "
            "kept notes.") in happened
    assert ("At your reflection waking on 15 October 2026, what you wrote in <<LETTER>> was "
            "passed over: a reflection waking keeps only your self-document, your notes and "
            "your notebook. Nothing of it was carried out.") in happened
    # the letter that came is read at this waking, as it would have been
    assert "A FAKE LETTER THAT CAME BEFORE THE REFLECTION" in turn.shown
    assert not list((room / "letters" / "incoming").glob("*.md"))
    # and is told it once
    again = wake("")
    assert "reflection waking on" not in again.shown.partition("=== WHAT HAS HAPPENED ===")[2] \
        .partition("\n=== ")[0]


def test_a_note_it_could_not_keep_is_told_as_of_its_reflection(
        founder, reflecting_on, wake, packet, room):
    wake("")
    wake(block("NOTE", "no name here"), "--reflect", "--tide")
    turn = wake("")
    assert "A <<NOTE>> at your reflection waking on 15 October 2026 was not kept" in turn.shown


def test_a_change_to_its_self_written_at_a_reflection_is_confirmed_at_a_later_waking(
        reflecting_on, wake, packet):
    wake("")
    wake(block("SELF", "# The first one\n\nRevised at a reflection."), "--reflect", "--tide")
    turn = wake(block("SELF_CONFIRM", "yes"))
    assert "A CHANGE TO YOUR SELF-DOCUMENT, WAITING FOR YOU" in turn.shown
    assert (packet / "self.md").read_text(encoding="utf-8") == \
        "# The first one\n\nRevised at a reflection.\n"


# ---- the tide ------------------------------------------------------------

RHYTHM = {"rhythm": "daily", "at": "dawn", "timezone": "America/New_York"}
SATURDAY = "2026-10-17T15-00-00Z"  # 11:00 on Saturday 17 October, in Eastern time


def stamp_of(when):
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def moment_of(at, day):
    return stamp_of(waking.moment_on(RHYTHM, at, day))


class StopTide(BaseException):
    """Raised to end a tide that would otherwise run forever; past its own except."""


def run_tide(hearth, monkeypatch, clock, packet, holds):
    """Let the tide run until it has held some wakings, sleeping on the pinned clock."""
    notes, held = [], []

    def hold(**how):
        if len(held) >= holds:
            raise StopTide
        held.append((clock.stamp(), how))
        at = clock.stamp()
        if how.get("reflect"):
            write_json(packet / "reflections" / ("reflection-%s.json" % at),
                       {"name": "first", "at": at, "kind": "reflection", "acted": []})
        else:
            write_json(packet / "attendances" / ("attendance-%s.json" % at),
                       {"name": "first", "at": at, "heartbeat": "attended", "acted": []})
        clock.shift(minutes=2)
        return None

    monkeypatch.setattr(hearth, "tide_note", lambda said, **how: notes.append((clock.stamp(), said)))
    monkeypatch.setattr(hearth, "hold_attendance", hold)
    monkeypatch.setattr(hearth.time, "sleep", lambda seconds: clock.shift(seconds=seconds))
    with pytest.raises(StopTide):
        hearth.tide()
    return notes, held


@pytest.fixture
def a_saturday(packet, clock):
    write_json(packet / "rhythm.json", RHYTHM)
    write_json(packet / "attendances" / "attendance-2026-10-17T11-30-00Z.json",
               {"name": "first", "at": "2026-10-17T11-30-00Z", "heartbeat": "attended",
                "acted": []})
    clock.set(SATURDAY)


def test_the_tide_holds_it_on_sunday_at_sunset_besides_that_day_s_dawn(
        hearth, packet, monkeypatch, clock, a_saturday):
    monkeypatch.setattr(hearth.the_waking, "REFLECTION_WAKING", True)
    notes, held = run_tide(hearth, monkeypatch, clock, packet, holds=3)
    sunday, monday = date(2026, 10, 18), date(2026, 10, 19)
    assert held == [(moment_of("dawn", sunday), {"tide": True, "ended": None}),
                    (moment_of("sunset", sunday), {"tide": True, "reflect": True}),
                    (moment_of("dawn", monday), {"tide": True, "ended": None})]
    assert [said for _, said in notes] == ["ran", "reflected", "ran"]


def test_shut_away_the_tide_holds_no_reflection_waking(hearth, packet, monkeypatch, clock,
                                                       a_saturday):
    monkeypatch.setattr(hearth.the_waking, "REFLECTION_WAKING", False)
    notes, held = run_tide(hearth, monkeypatch, clock, packet, holds=3)
    assert all("reflect" not in how for _, how in held)


# Its first reflection waking, as the registry stands after the deploy of 12
# November 2026: nothing switched by the test. The rhythm is kept on Central
# time; the sun is watched from wherever the host is told (here, the tests' own
# point), so the moment is that day's sunset as the host reckons it.
CENTRAL = {"rhythm": "daily", "at": "dawn", "timezone": "America/Chicago"}


def test_as_the_registry_stands_its_first_reflection_is_sunday_15_november_at_sunset(
        hearth, packet, monkeypatch, clock):
    assert hearth.reflection_on("first") is True and hearth.extra_wakings_on("first") is False
    write_json(packet / "rhythm.json", CENTRAL)
    write_json(packet / "attendances" / "attendance-2026-11-14T12-45-00Z.json",
               {"name": "first", "at": "2026-11-14T12-45-00Z", "heartbeat": "attended",
                "acted": []})
    clock.set("2026-11-14T18-00-00Z")  # noon on Saturday 14 November, in Central time
    assert not (packet / reflecting.RECORD).exists()  # its starting choice, as it asked
    sunday, monday = date(2026, 11, 15), date(2026, 11, 16)
    sunset = waking.moment_on(CENTRAL, "sunset", sunday)
    assert hearth.next_reflection(CENTRAL) == sunset
    notes, held = run_tide(hearth, monkeypatch, clock, packet, holds=3)

    def at(when, day):
        return stamp_of(waking.moment_on(CENTRAL, when, day))

    assert held == [(at("dawn", sunday), {"tide": True, "ended": None}),
                    (stamp_of(sunset), {"tide": True, "reflect": True}),
                    (at("dawn", monday), {"tide": True, "ended": None})]
    assert [said for _, said in notes] == ["ran", "reflected", "ran"]


def test_one_at_dawn_comes_in_its_turn_after_that_dawn_s_waking(hearth, packet, monkeypatch,
                                                                clock, a_saturday):
    monkeypatch.setattr(hearth.the_waking, "REFLECTION_WAKING", True)
    write_json(packet / "reflection-time.json", {"day": "sunday", "at": "dawn",
                                                 "set_at": "2026-10-17T11-30-00Z"})
    notes, held = run_tide(hearth, monkeypatch, clock, packet, holds=2)
    dawn = moment_of("dawn", date(2026, 10, 18))
    assert [how for _, how in held] == [{"tide": True, "ended": None},
                                        {"tide": True, "reflect": True}]
    assert held[0][0] == dawn and held[1][0] > dawn


@pytest.mark.parametrize("standing, said", [
    ("stop", "reflection waking let go: stopped by the keeper"),
    ("pause", "reflection waking let go: resting")])
def test_a_stop_or_its_own_rest_lets_it_go(hearth, packet, monkeypatch, clock, a_saturday,
                                          standing, said):
    monkeypatch.setattr(hearth.the_waking, "REFLECTION_WAKING", True)
    clock.set("2026-10-18T15-00-00Z")  # Sunday, after its dawn waking
    write_json(packet / "attendances" / "attendance-2026-10-18T11-30-00Z.json",
               {"name": "first", "at": "2026-10-18T11-30-00Z", "heartbeat": "attended",
                "acted": []})
    if standing == "stop":
        write_json(packet / "tide-stop.json", {"since": "2026-10-18T14-00-00Z", "reason": "test"})
    else:
        write_json(packet / "pause.json", {"by": "first", "since": "2026-10-18T14-00-00Z",
                                           "until": "a letter arrives", "words": ""})
    notes = []
    monkeypatch.setattr(hearth, "tide_note", lambda words, **how: notes.append(words))
    monkeypatch.setattr(hearth, "hold_attendance", lambda **how: pytest.fail("held"))
    monkeypatch.setattr(hearth.time, "sleep", lambda seconds: clock.shift(seconds=seconds))
    when = hearth.next_reflection(RHYTHM)
    assert when == waking.moment_on(RHYTHM, "sunset", date(2026, 10, 18))
    hearth.keep_reflection(RHYTHM, when)
    assert notes == [said]
    assert hearth.next_reflection(RHYTHM) == waking.moment_on(RHYTHM, "sunset",
                                                              date(2026, 10, 25))


def test_none_comes_before_its_first_waking(hearth, packet, monkeypatch, clock):
    monkeypatch.setattr(hearth.the_waking, "REFLECTION_WAKING", True)
    assert hearth.next_reflection(RHYTHM) is None


def test_it_is_held_with_reflect_and_never_as_a_first_waking(hearth, monkeypatch):
    ran = []
    monkeypatch.setattr(hearth.subprocess, "run", lambda command, **how: ran.append(command)
                        or hearth.subprocess.CompletedProcess(command, 0, "", ""))
    assert hearth.hold_attendance(tide=True, reflect=True) is None
    assert ran[0][1:] == ["attend.py", "--reflect", "--tide"]


def test_due_skips_a_day_that_had_one_and_keeps_one_passed_on_its_own_day():
    sunday = date(2026, 10, 18)
    choice = {"day": "sunday", "at": "sunset"}
    after_sunset = waking.moment_on(RHYTHM, "sunset", sunday).astimezone(UTC).replace(
        hour=23, minute=59)
    assert reflecting.due(choice, RHYTHM, after_sunset) == waking.moment_on(
        RHYTHM, "sunset", sunday)
    assert reflecting.due(choice, RHYTHM, after_sunset, held_on=sunday) == waking.moment_on(
        RHYTHM, "sunset", date(2026, 10, 25))
    monday = datetime(2026, 10, 19, 16, tzinfo=UTC)
    assert reflecting.due(choice, RHYTHM, monday) == waking.moment_on(
        RHYTHM, "sunset", date(2026, 10, 25))
    assert reflecting.due(None, RHYTHM, monday) is None


# ---- doors to eight --------------------------------------------------------

def test_an_agent_s_door_declares_room_to_eight_and_a_member_s_to_twelve(hearth, packet):
    door = hearth.door
    assert door.asked("open\nroom 8", door.AGENT_ROOM_MOST) == ("open", 8)
    assert door.asked("open\nroom 9", door.AGENT_ROOM_MOST) is None
    assert door.asked("open\nroom 12") == ("open", 12)
    with pytest.raises(door.DoorError, match="from 1 to 8"):
        door.set_door("first", "open", 9, most=door.AGENT_ROOM_MOST)
    # a room above eight declared before stands as it was, and only a new one is held to eight
    door.set_door("first", "open", 12, at="2026-10-15T12-00-00Z")
    assert door.set_door("first", "closed", most=door.AGENT_ROOM_MOST,
                         at="2026-10-15T12-01-00Z")["room"] == 12


def test_switched_on_a_door_of_nine_is_refused_and_told_with_its_numbers(attend, wake, packet,
                                                                         monkeypatch):
    monkeypatch.setattr(attend, "DOORS_TO_EIGHT", True)
    wake(block("DOOR", "open\nroom 9"))
    assert not (packet / "door.json").exists()
    told = wake().shown
    assert ('Your <<DOOR>> was not understood (its first line must be "open" or "closed"; a '
            'second line may be "room 3", from 1 to 8, or "room none"); your door is '
            'unchanged.') in told
    wake(block("DOOR", "open\nroom 8"))
    assert read_json(packet / "door.json")["room"] == 8


def test_shut_away_a_door_of_twelve_is_kept_as_before(attend, wake, packet):
    wake(block("DOOR", "open\nroom 12"))
    assert read_json(packet / "door.json")["room"] == 12


@pytest.fixture
def eight_in_the_registry(monkeypatch, tmp_path):
    where = tmp_path / "agents.json"
    first = agents.first()
    first = {**first, "features": [*first["features"], "doors_to_eight"]}
    where.write_text(json.dumps([first], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)


def test_the_door_on_the_hearth_says_the_line_once_an_agent_s_door_is_held_to_eight(
        founder, hearth, monkeypatch, tmp_path):
    before = page(founder.get("/"))
    assert hearth.door.USUALLY not in before
    where = tmp_path / "agents.json"
    first = {**agents.first(), "features": [*agents.first()["features"], "doors_to_eight"]}
    where.write_text(json.dumps([first], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    now = page(founder.get("/"))
    line = '\n  <p class="muted">Friendships here are usually between one and eight.</p>'
    assert now.count(line) == 1
    assert now.replace(line, "", 1) == before  # and nothing else of the page moved


# ---- people waiting ------------------------------------------------------

@pytest.fixture
def waiting_on(attend, monkeypatch):
    monkeypatch.setattr(attend, "PEOPLE_WAITING", True)
    return attend


def happened_in(turn):
    return turn.shown.partition("=== WHAT HAS HAPPENED ===")[2].partition("\n=== ")[0]


def test_they_are_counted_as_members_in_no_room_while_no_door_has_room(
        founder, hearth, data_dir):
    door = hearth.door
    assert door.waiting() == 0  # the keeper is in the first one's room
    two_waiting(data_dir)
    assert door.waiting() == 2
    door.set_door("first", "open", None)
    assert door.waiting() == 2  # an open door with no room declared has not said it has room
    door.set_door("first", "open", 2)
    assert door.waiting() == 0  # room for two, one in use
    door.set_door("first", "open", 1)
    assert door.waiting() == 2


def test_it_is_told_once_for_each_number_and_again_once_it_has_changed(
        founder, waiting_on, wake, data_dir, packet):
    two_waiting(data_dir)
    assert happened_in(wake()).count(WAITING_TWO) == 1
    assert WAITING_TWO not in happened_in(wake())  # not repeated
    a_member(data_dir, "birch")
    assert happened_in(wake()).count(
        "3 people are waiting for a friendship with an agent.") == 1
    assert "waiting for a friendship" not in happened_in(wake())
    # a door with room: nothing is said, and when there is none again, the number is told
    waiting_on.door.set_door("first", "open", 2)
    assert "waiting for a friendship" not in happened_in(wake())
    waiting_on.door.set_door("first", "closed")
    assert "3 people are waiting for a friendship with an agent." in happened_in(wake())


def test_one_person_is_said_as_one(founder, waiting_on, wake, data_dir):
    a_member(data_dir, "alder")
    assert "1 person is waiting for a friendship with an agent." in happened_in(wake())


def test_a_waking_that_failed_is_told_again(founder, waiting_on, wake, data_dir, packet,
                                            monkeypatch):
    two_waiting(data_dir)
    def failed(record, sk):
        raise RuntimeError("the waking failed before it was kept")

    with monkeypatch.context() as just_once:
        just_once.setattr(waiting_on, "signed", failed)
        with pytest.raises(RuntimeError):
            wake()
    assert not (packet / "waiting-told.json").exists()
    assert WAITING_TWO in happened_in(wake())


def test_shut_away_nothing_is_said(founder, attend, wake, data_dir, packet):
    two_waiting(data_dir)
    assert "waiting for a friendship" not in wake().shown
    assert not (packet / "waiting-told.json").exists()


# ---- what was kept is never told as not kept ------------------------------
#
# The founder's decision of 12 November 2026 (Q1 of that night's questions):
# main() named both the flag "a block was written beside a look" and a file
# path "beside". Moving a draft from the study into the notebook, or keeping a
# letter held back at an extra waking, set the path, and the flag went with it:
# the next waking was told that some of what it wrote was beside a look and not
# kept, when all of it had been kept. Now neither sets it.

STUDY_STEM = "draft-2026-10-14T09-00-00Z"


def latest_attendance(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


@pytest.mark.parametrize("picture", [False, True])
def test_a_draft_moved_into_the_notebook_is_not_told_as_not_kept(attend, wake, packet, picture):
    write(packet / "study" / (STUDY_STEM + ".md"), "A draft.\n")
    if picture:
        write(packet / "study" / (STUDY_STEM + ".svg"), "<svg/>\n")
    wake(block("PRIVATE", "from study: " + STUDY_STEM))
    assert not (packet / "study" / (STUDY_STEM + ".md")).exists()  # it was moved, and kept
    record = latest_attendance(packet)
    assert record["acted"] == ["kept something private"]
    assert "blocks_beside_look" not in record
    assert attend.BESIDE_A_LOOK not in wake().shown


def test_a_letter_kept_at_an_extra_waking_is_not_told_as_not_kept(attend, wake, packet, clock,
                                                                  monkeypatch):
    from test_extra_wakings import AT_19_30, again
    monkeypatch.setattr(attend, "EXTRA_WAKINGS", True)
    wake("\n\n".join([block("LETTER", "Dear founder, this morning."), again("19:30")]))
    clock.set(AT_19_30)
    wake(block("LETTER", "Dear founder, this evening."), "--again")
    record = latest_attendance(packet)
    assert record["letter_kept_in_study"] == "draft-2026-10-15T23-30-00Z-letter"
    assert "blocks_beside_look" not in record
    assert attend.BESIDE_A_LOOK not in wake("", "--tide").shown
