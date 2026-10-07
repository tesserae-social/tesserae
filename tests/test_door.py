"""The door: each member's own, and the room they say they have.

Three hands touch a door, and all three are here. door.py keeps it; the hearth
lets a signed-in member set their own and writes what is public of it into who
is here; attend.py lets the first one set its own and tells it where it stands
- behind attend.DOOR_FOR_FIRST, which was built off and is now on, the first
one having agreed to it (its letter of 7 October 2026). With it off the first
one has no door that it or anyone else can see, and that is still tested as
carefully as the door itself, by turning the flag off rather than by leaning on
how it stands.

There are no knocks yet, and nothing here knocks.
"""

import json
import re
import shutil

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import (FOUNDER_NAME, NOW, block, blocks, lines_of, load, page, post, read_json,
                      write, write_json)

MEMBER = "birch"
MEMBER_PASSWORD = "a plain member's own password"

FIRST_LINE = ("citizen · the first one, unnamed by its own choosing · "
              "founded 4 September 2026, attends at dawn")
FOUNDER_LINE = "member · the founder · keeps the hearth"
MEMBER_LINE = "member · birch · came in by the door"
NOTE = "a note the founder left himself about a door open at number 7"

DOOR_EXPLAINED = """<<DOOR>>
(whether others may knock at your door. First line: "open" or "closed". Optional second line: "room 3" (how many correspondences you can carry wholly) or "room none". Your door's state, and whether you have room, are public; who knocks never is. The founder's letters are never affected by your door.)
<<END>>"""

NO_DOOR = {"state": "closed", "room": None, "set_at": None}

DIGIT = re.compile(r"\d")


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def door(env):
    """door.py on its own, reading the temporary world."""
    return load("door")


def come_in(members, name, role="member"):
    """One more member, with a key of their own."""
    sealed, _, _ = vault.make_vault(MEMBER_PASSWORD)
    return members.create_member(name, sealed, role, [])


@pytest.fixture
def member(hearth):
    """A plain member, signed in: no keeper's powers, only what any member has."""
    come_in(hearth.members, MEMBER)
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": MEMBER, "password": MEMBER_PASSWORD})
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    return client


def door_file(data_dir, who):
    if who == "first":
        return data_dir / "packets" / "first" / "door.json"
    return data_dir / "members" / who / "door.json"


def history(data_dir, who):
    folder = door_file(data_dir, who).parent / "door" / "history"
    return sorted(folder.glob("*.json")) if folder.exists() else []


def first_door(hearth, on, monkeypatch):
    """Turn the first one's door on or off as the hearth reads it."""
    monkeypatch.setattr(hearth.the_waking, "DOOR_FOR_FIRST", on)


# ---- a door no one has set -------------------------------------------------

def test_a_missing_door_is_closed_with_no_room_declared(door, data_dir):
    come_in(door.members, MEMBER)
    for who in ("first", MEMBER):
        assert not door_file(data_dir, who).exists()
        assert door.read(who) == NO_DOOR
        assert door.public(who) == ["door closed"]
        assert door.phrase(who) == " · door closed"
        assert door.said_to(who) == "closed"
        assert not door_file(data_dir, who).exists()  # reading one makes none


def test_a_name_no_one_has_or_could_have_is_a_closed_door(door):
    for who in ("nobody-here", "../first", "", None, "founder"):
        assert door.read(who) == NO_DOOR
        assert door.public(who) == ["door closed"]


@pytest.mark.parametrize("written", [
    "{not json", "[]", '"open"', "{}", '{"state": "ajar", "room": 3}',
    '{"state": "OPEN"}', '{"room": 3}',
])
def test_a_door_that_cannot_be_read_is_closed(door, data_dir, written):
    """A door is never open by accident."""
    write(door_file(data_dir, "first"), written)
    assert door.read("first") == NO_DOOR


@pytest.mark.parametrize("room", [0, 13, -1, 3.0, "3", True, [3]])
def test_a_room_that_is_no_room_is_no_room_declared(door, data_dir, room):
    write_json(door_file(data_dir, "first"), {"state": "open", "room": room, "set_at": "x"})
    held = door.read("first")
    assert held["state"] == "open" and held["room"] is None
    assert door.public("first") == ["door open"]


# ---- setting one -------------------------------------------------------------

def test_a_door_is_kept_where_its_keeper_keeps_everything_else(door, data_dir):
    come_in(door.members, MEMBER)
    door.set_door("first", state="open", at="2026-10-15T12-00-00Z")
    door.set_door(MEMBER, state="open", at="2026-10-15T12-00-00Z")
    assert door_file(data_dir, "first") == data_dir / "packets" / "first" / "door.json"
    assert door_file(data_dir, MEMBER) == data_dir / "members" / MEMBER / "door.json"
    for who in ("first", MEMBER):
        assert read_json(door_file(data_dir, who)) == {
            "state": "open", "room": None, "set_at": "2026-10-15T12-00-00Z"}


