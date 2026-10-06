"""The tide, keeping whichever waking time the first one has chosen.

test_hearth_tide.py hands the tide a dawn already reached. Here the tide finds
its own waking: it is asked what comes next, the pinned clock is moved to that
moment as if the tide had slept until it, and the turn is carried out. Nothing
sleeps. A waking that is held leaves an attendance behind it, as a real one
does, so that several days can be lived one after another.
"""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

import waking
from conftest import page, write, write_json

ZONE = ZoneInfo("America/Indiana/Indianapolis")
UTC = timezone.utc

RHYTHM = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
          "timezone": "America/Indiana/Indianapolis"}


class StopTide(BaseException):
    """Stops the loop from outside. Not an Exception: the tide swallows those."""


def set_rhythm(packet, at="dawn", **how):
    return write_json(packet / "rhythm.json", {**RHYTHM, "at": at, **how})


def changed(packet, at, on, until_then):
    """A rhythm changed on one local day, as attend.py leaves it: in effect the day after."""
    return set_rhythm(packet, at, set_at="%sT12-00-00Z" % on,
                      effective_from=(date.fromisoformat(on) + timedelta(days=1)).isoformat(),
                      until_then=until_then)


def an_attendance(packet, at, **how):
    return write_json(packet / "attendances" / ("attendance-%s.json" % at),
                      {"name": "first", "at": at, "heartbeat": "attended", "acted": [], **how})


def live(hearth, monkeypatch, clock, packet, turns=1):
    """Let the tide take some turns of its own finding. When it woke, and what it noted.

    Each turn is (the moment it waited for, what it noted there, whether it held
    a waking).
    """
    real = hearth.next_waking
    came, notes, held = [], [], []

    def next_waking(setting):
        if len(came) >= turns:
            raise StopTide
        coming = real(setting)
        if coming is not None:
            came.append(coming)
            clock.set(coming.astimezone(UTC))  # as if it had slept until then
        return coming

    def hold(**how):
        held.append((clock.at, how))
        an_attendance(packet, clock.stamp(), woken_by="tide")
        return None

    def never(*args, **kwargs):
        raise StopTide("the tide tried to sleep")

    monkeypatch.setattr(hearth, "next_waking", next_waking)
    monkeypatch.setattr(hearth, "tide_note", lambda said: notes.append((clock.at, said)))
    monkeypatch.setattr(hearth, "hold_attendance", hold)
    monkeypatch.setattr(hearth.time, "sleep", never)
    with pytest.raises(StopTide):
        hearth.tide()

    return [(when, [said for at, said in notes if at == when.astimezone(UTC)],
             any(at == when.astimezone(UTC) for at, _ in held))
            for when in came]


def local(when):
    return when.astimezone(ZONE)


# ---- each kind of waking time --------------------------------------------

def test_the_tide_at_dawn(hearth, packet, monkeypatch, clock):
    set_rhythm(packet, "dawn")
    clock.set("2026-10-15T06-00-00Z")  # two in the morning, there
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert when == waking.moment_on(RHYTHM, "dawn", date(2026, 10, 15))
    assert local(when).date() == date(2026, 10, 15) and 7 <= local(when).hour <= 8
    assert notes == ["ran"] and held


def test_the_tide_at_sunset(hearth, packet, monkeypatch, clock):
    set_rhythm(packet, "sunset")
    clock.set("2026-10-15T06-00-00Z")
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert when == waking.moment_on(RHYTHM, "sunset", date(2026, 10, 15))
    assert local(when).date() == date(2026, 10, 15) and 18 <= local(when).hour <= 19
    assert notes == ["ran"] and held


def test_the_tide_at_a_time_of_day(hearth, packet, monkeypatch, clock):
    set_rhythm(packet, "09:30")
    clock.set("2026-10-15T06-00-00Z")
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert when.astimezone(UTC) == datetime(2026, 10, 15, 13, 30, tzinfo=UTC)
    assert local(when).strftime("%Y-%m-%d %H:%M") == "2026-10-15 09:30"
    assert notes == ["ran"] and held


