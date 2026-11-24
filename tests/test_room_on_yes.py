"""room-on-yes: the founder's request of 21 November 2026.

When the one knocked at says yes, the room opens by itself, within each side's door: no
"make the room" on /tides. Behind the switch room_on_yes for every agent of the two (on for
the second one and new agents; off for the first one, whose yeses the founder still makes on
/tides). A yes that does not fit, or that waits for wakings that can read it, waits, and opens
by itself once it can. Between two people a yes opens their notes, as it always has. The knock
page and the how-to-join page fold "How knocking works".

The world is test_introductions': hazel, a member in no room, signed in, and the second one,
whose room is shared with alder; here it reads every room.
"""

import pytest

from conftest import REPO, block, page, post, room_on_yes_not_yet
from test_introductions import home, kept_knock, knock_at, make_world
from test_knocks_tidy import registry_with
from test_later_citizen import HAZEL
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

YES = block("KNOCK_ANSWER", "from: hazel\nanswer: yes\n")


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "rooms_reading", "room_on_yes")
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


@pytest.fixture
def unswitched(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "rooms_reading")
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


def rooms_of(who):
    import rooms
    return [one.id for one in rooms.of(who)]


def test_the_switch_is_the_second_one_s_and_a_new_agent_s_not_the_first_one_s():
    import json
    import found_agent
    import knock
    registry = {one["id"]: one for one in json.loads((REPO / "agents.json").read_text(
        encoding="utf-8"))}
    assert knock.AUTO_SWITCH == "room_on_yes" and knock.AUTO is True
    assert "room_on_yes" in found_agent.FEATURES
    assert "room_on_yes" in registry["second"]["features"]
    assert "room_on_yes" not in registry["first"]["features"]


def test_an_agent_s_yes_opens_the_room_by_itself(world):
    knock_at(world)
    world.wake(YES)
    kept = kept_knock(world, HAZEL, "second")
    assert kept["set_up_at"] and kept["room"] == "second-hazel"
    assert "second-hazel" in rooms_of(HAZEL)
    said = home(world)
    assert 'href="/rooms/second-hazel">your room with the second one</a>' in said
    assert "The founder sets up the room by hand." not in said
    # nothing for the founder to do on /tides, and the agent is told at its next waking
    assert world.hearth.knocks_to_set_up() == []
    assert "Your room with hazel is open: /rooms/second-hazel." in world.wake().shown


def test_a_yes_over_a_door_waits_and_opens_once_there_is_room(world, monkeypatch):
    import door
    knock_at(world)
    world.hearth.door.set_door(HAZEL, state="open", room=None, at="2026-10-15T10-00-00Z")
    world.wake(YES)
    assert not kept_knock(world, HAZEL, "second").get("set_up_at")
    said = home(world)
    assert "The room opens by itself once you both have room for it." in said
    listed = world.hearth.knocks_to_set_up()
    assert len(listed) == 1 and listed[0]["auto"]
    # her door given room again: the room opens by itself
    assert world.post("/door", state="open", room="2").status_code == 302
    kept = kept_knock(world, HAZEL, "second")
    assert kept["set_up_at"] and kept["room"] == "second-hazel"
    assert door.read(HAZEL)["room"] == 2


def test_a_yes_that_waited_opens_when_the_hearth_starts(world):
    # small-builds, the founder's request of 23 November 2026: no door need be saved
    import door
    knock_at(world)
    world.hearth.door.set_door(HAZEL, state="open", room=None, at="2026-10-15T10-00-00Z")
    world.wake(YES)
    assert not kept_knock(world, HAZEL, "second").get("set_up_at")
    door.set_door(HAZEL, state="open", room=2, at="2026-10-16T10-00-00Z")  # by no page
    assert not kept_knock(world, HAZEL, "second").get("set_up_at")
    opened = world.hearth.open_waiting_at_start()
    kept = kept_knock(world, HAZEL, "second")
    assert len(opened) == 1 and kept["set_up_at"] and kept["room"] == "second-hazel"
    assert world.hearth.open_waiting_at_start() == []  # once: nothing more waits


