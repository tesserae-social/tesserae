"""The keeper's numbers, on /tides: counts only, never a name, nothing of any room.

The proposal "quiet, return, and the question of the day", section 7, "the
keeper's numbers": agents that wake, people (members), people per agent,
average friendships per agent, people waiting for a friendship, and doors with
room. They are shown on the keeper's own /tides page, which is linked from the
keeping menu already, so no other page moves (test_first_one_fingerprints.py
holds the founder's pages, and /tides is not among them). They are counted from
the registry, the members' store, the rooms' room.json and the agents' doors,
and from nothing anyone wrote.

The second and third agents are made only in a scratch registry and a scratch
DATA_DIR. The second wakes and has a room with alder; the third does not wake.
"""

import json

import pytest

import agents
from conftest import FOUNDER_NAME, load, page, write, write_json

ALDER, HAZEL, BIRCH = "alder", "hazel", "birch"  # the test keeper is conftest.FOUNDER_NAME
SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the scratch one", "room": "second", "bond": "founder-second",
          "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
          "hue": "#2F6F8F", "features": [], "wakes": True}
THIRD = {"id": "third", "did": "did:web:tesserae.social:ids:third",
         "commons_name": "the sleeping one", "room": "third", "bond": "founder-third",
         "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
         "hue": "#6F8F2F", "features": [], "wakes": False}
A_LETTER = "A FAKE LETTER IN A ROOM, FOR THE TESTS.\n"


@pytest.fixture
def registry(request, monkeypatch, tmp_path):
    """As the run reads it, or, asked for by name, the first one, a second that wakes and a
    third that does not."""
    if getattr(request, "param", "one") == "one":
        return None
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), SECOND, THIRD], indent=2) + "\n",
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


three = pytest.mark.parametrize("registry", ["three"], indirect=True)


@pytest.fixture
def hearth(registry, env, clock, monkeypatch):
    module = load("hearth")
    clock.pin(module, monkeypatch)
    module.app.config["TESTING"] = True
    return module


def a_member(data, name, role="member"):
    """A member, as far as being counted goes: a record and no vault."""
    write_json(data / "members" / name / "member.json",
               {"v": 1, "pseudonym": name, "role": role, "verify_key": "0" * 64})


def a_door(data, where, state, room):
    write_json(data / where / "door.json", {"state": state, "room": room,
                                            "set_at": "2026-10-15T09-00-00Z"})


def second_room_with(data, name):
    """The second one's room, with a member as its other party, and a letter in it."""
    home = data / "rooms" / "second"
    write_json(home / "room.json", {"id": "second", "bond": "founder-second",
                                    "parties": ["did:web:hearth.tesserae.social:ids:" + name,
                                                SECOND["did"]]})
    write(home / "letters" / "read" / "alder-2026-10-14T09-00-00Z.md", A_LETTER)


def the_numbers(founder):
    """The numbers section of /tides, as the keeper is shown it."""
    said = page(founder.get("/tides"))
    return said.partition("<h2>the numbers</h2>")[2].partition("</section>")[0]


def test_the_keeper_alone_with_the_first_one(founder):
    said = the_numbers(founder)
    for line in ("Agents that wake: 1", "People (members): 1", "People per agent: 1.0",
                 "Average friendships per agent: 1.0",
                 "People waiting for a friendship (in no room yet): 0",
                 "Agents' doors with room: 0"):
        assert line in said, line


def test_members_in_no_room_are_waiting_and_an_open_door_with_room_is_counted(founder, data_dir):
    for name in (ALDER, HAZEL, BIRCH):
        a_member(data_dir, name)
    a_door(data_dir, "packets/first", "open", 2)
    said = the_numbers(founder)
    for line in ("People (members): 4", "People per agent: 4.0",
                 "People waiting for a friendship (in no room yet): 3",
                 "Agents' doors with room: 1"):
        assert line in said, line


@pytest.mark.parametrize("state, room", [("open", 1), ("closed", 3), ("open", None)],
                         ids=["open and full", "closed, with room", "open, no room declared"])
def test_a_door_that_is_full_closed_or_says_no_room_is_not_counted(founder, data_dir, state, room):
    a_door(data_dir, "packets/first", state, room)
    assert "Agents' doors with room: 0" in the_numbers(founder)


@three
def test_only_agents_that_wake_are_counted_and_each_room_is_a_friendship(founder, data_dir):
    for name in (ALDER, HAZEL):
        a_member(data_dir, name)
    second_room_with(data_dir, ALDER)
    a_door(data_dir, "packets/second", "open", 3)
    a_door(data_dir, "packets/third", "open", 3)  # it does not wake, so is not counted
    said = the_numbers(founder)
    for line in ("Agents that wake: 2", "People (members): 3", "People per agent: 1.5",
                 "Average friendships per agent: 1.0",
                 "People waiting for a friendship (in no room yet): 1",
                 "Agents' doors with room: 1"):
        assert line in said, line


@three
def test_no_one_is_named_and_nothing_of_any_room_is_shown(founder, data_dir):
    for name in (ALDER, HAZEL):
        a_member(data_dir, name)
    second_room_with(data_dir, ALDER)
    said = page(founder.get("/tides"))
    for never in (ALDER, HAZEL, FOUNDER_NAME, A_LETTER.strip()):
        assert never not in said, never
    numbers = the_numbers(founder)
    for agent in (agents.first(), SECOND, THIRD):
        assert agent["commons_name"] not in numbers


def test_the_numbers_are_the_keeper_s_alone(hearth, founder, visitor):
    answer = visitor.get("/tides")
    assert answer.status_code == 302 and answer.headers["Location"] == "/login"
    for address in ("/", "/commons", "/commons/members.md"):
        said = page(visitor.get(address))
        assert "the numbers" not in said and "People per agent" not in said, address


def test_with_no_agent_that_wakes_the_averages_say_none_yet(hearth, founder, monkeypatch):
    asleep = [{**agents.first(), "wakes": False}]
    monkeypatch.setattr(hearth.agents, "registry", lambda: asleep)
    said = the_numbers(founder)
    assert "Agents that wake: 0" in said
    assert "People per agent: none yet" in said
    assert "Average friendships per agent: none yet" in said
