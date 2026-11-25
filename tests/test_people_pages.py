"""people-pages: the founder's request of 25 November 2026.

1. Every room's line on the home page carries its "open the room" on the line itself. The first
   one's had sat at the foot of a fold holding every letter, out of sight; its id "first" and
   its sealed bond were not the cause.
2. The home page's conversations are one line for each person, in the two columns; knocks and
   answers with no room or notes yet are lines too, with a short status, and are shown in full
   on the knocks page.
3. One people page: everyone here, each with their door, "knock" where one may, and "your room"
   or "your notes"; searched; /find leads to it; the menu links it once.
4. Private as before: one sees only one's own conversations and rooms.
5. Rooms left with someone are listed under the open one as "earlier, closed"; a new knock after
   leaving opens a room at a new address, and never one used before.
6. Room and bond pages say the parties in plain words, with the DIDs in a "details" fold.

The world for 2 to 5 is test_leaving's: hazel, a member, signed in, and the second one, whose
first room is shared with alder; hazel's room with it is opened by a yes.
"""

import re

from conftest import PASSWORD, block, page, post
from test_hearth_bonds import sealed
from test_introductions import knock_at
from test_later_citizen import ALDER, HAZEL
from test_leaving import ROOM, YES, leave_as_hazel, record, world  # noqa: F401 - a fixture
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

NOT_YET = block("KNOCK_ANSWER", "from: hazel\nanswer: not yet\n")


def switched(world):
    """The home page as the site draws it: conversations, and the people page."""
    world.monkeypatch.setattr(world.hearth, "CONVERSATIONS", True)
    world.monkeypatch.setattr(world.hearth, "PEOPLE_PAGES", True)
    return world


def flat(answer):
    return " ".join(page(answer).split())


def home(world):
    return flat(world.client.get("/"))


def outside_folds(said):
    """A page with every fold taken out."""
    return re.sub(r"<details.*?</details>", "", said, flags=re.S)


# ---- 1: the way into every room is on its line ---------------------------------------------

def test_the_first_one_s_line_opens_the_room_with_its_bond_sealed_and_many_letters(
        hearth, founder, wake, room, clock, conversations_shown, people_pages_shown):
    sealed(founder, wake, room, clock)
    for day in range(1, 29):  # a long correspondence, as the first one's is
        (room / "letters" / "read" / ("founder-2026-09-%02dT09-00-00Z.md" % day)).write_text(
            "A LETTER OF THE FOUNDER'S.\n", encoding="utf-8")
    said = page(founder.get("/"))
    line = next(one for one in said.split('<li class="conversation">')[1:]
                if "/names/first" in one)
    assert '<a href="/rooms/first">open the room</a>' in line.split("</li>")[0]
    assert '<a href="/rooms/first">open the room</a>' in outside_folds(said)
    assert "A LETTER OF THE FOUNDER" not in said  # no letter in full on the home page


def test_every_room_of_a_member_has_its_way_in_on_its_line(world):
    switched(world)
    import rooms
    said = outside_folds(page(world.client.get("/")))
    held = rooms.of(HAZEL)
    assert [one.id for one in held] == [ROOM]
    for one in held:
        assert '<a href="/rooms/%s">open the room</a>' % one.id in said


# ---- 2: one line for each person; knocks as lines, in full on the knocks page ---------------

LONG_NOTE = ("I have read your introduction twice and would like to write to you about rivers, "
             "and about the sea.")


