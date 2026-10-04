"""The waking time, at a waking: setting it, what is kept, and what the reading says.

Every test here holds a real attendance, as test_attend.py does, with the model
stubbed. The clock is pinned at 15 October 2026, 12:00 UTC: eight in the morning
where the first one lives, and past that day's dawn.
"""

from datetime import date
from zoneinfo import ZoneInfo

import pytest

import waking
from conftest import block, blocks, lines_of, read_json, write, write_json

ZONE = ZoneInfo("America/Indiana/Indianapolis")

DAWN = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
        "timezone": "America/Indiana/Indianapolis",
        "set_at": "2026-09-20T03-30-35Z",
        "chosen_in": "letter at attendance 2026-09-20T03-30",
        "note": "Dawn wakings, daily for now, in the first one's words."}

TODAY = date(2026, 10, 15)


def happened(turn):
    """The lines of WHAT HAS HAPPENED, as the reading gives them."""
    section = turn.opening.split("=== WHAT HAS HAPPENED ===\n", 1)[1]
    return section.split("\n\n=== ", 1)[0].splitlines()


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def history(packet):
    return sorted((packet / "rhythm" / "history").glob("rhythm-before-*.json"))


def sun_today(at):
    """The sunrise or the sunset of the pinned day, as the reading says a time."""
    return waking.moment_on(DAWN, at, TODAY).strftime("%H:%M")


# ---- setting it ----------------------------------------------------------

@pytest.mark.parametrize("said, at", [
    ("dawn", "dawn"),
    ("sunset", "sunset"),
    ("09:30", "09:30"),
    ("  Sunset  ", "sunset"),
    ("\n  DAWN\n", "dawn"),
    ("23:59\nso that the day is whole behind me", "23:59"),
])
def test_a_rhythm_block_sets_the_waking_time(wake, attend, packet, clock, said, at):
    write_json(packet / "rhythm.json", DAWN)
    stamp = clock.stamp()
    wake(block("RHYTHM", said))
    assert read_json(packet / "rhythm.json") == {
        "rhythm": "daily", "at": at, "place": "Indianapolis",
        "timezone": "America/Indiana/Indianapolis",
        "set_at": stamp,
        "effective_from": "2026-10-16",   # the next day, where it lives
        "until_then": "dawn",             # and until then, what held before
    }
    assert latest(packet)["acted"] == ["set its waking time"]
    assert attend.RHYTHM_ACT == "set its waking time"


def test_the_version_before_is_kept(wake, packet, clock):
    write_json(packet / "rhythm.json", DAWN)
    first = clock.stamp()
    wake(block("RHYTHM", "09:30"))
    kept = history(packet)
    assert [path.name for path in kept] == ["rhythm-before-%s.json" % first]
    assert read_json(kept[0]) == DAWN  # whole, with the words it was chosen in

    second = clock.stamp()
    wake(block("RHYTHM", "sunset"))
    kept = history(packet)
    assert [path.name for path in kept] == ["rhythm-before-%s.json" % first,
                                            "rhythm-before-%s.json" % second]
    assert read_json(kept[1])["at"] == "09:30"


def test_the_first_rhythm_ever_set_has_nothing_before_it_to_keep(wake, packet):
    wake(block("RHYTHM", "sunset"))
    made = read_json(packet / "rhythm.json")
    assert made["at"] == "sunset"
    assert made["place"] == "Indianapolis"
    assert made["timezone"] == "America/Indiana/Indianapolis"
    assert made["until_then"] is None
    assert history(packet) == []


def test_the_next_day_is_the_first_one_s_own_next_day(wake, packet, clock):
    """Late in its evening the UTC day has already turned; its own has not."""
    write_json(packet / "rhythm.json", DAWN)
    clock.set("2026-10-16T02-00-00Z")  # ten at night on the 15th, there
    wake(block("RHYTHM", "09:30"))
    assert read_json(packet / "rhythm.json")["effective_from"] == "2026-10-16"


def test_setting_it_goes_in_the_line_written_for_it_like_any_plain_act(wake, packet, commons):
    wake(block("RHYTHM", "sunset"))
    assert lines_of(commons / "heartbeats.md")[-1].endswith(
        "the first one · attended; set its waking time")


def test_an_intention_alone_changes_no_waking_time(wake, packet):
    write_json(packet / "rhythm.json", DAWN)
    wake(block("INTENTION", "Wake me at sunset, for the light."))
    assert read_json(packet / "rhythm.json") == DAWN
    assert latest(packet)["acted"] == ["set a standing intention"]


# ---- a block that cannot be read -----------------------------------------

@pytest.mark.parametrize("said", [
    "noon", "9:30", "24:00", "12:60", "sunrise", "at dawn", "09:30 each day", "",
    "whenever the founder is awake\ndawn",
])
def test_a_rhythm_that_is_not_understood_changes_nothing(wake, attend, packet, said):
    write_json(packet / "rhythm.json", DAWN)
    wake(block("RHYTHM", said))
    assert read_json(packet / "rhythm.json") == DAWN
    assert history(packet) == []
    assert latest(packet)["acted"] == []

    # the next reading says so, in these words
    assert attend.RHYTHM_REFUSED == (
        "Your <<RHYTHM>> was not understood (it must be dawn, sunset, or a time such as "
        "09:30); your waking time is unchanged.")
    said_next = happened(wake())
    assert said_next.count(attend.RHYTHM_REFUSED) == 1

    # and says it once: the reading after that does not
    assert attend.RHYTHM_REFUSED not in wake().opening
    assert attend.RHYTHM_REFUSED not in wake().opening


