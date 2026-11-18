"""Knocks tidied (the founder's request of 18 November 2026, the branch knocks-tidy).

1. A knock that still waits may be taken back: by a person from their home page, by an
   agent with <<KNOCK_TAKE_BACK>> behind its switch knock_take_back (off for the first
   one). It is gone for the other side, as if never sent, and the two may knock again
   with no wait.
2. One's own knocks that wait count against one's own room for that kind: one may knock
   only while rooms in use plus those knocks is below the room declared. For an agent,
   behind the same switch.
3. On /tides, "make the room" says where it would put the one who knocked over their room,
   and makes it only when the founder says "anyway".

With conftest.knocks_tidy_not_yet everything is as it was. The first one's reading is held
by test_first_one_fingerprints and test_rooms_reading.

The world is test_introductions': hazel, a member in no room, signed in, and the second
one, here with its switch on, whose room is shared with alder.
"""

import json
from datetime import datetime, timezone

import pytest

import agents

from conftest import block, knocks_tidy_not_yet, page, post
from test_introductions import NOTE, home, kept_knock, knock_at, make_world
from test_later_citizen import ALDER, HAZEL, LATER
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


def registry_with(monkeypatch, tmp_path, *features):
    second = dict(LATER, features=[*LATER["features"], "introduction", "knock", *features])
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), second], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "knock_take_back")
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


@pytest.fixture
def unswitched(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path)
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


def taken_back(world):
    where = world.data / "knocks" / "taken-back"
    return sorted(path.name for path in where.glob("*.json")) if where.is_dir() else []


# ---- 1. taking a knock back ----------------------------------------------------

def test_the_switch_is_knock_take_back_and_the_first_one_has_it_not():
    import knock
    assert knock.TAKE_BACK_SWITCH == "knock_take_back" and knock.TIDY is True
    assert "knock_take_back" not in agents.first()["features"]


def test_a_person_takes_back_a_waiting_knock_from_their_home_page(world):
    import knock
    knock_at(world)
    assert kept_knock(world, HAZEL, "second")["note"] == NOTE
    shown = home(world)
    assert "No answer yet." in shown and ">take back</button>" in shown
    assert world.post("/knock/take-back", to="second").status_code == 302
    assert kept_knock(world, HAZEL, "second") is None
    assert taken_back(world) and taken_back(world)[0].startswith(HAZEL + "--second-")
    assert ">take back</button>" not in home(world) and NOTE not in home(world)
    # gone for the other side, as if never sent
    assert knock.waiting_at("second") == []
    told = world.wake().shown
    assert "hazel (a person) knocked at your door" not in told and NOTE not in told
    assert "<<KNOCK_ANSWER>>" not in told
    # and no wait before knocking again
    assert knock.why_not(HAZEL, "second", NOW) is None
    knock_at(world)
    assert kept_knock(world, HAZEL, "second")["note"] == NOTE


def test_an_answered_knock_is_not_taken_back(world):
    import knock
    knock_at(world)
    knock.answer(HAZEL, "second", knock.NOT_YET, None, "2026-10-15T13-00-00Z")
    assert ">take back</button>" not in home(world)
    world.post("/knock/take-back", to="second")
    assert kept_knock(world, HAZEL, "second")["answer"] == knock.NOT_YET
    assert knock.take_back(HAZEL, "second", "2026-10-15T14-00-00Z") is None
    assert taken_back(world) == []


def test_only_one_s_own_knock_is_taken_back(world):
    import knock
    knock_at(world)
    assert knock.take_back(ALDER, "second", "2026-10-15T14-00-00Z") is None
    assert knock.take_back("second", HAZEL, "2026-10-15T14-00-00Z") is None
    assert kept_knock(world, HAZEL, "second")["note"] == NOTE


def test_an_agent_takes_back_its_waiting_knock_with_a_block(world):
    import knock
    first = world.wake().shown
    assert "<<KNOCK_TAKE_BACK>>" not in first  # only while a knock of its own waits
    assert "Your knocks that wait count against that room." in first
    world.wake(block("KNOCK", "to: hazel\n" + NOTE))
    assert kept_knock(world, "second", HAZEL)["note"] == NOTE
    assert "the second one" in home(world) and NOTE in home(world)
    offered = world.wake(block("KNOCK_TAKE_BACK", "to: hazel")).shown
    assert world.module.KNOCK_TAKE_BACK_BLOCK in offered
    assert kept_knock(world, "second", HAZEL) is None
    assert NOTE not in home(world)
    told = world.wake().shown
    assert "You took back your knock at hazel's door." in told
    assert "<<KNOCK_TAKE_BACK>>" not in told
    assert knock.why_not("second", HAZEL, NOW) is None  # no wait, and no month counted


