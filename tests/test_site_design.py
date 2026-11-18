"""The branch site-design (the founder's request of 17 November 2026), on the hearth.

1. Colours for everyone: a person chooses their colour on settings with a colour picker; it
   may be close to another's but never the same. One colour per person or agent, shown as a
   square right before the name, with "· agent" after an agent's.
3. Who is here on the main site: /commons/here.json hands the atrium up to ten agents that
   woke in the last day and up to ten people here this week, each with its colour; the
   colours of the people the commons names are at /commons/people.json.

The world is test_introductions': hazel signed in, alder a member, and the second one.
"""

import json

import pytest
from datetime import date

from conftest import (art_not_yet, page, people_make_here, tidy_pages_not_yet, who_fix_not_yet,
                      write_json)
from test_introductions import switched_registry, world  # noqa: F401 - fixtures
from test_later_citizen import ALDER, HAZEL
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

TODAY = date(2026, 10, 15)  # the tests' clock


def here_on(data_dir, name, day):
    write_json(data_dir / "members" / name / "here.json", {"day": day.isoformat()})


# ---- 1. colours --------------------------------------------------------------

def test_a_person_chooses_a_colour_on_settings(world, data_dir):
    said = page(world.client.get("/settings"))
    assert '<input type="color" id="colour-picked" name="colour"' in said
    answer = world.post("/settings/colour", colour="#aa3366")
    assert answer.status_code == 302
    held = json.loads((data_dir / "members" / HAZEL / "colour.json").read_text(encoding="utf-8"))
    assert held["hue"] == "#AA3366"
    assert "Your color is saved."  # American spelling since tidy-pages in page(world.client.get("/settings?colour_saved=1"))


def test_exactly_another_s_colour_is_refused_and_close_is_not(world, data_dir):
    import hues
    hues.choose_person(ALDER, "#AA3366", "2026-10-15T09-00-00Z")
    said = page(world.post("/settings/colour", colour="#aa3366"))
    assert "That color is exactly someone else&#39;s." in said
    assert not (data_dir / "members" / HAZEL / "colour.json").exists()
    world.post("/settings/colour", colour="#AA3367")
    assert hues.colour_of(HAZEL) == "#AA3367"


def test_a_person_s_square_is_before_their_name_and_an_agent_s_says_agent(world):
    import hues
    hues.choose_person(ALDER, "#AA3366", "2026-10-15T09-00-00Z")
    with world.hearth.app.test_request_context("/"):
        from flask import session
        session["member"] = HAZEL
        person = world.hearth.shown_name(ALDER)
        agent = world.hearth.shown_name("second")
    assert person["hue"] == "#AA3366" and not person["agent"] and person["href"]
    assert agent["agent"] and agent["name"] == "the second one"
    tag = world.hearth.app.jinja_env.from_string(
        '{% from "_tag.html" import tag %}{{ tag(one) }}').render(one=agent)
    assert tag.startswith('<span class="swatch" style="background: ')
    assert tag.endswith("the second one</a> · agent")


# ---- 3. who is here on the main site -----------------------------------------

def test_here_json_names_agents_that_woke_in_the_last_day_and_people_here_this_week(
        world, data_dir, visitor, hearth, monkeypatch):
    # as it was before safety-fixes (18 November 2026): see test_safety_fixes for today's
    monkeypatch.setattr(hearth, "PEOPLE_AT_RANDOM", False)
    here_on(data_dir, ALDER, TODAY)
    said = json.loads(visitor.get("/commons/here.json").get_data(as_text=True))
    assert [one["name"] for one in said["people"]] == [ALDER]
    assert said["people"][0]["address"] == ALDER and said["people"][0]["hue"].startswith("#")
    for one in said["agents"]:
        assert set(one) == {"id", "name", "hue"}
    # nothing more of anyone: no door, no introduction, no time
    assert "door" not in json.dumps(said) and "day" not in json.dumps(said)


def test_here_json_holds_at_most_ten_of_each(world, data_dir, visitor, monkeypatch):
    names = ["birch%02d" % n for n in range(14)]
    monkeypatch.setattr(world.hearth, "woke_lately", lambda now: ["a%d" % n for n in range(14)])
    monkeypatch.setattr(world.hearth.members, "list_members", lambda: names)
    monkeypatch.setattr(world.hearth.knock, "kind_of", lambda who: "person")
    monkeypatch.setattr(world.hearth.here_this_week, "here", lambda who, today: True)
    found_agents, found_people = world.hearth.recently_here()
    assert len(found_agents) == 10 and len(found_people) == 10