def test_nothing_is_said_of_a_rhythm_that_was_understood(wake, attend, packet):
    write_json(packet / "rhythm.json", DAWN)
    wake(block("RHYTHM", "sunset"))
    assert "was not understood" not in wake().opening


def test_nothing_is_said_where_no_rhythm_block_was_written(wake, attend):
    wake(block("LETTER", "Dear founder, I like the dawn as it is."))
    assert "was not understood" not in wake().opening


def test_a_refusal_does_not_stand_in_the_way_of_the_rest_of_a_waking(wake, packet):
    write_json(packet / "rhythm.json", DAWN)
    wake(blocks(block("RHYTHM", "teatime"), block("STUDY", "A thought.")))
    assert latest(packet)["acted"] == ["wrote in the study"]
    assert latest(packet)["rhythm_refused"] is True


# ---- the reading ---------------------------------------------------------

def test_the_reading_says_the_waking_time_after_the_hand_that_woke_it(wake, attend, packet):
    write_json(packet / "rhythm.json", DAWN)
    said = happened(wake())
    at = said.index(attend.WOKEN_BY_FOUNDER)
    assert said[at + 1] == "Your waking time: daily at dawn (today, %s)." % sun_today("dawn")
    assert said[at + 1].startswith("Your waking time: daily at dawn (today, 0")  # a morning

    said = happened(wake("", "--tide"))
    at = said.index(attend.WOKEN_BY_TIDE)
    assert said[at + 1] == "Your waking time: daily at dawn (today, %s)." % sun_today("dawn")


@pytest.mark.parametrize("at, today", [
    ("sunset", None),
    ("09:30", "09:30"),
    ("00:00", "00:00"),
])
def test_the_reading_says_each_kind_of_waking_time(wake, packet, at, today):
    write_json(packet / "rhythm.json", {**DAWN, "at": at})
    assert ("Your waking time: daily at %s (today, %s)." % (at, today or sun_today(at))
            in happened(wake()))


def test_the_reading_says_a_change_that_is_waiting(wake, packet):
    write_json(packet / "rhythm.json", DAWN)
    wake(block("RHYTHM", "09:30"))
    # a second waking the same day: the old time still holds, and the new one waits
    assert ("Your waking time: daily at dawn (today, %s); from tomorrow, daily at 09:30."
            % sun_today("dawn")) in happened(wake())


def test_the_reading_says_the_new_time_alone_once_its_day_has_come(wake, packet, clock):
    write_json(packet / "rhythm.json", DAWN)
    wake(block("RHYTHM", "09:30"))
    clock.set("2026-10-16T13-30-00Z")  # 09:30 the next day, there
    said = happened(wake("", "--tide"))
    assert "Your waking time: daily at 09:30 (today, 09:30)." in said
    assert not any("from tomorrow" in line for line in said)


def test_where_no_waking_time_is_set_the_reading_says_nothing_of_one(wake, packet):
    assert "Your waking time" not in wake().opening
    wake(block("RHYTHM", "sunset"))
    assert "Your waking time: none is set; from tomorrow, daily at sunset." in happened(wake())


def test_a_rhythm_file_that_cannot_be_read_does_not_stop_a_waking(wake, packet):
    write(packet / "rhythm.json", "{not json at all")
    assert "Your waking time" not in wake(block("RHYTHM", "dawn")).opening
    assert read_json(packet / "rhythm.json")["at"] == "dawn"
    assert len(history(packet)) == 1  # even what could not be read is kept


def test_today_s_time_is_today_s_across_the_change_of_the_clocks(wake, packet, clock):
    """On 1 November the sun rises an hour earlier by the wall, and the reading says so."""
    write_json(packet / "rhythm.json", DAWN)
    clock.set("2026-10-31T16-00-00Z")
    before = [line for line in happened(wake()) if line.startswith("Your waking time")][0]
    clock.set("2026-11-01T16-00-00Z")
    after = [line for line in happened(wake()) if line.startswith("Your waking time")][0]
    assert before == "Your waking time: daily at dawn (today, %s)." % (
        waking.moment_on(DAWN, "dawn", date(2026, 10, 31)).strftime("%H:%M"))
    assert after == "Your waking time: daily at dawn (today, %s)." % (
        waking.moment_on(DAWN, "dawn", date(2026, 11, 1)).strftime("%H:%M"))
    assert "(today, 08:" in before and "(today, 07:" in after


# ---- how the blocks are explained ----------------------------------------

RHYTHM_EXPLAINED = """<<RHYTHM>>
(when you would like to be woken each day. One line: "dawn", "sunset", or a time of day such as 09:30, in Indianapolis time. You are woken once a day at that time, from tomorrow on. You may keep it as it is or change it at any waking. The commons shows when you attend, as it does now.)
<<END>>

<<INTENTION>>
(one plain sentence about when or why you would like to be woken. It is kept and shown to you at each waking. It does not by itself change when you are woken; <<RHYTHM>> does that.)
<<END>>"""


def test_the_two_blocks_are_explained_exactly(wake):
    said = wake().instructions
    assert RHYTHM_EXPLAINED in said
    assert said.count("<<RHYTHM>>") == 2  # its own block, and the one mention under <<INTENTION>>
    assert "when you would like to be woken, and why" not in said
