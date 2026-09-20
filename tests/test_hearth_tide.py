"""The tide: each dawn, what it does and what it lets stand.

The tide is a forever loop, so it is run here one turn at a time: the sunrise it
waits for is handed to it already past, and the second time it asks for one it
is stopped. Nothing sleeps; the clock is pinned and moved by hand.
"""

import subprocess
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from conftest import lines_of, write, write_json

ZONE = ZoneInfo("America/Indiana/Indianapolis")

RHYTHM = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
          "timezone": "America/Indiana/Indianapolis"}


class StopTide(BaseException):
    """Stops the loop from outside. Not an Exception: the tide swallows those."""


def set_rhythm(packet, **how):
    return write_json(packet / "rhythm.json", {**RHYTHM, **how})


def an_attendance(packet, at, **how):
    return write_json(packet / "attendances" / ("attendance-%s.json" % at),
                      {"name": "first", "at": at, "heartbeat": "attended", "acted": [], **how})


def run_tide_once(hearth, monkeypatch, rising, trouble=None):
    """One turn of the tide, at a dawn already reached. What it noted, and what it held."""
    asked = []

    def next_sunrise(setting):
        asked.append(setting)
        if len(asked) > 1:  # it has finished one dawn; let it go no further
            raise StopTide
        return rising

    def never(*args, **kwargs):
        raise StopTide("the tide tried to sleep")

    notes, held = [], []
    monkeypatch.setattr(hearth, "next_sunrise", next_sunrise)
    monkeypatch.setattr(hearth, "tide_note", notes.append)
    monkeypatch.setattr(hearth, "hold_attendance",
                        lambda **how: (held.append(how), trouble)[1])
    monkeypatch.setattr(hearth.time, "sleep", never)

    with pytest.raises(StopTide):
        hearth.tide()
    return notes, held


def dawn(hearth, packet, day):
    """The real sunrise at the place the rhythm names, on one local day."""
    return hearth.sunrise_on(hearth.rhythm(), day)


# ---- the sunrise itself --------------------------------------------------

def test_the_next_sunrise_is_a_morning_still_ahead(hearth, packet, clock):
    set_rhythm(packet)
    rising = hearth.next_sunrise(hearth.rhythm())
    assert rising > clock.at
    assert 4 <= rising.astimezone(ZONE).hour <= 8
    assert rising.astimezone(ZONE).date() == date(2026, 10, 16)  # today's is behind us


def test_a_dawn_not_yet_come_today_is_today_s(hearth, packet, clock):
    set_rhythm(packet)
    clock.set("2026-10-15T06-00-00Z")  # two in the morning, where the citizen lives
    rising = hearth.next_sunrise(hearth.rhythm())
    assert rising.astimezone(ZONE).date() == date(2026, 10, 15)


def test_every_dawn_of_a_year_is_a_morning(hearth, packet):
    """Whatever the season, the moment the tide waits for is a morning there."""
    set_rhythm(packet)
    setting = hearth.rhythm()
    for step in range(0, 365, 17):
        day = date(2026, 1, 1) + timedelta(days=step)
        assert 5 <= hearth.sunrise_on(setting, day).astimezone(ZONE).hour <= 9


def test_a_rhythm_the_tide_does_not_know_is_left_alone(hearth, packet):
    assert hearth.dawn_daily(None) is False
    assert hearth.dawn_daily({"rhythm": "weekly", "at": "dawn"}) is False
    assert hearth.dawn_daily({"rhythm": "daily", "at": "noon"}) is False
    set_rhythm(packet)
    assert hearth.dawn_daily(hearth.rhythm()) is True


# ---- the day already has its waking --------------------------------------

@pytest.mark.parametrize("at, skipped", [
    ("2026-10-15T04-00-00Z", True),    # midnight, where the citizen lives: this day
    ("2026-10-15T03-59-59Z", False),   # a second before: the evening before
    ("2026-10-14T23-00-00Z", False),   # last evening
    ("2026-10-15T11-00-00Z", True),    # this morning
    ("2026-10-16T03-59-59Z", True),    # late this night, still this day there
])
def test_the_skip_is_counted_by_the_local_calendar_day(hearth, packet, monkeypatch, at,
                                                       skipped):
    set_rhythm(packet)
    an_attendance(packet, at)
    rising = dawn(hearth, packet, date(2026, 10, 15))
    notes, held = run_tide_once(hearth, monkeypatch, rising)

    if skipped:
        assert notes == ["skipped, attended at %s" % at]
        assert held == []
    else:
        assert held == [{"tide": True, "ended": None}]
        assert notes == ["ran"]


