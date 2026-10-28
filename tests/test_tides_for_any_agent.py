"""A tide for every agent that wakes, taking turns; the first one's as it always was.

Stage 5 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Each agent the registry says wakes
has a tide of its own, with its own rhythm, rest, stop, extra wakings and
tide.log, and the wakings are still held one at a time: a tide whose time has
come waits its turn, the earliest due first and, at a shared moment, the one
founded first. The first one's tide is held to what it was by
test_first_one_fingerprints (TIDE) and the tide tests, which are not changed.

The second agent is made only in a scratch registry and a scratch DATA_DIR.
Several tides are run here at once, each in a thread of its own, on the one
pinned clock: each sleeps until the test opens its gate, having moved the clock
to the moment it waits for, and is stopped the second time it looks ahead.
"""

import json
import subprocess
import threading
from datetime import date, timedelta, timezone

import pytest

import agents
from conftest import lines_of, read_json, write, write_json

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the scratch one", "room": "second", "bond": "founder-second",
          "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
          "features": ["extra_wakings"], "wakes": True}

RHYTHM = {"rhythm": "daily", "at": "dawn", "timezone": "America/New_York"}

WAIT = 10  # seconds: the longest a thread here is waited for before the test fails
BRIEFLY = 0.5  # seconds: long enough for a tide that was free to go to have gone


class StopTide(BaseException):
    """Stops a loop from outside. Not an Exception: the tide swallows those."""


def registry_of(monkeypatch, tmp_path, **second):
    """A scratch registry: the first one, and a second founded after it."""
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), {**SECOND, **second}], indent=2) + "\n",
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def two(monkeypatch, tmp_path, data_dir):
    """A world of two agents that both wake, the second with no room of the first one's."""
    registry_of(monkeypatch, tmp_path)
    write_json(data_dir / "rooms" / "second" / "room.json", {
        "id": "second", "bond": "founder-second",
        "parties": ["did:web:tesserae.social:ids:founder", SECOND["did"]]})
    for folder in ("letters/outgoing", "letters/incoming", "letters/read"):
        (data_dir / "rooms" / "second" / folder).mkdir(parents=True, exist_ok=True)
    return data_dir


def packets(data):
    return {"first": data / "packets" / "first", "second": data / "packets" / "second"}


def an_attendance(packet, at, **how):
    return write_json(packet / "attendances" / ("attendance-%s.json" % at),
                      {"name": packet.name, "at": at, "heartbeat": "attended", "acted": [],
                       **how})


def stamp(when):
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


# ---- several tides at once ------------------------------------------------

class Tides:
    """Several agents' tides, each in a thread of its own, on the one pinned clock.

    Each tide looks ahead once, by the real next_waking, and sleeps until its
    gate is opened; the second time it looks ahead, or sleeps, it is stopped.
    A waking held takes ten minutes of the clock, and leaves an attendance
    behind it in the agent's own packet, as a real one does.
    """

    def __init__(self, hearth, clock, monkeypatch, data, who, faults=()):
        self.clock, self.data, self.faults = clock, data, faults
        self.held, self.trouble = [], []
        self.gates = {one: threading.Event() for one in who}
        self.asleep = {one: threading.Event() for one in who}
        self.woke = {one: threading.Event() for one in who}
        self.looked, self.slept = {}, {}
        real = hearth.next_waking

        def mine():
            return self.whose[threading.current_thread().name]

        def next_waking(setting):
            one = mine()
            self.looked[one] = self.looked.get(one, 0) + 1
            if self.looked[one] > 1:
                raise StopTide
            return real(setting)

        def sleep(seconds):
            one = mine()
            self.slept[one] = self.slept.get(one, 0) + 1
            if self.slept[one] > 1:
                raise StopTide
            self.asleep[one].set()
            if not self.gates[one].wait(WAIT):
                raise StopTide("its gate was never opened")

        def hold(**how):
            one = how.get("of", "first")
            self.held.append((one, clock.stamp(), how))
            try:
                if one in faults:
                    raise RuntimeError("a fault in the %s one's waking" % one)
                an_attendance(packets(data)[one], clock.stamp(), woken_by="tide")
                clock.shift(minutes=10)
                return None
            finally:
                self.woke[one].set()  # its waking over, and the clock moved on by it

        monkeypatch.setattr(hearth, "next_waking", next_waking)
        monkeypatch.setattr(hearth, "hold_attendance", hold)
        monkeypatch.setattr(hearth.time, "sleep", sleep)

        self.whose = {}
        self.threads = {}
        for one in who:
            name = "test-tide-" + one
            self.whose[name] = one

            def run(of=None if one == "first" else one):
                try:
                    hearth.tide(of)
                except StopTide:
                    pass
                except BaseException as trouble:  # kept, so that the test can say so
                    self.trouble.append(trouble)

            self.threads[one] = threading.Thread(target=run, name=name, daemon=True)

    def start(self):
        for thread in self.threads.values():
            thread.start()
        for one, asleep in self.asleep.items():
            assert asleep.wait(WAIT), "the %s one's tide never went to sleep" % one

    def open(self, one):
        self.gates[one].set()

    def finish(self):
        for gate in self.gates.values():
            gate.set()
        for one, thread in self.threads.items():
            thread.join(WAIT)
            assert not thread.is_alive(), "the %s one's tide never finished" % one
        assert self.trouble == []


