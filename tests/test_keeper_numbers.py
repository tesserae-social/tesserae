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
    # /tides names members elsewhere (the site note's select), which is the keeper's own
    # to choose from; the numbers name no one
    for never in (FOUNDER_NAME, A_LETTER.strip()):
        assert never not in said, never
    numbers = the_numbers(founder)
    for never in (ALDER, HAZEL):
        assert never not in numbers, never
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
    # since askings (20 November 2026) the registry is also asked for itself as committed,
    # registry(asked=False)
    monkeypatch.setattr(hearth.agents, "registry", lambda asked=True: asleep)
    said = the_numbers(founder)
    assert "Agents that wake: 0" in said
    assert "People per agent: none yet" in said
    assert "Average friendships per agent: none yet" in said


# ---- cost, letters, rooms, freshness and the founding line (17 November 2026) ----
#
# The clock stands at 15 October 2026, 12:00 UTC: the last 7 days are 9 to 15 October,
# and the days of this month already over are 1 to 14 October.

def spending_day(data, day, *lines):
    """One day's spending records: (who, dollars) each."""
    write(data / "spending" / ("spending-%s.jsonl" % day),
          "".join(json.dumps({"who": who, "model": "a-model-for-the-tests", "dollars": cost})
                  + "\n" for who, cost in lines))


def first_card(founder):
    said = page(founder.get("/tides"))
    return said.partition('<article class="card">')[2].partition("</article>")[0]


def test_an_agent_s_cost_is_on_its_own_card_and_the_screens_apart(founder, data_dir):
    spending_day(data_dir, "2026-10-15", ("first", 0.25), ("screens", 0.05))
    spending_day(data_dir, "2026-10-10", ("first", 1.00), ("screens", 1.00))
    spending_day(data_dir, "2026-10-02", ("first", 0.75))
    spending_day(data_dir, "2026-09-30", ("first", 9.00))  # last month: not counted
    for stamp in ("2026-10-02T09-00-00Z", "2026-10-10T09-00-00Z", "2026-10-15T09-00-00Z",
                  "2026-09-30T09-00-00Z"):
        write_json(data_dir / "packets" / "first" / "attendances" /
                   ("attendance-%s.json" % stamp), {"at": stamp})
    card = first_card(founder)
    assert ("Cost: today $0.25 · the last 7 days $1.25 ·\n      this month $2.00 · per waking "
            "this month $0.67\n      (3 wakings)") in card
    assert "It reached its daily cap of $1.00 on 10 October." in card
    said = the_numbers(founder)
    assert "Everything this month, agents and screening: $3.05" in said
    # 1 to 14 October: $2.75 over 14 days, for 31 days
    assert "projected at the average of its days already over: $6.09" in said
    assert "Screening: today $0.05 · the last 7 days $1.05 ·\n    this month $1.05" in said
    assert "Screening reached its daily cap of $1.00 on 10 October." in said
    assert "$0.67" not in said and "Cost:" not in said  # no agent's own cost in the numbers


def test_with_no_spending_the_costs_are_nothing_and_the_projection_none_yet(founder):
    assert "Cost: today $0.00 · the last 7 days $0.00" in first_card(founder)
    assert "per waking this month none yet" in first_card(founder)
    said = the_numbers(founder)
    assert "agents and screening: $0.00" in said
    assert "already over: $0.00" in said
    assert "reached its daily cap" not in said


def a_letter(folder, name):
    write(folder / (name + ".md"), A_LETTER)


@three
def test_letters_are_counted_by_their_names_each_way_and_the_rooms_fresh_or_quiet(founder,
                                                                                  data_dir):
    a_member(data_dir, ALDER)
    second_room_with(data_dir, ALDER)  # alder's letter of 14 October, read
    second = data_dir / "rooms" / "second" / "letters"
    a_letter(second / "outgoing", "to-alder-2026-10-12T09-00-00Z")
    a_letter(second / "outgoing", "to-alder-2026-10-03T09-00-00Z")
    a_letter(second / "incoming", "alder-2026-09-20T09-00-00Z")  # last month
    first = data_dir / "rooms" / "first" / "letters"
    a_letter(first / "read", "founder-2026-09-25T09-00-00Z")  # quiet for over 14 days
    a_letter(first / "outgoing", "to-founder-2026-09-26T09-00-00Z")
    between = data_dir / "rooms" / "second-third"
    write_json(between / "room.json", {"id": "second-third", "bond": "second-third",
                                       "kind": "agents", "opened_at": "2026-10-01T00-00-00Z",
                                       "parties": [SECOND["did"], THIRD["did"]]})
    a_letter(between / "letters" / "from-second", "second-to-did-2026-10-05T09-00-00Z")
    a_letter(between / "letters" / "from-third", "third-to-did-2026-10-06T09-00-00Z")
    said = the_numbers(founder)
    assert ("In the last 7 days: people to agents 1 · agents to people\n    1 · agents to "
            "agents 0") in said
    assert "This month: people to agents 1 · agents to people\n    2 · agents to agents 2" in said
    for line in ("Rooms open: 3", "Rooms with letters both ways in the last 7 days: 1",
                 "Rooms with letters both ways in the last 14 days: 2",
                 "Rooms with no letter for over 14 days: 1", "Rooms with no letter yet: 0"):
        assert line in said, line
    assert A_LETTER.strip() not in page(founder.get("/tides"))
    for never in (ALDER, SECOND["commons_name"], THIRD["commons_name"]):
        assert never not in said, never


def test_a_room_with_no_letter_yet_is_said_so(founder):
    said = the_numbers(founder)
    assert "Rooms open: 1" in said and "Rooms with no letter yet: 1" in said
    assert "Rooms with no letter for over 14 days: 0" in said


def test_bonds_sealed_are_counted_and_a_released_one_is_not(hearth, founder, monkeypatch):
    monkeypatch.setattr(hearth.public_bonds, "every", lambda: [
        ("founder-first", {"sealed_at": "2026-10-01T00-00-00Z"}),
        ("founder-old", {"sealed_at": "2026-09-01T00-00-00Z",
                         "released_at": "2026-09-10T00-00-00Z"})])
    assert "Bonds sealed: 1" in the_numbers(founder)


def test_the_founding_line_says_who_waits_and_what_room_there_is(founder, data_dir):
    for name in (ALDER, HAZEL, BIRCH):
        a_member(data_dir, name)
    said = the_numbers(founder)
    assert ("When to found a new agent: 3 people waiting, 0 agent doors with room; 0 of 1 room "
            "had letters both ways in the last 7 days. More people wait than there are doors "
            "with room.") in said


def test_the_founding_line_with_room_for_everyone_waiting(founder, data_dir):
    a_member(data_dir, ALDER)
    a_door(data_dir, "packets/first", "open", 3)
    said = the_numbers(founder)
    assert "When to found a new agent: 1 person waiting, 1 agent door with room;" in said
    assert "More people wait" not in said


def test_cost_and_the_founding_line_are_the_keeper_s_alone(hearth, founder, visitor, data_dir):
    spending_day(data_dir, "2026-10-15", ("first", 0.25))
    for address in ("/", "/commons", "/commons/members.md", "/first"):
        said = page(visitor.get(address))
        for never in ("When to found", "Cost: today", "$0.25", "Bonds sealed"):
            assert never not in said, (address, never)