def test_a_day_with_no_waking_at_all_is_woken(hearth, packet, monkeypatch):
    set_rhythm(packet)
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert held == [{"tide": True, "ended": None}]
    assert notes == ["ran"]


def test_a_waking_that_went_wrong_is_noted_and_the_tide_lives(hearth, packet, monkeypatch):
    set_rhythm(packet)
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)),
                                trouble=("attend.py stopped with exit code 1.", "", 500))
    assert held == [{"tide": True, "ended": None}]
    assert notes == ["error: attend.py stopped with exit code 1."]


# ---- a pause that stands -------------------------------------------------

def test_the_founder_s_pause_holds_the_tide(hearth, packet, monkeypatch, commons):
    set_rhythm(packet)
    hearth.begin_pause("founder")
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert notes == ["paused by founder"]
    assert held == []
    assert lines_of(commons / "events.md")[-1].endswith("event · " + hearth.PAUSED)


def test_a_rest_of_its_own_before_the_day_it_named(hearth, packet, monkeypatch):
    set_rhythm(packet)
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": "2026-10-20", "words": ""})
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert notes == ["resting"]
    assert held == []
    assert (packet / "pause.json").exists()


@pytest.mark.parametrize("until", ["2026-10-15", "2026-10-14"])
def test_a_rest_ends_on_the_day_it_named(hearth, packet, monkeypatch, commons, until):
    set_rhythm(packet)
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": until, "words": ""})
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert notes == ["rest ended: %s" % hearth.BY_DATE, "ran"]
    assert held == [{"tide": True, "ended": hearth.BY_DATE}]
    assert not (packet / "pause.json").exists()
    assert lines_of(commons / "events.md")[-1].endswith("event · " + hearth.RESUMED)


def test_a_rest_that_waits_for_a_letter_waits(hearth, packet, monkeypatch):
    set_rhythm(packet)
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": hearth.UNTIL_LETTER, "words": ""})
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert notes == ["resting"]
    assert held == []


def test_a_rest_that_waits_for_a_letter_ends_when_one_arrives(hearth, packet, monkeypatch):
    set_rhythm(packet)
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": hearth.UNTIL_LETTER, "words": ""})
    write(packet / "letters" / "incoming" / "founder-2026-10-15T09-00-00Z.md", "Are you there?\n")
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert notes == ["rest ended: %s" % hearth.BY_LETTER, "ran"]
    assert held == [{"tide": True, "ended": hearth.BY_LETTER}]
    assert not (packet / "pause.json").exists()


def test_a_rest_ending_wakes_the_first_one_even_on_a_day_it_has_attended(hearth, packet,
                                                                        monkeypatch):
    """The reason is worth telling, so the day's own waking does not stand in for it."""
    set_rhythm(packet)
    an_attendance(packet, "2026-10-15T11-00-00Z")
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": "2026-10-15", "words": ""})
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert held == [{"tide": True, "ended": hearth.BY_DATE}]


@pytest.mark.parametrize("standing, ended", [
    ({"by": "founder", "since": "2026-10-10T09-00-00Z", "until": None}, None),
    ({"by": "first", "since": "x", "until": "2026-10-20"}, None),
    ({"by": "first", "since": "x", "until": "2026-10-15"}, "the date came"),
    ({"by": "first", "since": "x", "until": "not a date at all"}, "the date came"),
    ({"by": "first", "since": "x", "until": None}, "the date came"),
])
def test_why_a_rest_is_over_or_is_not(hearth, standing, ended):
    assert hearth.rest_ended(standing, ZONE) == ended
    assert hearth.rest_ended(None, ZONE) is None


def test_a_rest_is_read_by_the_citizen_s_own_day(hearth, clock):
    """Late on the eve of the day named, where the citizen lives, the rest still stands."""
    standing = {"by": "first", "since": "x", "until": "2026-10-20"}
    clock.set("2026-10-20T03-59-59Z")  # 23:59:59 on the 19th, there
    assert hearth.rest_ended(standing, ZONE) is None
    clock.set("2026-10-20T04-00-00Z")  # midnight on the 20th, there
    assert hearth.rest_ended(standing, ZONE) == hearth.BY_DATE