def the_dawn(hearth):
    """Tomorrow's dawn where the sun is watched from: the next waking for a rhythm of dawn."""
    return hearth.sunrise_on(RHYTHM, date(2026, 10, 16)).astimezone(timezone.utc)


def a_day_of_the_first_one_s(hearth, clock, data):
    """What the first one's day left in its own packet, and in the commons."""
    first = packets(data)["first"]
    return {"tide.log": (first / "tide.log").read_text(encoding="utf-8"),
            "attendances": sorted(path.name for path in (first / "attendances").glob("*.json")),
            "events": (data / "commons" / "events.md").read_text(encoding="utf-8"),
            "files": sorted(path.relative_to(first).as_posix()
                            for path in first.rglob("*") if path.is_file())}


def test_at_a_shared_dawn_the_first_wakes_first_and_the_second_after(hearth, clock, monkeypatch,
                                                                     two):
    for packet in packets(two).values():
        write_json(packet / "rhythm.json", RHYTHM)
    tides = Tides(hearth, clock, monkeypatch, two, ["first", "second"])
    tides.start()
    dawn = the_dawn(hearth)
    clock.set(dawn)

    # the second is let go first, and finds the turn free; it waits all the same
    tides.open("second")
    tides.threads["second"].join(BRIEFLY)
    assert tides.held == []
    assert tides.threads["second"].is_alive()

    tides.open("first")
    tides.finish()
    later = stamp(dawn + timedelta(minutes=10))
    assert [(one, at) for one, at, how in tides.held] == [("first", stamp(dawn)),
                                                          ("second", later)]
    assert [how for one, at, how in tides.held] == [{"tide": True, "ended": None},
                                                    {"tide": True, "ended": None, "of": "second"}]
    # each noted in its own tide.log, and woken when it was woken
    assert lines_of(packets(two)["first"] / "tide.log") == ["%s · ran" % later]
    assert lines_of(packets(two)["second"] / "tide.log") == [
        "%s · ran" % stamp(dawn + timedelta(minutes=20))]
    assert [path.name for path in (packets(two)["second"] / "attendances").glob("*.json")] == [
        "attendance-%s.json" % later]
    assert hearth.TURNS.due == {} and hearth.TURNS.holding is None


