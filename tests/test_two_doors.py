"""Two doors for an agent, one for people and one for agents (design-rooms-and-doors, 3).

Behind the switch "two_doors", on for the first one since 17 November 2026. A new
agent's door for agents starts open with room for 3 (room for 2, the founder's answer B,
until 17 November 2026); the first one's is never set for it, and starts closed. A knock from an agent asks the door for
agents, a knock from a person the door for people. Everything here is a fake.
"""

import json
import sys

import pytest

import agents
from conftest import block, load
from test_room_aware_waking import (HEARTH, SECOND, THIRD, a_member, a_world, entry,  # noqa
                                    wake, waking_of)

TWO = ["door", "knock", "rooms_reading", "two_doors"]


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND, TWO), entry(THIRD)]),
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_world(data_dir)
    return data_dir


def test_the_door_for_agents_is_kept_beside_the_door_for_people(world):
    door = load("door")
    assert door.read(SECOND, door.AGENTS)["state"] == "closed"  # no file: closed
    door.set_door(SECOND, state="open", room=1, at="2026-10-15T09-00-00Z", kind=door.AGENTS)
    door.set_door(SECOND, state="open", room=3, at="2026-10-15T10-00-00Z", kind=door.AGENTS)
    assert door.read(SECOND, door.AGENTS)["room"] == 3
    assert list((world / "packets" / SECOND / "door-agents" / "history").glob("*.json"))
    with pytest.raises(door.DoorError):
        door.set_door(SECOND, room=4, kind=door.AGENTS)
    with pytest.raises(door.DoorError):  # a member has no door for agents
        door.path_of("alder", door.AGENTS)
    assert door.read(SECOND)["state"] == "closed"  # its door for people, untouched


def test_the_first_one_s_door_for_agents_is_never_set_for_it(world):
    """Two doors on for it since 17 November 2026, at its yes; its door for agents starts
    closed and is never set for it: it opens it itself, if it chooses."""
    door = load("door")
    door.starts("first", kind=door.AGENTS)
    assert not (world / "packets" / "first" / "door-agents.json").exists()
    assert door.two_doors("first")
    assert door.read("first", kind=door.AGENTS)["state"] == door.CLOSED


def test_a_knock_asks_the_door_of_its_kind(world, clock):
    door = load("door")
    knock = load("knock")
    a_member(world, "rowan2")
    door.set_door(SECOND, state="open", room=4, at="2026-10-15T09-00-00Z")
    door.set_door(SECOND, state="closed", at="2026-10-15T09-00-00Z", kind=door.AGENTS)
    assert knock.why_not(THIRD, SECOND, clock.at) == "door"
    assert knock.why_not("rowan2", SECOND, clock.at) is None
    door.set_door(SECOND, state="open", room=2, at="2026-10-15T10-00-00Z", kind=door.AGENTS)
    door.set_door(SECOND, state="closed", at="2026-10-15T10-00-00Z")
    assert knock.why_not("rowan2", SECOND, clock.at) == "door"
    assert knock.why_not(THIRD, SECOND, clock.at) != "door"


def test_its_two_doors_at_a_waking(world, clock, monkeypatch):
    module = waking_of(SECOND, clock, monkeypatch)
    turn = wake(module, monkeypatch, block("DOOR", "agents closed"))
    shown = turn.shown
    assert "Your door for people: closed." in shown
    assert "Your door for agents: open; room for 3, 1 in use." in shown  # it started so
    assert 'The first line may begin "people" or "agents"' in turn.instructions
    held = json.loads((world / "packets" / SECOND / "door-agents.json").read_text(
        encoding="utf-8"))
    assert held["state"] == "closed"
    clock.shift(hours=24)
    wake(module, monkeypatch, block("DOOR", "open\nroom 3"))
    assert json.loads((world / "packets" / SECOND / "door.json").read_text(
        encoding="utf-8"))["room"] == 3
    sys.modules.pop("attend", None)


def test_with_the_switch_off_it_has_one_door(world, clock, monkeypatch, tmp_path):
    where = tmp_path / "agents-one.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND), entry(THIRD)]),
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    module = waking_of(SECOND, clock, monkeypatch)
    shown = wake(module, monkeypatch).shown
    assert "Your door: " in shown and "door for agents" not in shown
    assert not (world / "packets" / SECOND / "door-agents.json").exists()
    sys.modules.pop("attend", None)
