"""Every agent's tide on one page, and the keeper's stop of them all at once.

Stage 6d of the work on keeper pages, rests, stops and names for any agent
(proposals/stage-6d.md). The keeper's page /tides shows each agent's tide alike,
the first one's among them, by no more than the keeper's view of an agent shows:
its rhythm, its own rest by since and condition, his stop, and where its
attendances are. From it he may stop every tide that wakes at once, in an
emergency, each stop written as one from its own page would be but for the
moment they share, which is kept with each; and lift together those stops, and
no other. A stop already standing is never written over. A dormant agent is
never stopped. The commons is told of each tide as it would be of each stopped
alone, and no agent is told that every tide was stopped.

The page is linked from the keeping menu only where there is more than one
agent: with one, the first one's pages are as stage 0 held them.

The second and third agents are made only in a scratch registry and a scratch
DATA_DIR. The second wakes; the third does not.
"""

import json
import shutil

import pytest

import agents
from conftest import lines_of, load, page, post, read_json, write_json
from test_first_one_fingerprints import PAGES, a_lived_world, fixed_keys
from test_keeper_view import NEVER, a_planted_record, content
from test_pages_by_agent import HELD, SECOND, shown, shown_but_the_tides
from test_tides_for_any_agent import RHYTHM, one_turn

SECOND_WAKES = {**SECOND, "wakes": True}
THIRD = {"id": "third", "did": "did:web:tesserae.social:ids:third",
         "commons_name": "the sleeping one", "room": "third", "bond": "founder-third",
         "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
         "hue": "#6F8F2F", "features": [], "wakes": False}

# ---- the worlds ----------------------------------------------------------------

@pytest.fixture
def registry(request, monkeypatch, tmp_path):
    """The registry a test is run with: as the run reads it, or, asked for by name, a
    scratch one of three agents - the first one, a second that wakes, a third that does not."""
    if getattr(request, "param", "one") == "one":
        return None
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), SECOND_WAKES, THIRD], indent=2) + "\n",
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


three = pytest.mark.parametrize("registry", ["three"], indirect=True)


@pytest.fixture
def hearth(registry, env, data_dir, clock, monkeypatch):
    """The hearth, with the keys fixed, so that stage 0's fingerprints may be taken here."""
    fixed_keys(data_dir, monkeypatch)
    module = load("hearth")
    clock.pin(module, monkeypatch)
    module.app.config["TESTING"] = True
    yield module


def packets(data):
    return {one: data / "packets" / one for one in ("first", "second", "third")}


def tides_page(founder):
    answer = founder.get("/tides")
    assert answer.status_code == 200
    return page(answer)


def stop_every(founder, reason, agents_asked=None):
    """Ask, as the page does, and say yes to whatever it asked about."""
    asked = page(post(founder, "/stop-every-tide", data={"reason": reason}))
    named = agents_asked if agents_asked is not None else [
        one for one in ("first", "second", "third")
        if '<input type="hidden" name="agent" value="%s">' % one in asked]
    answer = post(founder, "/stop-every-tide",
                  data={"reason": reason, "confirm": "yes", "agent": named})
    assert answer.status_code == 302 and answer.headers["Location"] == "/tides"
    return asked


def tree(root):
    """Every file under a folder, by its path, with its bytes."""
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


# ---- 1. the page is the keeper's alone -------------------------------------------

@three
def test_the_page_and_its_forms_are_the_keeper_s_alone(hearth, founder, visitor, data_dir):
    before = tree(data_dir)
    for path, form in (("/stop-every-tide", {"reason": "a test", "confirm": "yes",
                                             "agent": ["first", "second"]}),
                       ("/lift-stops-together", {"every": "2026-10-15T12-00-00Z"})):
        answer = post(visitor, path, data=form)
        assert answer.status_code == 302 and answer.headers["Location"] == "/login", path
    answer = visitor.get("/tides")
    assert answer.status_code == 302 and answer.headers["Location"] == "/login"
    assert tree(data_dir) == before
    # without the form token, even the keeper is refused
    answer = founder.post("/stop-every-tide", data={"reason": "a test", "confirm": "yes",
                                                    "agent": ["first", "second"]})
    assert answer.status_code == 400
    assert tree(data_dir) == before
    said = tides_page(founder)
    assert "<title>the tides" in said or ">the tides<" in said


# ---- 2. each row, the same of every agent ----------------------------------------