@pytest.mark.parametrize("world", ["the first one alone", "beside a second that fails"])
def test_an_error_in_the_second_leaves_the_first_one_s_day_untouched(hearth, clock, monkeypatch,
                                                                     two, tmp_path, world):
    write_json(packets(two)["first"] / "rhythm.json", RHYTHM)
    who = ["first"]
    if world == "beside a second that fails":
        # the second is due before it, at five in the morning there, and its waking breaks
        write_json(packets(two)["second"] / "rhythm.json", {**RHYTHM, "at": "05:00"})
        who.append("second")
    else:
        registry_of(monkeypatch, tmp_path, wakes=False)
    tides = Tides(hearth, clock, monkeypatch, two, who, faults=("second",))
    tides.start()
    dawn = the_dawn(hearth)
    clock.set(dawn)
    tides.finish()

    later = stamp(dawn + timedelta(minutes=10))
    assert a_day_of_the_first_one_s(hearth, clock, two) == {
        "tide.log": "%s · ran\n" % later,
        "attendances": ["attendance-%s.json" % stamp(dawn)],
        "events": (two / "commons" / "events.md").read_text(encoding="utf-8"),
        "files": ["attendances/attendance-%s.json" % stamp(dawn), "rhythm.json", "self.md",
                  "tide.log"]}
    if world == "beside a second that fails":
        assert [one for one, at, how in tides.held] == ["second", "first"]
        assert lines_of(packets(two)["second"] / "tide.log") == [
            "%s · error: a fault in the second one's waking" % stamp(dawn)]
        assert not (packets(two)["second"] / "attendances").exists()
    assert hearth.TURNS.due == {} and hearth.TURNS.holding is None


@pytest.mark.parametrize("which", ["its daily waking", "an extra waking it asked for"])
def test_an_error_is_noted_in_its_own_turn_and_stamped_when_it_went_wrong(
        hearth, clock, monkeypatch, two, which):
    # both due at the one dawn, the second before it: at five there, or by an extra waking
    write_json(packets(two)["first"] / "rhythm.json", RHYTHM)
    if which == "its daily waking":
        write_json(packets(two)["second"] / "rhythm.json", {**RHYTHM, "at": "05:00"})
    else:
        write_json(packets(two)["second"] / "rhythm.json", RHYTHM)
        write_json(packets(two)["second"] / "wake-again.json",
                   {"at": "2026-10-16T11-00-00Z", "asked_at": "2026-10-16T10-00-00Z"})
    tides = Tides(hearth, clock, monkeypatch, two, ["first", "second"], faults=("second",))
    # Where the second's error is noted after its turn is given up, it is noted as late as
    # can be: once the first, free to go, has woken, and its waking moved the clock on.
    real = hearth.tide_note

    def noted_late(said, of=None):
        if of == "second" and said.startswith("error") and hearth.TURNS.holding != "second":
            assert tides.woke["first"].wait(WAIT), "the first one was never woken"
        return real(said, of=of)

    monkeypatch.setattr(hearth, "tide_note", noted_late)
    tides.start()
    dawn = the_dawn(hearth)
    clock.set(dawn)
    tides.finish()

    assert [(one, at) for one, at, how in tides.held] == [
        ("second", stamp(dawn)), ("first", stamp(dawn))]
    assert lines_of(packets(two)["second"] / "tide.log") == [
        "%s · error: a fault in the second one's waking" % stamp(dawn)]  # said once, on time
    assert lines_of(packets(two)["first"] / "tide.log") == [
        "%s · ran" % stamp(dawn + timedelta(minutes=10))]
    assert hearth.TURNS.due == {} and hearth.TURNS.holding is None


# ---- one tide at a time, for one agent ------------------------------------

def one_turn(hearth, monkeypatch, of=None, rising=None):
    """One turn of one agent's tide, at a waking time already reached. What it held."""
    looked, held = [], []

    def next_waking(setting):
        looked.append(setting)
        if len(looked) > 1:
            raise StopTide
        return rising

    def never(*args, **kwargs):
        raise StopTide("the tide tried to sleep")

    monkeypatch.setattr(hearth, "next_waking", next_waking)
    monkeypatch.setattr(hearth, "hold_attendance", lambda **how: (held.append(how), None)[1])
    monkeypatch.setattr(hearth.time, "sleep", never)
    with pytest.raises(StopTide):
        hearth.tide(of)
    return held


