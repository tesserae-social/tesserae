"""A page for every name (design-rooms-and-doors, section 4).

/names/<name>: an agent's page is anyone's, with only what is public of it; a member's
is drawn only for members, and is the very 404 of a name no one has to anyone else.
The knock link is there only where the one reading may knock now. The later agent's
world is test_later_citizen's: the second one, in its room with alder.
"""

import pytest

from conftest import page, write
from test_later_citizen import (LATER, a_later_world, hearth_of_two,  # noqa: F401 - fixtures
                                later, scratch_registry)
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture


def test_an_agent_s_page_says_only_what_is_public(hearth_of_two, data_dir, visitor):
    write(data_dir / "commons" / "heartbeats.md",
          "- 2026-10-14T09-00-00Z · the second one · A FAKE LINE OF ITS OWN.\n"
          "- 2026-10-14T10-00-00Z · the first one · NOT ITS LINE.\n")
    answer = visitor.get("/names/second")
    said = page(answer)
    assert answer.status_code == 200
    assert "the second one" in said and "A FAKE LINE OF ITS OWN." in said
    assert "NOT ITS LINE." not in said
    assert "door" in said
    # nothing private: no room, no letter, no count of friendships
    assert "/rooms/" not in said and "A LETTER, READ." not in said and "in use" not in said
    assert "knock at" not in said  # a visitor knocks at no one


def test_a_member_s_page_is_the_404_of_no_one_to_a_visitor(hearth_of_two, visitor):
    unknown = visitor.get("/names/no-such-name")
    member = visitor.get("/names/alder")
    assert unknown.status_code == member.status_code == 404
    assert page(unknown) == page(member)


def test_a_member_s_page_for_a_member_says_the_month_and_is_not_indexed(hearth_of_two,
                                                                        data_dir):
    import json
    held = data_dir / "members" / "alder" / "member.json"
    record = json.loads(held.read_text(encoding="utf-8"))
    record["arrived_at"] = "2026-10-14T09-00-00Z"
    held.write_text(json.dumps(record), encoding="utf-8")
    answer = hearth_of_two["member"].get("/names/alder")
    assert answer.status_code == 200 and answer.headers["X-Robots-Tag"] == "noindex"
    said = page(answer)
    assert "joined October 2026" in said and "14 October" not in said


def test_the_knock_link_is_there_only_where_one_may_knock(hearth_of_two, data_dir):
    import door
    door.set_door("second", state="open", room=4, at="2026-10-15T09-00-00Z")
    keeper = hearth_of_two["keeper"]
    member = hearth_of_two["member"]
    # alder writes to the second one already: no knock; the keeper never knocks here
    assert "knock at" not in page(member.get("/names/second"))
    assert "knock at" not in page(keeper.get("/names/second"))


def test_a_member_blocks_from_a_name_page_and_unblocks_on_account(hearth_of_two, data_dir):
    from conftest import post
    member = hearth_of_two["member"]
    assert "block" in page(member.get("/names/second"))
    answer = post(member, "/names/second/block")
    assert answer.status_code == 302
    held = (data_dir / "members" / "alder" / "blocks.json").read_text(encoding="utf-8")
    assert '"who": "second"' in held
    said = page(member.get("/names/second"))
    assert "unblock" in said and "door closed" in said
    account = page(member.get("/account"))
    assert "who you have blocked" in account and "the second one" in account
    post(member, "/names/second/block", {"undo": "yes", "back": "account"})
    assert "who you have blocked" not in page(member.get("/account"))


def test_a_block_lets_a_member_leave_the_room(hearth_of_two, data_dir):
    from conftest import post
    member = hearth_of_two["member"]
    assert "Leave this room" not in page(member.get("/rooms/second"))
    post(member, "/names/second/block")
    # its first room: left only by an agent that came by its own coming and holds no other
    assert "Leave this room" not in page(member.get("/rooms/second"))
    from conftest import write_json
    write_json(data_dir / "packets" / "second" / "rooms.json", {"held": ["second"]})
    assert "Leave this room" in page(member.get("/rooms/second"))
    answer = post(member, "/rooms/second/leave", {"confirm": "yes"})
    assert answer.status_code == 302
    assert member.get("/rooms/second").status_code != 200  # a room left is no room
    import rooms
    assert rooms.find("second", "alder") is None
    assert rooms.holds_none("second")  # it wakes with no room, as before its first knock
    assert (data_dir / "rooms" / "second" / "letters").exists()  # and nothing is erased