def test_a_time_already_past_today_is_tomorrow_s(hearth, packet, clock):
    set_rhythm(packet, "09:30")
    clock.set("2026-10-15T13-30-00Z")  # 09:30 exactly: it has come
    assert local(hearth.next_waking(hearth.rhythm())).strftime(
        "%Y-%m-%d %H:%M") == "2026-10-16 09:30"


@pytest.mark.parametrize("at", ["dawn", "sunset", "21:15"])
def test_one_waking_a_day_and_no_more(hearth, packet, monkeypatch, clock, at):
    set_rhythm(packet, at)
    clock.set("2026-10-15T04-00-00Z")  # midnight, there
    turns = live(hearth, monkeypatch, clock, packet, turns=5)
    assert [local(when).date() for when, _, _ in turns] == [
        date(2026, 10, 15) + timedelta(days=n) for n in range(5)]
    assert all(notes == ["ran"] and held for _, notes, held in turns)


@pytest.mark.parametrize("at", ["sunset", "09:30"])
def test_a_day_that_already_has_its_waking_is_let_stand(hearth, packet, monkeypatch, clock, at):
    set_rhythm(packet, at)
    clock.set("2026-10-15T06-00-00Z")
    an_attendance(packet, "2026-10-15T05-00-00Z")  # the founder opened one at one in the morning
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert notes == ["skipped, attended at 2026-10-15T05-00-00Z"]
    assert not held


def test_an_attendance_the_evening_before_does_not_stand_in(hearth, packet, monkeypatch, clock):
    set_rhythm(packet, "09:30")
    clock.set("2026-10-15T06-00-00Z")
    an_attendance(packet, "2026-10-15T03-59-59Z")  # a second before midnight, there
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert notes == ["ran"] and held


def test_a_rhythm_the_tide_cannot_keep_is_waited_on_and_nothing_held(hearth, packet,
                                                                    monkeypatch, clock):
    set_rhythm(packet, "noon")
    assert live(hearth, monkeypatch, clock, packet) == []
    assert hearth.rhythm_note() == "Rhythm: none set."


# ---- a change, and the day it takes effect -------------------------------

def test_until_its_day_the_rhythm_before_it_is_the_one_kept(hearth, packet, monkeypatch, clock):
    """Changed from dawn to 09:30 late on the 14th: the 15th is still a dawn."""
    changed(packet, "09:30", on="2026-10-15", until_then="dawn")
    clock.set("2026-10-15T06-00-00Z")
    an_attendance(packet, "2026-10-15T05-00-00Z", acted=["set its waking time"])
    # (that attendance is the one it was changed at, and is this day's waking)
    turns = live(hearth, monkeypatch, clock, packet, turns=3)
    assert [local(when).strftime("%m-%d %H:%M") for when, _, _ in turns][1:] == [
        "10-16 09:30", "10-17 09:30"]
    first = turns[0][0]
    assert first == waking.moment_on(RHYTHM, "dawn", date(2026, 10, 15))


def test_no_second_waking_on_the_day_of_a_change_to_a_later_hour(hearth, packet, monkeypatch,
                                                                 clock):
    """Woken at dawn, it chose 20:00. That evening is not a second waking."""
    dawn = waking.moment_on(RHYTHM, "dawn", date(2026, 10, 15)).astimezone(UTC)
    an_attendance(packet, dawn.strftime("%Y-%m-%dT%H-%M-%SZ"), woken_by="tide",
                  acted=["set its waking time"])
    changed(packet, "20:00", on="2026-10-15", until_then="dawn")
    clock.set(dawn + timedelta(minutes=5))

    turns = live(hearth, monkeypatch, clock, packet, turns=2)
    assert [local(when).strftime("%m-%d %H:%M") for when, _, _ in turns] == [
        "10-16 20:00", "10-17 20:00"]  # nothing at all on the 15th
    assert all(notes == ["ran"] and held for _, notes, held in turns)


