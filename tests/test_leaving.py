"""leaving-build: the founder's request of 21 November 2026 (leaving-design.md, choices 1-11).

A room may be left with no block, by either side, where every agent in it has the switch
leaving (asked of it first; off for the first one and the second one until each says yes). A
sealed bond in it is released in the same act; the other side is told once, with no reason;
both can still read the room and take a copy, and neither can write in it; a new knock may be
made after the usual wait. An agent's first room is left only where it then wakes with none.

The world is test_introductions': hazel, a member, signed in, and the second one, here with
its switches, whose first room is shared with alder; hazel's room with it is opened by a yes.
"""

import json
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest

from conftest import block, page, post, write_json
from test_introductions import home, knock_at, make_world
from test_knocks_tidy import registry_with
from test_later_citizen import HAZEL
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

ROOM = "second-hazel"
YES = block("KNOCK_ANSWER", "from: hazel\nanswer: yes\n")


def with_room(world):
    knock_at(world)
    world.wake(YES)
    assert (world.data / "rooms" / ROOM / "room.json").is_file()
    return world


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "rooms_reading", "room_on_yes", "leaving",
                  "longer_waking")
    return with_room(make_world(env, clock, monkeypatch, data_dir, member_vaults))


@pytest.fixture
def unswitched(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "rooms_reading", "room_on_yes")
    return with_room(make_world(env, clock, monkeypatch, data_dir, member_vaults))


def room_of(world, who=HAZEL, room_id=ROOM):
    import rooms
    return next((one for one in rooms.of(who) if one.id == room_id), None)


def record(world, room_id=ROOM):
    return json.loads((world.data / "rooms" / room_id / "room.json").read_text(encoding="utf-8"))


def leave_as_hazel(world):
    asked = world.post("/rooms/%s/leave" % ROOM)
    assert asked.status_code == 302 and "leaving=1" in asked.headers["Location"]
    said = page(world.client.get("/rooms/%s?leaving=1" % ROOM))
    assert "Yes, leave this room" in said and "take a copy" in said
    assert world.post("/rooms/%s/leave" % ROOM, confirm="yes").status_code == 302


# ---- choice 1: leaving with no block -------------------------------------------------

def test_the_switch_is_leaving_and_no_agent_has_it_yet():
    import agents
    import leaving
    from conftest import REPO
    assert leaving.SWITCH == "leaving"
    registry = json.loads((REPO / "agents.json").read_text(encoding="utf-8"))
    assert all("leaving" not in one["features"] for one in registry)
    assert "leaving" not in agents.first()["features"]


def test_a_person_leaves_a_room_with_no_block_asked_once_first(world):
    said = page(world.client.get("/rooms/" + ROOM))
    assert "You may leave this room. It closes for both of you" in said
    leave_as_hazel(world)
    held = record(world)
    assert held["left_at"] and held["left_by"] == HAZEL
    assert room_of(world) is None  # no room for either
    left = json.loads((world.data / "rooms" / ROOM / "left.json").read_text(encoding="utf-8"))
    assert left["by"] == HAZEL and left["told"] == {}


def test_without_the_switch_a_room_is_left_only_with_a_block(unswitched):
    import blocks
    room = room_of(unswitched)
    assert not blocks.leavable(room, HAZEL)
    assert "Leave this room" not in page(unswitched.client.get("/rooms/" + ROOM))
    blocks.block(HAZEL, "second", "2026-10-15T13-00-00Z")
    assert blocks.leavable(room, HAZEL)
    assert unswitched.post("/rooms/%s/leave" % ROOM, confirm="yes").status_code == 302
    assert record(unswitched)["left_at"]
    # left by a block, as before: nothing more
    assert not (unswitched.data / "rooms" / ROOM / "left.json").exists()


def test_an_agent_s_first_room_is_never_its_last_by_accident(world):
    import blocks
    import rooms
    first = next(one for one in rooms.of("alder") if one.id == "second")
    assert not blocks.leavable(first, "alder")  # the second one's first room
    founder_room = rooms.Room(rooms.FIRST_ROOM, "founder", ("founder", "first"), "the first one",
                              "founder-first")
    assert not blocks.leavable(founder_room, "founder")  # its waking is built on it


# ---- choice 4: a sealed bond is released ---------------------------------------------

