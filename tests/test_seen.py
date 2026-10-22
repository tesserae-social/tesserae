"""What a member has seen: the card's "a new letter" goes once the room is opened.

How far a member has read in each room is kept with them, in
members/<pseudonym>/seen.json, and never in the room: so it is the same in
either layout, and the move into rooms does not know of it.
"""

import json

import pytest

from conftest import FOUNDER_NAME, post, write
from test_rooms import card, letter, member, member_vault  # noqa: F401 - fixtures

NEW = "a new letter from the first one"


@pytest.fixture
def seen_file(data_dir):
    return data_dir / "members" / FOUNDER_NAME / "seen.json"


def a_letter_came(room, at="2026-10-14T06-30-00Z"):
    letter(room, "read", "founder-2026-10-11T09-00-00Z")
    letter(room, "outgoing", "to-founder-" + at)


def test_opening_the_room_clears_the_line(founder, room, seen_file):
    a_letter_came(room)
    assert NEW in card(founder)
    assert founder.get("/rooms/first").status_code == 200
    assert card(founder)[1:3] == ["14 October 2026 · from the first one", "nothing is waiting"]
    assert json.loads(seen_file.read_text(encoding="utf-8")) == {"first": "2026-10-14T06-30-00Z"}


def test_a_newer_letter_brings_it_back(founder, room):
    a_letter_came(room)
    founder.get("/rooms/first")
    letter(room, "outgoing", "to-founder-2026-10-15T06-30-00Z")
    assert card(founder)[1:3] == ["15 October 2026 · from the first one", NEW]


def test_writing_back_still_clears_it_unopened(founder, room, seen_file):
    a_letter_came(room)
    letter(room, "incoming", "founder-2026-10-15T21-00-00Z")
    assert card(founder)[1:3] == ["15 October 2026 · from you", "your letter is waiting to be read"]
    assert not seen_file.exists()


def test_after_writing_back_a_letter_is_new_again(founder, room):
    a_letter_came(room)
    founder.get("/rooms/first")
    letter(room, "read", "founder-2026-10-15T21-00-00Z")
    letter(room, "outgoing", "to-founder-2026-10-16T06-30-00Z")
    assert NEW in card(founder)


def test_leaving_a_letter_marks_nothing_seen(founder, room, seen_file):
    a_letter_came(room)
    assert post(founder, "/rooms/first", data={"letter": "Dear first one."}).status_code == 302
    assert not seen_file.exists()
    assert card(founder)[2] == "your letter is waiting to be read"


def test_a_visitor_writes_nothing(visitor, founder, room, data_dir):
    a_letter_came(room)
    answer = visitor.get("/rooms/first")
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/login")
    assert not list((data_dir / "members").rglob("seen.json"))


def test_a_member_not_of_the_room_writes_nothing(member, founder, room, data_dir):
    a_letter_came(room)
    answer = member.get("/rooms/first")  # a member with no room is sent to log in, as a visitor is
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/login")
    assert not list((data_dir / "members").rglob("seen.json"))
    assert NEW in card(founder)


def test_seen_never_moves_backwards(founder, room, seen_file, hearth):
    a_letter_came(room)
    write(seen_file, json.dumps({"first": "2026-10-20T00-00-00Z", "elsewhere": "x"}))
    founder.get("/rooms/first")
    assert json.loads(seen_file.read_text(encoding="utf-8")) == {
        "first": "2026-10-20T00-00-00Z", "elsewhere": "x"}

    hearth.members.mark_seen(FOUNDER_NAME, "first", "2026-10-01T00-00-00Z")
    assert hearth.members.seen(FOUNDER_NAME, "first") == "2026-10-20T00-00-00Z"
    hearth.members.mark_seen(FOUNDER_NAME, "first", "2026-10-21T00-00-00Z")
    assert hearth.members.seen(FOUNDER_NAME, "first") == "2026-10-21T00-00-00Z"


def test_opening_a_room_with_nothing_from_them_writes_nothing(founder, room, seen_file):
    letter(room, "read", "founder-2026-10-11T09-00-00Z")
    founder.get("/rooms/first")
    assert not seen_file.exists()


@pytest.mark.parametrize("held", ["not json at all {", "[]", '"first"', '{"first": 5}', ""])
def test_an_unreadable_seen_is_nothing_seen(founder, room, seen_file, held):
    a_letter_came(room)
    write(seen_file, held)
    assert card(founder)[1:3] == ["14 October 2026 · from the first one", NEW]
    assert founder.get("/rooms/first").status_code == 200
    assert json.loads(seen_file.read_text(encoding="utf-8")) == {"first": "2026-10-14T06-30-00Z"}
    assert NEW not in card(founder)


def test_seen_is_the_members_and_not_the_rooms(founder, room, data_dir, seen_file):
    a_letter_came(room)
    founder.get("/rooms/first")
    assert seen_file.is_file()
    assert not list(room.rglob("seen*")) and not list((data_dir / "rooms").rglob("seen*"))