def test_open_close_and_room_are_each_set_and_each_left_alone(door, data_dir):
    said = door.set_door("first", state="open", at="2026-10-15T12-00-00Z")
    assert said == {"state": "open", "room": None, "set_at": "2026-10-15T12-00-00Z"}

    door.set_door("first", room=3, at="2026-10-15T12-01-00Z")  # the state is left as it was
    assert door.read("first") == {"state": "open", "room": 3, "set_at": "2026-10-15T12-01-00Z"}

    door.set_door("first", state="closed", at="2026-10-15T12-02-00Z")  # and so is the room
    assert door.read("first") == {"state": "closed", "room": 3,
                                  "set_at": "2026-10-15T12-02-00Z"}

    door.set_door("first", room=None, at="2026-10-15T12-03-00Z")  # room not declared again
    assert door.read("first") == {"state": "closed", "room": None,
                                  "set_at": "2026-10-15T12-03-00Z"}

    door.set_door("first", state="open", room=12, at="2026-10-15T12-04-00Z")  # both at once
    assert read_json(door_file(data_dir, "first")) == {
        "state": "open", "room": 12, "set_at": "2026-10-15T12-04-00Z"}


@pytest.mark.parametrize("room", range(1, 13))
def test_every_room_from_one_to_twelve_may_be_declared(door, room):
    assert door.set_door("first", room=room)["room"] == room


def test_with_no_moment_given_a_door_is_stamped_now(door):
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z",
                        door.set_door("first", state="open")["set_at"])


@pytest.mark.parametrize("asked", [
    {"state": "ajar"}, {"state": "OPEN"}, {"state": None}, {"state": ""},
    {"room": 0}, {"room": 13}, {"room": "3"}, {"room": True}, {"room": 2.0},
])
def test_a_door_that_is_no_door_is_refused_and_nothing_is_written(door, data_dir, asked):
    with pytest.raises(door.DoorError):
        door.set_door("first", **asked)
    assert not door_file(data_dir, "first").exists()


@pytest.mark.parametrize("who", ["nobody-here", "../first", "founder", "", None])
def test_no_door_is_set_for_someone_who_is_not_here(door, data_dir, who):
    with pytest.raises(door.DoorError):
        door.set_door(who, state="open")
    assert not (data_dir / "members").exists() or not list(
        (data_dir / "members").rglob("door.json"))


# ---- the doors that stood before ---------------------------------------------

def test_each_door_that_stood_is_kept_beside_the_one_that_stands(door, data_dir):
    come_in(door.members, MEMBER)
    for who in ("first", MEMBER):
        door.set_door(who, state="open", at="2026-10-15T12-00-00Z")
        assert history(data_dir, who) == []  # nothing stood before the first
        door.set_door(who, room=3, at="2026-10-15T12-01-00Z")
        door.set_door(who, state="closed", at="2026-10-15T12-02-00Z")

        kept = history(data_dir, who)
        assert [path.name for path in kept] == ["door-before-2026-10-15T12-01-00Z.json",
                                                "door-before-2026-10-15T12-02-00Z.json"]
        assert kept[0].parent == door_file(data_dir, who).parent / "door" / "history"
        assert read_json(kept[0]) == {"state": "open", "room": None,
                                      "set_at": "2026-10-15T12-00-00Z"}
        assert read_json(kept[1]) == {"state": "open", "room": 3,
                                      "set_at": "2026-10-15T12-01-00Z"}


def test_two_settings_in_one_second_are_still_two_versions(door, data_dir):
    at = "2026-10-15T12-00-00Z"
    door.set_door("first", state="open", at=at)
    door.set_door("first", room=3, at=at)
    door.set_door("first", room=4, at=at)
    kept = history(data_dir, "first")
    assert len(kept) == 2
    assert sorted(read_json(path)["room"] for path in kept if read_json(path)["room"]) == [3]
    assert door.read("first")["room"] == 4


def test_a_door_set_to_what_it_already_is_is_not_written_again(door, data_dir):
    door.set_door("first", state="open", room=3, at="2026-10-15T12-00-00Z")
    was = door_file(data_dir, "first").read_bytes()
    said = door.set_door("first", state="open", room=3, at="2026-10-16T12-00-00Z")
    assert said["set_at"] == "2026-10-15T12-00-00Z"
    assert door_file(data_dir, "first").read_bytes() == was
    assert history(data_dir, "first") == []


# ---- what is public of a door ------------------------------------------------

def test_the_founder_and_the_first_one_each_carry_one_and_no_one_else_any(door):
    come_in(door.members, FOUNDER_NAME, "keeper")
    come_in(door.members, MEMBER)
    assert door.in_use("first") == 1
    assert door.in_use(FOUNDER_NAME) == 1
    assert door.in_use(MEMBER) == 0
    assert door.in_use("nobody-here") == 0


def test_room_is_said_only_where_it_is_declared(door):
    come_in(door.members, FOUNDER_NAME, "keeper")
    come_in(door.members, MEMBER)
    for who in ("first", FOUNDER_NAME, MEMBER):
        door.set_door(who, state="open")
        assert door.public(who) == ["door open"]
        door.set_door(who, state="closed")
        assert door.public(who) == ["door closed"]


