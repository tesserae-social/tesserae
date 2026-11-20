"""The keeper to "founder" (names-design.md, parts 2 and 6; the founder's request of 20 November
2026): move_to_ids.py, and the leave bug it mends.

The world is test_founder_room's: the second one, its room with alder, and the keeper under
FOUNDER_NAME, its sign-in name in the tests.
"""

import json

import pytest

from conftest import FOUNDER_NAME, PASSWORD, load, page, post, write
from test_founder_room import a_yes_from_the_second_one, carrying_the_name
from test_introductions import make_world
from test_knocks_tidy import registry_with
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

AT = "2026-10-16T10-00-00Z"
BACKED_UP = "2026-10-15T11-00-00Z · backed up · 1024 bytes · kept 3\n"


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, founder_vault, tmp_path):  # noqa: F811
    import move_to_ids
    monkeypatch.setattr(move_to_ids, "utc_now", lambda: clock.at)
    registry_with(monkeypatch, tmp_path, "knock_founder", "rooms_reading", "block")
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    made.hearth.members.create_member(FOUNDER_NAME, json.loads(json.dumps(founder_vault)),
                                      "keeper", [])
    return made


def with_a_room_and_a_block(world):
    import blocks
    knock = a_yes_from_the_second_one(world)
    knock.make_room(FOUNDER_NAME, "second", AT, anyway=True)
    assert blocks.block("second", FOUNDER_NAME, AT)  # kept under the sign-in name, as today
    return knock


def the_disk(root):
    """Every file under the world, by its path, as JSON where it is JSON."""
    found = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            text = path.read_bytes().decode("utf-8", "replace")
            try:
                found[path.relative_to(root).as_posix()] = json.loads(text)
            except ValueError:
                found[path.relative_to(root).as_posix()] = text
    return found


# ---- the leave bug --------------------------------------------------------------------------

def test_an_agent_that_blocked_the_keeper_can_leave_their_later_room(world):
    with_a_room_and_a_block(world)
    world.wake("<<LEAVE>>\nthe founder\n<<END>>")
    record = json.loads((world.data / "rooms" / "second-founder" / "room.json").read_text(
        encoding="utf-8"))
    assert record["left_by"] == "second" and record["left_at"]


def test_after_the_move_the_same_holds(world):
    import move_to_ids
    with_a_room_and_a_block(world)
    write(world.data / "backup.log", BACKED_UP)
    move_to_ids.apply(world.data)
    world.wake("<<LEAVE>>\nthe founder\n<<END>>")
    record = json.loads((world.data / "rooms" / "second-founder" / "room.json").read_text(
        encoding="utf-8"))
    assert record["left_by"] == "second"


# ---- the move -------------------------------------------------------------------------------

def test_a_dry_run_lists_and_changes_nothing(world, capsys):
    import move_to_ids
    with_a_room_and_a_block(world)
    before = the_disk(world.data)
    assert move_to_ids.main([]) == 0
    said = capsys.readouterr().out
    assert "move     members/%s -> members/founder" % FOUNDER_NAME in said
    assert "rewrite  packets/second/blocks.json" in said
    assert "A dry run: nothing was changed." in said
    assert the_disk(world.data) == before


def test_it_refuses_without_a_fresh_backup(world, capsys):
    import move_to_ids
    with_a_room_and_a_block(world)
    before = the_disk(world.data)
    assert move_to_ids.main(["--apply"]) == 1
    assert "take an encrypted backup first" in capsys.readouterr().out
    write(world.data / "backup.log", "2026-10-14T01-00-00Z · backed up · 1024 bytes · kept 3\n")
    before = the_disk(world.data)
    assert move_to_ids.main(["--apply"]) == 1  # a day and more old
    assert the_disk(world.data) == before


def test_the_move_puts_every_unsigned_place_under_founder(world):
    import move_to_ids
    knock = with_a_room_and_a_block(world)
    write(world.data / "backup.log", BACKED_UP)
    move_to_ids.apply(world.data)
    members = load("members")
    assert members.list_members() == ["alder", "founder", "hazel"] or "founder" in \
        members.list_members()
    assert not (world.data / "members" / FOUNDER_NAME).exists()
    record = members.load_member("founder")
    assert record["role"] == "keeper" and record["id"] == record["pseudonym"] == "founder"
    assert members.id_of_sign_in(FOUNDER_NAME) == "founder"
    assert members.id_of_sign_in("founder") is None
    blocks_held = json.loads((world.data / "packets" / "second" / "blocks.json").read_text(
        encoding="utf-8"))
    assert [one["who"] for one in blocks_held] == ["founder"]
    assert (world.data / "knocks" / "founder--second.json").is_file()
    knock = load("knock")
    assert knock.keeper() == "founder"
    # nothing outside the keeper's own record and the private index holds the sign-in name
    left = [path for path in carrying_the_name(world.data / "knocks", world.data / "members",
                                               world.data / "packets", world.data / "rooms")
            if path.name not in ("sign-in.json", "member.json", move_to_ids.RECORD)]
    assert left == []


def test_the_keeper_signs_in_with_the_same_name_and_password_after(world):
    import move_to_ids
    with_a_room_and_a_block(world)
    write(world.data / "backup.log", BACKED_UP)
    move_to_ids.apply(world.data)
    hearth = load("hearth")
    hearth.app.config["TESTING"] = True
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": FOUNDER_NAME, "password": PASSWORD})
    assert answer.status_code == 302
    with client.session_transaction() as held:
        assert held["member"] == "founder" and held["role"] == "keeper"
    other = hearth.app.test_client()
    answer = post(other, "/login", data={"pseudonym": "founder", "password": PASSWORD})
    assert answer.status_code != 302  # the id is no sign-in
    assert FOUNDER_NAME not in page(client.get("/tides"))


def test_undo_puts_every_file_back_as_it_was(world, capsys):
    import move_to_ids
    with_a_room_and_a_block(world)
    write(world.data / "backup.log", BACKED_UP)
    before = the_disk(world.data)
    move_to_ids.apply(world.data)
    assert move_to_ids.main(["--apply"]) == 1  # a move recorded already
    assert move_to_ids.main(["--undo"]) == 0
    assert the_disk(world.data) == before


def test_a_room_made_under_the_sign_in_name_is_listed_and_left(world, capsys):
    import move_to_ids
    with_a_room_and_a_block(world)
    (world.data / "rooms" / ("second-" + FOUNDER_NAME)).mkdir(parents=True)
    made = move_to_ids.plan(world.data)
    assert made["rooms_left"] == ["second-" + FOUNDER_NAME]
