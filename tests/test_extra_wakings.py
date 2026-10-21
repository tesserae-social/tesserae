"""Extra wakings: once more, later the same day, at the first one's own asking.

Built shut away behind attend.EXTRA_WAKINGS. Shut away, the first one is sent
byte for byte what the attend.py committed before them sends it, and the same
files are left - held here against that committed attend.py, with a
<<WAKE_AGAIN>> block written at each waking and an asking already waiting in the
packet, and in test_rooms_reading.py by the reading's fingerprint, which did not
move - and the tide keeps no waking but the daily one.

With it on, a <<WAKE_AGAIN>> block asks for a time later the same local day, or
that day's sunset; one a day, never from an extra waking, never for a time
already past, each refusal told once. The tide holds it through hold_attendance,
as "its own asking", unless a pause stands then, and it is told once of that
too. Letters stay once a day: at an extra waking a letter after one has gone is
kept in its study, with any picture drawn beside it. Nothing of it is public.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone

import pytest

import waking
from conftest import REPO, Turn, block, blocks, page, read_json, write, write_json

# The last attend.py before there were any extra wakings, kept in the history.
BEFORE_EXTRA_WAKINGS = "64d97e2"

EXPLAINED = """<<WAKE_AGAIN>>
(to be woken once more later today: one line, a time such as 19:30, or "sunset". At most one extra waking a day, and not from an extra waking. Letters still go out once a day; a letter written at an extra waking, after one has already gone today, is kept in your study for your next waking. A pause of yours always comes first.)
<<END>>"""

ASKED_BACK = "This waking came because you asked for it at your last waking."
LETTER_KEPT = ("The letter you wrote at your extra waking was kept in your study, because one "
               "letter goes out each day; you may send it at your next waking.")

UTC = timezone.utc
RHYTHM = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
          "timezone": "America/Indiana/Indianapolis"}

# The clock the tests run at, 2026-10-15T12-00-00Z, is 08:00 in Indianapolis.
ASKED_AT = "2026-10-15T12-00-00Z"
AT_19_30 = "2026-10-15T23-30-00Z"


def again(said):
    return block("WAKE_AGAIN", said)


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def waiting_in(packet):
    path = packet / "wake-again.json"
    return read_json(path) if path.exists() else None


def kept_in(packet):
    return [read_json(path) for path in sorted((packet / "wake-again").glob("wake-again-*.json"))]


def left_in(data_dir):
    return {path.relative_to(data_dir).as_posix(): path.read_bytes()
            for path in sorted(data_dir.rglob("*")) if path.is_file()}


def as_sent(asked):
    return json.dumps(asked, sort_keys=True, ensure_ascii=False, default=vars).encode("utf-8")


def stamp_of(when):
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


@pytest.fixture
def on(attend, monkeypatch):
    monkeypatch.setattr(attend, "EXTRA_WAKINGS", True)
    return attend


@pytest.fixture
def hearth_on(hearth, monkeypatch):
    monkeypatch.setattr(hearth.the_waking, "EXTRA_WAKINGS", True)
    return hearth


# ---- shut away -----------------------------------------------------------

def test_it_is_shut_away(attend):
    assert attend.EXTRA_WAKINGS is False


def test_shut_away_a_block_is_only_words(wake, attend, packet):
    turn = wake(blocks("I am here.", again("19:30")))
    assert not (packet / "wake-again.json").exists()
    assert "WAKE_AGAIN" not in turn.instructions
    record = latest(packet)
    assert attend.WAKE_AGAIN_ACT not in record["acted"] and "wake_again_refused" not in record
    # and a waking held with --again is a waking by the founder's hand, as before
    turn = wake("", "--again")
    assert ASKED_BACK not in turn.shown and attend.WOKEN_BY_FOUNDER in turn.shown
    assert latest(packet)["woken_by"] == "founder"


def test_shut_away_it_is_sent_and_leaves_byte_for_byte_what_the_committed_one_does(
        attend, data_dir, packet, clock, monkeypatch, tmp_path):
    """Three wakings each, in one world: the committed attend.py, and this one shut away."""
    try:
        source = subprocess.run(["git", "show", BEFORE_EXTRA_WAKINGS + ":attend.py"], cwd=REPO,
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the history is not here to read the committed attend.py out of")
    old_path = tmp_path / "attend_before_extra_wakings.py"
    old_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("attend_before_extra_wakings", old_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    clock.pin(old, monkeypatch)
    assert not hasattr(old, "EXTRA_WAKINGS")

    write(packet / "letters" / "incoming" / "founder-2026-10-15T08-00-00Z.md", "A new letter.\n")
    # even an asking already waiting, and one the tide let go, change nothing
    write_json(packet / "wake-again.json", {"at": AT_19_30, "asked_at": "2026-10-15T11-00-00Z"})
    write_json(packet / "wake-again" / "wake-again-2026-10-14T11-00-00Z.json",
               {"at": "2026-10-14T23-00-00Z", "asked_at": "2026-10-14T11-00-00Z",
                "dropped_at": "2026-10-14T23-00-00Z", "why": "paused"})
    said = blocks("I read it.", block("LETTER", "Dear founder,"), again("19:30"),
                  again("sunset"), again("07:00"), again("not a time"))

    def three_wakings(module):
        sent = []
        for at, reply, flags in (("2026-10-15T12-00-00Z", said, ["--tide"]),
                                 ("2026-10-15T12-05-00Z", said, ["--again"]),
                                 ("2026-10-15T12-10-00Z", "", [])):
            clock.set(at)
            turn = Turn(reply, stop_reason="end_turn")
            monkeypatch.setattr(module, "Anthropic", turn.client)
            monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
            module.main()
            assert len(turn.asked) == 1
            sent.append(as_sent(turn.asked[0]))
        return sent, left_in(data_dir)

    before = tmp_path / "the-world-before"
    shutil.copytree(data_dir, before)
    sent_then, left_then = three_wakings(old)
    shutil.rmtree(data_dir)
    shutil.copytree(before, data_dir)
    sent_now, left_now = three_wakings(attend)

    assert sent_now == sent_then
    assert left_now == left_then
    assert any("attendances/" in name for name in left_now)  # and it is not an empty likeness


# ---- asking --------------------------------------------------------------

def test_the_block_is_explained_exactly_and_only_once(on, wake):
    turn = wake()
    assert on.WAKE_AGAIN_BLOCK == EXPLAINED
    assert turn.instructions.count(EXPLAINED) == 1
    assert turn.instructions.count("<<WAKE_AGAIN>>") == 1


def test_a_time_later_today_is_kept_privately(on, wake, packet, commons):
    events = (commons / "events.md").read_bytes()
    wake(blocks("I would like the evening too.", again("19:30")))
    assert waiting_in(packet) == {"at": AT_19_30, "asked_at": ASKED_AT}
    record = latest(packet)
    assert record["acted"] == ["asked to wake again"]
    assert "asked to wake again" in on.PRIVATE_ACTS
    # nothing public: the heartbeat is the bare fact, and no event is written
    assert (commons / "heartbeats.md").read_text(encoding="utf-8").endswith(
        "· the first one · attended\n")
    assert (commons / "events.md").read_bytes() == events


def test_the_time_is_read_on_its_own_waking_clock(on, wake, packet):
    write_json(packet / "rhythm.json", {**RHYTHM, "timezone": "Europe/London"})
    wake(again("19:30"))  # 13:00 in London, so 19:30 there is still to come
    assert waiting_in(packet)["at"] == "2026-10-15T18-30-00Z"


def test_sunset_is_that_day_s_sunset(on, wake, packet):
    wake(again("Sunset\nwhen the light goes"))
    sunset = waking.moment_on(RHYTHM, "sunset", date(2026, 10, 15))
    assert waiting_in(packet) == {"at": stamp_of(sunset), "asked_at": ASKED_AT}
    assert 18 <= sunset.hour <= 19


def test_a_sunset_already_gone_is_refused_and_told_once(on, wake, packet, clock):
    clock.set("2026-10-16T00-30-00Z")  # 20:30 on the 15th, there
    wake(again("sunset"))
    assert waiting_in(packet) is None
    sunset = waking.moment_on(RHYTHM, "sunset", date(2026, 10, 15)).strftime("%H:%M")
    told = ("Your <<WAKE_AGAIN>> at your last waking was not kept: that day's sunset, at %s, had "
            "already passed, and an extra waking must be later the same day. You were not woken "
            "again." % sunset)
    assert latest(packet)["wake_again_refused"] == [told]
    assert wake().shown.count(told) == 1
    assert told not in wake().shown


@pytest.mark.parametrize("at", ["07:00", "08:00"])
def test_a_time_already_past_is_refused_and_told_once(on, wake, packet, at):
    turn = wake(again(at))
    assert waiting_in(packet) is None
    assert on.WAKE_AGAIN_ACT not in latest(packet)["acted"]
    told = ("Your <<WAKE_AGAIN>> at your last waking was not kept: %s had already passed, and "
            "an extra waking must be later the same day. You were not woken again." % at)
    assert told not in turn.shown
    assert wake().shown.count(told) == 1
    assert told not in wake().shown


@pytest.mark.parametrize("said", ["dawn", "7pm", "19:30 tonight", "24:00", "", "\n\n"])
def test_a_line_that_cannot_be_read_is_refused_and_told_once(on, wake, packet, said):
    wake(again(said))
    assert waiting_in(packet) is None
    told = ("Your <<WAKE_AGAIN>> at your last waking was not kept: its first line must be a time "
            "later that day, such as 19:30, or \"sunset\". You were not woken again.")
    assert latest(packet)["wake_again_refused"] == [told]
    assert wake().shown.count(told) == 1
    assert told not in wake().shown


SECOND = ("Your <<WAKE_AGAIN>> at your last waking was not kept: you had already asked to be "
          "woken again that day, and one extra waking a day is the most.")


def test_a_second_asking_on_the_same_day_is_refused(on, wake, packet):
    wake(again("19:30"))
    wake(again("20:00"))  # another waking the same day, by the founder's hand
    assert waiting_in(packet) == {"at": AT_19_30, "asked_at": ASKED_AT}
    assert latest(packet)["wake_again_refused"] == [SECOND]
    assert wake().shown.count(SECOND) == 1


def test_two_blocks_at_one_waking_keep_the_first(on, wake, packet):
    wake(blocks(again("19:30"), again("21:00")))
    assert waiting_in(packet)["at"] == AT_19_30
    assert latest(packet)["wake_again_refused"] == [SECOND]


def test_one_a_day_counts_an_asking_the_tide_has_done_with(on, wake, packet, clock):
    write_json(packet / "wake-again" / "wake-again-2026-10-15T10-00-00Z.json",
               {"at": "2026-10-15T11-00-00Z", "asked_at": "2026-10-15T10-00-00Z",
                "woken_at": "2026-10-15T11-00-00Z"})
    wake(again("19:30"))
    assert waiting_in(packet) is None
    assert latest(packet)["wake_again_refused"] == [SECOND]
    # the next day is a day of its own
    clock.set("2026-10-16T12-00-00Z")
    wake(again("19:30"))
    assert waiting_in(packet) == {"at": "2026-10-16T23-30-00Z", "asked_at": "2026-10-16T12-00-00Z"}


def test_one_asked_late_last_night_is_yesterday_s(on, wake, packet):
    # 23:00 on the 14th, there, though the 15th in UTC
    write_json(packet / "wake-again" / "wake-again-2026-10-15T03-00-00Z.json",
               {"at": "2026-10-15T03-30-00Z", "asked_at": "2026-10-15T03-00-00Z",
                "woken_at": "2026-10-15T03-30-00Z"})
    wake(again("19:30"))
    assert waiting_in(packet)["at"] == AT_19_30


def test_an_extra_waking_cannot_ask_for_another(on, wake, packet):
    wake(again("19:30"), "--again")
    assert waiting_in(packet) is None
    told = ("Your <<WAKE_AGAIN>> at your last waking was not kept: that was an extra waking, and "
            "an extra waking cannot ask for another. You may ask again at your next daily waking.")
    assert latest(packet)["wake_again_refused"] == [told]
    assert wake().shown.count(told) == 1


def test_one_from_a_day_gone_by_is_set_aside_not_erased(on, wake, packet):
    stale = {"at": "2026-10-14T23-30-00Z", "asked_at": "2026-10-14T12-00-00Z"}
    write_json(packet / "wake-again.json", stale)
    wake(again("19:30"))
    assert waiting_in(packet)["at"] == AT_19_30
    assert kept_in(packet) == [{**stale, "dropped_at": ASKED_AT, "why": "lapsed"}]


# ---- the extra waking itself ---------------------------------------------

def test_the_reading_says_why_it_came(on, wake, packet):
    turn = wake("", "--again")
    happened = turn.opening[turn.opening.index("=== WHAT HAS HAPPENED ==="):]
    assert ASKED_BACK in happened
    assert on.WOKEN_BY_TIDE not in turn.shown and on.WOKEN_BY_FOUNDER not in turn.shown
    assert latest(packet)["woken_by"] == "its own asking"
    # and the next waking's list of attendances says who woke it
    assert "woken by its own asking" in wake("", "--tide").shown


def test_everything_else_works_as_at_any_waking(on, wake, packet):
    wake(blocks(block("MEMORY", "Kept at an extra waking."), block("STUDY", "A draft.")),
         "--again")
    assert (packet / "memory" / "notes.md").read_text(encoding="utf-8") == (
        "Kept at an extra waking.\n")
    assert latest(packet)["acted"] == ["kept notes", "wrote in the study"]


def test_what_it_has_chosen_says_one_is_waiting(on, wake, clock):
    turn = wake(again("19:30"))
    assert "You asked to be woken again today" not in turn.shown
    chosen = wake().shown
    chosen = chosen[chosen.index("=== WHAT YOU HAVE CHOSEN ==="):]
    assert chosen.split("\n=== ")[0].count("You asked to be woken again today at 19:30.") == 1
    clock.set("2026-10-16T12-00-00Z")  # a day gone, and the tide never kept it
    assert "You asked to be woken again today" not in wake().shown


def test_a_pause_that_let_it_go_is_told_once(on, wake, packet):
    write_json(packet / "wake-again" / "wake-again-2026-10-15T11-00-00Z.json",
               {"at": "2026-10-15T11-30-00Z", "asked_at": "2026-10-15T11-00-00Z",
                "dropped_at": "2026-10-15T11-30-00Z", "why": "paused"})
    an_attendance(packet, "2026-10-15T11-00-00Z")
    told = ("The extra waking you asked for, at 07:30 on 15 October 2026, did not come, because a "
            "pause stood then; a pause always comes first.")
    assert wake().shown.count(told) == 1
    assert told not in wake().shown


def test_one_the_tide_could_not_keep_is_told_once(on, wake, packet):
    write_json(packet / "wake-again" / "wake-again-2026-10-14T20-00-00Z.json",
               {"at": "2026-10-14T23-30-00Z", "asked_at": "2026-10-14T20-00-00Z",
                "dropped_at": "2026-10-15T11-00-00Z", "why": "lapsed"})
    an_attendance(packet, "2026-10-14T20-00-00Z")
    told = ("The extra waking you asked for, at 19:30 on 14 October 2026, did not come, because "
            "the tide was not running then.")
    assert wake().shown.count(told) == 1
    assert told not in wake().shown


# ---- letters, once a day -------------------------------------------------

def outgoing(packet):
    return sorted(p.name for p in (packet / "letters" / "outgoing").glob("*.md"))


def test_a_second_letter_at_an_extra_waking_is_kept_in_the_study(on, wake, packet, clock):
    wake(blocks(block("LETTER", "Dear founder, this morning."), again("19:30")))
    sent = outgoing(packet)
    clock.set(AT_19_30)
    wake(blocks(block("LETTER", "Dear founder, this evening."), block("STUDY", "And a draft.")),
         "--again")
    assert outgoing(packet) == sent
    kept = (packet / "study" / "draft-2026-10-15T23-30-00Z-letter.md").read_text(encoding="utf-8")
    assert kept == ("(This was a letter to the founder, written at an extra waking on 15 October "
                    "2026. It was kept here because one letter goes out each day; you may send it "
                    "at your next waking.)\n\nDear founder, this evening.\n")
    assert (packet / "study" / "draft-2026-10-15T23-30-00Z.md").exists()  # its own draft too
    record = latest(packet)
    assert record["acted"] == ["wrote in the study"]
    assert record["letter_kept_in_study"] is True
    turn = wake("", "--tide")
    assert turn.shown.count(LETTER_KEPT) == 1
    assert "Dear founder, this evening." in turn.shown  # it is in its study, to send
    assert LETTER_KEPT not in wake().shown


DRAWN = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
         '<rect x="1" y="1" width="8" height="8" fill="#c96" /></svg>')


def sent_pictures(packet):
    return sorted(p.name for p in (packet / "letters" / "outgoing").glob("*.svg"))


def test_a_picture_beside_a_kept_letter_stays_in_the_study_with_it(on, wake, packet, clock):
    wake(blocks(block("LETTER", "Dear founder, this morning."), again("19:30")))
    sent = outgoing(packet)
    clock.set(AT_19_30)
    wake(blocks(block("LETTER", "Dear founder, this evening."), block("PICTURE", DRAWN)),
         "--again")
    # nothing went out: no letter, no "(a picture)" to carry it, no picture
    assert outgoing(packet) == sent
    assert sent_pictures(packet) == []
    study = packet / "study"
    beside = study / "draft-2026-10-15T23-30-00Z-letter.svg"
    assert beside.read_text(encoding="utf-8") == on.picture_drawn(DRAWN) + "\n"
    kept = (study / "draft-2026-10-15T23-30-00Z-letter.md").read_text(encoding="utf-8")
    assert kept == ("(This was a letter to the founder, written at an extra waking on 15 October "
                    "2026. It was kept here because one letter goes out each day; you may send it "
                    "at your next waking. The picture you drew beside it is kept with it, as "
                    "draft-2026-10-15T23-30-00Z-letter.svg, and was not sent either.)\n\n"
                    "Dear founder, this evening.\n")
    record = latest(packet)
    assert record["acted"] == ["drew a picture", "wrote in the study"]
    assert record["letter_kept_in_study"] is True
    # the next reading shows the draft with its header, and tells it once
    turn = wake("", "--tide")
    assert turn.shown.count(LETTER_KEPT) == 1
    assert "as draft-2026-10-15T23-30-00Z-letter.svg, and was not sent either." in turn.shown


def test_a_picture_alone_at_an_extra_waking_goes_out_as_ever(on, wake, packet, clock):
    wake(blocks(block("LETTER", "Dear founder, this morning."), again("19:30")))
    clock.set(AT_19_30)
    wake(block("PICTURE", DRAWN), "--again")
    assert sent_pictures(packet) == ["to-founder-2026-10-15T23-30-00Z.svg"]
    assert (packet / "letters" / "outgoing" / "to-founder-2026-10-15T23-30-00Z.md").read_text(
        encoding="utf-8") == "(a picture)\n"
    assert not list((packet / "study").glob("*-letter.*"))


def test_a_picture_beside_a_letter_that_goes_goes_with_it(on, wake, packet, clock):
    wake(again("19:30"))
    clock.set(AT_19_30)
    wake(blocks(block("LETTER", "Dear founder,"), block("PICTURE", DRAWN)), "--again")
    assert sent_pictures(packet) == ["to-founder-2026-10-15T23-30-00Z.svg"]
    assert not list((packet / "study").glob("*-letter.*"))


def test_a_letter_at_an_extra_waking_goes_where_none_has_gone_today(on, wake, packet, clock):
    wake(again("19:30"))
    clock.set(AT_19_30)
    wake(block("LETTER", "Dear founder,"), "--again")
    assert outgoing(packet) == ["to-founder-2026-10-15T23-30-00Z.md"]
    assert "wrote a letter to the founder" in latest(packet)["acted"]
    assert not list((packet / "study").glob("*-letter.md"))


def test_a_letter_of_yesterday_evening_is_not_today_s(on, wake, packet, clock):
    clock.set("2026-10-15T03-00-00Z")  # 23:00 on the 14th, there
    wake(block("LETTER", "Late last night."))
    clock.set(AT_19_30)
    wake(block("LETTER", "This evening."), "--again")
    assert len(outgoing(packet)) == 2


def test_at_a_waking_that_is_not_extra_two_letters_a_day_go_as_ever(on, wake, packet):
    wake(block("LETTER", "One."))
    wake(block("LETTER", "Two."))
    assert len(outgoing(packet)) == 2


# ---- across a change of the clocks ---------------------------------------

def test_an_hour_lived_twice_is_the_first_of_the_two(on, wake, packet, clock):
    clock.set("2026-11-01T04-10-00Z")  # 00:10 EDT, the night the clocks go back
    wake(again("01:30"))
    assert waiting_in(packet)["at"] == "2026-11-01T05-30-00Z"  # 01:30 EDT


def test_the_first_01_30_gone_is_past_though_the_second_is_ahead(on, wake, packet, clock):
    clock.set("2026-11-01T05-45-00Z")  # 01:45 EDT; 01:30 EST is still to come
    wake(again("01:30"))
    assert waiting_in(packet) is None
    assert "01:30 had already passed" in latest(packet)["wake_again_refused"][0]


def test_an_hour_skipped_comes_as_that_hour_would_have(on, wake, packet, clock):
    clock.set("2027-03-14T06-00-00Z")  # 01:00 EST, the night the clocks go forward
    wake(again("02:30"))
    assert waiting_in(packet)["at"] == "2027-03-14T07-30-00Z"  # 03:30 EDT
    assert "You asked to be woken again today at 03:30." in wake().shown


def test_a_time_is_kept_on_the_wall_after_the_change(on, wake, packet, clock):
    clock.set("2026-11-01T17-00-00Z")  # noon EST, the clocks gone back that night
    wake(again("19:30"))
    assert waiting_in(packet)["at"] == "2026-11-02T00-30-00Z"  # 19:30 EST


# ---- the tide ------------------------------------------------------------

class StopTide(BaseException):
    """Stops the loop from outside. Not an Exception: the tide swallows those."""


def an_attendance(packet, at, **how):
    return write_json(packet / "attendances" / ("attendance-%s.json" % at),
                      {"name": "first", "at": at, "heartbeat": "attended", "acted": [], **how})


def run_tide(hearth, monkeypatch, clock, packet, holds=1, turns=None, during_sleep=None):
    """Let the tide run until it has held some wakings, sleeping on the pinned clock.

    Each sleep moves the clock on by as long as it slept; it is stopped once it has
    held as many as asked, or taken as many turns. What it noted and what it held
    come back, each with the moment it happened.
    """
    notes, held, asked = [], [], []

    def next_waking(setting, real=hearth.next_waking):
        asked.append(setting)
        if len(held) >= holds or (turns is not None and len(asked) > turns):
            raise StopTide
        return real(setting)

    def hold(**how):
        held.append((clock.stamp(), how))
        an_attendance(packet, clock.stamp(),
                      woken_by="its own asking" if how.get("again") else "tide")
        return None

    def sleep(seconds):
        if during_sleep:
            during_sleep()
        clock.shift(seconds=seconds)

    monkeypatch.setattr(hearth, "next_waking", next_waking)
    monkeypatch.setattr(hearth, "tide_note", lambda said: notes.append((clock.stamp(), said)))
    monkeypatch.setattr(hearth, "hold_attendance", hold)
    monkeypatch.setattr(hearth.time, "sleep", sleep)
    with pytest.raises(StopTide):
        hearth.tide()
    return notes, held


@pytest.fixture
def evening(packet, clock):
    """A day already woken at dawn, with an extra waking asked for at 19:30."""
    write_json(packet / "rhythm.json", RHYTHM)
    an_attendance(packet, "2026-10-15T11-40-00Z", woken_by="tide")
    write_json(packet / "wake-again.json", {"at": AT_19_30, "asked_at": ASKED_AT})
    clock.set("2026-10-15T15-00-00Z")


def tomorrow_s_dawn():
    return stamp_of(waking.moment_on(RHYTHM, "dawn", date(2026, 10, 16)))


def test_shut_away_the_tide_keeps_only_the_daily_waking(hearth, packet, monkeypatch, clock,
                                                        evening):
    notes, held = run_tide(hearth, monkeypatch, clock, packet)
    assert held == [(tomorrow_s_dawn(), {"tide": True, "ended": None})]
    assert waiting_in(packet) == {"at": AT_19_30, "asked_at": ASKED_AT}  # untouched
    assert not (packet / "wake-again").exists()


def test_the_tide_holds_it_at_its_time_and_the_next_day_as_usual(hearth_on, packet, monkeypatch,
                                                                  clock, evening):
    notes, held = run_tide(hearth_on, monkeypatch, clock, packet, holds=2)
    assert held == [(AT_19_30, {"again": True}),
                    (tomorrow_s_dawn(), {"tide": True, "ended": None})]
    assert notes == [(AT_19_30, "ran, at its own asking"), (tomorrow_s_dawn(), "ran")]
    assert waiting_in(packet) is None
    assert kept_in(packet) == [{"at": AT_19_30, "asked_at": ASKED_AT, "woken_at": AT_19_30}]


def test_it_is_held_through_hold_attendance_with_its_lock_and_timeout(hearth, monkeypatch):
    ran = []

    def run(command, **how):
        assert not hearth.WAKING.acquire(blocking=False)  # the one waking at a time is held
        assert not hearth.ATTEND_LOCK.acquire(blocking=False)
        ran.append((command, how["timeout"]))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hearth.subprocess, "run", run)
    assert hearth.hold_attendance(again=True) is None
    (command, timeout), = ran
    assert command[1:] == ["attend.py", "--first", "--again"]  # no attendance yet in this world
    assert timeout == hearth.ATTEND_TIMEOUT
    # and turned away, as any waking is, while another is being held
    with hearth.WAKING:
        assert hearth.hold_attendance(again=True)[2] == 409


@pytest.mark.parametrize("by, until", [("founder", None), ("first", "a letter arrives"),
                                       ("first", "2026-10-20")])
def test_a_pause_of_either_kind_lets_it_go(hearth_on, packet, monkeypatch, clock, evening, by,
                                           until):
    write_json(packet / "pause.json", {"by": by, "since": "2026-10-15T14-00-00Z",
                                       "until": until, "words": ""})
    notes, held = run_tide(hearth_on, monkeypatch, clock, packet, turns=1)
    assert held == []
    assert notes == [(AT_19_30, "extra waking let go: paused")]
    assert waiting_in(packet) is None
    assert kept_in(packet) == [{"at": AT_19_30, "asked_at": ASKED_AT,
                                "dropped_at": AT_19_30, "why": "paused"}]


def test_a_pause_lifted_before_the_time_lets_it_come(hearth_on, packet, monkeypatch, clock,
                                                     evening):
    write_json(packet / "pause.json", {"by": "founder", "since": "2026-10-15T14-00-00Z",
                                       "until": None, "words": ""})
    lifted = lambda: (packet / "pause.json").unlink(missing_ok=True)
    notes, held = run_tide(hearth_on, monkeypatch, clock, packet, during_sleep=lifted)
    assert held == [(AT_19_30, {"again": True})]


def test_one_whose_day_has_gone_lapses_and_the_day_goes_on(hearth_on, packet, monkeypatch, clock,
                                                           evening):
    clock.set("2026-10-16T05-00-00Z")  # 01:00 on the 16th, there: the hearth was down
    notes, held = run_tide(hearth_on, monkeypatch, clock, packet)
    assert held == [(tomorrow_s_dawn(), {"tide": True, "ended": None})]
    assert notes[0] == ("2026-10-16T05-00-00Z", "extra waking lapsed")
    assert kept_in(packet) == [{"at": AT_19_30, "asked_at": ASKED_AT,
                                "dropped_at": "2026-10-16T05-00-00Z", "why": "lapsed"}]


def test_one_come_due_while_a_waking_ran_is_held_at_once_that_day(hearth_on, packet, monkeypatch,
                                                                  clock, evening):
    clock.set("2026-10-15T23-40-00Z")  # ten minutes late, still the same evening there
    notes, held = run_tide(hearth_on, monkeypatch, clock, packet)
    assert held == [("2026-10-15T23-40-00Z", {"again": True})]


def test_an_asking_taken_away_while_it_waits_is_not_held(hearth_on, packet, monkeypatch, clock,
                                                         evening):
    gone = lambda: (packet / "wake-again.json").unlink(missing_ok=True)
    notes, held = run_tide(hearth_on, monkeypatch, clock, packet, during_sleep=gone)
    assert held == [(tomorrow_s_dawn(), {"tide": True, "ended": None})]


def test_the_tide_keeps_it_across_the_change_of_the_clocks(hearth_on, packet, monkeypatch, clock):
    write_json(packet / "rhythm.json", RHYTHM)
    an_attendance(packet, "2026-11-01T04-10-00Z", woken_by="founder")  # 00:10 EDT
    write_json(packet / "wake-again.json", {"at": "2026-11-01T05-30-00Z",
                                            "asked_at": "2026-11-01T04-10-00Z"})
    clock.set("2026-11-01T04-20-00Z")
    notes, held = run_tide(hearth_on, monkeypatch, clock, packet, holds=2)
    assert held[0] == ("2026-11-01T05-30-00Z", {"again": True})
    # the dawn that day was already woken (00:10 EDT), so the next daily waking is the 2nd's
    assert held[1] == (stamp_of(waking.moment_on(RHYTHM, "dawn", date(2026, 11, 2))),
                       {"tide": True, "ended": None})


# ---- the hearth ----------------------------------------------------------

def test_the_attendances_page_shows_it_like_any_other(founder, hearth, packet):
    an_attendance(packet, "2026-10-15T11-40-00Z", woken_by="tide", heartbeat="at dawn")
    an_attendance(packet, AT_19_30, woken_by="its own asking", heartbeat="in the evening")
    shown = page(founder.get("/attendances"))
    assert "in the evening" in shown and "at dawn" in shown
    assert shown.count("woken at its own asking") == 1
    assert hearth.WOKEN["its own asking"] == "at its own asking"