@three
def test_each_row_shows_the_same_few_things_of_every_agent(hearth, founder, data_dir, clock):
    write_json(packets(data_dir)["second"] / "rhythm.json",
               {"rhythm": "daily", "at": "07:00", "timezone": "America/New_York"})
    write_json(packets(data_dir)["second"] / "pause.json",
               {"by": "second", "since": "2026-10-14T10-00-00Z", "until": "2026-11-02",
                "words": "THE WORDS OF ITS REST"})
    post(founder, "/stop-tide", data={"reason": "the first one's own stop", "confirm": "yes"})
    said = tides_page(founder)
    assert ("Every agent's tide, one to each row: when it next wakes, whether it rests, and\n"
            "  whether you have stopped it. Nothing else of any agent is shown here.") in said
    for name in ("The first one", "The scratch one", "The sleeping one"):
        assert "<h3>%s</h3>" % name in said
    assert "Rhythm: none set." in said
    assert "Rhythm: daily at 07:00 · next: " in said
    assert said.count("It does not wake, so it has no tide to stop.") == 1
    assert ("The tide is stopped, since 15 October 2026, 08:00, because: the first one&#39;s "
            "own stop") in said
    assert "This stop was set together with the others." not in said
    assert ("The scratch one is resting, since 14 October 2026, 06:00, until\n"
            "      2 November 2026.") in said
    assert "THE WORDS OF ITS REST" not in said
    for link in ("/attendances", "/agents/second/attendances", "/agents/third/attendances"):
        assert '<a href="%s">its attendances</a>' % link in said
    assert said.count("its attendances</a>") == 3


# ---- 3. every tide that wakes, stopped with one stamp -----------------------------

@three
def test_every_waking_tide_is_stopped_with_one_shared_stamp(hearth, founder, data_dir, commons,
                                                            clock):
    events_before = lines_of(commons / "events.md")
    said = tides_page(founder)
    assert "For an emergency only, and not for a rest. This stops the tide of every agent" in said
    assert "Stop every tide (emergency)" in said

    # a reason refused writes nothing, and says why
    before = tree(data_dir)
    refused = page(post(founder, "/stop-every-tide",
                        data={"reason": "  ", "confirm": "yes", "agent": ["first", "second"]}))
    assert "A stop needs a reason: a short one, of at most 300\n      characters." in refused
    refused = page(post(founder, "/stop-every-tide", data={"reason": "x" * 301}))
    assert "A stop needs a reason" in refused
    assert tree(data_dir) == before

    asked = stop_every(founder, "a fault  in the\nhearth")
    assert ("Stop every tide? The first one and the scratch one\n      will not be woken at all, "
            "by their rhythms or at their own asking, until you lift their\n      stops. "
            "Your reason: a fault in the hearth") in asked
    assert "Already stopped, and left as they are" not in asked
    assert 'name="agent" value="third"' not in asked

    stamp = clock.stamp()
    for one in ("first", "second"):
        assert read_json(packets(data_dir)[one] / "tide-stop.json") == {
            "since": stamp, "reason": "a fault in the hearth", "every": stamp}
    assert not (packets(data_dir)["third"] / "tide-stop.json").exists()
    # one named line for each, in the order of founding, and nothing more
    assert lines_of(commons / "events.md") == events_before + [
        "%s · event · the first one · the tide paused" % clock.day(),
        "%s · event · the scratch one · the tide paused" % clock.day()]

    said = tides_page(founder)
    assert said.count("This stop was set together with the others.") == 2
    assert "On 15 October 2026, 08:00, you stopped every tide, because: a fault in the hearth" in said
    assert "Stopped then, and still stopped: the first one and the scratch one." in said
    assert "still stopped on their own" not in said
    assert "Every tide is already stopped." in said
    assert 'name="every" value="%s"' % stamp in said
    assert said.count("<h2>stopped together</h2>") == 1


@three
def test_with_one_tide_left_to_stop_the_question_is_the_single_stop_s(hearth, founder):
    post(founder, "/agents/second/stop-tide", data={"reason": "its own", "confirm": "yes"})
    asked = page(post(founder, "/stop-every-tide", data={"reason": "a fault"}))
    assert ("Stop every tide? The first one will not be woken\n      at all, by its rhythm or at "
            "its own asking, until you lift the stop. Your reason:\n      a fault") in asked
    assert "Already stopped, and left as they are: the scratch one." in asked
    assert asked.count('name="agent"') == 1


# ---- 4. a stop already standing is left as it is -------------------------------