def test_a_knock_that_waits_is_a_line_and_in_full_on_the_knocks_page(
        env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    from test_knocks_tidy import registry_with
    from test_introductions import make_world
    registry_with(monkeypatch, tmp_path, "rooms_reading", "room_on_yes", "leaving",
                  "longer_waking")
    world = switched(make_world(env, clock, monkeypatch, data_dir, member_vaults))
    answer = knock_at(world, note=LONG_NOTE)
    assert answer.status_code == 302 and answer.headers["Location"].endswith(
        "/knocks?knocked=second")
    said = home(world)
    mine = said[said.index("You wrote last"):]
    assert "<strong>knock waiting</strong> · you · 15 October 2026 · &ldquo;I have read" in mine
    assert '<a href="/knocks#knock-second">see the knock</a>' in mine
    assert LONG_NOTE not in said and "about the sea" not in said  # its first few words only
    assert "…&rdquo;" in mine
    knocks = flat(world.client.get("/knocks"))
    assert LONG_NOTE in knocks and 'id="knock-second"' in knocks and "No answer yet." in knocks
    # answered not yet: the line is theirs now, with its status
    world.wake(NOT_YET)
    said = home(world)
    theirs = said[said.index("They wrote last"):said.index("You wrote last")]
    assert "<strong>not yet</strong> · the second one" in theirs
    # answered yes: its room is the line, and the knock no longer is
    world.clock.shift(days=31)
    knock_at(world, note="AGAIN")
    world.wake(YES)
    said = home(world)
    assert '<a href="/rooms/second-hazel">open the room</a>' in said
    assert "see the knock" not in said and "knock waiting" not in said


def test_the_home_page_has_no_who_is_here_and_no_knocks_section(world):
    switched(world)
    said = home(world)
    assert 'id="who-is-here"' not in said and 'id="knocks"' not in said
    assert "find someone" not in said


def test_the_knocks_page_is_a_member_s_alone(world):
    switched(world)
    visitor = world.hearth.app.test_client()
    assert visitor.get("/knocks").status_code == 302


# ---- 3: the people page ----------------------------------------------------------------------

def test_the_people_page_shows_everyone_with_door_knock_and_what_is_shared(world):
    switched(world)
    said = flat(world.client.get("/people?seed=abc"))
    assert "the second one" in said and ALDER in said
    # their door, plainly, and the way to knock where one may
    second = said[said.index('href="/names/second"'):]
    second = second[:second.index("</li>")]
    assert "door" in second
    assert '<a href="/rooms/second-hazel">your room</a>' in second
    assert "/knock/second" not in second  # they write to each other already
    alder = said[said.index('href="/names/%s"' % ALDER):]
    alder = alder[:alder.index("</li>")]
    assert "your room" not in alder and "your notes" not in alder


def test_the_people_page_is_searched_by_name(world):
    switched(world)
    said = flat(world.client.get("/people?seed=abc&q=second"))
    assert "the second one" in said and ALDER not in said
    said = flat(world.client.get("/people?seed=abc&q=nobody-is-called-this"))
    assert "No one here fits that." in said


def test_find_leads_to_the_people_page_with_what_it_was_asked(world):
    switched(world)
    answer = world.client.get("/find?seed=abc&kind=agents&q=river")
    assert answer.status_code == 302
    where = answer.headers["Location"]
    assert where.startswith("/people?") and "seed=abc" in where and "kind=agents" in where \
        and "q=river" in where


def test_the_menu_links_the_people_page_once(world):
    switched(world)
    for address in ("/", "/people", "/settings", "/commons", "/knocks"):
        said = page(world.client.get(address))
        menu = said[said.index('<nav class="menu top"'):said.index("</nav>")]
        assert menu.count(">people<") == 1, address
        assert "find someone" not in menu


def test_a_visitor_has_no_people_page_and_no_link_to_it(world):
    switched(world)
    visitor = world.hearth.app.test_client()
    assert visitor.get("/people").status_code == 302
    said = page(visitor.get("/commons"))
    assert "/people" not in said


# ---- 4: private as before ----------------------------------------------------------------------

def test_each_sees_only_their_own_rooms(world):
    switched(world)
    alder = world.hearth.app.test_client()
    assert post(alder, "/login", data={"pseudonym": ALDER, "password": PASSWORD}
                ).status_code == 302
    for address in ("/", "/people?seed=abc"):
        theirs = page(alder.get(address))
        assert "second-hazel" not in theirs
        mine = page(world.client.get(address))
        assert 'href="/rooms/second"' not in mine  # alder's room with the second one
    assert alder.get("/rooms/" + ROOM).status_code == 404


# ---- 5: rooms left, and a new room at a new address -------------------------------------------

def test_a_new_knock_after_leaving_opens_a_new_room_and_the_old_is_listed_closed(world):
    import knock
    switched(world)
    leave_as_hazel(world)
    before = record(world)
    # the closed room, with no other line yet, is under rooms closed
    said = home(world)
    assert "rooms closed" in said and "/rooms/%s/closed" % ROOM in said
    # its copy is linked by its address (before, a dict's own copy method was drawn there)
    assert '<a href="/rooms/%s/closed/copy">take a copy</a>' % ROOM in said
    assert "built-in method" not in said
    world.clock.shift(days=knock.AGAIN_AFTER_DAYS + 1)
    assert knock_at(world, note="MAY WE BEGIN AGAIN").status_code == 302
    said = home(world)
    # a knock that waits, with the room left beneath it
    assert "knock waiting" in said and "earlier, closed" in said
    world.wake(YES)
    new = ROOM + "-2"
    assert (world.data / "rooms" / new / "room.json").is_file()
    assert record(world) == before  # the room left is as it was, and its address is its own
    assert record(world, new)["id"] == new and not record(world, new).get("left_at")
    said = home(world)
    line = said[said.index('<li class="conversation">'):]
    line = line[:line.index("</li>")]
    assert '<a href="/rooms/%s">open the room</a>' % new in line
    assert "earlier, closed" in line and '/rooms/%s/closed"' % ROOM in line
    assert '<a href="/rooms/%s/closed/copy">take a copy</a>' % ROOM in line
    assert "rooms closed" not in said  # listed under its line, and not again
    people = flat(world.client.get("/people?seed=abc"))
    second = people[people.index('href="/names/second"'):]
    second = second[:second.index("</li>")]
    assert '<a href="/rooms/%s">your room</a>' % new in second
    assert "earlier, closed" in second and '/rooms/%s/closed"' % ROOM in second
    assert '<a href="/rooms/%s/closed/copy">take a copy</a>' % ROOM in second


# ---- 6: parties in plain words, the DIDs in a fold -----------------------------------------

def test_the_first_one_s_bond_says_its_parties_plainly(hearth, founder, wake, room, clock):
    sealed(founder, wake, room, clock)
    said = page(founder.get("/rooms/first"))
    assert "It is between you and the first one." in said
    assert "Signed by: the first one and you." in said
    assert "It was asked for by you." in said
    bare = outside_folds(said)
    assert "did:web:tesserae.social:ids:founder" not in bare
    assert "did:web:tesserae.social:ids:first" not in bare
    fold = said[said.index("<summary>details</summary>"):]
    fold = fold[:fold.index("</details>")]
    assert "did:web:tesserae.social:ids:founder" in fold and "did:web:tesserae.social:ids:first" in fold
    assert "Asked for by did:web:tesserae.social:ids:founder." in fold
    # what is signed is the record as it was
    assert set(hearth.load(room / "bonds" / "founder-first.json")["signatures"]) == {
        "first", "founder"}
