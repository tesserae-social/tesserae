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