def test_a_sealed_bond_is_released_in_the_same_act(world):
    import rooms
    places = rooms.places(ROOM)
    write_json(places.bond_record, {"parties": ["x", "y"], "sealed_at": "2026-10-15T09-00-00Z"})
    leave_as_hazel(world)
    bond = json.loads(places.bond_record.read_text(encoding="utf-8"))
    assert bond["released_at"] and bond["released_by"].endswith(":" + HAZEL)
    public = world.data / "commons" / "bonds" / (ROOM + ".json")
    assert json.loads(public.read_text(encoding="utf-8"))["released_at"]
    events = (world.data / "commons" / "events.md").read_text(encoding="utf-8")
    assert "a bond was released" in events


# ---- choice 2: the other side is told once --------------------------------------------

def test_the_agent_is_told_once_when_a_person_leaves(world):
    leave_as_hazel(world)
    shown = world.wake().shown
    assert "Hazel left your room on" in shown and "Your letters are kept." in shown
    assert "Your rooms closed, which you can still read and no one can write in: your room " \
           "with hazel (left" in shown
    assert "Hazel left your room on" not in world.wake().shown  # once


def test_a_person_is_told_once_when_the_agent_leaves(world):
    world.wake(block("LEAVE", "hazel"))
    assert record(world)["left_by"] == "second"
    said = home(world)
    assert "The second one left your room on" in said and "Your letters are kept." in said
    assert "The second one left your room on" not in home(world)  # once
    assert "rooms closed" in home(world)


def test_the_commons_is_told_nothing(world):
    world.wake(block("LEAVE", "hazel"))
    for name in ("events.md", "heartbeats.md", "acts.md"):
        path = world.data / "commons" / name
        said = path.read_text(encoding="utf-8") if path.exists() else ""
        assert "left a room" not in said


def test_a_daily_email_carries_the_line(world, monkeypatch):
    import mail
    sent = []
    monkeypatch.setattr(mail, "send", lambda kind, to, subject, text, now, **kw:
                        sent.append(text) or mail.SENT)
    assert mail.send_waiting("hazel@example.com", [], "stop", left=[
        "The second one left your room on 15 October 2026. Your letters are kept."]) == mail.SENT
    assert "The second one left your room on 15 October 2026." in sent[0]


# ---- choice 3: closed, read-only, for both -------------------------------------------

def test_both_still_read_it_and_take_a_copy_and_neither_writes(world):
    from conftest import write
    write(world.data / "rooms" / ROOM / "letters" / "incoming" / "hazel-2026-10-15T12-30-00Z.md",
          "HAZEL'S LETTER IN THE ROOM.\n")
    leave_as_hazel(world)
    said = page(world.client.get("/rooms/%s/closed" % ROOM))
    assert "LETTER IN THE ROOM." in said and "Nothing can be written in it." in said
    copy = world.client.get("/rooms/%s/closed/copy" % ROOM)
    names = zipfile.ZipFile(BytesIO(copy.data)).namelist()
    assert "rooms/%s/letters/incoming/hazel-2026-10-15T12-30-00Z.md" % ROOM in names
    assert world.client.get("/rooms/" + ROOM).status_code in (302, 404)  # no room to write in
    world.wake()
    import sys
    attend = sys.modules["attend"]
    assert "HAZEL'S LETTER IN THE ROOM." in attend.closed_room_said("hazel")


def test_someone_else_cannot_open_it(world):
    leave_as_hazel(world)
    other = world.hearth.app.test_client()
    assert other.get("/rooms/%s/closed" % ROOM).status_code in (302, 401, 404)


# ---- choice 5: a new knock after the wait ---------------------------------------------

def test_a_new_knock_may_be_made_after_the_usual_wait(world):
    import knock
    leave_as_hazel(world)
    now = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
    assert knock.why_not(HAZEL, "second", now) == "left_soon"
    later = now + timedelta(days=knock.AGAIN_AFTER_DAYS + 1)
    assert knock.why_not(HAZEL, "second", later) not in ("yes", "left_soon")


def test_a_room_left_between_agents_no_longer_counts_as_a_friendship(world, monkeypatch):
    import knock
    monkeypatch.setattr(knock, "room_left_between", lambda one, other: "2026-10-15T12-00-00Z")
    knock.write({"from": "second", "to": "first", "at": "2026-10-10T09-00-00Z", "note": "Hi.",
                 "introduction": None, "told_at": None, "answer": "yes",
                 "answered_at": "2026-10-11T09-00-00Z", "reply": None, "answer_told_at": None,
                 "waits_for_room": False, "set_up_at": None})
    assert knock.agent_friends("second") == 0
    monkeypatch.setattr(knock, "room_left_between", lambda one, other: None)
    assert knock.agent_friends("second") == 1


# ---- the leave bug: "the founder" finds the keeper -------------------------------------