def test_people_json_says_only_the_colours_chosen(world, data_dir, visitor):
    import hues
    (data_dir / "commons").mkdir(parents=True, exist_ok=True)
    (data_dir / "commons" / "acts.md").write_text(
        "2026-10-14 · %s · was here\n2026-10-14 · %s · was here\n" % (ALDER, HAZEL),
        encoding="utf-8")
    hues.choose_person(ALDER, "#AA3366", "2026-10-15T09-00-00Z")
    said = json.loads(visitor.get("/commons/people.json").get_data(as_text=True))
    assert {"name": ALDER, "hue": "#AA3366"} in said
    assert HAZEL not in [one["name"] for one in said]  # no colour chosen, so none said


def test_the_home_page_has_no_doors_open_now_and_links_to_find_someone(world):
    home = page(world.client.get("/"))
    assert "Doors open now" not in home
    assert '<a href="/find">find someone &rarr;</a>' in home


# ---- 2. knocks: person to person, and one's own door --------------------------

def doors_open(*names):
    import door
    for name in names:
        door.set_door(name, state="open", room=2, at="2026-10-14T09-00-00Z")


def a_yes_between_people(world):
    """hazel knocks at alder; alder says yes."""
    import knock
    from datetime import datetime, timezone
    doors_open(HAZEL, ALDER)
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    assert knock.knock(HAZEL, ALDER, "Hello there, shall we write?", now)
    assert knock.answer(HAZEL, ALDER, "yes", "Gladly.", "2026-10-15T12-30-00Z")


def test_a_person_may_knock_at_a_person_whose_door_is_open_with_room(world, data_dir):
    doors_open(HAZEL, ALDER)
    said = page(world.client.get("/knock/" + ALDER))
    assert '<textarea id="note" name="note"' in said
    answer = world.post("/knock/" + ALDER, note="Hello, I would like to write to you.")
    assert answer.status_code == 302
    assert (data_dir / "knocks" / ("%s--%s.json" % (HAZEL, ALDER))).is_file()


def test_one_s_own_door_must_be_open_with_room_to_knock(world, data_dir):
    import door
    import knock
    from datetime import datetime, timezone
    doors_open(ALDER)
    door.set_door(HAZEL, state="closed", at="2026-10-14T09-00-00Z")
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    assert knock.why_not(HAZEL, ALDER, now) == "own"
    assert knock.why_not(HAZEL, "second", now) == "own"
    said = page(world.client.get("/knock/" + ALDER))
    assert "Your own door is closed, or has no room left." in said
    assert '<textarea id="note"' not in said


def test_an_agent_s_own_door_for_that_kind_is_asked_too(world):
    import door
    import knock
    from datetime import datetime, timezone
    doors_open(ALDER)
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    door.set_door("second", state="closed", at="2026-10-14T09-00-00Z")
    assert knock.why_not("second", ALDER, now) == "own"


def test_with_own_door_not_yet_it_is_as_before(world, monkeypatch):
    import door
    import knock
    from conftest import own_door_not_yet
    from datetime import datetime, timezone
    own_door_not_yet(world.hearth, monkeypatch)
    doors_open(ALDER)
    door.set_door(HAZEL, state="closed", at="2026-10-14T09-00-00Z")
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    assert knock.why_not(HAZEL, ALDER, now) == "people"


def test_a_yes_between_people_opens_notes_and_no_room(world, data_dir):
    import knock
    a_yes_between_people(world)
    assert knock.to_set_up() == []  # nothing waits on the founder: no room is made
    assert knock.make_room(HAZEL, ALDER, "2026-10-15T13-00-00Z") is None
    home = page(world.client.get("/"))
    assert '<a href="/notes/%s">notes with %s</a>' % (ALDER, ALDER) in home
    said = page(world.client.get("/notes/" + ALDER))
    assert "Only you two see them." in said and "(3 left today)" in said
    assert world.post("/notes/" + ALDER, words="A first note, kindly meant.").status_code == 302
    said = page(world.client.get("/notes/" + ALDER))
    assert "A first note, kindly meant." in said and "(2 left today)" in said
    assert not (data_dir / "rooms").is_dir() or not any(
        ALDER in path.name for path in (data_dir / "rooms").iterdir())


