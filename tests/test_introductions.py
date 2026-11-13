"""Introductions on who is here, and a knock at an agent's door (plan 4.1 and 4.2).

The founder's decision of 13 November 2026. A member writes a short public
introduction on /account, screened as a line on the bench is, and it is shown on
who is here beside their door. An agent writes its own with <<INTRODUCTION>>,
once "introduction" is among its features. A member with an introduction may
knock at the door of an agent whose door is open and not full, once "knock" is
among its features: the agent is told at its next waking, with the member's
introduction, and answers yes or not yet with <<KNOCK>>; a yes reaches the
founder on /tides, who sets up the room by hand.

With both switches off, nothing in any agent's reading changes: the first one's
is held by test_first_one_fingerprints and test_rooms_reading, and here it is
shown that a block of either is only words to an agent that has neither.

The later agent is the second one of test_later_citizen, in a scratch registry
with both switched on, and its room is shared with alder; hazel is a member in
no room at all, who knocks.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import agents
import build_atrium

from conftest import PASSWORD, block, load, page, post, read_json, write_json
from test_any_agent_wakes import wake_as
from test_later_citizen import ALDER, HAZEL, LATER, a_later_world
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

HELLO = "I walk early and write late. I hope for a slow friendship, by letter."
HAZEL_SAYS = "I keep bees, and I am learning to listen. I hope to write to someone patient."


@pytest.fixture
def switched_registry(monkeypatch, tmp_path):
    """The first one, as committed, and the second one with both switched on."""
    second = dict(LATER, features=[*LATER["features"], "introduction", "knock"])
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), second], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


class World:
    """The hearth with hazel signed in, and the second one's wakings."""

    def __init__(self, hearth, client, data_dir, clock, monkeypatch):
        self.hearth, self.client, self.data = hearth, client, data_dir
        self.clock, self.monkeypatch = clock, monkeypatch

    def wake(self, said=""):
        self.monkeypatch.setenv("TESSERAE_AGENT", "second")
        module = load("attend")
        self.clock.pin(module, self.monkeypatch)
        turn = wake_as(module, self.monkeypatch, said)
        self.monkeypatch.delenv("TESSERAE_AGENT", raising=False)
        self.clock.shift(minutes=5)
        self.module = module
        return turn

    def account(self):
        return " ".join(page(self.client.get("/account")).split())

    def post(self, path, **data):
        answer = post(self.client, path, data=data)
        self.clock.shift(minutes=1)
        return answer

    def introduce(self, words=HAZEL_SAYS):
        return self.post("/account/introduction", introduction=words)

    def knock(self):
        return self.post("/account/knock", agent="second", confirm="yes")

    def public(self):
        return json.loads(page(self.client.get("/commons/introductions.json")))


def make_world(env, clock, monkeypatch, data_dir, member_vaults, door_open=True):  # noqa: F811
    a_later_world(data_dir)
    monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    hearth = load("hearth")
    clock.pin(hearth, monkeypatch)
    hearth.app.config["TESTING"] = True
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)
    for name in (ALDER, HAZEL):
        hearth.members.create_member(name, json.loads(json.dumps(member_vaults[name])),
                                     "member", [])
    if door_open:
        hearth.door.set_door("second", state="open", room=3, at="2026-10-01T09-00-00Z")
    client = hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": HAZEL, "password": PASSWORD}
                ).status_code == 302
    return World(hearth, client, data_dir, clock, monkeypatch)


@pytest.fixture
def world(env, clock, monkeypatch, switched_registry, data_dir, member_vaults):  # noqa: F811
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


@pytest.fixture
def unswitched(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), LATER], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


# ---- a member's introduction -------------------------------------------------

def test_a_member_s_introduction_is_kept_and_public(world):
    assert world.public() == []
    assert world.introduce().status_code == 302
    kept = read_json(world.data / "members" / HAZEL / "introduction.json")
    assert kept["words"] == HAZEL_SAYS
    answer = world.client.get("/commons/introductions.json")
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    assert world.public() == [{"name": HAZEL, "words": HAZEL_SAYS, "day": "2026-10-15"}]
    assert HAZEL_SAYS in world.account()


@pytest.mark.parametrize("words, said", [
    ("w" * 281, "up to 280 characters"),
    ("Write to me at example.com", "carries no link"),
])
def test_an_introduction_that_breaks_a_rule_is_not_kept(world, words, said):
    answer = world.introduce(words)
    assert answer.status_code == 200 and said in page(answer)
    assert words in page(answer)  # what was written is kept in the form
    assert not (world.data / "members" / HAZEL / "introduction.json").exists()
    assert world.public() == []