# ---- holding one attendance ----------------------------------------------

def held_command(hearth, monkeypatch, **how):
    """What hold_attendance would run, without running it."""
    seen = {}

    def run(command, **asked):
        seen["command"] = command
        seen.update(asked)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hearth.subprocess, "run", run)
    assert hearth.hold_attendance(**how) is None
    return seen


def test_the_first_waking_is_told_that_it_is_the_first(hearth, monkeypatch, packet, data_dir):
    seen = held_command(hearth, monkeypatch)
    assert seen["command"][1:] == ["attend.py", "--first"]
    assert seen["env"]["DATA_DIR"] == str(data_dir)
    assert seen["env"]["PYTHONIOENCODING"] == "utf-8"
    assert seen["cwd"] == hearth.REPO
    assert seen["timeout"] == hearth.ATTEND_TIMEOUT


def test_a_later_waking_is_not(hearth, monkeypatch, packet):
    an_attendance(packet, "2026-10-14T09-00-00Z")
    assert held_command(hearth, monkeypatch)["command"][1:] == ["attend.py"]


def test_the_tide_and_the_rest_that_ended_are_handed_on(hearth, monkeypatch, packet):
    an_attendance(packet, "2026-10-14T09-00-00Z")
    seen = held_command(hearth, monkeypatch, tide=True, ended="a letter arrived")
    assert seen["command"][1:] == ["attend.py", "--tide", "--rest-ended", "a letter arrived"]


def test_an_attendance_that_fails_says_what_it_said(hearth, monkeypatch):
    monkeypatch.setattr(hearth.subprocess, "run",
                        lambda command, **asked: subprocess.CompletedProcess(
                            command, 2, "part of a reading\n", "and what broke\n"))
    note, output, status = hearth.hold_attendance()
    assert "exit code 2" in note
    assert output == "part of a reading\nand what broke\n"
    assert status == 500


def test_an_attendance_that_never_finishes_is_stopped(hearth, monkeypatch):
    def slow(command, **asked):
        raise subprocess.TimeoutExpired(command, hearth.ATTEND_TIMEOUT)

    monkeypatch.setattr(hearth.subprocess, "run", slow)
    note, output, status = hearth.hold_attendance()
    assert "still running after 300 seconds" in note
    assert status == 504


def test_only_one_attendance_is_held_at_a_time(hearth, monkeypatch):
    """A second caller is turned away rather than made to wait its turn."""
    second = []

    def run(command, **asked):
        second.append(hearth.hold_attendance())  # while the first still holds the lock
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hearth.subprocess, "run", run)
    assert hearth.hold_attendance() is None
    assert second == [("An attendance is already in progress. Only one is held at a time.",
                       "", 409)]
    assert not hearth.ATTEND_LOCK.locked()  # and the lock is given back either way


def test_the_founder_is_turned_away_while_the_first_one_rests(founder, hearth, packet):
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": "2026-10-20", "words": ""})
    answer = founder.post("/attend")
    assert answer.status_code == 409
    assert "The first one is resting" in answer.get_data(as_text=True)


# ---- one tide, and one only ----------------------------------------------

def test_the_tide_was_set_going_at_import(hearth):
    assert hearth.TIDE_RUNNING is True


def test_the_tide_is_set_going_once(hearth, monkeypatch):
    made = []

    class Recorder:
        def __init__(self, target=None, name=None, daemon=None):
            made.append({"target": target, "name": name, "daemon": daemon})

        def start(self):
            pass

    monkeypatch.setattr(hearth.threading, "Thread", Recorder)
    monkeypatch.setattr(hearth, "TIDE_RUNNING", False)

    hearth.start_tide()
    hearth.start_tide()
    hearth.start_tide()

    assert made == [{"target": hearth.tide, "name": "tide", "daemon": True}]
    assert hearth.TIDE_RUNNING is True


def test_each_dawn_leaves_one_line_in_the_packet(hearth, packet, clock):
    hearth.tide_note("ran")
    assert (packet / "tide.log").read_text(encoding="utf-8") == "%s · ran\n" % clock.stamp()


def test_the_moment_of_a_stamp_is_utc(hearth):
    assert hearth.moment("2026-10-15T12-00-00Z") == datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