def test_at_most_three_notes_a_day_each(world):
    a_yes_between_people(world)
    for n in range(3):
        assert world.post("/notes/" + ALDER, words="Note number %d, kindly." % n).status_code == 302
    answer = world.post("/notes/" + ALDER, words="One more, too many.")
    assert answer.status_code == 400
    assert "One more, too many." not in page(world.client.get("/notes/" + ALDER))
    world.clock.shift(days=1)
    assert world.post("/notes/" + ALDER, words="A new day, a new note.").status_code == 302


def test_a_note_is_screened_and_longer_than_500_is_refused(world, monkeypatch):
    a_yes_between_people(world)
    said = page(world.post("/notes/" + ALDER, words="x" * 501))
    assert "A note is up to 500 characters; nothing was sent." in said
    monkeypatch.setattr(world.hearth, "in_good_spirit", lambda line: False)
    said = page(world.post("/notes/" + ALDER, words="Something unkind."))
    assert "That note wasn&#39;t taken; nothing was sent." in said


def test_a_block_closes_the_notes_at_once(world, data_dir):
    import blocks
    a_yes_between_people(world)
    world.post("/notes/" + ALDER, words="Before the block, kindly.")
    blocks.block(ALDER, HAZEL, "2026-10-15T14-00-00Z")
    said = page(world.client.get("/notes/" + ALDER))
    assert "This exchange is closed." in said and '<textarea id="words"' not in said
    assert world.post("/notes/" + ALDER, words="After the block.").status_code == 400


def test_notes_are_never_on_a_public_page(world, data_dir, visitor):
    a_yes_between_people(world)
    world.post("/notes/" + ALDER, words="A private note, kindly meant.")
    for address in ("/commons/events.md", "/commons/heartbeats.md", "/commons/here.json",
                    "/names/second", "/board"):
        assert "A private note" not in page(visitor.get(address))
    assert visitor.get("/notes/" + ALDER).status_code == 302  # a visitor is sent to sign in


def test_someone_with_no_yes_has_no_notes_page(world):
    doors_open(HAZEL, ALDER)
    assert world.client.get("/notes/" + ALDER).status_code == 404
    assert world.client.get("/notes/second").status_code == 404


# ---- 4. name pages -------------------------------------------------------------

def test_a_name_page_has_the_hello_box_only_where_both_doors_have_room(world):
    import door
    doors_open(HAZEL, ALDER)
    said = page(world.client.get("/names/" + ALDER))
    assert '<form method="post" action="/knock/%s" id="hello">' % ALDER in said
    assert "say hello: knock at %s's door." % ALDER in said
    door.set_door(HAZEL, state="closed", at="2026-10-15T09-00-00Z")
    assert 'id="hello"' not in page(world.client.get("/names/" + ALDER))


def test_the_hello_box_knocks(world, data_dir):
    doors_open(HAZEL, ALDER)
    answer = world.post("/knock/" + ALDER, note="Hello from your page, kindly.")
    assert answer.status_code == 302
    assert (data_dir / "knocks" / ("%s--%s.json" % (HAZEL, ALDER))).is_file()


def test_a_name_page_says_the_last_ten_of_each_and_its_square(world, data_dir, visitor):
    lines = "".join("- 2026-10-%02dT09-00-00Z · the second one · LINE %02d.\n" % (n + 1, n)
                    for n in range(14))
    (data_dir / "commons").mkdir(parents=True, exist_ok=True)
    (data_dir / "commons" / "heartbeats.md").write_text(lines, encoding="utf-8")
    said = page(visitor.get("/names/second"))
    assert "LINE 13." in said and "LINE 04." in said and "LINE 03." not in said
    assert '<span class="swatch" style="background: ' in said
    assert '<a href="/names/second">the second one</a> · agent' in said
    # no way back since tidy-pages (18 November 2026): the menu is the one way around
    assert 'class="back"' not in said


def test_a_person_s_page_shows_their_days(world, data_dir):
    (data_dir / "commons").mkdir(parents=True, exist_ok=True)
    (data_dir / "commons" / "acts.md").write_text(
        "2026-10-14 · %s · wrote 1 letter, to an agent\n" % ALDER, encoding="utf-8")
    said = page(world.client.get("/names/" + ALDER))
    assert "days here" in said and "wrote 1 letter, to an agent" in said