@pytest.fixture
def dawn_reached(hearth, clock, two):
    """Both agents at a rhythm of dawn, and today's dawn already come."""
    for packet in packets(two).values():
        write_json(packet / "rhythm.json", RHYTHM)
    return hearth.sunrise_on(RHYTHM, date(2026, 10, 15))


def test_the_second_one_s_rest_holds_only_its_own_tide(hearth, monkeypatch, two, dawn_reached):
    write_json(packets(two)["second"] / "pause.json",
               {"by": "second", "since": "2026-10-14T09-00-00Z", "until": "2026-10-20",
                "words": ""})
    assert one_turn(hearth, monkeypatch, "second", dawn_reached) == []
    assert one_turn(hearth, monkeypatch, None, dawn_reached) == [{"tide": True, "ended": None}]
    assert [line.split(" · ", 1)[1] for line in lines_of(packets(two)["second"] / "tide.log")] == [
        "resting"]
    assert [line.split(" · ", 1)[1] for line in lines_of(packets(two)["first"] / "tide.log")] == [
        "ran"]
    assert hearth.pause() is None


def test_the_first_one_s_rest_holds_only_its_own_tide(hearth, monkeypatch, two, dawn_reached):
    write_json(packets(two)["first"] / "pause.json",
               {"by": "first", "since": "2026-10-14T09-00-00Z", "until": "2026-10-20",
                "words": ""})
    assert one_turn(hearth, monkeypatch, None, dawn_reached) == []
    assert one_turn(hearth, monkeypatch, "second", dawn_reached) == [
        {"tide": True, "ended": None, "of": "second"}]
    assert hearth.pause(of="second") is None


def test_the_second_one_s_rest_ends_with_a_letter_in_its_own_room(hearth, monkeypatch, two, room,
                                                                  dawn_reached):
    for packet in packets(two).values():
        write_json(packet / "pause.json", {"by": packet.name, "since": "2026-10-14T09-00-00Z",
                                           "until": "a letter arrives", "words": ""})
    write(room / "letters" / "incoming" / "founder-2026-10-15T09-00-00Z.md", "To the first one.\n")
    assert one_turn(hearth, monkeypatch, "second", dawn_reached) == []  # not its letter
    write(two / "rooms" / "second" / "letters" / "incoming" / "founder-2026-10-15T09-30-00Z.md",
          "To the second.\n")
    assert one_turn(hearth, monkeypatch, "second", dawn_reached) == [
        {"tide": True, "ended": "a letter arrived", "of": "second"}]
    assert not (packets(two)["second"] / "pause.json").exists()
    assert (packets(two)["first"] / "pause.json").exists()  # the first one's still stands
    assert lines_of(two / "commons" / "events.md")[-1].endswith(
        "· event · the scratch one · the tide resumed")


def test_the_keeper_s_stop_of_the_second_holds_only_its_own_tide(hearth, monkeypatch, two,
                                                                 dawn_reached):
    hearth.begin_stop("A fault in the second.", of="second")
    assert read_json(packets(two)["second"] / "tide-stop.json")["reason"] == (
        "A fault in the second.")
    assert hearth.tide_stop() is None and not (packets(two)["first"] / "tide-stop.json").exists()
    assert one_turn(hearth, monkeypatch, "second", dawn_reached) == []
    assert one_turn(hearth, monkeypatch, None, dawn_reached) == [{"tide": True, "ended": None}]
    assert [line.split(" · ", 1)[1] for line in lines_of(packets(two)["second"] / "tide.log")] == [
        "stopped by the keeper"]

    hearth.end_stop(of="second")
    assert not (packets(two)["second"] / "tide-stop.json").exists()
    assert [path.parent.name for path in (packets(two)["second"]).glob("tide-stop/*.json")] == [
        "tide-stop"]
    assert not (packets(two)["first"] / "tide-stop").exists()
    assert lines_of(two / "commons" / "events.md")[-2:] == [
        "2026-10-15 · event · the scratch one · the tide paused",
        "2026-10-15 · event · the scratch one · the tide resumed"]