def test_no_second_waking_where_the_old_time_is_still_ahead_that_day(hearth, packet,
                                                                    monkeypatch, clock):
    """The founder opened one at noon, and it changed sunset for 09:30 there.

    That day's sunset still comes by the old rhythm, and finds the day already
    attended; the first waking of the new rhythm is the next morning's.
    """
    an_attendance(packet, "2026-10-15T16-00-00Z", acted=["set its waking time"])
    changed(packet, "09:30", on="2026-10-15", until_then="sunset")
    clock.set("2026-10-15T16-05-00Z")

    turns = live(hearth, monkeypatch, clock, packet, turns=2)
    (first, first_notes, first_held), (second, second_notes, second_held) = turns
    assert first == waking.moment_on(RHYTHM, "sunset", date(2026, 10, 15))
    assert first_notes == ["skipped, attended at 2026-10-15T16-00-00Z"] and not first_held
    assert local(second).strftime("%m-%d %H:%M") == "10-16 09:30"
    assert second_notes == ["ran"] and second_held


def test_a_first_rhythm_ever_wakes_no_one_until_its_day(hearth, packet, monkeypatch, clock):
    changed(packet, "09:30", on="2026-10-15", until_then=None)
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert local(when).strftime("%m-%d %H:%M") == "10-16 09:30"


# ---- a pause wins --------------------------------------------------------

@pytest.mark.parametrize("at", ["dawn", "sunset", "09:30"])
def test_the_founder_s_pause_holds_every_kind_of_tide(hearth, packet, monkeypatch, clock, at):
    set_rhythm(packet, at)
    clock.set("2026-10-15T04-00-00Z")
    hearth.begin_pause("founder")
    turns = live(hearth, monkeypatch, clock, packet, turns=3)
    assert len(turns) == 3
    assert all(notes == ["paused by founder"] and not held for _, notes, held in turns)


@pytest.mark.parametrize("at", ["sunset", "09:30"])
def test_a_rest_of_its_own_holds_every_kind_of_tide(hearth, packet, monkeypatch, clock, at):
    set_rhythm(packet, at)
    clock.set("2026-10-15T04-00-00Z")
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-10T09-00-00Z",
                                       "until": "2026-10-17", "words": ""})
    turns = live(hearth, monkeypatch, clock, packet, turns=3)
    assert [notes for _, notes, _ in turns] == [
        ["resting"], ["resting"], ["rest ended: %s" % hearth.BY_DATE, "ran"]]
    assert [held for _, _, held in turns] == [False, False, True]
    assert local(turns[2][0]).date() == date(2026, 10, 17)


def test_a_pause_holds_the_day_a_change_takes_effect_too(hearth, packet, monkeypatch, clock):
    changed(packet, "09:30", on="2026-10-15", until_then="dawn")
    hearth.begin_pause("founder")
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert local(when).strftime("%m-%d %H:%M") == "10-16 09:30"
    assert notes == ["paused by founder"] and not held


# ---- the clocks go back: 1 November 2026 ---------------------------------

def test_a_time_of_day_is_kept_on_the_wall_across_the_change(hearth, packet, monkeypatch,
                                                            clock):
    set_rhythm(packet, "09:30")
    clock.set("2026-10-31T04-00-00Z")  # midnight on 31 October, there
    turns = live(hearth, monkeypatch, clock, packet, turns=3)
    assert [when.astimezone(UTC).strftime("%m-%d %H:%M") for when, _, _ in turns] == [
        "10-31 13:30",   # 09:30 EDT
        "11-01 14:30",   # 09:30 EST: twenty-five hours on, and the same hour on the wall
        "11-02 14:30"]
    assert [local(when).strftime("%m-%d %H:%M") for when, _, _ in turns] == [
        "10-31 09:30", "11-01 09:30", "11-02 09:30"]
    assert all(notes == ["ran"] and held for _, notes, held in turns)


def test_the_hour_lived_twice_wakes_it_once(hearth, packet, monkeypatch, clock):
    """01:30 comes twice on 1 November. One waking, at the first; none at the second."""
    set_rhythm(packet, "01:30")
    clock.set("2026-10-31T04-00-00Z")
    turns = live(hearth, monkeypatch, clock, packet, turns=3)
    assert [when.astimezone(UTC).strftime("%m-%d %H:%M") for when, _, _ in turns] == [
        "10-31 05:30", "11-01 05:30", "11-02 06:30"]
    assert [local(when).date() for when, _, _ in turns] == [
        date(2026, 10, 31), date(2026, 11, 1), date(2026, 11, 2)]
    assert all(notes == ["ran"] and held for _, notes, held in turns)