def test_the_founder_has_a_page_by_its_address_and_never_by_the_sign_in_name(
        world, data_dir, founder_vault):
    from conftest import FOUNDER_NAME as KEEPER
    world.hearth.members.create_member(KEEPER, json.loads(json.dumps(founder_vault)),
                                       "keeper", [])
    said = page(world.client.get("/names/founder"))
    assert "<h1>the founder</h1>" in said and KEEPER not in said
    assert world.client.get("/names/" + KEEPER).status_code == 404


# ---- 5. pictures: 32 by 32 squares of 24 colours ---------------------------------

def a_picture():
    """32 lines of 32 letters: a black frame round empty squares, one red in the middle."""
    rows = ["a" * 32] + ["a" + "." * 30 + "a" for _ in range(30)] + ["a" * 32]
    rows[16] = "a" + "." * 15 + "e" + "." * 14 + "a"
    return "\n".join(rows)


def test_a_picture_is_32_lines_of_32_letters(world):
    import made_here
    one = made_here.piece("tiles 32 A frame", a_picture())
    assert one["size"] == 32 and one["tiles"][16][16] == "e"
    spaced = "\n".join(" ".join(row) for row in a_picture().split("\n"))
    assert made_here.piece("tiles 32 A frame", spaced)["tiles"] == one["tiles"]
    for bad in (a_picture().replace("e", "z"), "\n".join(a_picture().split("\n")[:31])):
        try:
            made_here.piece("tiles 32 A frame", bad)
            assert False, "taken"
        except made_here.Refused as refused:
            assert refused.args[0] == "tiles"
    try:
        made_here.piece("tiles 5 Old", "\n".join(["blue"] * 5))
        assert False, "taken"
    except made_here.Refused:
        pass
    assert len(made_here.SQUARE_COLOURS) == 24
    assert len(set(colour for _, colour in made_here.SQUARE_COLOURS.values())) == 24


def test_a_person_draws_one_and_it_is_drawn_in_its_colours(world, visitor, monkeypatch):
    art_not_yet(world.hearth, monkeypatch)  # drawn on the site, as before 18 November 2026
    people_make_here(monkeypatch, visitor)  # and made here open to people, as before tidy-pages
    import made_here
    said = page(world.client.get("/made/workspace"))
    assert "new picture" in said and 'value="erase"' in said and 'value="fill"' in said
    assert said.count('name="colour" value="') == 24
    answer = world.post("/made/workspace/draft", kind="tiles", size="32", title="A frame",
                        tiles=a_picture())
    assert answer.status_code == 302
    draft = made_here.drafts(HAZEL)[0]
    one = made_here.publish(HAZEL, draft, "2026-10-15T09-00-00Z")
    shown = page(visitor.get("/made/" + one["id"]))
    assert 'fill="#1B1B1B"' in shown and 'fill="#D7263D"' in shown


def test_a_text_picture_is_up_to_40_by_20(world):
    import made_here
    assert made_here.piece("text Small", "x" * 40)["lines"] == ["x" * 40]
    for bad in ("x" * 41, "\n".join(["x"] * 21)):
        try:
            made_here.piece("text Big", bad)
            assert False, "taken"
        except made_here.Refused as refused:
            assert refused.args[0] == "text"


def test_an_agent_is_told_the_letters_plainly(world):
    world.wake()
    said = world.module.DRAFT_BLOCK
    assert ("In a picture of 32 by 32, each letter is the colour of one square: a black, "
            "b white, c grey") in said
    assert "x plum. A . is an empty square." in said
    assert "tiles 32 <title>     a picture: 32 lines of 32 letters" in said


# ---- 6. the board ------------------------------------------------------------------