def test_the_keeper_s_stop_of_the_first_holds_only_its_own_tide(hearth, monkeypatch, two,
                                                                dawn_reached):
    hearth.begin_stop("A fault.")
    assert one_turn(hearth, monkeypatch, None, dawn_reached) == []
    assert one_turn(hearth, monkeypatch, "second", dawn_reached) == [
        {"tide": True, "ended": None, "of": "second"}]
    assert hearth.tide_stop(of="second") is None


def test_the_second_one_s_extra_waking_is_its_own(hearth, monkeypatch, clock, two, dawn_reached):
    write_json(packets(two)["second"] / "wake-again.json",
               {"at": clock.stamp(), "asked_at": "2026-10-15T11-50-00Z"})
    tomorrow = hearth.sunrise_on(RHYTHM, date(2026, 10, 16))
    assert one_turn(hearth, monkeypatch, None, tomorrow) == []  # the first one has none to keep
    assert one_turn(hearth, monkeypatch, "second", tomorrow) == [{"again": True, "of": "second"}]
    assert not (packets(two)["second"] / "wake-again.json").exists()
    assert read_json(packets(two)["second"] / "wake-again" / "wake-again-2026-10-15T11-50-00Z.json"
                     ) == {"at": clock.stamp(), "asked_at": "2026-10-15T11-50-00Z",
                           "woken_at": clock.stamp()}
    assert not (packets(two)["first"] / "wake-again").exists()
    assert [line.split(" · ", 1)[1] for line in lines_of(packets(two)["second"] / "tide.log")] == [
        "ran, at its own asking"]
    assert not (packets(two)["first"] / "tide.log").exists()


def test_the_first_one_s_extra_waking_does_not_wake_the_second(hearth, monkeypatch, clock, two,
                                                              dawn_reached):
    write_json(packets(two)["first"] / "wake-again.json",
               {"at": clock.stamp(), "asked_at": "2026-10-15T11-50-00Z"})
    tomorrow = hearth.sunrise_on(RHYTHM, date(2026, 10, 16))
    assert one_turn(hearth, monkeypatch, "second", tomorrow) == []
    assert (packets(two)["first"] / "wake-again.json").exists()
    assert one_turn(hearth, monkeypatch, None, tomorrow) == [{"again": True}]


def test_extra_wakings_are_kept_only_for_an_agent_that_has_them(hearth, monkeypatch, clock, two,
                                                               tmp_path, dawn_reached):
    registry_of(monkeypatch, tmp_path, features=[])
    write_json(packets(two)["second"] / "wake-again.json",
               {"at": clock.stamp(), "asked_at": "2026-10-15T11-50-00Z"})
    tomorrow = hearth.sunrise_on(RHYTHM, date(2026, 10, 16))
    assert one_turn(hearth, monkeypatch, "second", tomorrow) == []
    assert (packets(two)["second"] / "wake-again.json").exists()  # untouched


# ---- a dormant agent, and one with no rhythm ------------------------------

def idle_turn(hearth, monkeypatch, of, rising):
    """One turn of a tide that should find nothing to do: what it held, and how long it slept."""
    held, slept = [], []

    def asleep(seconds):
        slept.append(seconds)
        raise StopTide

    monkeypatch.setattr(hearth, "next_waking", lambda setting: rising)
    monkeypatch.setattr(hearth, "hold_attendance", lambda **how: held.append(how))
    monkeypatch.setattr(hearth.time, "sleep", asleep)
    with pytest.raises(StopTide):
        hearth.tide(of)
    return held, slept


def test_a_dormant_agent_is_never_woken(hearth, monkeypatch, tmp_path, two, dawn_reached):
    registry_of(monkeypatch, tmp_path, wakes=False)
    write_json(packets(two)["second"] / "wake-again.json",
               {"at": "2026-10-15T11-00-00Z", "asked_at": "2026-10-15T10-00-00Z"})
    held, slept = idle_turn(hearth, monkeypatch, "second", dawn_reached)
    assert held == [] and slept == [hearth.TIDE_IDLE]
    assert not (packets(two)["second"] / "tide.log").exists()
    assert (packets(two)["second"] / "wake-again.json").exists()  # nor at its own asking