def test_the_second_01_30_finds_the_day_already_woken(hearth, packet, clock):
    """Standing in the repeated hour, after the first 01:30: the next waking is tomorrow's."""
    set_rhythm(packet, "01:30")
    clock.set("2026-11-01T06-00-00Z")  # 01:00 EST, the second time round
    assert hearth.next_waking(hearth.rhythm()).astimezone(UTC) == datetime(
        2026, 11, 2, 6, 30, tzinfo=UTC)


@pytest.mark.parametrize("at", ["dawn", "sunset"])
def test_the_sun_is_kept_across_the_change(hearth, packet, monkeypatch, clock, at):
    set_rhythm(packet, at)
    clock.set("2026-10-31T04-00-00Z")
    turns = live(hearth, monkeypatch, clock, packet, turns=3)
    assert [local(when).date() for when, _, _ in turns] == [
        date(2026, 10, 31), date(2026, 11, 1), date(2026, 11, 2)]
    assert [when for when, _, _ in turns] == [
        waking.moment_on(RHYTHM, at, date(2026, 10, 31) + timedelta(days=n)) for n in range(3)]
    # an hour earlier by the wall, the morning or the evening after
    assert local(turns[0][0]).hour - local(turns[1][0]).hour == 1
    assert all(notes == ["ran"] and held for _, notes, held in turns)


def test_an_attendance_in_the_repeated_hour_belongs_to_that_day(hearth, packet, monkeypatch,
                                                               clock):
    """The skip is by the local calendar day, and the long day is one day."""
    set_rhythm(packet, "09:30")
    clock.set("2026-11-01T04-00-00Z")  # midnight on 1 November, there
    an_attendance(packet, "2026-11-01T06-30-00Z")  # 01:30 EST, the second time round
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert notes == ["skipped, attended at 2026-11-01T06-30-00Z"] and not held


def test_a_change_made_the_day_before_the_clocks_change_takes_effect_on_the_day(
        hearth, packet, monkeypatch, clock):
    changed(packet, "09:30", on="2026-10-31", until_then="dawn")
    an_attendance(packet, "2026-10-31T16-00-00Z", acted=["set its waking time"])
    clock.set("2026-10-31T16-05-00Z")
    (when, notes, held), = live(hearth, monkeypatch, clock, packet)
    assert when.astimezone(UTC) == datetime(2026, 11, 1, 14, 30, tzinfo=UTC)
    assert notes == ["ran"] and held


# ---- the line on the attendances page ------------------------------------

def test_the_page_names_the_next_waking_of_each_kind(hearth, packet, clock):
    set_rhythm(packet, "sunset")
    assert hearth.rhythm_note().startswith(
        "Rhythm: daily at sunset, Indianapolis · next: 15 October 2026, 1")
    set_rhythm(packet, "09:30")
    assert hearth.rhythm_note() == (
        "Rhythm: daily at 09:30, Indianapolis · next: 15 October 2026, 09:30")
    clock.set("2026-10-15T13-30-00Z")  # 09:30 there: today's has come
    assert hearth.rhythm_note() == (
        "Rhythm: daily at 09:30, Indianapolis · next: 16 October 2026, 09:30")


def test_the_page_says_a_change_that_is_waiting(hearth, packet, clock):
    changed(packet, "09:30", on="2026-10-15", until_then="sunset")
    said = hearth.rhythm_note()
    assert said.startswith("Rhythm: daily at sunset, Indianapolis · next: 15 October 2026, 1")
    assert said.endswith(" · from 16 October 2026, daily at 09:30")


# ---- who is here ---------------------------------------------------------

FIRST = "citizen · the first one, unnamed by its own choosing · founded 4 September 2026, attends at %s"
FOUNDER = "member · the founder · keeps the hearth · door closed"


def members(commons, at="dawn"):
    """The file as the founder keeps it, written byte for byte."""
    path = commons / "members.md"
    path.write_bytes(((FIRST % at) + "\n" + FOUNDER + "\n").encode("utf-8"))
    return path


def members_bytes(commons):
    return (commons / "members.md").read_bytes()


