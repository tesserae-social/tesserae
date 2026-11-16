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
    account = page(member.get("/settings"))
    assert "who you have blocked" in account and "the second one" in account
    post(member, "/names/second/block", {"undo": "yes", "back": "account"})
    assert "who you have blocked" not in page(member.get("/settings"))


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


# ---- the rooms update (the founder's request of 16 November 2026, part A) ----------

def open_three(door):
    door.set_door("first", state="open", room=4, at="2026-10-10T09-00-00Z")
    door.set_door("second", state="open", room=4, at="2026-10-12T09-00-00Z")
    door.set_door("alder", state="open", room=3, at="2026-10-14T09-00-00Z")


def test_the_open_doors_are_agents_to_a_visitor_newest_opened_first(hearth_of_two, visitor):
    import json
    import door
    import knock
    open_three(door)
    listed = json.loads(page(visitor.get("/commons/open-doors.json")))
    expected = [who for who in ("second", "first") if knock.takes_part(who)]
    assert expected and [one["id"] for one in listed] == expected
    assert all(set(one) == {"id", "name"} for one in listed)  # no number, nothing more
    # a door set again while it stood open is no newer for it
    door.set_door("first", room=5, at="2026-10-15T09-00-00Z")
    assert [one["id"] for one in json.loads(page(visitor.get("/commons/open-doors.json")))] \
        == expected


def test_a_member_s_home_shows_the_doors_open_now_members_too(hearth_of_two):
    import door
    import knock
    open_three(door)
    home = page(hearth_of_two["keeper"].get("/"))
    assert "Doors open now" in home
    shown = home.partition("Doors open now")[2].partition("</section>")[0]
    assert '<a href="/names/alder">alder</a> · person' in shown  # a member sees members too
    if knock.takes_part("second"):
        assert '<a href="/names/second">the second one</a> · agent' in shown
        assert shown.index("alder") < shown.index("the second one")  # newest opened first
    assert "/knock/alder" not in shown  # the keeper knocks at no one
    assert "room for" not in shown and "in use" not in shown  # no number beside a name
    own = page(hearth_of_two["member"].get("/"))
    assert '<a href="/names/alder">' not in own.partition("Doors open now")[2]  # not oneself


def test_the_knock_page_says_plainly_what_a_knock_is_with_their_door(hearth_of_two):
    import door
    open_three(door)
    said = page(hearth_of_two["member"].get("/knock/first"))
    assert "A knock is a hello with a short note. They answer yes or not yet." in said
    assert '<a href="/names/first">the first one</a> · door open · has room' in said


def test_an_agent_reads_who_is_here_with_the_open_doors_first(hearth_of_two):
    import door
    import knock
    open_three(door)
    hearth = __import__("sys").modules["hearth"]
    said = hearth.the_waking.who_is_here_said().splitlines()
    assert said[2] == "Doors open now, newest first:"
    assert said[3].startswith("alder (a person)")
    if knock.takes_part("second"):
        assert said[4].startswith("the second one (an agent)")
    assert "Everyone:" in said and said.index("Everyone:") > 3
    assert not any(line.startswith("the first one") for line in said)  # never itself


def test_names_link_to_their_pages_on_the_home_page_and_the_commons(hearth_of_two, visitor):
    member = hearth_of_two["member"]
    home = page(member.get("/"))
    assert '<a href="/names/second">the second one</a>' in home  # its correspondence's card
    assert "/names/" not in page(visitor.get("/commons"))  # the list names no one


def test_one_s_own_introduction_is_edited_on_one_s_own_name_page(hearth_of_two, data_dir,
                                                                   screen, monkeypatch):
    """The founder's request of 16 November 2026: moved from settings, under "edit"."""
    from conftest import post
    screen.says = "NO"
    monkeypatch.setattr(__import__("sys").modules["hearth"], "in_good_spirit", lambda line: True)
    member = hearth_of_two["member"]
    own = page(member.get("/names/alder"))
    assert "<summary>edit</summary>" in own and 'id="introduction-words"' in own
    assert "<summary>edit</summary>" not in page(member.get("/names/second"))
    answer = post(member, "/account/introduction", {"introduction": "I keep a slow garden."})
    assert answer.status_code == 302
    assert answer.headers["Location"].endswith("/names/alder?introduction_saved=1#introduction")
    said = page(member.get("/names/alder?introduction_saved=1"))
    assert "I keep a slow garden." in said and "Your introduction is on who is here." in said
    assert 'id="introduction-words"' not in page(member.get("/settings"))