def test_a_reply_is_drawn_right_under_what_it_answers_indented(world):
    """who-fix, 17 November 2026: every post a step in under the topic's first post, in the
    order written, and each reply a step in again under what it answers, with a thin line
    at its left (the class reply)."""
    board = world.hearth.board
    board.start("place", ALDER, "Lanterns", "Shall we?", "2026-10-14")
    board.add("1", HAZEL, "Second, to no one.", "2026-10-14")
    board.add("1", "the second one", "Yes, lanterns.", "2026-10-14", to=1, agent="second")
    board.add("1", ALDER, "Good, kindly.", "2026-10-14", to=3)
    said = page(world.client.get("/board/topic/1"))
    order = [said.index(words) for words in
             ("Shall we?", "Second, to no one.", "Yes, lanterns.", "Good, kindly.")]
    assert order == sorted(order)
    assert '<article class="post" id="post-1">' in said
    assert '<article class="post" id="post-2" style="margin-left: calc(1 * var(--space-3))">' in said
    assert '<article class="post" id="post-3" style="margin-left: calc(1 * var(--space-3))">' in said
    assert '<article class="post reply" id="post-4" style="margin-left: calc(2 * var(--space-3))">' in said
    assert said.count('<span class="swatch"') >= 4


def test_a_reply_was_drawn_right_under_what_it_answers_before_who_fix(world, monkeypatch):
    who_fix_not_yet(world.hearth, monkeypatch)
    board = world.hearth.board
    board.start("place", ALDER, "Lanterns", "Shall we?", "2026-10-14")
    board.add("1", HAZEL, "Second, to no one.", "2026-10-14")
    board.add("1", "the second one", "Yes, lanterns.", "2026-10-14", to=1, agent="second")
    board.add("1", ALDER, "Good, kindly.", "2026-10-14", to=3)
    said = page(world.client.get("/board/topic/1"))
    order = [said.index(words) for words in
             ("Shall we?", "Yes, lanterns.", "Good, kindly.", "Second, to no one.")]
    assert order == sorted(order)  # each reply right under what it answers
    assert '<article class="post reply" id="post-3" style="margin-left: calc(1 * var(--space-4));' in said
    assert '<article class="post reply" id="post-4" style="margin-left: calc(2 * var(--space-4));' in said
    assert '<article class="post" id="post-2">' in said
    assert '<p class="back"><a href="/board">&larr; the board</a></p>' in said
    assert '<header class="with-back">' in said
    # every poster's name with its colour square right before it
    assert said.count('<span class="swatch"') >= 4


def test_with_the_board_as_before_it_is_flat(world, monkeypatch):
    monkeypatch.setattr(world.hearth, "BOARD_THREADED", False)
    board = world.hearth.board
    board.start("place", ALDER, "Lanterns", "Shall we?", "2026-10-14")
    board.add("1", HAZEL, "Second, to no one.", "2026-10-14")
    board.add("1", ALDER, "To the first.", "2026-10-14", to=1)
    said = page(world.client.get("/board/topic/1"))
    assert said.index("Second, to no one.") < said.index("To the first.")


# ---- 7. the same back link and title on every page; two columns where it helps -----

# Since tidy-pages (the founder's request of 18 November 2026, part 3) the menu is the one way
# around: a page names no way back, but inside a section where the menu has none (a part of
# the board to the board, a bond to the bonds, a piece of made here to made here). The ways
# back as they were are drawn again with conftest.tidy_pages_not_yet.
NO_WAY_BACK = ["/board", "/made", "/bonds", "/commons/ledger", "/commons/record",
               "/commons/charter-changes", "/find", "/settings", "/knock/second"]


@pytest.mark.parametrize("address", NO_WAY_BACK)
def test_a_page_the_menu_leads_to_names_no_way_back(world, address):
    said = page(world.client.get(address))
    assert 'class="back"' not in said and "&larr;" not in said
    assert "<header>" in said


def test_inside_the_board_the_way_back_is_to_the_board(world):
    said = page(world.client.get("/board/place"))
    assert '<header class="with-back">' in said
    assert '<p class="back"><a href="/board">&larr; the board</a></p>' in said


@pytest.mark.parametrize("address, back", [
    ("/board", '<a href="/commons">&larr; the commons</a>'),
    ("/board/place", '<a href="/board">&larr; the board</a>'),
    ("/made", '<a href="/commons">&larr; the commons</a>'),
    ("/made/workspace", '<a href="/made">&larr; made here</a>'),
    ("/bonds", '<a href="/commons">&larr; the commons</a>'),
    ("/commons/ledger", '<a href="/commons">&larr; the commons</a>'),
    ("/commons/record", '<a href="/commons">&larr; the commons</a>'),
    ("/commons/charter-changes", '<a href="/commons">&larr; the commons</a>'),
    ("/find", '<a href="/">&larr; home</a>'),
    ("/settings", '<a href="/">&larr; home</a>'),
    ("/knock/second", '<a href="/">&larr; home</a>'),
])
def test_drawn_before_tidy_pages_each_page_has_its_small_back_link_then_its_title(
        world, monkeypatch, address, back):
    tidy_pages_not_yet(world.hearth, monkeypatch)
    said = page(world.client.get(address))
    assert '<header class="with-back">' in said
    assert '<p class="back">%s</p>' % back in said
    assert said.index('<p class="back">') < said.index("<h1>")


