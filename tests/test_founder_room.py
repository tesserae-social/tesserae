"""founder-room: the founder's request of 19 November 2026.

A room between an agent and the founder never carries the founder's sign-in name.
rooms.address_for names the keeper "founder", as rooms.store_name does, so a later
room's address and bond are <agent>-founder; the knock it came from is kept as
founder--<agent> (knock.make_room); and where the keeper leaves a room, its room.json
says left_by "founder" (blocks.leave). Not for deploying before 23 November 2026.

The world is test_introductions': the second one, its room shared with alder, and
here the keeper too, by FOUNDER_NAME, its sign-in name in the tests.
"""

import json

import pytest

from conftest import FOUNDER_NAME
from test_introductions import make_world
from test_knocks_tidy import registry_with
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

AT = "2026-10-16T10-00-00Z"


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, founder_vault, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "knock_founder", "rooms_reading")
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    made.hearth.members.create_member(FOUNDER_NAME, json.loads(json.dumps(founder_vault)),
                                      "keeper", [])
    return made


def a_yes_from_the_second_one(world):
    """The keeper knocked at the second one's door, and it said yes."""
    import knock
    assert knock.kind_of(FOUNDER_NAME) == "keeper"
    knock.write({"from": FOUNDER_NAME, "to": "second", "at": "2026-10-15T09-00-00Z",
                 "note": "A knock from the founder.", "introduction": None,
                 "told_at": "2026-10-15T12-00-00Z", "answer": knock.YES,
                 "answered_at": "2026-10-15T12-00-00Z", "reply": None,
                 "answer_told_at": None, "waits_for_room": False, "set_up_at": None})
    return knock


def carrying_the_name(*trees):
    """Every file under these trees whose path or words carry the keeper's sign-in name."""
    found = []
    for tree in trees:
        for path in (tree.rglob("*") if tree.exists() else []):
            if FOUNDER_NAME in path.as_posix().lower():
                found.append(path)
            elif path.is_file() and FOUNDER_NAME in path.read_bytes().decode(
                    "utf-8", "replace").lower():
                found.append(path)
    return found


def test_the_address_names_the_keeper_founder(world):
    import rooms
    assert rooms.address_for("second", FOUNDER_NAME) == "second-founder"
    assert rooms.address_for("second", "alder") == "second-alder"  # a member's, as before


def test_a_later_room_with_the_founder_carries_no_sign_in_name(world):
    import rooms
    knock = a_yes_from_the_second_one(world)
    made = knock.make_room(FOUNDER_NAME, "second", AT, anyway=True)
    assert made["room"] == "second-founder"
    record = json.loads((world.data / "rooms" / "second-founder" / "room.json").read_text(
        encoding="utf-8"))
    assert record["id"] == record["bond"] == "second-founder"
    assert record["from_knock"] == "founder--second"
    assert "did:web:tesserae.social:ids:founder" in record["parties"]
    # every id and address, as the agent and as the keeper stand in it, and the agent's
    # names for its two (the keeper's own view holds the keeper's own name, as "mine")
    for room in [*rooms.of("second"), *rooms.of(FOUNDER_NAME)]:
        assert FOUNDER_NAME not in room.id + " " + room.bond
    for room in rooms.of("second"):
        assert FOUNDER_NAME not in " ".join([*room.parties, room.other])
    assert "second-founder" in [room.id for room in rooms.of(FOUNDER_NAME)]
    # its next waking, which reads the room, and its signed record of it
    world.wake()
    assert carrying_the_name(world.data / "rooms", world.data / "commons",
                             world.data / "packets" / "second") == []


def test_the_keeper_leaving_is_kept_as_founder(world):
    import blocks
    import rooms
    knock = a_yes_from_the_second_one(world)
    knock.make_room(FOUNDER_NAME, "second", AT, anyway=True)
    assert blocks.block(FOUNDER_NAME, "second", AT)
    room = rooms.find("second-founder", FOUNDER_NAME)
    assert blocks.leave(room, FOUNDER_NAME, "2026-10-16T11-00-00Z")
    record = json.loads((world.data / "rooms" / "second-founder" / "room.json").read_text(
        encoding="utf-8"))
    assert record["left_by"] == "founder"
    assert carrying_the_name(world.data / "rooms") == []