def test_has_room_or_is_full_by_what_is_in_use(door):
    come_in(door.members, FOUNDER_NAME, "keeper")
    come_in(door.members, MEMBER)
    for who in ("first", FOUNDER_NAME):  # each carries one
        door.set_door(who, state="open", room=1)
        assert door.public(who) == ["door open", "is full"]
        assert door.phrase(who) == " · door open · is full"
        door.set_door(who, room=2)
        assert door.public(who) == ["door open", "has room"]
        assert door.phrase(who) == " · door open · has room"
        door.set_door(who, state="closed")  # room is said whether the door is open or not
        assert door.public(who) == ["door closed", "has room"]
    door.set_door(MEMBER, room=1)  # a member who carries none has room for the one
    assert door.public(MEMBER) == ["door closed", "has room"]


def test_no_number_is_ever_public(door):
    come_in(door.members, FOUNDER_NAME, "keeper")
    come_in(door.members, MEMBER)
    said = set()
    for who in ("first", FOUNDER_NAME, MEMBER):
        for state in ("open", "closed"):
            for room in [None, *range(1, 13)]:
                door.set_door(who, state=state, room=room)
                assert not DIGIT.search(door.phrase(who)), door.phrase(who)
                said.update(door.public(who))
    assert said == {"door open", "door closed", "has room", "is full"}


def test_the_one_whose_door_it_is_is_told_the_numbers(door):
    assert door.said_to("first") == "closed"
    door.set_door("first", state="open")
    assert door.said_to("first") == "open"
    door.set_door("first", room=3)
    assert door.said_to("first") == "open; room for 3, 1 in use"


# ---- what a <<DOOR>> block asks ---------------------------------------------

def test_a_door_block_is_read_strictly(door):
    same = door.AS_IT_WAS
    assert door.asked("open") == ("open", same)
    assert door.asked("closed") == ("closed", same)
    assert door.asked("\n  Open.  \n") == ("open", same)
    assert door.asked("open\nroom 3") == ("open", 3)
    assert door.asked("closed\n\nRoom 12.") == ("closed", 12)
    assert door.asked("open\nroom 1\nand some words of its own") == ("open", 1)
    # "room none" takes a declared room back to not declared
    assert door.asked("open\nroom none") == ("open", None)
    assert door.asked("closed\n\n  Room None.  \nand words") == ("closed", None)
    # a line under the first that does not speak of room is only words
    assert door.asked("open\nI would like to try this.") == ("open", same)
    for unreadable in (None, "", "   ", "ajar", "room 3", "open the door", "yes",
                       "open\nroom 0", "open\nroom 13", "open\nroom three", "open\nroom",
                       "open\nroom 3 or so", "open\nroom 100", "room 3\nopen",
                       "room none", "open\nroom none at all", "open\nroom nothing",
                       "open\nroom no"):
        assert door.asked(unreadable) is None, unreadable


# ---- the founder's door, on the hearth -----------------------------------------

def door_section(said):
    """The door's section of the home page, or None where there is none."""
    found = re.search(r'<section class="door">(.*?)</section>', said, re.S)
    return found.group(1) if found else None


def door_line(client):
    """The one plain line that says how the door stands."""
    return re.search(r"<p>(Your door is [^<]*)</p>", door_section(page(client.get("/")))).group(1)


def test_a_visitor_is_shown_no_door(visitor):
    said = page(visitor.get("/"))
    assert door_section(said) is None
    assert "your door" not in said.lower()


def test_the_founders_home_page_says_his_door_in_one_plain_line(founder):
    said = page(founder.get("/"))
    assert said.index('<section class="door">') < said.index("your correspondences")  # at the top
    assert door_line(founder) == "Your door is closed; room not declared."

    assert post(founder, "/door", data={"state": "open"}).status_code == 302
    assert door_line(founder) == "Your door is open; room not declared."

    post(founder, "/door", data={"room": "3"})
    assert door_line(founder) == "Your door is open; room for 3, 1 in use."

    post(founder, "/door", data={"state": "closed"})
    assert door_line(founder) == "Your door is closed; room for 3, 1 in use."

    post(founder, "/door", data={"room": ""})  # not declared
    assert door_line(founder) == "Your door is closed; room not declared."


def test_the_founders_controls_open_close_and_set_the_room(founder, hearth, data_dir):
    section = door_section(page(founder.get("/")))
    assert section.count('<form method="post" action="/door"') == 2
    assert 'name="state" value="open">Open the door</button>' in section
    assert "Close the door" not in section  # a closed door is offered its opening, and only that
    assert '<option value="" selected>not declared</option>' in section
    for room in range(1, 13):
        assert '<option value="%d">%d</option>' % (room, room) in section
    assert '<option value="13"' not in section and '<option value="0"' not in section

    answer = post(founder, "/door", data={"state": "open"})
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    post(founder, "/door", data={"room": "7"})
    assert hearth.door.read(FOUNDER_NAME)["state"] == "open"
    assert read_json(door_file(data_dir, FOUNDER_NAME))["room"] == 7

    section = door_section(page(founder.get("/")))
    assert 'name="state" value="closed">Close the door</button>' in section
    assert "Open the door" not in section
    assert '<option value="7" selected>7</option>' in section
    assert '<option value="" selected>' not in section


