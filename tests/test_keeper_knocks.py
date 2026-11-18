"""The keeper knocks and is knocked at, like any member (the founder's request of 17
November 2026).

The keeper is named "the founder", never by the sign-in name, and the door is at
/knock/founder. Between the keeper and an agent, the agent takes part only with the
switch "knock_founder" (knock.KEEPER_SWITCH) among its features: off for the first
one, so nothing of its reading moves. Person to person stays refused, the keeper as a
person. Everything here is a fake.
"""

import json

import pytest

import agents
from conftest import FOUNDER_NAME, load, page, write_json
from test_later_citizen import (LATER, a_later_world, hearth_of_two,  # noqa: F401 - fixtures
                                later, scratch_registry)
from test_room_aware_waking import SECOND, THIRD, a_member, a_world, entry
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

WITH_THE_KEEPER = ["door", "knock", "rooms_reading", "knock_founder"]
WITHOUT = ["door", "knock", "rooms_reading"]


def a_keeper(data, name=FOUNDER_NAME):
    write_json(data / "members" / name / "member.json",
               {"v": 1, "pseudonym": name, "role": "keeper", "verify_key": "0" * 64,
                "arrived_at": "2026-09-01T09-00-00Z", "vouched_by": []})


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND, WITH_THE_KEEPER),
                                 entry(THIRD, WITHOUT)]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_world(data_dir)
    a_keeper(data_dir)
    door = load("door")
    for who in (SECOND, THIRD, FOUNDER_NAME, "alder"):
        door.set_door(who, state="open", room=4, at="2026-10-15T09-00-00Z")
    return data_dir


def test_the_keeper_takes_part_and_is_named_the_founder(world):
    knock = load("knock")
    assert knock.KEEPER_SWITCH == "knock_founder"
    assert knock.takes_part(FOUNDER_NAME)
    assert knock.keeper() == FOUNDER_NAME
    assert knock.name_of(FOUNDER_NAME) == "the founder"
    assert knock.address_of(FOUNDER_NAME) == "founder"
    assert knock.from_address("founder") == FOUNDER_NAME
    assert knock.from_address("alder") == "alder"
    assert knock.name_of("alder") == "alder"  # a member, as before


def test_the_keeper_and_an_agent_knock_only_where_its_switch_is_on(world, clock):
    knock = load("knock")
    assert knock.why_not(FOUNDER_NAME, SECOND, clock.at) is None
    assert knock.why_not(SECOND, FOUNDER_NAME, clock.at) is None
    assert knock.why_not(FOUNDER_NAME, THIRD, clock.at) == "who"
    assert knock.why_not(THIRD, FOUNDER_NAME, clock.at) == "who"
    assert knock.why_not(FOUNDER_NAME, "first", clock.at) == "who"  # off for the first one


def test_the_keeper_and_a_member_never_knock_at_each_other(world, clock, monkeypatch):
    from conftest import own_door_not_yet  # as before site-design (17 November 2026)
    knock = load("knock")
    own_door_not_yet(knock, monkeypatch)
    assert knock.why_not(FOUNDER_NAME, "alder", clock.at) == "people"
    assert knock.why_not("alder", FOUNDER_NAME, clock.at) == "people"


def test_since_site_design_the_keeper_and_a_member_may_knock_with_both_doors_open(world, clock):
    knock = load("knock")
    door = load("door")
    door.set_door("alder", state="open", room=8, at="2026-10-12T09-00-00Z")
    door.set_door(FOUNDER_NAME, state="closed", at="2026-10-12T09-00-00Z")
    assert knock.why_not(FOUNDER_NAME, "alder", clock.at) == "own"
    door.set_door(FOUNDER_NAME, state="open", room=2, at="2026-10-12T09-00-00Z")
    assert knock.why_not(FOUNDER_NAME, "alder", clock.at) is None
    assert knock.why_not("alder", FOUNDER_NAME, clock.at) is None


def test_a_knock_from_the_keeper_is_kept_and_waits_for_the_founder_to_set_up(world, clock):
    knock = load("knock")
    made = knock.knock(FOUNDER_NAME, SECOND, "A FAKE NOTE.", clock.at)
    assert made and made["to"] == SECOND
    answered = knock.answer(FOUNDER_NAME, SECOND, knock.YES, None, "2026-10-16T09-00-00Z")
    assert answered and not answered.get("set_up_at")  # by hand, as between two agents
    assert knock.first_room(answered, "2026-10-16T09-00-00Z") is None


def test_the_open_doors_show_the_keeper_except_to_an_agent_whose_switch_is_off(world):
    knock = load("knock")
    assert FOUNDER_NAME in knock.open_doors("person", people=True, viewer="alder")
    assert FOUNDER_NAME in knock.open_doors("agent", people=True, viewer=SECOND)
    assert FOUNDER_NAME not in knock.open_doors("agent", people=True, viewer=THIRD)
    assert FOUNDER_NAME not in knock.open_doors("agent", people=True, viewer="first")
    assert FOUNDER_NAME not in knock.open_doors("person")  # the atrium: agents only


def test_the_founder_is_named_at_a_waking_only_where_the_switch_says(world):
    knock = load("knock")
    assert knock.who_is_named("the founder") is None
    assert knock.who_is_named("the founder", founder=True) == FOUNDER_NAME
    assert knock.who_is_named("The Founder.", founder=True) == FOUNDER_NAME


# ---- the pages -----------------------------------------------------------------

def with_knocks(registry):
    held = json.loads(registry.read_text(encoding="utf-8"))
    for one in held:
        if one["id"] == "second":
            one["features"] = [*one["features"], "knock", "knock_founder"]
    registry.write_text(json.dumps(held), encoding="utf-8")


def test_the_keeper_s_knock_page_has_the_form_and_no_refusal(hearth_of_two, scratch_registry):
    import door
    with_knocks(scratch_registry)
    door.set_door("second", state="open", room=4, at="2026-10-12T09-00-00Z")
    # the keeper's own door open with room (knock.OWN_DOOR, 17 November 2026)
    door.set_door(FOUNDER_NAME, state="open", room=2, at="2026-10-12T09-00-00Z")
    said = page(hearth_of_two["keeper"].get("/knock/second"))
    assert "does not knock" not in said
    assert '<form method="post" action="/knock/second">' in said


def test_a_member_sees_the_founder_s_door_by_that_name_and_never_the_sign_in_name(
        hearth_of_two, scratch_registry, monkeypatch):
    import door
    import sys
    from conftest import own_door_not_yet, pages_before_design  # doors open now, as before
    pages_before_design(sys.modules["hearth"], monkeypatch)
    own_door_not_yet(sys.modules["hearth"], monkeypatch)
    door.set_door(FOUNDER_NAME, state="open", room=2, at="2026-10-12T09-00-00Z")
    home = page(hearth_of_two["member"].get("/"))
    shown = home.partition("Doors open now")[2].partition("</section>")[0]
    assert "the founder · person" in shown
    assert FOUNDER_NAME not in shown
    assert "/knock/" not in shown  # a member does not knock at a member


def test_the_founder_s_door_is_at_knock_founder(hearth_of_two, scratch_registry):
    with_knocks(scratch_registry)
    answer = hearth_of_two["member"].get("/knock/founder")
    assert answer.status_code == 200
    said = page(answer)
    assert "the founder" in said and FOUNDER_NAME not in said