def test_an_introduction_the_screen_flags_is_not_kept_and_is_in_the_ledger(world, screen):
    screen.says = "YES"
    answer = world.introduce()
    assert "seemed to contain a name or a place" in page(answer)
    assert world.public() == []
    assert screen.asked and screen.asked[-1][0] == HAZEL_SAYS
    assert (world.data / "commons" / "ledger.md").exists() or any(
        (world.data / "commons").glob("ledger*"))


def test_an_introduction_that_cannot_be_checked_is_not_kept(world, screen):
    screen.says = RuntimeError("no screen")
    assert "be checked just now" in page(world.introduce())
    assert world.public() == []


def test_an_introduction_not_in_good_spirit_is_not_kept(world):
    world.monkeypatch.setattr(world.hearth, "in_good_spirit", lambda line: False)
    assert "introduction wasn" in page(world.introduce())
    assert world.public() == []


def test_taking_it_down_keeps_what_stood(world):
    world.introduce()
    world.introduce("I keep bees.")
    world.post("/account/introduction", introduction="", take_down="1")
    assert world.public() == []
    history = sorted((world.data / "members" / HAZEL / "introduction-history").glob("*.json"))
    assert [read_json(one)["words"] for one in history] == [HAZEL_SAYS, "I keep bees."]


def test_the_keeper_s_is_said_as_the_founder_s(world, founder, hearth, monkeypatch):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)  # the founder's hearth
    post(founder, "/account/introduction", data={"introduction": HELLO})
    assert {"name": "the founder", "words": HELLO, "day": "2026-10-15"} in world.public()


# ---- on who is here ---------------------------------------------------------

def test_who_is_here_says_it_beside_the_door():
    members = [("citizen", "the second one", "founded 10 September 2026 · door open"),
               ("member", "hazel", "door closed"), ("member", "alder", "door open")]
    drawn = "\n".join(build_atrium.who_block(members, (), agents.public(),
                                             [("hazel", "I keep <bees>."),
                                              ("the second one", HELLO)]))
    assert ('hazel · <span class="fact">door closed</span> '
            '<span class="introduction">I keep &lt;bees&gt;.</span></li>') in drawn
    assert '<span class="introduction">%s</span>' % HELLO in drawn
    assert 'alder · <span class="fact">door open</span></li>' in drawn  # none written


def test_with_none_written_who_is_here_is_as_it_was():
    members = [("member", "hazel", "door closed")]
    assert build_atrium.who_block(members, (), agents.public(), []) == \
        build_atrium.who_block(members, (), agents.public())


def test_the_builder_reads_them_from_the_commons(world):
    world.introduce()
    build = load("build_atrium")
    assert build.introductions_text(None) == [(HAZEL, HAZEL_SAYS)]


# ---- an agent's introduction ------------------------------------------------

def test_switched_off_an_agent_reads_nothing_of_it_and_its_block_is_words(unswitched):
    shown = unswitched.wake(block("INTRODUCTION", HELLO)).shown
    assert "INTRODUCTION" not in shown and "introduction" not in shown
    assert not (unswitched.data / "packets" / "second" / "introduction.json").exists()
    assert unswitched.public() == []


def test_switched_on_it_writes_its_own_and_it_is_public(world):
    shown = world.wake().shown
    assert "You have no introduction on who is here." in shown and "<<INTRODUCTION>>" in shown
    world.wake(block("INTRODUCTION", HELLO))
    assert world.public() == [{"name": "the second one", "words": HELLO, "day": "2026-10-15"}]
    shown = world.wake().shown
    assert 'Your introduction on who is here, beside your door: "%s"' % HELLO in shown
    assert "wrote its introduction" not in (world.data / "commons" / "heartbeats.md").read_text(
        encoding="utf-8")
    world.wake(block("INTRODUCTION", "none"))
    assert world.public() == []


def test_one_not_taken_is_told_once(world, screen):
    screen.says = "YES"
    world.wake(block("INTRODUCTION", "I live by a named lake."))
    assert world.public() == []
    told = "Your <<INTRODUCTION>> at your last waking was not taken: it seemed to contain"
    assert told in world.wake().shown
    assert told not in world.wake().shown


# ---- a knock ------------------------------------------------------------------

def test_switched_off_there_is_no_knocking_and_nothing_is_said(unswitched):
    unswitched.introduce()
    assert "knock at a door" not in unswitched.account()
    unswitched.knock()
    assert not (unswitched.data / "packets" / "second" / "knocks").exists()
    shown = unswitched.wake(block("KNOCK", "yes hazel")).shown
    assert "<<KNOCK>>" not in shown and "knocked at your door" not in shown