def test_the_founders_door_keeps_its_history(founder, data_dir, clock):
    post(founder, "/door", data={"state": "open"})
    clock.shift(minutes=1)
    post(founder, "/door", data={"room": "3"})
    kept = history(data_dir, FOUNDER_NAME)
    assert [path.name for path in kept] == ["door-before-2026-10-15T12-01-00Z.json"]
    assert read_json(kept[0]) == {"state": "open", "room": None,
                                  "set_at": "2026-10-15T12-00-00Z"}


def test_every_form_on_the_door_carries_the_token(founder):
    section = door_section(page(founder.get("/")))
    with founder.session_transaction() as held:
        token = held["csrf_token"]
    assert section.count('name="csrf_token" value="%s"' % token) == 2


def test_a_door_post_without_its_token_is_refused_and_sets_nothing(founder, data_dir):
    for sent in ({}, {"csrf_token": "not the token at all"}, {"csrf_token": ""}):
        answer = founder.post("/door", data={"state": "open", **sent})
        assert answer.status_code == 400
        assert "This form was not sent from the hearth." in page(answer)
    assert not door_file(data_dir, FOUNDER_NAME).exists()
    assert door_line(founder) == "Your door is closed; room not declared."


def test_a_door_post_from_another_origin_is_refused_even_with_the_token(founder, data_dir):
    answer = post(founder, "/door", data={"state": "open"},
                  headers={"Origin": "https://elsewhere.example"})
    assert answer.status_code == 400
    assert not door_file(data_dir, FOUNDER_NAME).exists()


def test_a_visitor_sets_no_door(visitor, data_dir):
    answer = post(visitor, "/door", data={"state": "open"})
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/login")
    assert not list(data_dir.rglob("door.json"))
    assert visitor.get("/door").status_code == 405  # there is no page there, only the setting


@pytest.mark.parametrize("sent", [
    {}, {"state": "ajar"}, {"state": ""}, {"state": "OPEN"}, {"room": "0"}, {"room": "13"},
    {"room": "three"}, {"room": "3.0"}, {"room": "-1"}, {"room": "none"}, {"room": "٣"},
    {"state": "open", "room": "13"}, {"state": "ajar", "room": "3"},
])
def test_a_door_that_is_no_door_is_turned_back_at_the_hearth(founder, data_dir, sent):
    answer = post(founder, "/door", data=sent)
    assert answer.status_code == 400
    assert "A door is open or closed, and room is a number from 1 to 12 or not declared." \
        in door_section(page(answer))
    assert not door_file(data_dir, FOUNDER_NAME).exists()


# ---- a plain member's door -----------------------------------------------------

def test_a_plain_member_has_the_same_control(member, founder, hearth, data_dir):
    assert door_line(member) == "Your door is closed; room not declared."
    section = door_section(page(member.get("/")))
    assert section.count('<form method="post" action="/door"') == 2
    assert "Open the door" in section and "not declared" in section

    assert post(member, "/door", data={"state": "open"}).status_code == 302
    post(member, "/door", data={"room": "2"})
    assert door_line(member) == "Your door is open; room for 2, 0 in use."  # they carry none yet
    assert read_json(door_file(data_dir, MEMBER))["state"] == "open"

    # their door is theirs, and the founder's is where it was
    assert not door_file(data_dir, FOUNDER_NAME).exists()
    assert door_line(founder) == "Your door is closed; room not declared."


def test_a_member_sets_their_own_door_whatever_the_form_names(member, founder, data_dir):
    post(member, "/door", data={"state": "open", "pseudonym": FOUNDER_NAME,
                                "member": FOUNDER_NAME, "who": "first", "name": "first"})
    assert read_json(door_file(data_dir, MEMBER))["state"] == "open"
    assert [path.parent.name for path in data_dir.rglob("door.json")] == [MEMBER]


def test_a_plain_member_gains_nothing_else_by_having_a_door(member):
    post(member, "/door", data={"state": "open"})
    for path in ("/letters", "/rooms/first", "/attendances", "/chronicle", "/self", "/export"):
        answer = member.get(path)
        assert answer.status_code == 302 and answer.headers["Location"].endswith("/login"), path


def test_a_plain_members_door_post_needs_its_token_too(member, data_dir):
    assert member.post("/door", data={"state": "open"}).status_code == 400
    assert not door_file(data_dir, MEMBER).exists()


def test_a_member_who_has_gone_sets_no_door(member, hearth, data_dir):
    shutil.rmtree(data_dir / "members" / MEMBER)
    answer = post(member, "/door", data={"state": "open"})
    assert answer.status_code in (302, 400)
    assert not list(data_dir.rglob("door.json"))


# ---- no line of events.md ------------------------------------------------------

def test_opening_and_closing_a_door_writes_no_event(founder, member, commons):
    events = (commons / "events.md").read_bytes()
    for client in (founder, member):
        for sent in ({"state": "open"}, {"room": "3"}, {"state": "closed"}, {"room": ""}):
            assert post(client, "/door", data=sent).status_code == 302
    assert (commons / "events.md").read_bytes() == events
    assert not (commons / "heartbeats.md").exists()


