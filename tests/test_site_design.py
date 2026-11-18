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
from datetime import date

from conftest import page, write_json
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
    assert "Your colour is saved." in page(world.client.get("/settings?colour_saved=1"))


def test_exactly_another_s_colour_is_refused_and_close_is_not(world, data_dir):
    import hues
    hues.choose_person(ALDER, "#AA3366", "2026-10-15T09-00-00Z")
    said = page(world.post("/settings/colour", colour="#aa3366"))
    assert "That colour is exactly someone else&#39;s." in said
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
        world, data_dir, visitor):
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
    assert '<p class="back"><a href="/commons">&larr; the commons</a></p>' in said


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


def test_a_person_draws_one_and_it_is_drawn_in_its_colours(world, visitor):
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