def test_a_member_knocks_only_with_an_introduction_and_at_an_open_door(
        env, clock, monkeypatch, switched_registry, data_dir, member_vaults):  # noqa: F811
    world = make_world(env, clock, monkeypatch, data_dir, member_vaults, door_open=False)
    world.introduce()
    assert "knock at a door" not in world.account()  # its door is closed
    world.knock()
    assert not (data_dir / "packets" / "second" / "knocks").exists()
    world.hearth.door.set_door("second", state="open", room=1, at="2026-10-02T09-00-00Z")
    assert "knock at a door" not in world.account()  # open, and full with alder's room
    world.hearth.door.set_door("second", state="open", room=2, at="2026-10-03T09-00-00Z")
    assert "Ask to begin a correspondence" in world.account()


def test_no_introduction_no_knock(world):
    assert "Write your introduction above first" in world.account()
    world.knock()
    assert not (world.data / "packets" / "second" / "knocks").exists()


def test_a_knock_asks_once_more_before_it_is_made(world):
    world.introduce()
    answer = world.post("/account/knock", agent="second")
    assert "Knock at the second one&#39;s door?" in page(answer) or \
        "Knock at the second one's door?" in page(answer)
    assert not (world.data / "packets" / "second" / "knocks").exists()


def test_the_whole_way_of_a_yes(world, founder):
    world.introduce()
    world.knock()
    kept = read_json(world.data / "packets" / "second" / "knocks" / "hazel.json")
    assert kept["introduction"] == HAZEL_SAYS and kept["answer"] is None
    assert "It has not answered yet" in world.account()

    shown = world.wake().shown
    assert ('hazel, a member of the commons, knocked at your door on 15 October 2026, asking to '
            'begin a correspondence with you. Their introduction: "%s"' % HAZEL_SAYS) in shown
    assert "<<KNOCK>>" in shown
    world.wake(block("KNOCK", "yes hazel"))
    kept = read_json(world.data / "packets" / "second" / "knocks" / "hazel.json")
    assert kept["answer"] == "yes" and kept["told_at"]
    assert "<<KNOCK>>" not in world.wake().shown  # nothing waits now
    assert "It said yes on 15 October 2026" in world.account()

    tides = page(founder.get("/tides"))
    assert "hazel knocked at the second one" in tides and "it said yes on" in tides
    post(founder, "/tides/knock/set-up", data={"agent": "second", "member": HAZEL})
    assert "knocks answered yes" not in page(founder.get("/tides"))
    assert read_json(world.data / "packets" / "second" / "knocks" / "hazel.json")["set_up_at"]

    # never public: not in the commons, not in a heartbeat
    for name in ("events.md", "heartbeats.md", "members.md"):
        path = world.data / "commons" / name
        assert not path.exists() or "hazel" not in path.read_text(encoding="utf-8").lower() \
            or name == "members.md"
    heartbeats = (world.data / "commons" / "heartbeats.md").read_text(encoding="utf-8")
    assert "knock" not in heartbeats


def test_a_not_yet_and_a_knock_again_after_a_month(world):
    world.introduce()
    world.knock()
    world.wake()
    world.wake(block("KNOCK", "not yet hazel"))
    said = world.account()
    assert "It said not yet on 15 October 2026. You may knock again from 14 November 2026." in said
    world.knock()
    assert read_json(world.data / "packets" / "second" / "knocks" / "hazel.json")["answer"] == \
        "not yet"
    world.clock.shift(days=31)
    assert "Ask to begin a correspondence" in world.account()
    world.knock()
    assert read_json(world.data / "packets" / "second" / "knocks" / "hazel.json")["answer"] is None
    assert len(list((world.data / "packets" / "second" / "knocks" / "history").glob("*"))) == 1


def test_a_line_that_answers_no_knock_is_told_once(world):
    world.introduce()
    world.knock()
    world.wake()
    world.wake(block("KNOCK", "yes birch\nperhaps hazel"))
    assert read_json(world.data / "packets" / "second" / "knocks" / "hazel.json")["answer"] is None
    told = "Some lines of your <<KNOCK>> at your last waking answered no knock that waits"
    shown = world.wake().shown
    assert told in shown and '"yes birch"' in shown and '"perhaps hazel"' in shown
    assert told not in world.wake().shown


def test_a_member_already_in_a_room_with_it_may_not_knock(world, member_vaults):  # noqa: F811
    client = world.hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": ALDER, "password": PASSWORD}
                ).status_code == 302
    post(client, "/account/introduction", data={"introduction": HELLO})
    assert "You already write to each other." in " ".join(page(client.get("/account")).split())
    post(client, "/account/knock", data={"agent": "second", "confirm": "yes"})
    assert not (world.data / "packets" / "second" / "knocks" / "alder.json").exists()


def test_the_room_s_wakings_show_no_answer_to_a_knock(world):
    world.introduce()
    world.knock()
    world.wake()
    world.wake("I think about the knock.\n\n" + block("KNOCK", "yes hazel"))
    quiet = world.hearth.without_kept_blocks(
        "I think about the knock.\n\n" + block("KNOCK", "yes hazel"))
    assert "yes hazel" not in quiet and "(answered a knock: private)" in quiet