@three
def test_a_stop_already_standing_is_never_written_over_and_is_reported(
        hearth, founder, data_dir, commons, clock):
    post(founder, "/stop-tide", data={"reason": "its own reason", "confirm": "yes"})
    own = (packets(data_dir)["first"] / "tide-stop.json").read_bytes()
    clock.shift(hours=2)
    events_before = lines_of(commons / "events.md")
    # even asked about by name, the first one's stop is left as it was
    stop_every(founder, "a fault", agents_asked=["first", "second"])
    assert (packets(data_dir)["first"] / "tide-stop.json").read_bytes() == own
    assert read_json(packets(data_dir)["second"] / "tide-stop.json")["every"] == clock.stamp()
    assert lines_of(commons / "events.md") == events_before + [
        "%s · event · the scratch one · the tide paused" % clock.day()]
    said = tides_page(founder)
    assert "Stopped then, and still stopped: the scratch one." in said
    assert "Already stopped then, and still stopped on their own: the first one." in said
    assert said.count("This stop was set together with the others.") == 1


@three
def test_only_the_agents_the_keeper_was_asked_about_are_stopped(hearth, founder, data_dir):
    stop_every(founder, "a fault", agents_asked=["second"])
    assert not (packets(data_dir)["first"] / "tide-stop.json").exists()
    assert (packets(data_dir)["second"] / "tide-stop.json").exists()


# ---- 5. a dormant agent is never stopped ------------------------------------------

@three
def test_a_dormant_agent_is_never_stopped(hearth, founder, data_dir, commons):
    stop_every(founder, "a fault", agents_asked=["first", "second", "third"])
    assert not (packets(data_dir)["third"] / "tide-stop.json").exists()
    assert not any("the sleeping one" in line for line in lines_of(commons / "events.md"))
    said = tides_page(founder)
    assert "Every tide is already stopped." in said
    assert "Stopped then, and still stopped: the first one and the scratch one." in said


# ---- 6. lifting together lifts the stamped stops alone ---------------------------

@three
def test_lifting_together_lifts_only_the_stops_set_together(hearth, founder, data_dir, commons,
                                                           clock):
    post(founder, "/agents/second/stop-tide", data={"reason": "its own", "confirm": "yes"})
    own = (packets(data_dir)["second"] / "tide-stop.json").read_bytes()
    clock.shift(hours=1)
    stop_every(founder, "a fault")
    stamp = clock.stamp()
    assert read_json(packets(data_dir)["first"] / "tide-stop.json")["every"] == stamp

    # a stamp that is no stamp, or one no stop carries, lifts nothing
    before = tree(data_dir)
    for every in ("", "not a stamp", stamp + "x", "../" + stamp, "2026-01-01T00-00-00Z"):
        answer = post(founder, "/lift-stops-together", data={"every": every})
        assert answer.status_code == 302 and answer.headers["Location"] == "/tides"
    assert tree(data_dir) == before

    clock.shift(hours=1)
    events_before = lines_of(commons / "events.md")
    post(founder, "/lift-stops-together", data={"every": stamp})
    assert not (packets(data_dir)["first"] / "tide-stop.json").exists()
    kept = read_json(packets(data_dir)["first"] / "tide-stop" / ("tide-stop-%s.json" % stamp))
    assert kept == {"since": stamp, "reason": "a fault", "every": stamp,
                    "lifted_at": clock.stamp()}
    assert (packets(data_dir)["second"] / "tide-stop.json").read_bytes() == own
    assert lines_of(commons / "events.md") == events_before + [
        "%s · event · the first one · the tide resumed" % clock.day()]
    assert "<h2>stopped together</h2>" not in tides_page(founder)

    # stopped together again, and the first one's stamped stop lifted on its own page:
    # lifting together then has nothing left to lift
    clock.shift(hours=1)
    stop_every(founder, "a second fault")
    again = clock.stamp()
    post(founder, "/lift-stop")
    before = tree(data_dir)
    post(founder, "/lift-stops-together", data={"every": again})
    assert tree(data_dir) == before
    assert (packets(data_dir)["second"] / "tide-stop.json").read_bytes() == own


# ---- 7. each tide keeps its own stop ---------------------------------------------