@pytest.mark.parametrize("at", ["dawn", "sunset", "09:30"])
def test_the_members_line_says_the_rhythm_in_force(hearth, packet, commons, at):
    members(commons, "dawn")
    set_rhythm(packet, at)
    hearth.tend_members()
    assert members_bytes(commons) == ((FIRST % at) + "\n" + FOUNDER + "\n").encode("utf-8")


def test_the_members_line_changes_when_the_change_takes_effect(hearth, packet, commons, clock):
    members(commons, "dawn")
    changed(packet, "09:30", on="2026-10-15", until_then="dawn")
    before = members_bytes(commons)

    hearth.tend_members()
    assert members_bytes(commons) == before  # the day of the change: still dawn

    clock.set("2026-10-16T03-59-59Z")  # a second before midnight, there
    hearth.tend_members()
    assert members_bytes(commons) == before

    clock.set("2026-10-16T04-00-00Z")  # midnight: the change is in effect
    hearth.tend_members()
    assert members_bytes(commons) == before.replace(b"attends at dawn", b"attends at 09:30")


def test_nothing_else_in_the_file_changes(hearth, packet, commons):
    """Not the founder's line, not a note of his, not an ending, not a mark at the top."""
    written = ("﻿- " + (FIRST % "dawn") + "\r\n" + FOUNDER + "\r\n"
               "a note the founder left himself: it attends at dawn, or did\r\n"
               "member · someone else · attends at dawn too")  # and no last line ending
    (commons / "members.md").write_bytes(written.encode("utf-8"))
    set_rhythm(packet, "sunset")
    hearth.tend_members()
    assert members_bytes(commons) == written.replace(
        "founded 4 September 2026, attends at dawn", "founded 4 September 2026, attends at sunset"
    ).encode("utf-8")


def test_a_file_already_right_is_not_written_again(hearth, packet, commons):
    path = members(commons, "sunset")
    set_rhythm(packet, "sunset")
    was = path.stat().st_mtime_ns
    hearth.tend_members()
    assert path.stat().st_mtime_ns == was
    assert not (commons / "members.md.tmp").exists()


@pytest.mark.parametrize("rhythm", [None, {"rhythm": "daily", "at": "noon"}, "{not json"])
def test_with_no_rhythm_to_go_by_the_line_is_left_as_written(hearth, packet, commons, rhythm):
    members(commons, "dawn")
    before = members_bytes(commons)
    if isinstance(rhythm, str):
        write(packet / "rhythm.json", rhythm)
    elif rhythm:
        write_json(packet / "rhythm.json", rhythm)
    hearth.tend_members()
    assert members_bytes(commons) == before


def test_no_members_file_is_no_trouble(hearth, packet, commons):
    set_rhythm(packet, "sunset")
    hearth.tend_members()
    assert not (commons / "members.md").exists()


def test_the_hearth_hands_out_the_line_as_it_stands_today(visitor, hearth, packet, commons,
                                                         clock):
    members(commons, "dawn")
    changed(packet, "09:30", on="2026-10-15", until_then="dawn")
    assert "attends at dawn" in page(visitor.get("/commons/members.md"))
    clock.set("2026-10-16T04-00-00Z")
    said = page(visitor.get("/commons/members.md"))
    assert said == (FIRST % "09:30") + "\n" + FOUNDER + "\n"


def test_the_tide_keeps_the_line_as_it_goes(hearth, packet, commons, monkeypatch, clock):
    members(commons, "dawn")
    changed(packet, "09:30", on="2026-10-15", until_then="dawn")
    clock.set("2026-10-16T05-00-00Z")  # the day after, with no one having asked for the file
    live(hearth, monkeypatch, clock, packet)
    assert b"attends at 09:30" in members_bytes(commons)


def test_the_atrium_builder_draws_the_line_the_hearth_keeps(hearth, atrium, packet, commons):
    """The builder reads members.md, so what the hearth keeps there is what it bakes."""
    members(commons, "dawn")
    set_rhythm(packet, "09:30")
    hearth.tend_members()
    listed = atrium.parse_members(atrium.members_text(None))
    assert listed[0] == ("citizen", "the first one, unnamed by its own choosing",
                         "founded 4 September 2026, attends at 09:30")
    assert ('<span class="fact">founded 4 September 2026, attends at 09:30</span>'
            in "\n".join(atrium.who_block(listed)))