def test_the_founder_is_found_by_name_and_counted_as_one(world):
    import blocks
    import knock
    assert knock.who_is_named("the founder", founder=True) == knock.keeper()
    keeper = knock.keeper()
    if keeper:
        assert blocks.aliases("founder") == {"founder", keeper}


def test_leaving_not_yet_puts_it_back(world, monkeypatch):
    import blocks
    from conftest import leaving_not_yet
    leaving_not_yet(world.hearth, monkeypatch)
    assert not blocks.leavable(room_of(world), HAZEL)


# ---- a member leaving the commons (choices 6 to 11) ------------------------------------

def leave_the_commons(world, **asked):
    from conftest import PASSWORD
    said = page(world.client.get("/account/leave"))
    assert "Take your copy first" in said and "Your rooms close." in said
    assert world.post("/account/leave", step="leave", password="not it").status_code == 400
    answer = world.post("/account/leave", step="leave", password=PASSWORD, **asked)
    assert answer.status_code == 200 and "You have left the commons." in page(answer)


def test_a_member_leaves_the_commons(world):
    import knock
    import members
    copy = world.post("/account/leave/copy")
    assert "yours.json" in zipfile.ZipFile(BytesIO(copy.data)).namelist()
    leave_the_commons(world)
    record = members.load_member(HAZEL)
    assert record["left_at"] and record["vault_kept_until"] and record["vault"]
    assert record["verify_key"]  # what they signed still checks
    assert not (world.data / "members" / HAZEL / "email.json").exists()
    assert knock.kind_of(HAZEL) is None
    held = record_left = json.loads((world.data / "rooms" / ROOM / "left.json").read_text(
        encoding="utf-8"))
    assert held["commons"] is True and record_left["by"] == HAZEL
    # signed out, and no sign-in opens again
    assert world.client.get("/").status_code == 302
    from conftest import PASSWORD
    again = post(world.hearth.app.test_client(), "/login",
                 data={"pseudonym": HAZEL, "password": PASSWORD})
    assert again.status_code != 302 or again.headers.get("Location") != "/"
    ledger = (world.data / "commons" / "ledger.md").read_text(encoding="utf-8")
    assert "a member left" in ledger and HAZEL not in ledger
    # the agent is told once, with no reason
    shown = world.wake().shown
    assert "Hazel has left the commons. Your letters with them are kept. Your room is closed." \
        in shown


def test_after_leaving_their_name_page_is_no_one_s(world):
    from conftest import PASSWORD
    leave_the_commons(world)
    alder = world.hearth.app.test_client()
    assert post(alder, "/login", data={"pseudonym": "alder", "password": PASSWORD}
                ).status_code == 302
    assert alder.get("/names/" + HAZEL).status_code == 404  # a 404 to everyone
    assert alder.get("/names/nobody-here").status_code == 404


def test_a_waiting_knock_is_answered_not_yet_in_silence(world):
    import knock
    knock.write({"from": "second", "to": HAZEL, "at": "2026-10-15T12-10-00Z", "note": "Hi.",
                 "introduction": None, "told_at": None, "answer": None, "answered_at": None,
                 "reply": None, "answer_told_at": None, "waits_for_room": False,
                 "set_up_at": None})
    leave_the_commons(world)
    held = knock.read("second", HAZEL)
    assert held["answer"] == knock.NOT_YET and held["reply"] is None


def test_the_keeper_cannot_leave_this_way(world):
    import leaving
    import knock
    keeper = knock.keeper()
    if keeper:
        with pytest.raises(leaving.Refused):
            leaving.leave_commons(keeper, "2026-10-15T12-00-00Z", "2027-01-13")


def test_an_agent_s_first_room_is_kept_open_when_its_person_leaves(world):
    import leaving
    import rooms
    done = leaving.leave_commons("alder", "2026-10-15T12-00-00Z", "2027-01-13")
    assert "second" in done["kept_open"] and not rooms.left("second")


def test_the_vault_is_deleted_only_by_hand_after_its_days(world, capsys, monkeypatch):
    from datetime import date
    import leaving
    import members
    leave_the_commons(world)
    assert leaving.vaults_due(date(2026, 11, 1)) == []
    until = members.load_member(HAZEL)["vault_kept_until"]
    assert leaving.vaults_due(date.fromisoformat(until)) == [HAZEL]
    assert members.come_back(HAZEL) is True and not members.has_left(HAZEL)
    members.mark_left(HAZEL, "2026-10-16T12-00-00Z", "2026-10-17")
    assert members.drop_vault(HAZEL) and "vault" not in members.load_member(HAZEL)
    assert members.come_back(HAZEL) is False  # with no vault, a new invitation and a new key