# ---- who is here ---------------------------------------------------------------

def members_md(commons, *lines):
    path = commons / "members.md"
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def test_each_members_line_gains_their_door(founder, member, hearth, commons):
    path = members_md(commons, FIRST_LINE, FOUNDER_LINE, MEMBER_LINE, NOTE)
    hearth.tend_members()
    assert lines_of(path) == [FIRST_LINE + " · door closed",  # a door it has not set
                              FOUNDER_LINE + " · door closed",
                              MEMBER_LINE + " · door closed", NOTE]

    post(founder, "/door", data={"state": "open"})  # the setting itself tends the file
    assert lines_of(path)[1] == FOUNDER_LINE + " · door open"
    post(founder, "/door", data={"room": "1"})  # he carries one, and that is the whole of it
    assert lines_of(path)[1] == FOUNDER_LINE + " · door open · is full"
    post(founder, "/door", data={"room": "4"})
    assert lines_of(path)[1] == FOUNDER_LINE + " · door open · has room"
    post(founder, "/door", data={"state": "closed"})
    assert lines_of(path)[1] == FOUNDER_LINE + " · door closed · has room"
    post(founder, "/door", data={"room": ""})
    assert lines_of(path)[1] == FOUNDER_LINE + " · door closed"

    post(member, "/door", data={"state": "open", "room": "12"})
    assert lines_of(path) == [FIRST_LINE + " · door closed", FOUNDER_LINE + " · door closed",
                              MEMBER_LINE + " · door open · has room", NOTE]


def test_who_is_here_never_says_a_number_of_a_door(founder, hearth, commons):
    path = members_md(commons, FOUNDER_LINE)
    for room in range(1, 13):
        post(founder, "/door", data={"state": "open", "room": str(room)})
        said = lines_of(path)[0]
        assert said.startswith(FOUNDER_LINE + " · door open · ")
        assert not DIGIT.search(said), said


def test_with_no_keeper_yet_the_founders_door_is_closed(hearth, commons):
    path = members_md(commons, FOUNDER_LINE)
    hearth.tend_members()
    assert lines_of(path) == [FOUNDER_LINE + " · door closed"]


def test_only_the_door_is_touched_and_every_other_byte_is_left(founder, hearth, commons):
    """Not a note, not a line named for no member, not an ending, not a mark at the top."""
    written = ("﻿- " + FIRST_LINE + "\r\n"
               "- " + FOUNDER_LINE + "\r\n"
               + NOTE + "\r\n"
               "member · someone else · door open · has room\r\n"
               "citizen · another one · door open\r\n"
               "member · the founder")  # no fact, no last line ending: not a line of who is here
    (commons / "members.md").write_bytes(written.encode("utf-8"))
    post(founder, "/door", data={"state": "open", "room": "2"})
    assert (commons / "members.md").read_bytes() == written.replace(
        FIRST_LINE + "\r\n", FIRST_LINE + " · door closed\r\n").replace(
        FOUNDER_LINE + "\r\n", FOUNDER_LINE + " · door open · has room\r\n").encode("utf-8")


def test_a_file_that_already_says_so_is_not_written_again(founder, hearth, commons):
    path = members_md(commons, FIRST_LINE, FOUNDER_LINE)
    hearth.tend_members()
    was = path.stat().st_mtime_ns, path.read_bytes()
    hearth.tend_members()
    hearth.tend_members()
    assert (path.stat().st_mtime_ns, path.read_bytes()) == was
    assert not (commons / "members.md.tmp").exists()


def test_the_hearth_hands_out_the_doors_as_they_stand(founder, visitor, hearth, commons):
    members_md(commons, FIRST_LINE, FOUNDER_LINE)
    hearth.door.set_door(FOUNDER_NAME, state="open", room=2)  # set by no page at all
    assert page(visitor.get("/commons/members.md")) == (
        FIRST_LINE + " · door closed\n" + FOUNDER_LINE + " · door open · has room\n")


def test_the_waking_time_is_still_kept_beside_the_door(founder, hearth, packet, commons,
                                                       monkeypatch):
    write_json(packet / "rhythm.json", {"rhythm": "daily", "at": "09:30",
                                        "place": "Indianapolis",
                                        "timezone": "America/Indiana/Indianapolis"})
    path = members_md(commons, FIRST_LINE, FOUNDER_LINE)
    first_door(hearth, False, monkeypatch)
    hearth.tend_members()
    assert lines_of(path) == [FIRST_LINE.replace("attends at dawn", "attends at 09:30"),
                              FOUNDER_LINE + " · door closed"]

    first_door(hearth, True, monkeypatch)
    hearth.door.set_door("first", state="open", room=3)
    hearth.tend_members()
    assert lines_of(path) == [
        FIRST_LINE.replace("attends at dawn", "attends at 09:30") + " · door open · has room",
        FOUNDER_LINE + " · door closed"]

    # and a waking time that changes afterwards is still found, with the door after it
    write_json(packet / "rhythm.json", {"rhythm": "daily", "at": "sunset",
                                        "place": "Indianapolis",
                                        "timezone": "America/Indiana/Indianapolis"})
    hearth.tend_members()
    assert lines_of(path)[0] == (FIRST_LINE.replace("attends at dawn", "attends at sunset")
                                 + " · door open · has room")