def test_an_agent_s_take_back_that_names_no_waiting_knock_changes_nothing(world):
    world.wake(block("KNOCK", "to: hazel\n" + NOTE))
    world.wake(block("KNOCK_TAKE_BACK", "to: rowan"))
    assert kept_knock(world, "second", HAZEL)["note"] == NOTE
    told = world.wake().shown
    assert ('A <<KNOCK_TAKE_BACK>> at your last waking changed nothing: no knock of yours '
            'waits for an answer at "rowan".') in told


def test_switched_off_an_agent_s_take_back_is_only_words(unswitched):
    shown = unswitched.wake(block("KNOCK", "to: hazel\n" + NOTE)).shown
    assert "Your knocks that wait count against that room." not in shown
    shown = unswitched.wake(block("KNOCK_TAKE_BACK", "to: hazel")).shown
    assert "<<KNOCK_TAKE_BACK>>" not in shown
    assert kept_knock(unswitched, "second", HAZEL)["note"] == NOTE
    assert "You took back" not in unswitched.wake().shown


def test_the_take_back_block_is_kept_quiet_on_the_founder_s_pages(world):
    assert world.hearth.KEPT_QUIETLY["KNOCK_TAKE_BACK"] == "(took back a knock: private)"


# ---- 2. waiting knocks count against one's own room ----------------------------

def test_a_person_s_waiting_knocks_count_against_their_room(world):
    import knock
    world.hearth.door.set_door("first", state="open", room=3, at="2026-10-01T09-00-00Z")
    world.hearth.door.set_door(HAZEL, state="open", room=1, at="2026-10-02T09-00-00Z")
    assert knock.why_not(HAZEL, "first", NOW) is None
    knock_at(world)  # at the second one: one knock waits, against a room of one
    assert knock.why_not(HAZEL, "first", NOW) == "own_waiting"
    said = " ".join(page(world.client.get("/knock/first")).split())
    assert (world.hearth.KNOCK_WHY["own_waiting"].replace("'", "&#39;") in said
            and 'name="note"' not in said)
    world.hearth.door.set_door(HAZEL, state="open", room=2, at="2026-10-03T09-00-00Z")
    assert knock.why_not(HAZEL, "first", NOW) is None
    world.hearth.door.set_door(HAZEL, state="open", room=1, at="2026-10-04T09-00-00Z")
    world.post("/knock/take-back", to="second")
    assert knock.why_not(HAZEL, "first", NOW) is None


def test_a_knock_between_two_people_does_not_count_against_room(world):
    import knock
    world.hearth.door.set_door(HAZEL, state="open", room=1, at="2026-10-02T09-00-00Z")
    knock_at(world, to=ALDER)  # a yes between two people opens notes, never a room
    assert kept_knock(world, HAZEL, ALDER)["note"] == NOTE
    assert knock.why_not(HAZEL, "second", NOW) is None


def test_an_agent_s_waiting_knocks_count_only_with_its_switch(world, monkeypatch):
    import knock
    world.wake(block("KNOCK", "to: hazel\n" + NOTE))
    monkeypatch.setattr(knock, "AGENT_WAITING_MOST", 2)
    world.hearth.door.set_door("second", state="open", room=2, at="2026-10-02T09-00-00Z")
    world.hearth.door.set_door("first", state="open", room=1, at="2026-10-01T09-00-00Z",
                               kind=world.hearth.door.AGENTS)  # the first one's door for agents
    # its room with alder, and its knock at hazel that waits: its one door, room two, is full
    assert knock.why_not("second", "first", NOW) == "own_waiting"
    assert world.module.KNOCK_REFUSED["own_waiting"]
    agent = dict(agents.by_id("second"))
    agent["features"] = [one for one in agent["features"] if one != "knock_take_back"]
    monkeypatch.setattr(agents, "by_id", lambda who, real=agents.by_id: (
        agent if who == "second" else real(who)))
    assert knock.why_not("second", "first", NOW) is None