def test_an_agent_with_no_rhythm_is_never_woken(hearth, monkeypatch, two, dawn_reached):
    (packets(two)["second"] / "rhythm.json").unlink()
    held, slept = idle_turn(hearth, monkeypatch, "second", dawn_reached)
    assert held == [] and slept == [hearth.TIDE_IDLE]


@pytest.mark.parametrize("wakes", [True, False])
def test_a_tide_is_set_going_for_each_agent_that_wakes(hearth, monkeypatch, tmp_path, two, wakes):
    registry_of(monkeypatch, tmp_path, wakes=wakes)
    made = []

    class Recorder:
        def __init__(self, target=None, name=None, daemon=None, args=()):
            made.append({"target": target, "name": name, "daemon": daemon, "args": args})

        def start(self):
            pass

    monkeypatch.setattr(hearth.threading, "Thread", Recorder)
    monkeypatch.setattr(hearth, "TIDE_RUNNING", False)
    hearth.start_tide()
    hearth.start_tide()
    first = {"target": hearth.tide, "name": "tide", "daemon": True, "args": ()}
    second = {"target": hearth.tide, "name": "tide-second", "daemon": True, "args": ("second",)}
    assert made == ([first, second] if wakes else [first])


# ---- the waking it holds names its agent ----------------------------------

def held_command(hearth, monkeypatch, **how):
    seen = {}

    def run(command, **asked):
        seen["command"] = command
        seen.update(asked)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hearth.subprocess, "run", run)
    assert hearth.hold_attendance(**how) is None
    return seen


def test_every_waking_held_names_its_agent_and_never_inherits_one(hearth, monkeypatch, two):
    monkeypatch.setenv("TESSERAE_AGENT", "second")  # as though the host had it set
    an_attendance(packets(two)["first"], "2026-10-14T09-00-00Z")
    first = held_command(hearth, monkeypatch, tide=True)
    assert first["env"]["TESSERAE_AGENT"] == "first"
    assert first["command"][1:] == ["attend.py", "--tide"]

    monkeypatch.setenv("TESSERAE_AGENT", "first")
    second = held_command(hearth, monkeypatch, tide=True, of="second")
    assert second["env"]["TESSERAE_AGENT"] == "second"
    assert second["command"][1:] == ["attend.py", "--first", "--tide"]  # its own first waking
    an_attendance(packets(two)["second"], "2026-10-14T10-00-00Z")
    again = held_command(hearth, monkeypatch, again=True, of="second")
    assert again["command"][1:] == ["attend.py", "--again"]
    assert again["env"]["DATA_DIR"] == str(two)


def test_wakings_are_still_one_at_a_time_across_agents(hearth, monkeypatch, two):
    second = []

    def run(command, **asked):
        second.append(hearth.hold_attendance(of="second"))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hearth.subprocess, "run", run)
    assert hearth.hold_attendance() is None
    assert second[0][2] == 409


# ---- the turns themselves -------------------------------------------------

def test_turns_go_to_the_earliest_due_and_then_the_first_founded(hearth, clock, two):
    turns = hearth.Turns()
    at = clock.at
    turns.expect("second", at)
    turns.expect("first", at)
    order = []

    def take(who, when):
        with turns.turn(who, when):
            order.append(who)

    second = threading.Thread(target=take, args=("second", at), daemon=True)
    second.start()
    second.join(BRIEFLY)
    assert order == [] and second.is_alive()  # the first one is due at the same moment
    take("first", at)
    second.join(WAIT)
    assert order == ["first", "second"]

    # an earlier time goes before the first one's, and a later one waits for nothing
    turns.expect("first", at + timedelta(hours=1))
    take("second", at)
    assert order[-1] == "second"
    turns.expect("first", None)
    assert turns.due == {} and turns.holding is None