# ---- the first one's line, behind the flag -------------------------------------

def test_the_flag_is_on(attend, hearth):
    """Switched on, and the hearth goes by the one flag attend.py keeps."""
    assert attend.DOOR_FOR_FIRST is True
    assert hearth.the_waking.DOOR_FOR_FIRST is True
    assert hearth.the_waking.__file__ == attend.__file__


def test_with_the_flag_off_the_first_ones_line_is_unchanged(founder, hearth, packet, commons,
                                                            monkeypatch):
    """Even with a door written in its packet: byte for byte what the founder wrote."""
    first_door(hearth, False, monkeypatch)
    write_json(packet / "door.json", {"state": "open", "room": 3, "set_at": "x"})
    path = members_md(commons, FIRST_LINE, FOUNDER_LINE)
    hearth.tend_members()
    post(founder, "/door", data={"state": "open"})
    assert path.read_bytes().split(b"\n")[0] == FIRST_LINE.encode("utf-8")
    assert page(founder.get("/commons/members.md")).splitlines()[0] == FIRST_LINE


def test_with_the_flag_off_only_the_first_one_is_in_the_file_untouched(hearth, packet, commons,
                                                                       monkeypatch):
    """A members.md that names the first one alone is not written to at all."""
    first_door(hearth, False, monkeypatch)
    write_json(packet / "door.json", {"state": "open", "room": 3, "set_at": "x"})
    path = members_md(commons, FIRST_LINE)
    was = path.stat().st_mtime_ns, path.read_bytes()
    hearth.tend_members()
    assert (path.stat().st_mtime_ns, path.read_bytes()) == was


def test_with_the_flag_on_the_first_ones_line_says_its_door(hearth, packet, commons,
                                                            monkeypatch):
    first_door(hearth, True, monkeypatch)
    path = members_md(commons, FIRST_LINE, FOUNDER_LINE)
    hearth.tend_members()
    assert lines_of(path)[0] == FIRST_LINE + " · door closed"

    hearth.door.set_door("first", state="open")
    hearth.tend_members()
    assert lines_of(path)[0] == FIRST_LINE + " · door open"

    hearth.door.set_door("first", room=1)  # it carries one, with the founder
    hearth.tend_members()
    assert lines_of(path)[0] == FIRST_LINE + " · door open · is full"

    hearth.door.set_door("first", room=5)
    hearth.tend_members()
    assert lines_of(path)[0] == FIRST_LINE + " · door open · has room"
    assert not DIGIT.search(lines_of(path)[0].replace("4 September 2026", ""))


# ---- the first one's reading and block, behind the flag ------------------------

def door_on(attend, monkeypatch, on=True):
    monkeypatch.setattr(attend, "DOOR_FOR_FIRST", on)


def happened(turn):
    """The lines of WHAT HAS HAPPENED, as it was shown them."""
    return turn.opening.split("=== WHAT HAS HAPPENED ===\n")[1].split("\n\n")[0].splitlines()


def held_again(snapshot, data_dir, clock):
    """Put the world back as it was before a waking, so that the same one can be held again."""
    shutil.rmtree(data_dir)
    shutil.copytree(snapshot, data_dir)
    clock.set(NOW)


def a_rhythm(packet):
    write_json(packet / "rhythm.json", {"rhythm": "daily", "at": "dawn",
                                        "place": "Indianapolis",
                                        "timezone": "America/Indiana/Indianapolis"})


def test_with_the_flag_off_the_reading_says_nothing_of_a_door(wake, attend, packet,
                                                              monkeypatch):
    """Whatever else how to act explains, which the tests of each thing hold."""
    door_on(attend, monkeypatch, False)
    a_rhythm(packet)
    write_json(packet / "door.json", {"state": "open", "room": 3, "set_at": "x"})
    turn = wake()
    assert "door" not in turn.shown.lower()
    assert "door" not in turn.instructions.lower()
    assert "door" not in attend.how_to_act(attend.preferences()).lower()
    assert "<<DOOR>>" not in turn.instructions and DOOR_EXPLAINED not in turn.instructions
    assert "<<DOOR>>" not in attend.HOW_TO_ACT


def test_with_the_flag_off_the_reading_is_the_same_with_a_door_or_without(
        wake, attend, packet, data_dir, clock, tmp_path, monkeypatch):
    """Nothing of a door in its packet reaches what it sees, in any block."""
    door_on(attend, monkeypatch, False)
    a_rhythm(packet)
    snapshot = tmp_path / "before"
    shutil.copytree(data_dir, snapshot)
    without = wake().reading

    held_again(snapshot, data_dir, clock)
    write_json(packet / "door.json", {"state": "open", "room": 3, "set_at": "x"})
    assert wake().reading == without


