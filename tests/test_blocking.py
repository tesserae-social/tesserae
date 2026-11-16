"""Blocking, and leaving a room a block stands between (design-rooms-and-doors, section 5).

A block works both ways and reads as a closed door; the blocked one is never told; a
knock waiting from them is answered not yet, in silence; a mention by them is not told.
A block lets either side leave a room they share (the founder's answer C); the first
one's room is never left. An agent blocks at a waking behind the switch "block", off for
the first one. Everything here is a fake, in test_room_aware_waking's world.
"""

import json
import sys

import pytest

import agents
from conftest import block, blocks as said_blocks, load
from test_room_aware_waking import (DID, HEARTH, SECOND, THIRD, a_member, a_world, entry,  # noqa
                                    wake, waking_of)

WITH_BLOCKS = ["door", "knock", "rooms_reading", "block"]


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND, WITH_BLOCKS), entry(THIRD)]),
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_world(data_dir)
    return data_dir


def test_a_block_is_a_closed_door_both_ways(world, clock):
    blocks = load("blocks")
    knock = load("knock")
    door = load("door")
    a_member(world, "rowan2")
    door.set_door(THIRD, state="open", room=4, at="2026-10-15T09-00-00Z")
    door.set_door("rowan2", state="open", room=2, at="2026-10-15T09-00-00Z")
    assert knock.why_not("rowan2", THIRD, clock.at) is None
    assert blocks.block(THIRD, "rowan2", "2026-10-15T10-00-00Z")
    assert knock.why_not("rowan2", THIRD, clock.at) == "door"
    assert knock.why_not(THIRD, "rowan2", clock.at) == "door"
    assert blocks.read("rowan2") == []  # nothing is kept on the blocked one's side
    assert blocks.unblock(THIRD, "rowan2", "2026-10-15T11-00-00Z")
    assert knock.why_not("rowan2", THIRD, clock.at) is None
    assert list((world / "packets" / THIRD / "blocks" / "history").glob("*.json"))


def test_a_waiting_knock_is_answered_not_yet_in_silence(world):
    blocks = load("blocks")
    knock = load("knock")
    a_member(world, "rowan2")
    knock.write({"from": "rowan2", "to": THIRD, "at": "2026-10-14T09-00-00Z", "note": "Hi.",
                 "introduction": None, "told_at": None, "answer": None, "answered_at": None,
                 "reply": None, "answer_told_at": None, "waits_for_room": False,
                 "set_up_at": None})
    blocks.block(THIRD, "rowan2", "2026-10-15T10-00-00Z")
    held = knock.read("rowan2", THIRD)
    assert held["answer"] == "not yet" and held["reply"] is None


def test_who_is_here_and_mentions_at_a_waking(world, clock, monkeypatch):
    blocks = load("blocks")
    blocks.block("hazel", SECOND, "2026-10-15T10-00-00Z")
    module = waking_of(SECOND, clock, monkeypatch)
    said = module.who_is_here_said()
    line = next(one for one in said.splitlines() if one.startswith("hazel"))
    assert "door closed" in line and "you may knock" not in line
    sys.modules.pop("attend", None)


def test_an_agent_blocks_and_it_is_its_own_to_see(world, clock, monkeypatch):
    module = waking_of(SECOND, clock, monkeypatch)
    turn = wake(module, monkeypatch, block("BLOCK", "hazel"))
    assert "<<BLOCK>>" in turn.instructions and "<<LEAVE>>" not in turn.instructions
    assert json.loads((world / "packets" / SECOND / "blocks.json").read_text(
        encoding="utf-8"))[0]["who"] == "hazel"
    heartbeats = (world / "commons" / "heartbeats.md").read_text(encoding="utf-8")
    assert "blocked" not in heartbeats  # never said in the commons
    clock.shift(hours=24)
    turn = wake(module, monkeypatch)
    assert "You have blocked: hazel." in turn.shown
    assert "<<LEAVE>>" in turn.instructions and "<<UNBLOCK>>" in turn.instructions
    clock.shift(hours=24)
    wake(module, monkeypatch, block("LEAVE", "hazel"))
    import rooms
    assert "second-hazel" not in [one.id for one in rooms.of(SECOND)]
    assert "second-hazel" not in [one.id for one in rooms.of("hazel")]
    left = json.loads((world / "rooms" / "second-hazel" / "room.json").read_text(
        encoding="utf-8"))
    assert left["left_by"] == SECOND and left["left_at"]
    assert (world / "rooms" / "second-hazel" / "letters" / "incoming").exists()  # nothing erased
    sys.modules.pop("attend", None)


def test_with_the_switch_off_a_block_is_only_words(world, clock, monkeypatch, tmp_path):
    where = tmp_path / "agents-off.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND), entry(THIRD)]),
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    module = waking_of(SECOND, clock, monkeypatch)
    turn = wake(module, monkeypatch, said_blocks(block("BLOCK", "hazel"),
                                                 block("LEAVE", "hazel")))
    assert "<<BLOCK>>" not in turn.instructions
    assert not (world / "packets" / SECOND / "blocks.json").exists()
    sys.modules.pop("attend", None)


def test_the_first_one_s_room_is_never_left(world):
    blocks = load("blocks")
    import rooms
    blocks.block("first", "rowan", "2026-10-15T10-00-00Z")
    room = rooms.of("first")[0]
    assert not blocks.leavable(room, "first")
    assert not blocks.leave(room, "first", "2026-10-15T11-00-00Z")


def test_the_first_one_s_block_is_only_words(attend, wake, packet):
    assert not attend.BLOCKING
    wake(block("BLOCK", "hazel"))
    assert not (packet / "blocks.json").exists()
