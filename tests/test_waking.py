"""The waking time: how one is read, when one holds, and what moment it is on a day.

waking.py reads no file and asks no clock, so everything here is plain
arithmetic: a setting, a day, and what comes of them.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import waking

ZONE = ZoneInfo("America/Indiana/Indianapolis")
UTC = timezone.utc

DAWN = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
        "timezone": "America/Indiana/Indianapolis"}


def rhythm(at, **how):
    return {**DAWN, "at": at, **how}


# ---- what a <<RHYTHM>> block asks for ------------------------------------

@pytest.mark.parametrize("said, at", [
    ("dawn", "dawn"),
    ("sunset", "sunset"),
    ("09:30", "09:30"),
    ("00:00", "00:00"),
    ("23:59", "23:59"),
    ("Dawn", "dawn"),                     # case is not held against it
    ("SUNSET", "sunset"),
    ("   dawn   ", "dawn"),               # nor space either side
    ("\n\n  21:05  \n", "21:05"),         # the first line that is not blank
    ("sunset\nbecause the light is kinder then", "sunset"),  # what is under it is only words
])
def test_a_waking_time_that_can_be_read(said, at):
    assert waking.asked(said) == at


@pytest.mark.parametrize("said", [
    "",
    "   \n  ",
    "noon",
    "sunrise",
    "9:30",               # two figures each side
    "24:00",
    "23:60",
    "09:30am",
    "09.30",
    "at dawn",
    "dawn, please",
    "dawn sunset",
    "because the light is kinder then\nsunset",  # the first line is the asking, not the second
])
def test_a_waking_time_that_cannot(said):
    assert waking.asked(said) is None


def test_no_block_at_all_asks_for_nothing():
    assert waking.asked(None) is None


# ---- which rhythm holds on a day -----------------------------------------

def test_a_rhythm_with_no_day_named_holds_already():
    assert waking.in_force(DAWN, date(2026, 10, 15)) == "dawn"
    assert waking.waiting(DAWN, date(2026, 10, 15)) is None


def test_until_its_day_the_rhythm_before_it_holds():
    changed = rhythm("09:30", effective_from="2026-10-16", until_then="dawn")
    assert waking.in_force(changed, date(2026, 10, 15)) == "dawn"
    assert waking.waiting(changed, date(2026, 10, 15)) == "09:30"
    assert waking.in_force(changed, date(2026, 10, 16)) == "09:30"
    assert waking.waiting(changed, date(2026, 10, 16)) is None
    assert waking.in_force(changed, date(2026, 12, 1)) == "09:30"


def test_where_nothing_held_before_nothing_holds_until_its_day():
    first = rhythm("sunset", effective_from="2026-10-16", until_then=None)
    assert waking.in_force(first, date(2026, 10, 15)) is None
    assert waking.waiting(first, date(2026, 10, 15)) == "sunset"
    assert waking.in_force(first, date(2026, 10, 16)) == "sunset"


@pytest.mark.parametrize("setting", [
    None, {}, [], "dawn",
    {"rhythm": "weekly", "at": "dawn"},
    {"rhythm": "daily", "at": "noon"},
    {"rhythm": "daily"},
])
def test_a_rhythm_the_tide_cannot_keep_is_none(setting):
    assert waking.in_force(setting, date(2026, 10, 15)) is None
    assert waking.waiting(setting, date(2026, 10, 15)) is None


# ---- choosing one --------------------------------------------------------

def test_a_choice_holds_from_the_next_local_day():
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    made = waking.chosen(DAWN, "09:30", "2026-10-15T12-00-00Z", now)
    assert made == {"rhythm": "daily", "at": "09:30", "place": "Indianapolis",
                    "timezone": "America/Indiana/Indianapolis",
                    "set_at": "2026-10-15T12-00-00Z",
                    "effective_from": "2026-10-16", "until_then": "dawn"}


def test_the_next_day_is_counted_where_the_first_one_lives():
    """02:00 UTC on the 16th is still the evening of the 15th there."""
    now = datetime(2026, 10, 16, 2, 0, tzinfo=UTC)
    made = waking.chosen(DAWN, "sunset", "2026-10-16T02-00-00Z", now)
    assert made["effective_from"] == "2026-10-16"


def test_with_no_rhythm_before_it_the_place_and_the_zone_are_the_first_one_s():
    made = waking.chosen(None, "dawn", "2026-10-15T12-00-00Z",
                         datetime(2026, 10, 15, 12, 0, tzinfo=UTC))
    assert made["place"] == "Indianapolis"
    assert made["timezone"] == "America/Indiana/Indianapolis"
    assert made["until_then"] is None


def test_a_second_change_on_one_day_does_not_bring_the_first_in_early():
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
    once = waking.chosen(DAWN, "09:30", "2026-10-15T12-00-00Z", now)
    twice = waking.chosen(once, "sunset", "2026-10-15T15-00-00Z", now + timedelta(hours=3))
    assert twice["at"] == "sunset"
    assert twice["until_then"] == "dawn"  # what holds today, not what was written last
    assert twice["effective_from"] == "2026-10-16"


# ---- the moment itself ---------------------------------------------------

def test_dawn_is_a_morning_and_sunset_an_evening_all_year():
    for step in range(0, 365, 11):
        day = date(2026, 1, 1) + timedelta(days=step)
        rising = waking.moment_on(DAWN, "dawn", day)
        setting = waking.moment_on(DAWN, "sunset", day)
        assert rising.astimezone(ZONE).date() == day
        assert setting.astimezone(ZONE).date() == day
        assert 5 <= rising.astimezone(ZONE).hour <= 9
        assert 17 <= setting.astimezone(ZONE).hour <= 21


def test_a_time_of_day_is_read_off_the_wall_there():
    at = waking.moment_on(DAWN, "09:30", date(2026, 10, 15))
    assert at.astimezone(UTC) == datetime(2026, 10, 15, 13, 30, tzinfo=UTC)  # EDT
    assert at.strftime("%H:%M") == "09:30"


# ---- the clocks change: 1 November 2026, and 14 March 2027 ---------------

def test_a_time_of_day_stays_on_the_wall_when_the_clocks_go_back():
    before = waking.moment_on(DAWN, "09:30", date(2026, 10, 31))
    after = waking.moment_on(DAWN, "09:30", date(2026, 11, 1))
    assert before.astimezone(UTC) == datetime(2026, 10, 31, 13, 30, tzinfo=UTC)  # EDT, -4
    assert after.astimezone(UTC) == datetime(2026, 11, 1, 14, 30, tzinfo=UTC)    # EST, -5
    # (taken in UTC: two moments on the one zone's clock subtract by the wall)
    assert after.astimezone(UTC) - before.astimezone(UTC) == timedelta(hours=25)  # the long day
    assert before.strftime("%H:%M") == after.strftime("%H:%M") == "09:30"


def test_an_hour_lived_twice_wakes_it_at_the_first_of_the_two():
    """01:30 comes twice on 1 November; the waking is the earlier, and there is one."""
    at = waking.moment_on(DAWN, "01:30", date(2026, 11, 1))
    assert at.astimezone(UTC) == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert at.astimezone(ZONE).date() == date(2026, 11, 1)
    next_day = waking.moment_on(DAWN, "01:30", date(2026, 11, 2))
    assert next_day.astimezone(UTC) == datetime(2026, 11, 2, 6, 30, tzinfo=UTC)


def test_an_hour_that_is_skipped_still_has_its_waking_that_day():
    """02:30 does not exist on 14 March 2027; it comes at 03:30, and on that day."""
    at = waking.moment_on(DAWN, "02:30", date(2027, 3, 14))
    assert at.astimezone(UTC) == datetime(2027, 3, 14, 7, 30, tzinfo=UTC)
    assert at.astimezone(ZONE).date() == date(2027, 3, 14)
    assert at.strftime("%H:%M") == "03:30"


def test_dawn_and_sunset_follow_the_sun_across_the_change():
    """The sun does not change its hour; the wall does. An hour earlier by the clock."""
    for at in ("dawn", "sunset"):
        before = waking.moment_on(DAWN, at, date(2026, 10, 31))
        after = waking.moment_on(DAWN, at, date(2026, 11, 1))
        apart = after.astimezone(UTC) - before.astimezone(UTC)
        assert timedelta(hours=23, minutes=55) < apart < timedelta(hours=24, minutes=5)
        assert before.astimezone(ZONE).hour - after.astimezone(ZONE).hour == 1
        assert after.astimezone(ZONE).date() == date(2026, 11, 1)