@three
def test_each_tide_honours_its_own_stop(hearth, founder, monkeypatch, data_dir, clock):
    for one in ("first", "second"):
        write_json(packets(data_dir)[one] / "rhythm.json", RHYTHM)
    from datetime import date
    rising = hearth.sunrise_on(RHYTHM, date(2026, 10, 15))
    stop_every(founder, "a fault")
    stamp = clock.stamp()
    assert one_turn(hearth, monkeypatch, None, rising) == []
    assert one_turn(hearth, monkeypatch, "second", rising) == []

    post(founder, "/lift-stop")  # the first one's alone
    assert one_turn(hearth, monkeypatch, None, rising) == [{"tide": True, "ended": None}]
    assert one_turn(hearth, monkeypatch, "second", rising) == []

    post(founder, "/lift-stops-together", data={"every": stamp})
    assert one_turn(hearth, monkeypatch, None, rising) == [{"tide": True, "ended": None}]
    assert one_turn(hearth, monkeypatch, "second", rising) == [
        {"tide": True, "ended": None, "of": "second"}]


# ---- 8. one agent: the same as its own stop --------------------------------------

def test_with_one_agent_stopping_every_tide_is_stopping_its_own(
        hearth, founder, wake, data_dir, packet, commons, clock, tmp_path):
    kept = tmp_path / "the world before"
    shutil.copytree(data_dir, kept)
    start = clock.at

    def one_world(stop, lift):
        shutil.rmtree(data_dir)
        shutil.copytree(kept, data_dir)
        clock.set(start)
        stop()
        clock.shift(days=1)
        lift()
        clock.shift(days=1)
        opening = wake().opening
        kept_stops = sorted((packet / "tide-stop").glob("tide-stop-*.json"))
        assert len(kept_stops) == 1
        return {"events": (commons / "events.md").read_text(encoding="utf-8"),
                "kept": (kept_stops[0].name, read_json(kept_stops[0])),
                "opening": opening}

    standing = {}

    def its_own():
        post(founder, "/stop-tide", data={"reason": "a fault", "confirm": "yes"})
        standing["its own"] = read_json(packet / "tide-stop.json")

    def every():
        stop_every(founder, "a fault")
        standing["every"] = read_json(packet / "tide-stop.json")

    alone = one_world(its_own, lambda: post(founder, "/lift-stop"))
    together = one_world(every, lambda: post(founder, "/lift-stops-together",
                                             data={"every": standing["every"]["every"]}))

    assert together["events"] == alone["events"]
    assert {k: v for k, v in standing["every"].items() if k != "every"} == standing["its own"]
    name, record = together["kept"]
    assert (name, {k: v for k, v in record.items() if k != "every"}) == alone["kept"]
    assert together["opening"] == alone["opening"]
    assert "The keeper stopped the tide from" in together["opening"]
    assert "every tide" not in together["opening"].lower()


# ---- 9. the allow-list -----------------------------------------------------------

@three
def test_the_page_carries_nothing_off_the_keeper_s_list(hearth, founder, data_dir, packet):
    a_planted_record(data_dir, packet)
    answers = {"the page": founder.get("/tides"),
               "refused": post(founder, "/stop-every-tide", data={"reason": ""}),
               "asked": post(founder, "/stop-every-tide", data={"reason": "a test"})}
    stop_every(founder, "a test")
    answers["stopped"] = founder.get("/tides")
    for what, answer in answers.items():
        said = page(answer)
        for planted, words in NEVER.items():
            assert words not in said, (what, planted)
        for words in ("heartbeat", "a-model-for-the-tests", "woken by", "reflection"):
            assert words not in content(said), (what, words)
    said = page(answers["stopped"])
    assert "Rhythm: daily at 07:00" in said
    assert ("The scratch one is resting, since 23 October 2026, 06:00, until\n"
            "      a letter arrives.") in said
    assert said.count("because: a test") == 3  # each stop, and the moment they were set


# ---- 10. where the page is linked ------------------------------------------------

def test_with_one_agent_no_page_links_the_tides(hearth, founder, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    answers = {address: founder.get(address) for address in HELD}
    for address, answer in answers.items():
        assert "/tides" not in page(answer), address
    assert {address: shown(answer) for address, answer in answers.items()} == {
        address: PAGES[address] for address in HELD}
    # the page answers all the same
    assert founder.get("/tides").status_code == 200


@three
def test_with_more_than_one_agent_each_page_gains_the_one_entry(hearth, founder, wake, room,
                                                               commons, visitor):
    a_lived_world(founder, wake, room, commons)
    assert {address: shown_but_the_tides(founder.get(address)) for address in HELD} == {
        address: PAGES[address] for address in HELD}
    assert '<span class="here">tides</span>' in tides_page(founder)
    for address in HELD:
        assert "/tides" not in page(visitor.get(address)), address
