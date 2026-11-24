"""hotfix-ids: the founder's request of 24 November 2026, after stage 3 and move_to_ids.py on
the host, where the keeper is now "founder".

1. Colours by any old name. hues.person_folder refused "founder" (a reserved pseudonym), so
   the founder had no colour; and people.json found a person only by their name now, so a
   line already written under an old name lost its colour. Now every member file found by id
   allows the keeper's "founder" (members.validate_member_id), and an old name (a joining
   name, any commons name held, an id from before ids, a sign-in name) finds its holder
   (members.id_of_written). A sign-in name is never shown: people.json and /commons/acts.md
   say the holder's name now in its place (members.shown_for).
2. /tides linked "its room" to an agent's first room (/rooms/second, its room with a member)
   even where the keeper's room with it is a later one (/rooms/second-founder).
3. /tides askings: one spacing field per agent or member, saying what is set now; no "Keep
   this"; no raw list of switches for a member, whose order is set by plain-named places.

The world is test_founder_room's, with the keeper by its id, "founder", as after the move.
"""

import json

import pytest

from conftest import PASSWORD, page, post
from test_introductions import make_world
from test_knocks_tidy import registry_with
from test_rooms_for_any_agent import ALDER, HAZEL, member_vaults  # noqa: F401 - a fixture

AT = "2026-10-16T10-00-00Z"
KEEPER = "founder"
FOUNDER_HUE, ALDER_HUE, HAZEL_HUE = "#AA3311", "#2266AA", "#118844"
SIGN_IN = "hazel-signs-in"


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, founder_vault, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "knock_founder", "rooms_reading")
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    made.hearth.members.create_member(KEEPER, json.loads(json.dumps(founder_vault)),
                                      "keeper", [])
    return made


def coloured(world, who, hue):
    path = world.data / "members" / who / "colour.json"
    path.write_text(json.dumps({"hue": hue, "at": AT}) + "\n", encoding="utf-8")


def keeper_client(world):
    client = world.hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": KEEPER, "password": PASSWORD})
    assert answer.status_code == 302
    return client


# ---- 1. colours by any old name ---------------------------------------------------------

def test_the_founder_s_colour_is_found_by_its_id(world):
    import door
    import here_this_week
    import hues
    coloured(world, KEEPER, FOUNDER_HUE)
    assert hues.person_chosen(KEEPER) == FOUNDER_HUE
    assert hues.colour_of(KEEPER) == FOUNDER_HUE
    # the keeper's other files kept by its id are found too
    assert door.path_of(KEEPER) == world.data / "members" / KEEPER / door.RECORD
    assert here_this_week.path_of(KEEPER) is not None
    # and "founder" is still no one's to join as
    with pytest.raises(world.hearth.members.MemberError):
        world.hearth.members.validate_pseudonym(KEEPER)


def test_an_old_name_finds_its_holder_and_a_sign_in_is_never_shown(world):
    members = world.hearth.members
    members.set_name(ALDER, "oakley")  # from before ids: its old lines name its id
    members.set_name(HAZEL, "willow")  # a joining name
    members.set_name(HAZEL, "birch")  # and the name now
    members.set_sign_in(HAZEL, SIGN_IN)
    assert members.id_of_written("the founder") == KEEPER
    assert members.id_of_written("founder") == KEEPER
    assert members.id_of_written(ALDER) == ALDER
    assert members.id_of_written("oakley") == ALDER
    assert members.id_of_written("willow") == HAZEL
    assert members.id_of_written("birch") == HAZEL
    assert members.id_of_written(SIGN_IN) == HAZEL
    assert members.id_of_written("no-one-at-all") is None
    assert members.shown_for("willow") == "willow"  # as written
    assert members.shown_for(ALDER) == ALDER
    assert members.shown_for(SIGN_IN) == "birch"  # never the sign-in


def test_people_json_colours_lines_written_under_old_names(world):
    members = world.hearth.members
    members.set_name(ALDER, "oakley")
    members.set_name(HAZEL, "willow")
    members.set_name(HAZEL, "birch")
    members.set_sign_in(HAZEL, SIGN_IN)
    for who, hue in ((KEEPER, FOUNDER_HUE), (ALDER, ALDER_HUE), (HAZEL, HAZEL_HUE)):
        coloured(world, who, hue)
    commons = world.data / "commons"
    commons.mkdir(exist_ok=True)
    (commons / "acts.md").write_text(
        "2026-10-12 · the founder · wrote letters.\n"
        "2026-10-12 · alder · knocked at a door.\n"
        "2026-10-13 · willow · wrote notes.\n"
        "2026-10-14 · %s · posted on the board.\n"
        "2026-10-15 · oakley · wrote letters.\n" % SIGN_IN, encoding="utf-8")
    with (commons / "events.md").open("a", encoding="utf-8") as events:
        events.write("- 2026-10-14 · letter · willow wrote a letter\n")
    said = json.loads(world.client.get("/commons/people.json").get_data(as_text=True))
    assert said == [{"name": "the founder", "hue": FOUNDER_HUE},
                    {"name": "alder", "hue": ALDER_HUE},
                    {"name": "willow", "hue": HAZEL_HUE},
                    {"name": "birch", "hue": HAZEL_HUE},
                    {"name": "oakley", "hue": ALDER_HUE}]
    acts = world.client.get("/commons/acts.md").get_data(as_text=True)
    assert SIGN_IN not in acts
    assert "2026-10-14 · birch · posted on the board.\n" in acts
    assert "2026-10-13 · willow · wrote notes.\n" in acts  # every other line as written
    assert SIGN_IN not in json.dumps(said)