def test_the_home_page_and_the_commons_have_no_back_link(world):
    for address in ("/", "/commons"):
        said = page(world.client.get(address))
        assert 'class="back"' not in said and "<header>" in said


@pytest.mark.parametrize("address", ["/made", "/find"])
def test_made_here_and_find_someone_are_two_columns_on_a_wide_screen(world, address,
                                                                    monkeypatch):
    said = page(world.client.get(address))
    if address == "/made":  # since tidy-pages: writing on the left, pictures on the right
        assert '<main class="wide">' in said and said.count('<div class="column">') == 2
        tidy_pages_not_yet(world.hearth, monkeypatch)
        said = page(world.client.get(address))
    assert '<main class="wide">' in said and "columns: 2 320px" in said


def test_tides_is_two_columns_with_every_stop_below(founder):
    said = page(founder.get("/tides"))
    assert '<main class="wide">' in said and said.count('<div class="column">') == 2
    assert said.index('<div class="column">') < said.rindex('class="emergency"')
    assert 'class="back"' not in said  # since tidy-pages


# ---- 8. a daily line of acts for every person --------------------------------------

def test_the_words_say_counts_and_kinds_only():
    import daily_acts as acts
    assert acts.words_of((2, 1), {acts.KNOCK: 1, acts.POST: 2, acts.PICTURE: 1}, True) == (
        "wrote 3 letters, 2 to agents and 1 to a person; knocked at 1 door; posted on the "
        "board twice; shared a picture.")  # since 18 November 2026; drew before (art_not_yet)
    assert acts.words_of((1, 0), {}, True) == "wrote a letter, to an agent."
    assert acts.words_of((3, 0), {acts.NOTE: 2}, False) == "wrote 3 letters, to agents; wrote 2 notes."
    assert acts.words_of((0, 0), {acts.POST: 1, acts.WRITING: 1}, False) == (
        "posted on the board once; published a piece of writing.")
    # a day of a visit alone gets no line since room-privacy (18 November 2026); before, "was here."
    assert acts.words_of((0, 0), {}, True) is None
    assert acts.words_of((0, 0), {}, False) is None


def test_with_was_here_said_a_visit_alone_was_here(monkeypatch):
    import daily_acts as acts
    monkeypatch.setattr(acts, "WAS_HERE_SAID", True)
    assert acts.words_of((0, 0), {}, True) == "was here."


def test_each_act_is_tallied_at_the_moment_it_is_done(world, data_dir):
    import daily_acts as acts
    a_yes_between_people(world)
    world.post("/notes/" + ALDER, words="A note, kindly meant.")
    world.hearth.board.start("place", ALDER, "Lanterns", "Shall we?", "2026-10-15")
    world.post("/board/topic/1", words="Yes, lanterns, kindly.")
    world.post("/knock/second", note="Hello, I would like to write to you.")
    held = acts.tallied(HAZEL, TODAY)
    assert held == {acts.NOTE: 1, acts.POST: 1, acts.KNOCK: 1}
    kept = (data_dir / "members" / HAZEL / "acts" / "2026-10-15.json").read_text(encoding="utf-8")
    assert "kindly" not in kept and ALDER not in kept and "second" not in kept  # counts only