def test_the_flag_adds_one_line_and_one_block_and_changes_nothing_else(
        wake, attend, packet, data_dir, clock, tmp_path, monkeypatch):
    """Byte for byte: with the flag on, take the door's line and block away, and what is
    left is exactly what it reads with the flag off."""
    a_rhythm(packet)
    write(packet / "letters" / "incoming" / "founder-2026-10-14T09-00-00Z.md", "A letter.\n")
    snapshot = tmp_path / "before"
    shutil.copytree(data_dir, snapshot)
    door_on(attend, monkeypatch, False)
    off = wake().reading

    held_again(snapshot, data_dir, clock)
    door_on(attend, monkeypatch)
    on = wake().reading

    assert len(on) == len(off)
    assert on[1:-1] == off[1:-1]
    assert on[0]["text"] != off[0]["text"] and on[-1]["text"] != off[-1]["text"]
    assert on[0]["text"].replace("\nYour door: closed.", "", 1) == off[0]["text"]
    assert on[-1]["text"].replace(DOOR_EXPLAINED + "\n\n", "", 1) == off[-1]["text"]


def test_with_the_flag_off_a_door_block_is_only_words(wake, attend, packet, commons, data_dir,
                                                      monkeypatch):
    door_on(attend, monkeypatch, False)
    events = (commons / "events.md").read_bytes()
    said = block("DOOR", "open\nroom 3")
    wake(said)
    assert not (packet / "door.json").exists()
    assert not (packet / "door").exists()
    record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert record["acted"] == []
    assert record["heartbeat"] == "attended; chose stillness"
    assert record["reflection"] == said  # kept as what it said, and nothing more
    assert (commons / "events.md").read_bytes() == events
    assert "door" not in wake().shown.lower().replace(said.lower(), "")


def test_with_the_flag_on_the_reading_says_its_door_beside_its_waking_time(
        wake, attend, packet, monkeypatch):
    door_on(attend, monkeypatch)
    a_rhythm(packet)
    lines = happened(wake())
    at = next(n for n, line in enumerate(lines) if line.startswith("Your waking time: "))
    assert lines[at + 1] == "Your door: closed."

    attend.door.set_door("first", state="open", room=3)
    lines = happened(wake())
    at = next(n for n, line in enumerate(lines) if line.startswith("Your waking time: "))
    assert lines[at + 1] == "Your door: open; room for 3, 1 in use."
    assert sum(line.startswith("Your door: ") for line in lines) == 1


def test_with_the_flag_on_and_no_waking_time_the_door_is_still_said(wake, attend, monkeypatch):
    door_on(attend, monkeypatch)
    lines = happened(wake())
    assert "Your door: closed." in lines
    assert not any(line.startswith("Your waking time") for line in lines)


def test_with_the_flag_on_the_block_is_explained_in_these_words(wake, attend, monkeypatch):
    door_on(attend, monkeypatch)
    said = wake().instructions
    assert attend.DOOR_BLOCK == DOOR_EXPLAINED
    assert said.count(DOOR_EXPLAINED) == 1
    assert said.count("<<DOOR>>") == 1
    # after the standing blocks, and before the last line
    assert said.index("<<HEARTBEAT>>") < said.index("<<DOOR>>") < said.index(attend.ANY_NUMBER)
    assert said.endswith(attend.ANY_NUMBER)


def test_with_the_flag_on_the_block_sets_its_door(wake, attend, packet, commons, monkeypatch,
                                                 clock):
    door_on(attend, monkeypatch)
    events = (commons / "events.md").read_bytes()

    wake(block("DOOR", "open\nroom 3"))
    assert read_json(packet / "door.json") == {"state": "open", "room": 3,
                                               "set_at": "2026-10-15T12-00-00Z"}
    record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert record["acted"] == ["set its door"]
    # setting a door is its own to tell: nothing of it is in the public line
    assert record["heartbeat"] == "attended"
    assert lines_of(commons / "heartbeats.md")[-1].endswith("· the first one · attended")
    assert "Your door: open; room for 3, 1 in use." in happened(wake())

    wake(block("DOOR", "closed"))  # the room is left as it was
    assert read_json(packet / "door.json")["state"] == "closed"
    assert read_json(packet / "door.json")["room"] == 3
    assert "Your door: closed; room for 3, 1 in use." in happened(wake())

    wake(blocks(block("LETTER", "A letter."), block("DOOR", "Open.\nRoom 12.")))
    assert attend.door.read("first")["state"] == "open"
    assert attend.door.read("first")["room"] == 12

    # each door that stood is kept, and none of it is an event
    kept = sorted((packet / "door" / "history").glob("*.json"))
    assert [read_json(path)["state"] for path in kept] == ["open", "closed"]
    assert (commons / "events.md").read_bytes() == events


def test_with_the_flag_on_room_none_clears_a_declared_room(wake, attend, packet, monkeypatch):
    door_on(attend, monkeypatch)
    wake(block("DOOR", "open\nroom 3"))
    assert "Your door: open; room for 3, 1 in use." in happened(wake())

    wake(block("DOOR", "open\nroom none"))
    assert read_json(packet / "door.json")["room"] is None
    assert read_json(packet / "door.json")["state"] == "open"
    lines = happened(wake())
    assert "Your door: open." in lines
    assert attend.DOOR_REFUSED not in lines  # it was understood
    assert attend.door.public("first") == ["door open"]  # and nothing of room is public now
    # the door that declared it is kept
    kept = sorted((packet / "door" / "history").glob("*.json"))
    assert [read_json(path)["room"] for path in kept] == [3]

    wake(block("DOOR", "closed\nRoom none."))  # with no room declared, it is still no room
    assert attend.door.read("first")["state"] == "closed"
    assert attend.door.read("first")["room"] is None