def test_the_hearth_checks_the_waiting_yeses_as_it_starts():
    source = (REPO / "hearth.py").read_text(encoding="utf-8")
    assert source.count("\nstart_waiting_yeses()\n") == 1


def test_without_the_switch_the_founder_makes_the_room(unswitched):
    knock_at(unswitched)
    unswitched.wake(YES)
    assert not kept_knock(unswitched, HAZEL, "second").get("set_up_at")
    assert "The founder sets up the room by hand." in home(unswitched)
    listed = unswitched.hearth.knocks_to_set_up()
    assert len(listed) == 1 and not listed[0]["auto"]


def test_a_person_s_yes_on_the_hearth_opens_the_room(world):
    """The second one knocks at hazel; she says yes on her home page."""
    import knock
    knock.write({"from": "second", "to": HAZEL, "at": "2026-10-14T09-00-00Z",
                 "note": "Hello there.", "introduction": None, "told_at": None, "answer": None,
                 "answered_at": None, "reply": None, "answer_told_at": None,
                 "waits_for_room": False, "set_up_at": None})
    assert world.post("/knock/answer", **{"from": "second", "answer": "yes"}).status_code == 302
    kept = knock.read("second", HAZEL)
    assert kept["set_up_at"] and kept["room"] == "second-hazel"


def test_with_room_on_yes_not_yet_nothing_opens_by_itself(world, monkeypatch):
    import knock
    room_on_yes_not_yet(world.hearth, monkeypatch)
    knock.write({"from": "second", "to": HAZEL, "at": "2026-10-14T09-00-00Z",
                 "note": "Hello there.", "introduction": None, "told_at": None, "answer": None,
                 "answered_at": None, "reply": None, "answer_told_at": None,
                 "waits_for_room": False, "set_up_at": None})
    assert world.post("/knock/answer", **{"from": "second", "answer": "yes"}).status_code == 302
    assert not knock.read("second", HAZEL).get("set_up_at")
    assert world.hearth.knock.AUTO is False


def test_tides_offers_no_button_for_a_yes_that_opens_by_itself(founder, hearth, monkeypatch):
    monkeypatch.setattr(hearth, "knocks_to_set_up", lambda: [{
        "by": "hazel", "to": "the second one", "knocked": "1 November 2026",
        "answered": "2 November 2026", "waits": False, "from_id": HAZEL, "to_id": "second",
        "over": None, "auto": True}])
    said = page(founder.get("/tides"))
    assert "It opens by itself once both sides have room for it." in said
    assert "Make the room" not in said.split('id="knocks"')[1].split("</section>")[0] \
        .split("</p>", 1)[1]


def test_the_knock_page_folds_how_knocking_works(world):
    said = page(world.client.get("/knock/second"))
    fold = said.split('<details class="how-knocking">')[1].split("</details>")[0]
    assert "<summary>How knocking works</summary>" in fold
    for line in world.hearth.HOW_KNOCKING:
        assert line in fold


def test_the_knock_page_says_the_founder_opens_a_room_with_an_agent_without_the_switch(
        unswitched):
    said = page(unswitched.client.get("/knock/second"))
    assert "A yes opens a room for letters. The founder opens it." in said


def test_how_to_join_folds_how_knocking_works():
    for name in ("docs/the-door.md", "the-door.html"):
        said = (REPO / name).read_text(encoding="utf-8")
        assert "<summary>How knocking works</summary>" in said
        assert "Not yet means you can knock again later, after 30 days." in said
        assert "Either of you can block the other at any time." in said


def test_no_page_says_the_founder_sets_up_a_room_where_it_opens_by_itself(world):
    knock_at(world)
    said = page(world.client.get("/knock/second"))
    assert "The founder sets up the room by hand" not in said


def test_roomless_words_say_a_yes_to_an_agent_opens_by_itself():
    import later_words
    before = "... A yes to an agent waits for the founder to set up the room.)"
    assert later_words.room_on_yes(before) == (
        "... A yes to an agent opens a room by itself, once each of you has a room with a "
        "person.)")


def test_a_yes_between_two_people_still_opens_notes_and_no_room(world):
    import knock
    assert knock.opens_by_itself({"from": HAZEL, "to": "alder"}) is False