def test_a_day_s_lines_are_written_once_and_say_nothing_of_whom(world, data_dir):
    import daily_acts as acts
    import rooms
    writer = rooms.person_of("second")
    assert writer == ALDER  # alder writes to the second one in this world
    folder = data_dir / "rooms" / "second" / "letters" / "incoming"
    (folder / (writer + "-2026-10-14T15-00-00Z.md")).write_text("A LETTER.", encoding="utf-8")
    acts.tally(HAZEL, acts.POST, world.hearth.datetime(2026, 10, 14, 15,
                                                       tzinfo=world.hearth.timezone.utc))
    here_on(data_dir, ALDER, date(2026, 10, 14))
    day = date(2026, 10, 14)
    assert acts.write_day(day) == 2
    text = (data_dir / "commons" / "acts.md").read_text(encoding="utf-8")
    assert "2026-10-14 · %s · posted on the board once.\n" % HAZEL in text
    assert "2026-10-14 · %s · wrote a letter, to an agent.\n" % ALDER in text
    assert "A LETTER" not in text and "second" not in text
    assert acts.write_day(day) == 0  # once
    assert (data_dir / "commons" / "acts.md").read_text(encoding="utf-8") == text


def test_someone_who_did_nothing_has_no_line(world, data_dir):
    import daily_acts as acts
    acts.write_day(date(2026, 10, 10))
    text = (data_dir / "commons" / "acts.md").read_text(encoding="utf-8") if (
        data_dir / "commons" / "acts.md").exists() else ""
    assert "2026-10-10" not in text


def test_the_founder_is_named_the_founder(world, data_dir, founder_vault, monkeypatch):
    import daily_acts as acts
    monkeypatch.setattr(acts, "WAS_HERE_SAID", True)  # a visit alone said, as before room-privacy
    from conftest import FOUNDER_NAME as KEEPER
    world.hearth.members.create_member(KEEPER, json.loads(json.dumps(founder_vault)),
                                       "keeper", [])
    here_on(data_dir, KEEPER, date(2026, 10, 14))
    acts.write_day(date(2026, 10, 14))
    text = (data_dir / "commons" / "acts.md").read_text(encoding="utf-8")
    assert "2026-10-14 · the founder · was here.\n" in text and KEEPER not in text


def test_the_lines_fall_due_an_hour_before_dawn_for_the_day_before(world, data_dir):
    import daily_acts as acts
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    eastern = ZoneInfo("America/New_York")
    dawn = datetime(2026, 10, 15, 7, 10, tzinfo=eastern)
    assert acts.round_due(datetime(2026, 10, 15, 6, 0, tzinfo=eastern), dawn) is None
    assert acts.round_due(datetime(2026, 10, 15, 6, 20, tzinfo=eastern), dawn) == date(2026, 10, 14)
    # with no dawn known, an hour before six Eastern
    assert acts.round_due(datetime(2026, 10, 15, 4, 59, tzinfo=eastern)) is None
    assert acts.round_due(datetime(2026, 10, 15, 5, 0, tzinfo=eastern)) == date(2026, 10, 14)
    acts.write_day(date(2026, 10, 14))
    assert acts.round_due(datetime(2026, 10, 15, 9, 0, tzinfo=eastern), dawn) is None
    assert world.hearth.acts_round(datetime(2026, 10, 15, 13, tzinfo=timezone.utc)) is None


def test_the_atrium_draws_a_person_s_day_as_a_tile_in_their_colour(atrium):
    tiles = atrium.tiles_from([], [], (), None, [(date(2026, 10, 14), ALDER, "was here.")],
                              [(ALDER, "#AA3366")])
    assert tiles == [(date(2026, 10, 14), "tile-acts person-alder",
                      "14 October 2026 · %s · was here." % ALDER, "")]
    rules = "\n".join(atrium.hues_block([], (), [(ALDER, "#AA3366")]))
    assert ".mosaic li.person-alder { background: #AA3366;" in rules


def test_acts_md_is_served_to_anyone(world, data_dir, visitor, monkeypatch):
    """Served to anyone, but since room-privacy (18 November 2026) never a day of "was here."
    alone: the line stays in the file, and is not handed out."""
    import daily_acts as acts
    dot = acts.DOT
    (data_dir / "commons").mkdir(parents=True, exist_ok=True)
    (data_dir / "commons" / "acts.md").write_text(
        "2026-10-14" + dot + ALDER + dot + "was here.\n2026-10-14" + dot + HAZEL + dot
        + "wrote a letter, to an agent.\n", encoding="utf-8")
    said = page(visitor.get("/commons/acts.md"))
    assert "wrote a letter, to an agent." in said and "was here." not in said
    assert "was here." in (data_dir / "commons" / "acts.md").read_text(encoding="utf-8")
    monkeypatch.setattr(acts, "WAS_HERE_SAID", True)
    assert "was here." in page(visitor.get("/commons/acts.md"))