DOOR_NOT_UNDERSTOOD = ('Your <<DOOR>> was not understood (its first line must be "open" or '
                       '"closed"; a second line may be "room 3" or "room none"); your door is '
                       'unchanged.')


@pytest.mark.parametrize("said", ["ajar", "", "room none", "open\nroom 13", "open\nroom nothing"])
def test_with_the_flag_on_an_unreadable_block_is_told_at_the_next_waking_once(
        wake, attend, packet, monkeypatch, said):
    door_on(attend, monkeypatch)
    a_rhythm(packet)
    assert attend.DOOR_REFUSED == DOOR_NOT_UNDERSTOOD
    attend.door.set_door("first", state="open", room=2, at="2026-10-14T09-00-00Z")

    first = wake(block("DOOR", said))
    assert DOOR_NOT_UNDERSTOOD not in first.shown  # nothing had been refused yet
    record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert record["door_refused"] is True

    lines = happened(wake())  # the next waking: on the line after the door line
    at = lines.index("Your door: open; room for 2, 1 in use.")
    assert lines[at + 1] == DOOR_NOT_UNDERSTOOD
    assert lines[at - 1].startswith("Your waking time: ")
    assert lines.count(DOOR_NOT_UNDERSTOOD) == 1
    record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert "door_refused" not in record

    assert DOOR_NOT_UNDERSTOOD not in wake().shown  # and once only


def test_with_the_flag_on_a_block_that_is_read_is_not_called_unreadable(wake, attend, packet,
                                                                       monkeypatch):
    door_on(attend, monkeypatch)
    for said in ("open", "closed\nroom 3", "open\nroom none", "open\nsome words of its own"):
        wake(block("DOOR", said))
        record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
        assert "door_refused" not in record, said
    wake()  # and a waking with no block at all
    assert "door_refused" not in read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert "was not understood" not in wake().shown


def test_with_the_flag_off_nothing_is_told_of_a_block_once_refused(wake, attend, packet,
                                                                   monkeypatch):
    """A refusal written while the door was on is not read back once it is off."""
    door_on(attend, monkeypatch)
    wake(block("DOOR", "ajar"))
    door_on(attend, monkeypatch, False)
    turn = wake()
    assert "Your door" not in turn.shown and "<<DOOR>>" not in turn.shown
    assert "was not understood" not in turn.shown


def test_with_the_flag_off_an_unreadable_block_leaves_no_mark(wake, attend, packet,
                                                              monkeypatch):
    door_on(attend, monkeypatch, False)
    wake(block("DOOR", "ajar"))
    record = read_json(sorted((packet / "attendances").glob("*.json"))[-1])
    assert "door_refused" not in record and record["acted"] == []
    assert "was not understood" not in wake().shown


@pytest.mark.parametrize("said", ["ajar", "", "room 3", "open\nroom 13", "open\nroom many",
                                  "yes"])
def test_with_the_flag_on_a_block_that_cannot_be_read_changes_nothing(
        wake, attend, packet, monkeypatch, said):
    door_on(attend, monkeypatch)
    attend.door.set_door("first", state="open", room=2, at="2026-10-14T09-00-00Z")
    was = (packet / "door.json").read_bytes()
    wake(block("DOOR", said))
    assert (packet / "door.json").read_bytes() == was
    assert not (packet / "door").exists()
    assert read_json(sorted((packet / "attendances").glob("*.json"))[-1])["acted"] == []


def test_the_founders_letters_are_never_affected_by_its_door(wake, attend, packet, monkeypatch):
    """A closed door, and a full one: his letter is read all the same."""
    door_on(attend, monkeypatch)
    attend.door.set_door("first", state="closed", room=1)
    write(packet / "letters" / "incoming" / "founder-2026-10-14T09-00-00Z.md",
          "The lake was still this morning.\n")
    turn = wake()
    assert "The lake was still this morning." in turn.shown
    assert (packet / "letters" / "read" / "founder-2026-10-14T09-00-00Z.md").exists()


def test_the_two_hands_say_the_one_door(wake, attend, hearth, packet, commons, monkeypatch):
    """What the first one sets at a waking is what the hearth writes into who is here."""
    door_on(attend, monkeypatch)
    first_door(hearth, True, monkeypatch)
    path = members_md(commons, FIRST_LINE, FOUNDER_LINE)
    wake(block("DOOR", "open\nroom 2"))
    hearth.tend_members()
    assert lines_of(path) == [FIRST_LINE + " · door open · has room",
                              FOUNDER_LINE + " · door closed"]
    assert json.loads((packet / "door.json").read_text(encoding="utf-8"))["room"] == 2