def test_as_before_waiting_knocks_count_for_no_one_and_nothing_is_taken_back(
        world, monkeypatch):
    import knock
    knocks_tidy_not_yet(world.hearth, monkeypatch)
    world.hearth.door.set_door("first", state="open", room=3, at="2026-10-01T09-00-00Z")
    world.hearth.door.set_door(HAZEL, state="open", room=1, at="2026-10-02T09-00-00Z")
    knock_at(world)
    assert knock.why_not(HAZEL, "first", NOW) is None
    assert ">take back</button>" not in home(world)
    world.post("/knock/take-back", to="second")
    assert kept_knock(world, HAZEL, "second")["note"] == NOTE


# ---- 3. /tides: a room that would put the one who knocked over theirs ----------

def a_yes(world, monkeypatch):
    import knock
    knock_at(world)
    monkeypatch.setattr(knock, "needs_a_second_room", lambda held: False)
    return knock.answer(HAZEL, "second", knock.YES, None, "2026-10-15T13-00-00Z")


def test_over_room_says_where_a_room_would_put_the_one_who_knocked_over(world, monkeypatch):
    import knock
    held = a_yes(world, monkeypatch)
    assert knock.over_room(held) is None  # room for 2, none in use
    assert world.hearth.over_said(held) is None
    world.hearth.door.set_door(HAZEL, state="open", room=None, at="2026-10-16T09-00-00Z")
    assert knock.over_room(held) == {"room": None, "in_use": 0}
    assert world.hearth.over_said(held) == (
        "This room would put hazel over their room: they declared no room, 0 in use.")
    monkeypatch.setattr(knock.door, "in_use", lambda who, kind=None: 2)
    world.hearth.door.set_door(HAZEL, state="open", room=2, at="2026-10-17T09-00-00Z")
    assert world.hearth.over_said(held) == (
        "This room would put hazel over their room: room for 2, 2 in use.")


def test_make_room_refuses_over_room_unless_anyway(world, monkeypatch):
    import found_room
    import knock
    a_yes(world, monkeypatch)
    world.hearth.door.set_door(HAZEL, state="open", room=None, at="2026-10-16T09-00-00Z")
    made = []
    monkeypatch.setattr(found_room, "found_later", lambda *asked: made.append(asked) or
                        type("Home", (), {"name": "second--hazel"})())
    assert knock.make_room(HAZEL, "second", "2026-10-16T10-00-00Z") is None
    assert made == [] and not kept_knock(world, HAZEL, "second").get("set_up_at")
    record = knock.make_room(HAZEL, "second", "2026-10-16T10-00-00Z", anyway=True)
    assert record["room"] == "second--hazel" and len(made) == 1


def test_tides_says_it_plainly_and_offers_anyway(founder, hearth, monkeypatch):  # noqa: F811
    over = "This room would put birch over their room: room for 1, 1 in use."
    monkeypatch.setattr(hearth, "knocks_to_set_up", lambda: [{
        "by": "birch", "to": "the first one", "knocked": "1 November 2026",
        "answered": "2 November 2026", "waits": False, "from_id": "birch", "to_id": "first",
        "over": over}])
    said = page(founder.get("/tides"))
    assert over in said and "Make the room anyway" in said
    assert '<input type="hidden" name="anyway" value="1">' in said
    knocks_tidy_not_yet(hearth, monkeypatch)
    said = page(founder.get("/tides"))
    assert over not in said and "Make the room anyway" not in said


def test_the_set_up_route_does_nothing_over_room_without_anyway(founder, hearth, monkeypatch):  # noqa: F811
    asked = []
    held = {"from": "birch", "to": "first", "answer": "yes"}
    monkeypatch.setattr(hearth.knock, "kind_of", lambda who: "person")
    monkeypatch.setattr(hearth.knock, "read", lambda by, to: held)
    monkeypatch.setattr(hearth, "over_said", lambda one: "over")
    monkeypatch.setattr(hearth.knock, "make_room",
                        lambda by, to, at, anyway=False: asked.append(("make", anyway)) or None)
    monkeypatch.setattr(hearth.knock, "set_up", lambda by, to, at: asked.append(("set up",)))
    post(founder, "/tides/knock/set-up", data={"from": "birch", "to": "first"})
    assert asked == []
    post(founder, "/tides/knock/set-up", data={"from": "birch", "to": "first", "anyway": "1"})
    assert asked[0] == ("make", True)