def test_new_lines_of_acts_name_the_founder_and_find_its_colour(world):
    import daily_acts
    assert (KEEPER, "the founder") in daily_acts.people()
    coloured(world, KEEPER, FOUNDER_HUE)
    said = json.loads(world.client.get("/commons/people.json").get_data(as_text=True))
    assert {"name": "the founder", "hue": FOUNDER_HUE} in said


def test_here_json_gives_the_founder_its_colour(world, monkeypatch):
    coloured(world, KEEPER, FOUNDER_HUE)
    monkeypatch.setattr(world.hearth, "recently_here", lambda: ([], [KEEPER]))
    said = json.loads(world.client.get("/commons/here.json").get_data(as_text=True))
    assert said["people"] == [{"name": "the founder", "address": "founder",
                               "hue": FOUNDER_HUE}]


# ---- 2. the keeper's room link ----------------------------------------------------------

def a_room_with_the_founder(world):
    import knock
    knock.write({"from": KEEPER, "to": "second", "at": "2026-10-15T09-00-00Z",
                 "note": "A knock from the founder.", "introduction": None,
                 "told_at": "2026-10-15T12-00-00Z", "answer": knock.YES,
                 "answered_at": "2026-10-15T12-00-00Z", "reply": None,
                 "answer_told_at": None, "waits_for_room": False, "set_up_at": None})
    made = knock.make_room(KEEPER, "second", AT, anyway=True)
    assert made["room"] == "second-founder"


def test_tides_links_the_keeper_s_own_room_with_an_agent(world):
    import rooms
    a_room_with_the_founder(world)
    assert "second-founder" in [room.id for room in rooms.of(KEEPER)]
    keeper = keeper_client(world)
    tides = page(keeper.get("/tides"))
    assert 'href="/rooms/second-founder#wakings"' in tides
    assert 'href="/rooms/second#wakings"' not in tides  # its room with a member
    assert keeper.get("/rooms/second-founder").status_code == 200


def test_tides_has_no_room_link_for_an_agent_the_keeper_has_no_room_with(world):
    keeper = keeper_client(world)
    assert 'href="/rooms/second#wakings"' not in page(keeper.get("/tides"))


# ---- 3. /tides askings ------------------------------------------------------------------

def test_tides_askings_one_spacing_field_each_with_its_value(world):
    import askings
    askings.set_queue("people", ALDER, ["own_name"])
    askings.set_every_days("people", ALDER, 4)
    keeper = keeper_client(world)
    tides = page(keeper.get("/tides"))
    section = tides[tides.index('id="askings"'):]
    section = section[:section.index("</section>")]
    subjects = section.count("<article>")
    assert subjects >= 2  # the agents and alder
    assert section.count('name="days"') == subjects
    assert "Keep this" not in section
    assert "now every 4 days" in section and 'value="4"' in section
    assert "now every 3 days" in section  # the first one's, by default
    # no raw switch list for a member: plain names, and a place for each
    assert "from " + ", ".join(askings.ASK_FIRST) not in section
    assert "<textarea" not in section
    assert askings.ASK_FIRST["own_name"]["name"] in section
    assert 'name="place-own_name"' in section


def test_a_member_s_order_is_set_by_places(world):
    import askings
    askings.set_queue("people", ALDER, [])
    keeper = keeper_client(world)
    people = [s for s in askings.ASK_FIRST if s != askings.META
              and askings.for_kind(s, "people")]
    form = {"kind": "people", "who": ALDER, "place-own_name": "1"}
    answer = post(keeper, "/tides/askings/order", data=form)
    assert "The order of what waits is kept." in page(answer)
    assert askings.queue_of("people", ALDER) == ["own_name"]
    if len(people) > 1:
        other = next(s for s in people if s != "own_name")
        post(keeper, "/tides/askings/order", data={"kind": "people", "who": ALDER,
                                                   "place-own_name": "2", "place-" + other: "1"})
        assert askings.queue_of("people", ALDER) == [other, "own_name"]
    answer = post(keeper, "/tides/askings/order",
                  data={"kind": "people", "who": ALDER, "place-own_name": "first"})
    assert "That order was not kept" in page(answer)
